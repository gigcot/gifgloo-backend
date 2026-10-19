"""
AI 처리 Lambda 핸들러 — 합성 파이프라인 전체 오케스트레이션

resume_from으로 특정 단계부터 재개 가능
"""
import base64
import io
import json
import math
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import boto3
from openai import OpenAI
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener
from shared.r2_config import private_bucket_name
from shared.exceptions import ExternalServiceException, ValidationException

BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "gifgloo")
PRIVATE_BUCKET_NAME = private_bucket_name()
UPLOAD_BUCKET_NAME = os.environ["R2_UPLOAD_BUCKET_NAME"]
SPEC_MODEL = "gpt-6-luna"
IMAGE_MODEL = "gpt-image-2.5-flare"
LEGACY_IMAGE_MODEL = "gpt-image-1.5"
DRAFT_SIZE = "1024x1024"
IMAGE_START_INTERVAL_SECONDS = 0.5
MAX_IMAGE_WORKERS = 20
GIF_PROCESSOR_FUNCTION = "gifgloo-gif-processor"

INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "")

SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "sparse_composition_plan.txt")
with open(SYSTEM_PROMPT_PATH) as f:
    SYSTEM_PROMPT = f.read()

def _response_format(frame_count: int) -> dict:
    text = {"type": "string"}
    strings = {"type": "array", "items": text}

    def obj(properties):
        return {"type": "object", "properties": properties,
                "required": list(properties), "additionalProperties": False}

    frame_index = {"type": "integer", "minimum": 0, "maximum": frame_count - 1}
    schema = obj({
        "source_reading": obj({"possible_uses": strings, "defining_cues": strings}),
        "replacement": obj({"base_subject": text, "target_subject": text, "scope": text,
                            "identity_features": strings, "adaptation": text}),
        "draft": obj({"reference_frame": frame_index, "appearance_plan": text}),
        "integration_notes": strings,
        "frame_exceptions": {"type": "array", "items": obj({
            "frame_idx": frame_index,
            "reason": {"type": "string", "enum": ["subject_selection", "anatomy_mapping", "interaction_ambiguity"]},
            "ambiguity": text, "instruction": text,
        })},
    })
    return {"type": "json_schema", "json_schema": {
        "name": "sparse_composition_plan", "strict": False, "schema": schema,
    }}


def _validate_spec(spec: dict, frame_count: int) -> None:
    if not 1 <= frame_count <= 20:
        raise ValidationException("합성 프레임 수는 1~20장이어야 합니다")

    def check(value, rule):
        kind = rule["type"]
        if kind == "object":
            if not isinstance(value, dict) or set(value) != set(rule["required"]):
                raise ExternalServiceException("합성 계획의 필드가 올바르지 않습니다")
            for key, child in rule["properties"].items():
                check(value[key], child)
        elif kind == "array":
            if not isinstance(value, list):
                raise ExternalServiceException("합성 계획의 목록이 올바르지 않습니다")
            for item in value:
                check(item, rule["items"])
        elif kind == "string":
            if not isinstance(value, str) or not value.strip():
                raise ExternalServiceException("합성 계획에 빈 지시가 있습니다")
            if "enum" in rule and value not in rule["enum"]:
                raise ExternalServiceException("합성 계획의 예외 유형이 올바르지 않습니다")
        elif type(value) is not int or not rule["minimum"] <= value <= rule["maximum"]:
            raise ExternalServiceException("합성 계획의 프레임 번호가 범위를 벗어났습니다")

    check(spec, _response_format(frame_count)["json_schema"]["schema"])
    indices = [entry["frame_idx"] for entry in spec["frame_exceptions"]]
    if len(indices) != len(set(indices)):
        raise ExternalServiceException("합성 계획에 중복 프레임 예외가 있습니다")


def _frame_output_size(frame: bytes) -> str:
    with Image.open(io.BytesIO(frame)) as image:
        width, height = image.size
    ratio = width / height
    if not 1 / 3 <= ratio <= 3:
        raise ValidationException("합성할 GIF 비율은 가로:세로 1:3~3:1 범위여야 합니다")
    output_width = round(math.sqrt(1048576 * ratio) / 16) * 16
    output_height = round(math.sqrt(1048576 / ratio) / 16) * 16
    if output_width > 3 * output_height:
        output_height = math.ceil(output_width / 3 / 16) * 16
    elif output_height > 3 * output_width:
        output_width = math.ceil(output_height / 3 / 16) * 16
    return f"{output_width}x{output_height}"


STAGE_ORDER = ["EXTRACTING_FRAMES", "ANALYZING", "GENERATING_DRAFT", "COMPOSITING", "BUILDING_GIF"]

openai_client = OpenAI(max_retries=6)
register_heif_opener()


class ImageRequestPacer:
    def __init__(self):
        self._lock = Lock()
        self._last_started_at: float | None = None

    def start(self) -> float:
        with self._lock:
            if self._last_started_at is not None:
                remaining = self._last_started_at + IMAGE_START_INTERVAL_SECONDS - time.monotonic()
                if remaining > 0:
                    time.sleep(remaining)
            self._last_started_at = time.monotonic()
            return self._last_started_at

    def elapsed_seconds(self) -> float | None:
        with self._lock:
            if self._last_started_at is None:
                return None
            return time.monotonic() - self._last_started_at

MAX_TARGET_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_TARGET_IMAGE_PIXELS = 20_000_000
MAX_TARGET_IMAGE_EDGE = 2048
ALLOWED_TARGET_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF", "HEIC"}


# ── R2 클라이언트 ─────────────────────────────────────────────

def _r2_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def _download(client, key: str) -> bytes:
    resp = client.get_object(Bucket=PRIVATE_BUCKET_NAME, Key=key)
    return resp["Body"].read()


def _upload_png(client, key: str, data: bytes) -> None:
    client.put_object(Bucket=PRIVATE_BUCKET_NAME, Key=key, Body=data, ContentType="image/png", CacheControl="private, no-store")


def _normalize_target(client, target_key: str, upload_key: str | None) -> None:
    source_bucket = UPLOAD_BUCKET_NAME if upload_key else PRIVATE_BUCKET_NAME
    source_key = upload_key or target_key
    try:
        response = client.get_object(Bucket=source_bucket, Key=source_key)
        data = response["Body"].read(MAX_TARGET_UPLOAD_BYTES + 1)
        if len(data) > MAX_TARGET_UPLOAD_BYTES:
            raise ValueError("업로드 이미지가 15MB를 초과합니다")

        try:
            with Image.open(io.BytesIO(data)) as opened:
                if opened.format not in ALLOWED_TARGET_FORMATS:
                    raise ValueError("지원하지 않는 이미지 형식입니다")
                width, height = opened.size
                if width < 1 or height < 1 or width * height > MAX_TARGET_IMAGE_PIXELS:
                    raise ValueError("이미지 해상도가 너무 큽니다")
                opened.seek(0)
                normalized = ImageOps.exif_transpose(opened)
                normalized.thumbnail((MAX_TARGET_IMAGE_EDGE, MAX_TARGET_IMAGE_EDGE))
                if normalized.mode not in {"RGB", "RGBA"}:
                    normalized = normalized.convert("RGBA" if "A" in normalized.getbands() else "RGB")
                output = io.BytesIO()
                normalized.save(output, format="PNG", optimize=True)
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("손상되었거나 지원하지 않는 이미지입니다") from exc

        _upload_png(client, target_key, output.getvalue())
    finally:
        if upload_key:
            client.delete_object(Bucket=UPLOAD_BUCKET_NAME, Key=upload_key)


# ── EC2 콜백 ──────────────────────────────────────────────────

def _ec2_post(callback_url: str, path: str, data: dict) -> None:
    url = f"{callback_url}/internal{path}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "X-Internal-Secret": INTERNAL_SECRET},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def _checkpoint(callback_url: str, job_id: str, run_id: str, stage: str, **kwargs) -> None:
    _ec2_post(callback_url, f"/compositions/{job_id}/checkpoint", {"run_id": run_id, "stage": stage, **kwargs})


def _record_edit(callback_url: str, job_id: str, run_id: str, elapsed_seconds: float = 0) -> None:
    _ec2_post(callback_url, f"/compositions/{job_id}/edit-started", {"run_id": run_id, "elapsed_seconds": elapsed_seconds})


def _complete(callback_url: str, job_id: str, run_id: str, draft_key: str, result_key: str, last_edit_elapsed_seconds: float | None) -> None:
    try:
        _ec2_post(callback_url, f"/compositions/{job_id}/complete", {"run_id": run_id, "draft_key": draft_key, "result_key": result_key, "last_edit_elapsed_seconds": last_edit_elapsed_seconds})
    except urllib.request.HTTPError as e:
        if e.code == 409:
            return
        raise


def _fail(callback_url: str, job_id: str, run_id: str, reason: str, last_edit_elapsed_seconds: float | None) -> None:
    try:
        _ec2_post(callback_url, f"/compositions/{job_id}/fail", {"run_id": run_id, "reason": reason, "last_edit_elapsed_seconds": last_edit_elapsed_seconds})
    except urllib.request.HTTPError as e:
        if e.code == 409:
            return
        raise


# ── GIF 프로세서 Lambda 호출 ──────────────────────────────────

def _invoke_gif_processor(payload: dict) -> dict:
    client = boto3.client("lambda", region_name="ap-northeast-2")
    response = client.invoke(
        FunctionName=GIF_PROCESSOR_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )
    result = json.loads(response["Payload"].read())
    if "errorMessage" in result:
        raise RuntimeError(f"GIF 처리 Lambda 오류: {result['errorMessage']}")
    return result


# ── 키 패턴 ───────────────────────────────────────────────────

def _target_key(job_id: str) -> str:
    return f"compositions/{job_id}/target.png"


def _draft_key(job_id: str) -> str:
    return f"compositions/{job_id}/draft.png"


def _result_key(job_id: str) -> str:
    return f"compositions/{job_id}/result.gif"


def _frame_key(job_id: str, idx: int) -> str:
    return f"temp/{job_id}/frame_{idx:04d}.png"


def _composited_key(job_id: str, idx: int) -> str:
    return f"temp/{job_id}/composited_{idx:04d}.png"


# ── 재개 판단 ─────────────────────────────────────────────────

def _should_run(stage: str, resume_from: str | None) -> bool:
    if resume_from is None:
        return True
    return STAGE_ORDER.index(stage) >= STAGE_ORDER.index(resume_from)


# ── 프롬프트 빌더 ─────────────────────────────────────────────

def _build_legacy_draft_prompt(spec: dict, white_bg: bool = True) -> str:
    object_draft = spec["object_draft"]
    composite_type = object_draft["type"]
    note = object_draft.get("note", {})
    base_obj = object_draft["object_match"]["base"]
    target_obj = object_draft["object_match"]["target"]
    bg_desc = "a plain white background" if white_bg else "a transparent background"

    if composite_type == "replace":
        return (
            "<context>\n"
            "This is the draft generation step of a meme GIF + user image compositing pipeline.\n"
            "The draft object is a reference image used as an anchor when compositing each frame.\n"
            "</context>\n\n"
            "<images>\nImage 1 (TARGET): The user's personal image.\n</images>\n\n"
            "<task>\n"
            f"Object: {target_obj}\n\n"
            f"Output only the object from this image on {bg_desc}.\n"
            "Remove all background and surrounding scene elements.\n"
            "If any part of the object is occluded, infer and reconstruct the hidden portions.\n"
            "The result should be a complete, natural-looking object ready for compositing reference.\n"
            "</task>"
        )
    else:
        note_lines = "\n".join(f"- {k}: {v}" for k, v in note.items())
        return (
            "<context>\n"
            "This is the draft generation step of a meme GIF + user image compositing pipeline.\n"
            "The draft object is a reference image used as an anchor when compositing each frame.\n"
            "The TARGET is the user's personal image.\n"
            "</context>\n\n"
            "<images>\n"
            "Image 1 (BASE FRAME): A reference frame from the base GIF.\n"
            "Image 2 (TARGET): The user's personal image.\n"
            "</images>\n\n"
            "<task>\n"
            f"Base object: {base_obj}\n"
            f"Target object: {target_obj}\n\n"
            "Edit the TARGET according to the order below.\n"
            f"Output the result on {bg_desc} — object only, no background, no surrounding scene.\n"
            "Preserve everything from the TARGET not covered by the order.\n"
            "</task>\n\n"
            f"<order>\n{note_lines}\n</order>"
        )


def _build_legacy_frame_prompt(spec: dict, frame_idx: int) -> str:
    frame_dir_map = {fd["frame_idx"]: fd for fd in spec["frame_directions"]}
    base_obj = spec["object_draft"]["object_match"]["base"]
    preserve = spec.get("preserve", "")
    frame_dir = frame_dir_map.get(frame_idx, {"frame_idx": frame_idx, "description": ""})
    description = frame_dir.get("description", "")

    prompt = (
        "<context>\n"
        "This is an individual frame compositing task within a GIF compositing pipeline.\n"
        "Image 1 (BASE FRAME): The base GIF frame to edit.\n"
        "Image 2 (DRAFT OBJECT): The replacement object to place into the BASE FRAME.\n"
        f"The DRAFT OBJECT replaces '{base_obj}' in the BASE FRAME.\n"
        "</context>\n\n"
        f"<object_match>\nbase: {base_obj}\n</object_match>\n\n"
        f"<direction>\n{description}\n</direction>\n\n"
    )
    if preserve:
        prompt += f"<preserve>\n{preserve}\n</preserve>\n\n"

    prompt += (
        "<task>\n"
        "Generate the output image by placing the DRAFT OBJECT into the BASE FRAME "
        "according to the direction.\n"
        "Only modify the area related to the object_match. "
        "Keep everything else in the BASE FRAME exactly as it appears.\n"
    )
    if preserve:
        prompt += (
            "The preserve field lists elements that are fixed in position, size, and form "
            "across all frames — these must not be altered.\n"
        )
    prompt += "</task>"
    return prompt


def _build_draft_prompt(spec: dict) -> str:
    return f'''Create ONE source-anchored identity-reference draft for a personalized GIF.
Image 1 is the selected BASE reference frame. It governs the current orientation,
posture, expression configuration and intensity, framing, and visible/cropped parts
of the replacement subject in this single draft, as well as source rendering.
Image 2 is TARGET. It supplies recognizable identity and stable appearance only.

Fixed replacement plan:
{json.dumps(spec['replacement'], ensure_ascii=False)}
Stable appearance and adaptation plan:
{spec['draft']['appearance_plan']}

Show only the selected replacement scope as it would appear in Image 1 after identity
transfer, isolated on a plain white background. Keep TARGET identity recognizable,
adapting anatomy or appearance only as required by the fixed replacement plan.
Do not turn the subject toward the camera, straighten its pose, neutralize or replace
its expression, or reveal hidden details merely to make identity easier to recognize.
When removing surrounding objects or actors, retain the subject's visible configuration;
do not restage it as a portrait. Do not add unrelated body regions to a head-only scope.
Do not copy TARGET's photographed pose, expression, scene, or unrelated props.
Omit BASE scene props, other actors, captions, and surrounding background.
This draft captures one selected BASE state. Later GIF frames will reuse its stable
identity/adaptation only, while their own BASE images supply their pose and expression.
'''


def _build_frame_prompt(spec: dict, frame_idx: int) -> str:
    exceptions = [item for item in spec['frame_exceptions'] if item['frame_idx'] == frame_idx]
    extra = ''
    if exceptions:
        extra = '\nFrame-specific decision:\n' + exceptions[0]['instruction'] + '\n'
    return f'''Edit Image 1 (CURRENT BASE FRAME) by transferring the selected subject identity
from Image 2 (DRAFT IDENTITY REFERENCE). Do not create a new scene or animation pose.

Replacement plan:
{json.dumps(spec['replacement'], ensure_ascii=False)}

Source meaning, for preservation only:
{json.dumps(spec['source_reading'], ensure_ascii=False)}
These are possible uses and defining cues, not instructions to enact a generic emotion.
Keep cues only in the configuration and intensity actually visible in CURRENT BASE.

Shared integration decisions:
{json.dumps(spec['integration_notes'], ensure_ascii=False)}
{extra}
FIXED EDIT RULES
1. CURRENT BASE governs actual pose, expression, gaze, head/body angle, subject placement,
   relative scale, framing and crop. Read them directly from Image 1. Preserve its subtle
   configuration and intensity, including meaningful asymmetry or stylization; do not
   exaggerate a reaction or normalize away visible exaggeration.
2. DRAFT governs recognizable identity and the planned stable appearance/adaptation only.
   Do not copy its pose, expression, orientation, crop, white background or extra objects.
3. Change only the selected replacement scope. Keep current-frame unrelated actors,
   background, visible text, objects and their positions/shapes as they appear in BASE.
   Match lighting and perspective to BASE. Do not freeze things across the whole clip.
4. Preserve current-frame contacts, depth ordering and occlusions. A cropped/hidden part
   stays cropped/hidden even if DRAFT shows it; if the subject is absent, do not add it.
   Adapt anatomy only as needed for the actual source configuration. Do not invent
   hidden or ambiguous details, move a prop to accommodate DRAFT, or add a new gesture.
5. If any textual interpretation conflicts with visible evidence, CURRENT BASE wins.
   Output this one edited frame, with no extra labels, panels, or decorative additions.
'''


# ── AI 액션 ───────────────────────────────────────────────────

def analyze(frame_keys: list[str], target_key: str) -> dict:
    r2 = _r2_client()
    if not 1 <= len(frame_keys) <= 20:
        raise ValidationException("합성 프레임 수는 1~20장이어야 합니다")
    content = []
    for i, key in enumerate(frame_keys):
        frame = _download(r2, key)
        if i == 0:
            _frame_output_size(frame)
        b64 = base64.b64encode(frame).decode()
        content.append({"type": "text", "text": f"Image {i} (GIF Frame {i}):"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    b64_target = base64.b64encode(_download(r2, target_key)).decode()
    content.append({"type": "text", "text": "(TARGET):"})
    content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_target}"}})

    response = openai_client.chat.completions.create(
        model=SPEC_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format=_response_format(len(frame_keys)),
        max_completion_tokens=16000,
        store=False,
    )
    choice = response.choices[0]
    if choice.finish_reason != "stop" or choice.message.refusal or not choice.message.content:
        raise ExternalServiceException("합성 계획 생성이 완료되지 않았습니다")
    try:
        spec = json.loads(choice.message.content)
    except json.JSONDecodeError as exc:
        raise ExternalServiceException("합성 계획 응답이 올바른 JSON이 아닙니다") from exc
    _validate_spec(spec, len(frame_keys))
    return spec


def generate_draft(target_key: str, ref_frame_key: str | None, spec: dict, draft_key: str, callback_url: str, job_id: str, run_id: str, pacer: ImageRequestPacer) -> None:
    r2 = _r2_client()


    legacy = "object_draft" in spec
    prompt = _build_legacy_draft_prompt(spec) if legacy else _build_draft_prompt(spec)
    images = []
    if ref_frame_key:
        images.append(("base_frame.png", io.BytesIO(_download(r2, ref_frame_key)), "image/png"))
    images.append(("target.png", io.BytesIO(_download(r2, target_key)), "image/png"))

    _record_edit(callback_url, job_id, run_id)
    pacer.start()
    response = openai_client.with_options(max_retries=0).images.edit(
        model=LEGACY_IMAGE_MODEL if legacy else IMAGE_MODEL,
        image=images,
        prompt=prompt,
        quality="low",
        n=1,
        size=DRAFT_SIZE,
        output_format="png",
    )
    _upload_png(r2, draft_key, base64.b64decode(response.data[0].b64_json))


def _composite_one(r2, openai_client, frame_data: bytes, draft_data: bytes, spec: dict, frame_idx: int, job_id: str, mark_edit_started, output_size: str) -> str:
    output_key = _composited_key(job_id, frame_idx)
    legacy = "object_draft" in spec
    prompt = _build_legacy_frame_prompt(spec, frame_idx) if legacy else _build_frame_prompt(spec, frame_idx)
    images = [
        ("frame.png", io.BytesIO(frame_data), "image/png"),
        ("draft.png", io.BytesIO(draft_data), "image/png"),
    ]
    mark_edit_started()
    response = openai_client.with_options(max_retries=0).images.edit(
        model=LEGACY_IMAGE_MODEL if legacy else IMAGE_MODEL,
        image=images,
        prompt=prompt,
        quality="low",
        n=1,
        size=output_size,
        output_format="png",
    )
    _upload_png(r2, output_key, base64.b64decode(response.data[0].b64_json))
    return output_key


def composite_frames(job_id: str, run_id: str, callback_url: str, frame_keys: list[str], draft_key: str, spec: dict, pacer: ImageRequestPacer) -> dict:
    r2 = _r2_client()
    draft_data = _download(r2, draft_key)
    frames = [_download(r2, frame_key) for frame_key in frame_keys]
    if "object_draft" in spec:
        output_size = DRAFT_SIZE
    else:
        _validate_spec(spec, len(frames))
        output_size = _frame_output_size(frames[0])
    _record_edit(callback_url, job_id, run_id)

    try:
        with ThreadPoolExecutor(max_workers=min(MAX_IMAGE_WORKERS, len(frame_keys))) as executor:
            futures = [
                executor.submit(_composite_one, r2, openai_client, frame_data, draft_data, spec, i, job_id, pacer.start, output_size)
                for i, frame_data in enumerate(frames)
            ]
            composited_keys = [f.result() for f in futures]
    finally:
        elapsed = pacer.elapsed_seconds()
        if elapsed is not None:
            _record_edit(callback_url, job_id, run_id, elapsed)

    return {"composited_keys": composited_keys}


# ── 파이프라인 ────────────────────────────────────────────────

def run_pipeline(event: dict, run_id: str) -> None:
    job_id = event["job_id"]
    gif_url = event["gif_url"]
    callback_url = event["callback_url"]
    resume_from = event.get("resume_from")
    durations_ms = event.get("durations_ms")
    spec_data = event.get("spec")
    r2 = _r2_client()

    target_key = _target_key(job_id)
    draft_key = _draft_key(job_id)
    result_key = _result_key(job_id)
    pacer = ImageRequestPacer()

    try:
        _normalize_target(r2, target_key, event.get("target_upload_key"))
        if _should_run("EXTRACTING_FRAMES", resume_from):
            _checkpoint(callback_url, job_id, run_id, "EXTRACTING_FRAMES")
            gif_result = _invoke_gif_processor({
                "action": "extract_frames",
                "gif_url": gif_url,
                "max_frames": event["max_frames"],
                "job_id": job_id,
            })
            durations_ms = gif_result["durations_ms"]

        frame_keys = [_frame_key(job_id, i) for i in range(len(durations_ms))]

        if _should_run("ANALYZING", resume_from):
            _checkpoint(callback_url, job_id, run_id, "ANALYZING", durations_ms=durations_ms)
            spec_data = analyze(frame_keys, target_key)

        if _should_run("GENERATING_DRAFT", resume_from):
            if "object_draft" in spec_data:
                ref_index = spec_data["draft_reference_frame"]
                ref_frame_key = frame_keys[ref_index] if ref_index is not None else None
            else:
                _validate_spec(spec_data, len(frame_keys))
                ref_frame_key = frame_keys[spec_data["draft"]["reference_frame"]]
            _checkpoint(callback_url, job_id, run_id, "GENERATING_DRAFT", spec=spec_data)
            generate_draft(target_key, ref_frame_key, spec_data, draft_key, callback_url, job_id, run_id, pacer)

        if _should_run("COMPOSITING", resume_from):
            _checkpoint(callback_url, job_id, run_id, "COMPOSITING")
            composite_frames(job_id, run_id, callback_url, frame_keys, draft_key, spec_data, pacer)

        _checkpoint(callback_url, job_id, run_id, "BUILDING_GIF")
        composited_keys = [_composited_key(job_id, i) for i in range(len(durations_ms))]
        _invoke_gif_processor({
            "action": "build_gif",
            "frames_r2_keys": composited_keys,
            "durations_ms": durations_ms,
            "output_key": result_key,
        })

        _complete(callback_url, job_id, run_id, draft_key, result_key, pacer.elapsed_seconds())

    except Exception as e:
        _fail(callback_url, job_id, run_id, str(e), pacer.elapsed_seconds())


# ── 핸들러 ────────────────────────────────────────────────────

def handler(event, context):
    job_id = event["job_id"]
    callback_url = event["callback_url"]
    run_id = context.aws_request_id
    try:
        _ec2_post(callback_url, f"/compositions/{job_id}/start", {"run_id": run_id})
    except urllib.request.HTTPError as e:
        if e.code == 409:
            return
        raise
    run_pipeline(event, run_id)

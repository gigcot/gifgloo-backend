"""
AI 처리 Lambda 핸들러 — 합성 파이프라인 전체 오케스트레이션

resume_from으로 특정 단계부터 재개 가능
"""
import base64
import io
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import boto3
from openai import OpenAI

BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "gifgloo")
IMAGE_MODEL = "gpt-image-1.5"
OUTPUT_SIZE = "1024x1024"
MAX_FRAMES = 10
GIF_PROCESSOR_FUNCTION = "gifgloo-gif-processor"

EC2_INTERNAL_URL = os.environ.get("EC2_INTERNAL_URL", "")
INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "")

SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "comp_order_prompt_ver7.txt")
with open(SYSTEM_PROMPT_PATH) as f:
    SYSTEM_PROMPT = f.read()

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "composition_spec",
        "strict": False,
        "schema": {
            "type": "object",
            "properties": {
                "object_draft": {
                    "type": "object",
                    "properties": {
                        "object_match": {
                            "type": "object",
                            "properties": {
                                "base": {"type": "string"},
                                "target": {"type": "string"},
                            },
                            "required": ["base", "target"],
                        },
                        "type": {"type": "string", "enum": ["replace", "mix"]},
                        "note": {"type": "object"},
                    },
                    "required": ["object_match", "type", "note"],
                },
                "draft_reference_frame": {"type": ["integer", "null"]},
                "preserve": {"type": "string"},
                "frame_directions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "frame_idx": {"type": "integer"},
                            "description": {"type": "string"},
                        },
                        "required": ["frame_idx", "description"],
                    },
                },
            },
            "required": ["object_draft", "draft_reference_frame", "preserve", "frame_directions"],
        },
    },
}

STAGE_ORDER = ["EXTRACTING_FRAMES", "ANALYZING", "GENERATING_DRAFT", "COMPOSITING", "BUILDING_GIF"]

openai_client = OpenAI(max_retries=6)


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
    resp = client.get_object(Bucket=BUCKET_NAME, Key=key)
    return resp["Body"].read()


def _upload_png(client, key: str, data: bytes) -> None:
    client.put_object(Bucket=BUCKET_NAME, Key=key, Body=data, ContentType="image/png")


# ── EC2 콜백 ──────────────────────────────────────────────────

def _ec2_post(path: str, data: dict) -> None:
    url = f"{EC2_INTERNAL_URL}/internal{path}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "X-Internal-Secret": INTERNAL_SECRET},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def _checkpoint(job_id: str, stage: str, **kwargs) -> None:
    _ec2_post(f"/compositions/{job_id}/checkpoint", {"stage": stage, **kwargs})


def _complete(job_id: str, draft_key: str, result_key: str) -> None:
    try:
        _ec2_post(f"/compositions/{job_id}/complete", {"draft_key": draft_key, "result_key": result_key})
    except urllib.request.HTTPError as e:
        if e.code == 409:
            return
        raise


def _fail(job_id: str, reason: str) -> None:
    _ec2_post(f"/compositions/{job_id}/fail", {"reason": reason})


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

def _build_draft_prompt(spec: dict, white_bg: bool = True) -> str:
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


def _build_frame_prompt(spec: dict, frame_idx: int) -> str:
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


# ── AI 액션 ───────────────────────────────────────────────────

def analyze(frame_keys: list[str], target_key: str) -> dict:
    r2 = _r2_client()


    content = []
    for i, key in enumerate(frame_keys):
        b64 = base64.b64encode(_download(r2, key)).decode()
        content.append({"type": "text", "text": f"Image {i} (GIF Frame {i}):"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    b64_target = base64.b64encode(_download(r2, target_key)).decode()
    content.append({"type": "text", "text": "(TARGET):"})
    content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_target}"}})

    response = openai_client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format=RESPONSE_FORMAT,
    )
    return json.loads(response.choices[0].message.content)


def generate_draft(target_key: str, ref_frame_key: str | None, spec: dict, draft_key: str) -> None:
    r2 = _r2_client()


    prompt = _build_draft_prompt(spec)
    images = []
    if ref_frame_key:
        images.append(("base_frame.png", io.BytesIO(_download(r2, ref_frame_key)), "image/png"))
    images.append(("target.png", io.BytesIO(_download(r2, target_key)), "image/png"))

    response = openai_client.images.edit(
        model=IMAGE_MODEL,
        image=images,
        prompt=prompt,
        quality="low",
        n=1,
        size=OUTPUT_SIZE,
        output_format="png",
    )
    _upload_png(r2, draft_key, base64.b64decode(response.data[0].b64_json))


def _composite_one(r2, openai_client, frame_key: str, draft_key: str, spec: dict, frame_idx: int, job_id: str) -> str:
    output_key = _composited_key(job_id, frame_idx)
    prompt = _build_frame_prompt(spec, frame_idx)
    images = [
        ("frame.png", io.BytesIO(_download(r2, frame_key)), "image/png"),
        ("draft.png", io.BytesIO(_download(r2, draft_key)), "image/png"),
    ]
    response = openai_client.images.edit(
        model=IMAGE_MODEL,
        image=images,
        prompt=prompt,
        quality="low",
        n=1,
        size=OUTPUT_SIZE,
    )
    _upload_png(r2, output_key, base64.b64decode(response.data[0].b64_json))
    return output_key


def composite_frames(job_id: str, frame_keys: list[str], draft_key: str, spec: dict) -> dict:
    r2 = _r2_client()


    with ThreadPoolExecutor(max_workers=len(frame_keys)) as executor:
        futures = [
            executor.submit(_composite_one, r2, openai_client, fk, draft_key, spec, i, job_id)
            for i, fk in enumerate(frame_keys)
        ]
        composited_keys = [f.result() for f in futures]

    return {"composited_keys": composited_keys}


# ── 파이프라인 ────────────────────────────────────────────────

def run_pipeline(event: dict) -> None:
    job_id = event["job_id"]
    gif_url = event["gif_url"]
    resume_from = event.get("resume_from")
    durations_ms = event.get("durations_ms")
    spec_data = event.get("spec")

    target_key = _target_key(job_id)
    draft_key = _draft_key(job_id)
    result_key = _result_key(job_id)

    try:
        if _should_run("EXTRACTING_FRAMES", resume_from):
            _checkpoint(job_id, "EXTRACTING_FRAMES")
            gif_result = _invoke_gif_processor({
                "action": "extract_frames",
                "gif_url": gif_url,
                "max_frames": MAX_FRAMES,
                "job_id": job_id,
            })
            durations_ms = gif_result["durations_ms"]

        frame_keys = [_frame_key(job_id, i) for i in range(len(durations_ms))]

        if _should_run("ANALYZING", resume_from):
            _checkpoint(job_id, "ANALYZING", durations_ms=durations_ms)
            spec_data = analyze(frame_keys, target_key)

        if _should_run("GENERATING_DRAFT", resume_from):
            _checkpoint(job_id, "GENERATING_DRAFT", spec=spec_data)
            ref_frame_key = frame_keys[spec_data["draft_reference_frame"]] if spec_data.get("draft_reference_frame") is not None else None
            generate_draft(target_key, ref_frame_key, spec_data, draft_key)

        if _should_run("COMPOSITING", resume_from):
            _checkpoint(job_id, "COMPOSITING")
            composite_frames(job_id, frame_keys, draft_key, spec_data)

        _checkpoint(job_id, "BUILDING_GIF")
        composited_keys = [_composited_key(job_id, i) for i in range(len(durations_ms))]
        _invoke_gif_processor({
            "action": "build_gif",
            "frames_r2_keys": composited_keys,
            "durations_ms": durations_ms,
            "output_key": result_key,
        })

        _complete(job_id, draft_key, result_key)

    except Exception as e:
        _fail(job_id, str(e))
        raise


# ── 핸들러 ────────────────────────────────────────────────────

def handler(event, context):
    run_pipeline(event)

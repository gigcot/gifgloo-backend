"""
AI 처리 Lambda 핸들러 — OpenAI 기반

액션:
  analyze         : frame_keys + target_key → CompositionSpec JSON
  generate_draft  : target_key + spec → draft_key에 PNG 저장
  composite_frame : frame_key + draft_key + spec + frame_idx → output_key에 PNG 저장
"""
import base64
import io
import json
import os

import boto3
from openai import OpenAI

BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "gifgloo")
IMAGE_MODEL = "gpt-image-1.5"
OUTPUT_SIZE = "1024x1024"

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


# ── 액션 ──────────────────────────────────────────────────────

def analyze(frame_keys: list[str], target_key: str) -> dict:
    r2 = _r2_client()
    openai_client = OpenAI()

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
    openai_client = OpenAI()

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
    draft_bytes = base64.b64decode(response.data[0].b64_json)
    _upload_png(r2, draft_key, draft_bytes)


def _composited_frame_key(job_id: str, frame_idx: int) -> str:
    return f"temp/{job_id}/composited_{frame_idx:04d}.png"


def _composite_one(r2, openai_client, frame_key: str, draft_key: str, spec: dict, frame_idx: int, job_id: str) -> str:
    output_key = _composited_frame_key(job_id, frame_idx)
    prompt = _build_frame_prompt(spec, frame_idx)
    draft_bytes = _download(r2, draft_key)
    images = [
        ("frame.png", io.BytesIO(_download(r2, frame_key)), "image/png"),
        ("draft.png", io.BytesIO(draft_bytes), "image/png"),
    ]
    response = openai_client.images.edit(
        model=IMAGE_MODEL,
        image=images,
        prompt=prompt,
        quality="low",
        n=1,
        size=OUTPUT_SIZE,
    )
    result_bytes = base64.b64decode(response.data[0].b64_json)
    _upload_png(r2, output_key, result_bytes)
    return output_key


def composite_frames(job_id: str, frame_keys: list[str], draft_key: str, spec: dict) -> dict:
    from concurrent.futures import ThreadPoolExecutor

    r2 = _r2_client()
    openai_client = OpenAI()

    with ThreadPoolExecutor(max_workers=len(frame_keys)) as executor:
        futures = [
            executor.submit(_composite_one, r2, openai_client, frame_key, draft_key, spec, i, job_id)
            for i, frame_key in enumerate(frame_keys)
        ]
        composited_keys = [f.result() for f in futures]

    return {"composited_keys": composited_keys}


# ── 핸들러 ────────────────────────────────────────────────────

def handler(event, context):
    action = event.get("action")

    if action == "analyze":
        return analyze(event["frame_keys"], event["target_key"])

    elif action == "generate_draft":
        generate_draft(event["target_key"], event.get("ref_frame_key"), event["spec"], event["draft_key"])
        return {"ok": True}

    elif action == "composite_frames":
        return composite_frames(event["job_id"], event["frame_keys"], event["draft_key"], event["spec"])

    else:
        raise ValueError(f"알 수 없는 액션: {action}")

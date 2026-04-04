import base64
import io

from openai import AsyncOpenAI

from composition.application.ports.outbound.ai.composition_analysis_port import CompositionSpec
from composition.application.ports.outbound.ai.image_inpainting_port import (
    ImageInpaintingPort,
    DraftGenerationCommand,
    FrameCompositingCommand,
)

IMAGE_MODEL = "gpt-image-1.5"
OUTPUT_SIZE = "1024x1024"


def _build_draft_prompt(spec: CompositionSpec, white_bg: bool = True) -> str:
    object_draft = spec.object_draft
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
    else:  # mix
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


def _build_frame_dir_map(spec: CompositionSpec) -> dict[int, dict]:
    return {fd["frame_idx"]: fd for fd in spec.frame_directions}


def _build_frame_prompt(spec: CompositionSpec, frame_idx: int, frame_dir_map: dict[int, dict]) -> str:
    base_obj = spec.object_draft["object_match"]["base"]
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
    if spec.preserve:
        prompt += f"<preserve>\n{spec.preserve}\n</preserve>\n\n"

    prompt += (
        "<task>\n"
        "Generate the output image by placing the DRAFT OBJECT into the BASE FRAME "
        "according to the direction.\n"
        "Only modify the area related to the object_match. "
        "Keep everything else in the BASE FRAME exactly as it appears.\n"
    )
    if spec.preserve:
        prompt += (
            "The preserve field lists elements that are fixed in position, size, and form "
            "across all frames — these must not be altered.\n"
        )
    prompt += "</task>"
    return prompt


class OpenAiInpaintingAdapter(ImageInpaintingPort):
    def __init__(self):
        self._client = AsyncOpenAI()
        self._frame_dir_map: dict[int, dict] | None = None

    async def generate_draft(self, command: DraftGenerationCommand) -> bytes:
        self._frame_dir_map = _build_frame_dir_map(command.spec)
        prompt = _build_draft_prompt(command.spec)

        images = []
        if command.spec.draft_reference_frame is not None and command.frames:
            ref_idx = command.spec.draft_reference_frame
            if ref_idx < len(command.frames):
                images.append(("base_frame.png", io.BytesIO(command.frames[ref_idx]), "image/png"))
        images.append(("target.png", io.BytesIO(command.target), "image/png"))

        response = await self._client.images.edit(
            model=IMAGE_MODEL,
            image=images,
            prompt=prompt,
            quality="low",
            n=1,
            size=OUTPUT_SIZE,
            output_format="png",
        )
        return base64.b64decode(response.data[0].b64_json)

    async def composite_frame(self, command: FrameCompositingCommand) -> bytes:
        if self._frame_dir_map is None:
            self._frame_dir_map = _build_frame_dir_map(command.spec)
        prompt = _build_frame_prompt(command.spec, command.frame_idx, self._frame_dir_map)
        images = [
            ("frame.png", io.BytesIO(command.frame), "image/png"),
            ("draft.png", io.BytesIO(command.draft), "image/png"),
        ]
        response = await self._client.images.edit(
            model=IMAGE_MODEL,
            image=images,
            prompt=prompt,
            quality="low",
            n=1,
            size=OUTPUT_SIZE,
        )
        return base64.b64decode(response.data[0].b64_json)

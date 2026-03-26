import base64
import json
from pathlib import Path

from openai import AsyncOpenAI

from composition.application.ports.outbound.ai.composition_analysis_port import (
    CompositionAnalysisPort,
    CompositionAnalysisCommand,
    CompositionSpec,
)

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "comp_order_prompt_ver7.txt").read_text()

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


class OpenAiCompositionAnalysisAdapter(CompositionAnalysisPort):
    def __init__(self, api_key: str):
        self._client = AsyncOpenAI(api_key=api_key)

    async def analyze(self, command: CompositionAnalysisCommand) -> CompositionSpec:
        content = []
        for i, frame in enumerate(command.frames):
            b64 = base64.b64encode(frame).decode()
            content.append({"type": "text", "text": f"Image {i} (GIF Frame {i}):"})
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

        b64_target = base64.b64encode(command.target).decode()
        content.append({"type": "text", "text": "(TARGET):"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_target}"}})

        response = await self._client.chat.completions.create(
            model="gpt-5.1-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            response_format=RESPONSE_FORMAT,
        )

        raw = json.loads(response.choices[0].message.content)
        return CompositionSpec(
            object_draft=raw["object_draft"],
            draft_reference_frame=raw["draft_reference_frame"],
            preserve=raw["preserve"],
            frame_directions=raw["frame_directions"],
        )

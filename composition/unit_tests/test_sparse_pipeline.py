import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from shared.exceptions import ExternalServiceException, ValidationException


ROOT = Path(__file__).resolve().parents[2]
ENV = {
    "R2_BUCKET_NAME": "test-public", "R2_PRIVATE_BUCKET_NAME": "test-private",
    "R2_UPLOAD_BUCKET_NAME": "test-uploads", "OPENAI_API_KEY": "test-not-a-real-key",
}


def load_handler(name):
    module_spec = importlib.util.spec_from_file_location(name, ROOT / "lambda" / name / "handler.py")
    module = importlib.util.module_from_spec(module_spec)
    with patch.dict(os.environ, ENV):
        module_spec.loader.exec_module(module)
    return module


def plan():
    return {
        "source_reading": {"possible_uses": [], "defining_cues": ["Keep the visible gesture."]},
        "replacement": {"base_subject": "foreground subject", "target_subject": "target subject",
                        "scope": "whole subject", "identity_features": ["distinctive hair"],
                        "adaptation": "Follow the source rendering."},
        "draft": {"reference_frame": 0, "appearance_plan": "Keep the target identity in the selected source state."},
        "integration_notes": [], "frame_exceptions": [],
    }


def legacy_plan():
    return {"object_draft": {"object_match": {"base": "person", "target": "dog"},
                             "type": "replace", "note": {}},
            "draft_reference_frame": None, "preserve": "background",
            "frame_directions": [{"frame_idx": 0, "description": "original direction"}]}


def png(size=(64, 48), color="red"):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, "PNG")
    return output.getvalue()


class MemoryStorage:
    def __init__(self, files=None):
        self.files = files or {}

    def get_object(self, *, Bucket, Key):
        return {"Body": io.BytesIO(self.files[Key])}

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        self.files[Key] = Body


class SparsePlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ai = load_handler("ai_processor")

    def test_schema_tracks_actual_frame_count_and_accepts_empty_exceptions(self):
        for count in (1, 6, 14, 20):
            self.ai._validate_spec(plan(), count)
            props = self.ai._response_format(count)["json_schema"]["schema"]["properties"]
            self.assertEqual(props["draft"]["properties"]["reference_frame"]["maximum"], count - 1)
            self.assertEqual(props["frame_exceptions"]["items"]["properties"]["frame_idx"]["maximum"], count - 1)

    def test_rejects_incomplete_out_of_range_and_duplicate_plans(self):
        bad = []
        item = plan(); del item["replacement"]; bad.append(item)
        item = plan(); item["draft"]["reference_frame"] = 3; bad.append(item)
        item = plan(); item["draft"]["reference_frame"] = True; bad.append(item)
        item = plan(); item["draft"]["appearance_plan"] = " "; bad.append(item)
        item = plan(); item["integration_notes"] = "not an array"; bad.append(item)
        exception = {"frame_idx": 1, "reason": "subject_selection", "ambiguity": "two subjects", "instruction": "replace left"}
        item = plan(); item["frame_exceptions"] = [exception, exception]; bad.append(item)
        item = plan(); item["frame_exceptions"] = [dict(exception, reason="invent_motion")]; bad.append(item)
        item = plan(); item["frame_exceptions"] = [dict(exception, frame_idx=3)]; bad.append(item)
        for item in bad:
            with self.subTest(item=item), self.assertRaises(ExternalServiceException):
                self.ai._validate_spec(item, 3)
        for count in (0, 21):
            with self.assertRaises(ValidationException):
                self.ai._validate_spec(plan(), count)

    def test_frame_exception_is_only_sent_to_its_frame(self):
        spec = plan()
        spec["frame_exceptions"] = [{"frame_idx": 1, "reason": "subject_selection",
                                     "ambiguity": "two subjects", "instruction": "ONLY_LEFT_SUBJECT"}]
        self.assertNotIn("ONLY_LEFT_SUBJECT", self.ai._build_frame_prompt(spec, 0))
        self.assertIn("ONLY_LEFT_SUBJECT", self.ai._build_frame_prompt(spec, 1))
        self.assertIn("if the subject is absent, do not add it", self.ai._build_frame_prompt(spec, 0))
        self.assertIn("do not restage it as a portrait", self.ai._build_draft_prompt(spec))
        self.assertIn("Later frame editors reuse stable identity/adaptation", self.ai.SYSTEM_PROMPT)

    def test_matched_size_respects_budget_alignment_and_extreme_valid_ratios(self):
        for source in ((512, 512), (640, 480), (480, 640), (480, 616), (1920, 1080), (3, 1), (1, 3), (299, 100), (100, 299)):
            with self.subTest(source=source):
                width, height = map(int, self.ai._frame_output_size(png(source)).split("x"))
                self.assertEqual(width % 16, 0)
                self.assertEqual(height % 16, 0)
                self.assertLessEqual(max(width, height), 3840)
                self.assertLessEqual(max(width, height) / min(width, height), 3)
                self.assertTrue(655360 <= width * height <= 8294400)
                self.assertLess(abs(width * height / 1048576 - 1), .04)
                self.assertLess(abs((width / height) / (source[0] / source[1]) - 1), .025)
        self.assertEqual(self.ai._frame_output_size(png((512, 512))), "1024x1024")
        for source in ((4, 1), (1, 4)):
            with self.assertRaises(ValidationException):
                self.ai._frame_output_size(png(source))

    def test_analyze_reads_all_frames_then_target_and_uses_luna(self):
        storage = MemoryStorage({"f0": png(), "f1": png(color="blue"), "target": png(color="green")})
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(
            finish_reason="stop", message=SimpleNamespace(content=json.dumps(plan()), refusal=None))])
        with patch.object(self.ai, "_r2_client", return_value=storage), patch.object(self.ai, "openai_client", client):
            self.assertEqual(self.ai.analyze(["f0", "f1"], "target"), plan())
        args = client.chat.completions.create.call_args.kwargs
        self.assertEqual(args["model"], "gpt-6-luna")
        self.assertFalse(args["store"])
        self.assertEqual(args["max_completion_tokens"], 16000)
        images = [entry["image_url"]["url"].split(",")[1] for entry in args["messages"][1]["content"] if entry["type"] == "image_url"]
        self.assertEqual([base64.b64decode(value) for value in images], [storage.files[k] for k in ("f0", "f1", "target")])

    def test_analyze_rejects_refusal_truncation_and_invalid_json(self):
        storage = MemoryStorage({"f0": png(), "target": png()})
        for finish, content, refusal in [("length", "{}", None), ("stop", None, "refused"), ("stop", "not json", None), ("stop", "{}", None)]:
            client = Mock()
            client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(
                finish_reason=finish, message=SimpleNamespace(content=content, refusal=refusal))])
            with patch.object(self.ai, "_r2_client", return_value=storage), patch.object(self.ai, "openai_client", client):
                with self.assertRaises(ExternalServiceException):
                    self.ai.analyze(["f0"], "target")

    def test_unsupported_aspect_fails_before_any_model_call(self):
        client = Mock()
        with patch.object(self.ai, "_r2_client", return_value=MemoryStorage({"f0": png((4, 1))})), patch.object(self.ai, "openai_client", client):
            with self.assertRaises(ValidationException):
                self.ai.analyze(["f0"], "unused-target")
        client.chat.completions.create.assert_not_called()

    def test_draft_uses_selected_base_and_target_with_fixed_square_size(self):
        storage = MemoryStorage({"selected-base": png(), "target": png(color="green")})
        client = Mock()
        client.with_options.return_value = client
        client.images.edit.return_value = SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(png()).decode())])
        with patch.object(self.ai, "_r2_client", return_value=storage), patch.object(self.ai, "openai_client", client), patch.object(self.ai, "_record_edit"):
            self.ai.generate_draft("target", "selected-base", plan(), "draft", "callback", "job", "run")
        args = client.images.edit.call_args.kwargs
        self.assertEqual(args["model"], "gpt-image-2.5-flare")
        self.assertEqual(args["size"], "1024x1024")
        self.assertEqual(args["quality"], "low")
        self.assertEqual([value[1].getvalue() for value in args["image"]], [storage.files["selected-base"], storage.files["target"]])
        self.assertNotIn("input_fidelity", args)
        client.with_options.assert_called_once_with(max_retries=0)
        self.assertIn("draft", storage.files)

    def test_parallel_frames_only_receive_current_base_and_same_draft(self):
        storage = MemoryStorage({"f0": png(color="red"), "f1": png(color="blue"), "f2": png(color="green"), "draft": png(color="yellow")})
        client = Mock()
        client.with_options.return_value = client
        barrier = threading.Barrier(3)
        inputs = []

        def edit(**kwargs):
            inputs.append(kwargs)
            barrier.wait(timeout=5)
            return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(png()).decode())])

        client.images.edit.side_effect = edit
        with patch.object(self.ai, "_r2_client", return_value=storage), patch.object(self.ai, "openai_client", client), patch.object(self.ai, "_record_edit"):
            result = self.ai.composite_frames("job", "run", "callback", ["f0", "f1", "f2"], "draft", plan())
        self.assertEqual(result["composited_keys"], [f"temp/job/composited_{i:04d}.png" for i in range(3)])
        self.assertEqual(len(inputs), 3)
        self.assertEqual({args["image"][0][1].getvalue() for args in inputs}, {storage.files[k] for k in ("f0", "f1", "f2")})
        for args in inputs:
            self.assertEqual(len(args["image"]), 2)
            self.assertEqual(args["image"][1][1].getvalue(), storage.files["draft"])
            self.assertEqual(args["model"], "gpt-image-2.5-flare")
            self.assertEqual(args["size"], self.ai._frame_output_size(storage.files["f0"]))
            self.assertEqual(args["output_format"], "png")
            self.assertNotIn("input_fidelity", args)

    def test_legacy_checkpoint_keeps_old_model_square_size_and_instructions(self):
        storage = MemoryStorage({"f0": png(), "target": png(), "draft": png()})
        client = Mock()
        client.with_options.return_value = client
        client.images.edit.return_value = SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(png()).decode())])
        with patch.object(self.ai, "_r2_client", return_value=storage), patch.object(self.ai, "openai_client", client), patch.object(self.ai, "_record_edit"):
            self.ai.generate_draft("target", None, legacy_plan(), "draft", "callback", "job", "run")
            self.ai.composite_frames("job", "run", "callback", ["f0"], "draft", legacy_plan())
        for call in client.images.edit.call_args_list:
            self.assertEqual(call.kwargs["model"], "gpt-image-1.5")
            self.assertEqual(call.kwargs["size"], "1024x1024")
        self.assertIn("original direction", client.images.edit.call_args.kwargs["prompt"])

    def test_frame_failure_is_not_retried_or_replaced_with_source(self):
        storage = MemoryStorage({"f0": png(), "draft": png()})
        client = Mock()
        client.with_options.return_value = client
        client.images.edit.side_effect = ExternalServiceException("test image failure")
        with patch.object(self.ai, "_r2_client", return_value=storage), patch.object(self.ai, "openai_client", client), patch.object(self.ai, "_record_edit"):
            with self.assertRaises(ExternalServiceException):
                self.ai.composite_frames("job", "run", "callback", ["f0"], "draft", plan())
        client.images.edit.assert_called_once()
        client.with_options.assert_called_once_with(max_retries=0)
        self.assertNotIn("temp/job/composited_0000.png", storage.files)

    def test_legacy_draft_resume_uses_legacy_reference_without_reanalysis(self):
        event = {"job_id": "job", "gif_url": "source", "callback_url": "callback", "max_frames": 20,
                 "resume_from": "GENERATING_DRAFT", "durations_ms": [130, 130], "spec": legacy_plan()}
        with patch.object(self.ai, "_r2_client"), patch.object(self.ai, "_normalize_target"), \
             patch.object(self.ai, "_checkpoint"), patch.object(self.ai, "_fail") as fail, \
             patch.object(self.ai, "_complete"), patch.object(self.ai, "analyze") as analyze, \
             patch.object(self.ai, "generate_draft", return_value=100) as draft, patch.object(self.ai, "composite_frames"), \
             patch.object(self.ai, "_invoke_gif_processor"), patch.object(self.ai.time, "sleep"):
            self.ai.run_pipeline(event, "run")
        fail.assert_not_called()
        analyze.assert_not_called()
        self.assertIsNone(draft.call_args.args[1])
        self.assertEqual(draft.call_args.args[2], legacy_plan())

    def test_pipeline_checkpoint_and_resume_do_not_restart_analysis_or_draft(self):
        event = {"job_id": "job", "gif_url": "source", "callback_url": "callback", "max_frames": 20,
                 "durations_ms": [130, 130], "spec": plan()}
        for resume in (None, "GENERATING_DRAFT", "COMPOSITING", "BUILDING_GIF"):
            with self.subTest(resume=resume), patch.object(self.ai, "_r2_client"), patch.object(self.ai, "_normalize_target"), \
                 patch.object(self.ai, "_checkpoint") as checkpoint, patch.object(self.ai, "_fail") as fail, \
                 patch.object(self.ai, "_complete") as complete, patch.object(self.ai, "analyze", return_value=plan()) as analyze, \
                 patch.object(self.ai, "generate_draft", return_value=100) as draft, patch.object(self.ai, "composite_frames") as frames, \
                 patch.object(self.ai, "_invoke_gif_processor", return_value={"durations_ms": [130, 130]}) as gif, \
                 patch.object(self.ai.time, "sleep") as sleep, patch.object(self.ai.time, "monotonic", return_value=110):
                self.ai.run_pipeline(dict(event, resume_from=resume), "run")
                fail.assert_not_called()
                complete.assert_called_once()
                self.assertEqual(analyze.call_count, 1 if resume is None else 0)
                self.assertEqual(draft.call_count, 1 if resume in (None, "GENERATING_DRAFT") else 0)
                self.assertEqual(frames.call_count, 0 if resume == "BUILDING_GIF" else 1)
                if draft.called:
                    self.assertEqual(draft.call_args.args[1], "temp/job/frame_0000.png")
                    self.assertEqual(checkpoint.call_args_list[-3].kwargs["spec"], plan())
                    sleep.assert_called_once_with(55)
                else:
                    sleep.assert_not_called()
                self.assertEqual(gif.call_args.args[0]["durations_ms"], [130, 130])


class GifTimingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gif = load_handler("gif_processor")
        cls.gif.FFMPEG = shutil.which("ffmpeg")
        cls.gif.FFPROBE = shutil.which("ffprobe")

    def setUp(self):
        if not self.gif.FFMPEG or not self.gif.FFPROBE:
            self.skipTest("Local ffmpeg and ffprobe required")

    def test_round_trip_preserves_all_delays_last_frame_count_and_canvas(self):
        for delays in ([130] * 20, [70, 130, 250], [120]):
            with self.subTest(delays=delays):
                keys = [f"frame{i}" for i in range(len(delays))]
                storage = MemoryStorage({key: png((96, 64), (i * 11 % 256, i * 31 % 256, i * 53 % 256)) for i, key in enumerate(keys)})
                with patch.object(self.gif, "_r2_client", return_value=storage):
                    self.gif.build_gif(keys, delays, "result")
                    with Image.open(io.BytesIO(storage.files["result"])) as result:
                        self.assertEqual(result.size, (96, 64))
                        self.assertEqual(result.n_frames, len(delays))
                        actual = []
                        for i in range(result.n_frames):
                            result.seek(i)
                            actual.append(result.info["duration"])
                        self.assertEqual(actual, delays)
                    with patch.object(self.gif, "_fetch_url", return_value=storage.files["result"]):
                        extracted = self.gif.extract_frames("test-source", 20, "job")
                    self.assertEqual(extracted["durations_ms"], delays)
                    self.assertEqual(len(extracted["frame_keys"]), len(delays))

    def test_downsampling_preserves_total_time_and_endpoint_frames(self):
        images = [Image.new("RGB", (64, 48), (i * 5, i * 3, i * 7)) for i in range(23)]
        source = io.BytesIO()
        delays = [70, 130, 230] * 7 + [110, 170]
        images[0].save(source, "GIF", save_all=True, append_images=images[1:], duration=delays, loop=0)
        storage = MemoryStorage()
        with patch.object(self.gif, "_r2_client", return_value=storage), patch.object(self.gif, "_fetch_url", return_value=source.getvalue()):
            result = self.gif.extract_frames("test-source", 20, "job")
        self.assertEqual(len(result["frame_keys"]), 20)
        self.assertEqual(sum(result["durations_ms"]), sum(delays))
        self.assertTrue(all(delay % 10 == 0 for delay in result["durations_ms"]))
        for output_index, source_index in ((0, 0), (19, 22)):
            with Image.open(io.BytesIO(storage.files[result["frame_keys"][output_index]])) as decoded:
                self.assertEqual(decoded.convert("RGB").getpixel((0, 0)), images[source_index].getpixel((0, 0)))

    def test_legacy_non_centisecond_delays_keep_rounded_total(self):
        storage = MemoryStorage({"f0": png(color="red"), "f1": png(color="blue"), "f2": png(color="green")})
        with patch.object(self.gif, "_r2_client", return_value=storage):
            self.gif.build_gif(["f0", "f1", "f2"], [133, 133, 133], "result")
        with Image.open(io.BytesIO(storage.files["result"])) as result:
            delays = []
            for index in range(result.n_frames):
                result.seek(index)
                delays.append(result.info["duration"])
        self.assertEqual(delays, [130, 140, 130])

    def test_invalid_assembly_inputs_fail_before_storage_access(self):
        for keys, delays in (([], []), (["f"], []), (["f"], [0])):
            with patch.object(self.gif, "_r2_client") as client, self.assertRaises(ValidationException):
                self.gif.build_gif(keys, delays, "result")
            client.assert_not_called()

    def test_bad_frame_count_or_missing_delays_fail_without_upload(self):
        with patch.object(self.gif, "_fetch_url") as fetch, self.assertRaises(ValidationException):
            self.gif.extract_frames("test-source", 21, "job")
        fetch.assert_not_called()
        storage = Mock()
        with patch.object(self.gif, "_r2_client", return_value=storage), \
             patch.object(self.gif, "_fetch_url", return_value=b"fake gif"), \
             patch.object(self.gif, "_count_frames", return_value=2), \
             patch.object(self.gif.subprocess, "run", return_value=SimpleNamespace(stdout='{"packets": [{"duration_time": "0.1"}]}')):
            with self.assertRaises(ExternalServiceException):
                self.gif.extract_frames("test-source", 20, "job")
        storage.put_object.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""
GIF 처리 Lambda 핸들러 — ffmpeg 기반

액션:
  count_frames  : GIF 프레임 수 반환
  extract_frames: GIF → PNG 프레임 목록 + duration 목록
  build_gif     : PNG 프레임 목록 + duration 목록 → GIF

ffmpeg 바이너리 경로: /opt/bin/ffmpeg, /opt/bin/ffprobe (Lambda Layer)

입력/출력 바이트는 모두 base64 인코딩
"""
import base64
import io
import json
import os
import subprocess
import tempfile

FFMPEG = "/opt/bin/ffmpeg"
FFPROBE = "/opt/bin/ffprobe"
MAX_FRAMES = 10


def _b64_decode(s: str) -> bytes:
    return base64.b64decode(s)


def _b64_encode(b: bytes) -> str:
    return base64.b64encode(b).decode()


# ── count_frames ─────────────────────────────────────────────

def count_frames(gif_bytes: bytes) -> int:
    with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as f:
        f.write(gif_bytes)
        gif_path = f.name

    try:
        result = subprocess.run(
            [
                FFPROBE, "-v", "quiet",
                "-select_streams", "v:0",
                "-count_packets",
                "-show_entries", "stream=nb_read_packets",
                "-of", "csv=p=0",
                gif_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return int(result.stdout.strip())
    finally:
        os.unlink(gif_path)


# ── extract_frames ────────────────────────────────────────────

def extract_frames(gif_bytes: bytes) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        gif_path = os.path.join(tmpdir, "input.gif")
        with open(gif_path, "wb") as f:
            f.write(gif_bytes)

        total = count_frames(gif_bytes)

        # 균등 샘플링 (MAX_FRAMES 초과 시)
        if total > MAX_FRAMES:
            indices = [round(i * (total - 1) / (MAX_FRAMES - 1)) for i in range(MAX_FRAMES)]
        else:
            indices = list(range(total))

        # duration 추출 (ffprobe)
        probe = subprocess.run(
            [
                FFPROBE, "-v", "quiet",
                "-select_streams", "v:0",
                "-show_entries", "packet=duration_time",
                "-of", "json",
                gif_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        probe_data = json.loads(probe.stdout)
        all_durations_sec = [
            float(p.get("duration_time", 0.1))
            for p in probe_data.get("packets", [])
        ]

        # 전체 프레임 PNG 추출
        frames_dir = os.path.join(tmpdir, "frames")
        os.makedirs(frames_dir)
        subprocess.run(
            [
                FFMPEG, "-i", gif_path,
                os.path.join(frames_dir, "frame_%04d.png"),
            ],
            capture_output=True,
            check=True,
        )

        frames_b64 = []
        durations_ms = []
        for i in indices:
            frame_path = os.path.join(frames_dir, f"frame_{i + 1:04d}.png")
            with open(frame_path, "rb") as f:
                frames_b64.append(_b64_encode(f.read()))

            duration_sec = all_durations_sec[i] if i < len(all_durations_sec) else 0.1
            durations_ms.append(int(duration_sec * 1000))

        # 샘플링 시 duration 균등 분배
        if total > MAX_FRAMES:
            total_ms = sum(int(d * 1000) for d in all_durations_sec)
            per_frame_ms = total_ms // MAX_FRAMES
            durations_ms = [per_frame_ms] * MAX_FRAMES

        return {"frames": frames_b64, "durations_ms": durations_ms}


# ── build_gif ─────────────────────────────────────────────────

def build_gif(frames_b64: list[str], durations_ms: list[int]) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        # PNG 프레임 저장
        for i, frame_b64 in enumerate(frames_b64):
            frame_path = os.path.join(tmpdir, f"frame_{i:04d}.png")
            with open(frame_path, "wb") as f:
                f.write(_b64_decode(frame_b64))

        # ffmpeg concat demuxer용 리스트 파일 생성
        list_path = os.path.join(tmpdir, "frames.txt")
        with open(list_path, "w") as f:
            for i, duration_ms in enumerate(durations_ms):
                f.write(f"file 'frame_{i:04d}.png'\n")
                f.write(f"duration {duration_ms / 1000:.3f}\n")

        out_path = os.path.join(tmpdir, "output.gif")
        subprocess.run(
            [
                FFMPEG,
                "-f", "concat", "-safe", "0", "-i", list_path,
                "-loop", "0",
                out_path,
            ],
            capture_output=True,
            check=True,
        )

        with open(out_path, "rb") as f:
            return _b64_encode(f.read())


# ── check_feasibility ─────────────────────────────────────────

MAX_GIF_DIMENSION = 1920
MIN_TARGET_DIMENSION = 256
MAX_TARGET_DIMENSION = 4096


def _probe_dimensions(file_path: str) -> tuple[int, int]:
    result = subprocess.run(
        [
            FFPROBE, "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            file_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    return stream["width"], stream["height"]


def check_feasibility(gif_bytes: bytes, target_bytes: bytes) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        gif_path = os.path.join(tmpdir, "input.gif")
        target_path = os.path.join(tmpdir, "target.png")

        with open(gif_path, "wb") as f:
            f.write(gif_bytes)
        with open(target_path, "wb") as f:
            f.write(target_bytes)

        # GIF 검사
        frame_count = count_frames(gif_bytes)
        if frame_count < 1:
            return {"ok": False, "reason": "유효한 GIF가 아닙니다"}
        if frame_count > MAX_FRAMES:
            return {"ok": False, "reason": f"GIF 프레임 수가 너무 많습니다 (최대 {MAX_FRAMES}프레임)"}

        gif_w, gif_h = _probe_dimensions(gif_path)
        if gif_w > MAX_GIF_DIMENSION or gif_h > MAX_GIF_DIMENSION:
            return {"ok": False, "reason": f"GIF 해상도가 너무 큽니다 (최대 {MAX_GIF_DIMENSION}px)"}

        # 타겟 이미지 검사
        target_w, target_h = _probe_dimensions(target_path)
        if target_w < MIN_TARGET_DIMENSION or target_h < MIN_TARGET_DIMENSION:
            return {"ok": False, "reason": f"타겟 이미지가 너무 작습니다 (최소 {MIN_TARGET_DIMENSION}px)"}
        if target_w > MAX_TARGET_DIMENSION or target_h > MAX_TARGET_DIMENSION:
            return {"ok": False, "reason": f"타겟 이미지가 너무 큽니다 (최대 {MAX_TARGET_DIMENSION}px)"}

        return {"ok": True, "reason": None}


# ── 핸들러 ────────────────────────────────────────────────────

def handler(event, context):
    action = event.get("action")

    if action == "count_frames":
        gif_bytes = _b64_decode(event["gif_b64"])
        count = count_frames(gif_bytes)
        return {"count": count}

    elif action == "check_feasibility":
        gif_bytes = _b64_decode(event["gif_b64"])
        target_bytes = _b64_decode(event["target_b64"])
        return check_feasibility(gif_bytes, target_bytes)

    elif action == "extract_frames":
        gif_bytes = _b64_decode(event["gif_b64"])
        result = extract_frames(gif_bytes)
        return result

    elif action == "build_gif":
        result_b64 = build_gif(event["frames_b64"], event["durations_ms"])
        return {"gif_b64": result_b64}

    else:
        raise ValueError(f"알 수 없는 액션: {action}")

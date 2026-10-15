"""
GIF 처리 Lambda 핸들러 — ffmpeg 기반

액션:
  check_feasibility: gif_url → 프레임 수 / 유효성 반환
  extract_frames   : gif_url + job_id → 프레임을 R2 temp 저장, frame_keys + durations 반환
  build_gif        : frames_r2_keys + durations → R2 output_key에 GIF 직접 저장

ffmpeg 바이너리 경로: /opt/bin/ffmpeg, /opt/bin/ffprobe (Lambda Layer)
"""
import json
import os
import subprocess
import tempfile
import urllib.request

import boto3
from shared.r2_config import private_bucket_name
from shared.exceptions import ExternalServiceException, ValidationException

FFMPEG = "/opt/bin/ffmpeg"
FFPROBE = "/opt/bin/ffprobe"


# ── R2 클라이언트 ─────────────────────────────────────────────

def _r2_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "gifgloo")
PRIVATE_BUCKET_NAME = private_bucket_name()


def _extracted_frame_key(job_id: str, frame_idx: int) -> str:
    return f"temp/{job_id}/frame_{frame_idx:04d}.png"


# ── HTTP 다운로드 ──────────────────────────────────────────────

def _fetch_url(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


# ── 내부 유틸 ─────────────────────────────────────────────────

def _count_frames(gif_path: str) -> int:
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


# ── check_feasibility ─────────────────────────────────────────

def check_feasibility(gif_url: str) -> dict:
    gif_bytes = _fetch_url(gif_url)
    with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as f:
        f.write(gif_bytes)
        gif_path = f.name

    try:
        frame_count = _count_frames(gif_path)
    finally:
        os.unlink(gif_path)

    if frame_count < 1:
        return {"ok": False, "reason": "유효한 GIF가 아닙니다", "frame_count": 0}
    return {"ok": True, "reason": None, "frame_count": frame_count}


# ── extract_frames ────────────────────────────────────────────

def extract_frames(gif_url: str, max_frames: int, job_id: str) -> dict:
    if not 1 <= max_frames <= 20:
        raise ValidationException("합성 프레임 수는 1~20장이어야 합니다")
    gif_bytes = _fetch_url(gif_url)
    client = _r2_client()

    with tempfile.TemporaryDirectory() as tmpdir:
        gif_path = os.path.join(tmpdir, "input.gif")
        with open(gif_path, "wb") as f:
            f.write(gif_bytes)

        total = _count_frames(gif_path)
        if total < 1:
            raise ValidationException("유효한 GIF 프레임이 없습니다")

        if max_frames == 1:
            indices = [0]
        elif total > max_frames:
            indices = [round(i * (total - 1) / (max_frames - 1)) for i in range(max_frames)]
        else:
            indices = list(range(total))

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
        durations = [round(float(packet["duration_time"]) * 1000) for packet in probe_data["packets"]]
        if len(durations) != total or any(ms <= 0 or ms % 10 for ms in durations):
            raise ExternalServiceException("GIF 프레임 지연 시간을 읽지 못했습니다")

        frames_dir = os.path.join(tmpdir, "frames")
        os.makedirs(frames_dir)
        subprocess.run(
            [
                FFMPEG, "-i", gif_path, "-fps_mode", "passthrough",
                os.path.join(frames_dir, "frame_%04d.png"),
            ],
            capture_output=True,
            check=True,
        )
        if len(os.listdir(frames_dir)) != total:
            raise ExternalServiceException("GIF 디코딩 프레임 수가 원본과 다릅니다")

        frame_keys = []
        durations_ms = []
        for i in indices:
            frame_path = os.path.join(frames_dir, f"frame_{i + 1:04d}.png")
            with open(frame_path, "rb") as f:
                frame_bytes = f.read()

            key = _extracted_frame_key(job_id, len(frame_keys))
            client.put_object(Bucket=PRIVATE_BUCKET_NAME, Key=key, Body=frame_bytes, ContentType="image/png", CacheControl="private, no-store")
            frame_keys.append(key)

            durations_ms.append(durations[i])

        if total > max_frames:
            total_cs = sum(durations) // 10
            boundaries = [round(i * total_cs / max_frames) for i in range(max_frames + 1)]
            durations_ms = [(end - start) * 10 for start, end in zip(boundaries, boundaries[1:])]

        return {"frame_keys": frame_keys, "durations_ms": durations_ms}


# ── build_gif ─────────────────────────────────────────────────

def build_gif(frames_r2_keys: list[str], durations_ms: list[int], output_key: str) -> None:
    if not frames_r2_keys or len(frames_r2_keys) != len(durations_ms) or any(ms <= 0 for ms in durations_ms):
        raise ValidationException("GIF 프레임과 지연 시간 정보가 올바르지 않습니다")
    # Old checkpoints can contain non-centisecond delays; retain total time on GIF's 10ms clock.
    boundaries = [0]
    elapsed_ms = 0
    for duration_ms in durations_ms:
        elapsed_ms += duration_ms
        boundaries.append(round(elapsed_ms / 10))
    gif_delays = [(end - start) * 10 for start, end in zip(boundaries, boundaries[1:])]
    if any(ms <= 0 or ms > 655350 for ms in gif_delays):
        raise ValidationException("GIF 지연 시간이 지원 범위를 벗어났습니다")
    client = _r2_client()

    with tempfile.TemporaryDirectory() as tmpdir:
        # R2에서 composited frames 다운로드
        for i, key in enumerate(frames_r2_keys):
            resp = client.get_object(Bucket=PRIVATE_BUCKET_NAME, Key=key)
            frame_path = os.path.join(tmpdir, f"frame_{i:04d}.png")
            with open(frame_path, "wb") as f:
                f.write(resp["Body"].read())

        # ffmpeg concat demuxer용 리스트 생성
        list_path = os.path.join(tmpdir, "frames.txt")
        with open(list_path, "w") as f:
            for i, duration_ms in enumerate(gif_delays):
                f.write(f"file 'frame_{i:04d}.png'\n")
                f.write("option framerate 100\n")
                f.write(f"duration {duration_ms / 1000:.3f}\n")

        out_path = os.path.join(tmpdir, "output.gif")
        subprocess.run(
            [
                FFMPEG,
                "-f", "concat", "-safe", "0", "-i", list_path,
                "-fps_mode", "passthrough", "-loop", "0",
                "-final_delay", str(gif_delays[-1] // 10),
                out_path,
            ],
            capture_output=True,
            check=True,
        )

        # 결과 GIF → R2 직접 저장
        with open(out_path, "rb") as f:
            client.put_object(
                Bucket=BUCKET_NAME,
                Key=output_key,
                Body=f.read(),
                ContentType="image/gif",
            )


# ── 핸들러 ────────────────────────────────────────────────────

def handler(event, context):
    action = event.get("action")

    if action == "check_feasibility":
        return check_feasibility(event["gif_url"])

    elif action == "extract_frames":
        return extract_frames(event["gif_url"], event["max_frames"], event["job_id"])

    elif action == "build_gif":
        build_gif(event["frames_r2_keys"], event["durations_ms"], event["output_key"])
        return {"ok": True}

    else:
        raise ValueError(f"알 수 없는 액션: {action}")

def extracted_frame_key(job_id: str, frame_idx: int) -> str:
    # lambda/gif_processor/handler.py의 _extracted_frame_key와 패턴 동일하게 유지
    return f"temp/{job_id}/frame_{frame_idx:04d}.png"


def composited_frame_key(job_id: str, frame_idx: int) -> str:
    # lambda/ai_processor/handler.py의 _composited_frame_key와 패턴 동일하게 유지
    return f"temp/{job_id}/composited_{frame_idx:04d}.png"

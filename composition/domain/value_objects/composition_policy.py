MAX_FRAMES = 20
MAX_TARGET_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_TARGET_IMAGE_PIXELS = 20_000_000
MAX_TARGET_IMAGE_EDGE = 2048

ALLOWED_TARGET_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}

ALLOWED_IMAGE_SIGNATURES = [
    b"\x89PNG",
    b"\xff\xd8\xff",
]

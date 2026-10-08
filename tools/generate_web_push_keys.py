"""Generate a VAPID pair without printing secrets or overwriting existing files."""

import argparse
import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def generate_env(output: Path, subject: str):
    key = ec.generate_private_key(ec.SECP256R1())
    private_key = base64.urlsafe_b64encode(key.private_numbers().private_value.to_bytes(32, "big")).decode().rstrip("=")
    public_key = base64.urlsafe_b64encode(key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)).decode().rstrip("=")
    descriptor = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as file:
        file.write(f"WEB_PUSH_ENABLED=false\nWEB_PUSH_PUBLIC_KEY={public_key}\nWEB_PUSH_PRIVATE_KEY={private_key}\nWEB_PUSH_SUBJECT={subject}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".env.web-push.local"))
    parser.add_argument("--subject", default="mailto:support@gifgloo.com")
    args = parser.parse_args()
    if not args.subject.startswith(("mailto:", "https://")) or any(c.isspace() for c in args.subject):
        parser.error("subject must be a mailto: or https:// contact with no whitespace")
    if not args.output.name.startswith(".env.web-push."):
        parser.error("use an ignored .env.web-push.* filename and keep it out of Git")
    try:
        generate_env(args.output, args.subject)
    except FileExistsError:
        parser.error("file already exists; not overwritten (rotating keys invalidates subscriptions)")
    print(f"VAPID settings created with mode 0600: {args.output}. Push remains disabled.")

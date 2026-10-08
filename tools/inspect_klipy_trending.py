"""Download a trending GIF sample and rank it by decoded frame count.

Requires Pillow and python-dotenv. API credentials are read from the frontend
environment file, never included in reports or console output.
"""

import argparse
import csv
import html
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from dotenv import dotenv_values
from PIL import Image, ImageSequence, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.exceptions import ExternalServiceException, ValidationException


def download_and_measure(item, output, target, tolerance):
    gif = None
    for quality in ("hd", "md", "sm", "xs"):
        if quality in item["file"] and "gif" in item["file"][quality]:
            gif = item["file"][quality]["gif"]
            break
    if gif is None:
        raise ValidationException("No GIF rendition in item")
    url = gif["url"]
    if urlparse(url).scheme != "https":
        raise ValidationException("Expected an HTTPS media URL")
    filename = str(int(item["id"])) + ".gif"
    destination = output / "gifs" / filename
    request = Request(url, headers={"User-Agent": "Gifgloo-GIF-Inspector/1.0"})
    with urlopen(request, timeout=60) as response:
        payload = response.read(50 * 1024 * 1024 + 1)
    if len(payload) > 50 * 1024 * 1024:
        raise ValidationException("GIF exceeds the 50 MiB download limit")
    destination.write_bytes(payload)
    with Image.open(destination) as image:
        if image.format != "GIF":
            raise ValidationException("Downloaded media is not a GIF")
        width, height = image.size
        delays = []
        for frame in ImageSequence.Iterator(image):
            frame.load()
            delays.append(frame.info["duration"] if "duration" in frame.info else None)
    frame_count = len(delays)
    duration = sum(delays) / 1000 if all(value is not None for value in delays) else None
    return {
        "id": str(item["id"]),
        "slug": item["slug"],
        "title": item["title"],
        "quality": quality,
        "frame_count": frame_count,
        "distance_from_target": abs(frame_count - target),
        "near_target": abs(frame_count - target) <= tolerance,
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "bytes": len(payload),
        "source_url": url,
        "local_path": str(destination),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--target", type=int, default=20)
    parser.add_argument("--tolerance", type=int, default=5)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--env-file", type=Path, default=ROOT.parent / "gifgloo-frontend/.env.local")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.count <= 50 or args.target < 1 or args.tolerance < 0 or not 1 <= args.workers <= 8:
        parser.error("count: 1–50; target >= 1; tolerance >= 0; workers: 1–8")
    env = {**dotenv_values(args.env_file), **os.environ}
    if "KLIPY_API_KEY" not in env or not env["KLIPY_API_KEY"]:
        raise ValidationException("KLIPY_API_KEY is missing")
    started_at = datetime.now(timezone.utc)
    output = (args.output or ROOT / "downloads" / started_at.strftime("klipy-trending-%Y%m%dT%H%M%S%fZ")).resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "gifs").mkdir()
    query = urlencode({"customer_id": "anonymous", "page": 1, "per_page": args.count})
    api_url = f"https://api.klipy.com/api/v1/{env['KLIPY_API_KEY']}/gifs/trending?{query}"
    try:
        request = Request(api_url, headers={"User-Agent": "Gifgloo-GIF-Inspector/1.0"})
        with urlopen(request, timeout=30) as response:
            response_body = json.load(response)
    except HTTPError as error:
        raise ExternalServiceException(f"KLIPY returned HTTP {error.code}") from None
    except URLError:
        raise ExternalServiceException("KLIPY connection failed; API URL omitted to protect key") from None
    if not response_body["result"]:
        raise ExternalServiceException("KLIPY returned result=false")
    items = []
    seen = set()
    skipped = []
    for item in response_body["data"]["data"]:
        if "type" in item and item["type"] == "ad":
            skipped.append({"reason": "advertisement"})
            continue
        if item["id"] in seen:
            skipped.append({"reason": "duplicate", "id": str(item["id"])})
            continue
        seen.add(item["id"])
        items.append(item)
    print(f"Received {len(items)} unique GIFs; output: {output}", flush=True)
    results = []
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download_and_measure, item, output, args.target, args.tolerance): item for item in items}
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
            except (HTTPError, URLError, TimeoutError, OSError, UnidentifiedImageError, ValidationException) as error:
                failure = {"id": str(item["id"]), "title": item["title"], "error": type(error).__name__}
                failures.append(failure)
                print(f"FAILED {failure['id']}: {failure['error']}", flush=True)
            else:
                results.append(result)
                print(f"[{len(results) + len(failures)}/{len(items)}] {result['frame_count']} frames | {result['duration_seconds']}s | {result['title']}", flush=True)
    results.sort(key=lambda row: (row["distance_from_target"], row["frame_count"], row["id"]))
    report = {
        "fetched_at_utc": started_at.isoformat(),
        "endpoint": "/api/v1/{app_key}/gifs/trending",
        "query": {"customer_id": "anonymous", "page": 1, "per_page": args.count},
        "target_frames": args.target,
        "tolerance_frames": args.tolerance,
        "requested_count": args.count,
        "successful_count": len(results),
        "near_target_count": sum(row["near_target"] for row in results),
        "skipped": skipped,
        "failures": failures,
        "results": results,
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if results:
        with (output / "report.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(results[0]))
            writer.writeheader()
            writer.writerows(results)
    cards = []
    for row in results:
        relative_path = "gifs/" + Path(row["local_path"]).name
        label = "✓ 근방" if row["near_target"] else ""
        cards.append(f'<article><a href="{relative_path}"><img loading="lazy" src="{relative_path}" alt="{html.escape(row["title"], quote=True)}"></a><h2>{html.escape(row["title"])}</h2><p>{row["frame_count"]} frames · {row["duration_seconds"]}s · {row["width"]}×{row["height"]} · {row["quality"]} {label}</p></article>')
    gallery = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>KLIPY GIF frame inspection</title>
<style>body{{font:16px system-ui;margin:30px;background:#15151b;color:#eee}}main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:20px}}article{{background:#25252d;padding:16px;border-radius:12px}}img{{width:100%;height:220px;object-fit:contain}}h2{{font-size:16px}}</style>
<h1>20프레임 근접 GIF — 목표 {args.target} ± {args.tolerance}</h1><p>{len(results)}개 분석 · 근방 {report['near_target_count']}개 · 실패 {len(failures)}개. 프레임 차이순 정렬. 재생시간은 GIF 한 주기의 기록된 지연시간 합계.</p><main>{''.join(cards)}</main></html>'''
    (output / "gallery.html").write_text(gallery, encoding="utf-8")
    print(f"\nDone: {len(results)} analyzed, {report['near_target_count']} near target, {len(failures)} failed.")
    print(f"Report: {output / 'report.json'}\nGallery: {output / 'gallery.html'}")
    if failures or skipped or len(results) != args.count:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

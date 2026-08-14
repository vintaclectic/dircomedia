#!/usr/bin/env python3
"""
youtube_test_upload.py — prove the YouTube lane end to end (task TA3SQSM).

Modes:
  --health          credentials/token check only. Zero quota, zero uploads.
  --seo-only        run the SEO engine and print the metadata. No upload, no
                    quota, no API key needed beyond the text model.
  --upload          REAL upload. Defaults to privacy=private so a test never
                    lands publicly on Vinta's channel by accident.
                    Costs 1,600 of the 10,000 daily quota units.

Examples:
    ./.venv/bin/python scripts/youtube_test_upload.py --health
    ./.venv/bin/python scripts/youtube_test_upload.py --seo-only \
        --topic "DirHaven karma system v2"
    ./.venv/bin/python scripts/youtube_test_upload.py --upload \
        --video /path/clip.mp4 --topic "DirHaven karma v2" --privacy private

The --upload path generates a 3-second test clip with ffmpeg when no --video
is given, so the lane can be proven without hunting for a file.
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env", override=False)
except Exception:
    pass

from app.services.content_engine.youtube_seo import YouTubeSEO  # noqa: E402
from app.services.distribution.platforms.youtube import YouTubeClient  # noqa: E402


def make_test_clip() -> str:
    """Generate a tiny 3s clip so --upload works with no source file."""
    out = os.path.join(tempfile.gettempdir(), "dirco_yt_selftest.mp4")
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "color=c=0x0b0b0f:s=1280x720:d=3",
        "-vf", "drawtext=text='DirCoMedia':fontcolor=0x5ee6a8:fontsize=64:"
               "x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "3", out,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    except FileNotFoundError:
        print("  ffmpeg not installed — pass --video <path> instead.", file=sys.stderr)
        raise SystemExit(2)
    except subprocess.CalledProcessError as exc:
        print(f"  ffmpeg failed: {exc.stderr[-400:].decode(errors='replace')}", file=sys.stderr)
        raise SystemExit(2)
    return out


async def run(args) -> int:
    client = YouTubeClient()

    if args.health or not (args.upload or args.seo_only):
        health = await client.health()
        print(json.dumps({"youtube_health": health}, indent=2))
        if not health.get("configured"):
            print(
                "\n  Not configured. Run:\n"
                "    ./.venv/bin/python scripts/youtube_auth.py\n"
                "  (see docs/PLATFORM_CONNECTIONS.md §5 for the Google Cloud setup)\n",
                file=sys.stderr,
            )
            return 2
        return 0 if health.get("live") else 1

    seo = await YouTubeSEO().generate(
        project_slug=args.project,
        topic=args.topic,
        body=args.body or args.topic,
        duration=args.duration,
    )
    print(json.dumps({"seo": seo}, indent=2, ensure_ascii=False))

    if args.seo_only:
        return 0

    video = args.video or make_test_clip()
    print(f"\n  Uploading {video} (privacy={args.privacy}) ...\n")
    try:
        result = await client.upload_video(
            video_url=video,
            title=seo["title"],
            description=seo["description"],
            tags=seo["tags"],
            privacy=args.privacy,
        )
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"upload": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps({"upload": result}, indent=2))
    print(f"\n  Live at: {result.get('url')}\n  Studio:  {result.get('studio_url')}\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="YouTube lane self-test")
    p.add_argument("--health", action="store_true", help="credential check only")
    p.add_argument("--seo-only", action="store_true", help="metadata only, no upload")
    p.add_argument("--upload", action="store_true", help="REAL upload (1600 quota units)")
    p.add_argument("--video", help="path or URL; a 3s clip is generated if omitted")
    p.add_argument("--project", default="dirco", help="brand config slug")
    p.add_argument("--topic", default="DirCoMedia YouTube pipeline self-test")
    p.add_argument("--body", default="")
    p.add_argument("--duration", type=int, default=None)
    p.add_argument(
        "--privacy", default="private", choices=["private", "unlisted", "public"],
        help="default private — a self-test must never surprise the channel",
    )
    return asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())

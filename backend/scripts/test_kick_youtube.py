#!/usr/bin/env python3
"""
Quick test script for Kick→YouTube pipeline (task 3JFWZQK, 2026-08-14).

Usage:
    # Test Kick API connection only (no download/upload)
    python scripts/test_kick_youtube.py --kick-only

    # Test full pipeline (download + upload to YouTube)
    python scripts/test_kick_youtube.py --full

    # Dry run (everything except actual YouTube upload)
    python scripts/test_kick_youtube.py --dry-run
"""
import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.distribution.platforms.kick import KickClient
from app.services.distribution.platforms.youtube import YouTubeClient
from app.services.distribution.platforms.twitter import TwitterClient
from app.config import settings


async def test_kick_only():
    """Test Kick API — fetch channel info and recent streams."""
    if not settings.kick_username:
        print("❌ KICK_USERNAME not set in .env")
        return False

    print(f"🔍 Testing Kick API for channel: {settings.kick_username}\n")

    kick = KickClient(settings.kick_username)

    try:
        # Fetch channel info
        print("1️⃣ Fetching channel info...")
        info = await kick.get_channel_info()
        print(f"   ✅ Channel: {info.get('slug')}")
        print(f"   📡 Live now: {info.get('livestream') is not None}")
        print(f"   👥 Followers: {info.get('followers_count', 'N/A')}\n")

        # Fetch recent streams
        print("2️⃣ Fetching recent streams...")
        streams = await kick.get_recent_streams(limit=5)
        print(f"   ✅ Found {len(streams)} recent streams\n")

        if streams:
            print("   Recent streams:")
            for i, stream in enumerate(streams, 1):
                title = stream.get('session_title', 'Untitled')
                created = stream.get('created_at', 'N/A')
                is_live = stream.get('is_live', False)
                has_vod = stream.get('video') is not None
                print(f"   {i}. {title}")
                print(f"      Created: {created} | Live: {is_live} | VOD: {has_vod}")
            print()

        # Check for latest ended stream (what pipeline would upload)
        print("3️⃣ Checking for latest ended stream with VOD...")
        latest = await kick.get_latest_ended_stream()
        if latest:
            print(f"   ✅ Found: {latest.get('session_title')}")
            print(f"   📅 Created: {latest.get('created_at')}")
            print(f"   🎬 VOD available: Yes")

            # Test metadata optimization
            print("\n4️⃣ Testing YouTube metadata optimization...")
            metadata = kick.optimize_metadata_for_youtube(latest)
            print(f"   Title: {metadata['title']}")
            print(f"   Tags: {', '.join(metadata['tags'][:5])}...")
            print(f"   Description (first 200 chars):\n   {metadata['description'][:200]}...\n")
        else:
            print("   ⚠️ No ended streams with VODs found (all streams are live or no VODs yet)")
            print("   This is normal if you just ended a stream — Kick takes 5-15min to process VODs\n")

        print("✅ Kick API test PASSED\n")
        return True

    except Exception as e:
        print(f"❌ Kick API test FAILED: {e}\n")
        return False


async def test_full_pipeline():
    """Test full pipeline: Kick → download → YouTube upload → X post."""
    print("🚀 Testing FULL pipeline (Kick → YouTube → X)\n")

    # Check prerequisites
    if not settings.kick_username:
        print("❌ KICK_USERNAME not set in .env")
        return False

    kick = KickClient(settings.kick_username)
    youtube = YouTubeClient()
    twitter = TwitterClient()

    if not youtube.configured:
        print("❌ YouTube OAuth not configured (see docs/PLATFORM_CONNECTIONS.md §5)")
        return False

    # Step 1: Fetch latest ended stream
    print("1️⃣ Fetching latest ended Kick stream...")
    latest = await kick.get_latest_ended_stream()
    if not latest:
        print("   ⚠️ No ended streams found — nothing to upload")
        print("   Either:")
        print("   - You haven't streamed on Kick yet")
        print("   - All recent streams are still live")
        print("   - VODs aren't processed yet (wait 5-15min after stream ends)")
        return False

    stream_title = latest.get('session_title', 'Untitled')
    stream_id = latest.get('id')
    print(f"   ✅ Found: {stream_title} (ID: {stream_id})\n")

    # Step 2: Download VOD
    print("2️⃣ Downloading VOD (this may take 1-5 min for large streams)...")
    try:
        vod_path = await kick.download_vod(latest)
        vod_size_mb = os.path.getsize(vod_path) / 1e6
        print(f"   ✅ Downloaded: {vod_path} ({vod_size_mb:.1f} MB)\n")
    except Exception as e:
        print(f"   ❌ Download failed: {e}")
        print("   Possible causes:")
        print("   - yt-dlp not installed: pip install yt-dlp")
        print("   - VOD not available yet (try again in 5-10min)")
        return False

    # Step 3: Optimize metadata
    print("3️⃣ Optimizing metadata for YouTube...")
    metadata = kick.optimize_metadata_for_youtube(latest)
    print(f"   Title: {metadata['title']}")
    print(f"   Tags: {', '.join(metadata['tags'])}")
    print(f"   Category: {metadata['category_id']} (Gaming)\n")

    # Step 4: Upload to YouTube
    print("4️⃣ Uploading to YouTube (this may take 2-10 min depending on file size)...")
    print("   ⏳ Upload in progress... (chunked resumable upload)")
    try:
        result = await youtube.upload(
            video=vod_path,
            title=metadata['title'],
            description=metadata['description'],
            tags=metadata['tags'],
            category_id=metadata['category_id'],
            privacy="public",  # Change to "unlisted" if you want to review first
        )
        video_id = result.get('id')
        video_url = f"https://youtube.com/watch?v={video_id}"
        print(f"   ✅ Uploaded successfully!")
        print(f"   📺 YouTube URL: {video_url}")
        print(f"   🆔 Video ID: {video_id}\n")
    except Exception as e:
        print(f"   ❌ Upload failed: {e}")
        print("   Check:")
        print("   - YouTube quota (1600 units/upload, max ~6/day)")
        print("   - OAuth token valid (run scripts/youtube_auth.py if expired)")
        # Clean up VOD even if upload failed
        if os.path.exists(vod_path):
            os.remove(vod_path)
        return False

    # Step 5: Post to X (optional)
    if twitter.configured:
        print("5️⃣ Posting announcement to X/Twitter...")
        try:
            tweet_text = (
                f"🎮 New video live on YouTube!\n\n"
                f"{metadata['title']}\n\n"
                f"Watch now: {video_url}\n\n"
                f"#LiveStream #Gaming #Kick #YouTube"
            )
            tweet_result = await twitter.post(tweet_text)
            tweet_url = tweet_result.get('url', 'N/A')
            print(f"   ✅ Tweeted: {tweet_url}\n")
        except Exception as e:
            print(f"   ⚠️ Tweet failed (non-fatal): {e}\n")
    else:
        print("5️⃣ Skipping X post (Twitter not configured)\n")

    # Clean up VOD
    if os.path.exists(vod_path):
        os.remove(vod_path)
        print(f"🧹 Cleaned up temp VOD: {vod_path}\n")

    print("✅ Full pipeline test PASSED")
    print(f"📺 Your video is live: {video_url}\n")
    return True


async def test_dry_run():
    """Dry run: everything except actual YouTube upload."""
    print("🧪 DRY RUN mode (no actual YouTube upload)\n")

    if not settings.kick_username:
        print("❌ KICK_USERNAME not set in .env")
        return False

    kick = KickClient(settings.kick_username)

    # Fetch + download
    print("1️⃣ Fetching latest ended stream...")
    latest = await kick.get_latest_ended_stream()
    if not latest:
        print("   ⚠️ No ended streams found\n")
        return False

    stream_title = latest.get('session_title', 'Untitled')
    print(f"   ✅ Found: {stream_title}\n")

    print("2️⃣ Testing VOD download...")
    try:
        vod_path = await kick.download_vod(latest)
        vod_size_mb = os.path.getsize(vod_path) / 1e6
        print(f"   ✅ Downloaded: {vod_size_mb:.1f} MB\n")
    except Exception as e:
        print(f"   ❌ Download failed: {e}\n")
        return False

    print("3️⃣ Metadata optimization:")
    metadata = kick.optimize_metadata_for_youtube(latest)
    print(f"   Title: {metadata['title']}")
    print(f"   Description:\n{metadata['description'][:300]}...\n")

    print("4️⃣ [DRY RUN] Skipping actual YouTube upload")
    print("   Would upload:")
    print(f"   - File: {vod_path} ({vod_size_mb:.1f} MB)")
    print(f"   - Title: {metadata['title']}")
    print(f"   - Privacy: public\n")

    # Clean up
    if os.path.exists(vod_path):
        os.remove(vod_path)
        print(f"🧹 Cleaned up: {vod_path}\n")

    print("✅ Dry run PASSED — pipeline is ready\n")
    return True


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test Kick→YouTube pipeline")
    parser.add_argument("--kick-only", action="store_true", help="Test Kick API only (no upload)")
    parser.add_argument("--full", action="store_true", help="Test full pipeline (download + upload)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (no actual upload)")
    args = parser.parse_args()

    if args.kick_only:
        await test_kick_only()
    elif args.full:
        await test_full_pipeline()
    elif args.dry_run:
        await test_dry_run()
    else:
        print("Usage:")
        print("  python scripts/test_kick_youtube.py --kick-only    # Test Kick API")
        print("  python scripts/test_kick_youtube.py --dry-run      # Test download only")
        print("  python scripts/test_kick_youtube.py --full         # Test full pipeline\n")


if __name__ == "__main__":
    asyncio.run(main())

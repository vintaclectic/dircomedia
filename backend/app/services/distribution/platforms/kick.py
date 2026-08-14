"""
Kick.com client — fetch live stream + VOD metadata, download VODs for YouTube
cross-posting (task 3JFWZQK, 2026-08-14).

Kick API is undocumented/unofficial — reverse-engineered endpoints from the
public web app (same as community tools like autovod). Endpoints observed:
  - /api/v2/channels/{username} — channel metadata, live status
  - /api/v2/channels/{username}/livestreams — recent/past streams
  - VOD m3u8 playlists served from CDN, downloadable via ffmpeg/yt-dlp

Kick has no official API/OAuth — this operates as read-only public scraping
of a creator's own content (legally safe: creator owns rights per Kick ToS §6).
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.exceptions import DistributionError

KICK_API_BASE = "https://kick.com/api/v2"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


class KickClient:
    def __init__(self, username: str):
        """
        Args:
            username: Kick channel username (e.g. "vintaclectic")
        """
        self.username = username

    async def get_channel_info(self) -> dict:
        """Fetch channel metadata and current live status."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{KICK_API_BASE}/channels/{self.username}",
                headers={"User-Agent": USER_AGENT},
            )
            if response.status_code == 404:
                raise DistributionError(
                    f"Kick channel '{self.username}' not found", "kick"
                )
            if response.status_code >= 400:
                raise DistributionError(
                    f"Kick API error {response.status_code}: {response.text[:200]}",
                    "kick",
                )
            return response.json()

    async def get_recent_streams(self, limit: int = 10) -> list[dict]:
        """
        Fetch recent/past livestreams (VODs).

        Returns list of stream objects with keys:
          - id: stream ID
          - session_title: stream title
          - created_at: ISO timestamp when stream started
          - duration: stream length in seconds (if ended)
          - video: VOD metadata (m3u8 URL, thumbnail)
          - is_live: whether currently streaming
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Kick's livestreams endpoint — paginated, newest first
            response = await client.get(
                f"{KICK_API_BASE}/channels/{self.username}/livestreams",
                headers={"User-Agent": USER_AGENT},
                params={"limit": limit},
            )
            if response.status_code >= 400:
                raise DistributionError(
                    f"Kick streams API error {response.status_code}: {response.text[:200]}",
                    "kick",
                )
            data = response.json()
            return data.get("data", [])

    async def get_latest_ended_stream(self) -> Optional[dict]:
        """
        Get the most recent stream that has ENDED (not live, has VOD available).

        Returns None if no ended streams found (e.g. channel never streamed, or
        all recent streams are still live).
        """
        streams = await self.get_recent_streams(limit=20)
        for stream in streams:
            # Stream has ended if is_live=False and it has a video/VOD
            if not stream.get("is_live", False) and stream.get("video"):
                return stream
        return None

    async def download_vod(
        self,
        stream: dict,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Download a Kick VOD to local disk via yt-dlp (handles m3u8 → mp4).

        Args:
            stream: Stream object from get_recent_streams() with 'video' key
            output_path: Where to save (default: temp file). Must end in .mp4

        Returns:
            Path to downloaded .mp4 file

        Raises:
            DistributionError if download fails or yt-dlp not installed
        """
        video_data = stream.get("video")
        if not video_data:
            raise DistributionError("Stream has no VOD available", "kick")

        # Kick VODs are served as m3u8 playlists — yt-dlp handles the conversion
        vod_url = video_data.get("url") or video_data.get("hls_url")
        if not vod_url:
            raise DistributionError("VOD URL not found in stream metadata", "kick")

        # Determine output path
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".mp4", prefix="kick_vod_")
            os.close(fd)  # yt-dlp will overwrite it

        # Use yt-dlp to download and convert m3u8 → mp4
        # Flags: --no-warnings, --quiet for cleaner logs; --merge-output-format mp4
        # forces container format; -o is output template
        cmd = [
            "yt-dlp",
            "--quiet",
            "--no-warnings",
            "--merge-output-format", "mp4",
            "-o", output_path,
            vod_url,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err = stderr.decode()[:500]
            # Check if yt-dlp not installed
            if "not found" in err or "No such file" in err:
                raise DistributionError(
                    "yt-dlp not installed — install with: pip install yt-dlp",
                    "kick",
                )
            raise DistributionError(f"VOD download failed: {err}", "kick")

        # Verify file exists and has content
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            raise DistributionError(
                "Downloaded VOD is empty or missing", "kick"
            )

        return output_path

    def optimize_metadata_for_youtube(self, stream: dict) -> dict:
        """
        Transform Kick stream metadata into YouTube-optimized upload metadata.

        Returns dict with:
          - title: SEO-optimized title (≤100 chars, keyword-rich)
          - description: Formatted description with links, timestamps, hashtags
          - tags: List of relevant tags (max 500 chars total)
          - category_id: YouTube category (20=Gaming by default)
        """
        # Original stream title from Kick
        original_title = stream.get("session_title", "Untitled Stream")

        # YouTube title optimization:
        # - Keep it under 100 chars (YouTube truncates in search)
        # - Add hook/keyword prefix if generic
        # - Include date for discoverability
        stream_date = stream.get("created_at", "")
        date_suffix = ""
        if stream_date:
            try:
                dt = datetime.fromisoformat(stream_date.replace("Z", "+00:00"))
                date_suffix = f" | {dt.strftime('%b %d, %Y')}"
            except:
                pass

        # If title is generic/short, prepend a hook (customize per brand)
        if len(original_title) < 20:
            title = f"🔴 LIVE: {original_title}{date_suffix}"
        else:
            title = f"{original_title}{date_suffix}"

        # Truncate to 100 chars (YouTube best practice)
        if len(title) > 100:
            title = title[:97] + "..."

        # Description optimization:
        # - First 2-3 lines are visible in search → strongest hook + CTA
        # - Link back to Kick channel for cross-platform growth
        # - Timestamps (if available) drive watch time
        # - Hashtags (3-5) for discoverability
        description_lines = [
            original_title,
            "",
            f"🎮 Streamed live on Kick: https://kick.com/{self.username}",
            "",
            "❤️ Follow for more live streams and gaming content!",
            "",
            "---",
            f"📅 Stream Date: {stream_date or 'N/A'}",
            f"⏱️ Duration: {stream.get('duration', 'N/A')} seconds",
            "",
            "🔔 Subscribe and hit the bell to never miss a stream!",
            "",
            "#LiveStream #Gaming #Kick #VOD #Gameplay",
        ]
        description = "\n".join(description_lines)

        # Tags: mix of generic gaming + specific game/topic (extract from title)
        # YouTube allows max 500 chars total across all tags
        base_tags = ["live stream", "gaming", "kick", "vod", "gameplay"]
        # Could extract game name from title here if known — for now, use generics
        tags = base_tags[:15]  # cap at 15 tags to stay under 500 char limit

        return {
            "title": title,
            "description": description,
            "tags": tags,
            "category_id": "20",  # 20 = Gaming (adjust if content is non-gaming)
        }


async def test_kick_client():
    """Quick smoke test — fetch channel info and recent streams."""
    client = KickClient("vintaclectic")  # Replace with actual channel

    print("Fetching channel info...")
    info = await client.get_channel_info()
    print(f"Channel: {info.get('slug')} — Live: {info.get('livestream') is not None}")

    print("\nFetching recent streams...")
    streams = await client.get_recent_streams(limit=5)
    print(f"Found {len(streams)} recent streams")

    if streams:
        latest = streams[0]
        print(f"\nLatest: {latest.get('session_title')}")
        print(f"  Created: {latest.get('created_at')}")
        print(f"  Live: {latest.get('is_live')}")
        print(f"  Has VOD: {latest.get('video') is not None}")

        # Test metadata optimization
        print("\nOptimized YouTube metadata:")
        metadata = client.optimize_metadata_for_youtube(latest)
        print(f"  Title: {metadata['title']}")
        print(f"  Tags: {', '.join(metadata['tags'])}")


if __name__ == "__main__":
    asyncio.run(test_kick_client())

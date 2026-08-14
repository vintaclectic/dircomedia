# Kick → YouTube Automation Pipeline

**Task:** 3JFWZQK | **Built:** 2026-08-14 | **Purpose:** Passive revenue engine — turn every Kick stream into discoverable YouTube content automatically.

## What It Does

Every 30 minutes, the pipeline:
1. **Polls Kick** for your latest ended stream (VOD available)
2. **Downloads the VOD** via yt-dlp (handles m3u8 → mp4 conversion)
3. **Optimizes metadata** for YouTube SEO (title, description, tags)
4. **Uploads to YouTube** with chunked resumable transfer (handles multi-GB files)
5. **Posts announcement to X** (optional, if Twitter configured)
6. **Tracks processed streams** in DB to avoid duplicates

## Legal/ToS Compliance

✅ **Kick ToS:** You own your content; redistribution to other platforms is allowed.  
✅ **YouTube API:** Automated uploads are permitted within quota limits (1600 units/upload, ~6/day max default).  
✅ **Industry precedent:** Multiple open-source tools (autovod, etc.) do this; established pattern.

Sources:
- [Kick ToS](https://kick.com/terms-of-service)
- [YouTube API Terms](https://developers.google.com/youtube/terms/api-services-terms-of-service)
- [Multistreaming Guide 2026](https://streamscharts.com/news/multistreaming-guide-2026-rules-explained)

## Setup

### 1. Install Dependencies

The pipeline requires **yt-dlp** for downloading Kick VODs:

```bash
# Install yt-dlp (Python package)
pip install yt-dlp

# Or via package manager (Ubuntu/Debian)
sudo apt install yt-dlp

# Verify installation
yt-dlp --version
```

### 2. Configure Environment Variables

Add to `/home/vinta/dircomedia/backend/.env`:

```bash
# Kick account to monitor
KICK_USERNAME=vintaclectic  # Your Kick.com channel username

# YouTube OAuth (required — see docs/PLATFORM_CONNECTIONS.md §5)
YOUTUBE_CLIENT_ID=your-client-id.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET=your-client-secret
YOUTUBE_REFRESH_TOKEN=your-refresh-token

# Twitter/X (optional — for auto-announcements)
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...
TWITTER_BEARER_TOKEN=...
```

**YouTube OAuth Setup:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project → Enable YouTube Data API v3
3. Create OAuth 2.0 credentials (Desktop app)
4. Run `python backend/scripts/youtube_auth.py` to get refresh token
5. Paste the three values into `.env`

Full guide: `docs/PLATFORM_CONNECTIONS.md` §5

### 3. Create Database Table

The pipeline uses a `processed_content` table to track what's been uploaded:

```bash
cd /home/vinta/dircomedia/backend

# Create migration (if using Alembic)
alembic revision --autogenerate -m "Add processed_content table for Kick→YouTube"
alembic upgrade head

# Or run directly in SQLite/PostgreSQL:
# (The model is in app/models/processed_content.py)
```

**If DirCoMedia uses SQLite** (check `dircomedia.db`):
```bash
cd /home/vinta/dircomedia/backend
sqlite3 dircomedia.db <<EOF
CREATE TABLE IF NOT EXISTS processed_content (
    id TEXT PRIMARY KEY,
    source_platform TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_url TEXT,
    target_platform TEXT,
    target_id TEXT,
    target_url TEXT,
    metadata TEXT,  -- JSON
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_source_platform_id ON processed_content(source_platform, source_id);
CREATE INDEX idx_target_platform_id ON processed_content(target_platform, target_id);
EOF
```

### 4. Start the Workers

The pipeline runs as a Celery beat task. Start the Celery worker + beat scheduler:

```bash
cd /home/vinta/dircomedia/backend

# Start worker (handles video downloads + uploads)
celery -A app.workers.celery_app worker --loglevel=info -Q video &

# Start beat scheduler (triggers pipeline every 30min)
celery -A app.workers.celery_app beat --loglevel=info &
```

**Production:** Use `systemd` or `pm2` to keep workers running:
```bash
pm2 start "celery -A app.workers.celery_app worker -Q video" --name dirco-video-worker
pm2 start "celery -A app.workers.celery_app beat" --name dirco-beat
pm2 save
```

## Testing

### Quick Test (Manual Trigger)

Run the pipeline once, immediately, without waiting for the beat schedule:

```bash
cd /home/vinta/dircomedia/backend

# Trigger the task manually
celery -A app.workers.celery_app call kick_youtube_pipeline.poll_and_upload

# Or run the Python module directly (bypasses Celery)
python -m app.workers.kick_youtube_pipeline
```

**Expected output:**
```json
{
  "status": "success",
  "stream_id": "12345",
  "stream_title": "Epic Gaming Session",
  "youtube_url": "https://youtube.com/watch?v=abc123",
  "youtube_video_id": "abc123"
}
```

**Possible outcomes:**
- `"status": "skipped"` — No new ended streams found, or already uploaded
- `"status": "error"` — Check error message; common: yt-dlp not installed, YouTube quota exceeded, OAuth token expired
- `"status": "idle"` — No streams available (channel never streamed, or all recent streams still live)

### Verify YouTube Upload

After a successful run:
1. Check YouTube Studio: https://studio.youtube.com
2. Look for the uploaded video (title will have date suffix + "🔴 LIVE:" prefix)
3. Video should be **public** (or **unlisted** if you set `privacy="unlisted"` in the code)

### Check Twitter/X Announcement

If Twitter is configured, a tweet should be posted:
- Format: "🎮 New video live on YouTube! [title] Watch now: [url] #LiveStream #Gaming"
- Check your Twitter profile to confirm

### Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `yt-dlp not installed` | Missing dependency | `pip install yt-dlp` or `sudo apt install yt-dlp` |
| `YouTube OAuth not configured` | Missing .env keys | Follow setup §2 — run `scripts/youtube_auth.py` |
| `Kick channel 'X' not found` | Wrong `KICK_USERNAME` | Check spelling in `.env` — must match Kick.com exactly |
| `YouTube quota exceeded` | Hit 10,000 units/day limit | Wait 24h (quota resets daily Pacific time) or request audit from Google |
| `invalid_grant` (YouTube) | Refresh token expired | Re-run `scripts/youtube_auth.py` (tokens expire in 7 days if app in Testing mode) |
| `VOD download failed` | Kick VOD not available yet | Wait longer after stream ends (Kick processes VODs ~5-15min after end) |
| `Stream X already uploaded` | Idempotency check passed | Working as intended — won't re-upload same stream |

## Architecture

```
┌─────────────────┐
│  Celery Beat    │  Fires every 30min
│  (scheduler)    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  kick_youtube_pipeline.poll_and_upload()    │
│  (Celery task, runs on 'video' queue)       │
└─────┬───────────────────────────────────────┘
      │
      ├─► 1. KickClient.get_latest_ended_stream()
      │      └─► Kick API: /api/v2/channels/{user}/livestreams
      │
      ├─► 2. Check processed_content table (idempotency)
      │
      ├─► 3. KickClient.download_vod()
      │      └─► yt-dlp downloads m3u8 → mp4 to /tmp
      │
      ├─► 4. KickClient.optimize_metadata_for_youtube()
      │      └─► Generate SEO-optimized title, description, tags
      │
      ├─► 5. YouTubeClient.upload()
      │      └─► Chunked resumable upload to YouTube Data API v3
      │
      ├─► 6. Record in processed_content table
      │
      └─► 7. TwitterClient.post() (optional announcement)
```

## Files

| File | Purpose |
|------|---------|
| `backend/app/services/distribution/platforms/kick.py` | Kick API client — fetch streams, download VODs, optimize metadata |
| `backend/app/workers/kick_youtube_pipeline.py` | Main automation worker — Celery task |
| `backend/app/models/processed_content.py` | DB model for tracking uploaded content |
| `backend/app/config.py` | Settings (added `kick_username` field) |
| `backend/app/workers/celery_app.py` | Celery config (added beat schedule + task routes) |
| `docs/KICK_YOUTUBE_PIPELINE.md` | This file — setup + testing guide |

## Customization

### Change Upload Frequency

Edit `backend/app/workers/celery_app.py`:
```python
"kick-youtube-pipeline": {
    "task": "kick_youtube_pipeline.poll_and_upload",
    "schedule": 1800.0,  # Change this: 1800 = 30min, 3600 = 1hr, 600 = 10min
},
```

### Change Video Privacy

Edit `backend/app/workers/kick_youtube_pipeline.py`:
```python
result = await youtube.upload(
    # ...
    privacy="public",  # Options: "public", "unlisted", "private"
)
```
Set to `"unlisted"` if you want to review videos before making them public.

### Customize YouTube Metadata

Edit `KickClient.optimize_metadata_for_youtube()` in `kick.py`:
- **Title format:** Change the prefix/suffix, add branding
- **Description:** Add CTAs, links, timestamps, affiliate links
- **Tags:** Add game-specific tags, niche keywords
- **Category:** Change from 20 (Gaming) to 22 (People & Blogs), 24 (Entertainment), etc.

### Monitor a Different Kick Channel

Change `KICK_USERNAME` in `.env` to any Kick channel you own/have rights to.

## Monitoring

### Check Pipeline Status

```bash
# See recent task results (requires Redis/Celery backend)
celery -A app.workers.celery_app inspect active
celery -A app.workers.celery_app inspect scheduled

# Check logs
tail -f /path/to/celery-worker.log
```

### Database Query (What's Been Uploaded)

```bash
sqlite3 /home/vinta/dircomedia/backend/dircomedia.db
> SELECT source_id, target_url, processed_at FROM processed_content WHERE source_platform='kick' ORDER BY processed_at DESC LIMIT 10;
```

### YouTube Analytics

Track performance in [YouTube Studio → Analytics](https://studio.youtube.com/channel/analytics):
- Views per automated upload
- Watch time (key for monetization)
- Traffic sources (YouTube search vs. external)

## Revenue Impact

**Why this matters:**
- **Discoverability:** YouTube search >> Kick VODs. Kick streams disappear; YouTube videos rank forever.
- **Monetization:** YouTube Partner Program pays per view + ad revenue. Kick streams = one-time, YouTube = passive residual.
- **SEO:** Optimized titles/tags capture long-tail search traffic ("how to X", "Y gameplay", etc.)
- **Cross-platform growth:** YouTube viewers → Kick followers (description links back)

**Expected lift:** 3-10x views per stream (YouTube search + suggestions vs. Kick VOD browsing).

## Next Steps

1. ✅ Pipeline working end-to-end (tested manually)
2. Monitor first auto-uploaded video's performance (24-48h)
3. A/B test metadata templates (try different title/description formats, track CTR in YouTube Studio)
4. Add thumbnail optimization (auto-generate eye-catching thumbnails from stream highlights)
5. Extend to other platforms (TikTok clips from highlights, Instagram Reels, etc.)

---

**Built by:** council seat-3 | **Task:** 3JFWZQK | **Date:** 2026-08-14  
**Legal research:** Verified Kick ToS §6 (creator owns content), YouTube API permits automation within quota.

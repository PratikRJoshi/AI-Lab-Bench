# LinkedIn Video Extraction Workaround

## Problem
Neither yt-dlp nor gallery-dl support extracting videos from LinkedIn posts. LinkedIn requires authentication and dynamically loads video URLs.

## Solution: Browser Developer Tools Method

### Step-by-step instructions:

1. **Open the LinkedIn post**
   - Use Firefox (already configured with cookies)
   - Navigate to the LinkedIn post URL

2. **Open Developer Tools**
   - Press **F12** (or Right-click → Inspect)

3. **Go to Network tab**
   - Click on the **Network** tab in Developer Tools
   - **Important**: Do this BEFORE playing the video

4. **Filter for media**
   - In the filter box at the top, type: `media` or `.mp4`
   - Or use the filter buttons to show only "Media" requests

5. **Play the video**
   - Click play on the LinkedIn video
   - Watch the Network tab populate with requests

6. **Find the video file**
   - Look for entries with:
     - Large size (multiple MB)
     - Type: "media" or "video"
     - Extension: `.mp4` or similar
   - Common patterns:
     - `dms-delivered-secure-prod-video-*.mp4`
     - URLs containing `media.licdn.com`
     - Progressive download URLs

7. **Copy the video URL**
   - Right-click on the video request
   - Select **Copy** → **Copy URL**
   - The URL should look like:
     ```
     https://media.licdn.com/dms/video/[hash]/[params]/[video-id].mp4
     ```

8. **Add to Watch-urls.md**
   - Replace the LinkedIn post URL with the direct video URL
   - Or add it as a new entry under `## Pending`

## Alternative: Browser Extension

Install one of these Firefox extensions:
- **Video DownloadHelper**: Most popular, works with many sites
- **Video Downloader professional**: Lightweight alternative

These extensions can automatically detect and download LinkedIn videos.

## Verification

Test the extracted URL works:
```bash
yt-dlp --cookies-from-browser firefox '<DIRECT_VIDEO_URL>'
```

If it downloads successfully, you can add it to Watch-urls.md for analysis.

## Technical Note

LinkedIn video URLs are often time-limited and may expire after a few hours. If you extract a URL but don't process it immediately, you may need to re-extract a fresh URL later.

# Image/Carousel Support for URL Truth Analyzer

## Overview

The url-truth-analyzer skill now supports analyzing image posts and carousels from Instagram, Facebook, and Twitter/X, in addition to video/audio content.

## What Changed

### 1. Content Type Detection (Step 1)
- Skill now detects when a URL contains images instead of video
- Detection: yt-dlp returns "No video formats found" but successfully extracts metadata
- Automatically switches to image download mode (Mode F)

### 2. Image Download (Mode F)
Downloads images from social media posts:
- Single images or carousels (multiple images)
- Uses yt-dlp thumbnail extraction + fallback to direct download
- Supported platforms:
  - Instagram posts (`instagram.com/p/ID`)
  - Facebook posts/photos (`facebook.com/<user>/posts/ID`, `facebook.com/photo/?fbid=ID`)
  - Twitter/X posts (`twitter.com/<user>/status/ID` or `x.com/<user>/status/ID`)

### 3. OCR + Visual Analysis (Step 2, Path C)
Two-stage text extraction:
- **Stage 1 - OCR**: Uses Tesseract to extract visible text from images
- **Stage 2 - Visual Analysis**: Uses Claude's vision API to:
  - Validate OCR results
  - Identify visual claims (charts, graphs, infographics)
  - Detect misleading techniques (cropped graphs, cherry-picked comparisons)
  - Extract context (branding, settings, emotional appeals)

### 4. Enhanced Analysis (Steps 3-4)
- Classification works on OCR output same as transcripts
- Medical analysis (SORT) applies to health claims in images
- General science validation includes:
  - Visual presentation quality
  - Misleading chart techniques
  - Reverse image search for context
  - Fact-checker sources for viral images

### 5. Updated Output Format (Step 5)
Analysis files now include:
- **Format** field: Video | Audio | Image Post | Carousel (N images)
- **Visual Analysis** section: Documents misleading visual techniques
- **Evidence Links**: Includes fact-check sites, original image sources

## Dependencies

- **Tesseract OCR**: Already installed (`brew install tesseract`)
  - Version: 5.5.1
  - Used for text extraction from images

- **Claude Vision API**: Built-in, used via Read tool
  - Analyzes visual content and context

- **yt-dlp**: Already installed
  - Downloads images via thumbnail extraction

## Example Workflows

### URL-based (Instagram carousel)

For a post like `https://www.instagram.com/p/DWKE4kJDbfz/`:

1. **Step 1**: yt-dlp detects 8-image carousel, downloads all images
2. **Step 2**:
   - Tesseract extracts text from each image
   - Claude vision analyzes visual claims, charts, context
   - Combined into structured content summary
3. **Step 3**: Classifies as Medical or General Science based on claims
4. **Step 4**: Validates claims, notes visual presentation issues
5. **Step 5**: Saves analysis with "Format: Carousel (8 images)"
6. **Step 6**: Cleans up downloaded JPGs
7. **Step 7**: Updates watch-urls.md

### Local folder (NEW: Recursive scanning)

For a folder like `/Users/pratik.joshi/Desktop/my-project/` with images in subfolders:

```
/Users/pratik.joshi/Desktop/my-project/
├── before/
│   ├── photo1.jpg
│   └── photo2.jpg
├── after/
│   ├── photo1.jpg
│   └── photo2.jpg
└── charts/
    └── data.png
```

1. **Step 0**:
   - Detects local folder path
   - **Validates depth** (max 5 levels from root folder) — fails if deeper
   - Recursively scans for images (finds 5 images across 3 subfolders)
   - Checks for duplicates (local only, no network calls)
   - Reports: `⏳ Step 0/7: Local folder detected (depth: 2 levels, 5 images), checking for duplicates...`
2. **Step 1**:
   - Recursively copies all JPGs/PNGs to `/tmp/url-analyzer/` (skips download phase entirely)
   - Creates path mapping file to preserve subfolder context
   - Reports: `✓ Step 1/7: 5 local images staged for analysis (from 3 subfolders, no download needed).`
3. **Step 2**:
   - OCR + visual analysis with subfolder context
   - Each image annotated with its source subfolder (e.g., "Source: before/photo1.jpg")
   - Analysis considers organizational patterns (before/after, time-series, categories)
4. **Step 3**: Same classification
5. **Step 4**: Same validation
6. **Step 5**: Saves with `Source: Local folder: /Users/pratik.joshi/Desktop/my-project (5 images across 3 subfolders)`
7. **Step 6**: Cleans `/tmp/url-analyzer/` but **preserves original folder**
8. **Step 7**: Updates watch-urls.md with folder path

**Depth limit**: Maximum 5 levels of subfolders. Folders exceeding this are rejected with: `(failed YYYY-MM-DD — folder structure exceeds maximum depth of 5 levels. Found: N levels)`

## Supported Social Media Platforms

| Platform | Video/Audio | Images/Carousels |
|----------|-------------|------------------|
| YouTube | ✅ | ❌ (video platform only) |
| Instagram | ✅ Reels | ✅ Posts, Carousels |
| Facebook | ✅ Videos, Reels | ✅ Posts, Photos |
| Twitter/X | ✅ Video tweets | ✅ Image tweets |
| LinkedIn | ✅ Videos | ❌ (not yet implemented) |
| **Local folder** | ❌ | ✅ Any folder with images |

## Error Handling

- If no images found: Marks as failed with "Could not download images from post" (URL) or "no supported image files found in folder tree" (local folder)
- If folder depth exceeds 5 levels: Marks as failed with "folder structure exceeds maximum depth of 5 levels. Found: N levels"
- If OCR fails: Falls back to visual analysis only
- If post is deleted/private: Standard yt-dlp error handling applies
- Image-only posts have no "transcript-only" mode (images are already lightweight)

## Recursive Folder Scanning (NEW)

### Overview

The skill now supports **recursive scanning** of local folders up to **5 levels deep**. This enables analyzing image collections organized in subfolder hierarchies.

### Why 5 levels?

- **Common use cases**: Most real-world image collections use 1-3 levels of organization
  - `project/before-after/before/*.jpg` (3 levels)
  - `research/2024/experiment-1/group-a/*.png` (4 levels)
- **Performance**: Deeper nesting can cause excessive scanning time and memory usage
- **Safety**: Prevents accidental analysis of entire home directories or system folders

### Depth calculation

Depth is counted **relative to the specified folder**, not from filesystem root:

```
Specified folder: /Users/pratik.joshi/Documents/study/
└── images/           ← Level 1
    └── week-1/        ← Level 2
        └── morning/   ← Level 3
            └── test.jpg

Relative depth: 3 levels ✅ (allowed)
```

```
Specified folder: /Users/pratik.joshi/Documents/study/
└── a/
    └── b/
        └── c/
            └── d/
                └── e/
                    └── f/
                        └── test.jpg

Relative depth: 7 levels ❌ (exceeds limit)
Error: "folder structure exceeds maximum depth of 5 levels. Found: 7 levels"
```

### Subfolder context in analysis

Images are analyzed with their subfolder paths preserved. This provides valuable context:

**Example 1: Before/After comparison**
```
Source folder: /Users/pratik.joshi/Desktop/weight-loss-claims/
├── before/photo.jpg    → Analysis notes: "Source: before/photo.jpg"
└── after/photo.jpg     → Analysis notes: "Source: after/photo.jpg"

Combined Analysis: "Images organized as before/after comparison. Check if same subject, same conditions, same time of day..."
```

**Example 2: Time-series data**
```
Source folder: /Users/pratik.joshi/Desktop/plant-growth/
├── week-1/sample.jpg
├── week-2/sample.jpg
└── week-3/sample.jpg

Combined Analysis: "Images organized chronologically by week. Time-series progression claim..."
```

**Example 3: Categorical organization**
```
Source folder: /Users/pratik.joshi/Desktop/supplement-claims/
├── clinical-trials/study-1.png
├── testimonials/review-1.jpg
└── product-labels/bottle.jpg

Combined Analysis: "Images grouped by evidence type. Clinical trial charts vs testimonials vs product labeling..."
```

### Performance considerations

- **Large folders**: Folders with 20+ images trigger a warning but still process
- **Mixed content**: Non-image files are automatically ignored (no error)
- **Symbolic links**: Followed by `find` (default behavior) — be cautious with linked directories
- **Hidden files**: Files starting with `.` are ignored by default

### Testing

#### Test 1: Flat folder (existing behavior)
```
## Pending
/Users/pratik.joshi/Desktop/single-level-images/
```

#### Test 2: Nested folder (new behavior)
```
## Pending
/Users/pratik.joshi/Desktop/nested-study/ [title: Multi-level Image Study]
```

#### Test 3: Instagram carousel (URL, existing behavior)
```
## Pending
https://www.instagram.com/p/DWKE4kJDbfz/
```

Then run: `/url-truth-analyzer`

The skill will now:
1. Detect content type (URL vs local folder)
2. For folders: Check depth, scan recursively
3. For URLs: Download images or video
4. Extract text + analyze visual content
5. Create full truth analysis with subfolder context
6. Move to Processed with success marker

#!/usr/bin/env python3
"""
Instagram image scraper using Playwright browser automation.
Extracts image URLs from Instagram posts when yt-dlp fails.
"""

import sys
import json
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

def scrape_instagram_images(url):
    """
    Scrape image URLs from an Instagram post using browser automation.

    Args:
        url: Instagram post URL (e.g., https://www.instagram.com/p/POST_ID/)

    Returns:
        dict: JSON with 'success' bool and 'images' list of image URLs
    """
    try:
        with sync_playwright() as p:
            # Launch browser in headless mode
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = context.new_page()

            # Navigate to Instagram post
            page.goto(url, wait_until='networkidle', timeout=30000)

            # Wait for images to load
            page.wait_for_timeout(3000)

            # Extract all image elements
            images = page.locator('img').all()

            # Collect image URLs with their dimensions
            image_data = []
            for img in images:
                try:
                    src = img.get_attribute('src')
                    alt = img.get_attribute('alt') or ''

                    # Filter out profile pictures, icons, and small thumbnails
                    if not src or any(x in src.lower() for x in ['profile', 'avatar', 's150x150']):
                        continue

                    # Filter out Instagram UI elements by alt text
                    if any(x in alt.lower() for x in ['profile picture', 'verified badge', 'icon']):
                        continue

                    # Get natural dimensions if available
                    width = img.evaluate('el => el.naturalWidth') or 0
                    height = img.evaluate('el => el.naturalHeight') or 0

                    # Only include images that are reasonably large (post images, not thumbnails)
                    if width >= 300 and height >= 300:
                        image_data.append({
                            'url': src,
                            'width': width,
                            'height': height,
                            'size': width * height
                        })
                except Exception as e:
                    # Skip problematic images
                    continue

            browser.close()

            # Sort by size (largest first) and return top 10
            image_data.sort(key=lambda x: x['size'], reverse=True)
            top_images = [img['url'] for img in image_data[:10]]

            if not top_images:
                return {
                    'success': False,
                    'error': 'No images found in post',
                    'images': []
                }

            return {
                'success': True,
                'images': top_images,
                'count': len(top_images)
            }

    except PlaywrightTimeout:
        return {
            'success': False,
            'error': 'Timeout loading Instagram page',
            'images': []
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'images': []
        }

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({
            'success': False,
            'error': 'Usage: python3 instagram_scraper.py <INSTAGRAM_URL>',
            'images': []
        }))
        sys.exit(1)

    url = sys.argv[1]
    result = scrape_instagram_images(url)
    print(json.dumps(result, indent=2))

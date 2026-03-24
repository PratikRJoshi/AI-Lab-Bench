# Scraper Setup Guide

## CloudFlare Cookie Extraction (Required)

Bogleheads.org is protected by CloudFlare's "Just a moment..." JavaScript challenge. To bypass this, you need to extract the `cf_clearance` cookie from your browser after solving the challenge.

### Step-by-Step Instructions

#### 1. Open Bogleheads in Your Browser
Navigate to: https://www.bogleheads.org/forum/index.php

You will see a "Just a moment..." page for 1-2 seconds while CloudFlare verifies your browser. Wait for it to complete and the forum page to load.

#### 2. Extract the Cookie

**Chrome / Brave:**
1. Press `Cmd+Option+I` (Mac) or `F12` (Windows/Linux) to open DevTools
2. Click the **Application** tab
3. In the left sidebar, expand **Cookies** → `https://www.bogleheads.org`
4. Find the cookie named `cf_clearance`
5. Double-click the **Value** column to select the entire value
6. Copy it (Cmd+C / Ctrl+C)

**Firefox:**
1. Press `Cmd+Option+I` (Mac) or `F12` (Windows/Linux) to open DevTools
2. Click the **Storage** tab
3. Expand **Cookies** → `https://www.bogleheads.org`
4. Find the cookie named `cf_clearance`
5. Double-click the **Value** to select and copy

**Safari:**
1. Enable Developer menu: Safari → Settings → Advanced → Show Develop menu
2. Press `Cmd+Option+I` to open Web Inspector
3. Click the **Storage** tab
4. Select **Cookies** → `https://www.bogleheads.org`
5. Find `cf_clearance` and copy the value

#### 3. Configure the Application

Open `src/main/resources/application.properties` and paste the cookie value:

```properties
app.scraper.cf-clearance-cookie=YOUR_COOKIE_VALUE_HERE
```

**Example:**
```properties
app.scraper.cf-clearance-cookie=0HhTRWlm.NGQzNmQ1YTYtNzRiMS00ZmY3LWFkMGItMGY1MzM3ZjJhYzI0
```

#### 4. Enable the Scraper

Set `app.scraper.enabled=true` in the same file:

```properties
app.scraper.enabled=true
```

#### 5. Run the Application

```bash
mvn spring-boot:run
```

The scraper will now use the CloudFlare cookie to access bogleheads.org.

---

## Cookie Expiration

CloudFlare cookies typically expire after **30 minutes to 24 hours**. If you get 403 errors again:

1. The cookie has expired
2. Repeat steps 1-3 to get a fresh cookie
3. Restart the application

---

## Future Automation: FlareSolverr

For production use without manual cookie management, you can use FlareSolverr (a CloudFlare solver service):

### Setup FlareSolverr (Docker)

```bash
docker run -d \
  --name flaresolverr \
  -p 8191:8191 \
  ghcr.io/flaresolverr/flaresolverr:latest
```

### Configuration

Add to `application.properties`:
```properties
app.scraper.flaresolverr-url=http://localhost:8191/v1
app.scraper.use-flaresolverr=true
```

**Note:** FlareSolverr integration is planned but not yet implemented. See the implementation plan for details.

---

## Troubleshooting

### Still Getting 403?
- **Cookie expired**: Get a fresh cookie (steps 1-3)
- **Cookie format error**: Make sure you copied the entire value without extra spaces
- **Wrong domain**: The cookie must be from `https://www.bogleheads.org`, not `http://` or a different subdomain

### "Enable JavaScript and cookies to continue"
- This message appears if the CloudFlare challenge didn't solve
- Make sure JavaScript is enabled in your browser
- Try in an Incognito/Private window to avoid extension interference
- Wait longer (up to 5 seconds) for the challenge to complete

### Application won't start
- Check that `cf_clearance` cookie value has no line breaks or quotes
- Verify `app.scraper.enabled` is set to `true` only when you have a valid cookie

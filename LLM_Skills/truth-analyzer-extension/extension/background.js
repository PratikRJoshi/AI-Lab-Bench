"use strict";

const BACKEND = "http://localhost:5757";

// Tracking/sharing params to strip before sending to the backend
const STRIP_PREFIXES = ["utm_", "igsh", "fbclid", "gclid", "ref", "si", "s"];

function stripTracking(rawUrl) {
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch (_) {
    return rawUrl;
  }
  const keep = new URLSearchParams();
  for (const [k, v] of parsed.searchParams.entries()) {
    const isTracking = STRIP_PREFIXES.some(p => k.startsWith(p));
    if (!isTracking) keep.append(k, v);
  }
  parsed.search = keep.toString();
  return parsed.toString();
}

async function analyzeUrl(rawUrl) {
  const url = stripTracking(rawUrl);

  let jobId;
  try {
    const resp = await fetch(`${BACKEND}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await resp.json();
    if (!data.id) throw new Error(data.error || "No job ID returned");
    jobId = data.id;
  } catch (err) {
    // Server not running — open the manual entry page with error notice
    browser.tabs.create({
      url: `${BACKEND}/?error=${encodeURIComponent(
        "Could not reach Truth Analyzer server on port 5757. Is it running?"
      )}`,
    });
    return;
  }

  browser.tabs.create({
    url: `${BACKEND}/results/${encodeURIComponent(jobId)}?url=${encodeURIComponent(url)}`,
  });
}

// Toolbar icon click → analyze current tab URL
browser.browserAction.onClicked.addListener(tab => {
  if (tab && tab.url) analyzeUrl(tab.url);
});

// Context menu — right-click any link
browser.contextMenus.create({
  id: "truth-analyze-link",
  title: "Analyze link with Truth Analyzer",
  contexts: ["link"],
});

// Context menu — right-click anywhere on the page (analyzes current page URL)
browser.contextMenus.create({
  id: "truth-analyze-page",
  title: "Analyze this page with Truth Analyzer",
  contexts: ["page", "frame"],
});

browser.contextMenus.onClicked.addListener((info, tab) => {
  const url = info.menuItemId === "truth-analyze-link"
    ? info.linkUrl
    : (tab && tab.url);
  if (url) analyzeUrl(url);
});

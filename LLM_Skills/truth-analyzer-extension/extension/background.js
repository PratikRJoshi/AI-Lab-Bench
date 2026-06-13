"use strict";

const BACKEND = "http://localhost:5757";

// Tracking/sharing params to strip before sending to the backend.
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

function notify(title, message) {
  // Best-effort OS notification; falls back silently if the API isn't available.
  try {
    browser.notifications.create({
      type: "basic",
      iconUrl: browser.runtime.getURL("icons/icon-48.png"),
      title,
      message,
    });
  } catch (_) {
    // No-op — the user will just see the error tab below.
  }
}

async function analyzeUrl(rawUrl) {
  const url = stripTracking(rawUrl);

  let resp;
  try {
    resp = await fetch(`${BACKEND}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
  } catch (err) {
    notify(
      "Truth Analyzer offline",
      "Could not reach the backend on port 5757. Run ./start.sh in the backend directory."
    );
    browser.tabs.create({
      url: `${BACKEND}/?error=${encodeURIComponent(
        "Could not reach Truth Analyzer server on port 5757. Is it running?"
      )}`,
    });
    return;
  }

  if (resp.status === 429) {
    let payload = {};
    try { payload = await resp.json(); } catch (_) {}
    const msg = payload.message ||
      "Concurrent analysis limit reached. Wait for one to finish.";
    notify("Truth Analyzer — limit reached", msg);
    return;
  }

  let data;
  try { data = await resp.json(); } catch (_) { data = {}; }

  if (!resp.ok || !data.id) {
    notify(
      "Truth Analyzer error",
      data.message || data.error || `Server returned ${resp.status}`
    );
    return;
  }

  browser.tabs.create({
    url: `${BACKEND}/results/${encodeURIComponent(data.id)}?url=${encodeURIComponent(url)}`,
  });
}

// Toolbar icon click → analyze current tab URL.
browser.browserAction.onClicked.addListener(tab => {
  if (tab && tab.url) analyzeUrl(tab.url);
});

// Context menu — right-click any link.
browser.contextMenus.create({
  id: "truth-analyze-link",
  title: "Analyze link with Truth Analyzer",
  contexts: ["link"],
});

// Context menu — right-click anywhere on the page (analyzes current page URL).
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

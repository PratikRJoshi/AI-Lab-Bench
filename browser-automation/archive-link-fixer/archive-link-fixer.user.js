// ==UserScript==
// @name         Archive.ph — Restore Original Links
// @namespace    https://github.com/PratikRJoshi
// @version      1.0
// @description  Rewrites archive.ph proxied links back to their original URLs
// @match        *://archive.ph/*
// @match        *://archive.is/*
// @match        *://archive.today/*
// @match        *://archive.li/*
// @match        *://archive.vn/*
// @match        *://archive.md/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  const PROXY_RE = /^https?:\/\/archive\.[a-z]+\/o\/[A-Za-z0-9]+\/(.+)$/;

  function fixLinks(root) {
    for (const a of root.querySelectorAll('a[href*="/o/"]')) {
      const m = a.href.match(PROXY_RE);
      if (!m) continue;
      let original = m[1];
      if (!/^https?:\/\//.test(original)) original = "https://" + original;
      a.href = original;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    }
  }

  fixLinks(document);

  new MutationObserver((muts) => {
    for (const mut of muts)
      for (const node of mut.addedNodes)
        if (node.nodeType === 1) fixLinks(node);
  }).observe(document.body, { childList: true, subtree: true });
})();

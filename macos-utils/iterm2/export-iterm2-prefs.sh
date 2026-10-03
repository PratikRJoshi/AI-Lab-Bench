#!/usr/bin/env zsh
# Exports iTerm2 preferences to a cleaned plist safe for a public repo.
# Restore on a new machine (quit iTerm2 first):
#   defaults import com.googlecode.iterm2 macos-utils/iterm2/com.googlecode.iterm2.plist
set -euo pipefail
out="${0:A:h}/com.googlecode.iterm2.plist"
tmp=$(mktemp -t iterm2-export.XXXXXX)
defaults export com.googlecode.iterm2 "$tmp"
python3 - "$tmp" "$out" <<'EOF'
import plistlib, re, sys
src, dst = sys.argv[1], sys.argv[2]
d = plistlib.load(open(src, "rb"))
# Machine/session state: window layouts, saved prompts, last-used paths, update timestamps
drop = {"Window Arrangements", "CodeReviewSavedPrompts", "NoSyncFrame_SharedPreferences",
        "SUFeedURL", "SULastCheckTime", "NSNavLastRootDirectory", "PrefsCustomFolder",
        "LoadPrefsFromCustomFolder"}
for k in list(d):
    if k in drop or k.startswith(("NoSync", "NSWindow Frame", "NSSplitView", "NSTableView")):
        del d[k]
for b in d.get("New Bookmarks", []):
    b.pop("Working Directory", None)
leak = re.compile(r"/Users/|\.internal\.|salesforce|sfdc|soma\.", re.I)
def walk(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items(): yield from walk(v, f"{p}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from walk(v, f"{p}[{i}]")
    elif isinstance(o, str) and leak.search(o):
        yield p
hits = list(walk(d))
if hits:
    sys.exit("refusing to write; possible internal data at: " + ", ".join(hits[:10]))
with open(dst, "wb") as f:
    plistlib.dump(d, f, fmt=plistlib.FMT_XML, sort_keys=True)
print(f"wrote {dst} ({len(d)} keys)")
EOF
rm -f "$tmp"

#!/usr/bin/env bash
# Enforce /layman as the default communication mode for every session.
# Emits an additionalContext reminder that Claude reads at session start.
cat <<'EOF'
DEFAULT COMMUNICATION MODE: layman (enforced every session).
- Plain English. No jargon (if a term is unavoidable, add a one-phrase clarifier).
- <=60 words per response. Code blocks exempt.
- Normal grammar (not caveman).
- Takes precedence over teaching, Socratic, and verbose-mentor styles.
- Auto-Clarity Exception: drop the word cap for security warnings, irreversible-action confirmations, and verbatim commands the user must run.
- Off only when the user says `stop layman`, `disable layman`, or `normal mode`. Re-enable with `/layman` or `in plain English`.
EOF
exit 0

---
description: Manage structured approval / elicitation requests
version: 0.11.2
allowed-tools: [Bash, Read]
---

# /vibe-approval

Surface or respond to the structured approval contract described in Giải
phẫu §10.4.  Every human-in-the-loop decision (permission bubble, dangerous
diff, elicitation) is persisted under
`.vibecode/runtime/approvals/appr-<id>.json` so any UI can render it.

## Usage
```bash
# List currently-pending approvals
python -m vibecodekit.cli approval list

# Create a new approval (typically from inside a hook or subagent)
python -m vibecodekit.cli approval create \
  --kind permission --title "Allow rm -rf node_modules?" \
  --risk medium --summary "Rebuild deps"

# Respond to a pending approval
python -m vibecodekit.cli approval respond appr-xxxxxxxx allow --note "verified"

# Inspect a specific approval (request + response merged)
python -m vibecodekit.cli approval get appr-xxxxxxxx
```

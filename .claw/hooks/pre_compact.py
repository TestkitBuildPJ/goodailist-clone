#!/usr/bin/env python3
"""pre_compact hook — allow-only; logs which layer was triggered."""

import json
import sys

sys.stdout.write(json.dumps({"decision": "allow"}))

---
description: Run Deep Bug Hunter, audit all roles/UI/workflows, and auto-fix any detected bugs.
---
1. Run `python tests/deep_bug_hunter.py` in the terminal.
2. Verify all 4 audit layers:
   - Layer 1: Zero 500/422 errors across all GET/POST routes for all 5 roles.
   - Layer 2: Zero Ghost UI (no links, buttons, or financial fields visible in HTML to unauthorized roles like `warehouse` or `baskool`).
   - Layer 3: Full E2E workflow integrity (Commercial PO/SO -> Baskool Weighing -> Warehouse Cartable Approve -> Finance Kardex & Year-End Close).
   - Layer 4: Persian/Arabic digits & Turkish decimal comma fuzzing.
3. If ANY test fails or ANY UI/RBAC leak is found, immediately fix the Python code and Jinja2 templates, and re-run `python tests/deep_bug_hunter.py` until 100% PASS (0 bugs).
4. Output a concise 10-line summary of the health check.

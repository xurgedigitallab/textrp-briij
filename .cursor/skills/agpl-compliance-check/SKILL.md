---
name: agpl-compliance-check
description: Perform AGPL-3.0 compliance verification and fixes for TextRP-Briij (Synapse fork). Ensures headers, notices, source availability, and repo hygiene for modifications. Trigger on new modules, features, or before deploy/PR.
version: 1.1.0
tags: [license, compliance, agpl, opensource, synapse, textrp]
---

# AGPL-3.0 Compliance Skill for TextRP-Briij

You are enforcing AGPL-3.0 compliance on a forked Synapse project (TextRP-Briij). The entire codebase must remain AGPL-3.0 compatible, with proper notices for modifications and network-use obligations.

## When to Activate
- User says: "check AGPL compliance", "ensure compliance for new module", "run license check before deploy", "add AGPL headers", or similar.
- After major changes (new auth provider, XRPL handlers, etc.).
- Before pushing to public repo or production.

## Strict Rules
- ONLY edit files explicitly mentioned by user or obvious candidates (e.g., new briij/auth/*.py, README.md, LICENSE*).
- Never remove existing upstream headers/notices.
- xrpl-py (ISC) → preserve its LICENSE text/reference only.
- Always suggest public repo push + runtime source link.
- After fixes: Run `grep -r "GNU Affero" .` or similar to verify headers.
- End each major step with: "✅ COMPLIANCE CHECKPOINT X COMPLETE"

## Step-by-Step Workflow (Execute Sequentially Unless User Specifies Jump)

1. Scan & Report Current State
   - List files without AGPL header (focus on .py, .md in briij/, synapse/custom/).
   - Check for LICENSE-AGPL-3.0 or COPYING in root.
   - Verify README mentions AGPL + public repo URL.
   - Check if any /info or custom endpoint exposes source repo.

2. Add/Verify File Headers (New/Modified Files)
   - For every .py file in briij/ or custom modules:
     Insert at top (after shebang if present):

```text

Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors

This file is part of TextRP-Briij, a modified version of Synapse.

TextRP-Briij is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

...
You should have received a copy of the GNU Affero General Public License
along with TextRP-Briij.  If not, see <https://www.gnu.org/licenses/>.
```

- For JS/TS (Briij SDK): Use `/* ... */` block with same text.
- Do NOT overwrite existing Element/Synapse copyrights — append if needed.

3. Update Repo-Level Notices
- Ensure root has `LICENSE-AGPL-3.0` (copy full AGPL text if missing).
- In README.md: Add/verify block:

```text
TextRP-Briij
Fork of Element Synapse with native XRPL/Xahau integration.
Licensed under GNU Affero General Public License v3.0 (or later) — see LICENSE-AGPL-3.0
Source: https://github.com/xurgedigitallab/textrp-briij (always public)
Modifications: See CHANGELOG.md or git history.
Third-party: xrpl-py (ISC) — see licenses/xrpl-py.LICENSE
```

- Create/update `licenses/` folder with xrpl-py license copy.

4. Runtime Source Disclosure (AGPL §13 – Network Use)
- Recommend adding a simple endpoint (if not present):
In a custom module or handler: `/briij/info` returning JSON with `"source_repository": "https://github.com/xurgedigitallab/textrp-briij"`
- Or static: Serve a NOTICE file at `/.well-known/briij-source`.
- Suggest homeserver.yaml note or admin UI link to repo.

5. Document Changes
- Append to CHANGELOG.md or docs/compliance.md:
"Added XRPL wallet auth module – compliant under AGPL-3.0. Headers added, source repo public."

6. Final Verification
- Suggest commands: `grep -r "Affero General Public License" .` (should hit new headers)
- Remind: Push to public GitHub before deploy.
- Output summary table:
| Item                          | Status     |
|-------------------------------|------------|
| File headers present          | ✓ / ✗     |
| Repo LICENSE-AGPL-3.0         | ✓ / ✗     |
| README notice + repo link     | ✓ / ✗     |
| Runtime source disclosure     | Suggested |
| xrpl-py notice preserved      | ✓ / ✗     |

7. Cleanup & Next Steps
- Commit message: "chore: enforce AGPL-3.0 compliance for [feature]"
- If issues: List exact fixes needed.
- Remind: If commercial/SaaS closed variant ever planned → contact Element for dual-license.

Reply with progress per checkpoint. If user provides specific files/feature, focus there first.
# scripts/ has been archived (SG-H-103)

This folder used to hold one-off manual scripts (data fixes, exploratory
API calls) written during early development. Per `docs/refactor-siamganesh/
PHASES.md` (SG-003 / SG-H-103), they were confirmed to have zero runtime
or CI usage — see the previous `scripts/README.md` for the full list of
characteristics that made them unsafe to keep alongside the real app
code (real network calls at import time, no lint/type-check/test
coverage, `test_*.py` naming that had to be explicitly excluded from
pytest discovery).

The files themselves are not deleted, only removed from the working
tree. Full history and content are still available at the commit just
before this one:

  git show 6bda12d -- scripts/
  git checkout 6bda12d -- scripts/   # to restore a single file's old contents

If you need one of these capabilities for real, build it as a proper,
tested module under `core/` — don't resurrect a script here.

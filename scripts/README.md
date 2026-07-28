# scripts/ — legacy ad hoc tooling (not part of the app runtime)

Every file in this folder is a one-off manual script written at some
point to poke at an external API (Supabase, GitHub, Gemini, Facebook)
or clean up data during development. **None of them are imported by
`app.py`, run in production, or covered by CI.**

Characteristics to know before touching or running any of these:

- Several make real network calls at import/module level (e.g.
  `test_gemini.py`, `test_github.py`, `test_supabase*.py`) — running
  them executes real API requests against whatever credentials are in
  your local environment, not a mock.
- They are excluded from pytest discovery via `../pytest.ini`
  (`testpaths = tests`), specifically because their `test_*.py` naming
  would otherwise make a bare `pytest` invocation from the repo root
  collect and "run" them as if they were real automated tests.
- They are not linted, type-checked, or maintained as part of the
  standard quality gates in `.github/workflows/ci.yml`.

If you need one of these capabilities for real, promote the relevant
logic into `app.py` (or, after the refactor described in the
`siamganesh-online-frontend` repo's `docs/refactor-siamganesh/`, into
the owning module/service) with proper tests — don't extend a script
here.

See `docs/refactor-siamganesh/PHASES.md` (SG-003 / SG-H-103) in that
same doc set for the plan to eventually archive this folder entirely
once confirmed nobody still runs these manually.

Archive of development scripts moved from `scripts/` to keep the repository root tidy.

Why:
- Files in `scripts/` were a mix of one-off migration helpers, debugging utilities and CI helpers.
- To reduce clutter and the chance of accidentally running destructive scripts, these were moved to `archive/dev-scripts/`.

What to do if you need them:
- The files remain in `archive/dev-scripts/` and are preserved in git history.
- If you want to restore any script to active use, move it back to `scripts/` or `tools/` and document its purpose.

Notes:
- Some scripts are destructive (e.g. deleting sqlite DB); read the header comments before running.
- Consider migrating long-term utilities into a `tools/` package with README and safety checks.

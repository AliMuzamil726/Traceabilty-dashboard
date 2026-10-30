# Next steps

1. **Session hardening.** Sign-in now mints a signed token (`core/sessions.py`), production
   ignores the development `X-Officer-Id` header, and sign-in attempts are rate limited;
   `get_current_officer` stayed the single seam. Still to do: a revocation list (so a
   stolen token can be cut short), shorter lifetimes with refresh, and lockout after
   repeated failures. The default password (`12345678`) is still set by the seed, so a
   forced change on first sign-in belongs here too.
2. **Supabase or PostgreSQL migration.** The models avoid SQLite-only features. Steps:
   point `DATABASE_URL` at Postgres, run the migrations, replace the `BEGIN IMMEDIATE`
   counter locking with `SELECT ... FOR UPDATE` in `core/ids.py`, rerun the whole suite
   and `scripts/seed_perf.py`, compare query plans against the indexes.
3. **Deployment.** HTTPS, a real tile provider, secrets from the environment, a shared
   cache and rate limit store, log shipping without personal data, backups.
4. **Run the Playwright suites** (`frontend/e2e`) in CI on every change.
5. **Upgrade Tailwind** to clear the remaining build tool advisories.

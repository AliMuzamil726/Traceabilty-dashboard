# Next steps

1. **Login and roles.** Replace the header identity with real sessions, hash and rotate
   credentials, keep `get_current_officer` as the single seam so no module changes.
   Settings already holds the officer records and the role matrix this needs (D-121).
2. **Supabase or PostgreSQL migration.** The models avoid SQLite-only features. Steps:
   point `DATABASE_URL` at Postgres, run the migrations, replace the `BEGIN IMMEDIATE`
   counter locking with `SELECT ... FOR UPDATE` in `core/ids.py`, rerun the whole suite
   and `scripts/seed_perf.py`, compare query plans against the indexes.
3. **Deployment.** HTTPS, a real tile provider, secrets from the environment, a shared
   cache and rate limit store, log shipping without personal data, backups.
4. **Run the Playwright suites** (`frontend/e2e`) in CI on every change.
5. **Upgrade Tailwind** to clear the remaining build tool advisories.

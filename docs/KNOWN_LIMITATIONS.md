# Known limitations

* **Sessions are signed tokens, not server-side sessions.** Sign-in checks the password
  and mints an HMAC-signed token (12 hours) that proves the officer id; the token is not
  encrypted, so it carries only the id and timestamps. The `X-Officer-Id` header still
  works in development (the officer switcher), but production ignores it. There is no
  revocation list yet: signing out forgets the token on the device, and a stolen token
  stays valid until it expires, so keep `SESSION_TTL_SECONDS` short if that matters.
* **Every account starts on the same password** (`12345678`), set by the seed, and the
  product does not force a change on first sign-in. An administrator adding an officer
  in Settings creates them on that password too.
* **Settings changes apply to new work only.** A crop clock, tolerance or ratio that is
  changed does not alter a submitted fieldbook, a weighed delivery or a heap that is
  already open; those keep the values they were recorded with. This is deliberate, but
  it means a correction has to be made before the work, not after.
* **One process for settings too.** The resolved-value cache is per process, cleared by
  `config.changed`. With several workers a change would reach only the worker that made
  it until the others expire theirs.
* **Dummy data.** The seed farmers, deliveries and heaps are invented. Settings can
  remove the unused dummy officers, offices and sites; anything real work refers to is
  kept.
* **Locations are incomplete.** Tehsils and field offices are a working subset, not the
  full national list.
* **Map tiles** come from a public provider whose terms limit heavy use; a production
  deployment needs its own tile account or server. Maps fall back to a plain message
  when tiles cannot load.
* **Postcode lookup** (UK) uses postcodes.io and falls back to a bundled area table when
  it is unreachable, so coordinates may be coarser offline.
* **One process.** Rate limits and the dashboard cache live in memory, so they are per
  process. Several workers need a shared store.
* **SQLite.** Single writer with WAL. Fine for the pilot load; PostgreSQL is the planned
  store.
* **First read after a write is slow** (about 3 s) while the Harvest Radar dataset
  rebuilds.
* **Tailwind 3 build tooling** carries seven low risk advisories (build time only).
* **Windows launchers** were not run in the audit environment.

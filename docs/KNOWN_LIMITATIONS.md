# Known limitations

* **Sign-in is not authentication yet.** The sign-in screen does check a password
  against a stored PBKDF2 hash, but it hands back no session: every request afterwards
  still names the acting officer in an `X-Officer-Id` header, which is not a secret and
  can be spoofed. Officer scoping (mine or all) and the ownership rule (D-110) are real
  checks but only as trustworthy as that header. Do not expose the API to an untrusted
  network until a session layer exists.
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

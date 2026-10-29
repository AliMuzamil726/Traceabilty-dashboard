# SAWIE

Fibre-crop traceability platform. Field officers register farmers, map their fields and
keep digital fieldbooks. Harvested crop then moves through pickup and delivery into a
heap (cotton) or batch (hemp) at a ginner or processor, and ends as QR-tagged bales
that trace back to farmers and fields.

Two crop programmes run in this phase: **Cotton** for Pakistani farmers and **Hemp** for
UK farmers. The selected crop decides the country, form fields, units and dropdown
lists everywhere in the product.

All nine modules are built. The sign-in screen checks a password, but every request
still names the acting officer in an `X-Officer-Id` header, so this is not
authentication yet (`docs/KNOWN_LIMITATIONS.md`).

## Modules

| No | Name | Folder | Route | API prefix | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Dashboard / Home | `module_1` | `/` | `/api/v1/dashboard` | **built** |
| 2 | Register Farmer | `module_2` | `/register` | `/api/v1/register` | **built** |
| 3 | Fieldbook | `module_3` | `/fieldbook` | `/api/v1/fieldbook` | **built** |
| 4 | Harvest Radar | `module_4` | `/radar` | `/api/v1/radar` | **built** |
| 5 | Deliveries | `module_5` | `/deliveries` | `/api/v1/deliveries` | **built** |
| 6 | Heap | `module_6` | `/heaps` | `/api/v1/heaps` | **built** |
| 7 | QR Tracing | `module_7` | `/qr` (public page `/trace/:code`) | `/api/v1/qr` | **built** |
| 8 | Settings | `module_8` | `/settings` | `/api/v1/settings` | **built** (administrator only) |
| 9 | Gate Reception | `module_9` | `/gate` | `/api/v1/gate` | **built** |

Data flows Farmer and Field (2) to Fieldbook (3) to Harvest Radar (4) to Deliveries (5),
through Gate Reception (9), to Heap (6) to QR Tracing (7); the Dashboard (1) reads from
all of them.
Build order: 2, 3, 4, 5, 6, 7, then 1, then 8, then 9.

## Dashboard (Module 1)

The home screen. A header greets the officer and holds the controls, all kept in the web
address: crop (all, cotton, hemp), season, range (last 7 or 30 days, this season, or a
custom range) and scope (my work, or the whole programme; officers start on their own
work, administrators on the programme). Figures refresh every minute and on Refresh.

The pipeline tracker is the main element: farmers registered, fields mapped,
fieldbooks, harvest ready or done, deliveries delivered, heaps and bales, QR codes
scanned. Each stage shows its count, a bar against the first stage, the share of the
stage before, a line on what it measures, and opens its module already filtered. Below
it sit seven KPIs, six charts (each with a Show data table), a satellite map of every
field coloured by crop or readiness, an attention panel, a recent-activity feed and, for
administrators, a table of each officer's work. An empty database shows a Get started
checklist instead of empty charts.

The attention panel checks eight rules: ready fields with no pickup request for over 7
days; overdue fields; deliveries scheduled but not dispatched after their date; flagged
weight variances; open heaps idle for 14 days; hemp licences expired or expiring within
30 days; draft fieldbooks untouched for 21 days; farmers with no mapped field. Only
overdue fields and expired licences are red; everything else is wheat. The thresholds are
in `backend/module_1/config.py` until Settings takes them over.

The dashboard owns no data. Every number comes from the owning module's public API, the
same functions its own screen uses, and a reconciliation test checks they agree. Each
section is a separate request cached for 30 seconds and dropped on any change, so one
slow or failing section shows its own retry without breaking the page.

## Settings (Module 8)

The administration console, at `/settings`. Everything in it is administrator-only
except **My preferences**, which every officer uses for their own sidebar, table
density and default crop.

| Section | What it changes |
| --- | --- |
| Officers | Who may use the product, their field office and role. New accounts start on the shared default password and each officer changes it from their profile |
| Permissions | A read-only matrix of what each role may do, generated from the rules the server enforces |
| Field offices | The teams farmers and officers belong to |
| Crops and season | The crop clock, with a preview of how many fields would change readiness bucket |
| Ginners and processors | Delivery and heap sites. A code is fixed once heaps carry it |
| Dropdown lists | The options every form offers: add, rename, reorder, deactivate, import and export |
| Locations | Province, district and tehsil (and UK postcode areas). Renaming or merging moves every farmer that names the place, in one transaction |
| Deliveries and heaps | Variance and moisture thresholds, outturn ratios and bale weights |
| Alerts and thresholds | When the dashboard calls something a problem, and the radar benchmarks |
| Validation rules | ID number digits, field area limits, name and phone rules |
| Map | Tile provider, labels, default centres, with a live preview and a Test tiles button |
| QR and labels | The public base URL (with a warning for localhost) and the label grid |
| Audit log | Every change, with its before and after. Read-only, exportable |
| Backup and restore | SQLite online backups, and a guarded restore |
| System information | Versions, record counts, health checks and the dummy-data cleanup |

Three rules run through the whole module:

* **Keys are stable, labels are not.** Records store the value key, so a label can be
  corrected at any time and every existing record follows.
* **Deactivating hides, deleting removes.** Deactivating takes a value out of new forms
  and changes nothing already recorded. Deleting is offered only while nothing uses it.
* **Changes apply to new calculations.** A heap that is already open keeps the ratio it
  froze when it opened, a submitted fieldbook stays as it was, and history never moves.

## Register Farmer (Module 2)

A field officer picks the crop programme, which decides the country, the details asked
for and the dropdown lists. Entering an ID number looks it up: a new farmer gets a
preview of their **SAWIE ID** (a plain number from 1001, assigned when the record is
saved), while an existing one has their personal details filled in, leaving this
season's variety, tenure and previous crop to be entered. One person keeps one SAWIE ID
for life, and a farmer belongs to one crop programme.

Fields are then drawn on a satellite map. Every field in the database is shown
underneath as context, because boundaries must not overlap: the server measures each
polygon in its local UTM zone and refuses any boundary that overlaps an existing field
by more than 0.01 m2, however small a share that is. Fields that touch along a shared
edge are fine. Field IDs are `{sawie_id}-{nn}`, so `1001-03` names its farmer, and a
number is never reused after a field is removed.

A farmer is not complete for the later modules until at least one field is mapped,
which the farmer list and profile both say.

No API keys are needed. The map uses Esri's public tiles, and postcodes resolve through
postcodes.io with a bundled fallback table.

## Fieldbook (Module 3)

The fieldbook is each field's season diary. The officer opens it by choosing
themself (an administrator may choose any officer), then one of their farmers
(searchable by SAWIE ID or name, with the crop and fieldbook status shown), then the
field, then the season. A farmer with no mapped field is sent to Register Farmer to map
one. A link such as `/fieldbook?farmerId=...&fieldId=...` opens with both preselected.
Each field has one fieldbook per season; opening it again resumes where it was left.

Cotton has 11 steps and hemp 9. The questions are not written in React: they come from
`backend/module_3/form_definitions/cotton.json` and `hemp.json`, which the screen renders
and the server validates with, so both always agree. Dropdowns read the master lists.
Some steps repeat (each irrigation, spray or picking is an entry that can be added,
duplicated or deleted); some may be marked "Nothing to record for this step". Answers
can raise warnings, which ask for a second look, or errors, which must be fixed.
Values such as the area sown and the variety start from Register Farmer. Up to 8
photos per fieldbook can be added (JPEG, PNG or WebP, 8 MB each).

Beside the form, a crop clock shows the days since sowing against the harvest window
(cotton ready from day 135 to day 200, hemp from day 95 to day 125), and an activity
list shows what was recorded and by whom. On the last step, **Save and Submit** asks
for confirmation, listing any warnings, and then locks the fieldbook for good: from
then on it is read only and its field can no longer be reshaped or removed. A harvest
picking (cotton) or baling (hemp) marked ready for pickup is announced for Harvest
Radar.

## Harvest Radar (Module 4)

The radar is the control tower between the field and logistics. For the chosen crop
and season it puts every mapped field into one bucket, worked out from the fieldbook
and the crop clock: No sowing data, Growing, Approaching, Ready or Harvested. Fields past
the end of the harvest window carry an Overdue badge. Each field shows its days after
sowing, expected ready date, next milestone ("Ready in 12 days", "Overdue by 9 days"),
estimated quantity (from the fieldbook yield, or a benchmark marked as an estimate) and
its pickup state.

Four figures sit at the top: ready now, ready within 14 days, pickup requested and
overdue. Below them the buckets filter the views, and a filter bar narrows by search,
location (district, tehsil and village for cotton; county and region for hemp), field
office, officer, status, pickup state and expected ready date. Every filter lives in the
web address, so a view can be shared or reloaded. The same fields appear as a table, on
the satellite map coloured by status, and on a calendar of expected ready dates with an
8-week demand chart. The page refreshes every minute.

Officers select ready or harvested fields and request a pickup, with an optional date
and note; any field that cannot be requested is listed with the reason. A field can have
only one open request per season, a request can be cancelled with a reason while it is
still waiting, and a field with an open request cannot be removed. Officers act for the
farmers they registered and can view everyone else's read only; administrators act for
all. Deliveries (Module 5) picks the requests up from here.

## Deliveries (Module 5)

Deliveries moves harvested crop from the farm to a ginner (cotton) or a processor (hemp).
Pickup requests made in Harvest Radar wait in the Requests inbox. An officer selects one
or several and schedules them together: the site, date, driver, phone and vehicle apply
to all, and each request gets its own delivery (`DL-0001` onwards). The radar shows the
request as scheduled.

A delivery moves strictly from scheduled to in transit (Dispatch, optionally with the
weight taken at the farm) to delivered (Receive at gate, with the weighbridge weight and
moisture). The gate can also record that decision on its own screen (Module 9, below).
Before confirming, the gate officer sees the difference from the field weight
or the estimate: within 3 percent is fine, from 3 percent it asks for a check, from 5
percent it is flagged and needs a note. Moisture above 12 percent (cotton) or 16 percent
(hemp) is warned. A delivery can be cancelled with a reason until it is delivered, which
also closes the radar request so the field can be requested again; receiving it closes
the request the same way. Once delivered it cannot change, except by an administrator
correction with a reason, which is audited and, for an accepted load, copied onto the
gate entry.
Each delivery has a one-page slip for the driver with a QR of its number. Cotton weights
are also shown in maunds (40 kg).

## Gate Reception (Module 9)

The ginner's or processor's gate, at `/gate`, filtered by site and crop. **Due to
arrive** lists the in-transit deliveries heading to the site that have not reached the
gate yet; **Record arrival** opens one gate entry for that delivery, copying its vehicle
and driver. A delivery can have only one gate entry, so arriving twice is refused.

**At the gate** lists the loads standing there. Accepting a load asks for the weighbridge
readings, gross and tare: the net weight (gross minus tare) is what the delivery records.
The screen shows the variance against the field weight or the pickup estimate before
confirming, using the tolerances in force for the crop, and holds a flagged load until a
note explains the difference. Accepting marks the delivery delivered with that net
weight, exactly as the Receive dialog in Deliveries does, including warnings, audit,
history and the Radar release. Receiving or cancelling from Deliveries while a load
stands at the gate settles its entry instead of leaving a second open record.

Rejecting a load needs a reason (3 to 500 characters) and cancels the delivery, which
also releases its Radar request; the reason is kept on both records. Five figures sit at
the top: due to arrive, at the gate, accepted today, rejected today and the net weight
received today. Every decision is audited with the officer and the weights.

## Heap (Module 6)

A heap (cotton, at a ginner) or batch (hemp, at a processor) gathers delivered crop from
many farmers. Delivered loads can be added from the Heap screen or straight from the
Receive dialog in Deliveries. From the total weighbridge weight and the outturn ratio
(34 percent of seed cotton to lint, or 25 percent of hemp straw to fibre, placeholders to
confirm) the screen shows the expected output, how many bales of 170 kg (or 250 kg) it
allows, how many have been made, and how much input remains; hemp also shows the
expected shiv and dust. Each farmer's share of the input is listed, and adds up to 100
percent.

Bales get sequential serials (`BWP-G1-H01-001`) and can never exceed the maximum, even
when two people record at once. The ratio and bale size are fixed once the first bale
exists. A heap closes when less than one bale of output remains; an administrator can
close earlier with a reason, and the remainder is recorded. A closed heap is locked. The
heap is what lets every bale be traced back to its farmers and fields.

## QR Tracing (Module 7)

Every heap or batch and every bale gets its own code as soon as it is made: twelve random
characters (for example `K7QF2MXD4BNA`), never derived from the serial, so nobody can guess
another bale's code. The code is printed as a QR that opens `{PUBLIC_BASE_URL}/trace/{code}`.

Scanning opens a public page with no login and no sidebar, built for phones. It shows the
product, serial and weight, the heap or batch, the season, the ginner or processor and its
region, the number of farms and fields, the districts (cotton) or counties (hemp), the
harvest window, the journey from registration to bale, and four checks: all fieldbooks
submitted, all deliveries weighed, the heap closed, and bales within the expected output.
A failed check is shown, never hidden. It never shows names, ID numbers, phone numbers,
villages, farm names, licences, postcodes, coordinates or officer names. A withdrawn code
and a made-up one both say "This code is not valid". The page is rate limited and cached
for 60 seconds; each scan is logged with a salted hash of the address, never the address.

The QR Tracing screen (`/qr`) lists each heap's code, scan counts and bales. From there you
can print A4 label sheets (3 by 8, PDF), download a ZIP of QR images or one label as PNG,
copy a link, and (administrators, with a reason) revoke a code or make a new one for a
bale. Voiding a bale in Heap revokes its code automatically. "Find a code" takes a code, a
bale serial or a trace link, typed or scanned with the camera where the browser supports
it, and opens the full trace: bale, heap, deliveries, farmers with their share, each field
on the satellite map, and its fieldbook log. ID numbers stay masked unless you registered
that farmer or are an administrator.

### Scanning codes with a phone

`http://localhost:5173` only works on the computer running SAWIE; a phone that scans it
looks for a server on itself and fails. The QR screen warns while the address is local.
To test with a phone on the same Wi-Fi:

1. Find the computer's network address: run `ipconfig` and read "IPv4 Address" (for
   example `192.168.1.20`).
2. In `backend\.env` set `PUBLIC_BASE_URL=http://192.168.1.20:5173` and add the same
   address to `CORS_ORIGINS`.
3. Start the frontend so other devices can reach it: `cd frontend` then
   `npm run dev -- --host` (the shortcut `frontend.bat` listens on this computer only).
4. Restart the backend and print the labels again. Codes already printed keep working
   once the address is right, because the address is not stored in the code.

Windows may ask to allow Node.js through the firewall; allow it on private networks.

## Folder structure

```
project-root/
  backend.bat              double-click: set up and start the API
  frontend.bat             double-click: start everything and open the browser
  requirements.txt         Python dependencies
  README.md  .gitignore  .gitattributes
  docs/                    ARCHITECTURE, DESIGN_SYSTEM, DATA_MODEL, CONTRACTS, DECISIONS, TESTING
  backend/
    venv/                  created by backend.bat (git-ignored)
    .env.example           copied to .env on first run
    app/                   main.py, registry.py, lifespan.py
    core/                  config, database, deps, errors, events, audit, guards, logging, pagination, ids
    shared/                models/, repositories/, schemas/, routers/ (master, officers, offices, health)
    module_1/ ... module_7/  __init__, meta, router, schemas, models, repository, services, public_api, events, tests/
    module_2/              built: services/ is a package (validators, ids, geometry, farmers,
                           fields, locations, postcode, ratelimit) and data/ holds the
                           UK postcode-area fallback table
    module_3/              built: services/ package (formschema, books, selectors, photos,
                           clock), form_definitions/ (cotton.json, hemp.json), seed.py
    module_4/              built: services/ package (readiness, dataset, radar, pickups,
                           cache, config)
    module_5/              built: services/ package (deliveries, queries, weights,
                           validators, slip), seed.py (thresholds)
    module_6/              built: services/ package (heap_calc, heaps, views,
                           permissions), seed.py (heap defaults)
    module_1/              built: config.py (alert thresholds), services/ package (filters,
                           sources, overview, charts, alerts, activity, mapview,
                           officers, links, cache); owns no tables
    module_8/              built: settings values and history, officers and reference
                           data, config proxies, backup and restore, audit view
    module_9/              built: gate_entries (models, repository, services, events);
                           accepting or rejecting a load settles the delivery through
                           Module 5's public API, in the same transaction
    scripts/               seed.py, seed_data/*.json, seed_perf.py (10,000-farmer measuring set)
    migrations/            Alembic scaffold (alembic.ini next to it)
    data/                  SQLite database (git-ignored)
    storage/               uploads, e.g. uploads/fieldbook/{fieldbook_id}/ (git-ignored)
    tests/                 cross-module and architecture tests
  frontend/
    index.html  package.json  vite.config.ts  tailwind.config.ts  postcss.config.js  tsconfig.json  .env.example
    scripts/               probe.mjs, hash-file.mjs (used by frontend.bat), check-colors.mjs
    src/
      app/                 App, router, moduleRegistry, providers, layout/
      core/                api/, store/, hooks/, utils/
      design-system/       tokens.css, components/, motion/
      shared/              components/ (OfficerSwitcher, ModulePlaceholder, ErrorBoundary, NotFound, ...)
      module_1/ ... module_9/
    e2e/                   Playwright smoke tests for Modules 2 and 3 (not part of npm run test)
```

## Prerequisites

* Windows 10 or 11 (macOS and Linux work with the manual commands below).
* **Python 3.11 or newer** from https://www.python.org/downloads/windows/ (tick "Add python.exe to PATH").
* **Node.js 22.12 or newer** (the current LTS) from https://nodejs.org/ (includes npm). Node 18 and 20 are past end of life and the build tools no longer support them.
* Internet access for the first run (dependency downloads). No CDN is used at runtime;
  fonts are bundled.

## Run it

1. Double-click **`frontend.bat`**.

That is all. The script checks Node, installs frontend packages when needed, sees that
the backend is not running, opens `backend.bat` in a second window (which creates the
Python environment, installs packages and starts the API), waits for the API to answer,
then starts the web app and opens **http://localhost:5173** in your browser.

The first run downloads dependencies and takes a few minutes. Later starts take seconds.

To run only the API, double-click `backend.bat`. Close a window (or press Ctrl+C in it)
to stop that part.

| What | Address |
| --- | --- |
| Web app | http://localhost:5173 |
| API | http://127.0.0.1:8000 |
| API docs (Swagger) | http://127.0.0.1:8000/docs |
| Health | http://127.0.0.1:8000/api/health |

### Manual commands (any OS)

```bash
# backend
python -m venv backend/venv
backend/venv/Scripts/activate        # Windows; on macOS/Linux: source backend/venv/bin/activate
pip install -r requirements.txt
cp backend/.env.example backend/.env
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# frontend (second terminal)
cd frontend && npm install && npm run dev -- --open
```

Reseed reference data at any time (safe to repeat): `cd backend && python -m scripts.seed`.

## Environment variables

`backend/.env` (created from `backend/.env.example`):

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./data/sawie.db` | The only switch between SQLite and Supabase Postgres. Relative paths resolve against `backend/`. |
| `APP_ENV` | `development` | `development`, `test` or `production` (production requires the `X-Officer-Id` header) |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | comma-separated |
| `PUBLIC_BASE_URL` | `http://localhost:5173` | address the QR codes open (`{PUBLIC_BASE_URL}/trace/{code}`). Use the computer's network address to scan with a phone; see QR Tracing. |
| `QR_IP_SALT` | `sawie-dev-salt-change-me` | secret mixed into the hash of a scanner's address. Production refuses to start with a placeholder value |
| `UPLOAD_DIR` | `./storage` | uploaded files |
| `SEED_ON_START` | `false` | insert missing reference rows (offices, officers, master lists, crop clock) on start; existing rows are left alone. `.env.example` turns it on for development; production refuses `true` because the seed creates officers with a known password |
| `DEFAULT_OFFICER_CODE` | `PK-MUL-01` | acting officer in development when no header is sent |
| `LOG_LEVEL` | `INFO` | |

`frontend/.env` (optional, from `frontend/.env.example`):

| Variable | Default | Meaning |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `/api` | API base; the Vite dev server proxies `/api` to port 8000 |

## Seed data

All seeded offices and officers are marked dummy (`is_dummy = true`) for replacement later.

* Pakistan: Multan, Bahawalpur and Lodhran Field Offices, two officers each.
* United Kingdom: East of England and East Midlands Field Offices, two officers each.
* One administrator (`ADMIN-01`).
* Master lists `country` (Pakistan, United Kingdom) and `crop` (Cotton for PK, Hemp for GB).
* Master lists `variety` and `tenure` (scoped by crop) and `previous_crop` (scoped by country).
* The fieldbook's lists (soil, tillage, irrigation, products, harvest and so on), scoped
  to cotton in Pakistan or hemp in the UK, and `yes_no`.
* The crop clock: cotton 120 / 135 / 200 and hemp 80 / 95 / 125 days after sowing.
* Dummy sites: ginners `BWP-G1` to `BWP-G3` (Bahawalpur) and `MUX-G1` (Multan), processors
  `UK-P1` (Norfolk) and `UK-P2` (Lincolnshire).
* Delivery thresholds (variance 3 and 5 percent; moisture 12 percent cotton, 16 percent
  hemp) and heap defaults (placeholders, see Heap above).
* Pakistan's administrative hierarchy: 7 provinces and territories, all 158 districts
  (36 in Punjab), and tehsils for the cotton-belt districts of Punjab and Sindh.
  Districts without a seeded tehsil list are expected: the form always offers
  "Other (type manually)". Villages are never seeded; officers type them and the form
  suggests the ones already entered in that tehsil.

Reference data added for Module 2 is marked in the seed files themselves with a
`_meta` block reading `SEED DATA - TO BE VERIFIED`; the same applies to
`backend/module_2/data/uk_postcode_areas.json`. Verify these against official sources
before production use. The fieldbook's lists and crop-clock days follow the Module 3
specification and should be checked the same way.

Sign in on the login screen with an officer's code and password. Every seeded account
starts on the shared default password and can change it from **My profile**. In
development the **Dev** switcher in the top bar acts as any officer without signing in.

## How modules communicate

* A module imports only `core`, `shared`, its own code and other modules' `public_api.py`.
  `backend/tests/test_architecture.py` fails the build otherwise.
* Cross-module reads go through `public_api.py` functions that return plain DTOs.
* Cross-module reactions go through the in-process event bus (`core/events.py`).
* Upstream modules ask downstream ones for permission through guards (`core/guards.py`),
  for example `field.can_delete`.
* Every dropdown reads `GET /api/v1/master/{list_key}?country=&crop=`; nothing is hard-coded in React.

Details: `docs/ARCHITECTURE.md` and `docs/CONTRACTS.md`.

## Add a new module

Backend:
1. Create `backend/module_N/` with `__init__.py`, `meta.py`, `router.py`, `schemas.py`,
   `models.py`, `repository.py`, `services.py`, `public_api.py`, `events.py`, `tests/`.
2. Add one `ModuleEntry.build(...)` line in `backend/app/registry.py` (meta, router, `events.register`).
3. Add its tables to `docs/DATA_MODEL.md`, its events and public API to `docs/CONTRACTS.md`
   and new event names to `core.events.KNOWN_EVENTS`.
4. Add `module_N` to `testpaths` and isort `known-first-party` in `backend/pyproject.toml`.

Frontend:
1. Create `frontend/src/module_N/` with `index.ts` (exports `meta` and the default page),
   `module.meta.ts`, and the `pages`, `components`, `hooks`, `api`, `store`, `types`, `tests` folders.
2. Add the meta import and an entry with its loader to `src/app/moduleRegistry.ts`.
3. Add `N` to the `MODULES` list in `eslint.config.js` so isolation rules cover it.

## Testing

```bat
cd backend  && venv\Scripts\python -m pytest && venv\Scripts\ruff check .
cd frontend && npm run test && npm run lint && npm run typecheck
```

One end-to-end smoke test (register a farmer, draw a field, add a second) runs
separately, because it needs a browser and both servers:

```bat
cd frontend && npx playwright install chromium && npm run test:e2e
```

See `docs/TESTING.md` for everything that is covered.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| "Python 3.11 or newer was not found" | Install Python from python.org with "Add python.exe to PATH" ticked, then run `backend.bat` again. If `python` opens the Microsoft Store, turn off the "App execution aliases" for python in Windows Settings. |
| "Node.js was not found" or too old | Install the Node.js LTS from nodejs.org, close and reopen the window, run `frontend.bat` again. |
| "Port 8000 is already used" | The window shows the process ID and program. Close it or end it in Task Manager. If it is an older SAWIE backend, the script says so and leaves it running. |
| "Port 5173 is already used" | Close the other program (often another Vite app) and run `frontend.bat` again. |
| Backend did not become ready | Read the "SAWIE backend" window; it keeps errors on screen. |
| Broken Python environment | Delete `backend\venv` and run `backend.bat`; it rebuilds everything. |
| Frontend packages broken | Delete `frontend\node_modules` and run `frontend.bat`. If an error mentions a missing `@rollup/rollup-win32-*` package, delete `frontend\package-lock.json` too. |
| Start from an empty database | Stop the backend, delete `backend\data\sawie.db*`, start again (it reseeds). |
| A scanned code does not open on the phone | `PUBLIC_BASE_URL` still says `localhost`, or the frontend was not started with `--host`. See "Scanning codes with a phone". |
| "The selected officer does not exist" | Handled automatically: the app forgets the stale choice and uses the default officer. |

## Audit

See `docs/AUDIT_REPORT.md`, `docs/KNOWN_LIMITATIONS.md` and `docs/NEXT_STEPS.md`. Read the limitations before exposing the API: the sign-in screen checks a password, but requests still identify the officer with a header, not a session.

## Roadmap

* **Real sessions**: the sign-in screen already checks passwords, but requests still
  identify the officer with the `X-Officer-Id` header. A signed cookie or token replaces
  that header, and the Dev officer switcher with the `DEFAULT_OFFICER_CODE` fallback.
* **Supabase (Postgres)**: change `DATABASE_URL`, then create the first Alembic revision.

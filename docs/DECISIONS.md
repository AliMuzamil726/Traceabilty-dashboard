# Decisions

Nontrivial decisions taken while building the foundation (Prompt 1). Each entry says
what was decided and why. Later prompts append to this file.

## D-001 Backend packages sit side by side under `backend/`
`app`, `core`, `shared`, `scripts` and `module_1..8` are top-level packages inside
`backend/`, matching the requested tree. Uvicorn runs `app.main:app` from `backend/`,
and pytest uses `pythonpath = ["."]` from `backend/pyproject.toml`.

## D-002 Module identity lives in plain `meta.py` constants
Each `meta.py` holds `NUMBER`, `NAME`, `FOLDER`, `ROUTE_PREFIX`, `API_PREFIX`,
`STATUS`, `BUILD_ORDER`, `PURPOSE`. A shared dataclass would need a new file in `core`
outside the requested tree; constants keep modules free of extra imports and
`app/registry.py` builds a `ModuleEntry` from them. The frontend `module.meta.ts`
mirrors the same values.

## D-003 `BUILD_ORDER` drives the "In build" and "Planned" pills
Only three statuses exist (active, placeholder, deferred). The sidebar needs "In build"
for the module being built now, so the placeholder with the lowest build order shows
"In build" and the rest "Planned". Marking a module active moves the pill automatically.

## D-004 Every module exposes `GET <prefix>/meta`
Placeholder modules need a router for the registry and the documented prefixes. A
read-only meta endpoint proves the mount works and is covered by tests, without
inventing features. Settings (deferred) has no router.

## D-005 String UUID keys; deterministic UUID5 for seeded rows
UUIDs are portable to Postgres and never assumed numeric. Seeded offices, officers,
locations and master-list rows use UUID5 of their natural key, so a stored officer id
in the browser stays valid after the database is deleted and reseeded.

## D-006 SQLite transactions start with `BEGIN IMMEDIATE`
pysqlite's implicit transaction handling is disabled and every transaction takes the
write lock up front (WAL journal, 30 s busy timeout). This makes the ID counter safe
without SQLite-specific code in repositories (the counter uses a portable
`UPDATE ... RETURNING`). Cost: writes are serialised, which is fine for a local
development database. Postgres gets row locks from the same statement.

## D-007 Services commit; the session dependency never does
FastAPI has changed when yield-dependency teardown runs relative to sending the
response. Committing inside the service makes a commit failure an error response in
every FastAPI version. The dependency only rolls back and closes.

## D-008 Event handler failures roll the transaction back
"Failures logged and never swallowed silently": every handler runs, each failure is
logged with a traceback, then `EventHandlerError` is raised so the request fails and
the unit of work rolls back. Partial cross-module state is worse than a visible error.
Event names are checked against `KNOWN_EVENTS` to catch typos.

## D-009 Guard denials collect every reason
`guards.check` runs all checks so the UI can explain every blocker at once (for
example "has a fieldbook" and "has a delivery"). `enforce` raises a 409 whose code is
the first denial and whose `details.reasons` lists all of them.

## D-010 Development officer fallback: `PK-MUL-01`, not the admin
Defaulting to an ordinary officer surfaces permission problems during development.
The fallback code is configurable (`DEFAULT_OFFICER_CODE`). In production the
`X-Officer-Id` header is mandatory. An unknown id returns `officer_not_found`, and the
frontend then clears its stored choice and falls back automatically.

## D-011 Countries are ISO codes `PK` and `GB`; crop scopes the country list
Master-list rows for `crop` are scoped by country (cotton to PK, hemp to GB), so
`GET /master/crop?country=GB` returns hemp only. Rows with NULL scope are global and
always included. Uniqueness with NULL scopes is enforced in the repository.

## D-012 Locations seeded only for the seeded offices
The `locations` table (province, district, tehsil; region, county, district for the
UK) is created with the minimum rows the dummy offices reference. Full administrative
lists arrive with Module 2. No locations endpoint yet: the module that needs it will
add one.

## D-013 Health is always HTTP 200
`/api/health` reports `status: degraded` when the database is unreachable instead of
failing. frontend.bat only needs to know that the process answers; the UI can show the
degraded state.

## D-014 Tables created with `create_all`; Alembic scaffolded only
Migrations before the schema settles would be churn. Alembic is wired to the settings
and metadata (`backend/migrations/env.py`, batch mode for SQLite) so the first
revision can be the Supabase baseline.

## D-015 Tailwind palette replaced and audited
`theme.colors` replaces the defaults, so off-brand classes do not compile.
`npm run check:colors` also scans source, SVGs and the built CSS. Two aliases
(`gray.200`, `gray.400`) point at Line and Muted because Tailwind's base styles read
those names; the default ring colour is set to Forest 500.

## D-016 DatePicker and Select use native controls
Native date and select inputs give full keyboard support, screen-reader support and
the platform picker on tablets used in the field, with ISO values. They are styled to
match the system. The searchable, async-capable `Combobox` covers long lists.

## D-017 Pipeline tracker shows six stages
The brief says "seven working modules" but lists six stages; the seventh working
module is the Dashboard itself, which reads from all stages rather than being one. The
tracker shows Register Farmer to QR Tracing (stages 1 to 6) and states that the
dashboard reads from all of them.

## D-018 `ModulePlaceholder` reads the registry
To show a module's position in the pipeline the placeholder uses `PIPELINE` from
`app/moduleRegistry.ts`. This is the only shared-to-app import and disappears as
modules replace their placeholders.

## D-019 Frontend module isolation via ESLint
A module may import another module only through `@/module_N` (its `index.ts`).
`no-restricted-imports` patterns generated per module enforce it in `npm run lint`.

## D-020 OfficerSwitcher hidden below 640px
The Dev switcher is a desktop development tool; on phones the topbar keeps the page
title and avatar only. The acting officer still applies on every device.

## D-021 First-run backend install does not count against the 60 second wait
On a clean machine `pip install` can take longer than 60 seconds. backend.bat writes
`backend/.setup_in_progress` while creating the venv and installing packages;
frontend.bat pauses its 60 second countdown while that flag exists (with a 15 minute
ceiling), so the one-double-click start works on a fresh PC.

## D-022 Dependency installs keyed by file hashes
backend.bat stores the SHA-256 of `requirements.txt` in `backend/venv/.req_hash`;
frontend.bat stores the SHA-256 of `package-lock.json` in
`frontend/node_modules/.lock_hash`. Restarts skip installs unless the file changed.

## D-023 Uvicorn reload watches source folders only
`--reload-dir` lists `app`, `core`, `shared`, `scripts` and the module folders so
the watcher never scans `venv` or reacts to SQLite writes in `data`.

## D-024 Package name for Inter
The brief names `@fontsourcevariable/inter`; the published package is
`@fontsource-variable/inter`, which is what is installed.

## D-025 Display units
Storage is SI (m², kg). Cotton (Pakistan) displays acres and maunds (40 kg); hemp (UK)
displays hectares and tonnes (`src/core/utils/units.ts`).

## Prompt 2: Module 2, Register Farmer and Fields

## D-026 `services` is a package in a built module
A built module needs more than one service file (Module 2 has validators, IDs, the
geometry engine, farmers, fields, locations, postcodes and a rate limiter), so
`module_2/services.py` became `module_2/services/`. `tests/test_architecture.py` now
accepts either a `services.py` or a `services/__init__.py` for any module, so the
boundary is still enforced and unbuilt modules are unaffected.

## D-027 The SAWIE ID is a plain number starting at 1001
Prompt 1 planned `SAW-PK-000123`. A SAWIE ID belongs to a person for life, so anything
encoded in it (country, crop, office) can go stale, and officers read these numbers
aloud and write them on sacks. One counter, `sawie_id`, is shared by both programmes;
`core.ids` counts from 1, so Module 2 adds a base of 1000. Field IDs are counted per
farmer as `{sawie_id}-{nn}`, so a field ID names its farmer. Neither counter is ever
rewound, so a deleted field's number is not reissued. DATA_MODEL.md was updated.

## D-028 Personal data is permanent, crop data is per season
`farmers` holds who someone is; `farmer_season_profiles` holds what they grew this
season. A lookup returns only the personal half, so registering a returning farmer
pre-fills their details and leaves variety, tenure and previous crop blank. Without the
split, last season's values would be inherited silently and a farmer returning next
season would otherwise need a duplicate record.

## D-029 `farmers` keeps location names plus a location id
Prompt 2 lists province, district and tehsil as columns, and a tehsil may be typed by
hand where no list is seeded, so the names are stored as entered. `location_id`
(planned in DATA_MODEL.md) is kept alongside and set when a seeded location was chosen,
so later modules can group by administrative area even if a name is retyped. It is null
for a typed tehsil.

## D-030 Phones are stored twice: E.164 and local
`phone_norm` holds `+923001234567` and `phone_display` holds `0300-1234567`. The
normalised form is unambiguous across two countries and is what messaging would use;
the display form is what an officer recognises. Search matches both, because a search
for "0300" would never match the E.164 form.

## D-031 Overlap is measured in metres, in the centroid's UTM zone
A degree of longitude is about 91 km in Multan and 62 km in Lincolnshire, so a
degree-based area would be wrong by a different amount in each programme. Both the new
boundary and each candidate are projected into the UTM zone of the new polygon's
centroid before intersecting. Candidates are prefiltered on the indexed bbox columns
and tested exactly with Shapely through an STRtree.

## D-032 The overlap check runs again inside the saving transaction
The live check during drawing cannot be authoritative: another officer may save an
overlapping boundary between the last keystroke and the save. The check is repeated
immediately before the INSERT. On SQLite every transaction opens with `BEGIN IMMEDIATE`
(D-006), so two concurrent saves serialise and the second reads the first's committed
field and is rejected. A test proves exactly one of two concurrent overlapping saves
succeeds.

## D-033 `validate-geometry` always answers 200
A half-drawn or overlapping boundary is an expected state of a map, not a failed
request. The endpoint returns `valid` plus the measurements and every conflict, and the
Save button follows that answer. Errors are reserved for the save itself, which does
raise 409 `field_overlap` or a 422 for a bad shape.

## D-034 Leaflet, Geoman and markercluster CSS is vendored and re-authored
Those packages ship CSS carrying their own colours, and importing it would put
off-brand colours into the bundle and fail `npm run check:colors` (D-015). Their layout
rules are vendored into `src/design-system/map.css` with every colour replaced by a
brand token, Geoman's toolbar is hidden and the app supplies its own design-system
toolbar. The audit earned its keep here: Leaflet writes two colours as the keywords
`black` and `white`, which a hex scan misses but the minifier turns into `#000`.

## D-035 react-leaflet is pinned to v4
react-leaflet 5 requires React 19 and the stack is fixed at React 18. v4 is used for
the container and tile layers; drawing, editing and the layers are driven imperatively
through Leaflet and Geoman, which suits a map whose state lives outside React anyway.

## D-036 Officers see their own farmers; the map shows everyone's fields
The list is scoped to `registered_by` for officers and unscoped for administrators.
The map layer is deliberately not scoped: the zero-overlap rule applies across every
farmer, so an officer must be able to see the boundary they are about to clash with,
whoever registered it. Lookup is likewise unscoped, or a returning farmer would be
registered twice by a different officer.

## D-037 The ID number lookup is rate limited
Lookup answers whether an ID number is registered, so it must not be usable to test
numbers in bulk. A fixed window of 60 requests per minute per officer and client
address is generous for typing a CNIC and useless for enumeration. It is in-process,
which suits one worker; a shared store is needed when the API is scaled out.

## D-038 Pakistani locations are seeded, villages are not
All 7 provinces and territories and all 158 districts are seeded, with tehsils for the
cotton-belt districts of Punjab and Sindh. Villages are not: there are tens of
thousands and any list goes stale, so the officer types the village and the suggestion
endpoint offers what other officers already typed in that tehsil, which makes spellings
converge without freezing them. Every district offers "Other (type manually)" for the
tehsil. The seed files carry a `_meta` block marking them as data still to be verified.

## D-039 The UK postcode-area fallback is a data file, not a table
About 120 postcode areas mapped to a county and region live in
`backend/module_2/data/uk_postcode_areas.json`. It is reference data owned by the
module and read at startup, not something an officer edits, so a table and a migration
would buy nothing. Resolved postcodes are cached in `uk_postcode_cache`; county and
region become editable only when the API and the table both fail.

## D-040 The frontend form is one flat value shape, not one per crop
A schema per crop would force react-hook-form to swap its value shape when the crop
changes, losing the fields the two programmes share. Instead the values are a flat
superset and `superRefine` applies only the chosen crop's rules, so each error still
lands on its own field. `postcode_manual` is part of the values because county and
region are required only when the postcode could not be resolved.

## D-041 The end-to-end smoke test is Playwright, run on demand
`npm run test` stays fast and dependency-free; `npm run test:e2e` starts both servers
and drives a real browser. It writes to `backend/data/e2e.db`, so it never touches the
development database, and each run places the officer at a fresh map location, so it
does not depend on an empty database and can be repeated. `SAWIE_PYTHON` and
`SAWIE_CHROMIUM` let it use an existing interpreter or browser on CI images.

## D-042 One fieldbook per field per season
The prompt allowed a book per farmer or per field. Per field was chosen: inputs, sowing
dates and pickings differ between a farmer's fields, Harvest Radar needs readiness per
field, and a guard on a field (reshape, delete) must ask about that field alone. The
unique key is `(field_id, season_year)`; opening an existing pair returns that book.

## D-043 Fieldbooks hold Module 2's field and farmer ids without foreign keys
Module 3 may not reach into Module 2's tables, so `field_id` and `farmer_id` are plain
UUID strings checked through `module_2.public_api`. The readable `field_code` is copied
at creation so lists and events read well without a call per row. A field removed in
Module 2 soft-removes its drafts through the `field.deleted` event (D-053).

## D-044 Forms are JSON definitions shared by the screen and the server
`module_3/form_definitions/{crop}.json` lists every step, field, type, unit, range,
master list, condition, computed value and rule. `GET /schemas/{crop}` serves the file
unchanged; React renders from it and the backend validates with it, so the two cannot
drift and adding a question is a data change. Each book stores the `schema_version` it
was created with. The loader rejects malformed definitions at startup. Fertiliser
analyses (the "typical value" hints) live in the definition's `suggestions`, because
`master_lists` has no column for extra numbers per value. Hemp nutrient rates needed a
unit list, so `nutrient_rate_unit` (kg per ha, t per ha) was added to the seed.

## D-045 Guards receive the caller's session
A guard check that opened its own SQLite connection waited on the caller's write lock
(`BEGIN IMMEDIATE`) and deadlocked. Module 2 now passes `session=self.session` to
`guards.enforce`, and Module 3's checks read through it, inside the same transaction.

## D-046 Concurrent edits use an optional version token
Each write bumps `fieldbooks.version`. A client that sends `X-Fieldbook-Version` gets
`409 fieldbook_stale` when another save landed first, and the screen reloads the book
and says so. The header is optional so scripts and tests can write without it; the web
app always sends it. Order of checks on every write: access, lock, version, crop.

## D-047 FarmerDTO carries the Home Office licence number
The hemp field-information step shows the licence read only. Module 2's public DTO
gained `home_office_licence_no` (null for cotton) rather than Module 3 reading
Module 2's tables.

## D-048 Module 3 owns `crop_clock_config`
The editor shows crop status as soon as sowing is recorded, so the clock belongs to the
module that computes it; Harvest Radar reads it through `get_crop_clock`. The planned
per-stage, per-variety table was reduced to one row per crop with three day counts
(approach, ready, window end), which is all the prompt defines.

## D-049 Reference seed runs on every start; modules seed their own rows
`SEED_ON_START` now means "insert any missing reference rows" on every start, not only
into an empty database, so a new master list reaches an existing developer database
without a reset. Inserts are idempotent. `app.registry.run_module_seeds` then calls each
module's optional `seed.run(session)` (Module 3 seeds the crop clock).

## D-050 What counts as a complete step
A single step is complete once saved; a repeatable step once it has one entry. A step
whose definition sets `allow_not_applicable` must still be answered before submit:
either entries, or "Nothing to record for this step". Required steps cannot be marked.
Warnings never block submit; errors (including cross-step ones that a later change
created, such as a picking now dated before sowing) do.

## D-051 Crop status rules
Days after sowing below `approach_day` is Growing, below `ready_day` Approaching, up to
and including `window_end_day` Ready, and beyond it still Ready with `overdue` set, so
an unharvested late crop stays on the radar. Harvested means a harvest entry exists.

## D-052 Officer scoping in the selectors
An officer's officer list holds only themself and their farmer list only the farmers
they registered; asking for another officer's farmers is a 403. An administrator may
choose any officer. Every book endpoint applies the same farmer-access check.

## D-053 Removing a field soft-removes its drafts
Module 3 subscribes to `field.deleted` and sets `deleted_at` on that field's drafts. A
submitted book never reaches this point, because the `field.can_delete` guard refuses
the delete first.

## D-054 The activity timeline is derived, not stored
Entries already carry their time and officer, and the audit log carries the rest, so
the timeline is built from entries, not-applicable marks, creation and submission
rather than a second table that could disagree with them.

## D-055 Entry indexes are stable
Deleting an entry does not renumber the others, so an index named in an event, a
warning or another officer's open form keeps pointing at the same entry.

## D-056 Photos are stored by relative path and served through the API
Paths are relative to `UPLOAD_DIR`, so the folder can move. The image route goes
through the officer dependency, and the screen fetches thumbnails with the officer
header instead of a bare image URL, so real authentication can be added later without
changing the screen. Content is verified with Pillow, never trusted from the extension.

## D-057 Combobox gained a `renderMeta` slot
The farmer picker shows crop and fieldbook-status pills in each row. A small optional
slot on the design-system Combobox does that without a second combobox.

## D-058 Radar owns pickup requests; the events are `pickup.requested` and `pickup.cancelled`
Module 5 is built after Module 4, so the request to collect a crop belongs to Radar.
Module 5 will take open requests through `module_4.public_api` and report back with
`mark_pickup_scheduled`, `mark_pickup_fulfilled` and `mark_pickup_cancelled`, which work
inside its own transaction. The placeholder event `delivery.requested` was removed from
`core.events`; Module 5 keeps its own delivery events.

## D-059 Bulk reads from Modules 2 and 3, so the radar never calls per field
`module_2.public_api.list_field_sources` returns every active field with the farmer
details a listing needs (no ID number or phone) in one query.
`module_3.public_api.get_crop_status_bulk` returns the fieldbook facts for many
(field, season) pairs in one query for books, one for entries and one for clocks, in
chunks of 500 ids. A radar read therefore costs the same few queries for 10 fields or
1000; tests assert it.

## D-060 Readiness rules and their precedence
The rules live once, in `module_4/services/readiness.py`. A fieldbook entry marked
Ready for pickup = Yes puts the field in Ready even after a picking, because that flag
is what logistics acts on; a picking or baling without it puts the field in Harvested.
Overdue is a flag (not harvested, past the window end), so an overdue field stays in
Ready. Hemp counts as harvested once the cutting step or a baling entry exists. The day
counts come from Module 3's crop clock, never from Radar.

## D-061 Estimated quantity falls back to a benchmark
When a fieldbook has no yield yet, Radar uses 800 kg of seed cotton per acre or 6 t of
hemp straw per hectare (`module_4/services/config.py`) and marks the figure as an
estimate everywhere it is shown and on the pickup request (`quantity_is_estimate`).

## D-062 Radar views are cached for 30 seconds and computed in memory
Readiness is not stored, so sorting and paging happen after computing the rows. The
rows per crop and season, and each filtered view, are cached for 30 seconds keyed by
database, date, officer and every filter. Fieldbook, field and pickup events clear the
cache at once and again after the publisher commits, so a read between the event and
the commit cannot keep stale data. The cache is per process, which is enough while
entries live seconds.

## D-063 Officer scope on the radar
Officers see the farmers they registered; the All farmers switch shows everyone's
fields read only (`can_act` false, no request or cancel). Administrators always see
and act on everything. Requesting and cancelling check the same rule on the server.

## D-064 Filter options come from the data, not the location tables
The district, tehsil and village (or county and region) choices are the values present
on the radar's own fields, nested for cascading, and returned with the rows. They are
never empty choices, need no extra endpoint, and stay correct for typed tehsils.
Status and pickup-state options are the API's own states rather than reference data,
so they are not master lists.

## D-065 One open request per field and season, enforced twice
The service checks for an open request inside its `BEGIN IMMEDIATE` transaction, and a
partial unique index on `(field_id, season_year)` where the status is requested or
scheduled refuses any second row. Each insert runs in a savepoint, so a clash skips that
field with `pickup_already_open` instead of failing the whole bulk request.

## D-066 Shared map configuration is exported from Module 2's entry
Radar imports the satellite, street and label layers and the region centres from
`@/module_2` (its `index.ts`), never from Module 2's folders. The popup button style
lives in `design-system/map.css` beside the other Leaflet rules.

## D-067 Recharts for the demand chart
Recharts 2.13.3 (React 18 compatible) draws the 8-week demand bars, coloured with brand
tokens only.

## D-068 Sites are a shared table
Deliveries, Heap and QR Tracing all refer to the ginner or processor, so `sites` lives in
`backend/shared` with its own read-only router (`GET /api/v1/sites`). The seed adds six
dummy sites flagged `is_dummy`. Screens say Ginner and Heap for cotton, Processor and
Batch for hemp.

## D-069 The delivery status machine is a table in the model
`TRANSITIONS` in `module_5/models.py` lists the only moves; the service refuses anything
else with 409 `invalid_transition` (the prompt's INVALID_TRANSITION, in the lower-case
style of every other code). Every move writes the delivery, a history row, an audit entry
and an event in one transaction. `delivered` is terminal; an administrator correction
writes a `delivered` to `delivered` history row with the reason.

## D-070 Cancelling a delivery cancels its Radar request
The prompt allowed releasing the request back to `requested` or cancelling it. Cancelling
it (`mark_pickup_cancelled`, reason naming the delivery) was chosen: it needs no new
Module 4 function, the field shows as ready with no request on the radar, and the
officer can request again from there. The reverse also holds: when a request is
cancelled elsewhere, Module 5 cancels the delivery still moving for it.

## D-071 Variance compares with the field weight, else the estimate
The weighbridge weight is compared with the field weight when the driver recorded one at
dispatch, otherwise with the estimate from the pickup request. Percentages are rounded
half up to 0.01 before the level is decided, so 2.99 is ok, 3.00 warn, 4.99 warn and 5.00
flag at the default thresholds; both signs count. A flag needs a note. With no reference
there is no variance. The Receive dialog previews the same arithmetic
(`module_5/lib/variance.ts`); the server recomputes and decides.

## D-072 Officers read every delivery, act only on their own
As on the radar, the list defaults to the officer's farmers and an All farmers switch
shows the rest read only (`can_act` false). A delivery's detail can be opened by any
officer; scheduling, transitions and edits check that the officer registered the farmer.
Administrators act on all.

## D-073 A delivery's heap is stored on the delivery
The prompt names `deliveries.heap_id` and says each delivery belongs to at most one heap,
so no `heap_deliveries` table was built. Module 5 owns the column and changes it only
through `assign_heap` and `unassign_heap` in its public API, which Module 6 calls. It holds
the heap's business ID (`BWP-G1-H01`), readable on the delivery without asking Module 6.
`assign_heap` takes the heap's site and crop as arguments so Module 5 can check them
without importing Module 6.

## D-074 Heap totals are computed on read, in Decimal
Nothing derived is stored: input, expected output, bale maximum, remaining and
contributions come from `heap_calc.py` each time from the deliveries' weighbridge
weights and the active bales. That is how "recompute any dependent heap" after an
administrator correction works: the next read shows it. The guard `delivery.can_correct`
refuses corrections for deliveries in a closed heap. A bale maximum and can-close are
decided on unrounded values, so rounding cannot allow an extra bale.

## D-075 Bales are created under the heap's write lock
`create_bales` reads the heap with `FOR UPDATE` inside a transaction that SQLite starts
with `BEGIN IMMEDIATE`, then recounts the bales before checking the maximum, so
concurrent requests are serialised and can never exceed `max_bales` (tested with eight
threads). Serials are `{heap_id}-001` onwards, unique, and never reused after a void.

## D-076 Heap roles in one place
Officers open heaps, add and remove deliveries, record bales and close a heap with no
remainder. Only administrators void bales and close with a remainder, because both change
what the record says was produced. The checks live in `module_6/services/permissions.py`
and the detail response carries `permissions` so the screen shows only what is allowed.

## D-077 Heap and batch defaults are placeholders
Outturn 34 percent and 170 kg bales for cotton; 25 percent, 250 kg, 55 percent shiv and
15 percent dust for hemp. They are seeded into `heap_config`, marked as placeholders to
confirm with the business, copied into each heap at opening, editable until the first
bale, and frozen after it.

## D-078 Pending deliveries come with the heap detail
The Receive deliveries drawer needs the delivered, unassigned deliveries at the heap's
site. Rather than add an endpoint beyond the prompt's list, `GET /heaps/{key}` returns them
as `pending_deliveries` while the heap is open (from `list_delivered_unassigned`).

## D-079 Module 6 exports HeapPicker and useAssignToHeap
The prompt allows Module 5's Receive dialog and detail panel to show an Assign to heap
control using a HeapPicker exported from `module_6/index.ts`. Picking a heap is not enough
on its own, so the same index also exports `useAssignToHeap`, which posts to Module 6's
own endpoint. Module 5 imports nothing else from Module 6.

## D-080 bale.voided is a new event
The prompt lists `bale.voided` among Module 6's events; it was added to
`core.events.KNOWN_EVENTS` and the events test.

## D-081 Codes are random, short and not stored as URLs
A code is 12 characters of base32 (`A-Z`, `2-7`) from `secrets.choice`: about 60 bits,
short enough to type, never derived from a serial, and readable without 0/O or 1/I
confusion. The trace link `{PUBLIC_BASE_URL}/trace/{code}` is built when needed and never
stored, so fixing the base URL repairs every label already printed.

## D-082 Heaps and bales are referenced by business ID
`qr_tokens` keeps `heap_id` and `bale_serial`, the identifiers the Heap events carry, and
no foreign key into Module 6's tables. Module 7 reads heaps and bales only through
`module_6.public_api`.

## D-083 Heap codes stay active after the heap closes
A closed heap is still a real lot that buyers may scan, so `heap.closed` only clears the
public cache. Codes are revoked only by an administrator, by a regenerate, or when a bale
is voided.

## D-084 Regenerate needs an active bale
A voided bale has no product to label. Regenerating revokes the old code first, with the
reason, and issues a new one in the same transaction.

## D-085 One generic rate limiter in core
`core/ratelimit.py` holds an in-memory sliding-window `RateLimiter`. The public page allows
30 lookups a minute per hashed address. It is per process, which is enough for one worker;
a shared store is listed under deferred work.

## D-086 QR_IP_SALT setting
Scan logs keep SHA-256 of a secret salt plus the address, so repeat scans can be counted
without storing who scanned. The salt is a new setting with a development default that
must be changed in production.

## D-087 The scan is logged after the response, in its own session
Logging must never slow down or break the public page. The route ends its read transaction
before scheduling the log as a background task: FastAPI runs background tasks before the
request's session closes, and with `BEGIN IMMEDIATE` an open read still holds SQLite's
write lock, so the log would otherwise wait 30 seconds and fail. Failures in the log are
swallowed and written to the server log.

## D-088 Find a code logs internal scans
`/resolve` records an `internal` scan when the input matches a code, so the scan counts
show both how often staff and the public look a code up.

## D-089 The public cache key includes the database
Public pages are cached for 60 seconds by (database URL, code). Revoke, regenerate and
heap close clear the cache, so a withdrawn code stops working at once.

## D-090 What the four checks mean
Fieldbooks submitted: every contributing field has a submitted fieldbook for the delivery's
season. Deliveries weighed: every delivery in the heap is delivered with a weighbridge
weight. Heap closed: the heap's status. Mass balance: active bale weight does not exceed
expected output. A check with nothing to check (no fieldbooks, no deliveries) fails.

## D-091 Timeline dates
"Farmers registered" and "Fields mapped" use the farmer and field creation dates, added to
Module 2's `FieldSourceDTO` as `farmer_registered_at` and `field_mapped_at`. "Harvest" uses
the fieldbook's ready-for-pickup dates; the public "Harvest window" uses the delivery dates,
which every lot has.

## D-092 Two extra endpoints and base URL in responses
The screen needs a ZIP of PNGs and a single-label PNG, so `POST /images.zip` and
`GET /bales/{serial}/label.png` were added. `/lots` and the overview return `base_url` and
`base_url_is_local` so the screen can warn without another request.

## D-093 QR images and labels
QRs use error correction M with the standard 4-module quiet zone, drawn in the ink colour
`#15221B` on white. Labels are A4 sheets of 3 by 8 (configurable in
`module_7/services/labels.py`) with QR, serial in a monospace face, heap ID, site name,
production date and "Scan to trace". At most 480 labels per request.

## D-094 The public page is a separate lazy route
`/trace/:token` is registered before the app shell in `app/router.tsx` and loaded through
`@/module_7` (`loadPublicTracePage`), so scanners download only that page. For phone tests
the dev server must listen on the network (`npm run dev -- --host`); `vite.config.ts`
keeps `localhost` so `frontend.bat` behaves as before.

## D-095 Camera scanning uses BarcodeDetector only
No scanning library was added. Where the browser has no `BarcodeDetector` (Firefox, older
Safari) or the camera is refused, the dialog says so and suggests typing the code or using
the phone's camera app, which opens the link directly.

## Intentionally deferred
* Login and real authentication (replaces `get_current_officer` and OfficerSwitcher).
* Editing a farmer's crop programme (one farmer belongs to one programme in this phase).
* A shared-store rate limiter, needed once the API runs with more than one worker.
* Settings page (Module 8): sidebar item is disabled with "Coming later".
* Supabase/Postgres connection and the first Alembic revision.
* Global search (topbar field is visible and labelled "Soon").
* Dashboard KPIs and charts (Prompt 8); the KPI row shows skeletons until then.
* Fieldbook PDF export and fieldbook analytics (not part of Module 3).
* Reopening a submitted fieldbook. Submission is permanent by design.
* Signing the public page or adding a buyer-facing certificate download.
* Editing site, delivery and heap thresholds in Settings (Module 8); the seeded values are used until then.

## D-096 The Dashboard adds aggregate functions to the modules that own the data
Module 1 owns no tables and may read others only through `public_api.py`. Where a count
or sum did not exist yet, it was added to the owning module's public API as a small
documented function computed in SQL (for example `module_2.get_registration_totals`,
`module_5.get_delivery_totals`, `module_6.list_heap_activity`, `module_7.get_scan_totals`),
each listed in CONTRACTS. The dashboard never loads a table to add it up, and every
figure is the owner's own definition.

## D-097 Time series are bucketed in Python, not in SQL
Truncating a timestamp to a day, week or month is written differently on SQLite and
Postgres. The owning module returns the timestamps inside the requested range (bounded
by the range and capped at 400 buckets) and Module 1 groups them. Weeks start on Monday,
in UTC.

## D-098 Hemp licence expiry is read from the fieldbook
The expiry date is only recorded on the hemp fieldbook's first step (`field_info.licence_expiry`),
so the licence alert reads it through `module_3.list_licence_expiries`. A field with no
fieldbook yet cannot be checked and is not counted. The alert is critical as soon as one
licence has actually expired, otherwise attention.

## D-099 A heap's last activity
`last_activity_at` is the latest of its opening, the last delivery assigned to it and the
last bale made. The idle-heap alert ages that value; closed heaps are never idle.

## D-100 Ranges are whole UTC days
`7d` and `30d` count today; `season` is 1 January to 31 December of the season year, ending
today while the season is current; `custom` needs `from` and `to` (at most two years).
A date becomes the first and last instant of that day in UTC. The range narrows only
flows inside it (registrations, mapping, deliveries weighed in, bales made, scans in the
range); running totals (farmers, fields, readiness) describe the season.

## D-101 Heaps are not scoped to an officer
A heap mixes many farmers' crop, so heap figures, the heap utilisation chart and the
idle-heap alert always describe the crop programme, whatever the scope.

## D-102 Single-crop sections with every crop selected
The fieldbook funnel and the top regions describe one crop (the steps and the kind of
region differ). With "All crops" the crop with the most mapped fields is used and named
in the response (`focus_crop`), and the chart title says which.

## D-103 Overdue on the radar is "ready, expected ready on or before the cutoff"
Harvest Radar has no overdue filter. Overdue means days after sowing past the window end,
which is exactly `status=ready` with an expected ready date on or before
`today - (window_end - ready_day + 1)`. The overdue alert links with those filters, and a
test checks the link selects the same fields the alert counts.

## D-104 Activity links
An audit entry links to its record when the log carries a usable id (farmer, fieldbook,
delivery); otherwise to the owning module's screen. Resolving a field to its farmer would
cost a query per line.

## D-105 The performance seed writes through table metadata
`scripts/seed_perf.py` must not import modules (architecture rule), so it inserts with
SQLAlchemy Core into `Base.metadata` tables after the composition root has loaded the
models. It runs no business rule, audit or event: it is a measuring tool. Pickup requests
are unique per field and season, so deliveries beyond one per eligible field fall into
earlier seasons.

## D-106 Harvest Radar can build its dataset without geometry
`RadarService.rows_for(..., include_geometry=False)` leaves polygons out and is cached
separately. Every Module 4 view still uses the full set; the dashboard uses the light one
for counting and the full one only for its map.

## D-107 Dashboard links open filtered lists
The Deliveries list and the farmer list now take their initial filters from the address
(`crop`, `status`, `date_from`, `date_to`, `scope`; `crop`, `q`), so a dashboard link lands
on the filtered view. With no parameters they behave exactly as before.

## D-108 Small lint fix outside Module 1
`module_7/services/scans.py` catches every exception on purpose (logging a scan must
never fail a response); ruff 0.12 flags it, so it now carries `noqa: BLE001` with the
reason.

## D-109 The Cotton/Hemp pair stays a literal in the filters
The two programmes are code paths with different forms, rules and countries, not master
data an administrator adds to. A third crop means new code in every module, so a
configurable list would promise something the system cannot do. Audit finding F-07.

## D-110 An officer changes only the farmers they registered
Any write to a farmer or a field (edit, add, reshape, delete a field) requires the acting
officer to be the registering officer or an administrator (`module_2/services/permissions.py`).
Reading stays wider, with other officers' details masked. Re-registering an existing ID
number is the specified flow and never hands the farmer to the new officer. This was
ambiguous in the specification and the safe reading was chosen. Audit finding F-11.

## D-111 Digits in any script are folded to ASCII before ID checks
Arabic-Indic and Devanagari digits satisfy Python's `\d`, so a national ID typed on a
phone keyboard in another script passed validation and then failed to match the stored
form. Input is folded with `unicodedata.decimal` first, and the pattern checks `[0-9]`.
Audit finding F-10.

## D-112 Every CSV export goes through one safe writer
`core/csvsafe.py` prefixes a cell that starts with `=`, `+`, `-`, `@`, tab or carriage
return with an apostrophe, except plain numbers, so a village named `=HYPERLINK(...)`
cannot run in a spreadsheet. Audit finding F-09.

## D-113 Node 22.12 is the minimum
Node 18 and 20 are end of life and Vite 8 needs 22.12 or newer. `package.json` engines,
`frontend.bat` and the README all say so. Audit finding F-02.

## D-114 Module 6 reads and exports require an identified officer
The heap list, configuration, contributors and CSV routes were missing the identity
dependency every other module has. They now require it, and a test walks every route
and fails if a non-public one does not. Audit finding F-12.

## D-115 Visual refinement of the dashboard and shared layer
Audit of screenshots at 1440 and 390 px found: pages of Modules 3 to 7 had no page frame
(content flush to the sidebar and clipped on the right); the key figures repeated the
pipeline; seven separate pipeline cards with a gradient thread; conversion shares above
100 percent; the page title shown twice; uneven tile heights; cramped, wrapping table
cells; large radii. Changes: router frames those modules, pipeline becomes one divided
strip, key figures keep only non-duplicated quantities, top bar title hidden beside its
own breadcrumb, `StatCard` aligns from the top, radii 8 and 10 px, nowrap for mono,
numeric and date cells, chart axis labels angled. No colour, route, API or behaviour
changed; the colour audit still passes.

## D-116 `app_settings` lives in shared, but only Settings writes it
`core.app_settings.get_setting` is read by Modules 2, 3, 5, 6 and 7, so the table it
reads cannot live inside Module 8 without every module importing Module 8. The table is
therefore in `shared/models/`, while the only writer is Module 8's values service. The
same reasoning puts the resolved-value cache in `core` and the declarations in
`module_8/registry.py`, handed over at startup the way event handlers are.

## D-117 Settings calls the owning module, never its table
Crop clock days belong to Module 3's rules, delivery tolerances to Module 5's, heap
ratios to Module 6's. Each owner exposes `get_config`, `update_config` and, where a
change is worth seeing first, `preview_config_change` on its `public_api`; Settings
calls those and commits. So the validation that protects a module's own data stays in
that module, and the architecture test's rule (only `public_api` crosses a module
boundary) holds for configuration as it does for everything else. Alert thresholds have
no table, so they are generic settings in the registry and Module 1 exposes only the
read side.

## D-118 One public configuration endpoint for every map
Each map used to carry its own Esri URLs and attribution. `GET /api/v1/settings/public`
now serves the tile layer, the overlay, the default centres and the QR base URL, and
`useAppConfig` (exported from Module 8) feeds `useTileLayers` in Module 2, which the
register, Harvest Radar, the dashboard and the public trace page all use. Changing the
provider in Settings changes every map at once, and a licence's credit line cannot be
right on one screen and wrong on another. The endpoint is public because the trace page
is served to people who are not signed in; only definitions marked `public` and not
`sensitive` are included, and a test asserts it.

## D-119 Deactivating hides, deleting removes, keys never change
A list value, office or site that is deactivated disappears from new forms and stays on
every record and draft that already names it. Deleting is offered only while usage is
zero, counted through `core.usage`, where each module registers a counter for the
references it holds. A value key and a site code are immutable once anything uses them;
labels and names stay editable, which is safe because records store the key.

## D-120 A restore is guarded, and maintenance mode always clears
Restoring a backup takes a safety copy first, checks the candidate file with
`PRAGMA integrity_check` before putting it in place, turns on a process-wide
maintenance flag so writes answer 503 while the file is swapped, and clears that flag in
a `finally`. A failure therefore cannot leave the product read-only. The confirmation is
a typed phrase rather than a second button, because the action destroys work. On a
database that is not SQLite the screen explains that backups belong to the host and
gives the commands instead of offering buttons that would not work.

## D-121 Officers carry no credentials yet
Module 8 manages officers without a password, token or session field anywhere, and a
test walks every route to prove no request body has one. Identity is still the
`X-Officer-Id` header (KNOWN_LIMITATIONS). When Login is built it adds credentials to
the officer record and replaces the header; nothing else in Settings has to move,
because every role check already goes through `core.permissions`.

## D-122 Staff role and placeholder sign-in

A third role, `staff`, sits between field officer and administrator. Staff work on every
officer's farmers, fields, fieldbooks and downstream records exactly like an
administrator (`CurrentOfficer.sees_all`), but cannot open Settings, the audit log or
backups (`is_admin` stays administrator only). The web app now opens on a sign-in screen
where a role and a person are picked (no password check yet). Field officers see only
Register Farmer and Fieldbook; staff see every module except Settings; administrators
see everything plus their own profile. This is a navigation rule on top of the server's
rules, not a security boundary: the `X-Officer-Id` header is still trusted until real
login is built.

## D-123 Passwords, profiles and a field officer's own home screen

Sign-in asks for a password, stored as a PBKDF2-SHA256 hash on the officer row
(`core/passwords.py`). Every seeded account starts on `12345678` and changes it on its
own profile screen; an account created in Settings starts there too. This is a sign-in
screen, not a session: requests still carry `X-Officer-Id`, so the honest description
stays in `docs/KNOWN_LIMITATIONS.md`.

A profile screen belongs to every role, and the rules are the server's, not the
screen's: anyone changes their own email, mobile and password; only an administrator
changes a name (their own or, in Settings, anyone's); a photo belongs to administrators
and staff, who appear across the product, and is refused for a field officer.

A field officer sees a different product from an office: two modules, on a phone, in a
field. So the home screen at `/` is theirs (`module_1/pages/OfficerHomePage.tsx`) and
the frame is a bottom tab bar rather than a sidebar. The modules, their numbers and
their routes are unchanged; only the frame and the home screen differ by role.

Printed QR codes default to this computer's address on the local network rather than
`localhost`, so a phone can open a label without anyone editing `.env` first
(`core/network.py`). A configured value, in Settings or `.env`, still wins (D-119).

`core/schema_upgrade.py` now runs at startup. It was written for exactly this case (a
column added after a database was created) but had never been wired in; its inspection
also had to move outside the transaction, because on SQLite an inspector reading from a
second connection while an `ALTER` holds the write lock waits on itself.

## D-124 Gate Reception settles the delivery through Module 5, in one transaction
The gate screen (Module 9) has to decide what happens to a delivery it does not own.
Duplicating the receive rules there would let the two screens drift on variance, audit
and events, and publishing an event after committing the entry would leave a window
where the gate says accepted and the delivery is not. Module 5 therefore exposes
`receive_at_gate` and `cancel_at_gate` on its public API: they apply its own rules but
only `flush`, and Module 9 sets its entry and commits. Both screens then feed the same
state machine, and a delivery has one history, one audit trail and one set of events
whatever the officer used. The reverse direction is an event: when a load is received or
cancelled in Deliveries, Module 9's handler closes a still-pending entry, so a load at
the gate never leaves two open records. Accepting at the gate marks the entry first and
then calls `receive_at_gate`, so the `delivery.delivered` handler that follows finds
nothing pending and cannot react to its own change.

## D-125 A delivery closes its pickup request, and a correction reaches the gate
Receiving a load in Deliveries only moved the delivery; the Radar request it came from
stayed `scheduled`, so the field could never be requested again and the radar kept
showing a pickup in progress. Receipt now calls `mark_pickup_fulfilled` in the same
transaction, which is also what the gate path gets for free, because accepting there
goes through `receive_at_gate`.

An administrator's correction after delivery (`POST /{id}/correct`) changed the weight
of a load the gate had already accepted, leaving two different figures for one delivery.
Module 5 now publishes `delivery.corrected`, and Module 9 copies the corrected weight and
moisture onto the accepted entry and appends a note naming the reason; the gate audit
records the change, so the gate record and Deliveries agree again. The entries list also
accepts `status=decided` (accepted or rejected), because the history panel has no useful
answer for "every decided entry" otherwise.

## D-126 Production refuses the demo seed and a placeholder salt, and contracts check payloads
`SEED_ON_START` defaulted to true, so a production boot created the demo offices and
officers, every one of them on the shared default password; the default `QR_IP_SALT` was
the development placeholder, so visitor hashes were reversible from the source. Both
defaults are now false/placeholder for development only, and `Settings.check_production`
refuses to build a production configuration with `SEED_ON_START` on or a salt that is a
known placeholder or shorter than 16 characters. It runs in the model validator, so a
`model_copy` that flips `app_env` is caught, and again in the lifespan because `model_copy`
skips validators. Tests that need production behaviour now pass an explicit salt and seed
the data they assert on instead of relying on the boot seed.

`test_contracts.py` also compared only event and route names, so a payload key could be
added, renamed or dropped without a failure, and Module 8 was excluded from the scan. The
test now parses every `bus.publish` call in Modules 1 to 9, resolves helper-built payload
dictionaries, and asserts the documented keys are present at each publish site. Turning it
on found five real drifts, all fixed: `delivery.*` payloads lacked `scheduled_date`, Module
8's `config.changed` for the crop clock did not name `crops`, and the serialization events
and `/me/preferences` route were documented one way and published another.

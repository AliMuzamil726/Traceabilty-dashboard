# Testing

## Backend

From `backend/` with the virtual environment active (`backend.bat` creates it):

```bat
cd backend
venv\Scripts\activate
python -m pytest            :: all tests
python -m pytest tests\test_ids.py -q
ruff check .                :: lint
ruff format --check .       :: formatting
```

Every test gets its own temporary SQLite file (see `backend/conftest.py`), so tests
never touch `backend/data/sawie.db`.

| File | Covers |
| --- | --- |
| `tests/test_health.py` | health payload, degraded state, request id header, `/docs`, every module prefix mounted, CORS for port 5173 |
| `tests/test_errors.py` | error envelope for 404, 405, 409, 422 (per-field details) and 500 (no internals leaked) |
| `tests/test_ids.py` | counters start at 1, formatting, rollback does not consume numbers, 12 threads x 25 allocations never duplicate (new and existing keys) |
| `tests/test_events.py` | event list matches CONTRACTS.md, ordered delivery, idempotent subscribe, failure logged then raised, capture hook, unknown names rejected |
| `tests/test_guards.py` | empty registry allows, all denials collected, 409 with reasons, independent guard names |
| `tests/test_officers.py` | dev fallback officer, header selection, admin role, unknown officer, production requires header, `require_admin`, pagination and filters, offices |
| `tests/test_master.py` | list keys, country and crop filters, global rows, unknown list, bad parameters |
| `tests/test_seed.py` | seed counts, running twice inserts nothing, only missing rows restored, edits preserved |
| `tests/test_audit.py` | diff computation, audit entry written |
| `tests/test_architecture.py` | import rules across modules, required module files, the checker itself catches violations |
| `module_N/tests/test_meta.py` | module identity, declared events, `/meta` endpoint |

### Module 2 (Register Farmer)

| File | Covers |
| --- | --- |
| `module_2/tests/test_validators.py` | CNIC in every written form, hemp ID length and grouping, Pakistani and UK phone normalisation to E.164, UK postcode spacing, names in Latin and non-Latin scripts, licence numbers, ID and phone masking, text sanitising |
| `module_2/tests/test_geometry.py` | self-intersection, unclosed ring, too few corners, holes, malformed and out-of-range coordinates, the 500 corner limit, country boxes both ways, area in the centroid's UTM zone, the minimum and maximum area, pin placement and distance, and every overlap case: identical, one percent, fully contained, edge-touching allowed, edit-self allowed, several conflicts reported at once |
| `module_2/tests/test_farmers_api.py` | SAWIE IDs from 1001, one ID number never getting two, lookup returning personal data only, crop mismatch blocked, the notice when another officer registered the farmer, lookup rate limiting, both crop forms, master-list validation, office country matching, officer scoping, masking in lists and on the profile, search, update, season profiles, completeness |
| `module_2/tests/test_fields_api.py` | field ID sequence per farmer, numbers not reused after a delete, pins, geometry rejections at save, overlap rejected at save (including between farmers), touching edges accepted, reshape and re-pin, guards blocking delete and reshape, soft delete, the map layer with clustering, bbox and crop filters |
| `module_2/tests/test_concurrency.py` | 50 threads allocating SAWIE IDs with no duplicates and no gaps, a rolled-back registration not consuming a number, 20 concurrent field saves, and two concurrent overlapping saves where exactly one succeeds |
| `module_2/tests/test_locations_api.py` | 7 provinces, 36 Punjab districts, districts scoped to their province, tehsils for cotton-belt districts, manual entry offered everywhere, village suggestions |
| `module_2/tests/test_postcode.py` | the bundled area table, postcodes.io preferred and cached, every kind of API failure falling back, unresolved postcodes opening manual entry, and manual county and region accepted only then |
| `module_2/tests/test_events_audit.py` | every documented event and payload, no event when nothing changed, audit entries for farmer, season profile and field creates, updates and deletes, and `created_by` on every write |
| `module_2/tests/test_public_api.py` | frozen DTOs, the sensitive-data gate for each kind of caller, officer scoping, lookups by key or business ID, soft-deleted fields disappearing, and that no ORM row escapes |

### Module 3 (Fieldbook)

| File | Covers |
| --- | --- |
| `module_3/tests/test_schemas.py` | both definitions load with their 11 and 9 steps in order; every field has what the renderer needs; every list, condition value, warning value and suggestion names a real master-list value; the schema endpoint serves the file unchanged; the loader rejects malformed definitions |
| `module_3/tests/test_validation.py` | every field type (text, number, integer, date, dates, select, multiselect, yes/no, paired numbers), required and range checks, `in` and `not_in` conditions dropping hidden answers, computed fields recalculated by the server, read-only defaults, every rule kind at error and warning level, and cross-step rules against sowing |
| `module_3/tests/test_books_api.py` | open creates once per field and season, crop mismatch refused, officer scoping and the administrator exception, selectors and their statuses, saving and advancing, per-field errors, area capped at the mapped field, repeatable add, update and delete, single versus repeatable endpoints, the stale version token, warnings, cross-step errors, duplicate picking numbers, computed hemp values, nothing-to-record rules, submit completeness and blocking errors, both crops submitting, every mutation refused after submit (even for an administrator), deleting a draft, the timeline |
| `module_3/tests/test_photos.py` | JPEG, PNG and WebP accepted with thumbnails; a renamed non-image, other image types and oversize files refused; the 8 photo limit; removing a photo or a draft deletes the files; another officer cannot fetch a photo |
| `module_3/tests/test_events_guards.py` | `fieldbook.step_saved`, `fieldbook.ready_for_pickup` fired once on the change to Yes, `fieldbook.submitted`; a draft does not block Module 2, a removed field takes its draft with it, a submitted book blocks reshaping and removing the field |
| `module_3/tests/test_clock.py` | cotton at 119, 120, 134, 135, 199, 200 and 201 days after sowing; hemp at its boundaries; no sowing date; harvested; milestone wording |
| `module_3/tests/test_public_api.py` | every public function through a filled cotton book (summary, sowing date, crop status, clock, ready for pickup, estimated yield, timeline, submitted) and hemp yield and pickup |

### Module 4 (Harvest Radar)

| File | Covers |
| --- | --- |
| `module_4/tests/test_readiness.py` | for both crops, days after sowing at approach minus 1, approach, ready minus 1, ready, window end and window end plus 1; the clock days read from Module 3; no sowing date; harvested and the ready flag overriding the clock; expected ready dates, milestone wording and progress |
| `module_4/tests/test_radar_api.py` | rows, buckets and clock details; harvest and ready flag from the fieldbook; the yield or benchmark estimate; KPIs and buckets agreeing with the rows; every filter and the cascading options; the crop switch and its units; officer scope and read-only rows; sorting and paging; summary equals fields; map features; calendar days and weeks; CSV content, BOM, CRLF and selected rows; query count not growing with the number of fields; a fieldbook event refreshing the cached view |
| `module_4/tests/test_pickups.py` | bulk request with partial success and a reason for each skip, duplicates refused, one open request under twelve concurrent threads, the partial unique index, cancel rules, scoped listing, `pickup.requested` and `pickup.cancelled`, the delete guard, `field.deleted` cancelling open requests, and the public API Module 5 will use |
| `module_3/tests/test_bulk_status.py` | `get_crop_status_bulk` for 1001 pairs in at most 6 queries, and agreement with the single-field functions for both crops |

### Module 5 (Deliveries)

| File | Covers |
| --- | --- |
| `module_5/tests/test_weights.py` | variance at 2.99, 3, 4.99 and 5 percent, both signs, for both crops; field weight before the estimate; no reference; moisture limits per crop; maunds |
| `module_5/tests/test_deliveries_api.py` | the inbox; scheduling and the Radar request following; bulk partial success with a reason per skip; site and crop mismatch; schedule validation (past date, phones per country, vehicle, name); the happy path and its history; every invalid transition; cancelling with a reason releasing the request; editing only while scheduled; weight, moisture and flag-note rules; warnings; officer scoping and read-only rows; immutability of delivered records and the audited administrator correction; the slip PDF; stats and list filters; CSV; the sites endpoint |
| `module_5/tests/test_events_guards.py` | every transition's event; a cancelled Radar request cancelling the delivery; the field delete and reshape guards; `field.deleted` cancelling moving deliveries; heap assignment rules (wrong site, wrong crop, not delivered, already assigned); unassigning through the guard; the stats DTO |

### Module 6 (Heap)

| File | Covers |
| --- | --- |
| `module_6/tests/test_heap_calc.py` | the documented example (17,000 kg at 34 percent with 170 kg bales: 5,780 kg and 34 bales), bales consuming input, a full heap, a remainder below one bale, rounding never allowing an extra bale, hemp shiv and dust, an empty heap, bad configuration, contributions summing to exactly 100 |
| `module_6/tests/test_heaps_api.py` | heap and batch IDs per site and the already-open warning; assignment rules; the documented example end to end with sequential serials and the bale limit; values freezing at the first bale; eight concurrent bale requests never exceeding the maximum; close rules (empty, no bales, remainder, administrator only, reason) with the remainder in the audit log; locking after close, including the correction guard; removing a delivery and the unassign guard; voiding without reusing serials; a correction in an open heap recomputing; events; the public API and lineage; CSV for both crops |

### Module 7 (QR Tracing)

| File | Covers |
| --- | --- |
| `module_7/tests/test_tokens.py` | 12-character base32 codes; 10,000 generated with no collision; characters spread evenly with no fixed prefix; codes not derived from serials; each verification check flipping (a draft or missing fieldbook, a delivery not delivered or not weighed, an open heap, bales over expected output) |
| `module_7/tests/test_qr_api.py` | one code per heap and bale, idempotent on repeated events; voiding a bale revokes its code; the public payload for a bale and a heap; a privacy deny-list of values (names, CNIC, phone, village, vehicle, officer, IDs, coordinates, other serials) and keys; identical 404 bodies for revoked, unknown and malformed codes; verification flipping on a draft fieldbook and an open heap; scans stored as a 64-character salted hash with the user-agent family only; a failing scan log not failing the page; the rate limit (30 then 429); the QR encoding the configured base URL; PNG and SVG; label PDFs with the right label count, one A4 page for 20 labels, print counts and audit; ZIP and label PNG; revoke and regenerate administrator-only with reasons and audit; lineage of three farmers at 50, 30 and 20 percent with geometry, fieldbook log and ID masking by officer; resolve for code, lower-case code, serial, URL and heap ID; the public API |

The lot fixture builds three farmers through the HTTP APIs of Modules 2 to 6 with full,
submitted cotton fieldbooks, so these tests take a little longer than the others.

### Module 8 (Settings)

| File | Covers |
| --- | --- |
| `module_8/tests/test_access.py` | every route administrator-only, with the two exceptions (`/public`, `/me/preferences`); a walk of the router so a new route cannot miss the check; preferences per officer; the last administrator and self-deactivation refused; the public config holding no sensitive or private value |
| `module_8/tests/test_values.py` | the registry listing every declared setting; **defaults identical to the old constants**; validation (range, choice, type, JSON shape); versions and the 409 on a stale save; history and restore; reset to default; cache invalidation proved by reading a value back through another endpoint; resolution order database, then `.env`, then default |
| `module_8/tests/test_reference_data.py` | list values added with a derived key, labels corrected while the key stays, duplicates refused, reorder saved, deactivate keeping existing records, delete refused while in use; CSV dry run changing nothing and a commit adding rows; formula-safe export; sites and their locked codes; officers, including a Unicode name and no password field anywhere; locations renamed and merged, moving every farmer in one transaction |
| `module_8/tests/test_config_and_system.py` | crop clock defaults, ordering rules, stale version, the impact preview writing nothing; delivery and heap defaults matching the constants; alerts read-only through the config API; the audit log filtered, paged and formula-safe, with no route that edits it; backups taken, downloaded, restored with an integrity check and a safety copy, and maintenance mode clearing itself; system information masking credentials; dummy data removed only where unreferenced |

## Frontend

From `frontend/`:

```bat
cd frontend
npm run test          :: Vitest, once
npm run test:watch    :: Vitest in watch mode
npm run lint          :: ESLint (zero warnings allowed), includes module-isolation rules
npm run typecheck     :: TypeScript strict
npm run build         :: typecheck + production build
npm run check:colors  :: brand colour audit (run after build to include the built CSS)
```

| File | Covers |
| --- | --- |
| `src/core/utils/format.test.ts` | numbers, decimals, percent, compact, units, dates, coordinates, initials, labels |
| `src/core/utils/validators.test.ts` | blank/required, email, CNIC, phone per country, UK postcode, coordinates, ranges |
| `src/core/utils/units.test.ts` | area and mass conversions, units per crop |
| `src/core/utils/dates.test.ts` | ISO date parsing, day arithmetic, relative days |
| `src/core/api/client.test.ts` | URL building, officer header, error envelope to ApiError, stale officer reset, network errors |
| `src/app/moduleRegistry.test.ts` | 8 unique numbers, paths, folders and prefixes; fixed names; Settings deferred; pipeline order; status pills |
| `src/app/layout/Sidebar.test.tsx` | 8 items in order, Settings disabled with "Coming later", links and active state, collapse to rail |
| `src/module_2/tests/format.test.ts` | the CNIC mask as it is typed and on paste, hemp ID grouping, Pakistani and UK phone normalisation, postcode formatting, and that each formatter is stable on its own output |
| `src/module_2/tests/schemas.test.ts` | both crop forms: what each requires, what it ignores from the other programme, the tehsil rule that spans two fields, and county and region required only when the postcode lookup failed |
| `src/module_2/tests/LocationCascade.test.tsx` | each level enabled only once the one above is chosen, the district, tehsil and village cleared when the province changes, manual entry offered for every district, and a village typed freely with suggestions |
| `src/module_2/tests/IdNumberInput.test.tsx` | the mask while typing and on paste for both programmes, and the SAWIE ID chip showing a preview as a preview |
| `src/module_3/tests/SchemaForm.test.tsx` | every visible field of every step of both backend definitions renders, with list options from the seed; every field type is covered; the photo slot; the date list; computed fields while typing; the fertiliser suggestion; conditional fields appearing and disappearing (`in`, `not_in`, yes/no) |
| `src/module_3/tests/RepeatableEntries.test.tsx` | summary line and totals, adding, duplicating into an unsaved entry, and deleting only after confirmation |
| `src/module_3/tests/FieldbookEditor.test.tsx` | the stepper marking each step by its own state and jumping to any step; Save and Next on every step but the last, Save and Submit only on the last; missing answers stopping a save before the server is called |
| `src/module_3/tests/schemaLogic.test.ts` | the client mirror of the backend: conditions, computed values, defaults, payloads, required fields, summaries and totals |

| `src/module_4/tests/logic.test.ts` | the Request pickup rules (ready or harvested, no open request, own farmer) with their reasons; reading and sending URL filters per crop; the active-filter count; calendar month grids |
| `src/module_4/tests/RadarPage.test.tsx` | bucket cards filtering and highlighting, synced to the URL and the API; filters read from the URL; changing a district clearing tehsil and village; Clear filters; Request pickup enabled only for an eligible selection, with its reasons; a calendar day filtering the table |

| `src/module_5/tests/logic.test.ts` | the variance preview at the thresholds, schedule validation per country, which actions each status offers |
| `src/module_5/tests/dialogs.test.tsx` | the Schedule dialog showing every problem and sending nothing until fixed; the Receive dialog previewing ok, check and flag, the moisture warning, and requiring a note when flagged; the Assign to heap control; status-dependent actions on the detail panel |
| `src/module_6/tests/heaps.test.tsx` | HeapPicker listing open heaps and opening a new one, and saying batch for hemp; Record bales validation before the server is called; Close button states for officers and administrators; the Heap and Batch wording |
| `src/module_7/tests/qr.test.tsx` | the public page for a valid bale (outside the app shell, no personal data), a revoked or unknown code (one request, never retried) and a failed check; the localhost warning for `localhost` and `127.0.0.1` but not a network address; Find a code classifying and resolving a code, a bale serial and a trace link, the not-found message, and the camera fallback message |

The Module 3 tests import the backend's `cotton.json`, `hemp.json` and master-list seed
directly, so a change to a definition that the screen cannot render fails here.

## End-to-end smoke test

Two Playwright tests, kept out of `npm run test` because they need a real browser and
both servers:

* `e2e/register-farmer.spec.ts` (Module 2): register a cotton farmer, draw a field,
  save it, then add a second field for the same farmer.
* `e2e/fieldbook-cotton.spec.ts` (Module 3): set up a cotton farmer and field through
  the API, open the fieldbook from a deep link, fill in all 11 steps through the
  screen (including repeatable entries, a conditional field, a suggestion and a step
  with nothing to record), submit through the confirmation, and check the book is
  read only and that the editor route sends it back to the summary.

```bat
cd frontend
npx playwright install chromium   :: once per machine
npm run test:e2e                  :: starts both servers itself
npm run test:e2e:ui               :: the same test with Playwright's UI
```

It writes to `backend/data/e2e.db`, so the development database is untouched, and each
run places its fields at a fresh location, so they can be repeated without clearing
anything. Map tiles are stubbed, so it needs no network.

Two environment variables help on machines that already have the tools:
`SAWIE_PYTHON` (the interpreter holding the backend dependencies, for example
`python3`) and `SAWIE_CHROMIUM` (the path to an existing Chromium).

## Dashboard (Module 1)

Backend, in `backend/module_1/tests/` (every row is created through the other modules'
HTTP APIs, as an officer would):

* `test_sections.py`: every endpoint with seeded multi-module data, crop and scope filters,
  role defaults, links and captions, units per crop, empty state, admin-only officer table.
* `test_alerts.py`: each of the eight rules one day inside, on and past its threshold
  (ready 6, 7 and 8 days; window end 200 and 201; scheduled today and yesterday; heap idle
  13 and 14 days; licence 30 and 31 days and expired; drafts 20 and 22 days), severity,
  and that the overdue link selects exactly the counted fields on the radar.
* `test_cache.py`: repeated reads are cached per section, filters and officer; any write
  (farmer, field, fieldbook step, delivery) empties it; the subscription covers every event.
* `test_reconciliation.py`: dashboard figures against Harvest Radar, Deliveries, Heap, QR
  Tracing and the farmer list, and against each other.
* `test_filters.py`: validation, range arithmetic in whole UTC days, scope, units, wording.
* `test_performance.py`: query counts do not grow with the data (two seed sizes), a cached
  read runs no queries, and every section answers inside a generous ceiling.

Frontend, in `frontend/src/module_1/tests/`: pipeline conversion and progress display,
filters synced with the address, a failing section's retry while the rest still renders,
the Get started checklist, unit and wording switches (acres and maunds, hectares and
tonnes, heap and batch), the attention panel order, and chart data tables.

### Performance on the 10,000-farmer seed

```bat
cd backend
python -m scripts.seed_perf --reset          :: 10,000 farmers, 20,000 fields, 50,000 deliveries, 500 heaps
```

Measured on SQLite in the development container, cache emptied before every request
(the worst case: in normal use a section is served from the 30-second cache in about
1 ms), 10 requests per section, admin, whole programme:

| Section | All crops p95 / median (ms) | Cotton p95 / median (ms) |
| --- | --- | --- |
| overview | 445 / 280 | 232 / 209 |
| pipeline | 349 / 270 | 193 / 163 |
| distribution | 188 / 158 | 122 / 116 |
| alerts | 412 / 360 | 205 / 189 |
| map | 85 / 67 | 97 / 75 |
| activity | 7 / 6 | 6 / 6 |
| officers | 62 / 60 | 42 / 41 |
| onboarding | 45 / 40 | 46 / 42 |
| timeseries (season) | 239 / 170 registrations, 82 / 71 deliveries | |

Every median is under 400 ms and every cotton or hemp read is under 400 ms p95. With
"All crops" and the cache empty, overview and alerts can reach about 450 ms at p95
because every rule runs once per crop. The first read after a write also rebuilds
Harvest Radar's shared dataset for the season (about 3 s for 16,000 cotton fields); the
radar page itself pays the same cost. Both are recorded for the audit.

## Audit tests

* `backend/tests/test_audit_security.py`: CSV injection, cross officer access, identity
  header in production, error bodies, CORS, uploads, the public trace page, Unicode digits.
* `backend/tests/test_scenarios.py`: cross module scenarios through the HTTP API.
* `frontend/e2e/settings.spec.ts`: an administrator adds a list value and sees it in
  Register Farmer, deactivates it and sees it gone from new forms; a crop-clock change
  previews its effect and saves; a field officer is refused Settings but keeps their
  own preferences.
* `backend/tests/test_contracts.py`: `docs/CONTRACTS.md` against events, public APIs and routes.
* `backend/tests/test_architecture.py`: module isolation, including bare imports.

See `docs/AUDIT_REPORT.md` for findings and what was not exercised.

## Before every commit

```bat
cd backend && python -m pytest && ruff check . && cd ..
cd frontend && npm run lint && npm run typecheck && npm run test && npm run build && npm run check:colors
```

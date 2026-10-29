# SAWIE contracts

How modules talk to each other and to the frontend. Every name here is fixed; later
prompts fill in the bodies, not the names.

## 1. HTTP conventions

| Topic | Contract |
| --- | --- |
| Base paths | Module routes under `/api/v1/<prefix>`; health at `/api/health`. |
| Module prefixes | 1 `/api/v1/dashboard`, 2 `/api/v1/register`, 3 `/api/v1/fieldbook`, 4 `/api/v1/radar`, 5 `/api/v1/deliveries`, 6 `/api/v1/heaps`, 7 `/api/v1/qr`, 8 `/api/v1/settings`, 9 `/api/v1/gate`. |
| Shared routes | `/api/v1/master`, `/api/v1/officers`, `/api/v1/offices`, `/api/health`. |
| JSON | snake_case keys. Dates `YYYY-MM-DD`; timestamps ISO 8601 in UTC with offset (`2026-10-19T11:07:44Z`). |
| IDs | Always strings. |
| Lists | `{ "items": [...], "total": n, "page": p, "page_size": s }`; query `page` (1-based) and `page_size` (1 to 200, default 25). |
| Errors | `{ "error": { "code", "message", "details" } }` for every non-2xx response. |
| Validation | HTTP 422, `code = "validation_error"`, `details.fields = [{ field, location, message, type }]`. |
| Sign-in | `POST /api/v1/officers/sign-in` `{officer_id, password}` checks the password and returns the account (401 `invalid_credentials`). No session is issued. |
| Acting officer | Header `X-Officer-Id`, set by the sign-in screen. Development falls back to `DEFAULT_OFFICER_CODE`; production requires the header. Roles: `officer` (own farmers only), `staff` (every officer's records, no Settings), `admin` (everything). `GET /officers/me` returns `is_admin` and `sees_all`. |
| Tracing | Every response carries `X-Request-Id` (echoes the request header if sent). |
| Module meta | Every built module exposes `GET <prefix>/meta` returning its number, name, prefixes, status, build order and purpose. |

### Shared officer endpoints, under `/api/v1/officers`

| Method and path | Purpose |
| --- | --- |
| `POST /sign-in` | Check a password and return the account. 401 `invalid_credentials`; 403 `officer_inactive`. |
| `GET /me` | The acting officer, with `email`, `phone`, `has_photo`, `is_admin` and `sees_all`. |
| `PUT /me` | Change my own email and phone. `full_name` is accepted from an administrator only (403 `name_admin_only`). Audited. |
| `POST /me/password` | Change my own password: current password plus a new one of at least 8 characters (401 `invalid_credentials`, 422 `password_too_short`). Audited without the hash. |
| `POST /me/photo` | Upload my profile photo (JPEG, PNG or WebP, 5 MB). Refused for a field officer (403 `photo_not_allowed`). Squared to 320px and re-encoded. Audited. |
| `DELETE /me/photo` | Remove my profile photo. Audited. |
| `GET /{officer_id}/photo` | That officer's photo, or 404 `photo_not_found`. |

### Module 1 endpoints (built), under `/api/v1/dashboard`

Read only, no tables. Every section is its own endpoint and takes the same filters:
`crop` (`all` default, `cotton`, `hemp`), `season_year` (default this year), `range`
(`7d`, `30d` default, `season`, `custom` with `from` and `to`, at most two years) and
`scope` (`mine` or `all`; officers default to `mine`, administrators to `all`; scope is a
choice, not a permission). Each response is cached for 30 seconds keyed by its section,
filters, acting officer and day, and the cache is dropped on every event (and again after
the publisher commits).

| Method and path | Purpose |
| --- | --- |
| `GET /overview` | Greeting block and KPIs: farmers (cotton and hemp split), fields and mapped area (acres for cotton, hectares for hemp), fieldbooks submitted percentage, ready for pickup now, delivered in the range (kg, maunds for cotton, average moisture), bales produced, QR scans. |
| `GET /pipeline` | Seven stages with `count`, `conversion_pct` (from the stage before; null for the first), `progress_pct` (share of the first stage), a `caption`, a `detail` and a `link`. |
| `GET /timeseries?metric=&interval=` | `metric` `registrations` (series farmers and fields) or `deliveries` (delivered kg and average moisture); `interval` `day`, `week` or `month` (default from the range length). Every bucket in the range is returned, empty ones as 0. |
| `GET /distribution` | Readiness buckets, fieldbook completion by step, heap utilisation (largest 12) and top districts (cotton) or counties (hemp) by mapped area (8). `focus_crop` names the crop the funnel and regions describe. |
| `GET /alerts` | All eight rules in a fixed order, each with `count`, `severity` (`attention` or `critical`), a `link` and up to five named `samples`; plus `total` and `critical`. Thresholds in `module_1/config.py`. |
| `GET /activity?module=&limit=` | Newest audited changes across modules (default 25, at most 100), each with module, officer, one-line summary and link. |
| `GET /map` | GeoJSON FeatureCollection (at most 2000) with field ID, farmer, crop, status, area and its unit, centroid `[lng, lat]`. |
| `GET /officers` | Administrators and staff (403 `admin_required` for a field officer): per officer farmers, fields, area and fieldbooks submitted this season. |
| `GET /onboarding` | `is_empty` and the three-step Get started checklist, worded for the role. |

Links (`{ path, params }`) use the query keys each target page reads, built in one place
(`module_1/services/links.py`).

### Module 2 endpoints (built), under `/api/v1/register`

| Method and path | Purpose |
| --- | --- |
| `GET /farmers?q=&crop=&field_office_id=&registered_by=&page=&page_size=` | Page of farmers. Officers see the farmers they registered; administrators see all. ID numbers and phones are masked in every row. `q` matches SAWIE ID, name, farm name, ID number fragment or phone. |
| `GET /farmers/lookup?id_number=&crop=` | Is this ID number registered? Returns `next_sawie_id_preview` when not, or the SAWIE ID plus **personal data only** when it is. `crop_mismatch` is true when the farmer belongs to the other programme, and the personal data is then withheld. Rate limited per officer and client address. |
| `POST /farmers` | Register a farmer (201) or, when the ID number already exists, update them and upsert this season's profile (200). The SAWIE ID is allocated inside the transaction. |
| `GET /farmers/{id}` | One farmer. Full ID number and phone only for the registering officer or an administrator; masked otherwise, with `sensitive_visible` saying which. |
| `PUT /farmers/{id}` | Update one farmer and upsert this season's profile. |
| `GET /farmers/{id}/profile` | Farmer, season profiles, fields and a `completeness` block (`ready_for_fieldbook` is false until at least one field is mapped). |
| `GET /farmers/{id}/fields` | This farmer's active fields plus `next_field_id_preview`. |
| `POST /farmers/{id}/fields` | Save a mapped field (201). Geometry is re-validated and the overlap check re-run inside the saving transaction. |
| `GET /fields/{field_id}` | One field. |
| `PUT /fields/{field_id}` | Reshape or re-pin. A geometry change calls guard `field.can_edit_geometry`; the field is excluded from its own overlap check. |
| `DELETE /fields/{field_id}` | Soft delete (204), after guard `field.can_delete`. The field ID is never reissued. |
| `POST /fields/validate-geometry` | Live check while drawing. **Always 200**: an overlapping or half-drawn boundary is an expected state of the map, not a failed request. `valid` says whether Save may be enabled; `conflicts` names every clash. |
| `GET /fields/map?bbox=&zoom=&crop=&limit=` | Every field in the database, for the map's context layer. Below zoom 13 the response carries centroids for clustering (`mode: "points"`, no geometry); at or above it, outlines. Hard cap of 2000 features, with `total`, `returned` and `truncated`. |
| `GET /locations/provinces?country=` | Provinces. |
| `GET /locations/districts?province=&country=` | Districts of a province. |
| `GET /locations/tehsils?district=&country=` | Tehsils of a district. May be empty; `allow_manual` is always true, so the form offers "Other (type manually)". |
| `GET /locations/villages/suggest?tehsil=&q=&limit=` | Villages already entered in that tehsil. Villages are never seeded. |
| `GET /uk/postcode/{postcode}` | County and region: cache, then postcodes.io (3 s timeout), then the bundled postcode-area table. `editable` is true only when nothing resolved it, which is the one case the officer may type them. |

### Module 3 endpoints (built), under `/api/v1/fieldbook`

Every write accepts the optional header `X-Fieldbook-Version: <book.version>`. When it
is sent and no longer matches, the write is refused with `fieldbook_stale` (D-046).
Every write is audited. After submit, every write is refused with `fieldbook_locked`.

| Method and path | Purpose |
| --- | --- |
| `GET /schemas/{crop}` | The crop's form definition (`cotton` or `hemp`), exactly as the backend validates with it. |
| `GET /selectors/officers` | Officers to choose from: yourself only, or every officer for an administrator. |
| `GET /selectors/farmers?officer_id=&q=&season_year=` | That officer's farmers (via `module_2.public_api.list_farmers_for_officer`). `q` matches SAWIE ID or name. Each row has `crop`, `field_count` and `fieldbook_status` (`no_field`, `not_started`, `in_progress`, `submitted`). 403 for another officer's list unless administrator. |
| `GET /selectors/fields?farmer_id=&season_year=` | The farmer card plus their fields, each with its `fieldbook_id` and `fieldbook_status` (`none`, `draft`, `submitted`) for the season. |
| `GET /books?status=&page=&page_size=` | Page of fieldbooks the officer may see. |
| `POST /books` | `{ field_id, season_year, crop? }`. Creates the draft (201) or returns the existing book for that field and season (200). `crop`, when sent, must match the farmer's. |
| `GET /books/{id}` | Full state: steps with entries and status, photos, `defaults` (values from Module 2 such as `field.area_acre`, `season.variety`, `farmer.licence`), `warnings`, `errors` (cross-step problems), `missing_steps`, `crop_clock`, `crop_status`, farmer and field cards, `version`. |
| `DELETE /books/{id}` | Delete a draft (204), with its photos on disk. Only its creator or an administrator. |
| `PUT /books/{id}/steps/{step}` | Save a single step: `{ data, crop? }`. Returns `{ book, warnings }`. |
| `POST /books/{id}/steps/{step}/entries` | Add an entry to a repeatable step (201). |
| `PUT /books/{id}/steps/{step}/entries/{index}` | Replace one entry. |
| `DELETE /books/{id}/steps/{step}/entries/{index}` | Remove one entry; returns the book. Indexes are not renumbered. |
| `POST /books/{id}/steps/{step}/not-applicable` | `{ not_applicable: bool }`: "Nothing to record for this step", for steps that allow it and have no entries. |
| `POST /books/{id}/photos` | Multipart `files` (201). JPEG, PNG or WebP, checked by content; 8 MB each; 8 per book. Orientation is fixed and a 320 px thumbnail stored. |
| `DELETE /books/{id}/photos/{photo_id}` | Remove a photo and its files. |
| `GET /books/{id}/photos/{photo_id}?size=thumb` | The image (or thumbnail), through the officer dependency so real authentication can be added without changing clients. |
| `POST /books/{id}/submit` | Lock permanently. Refused with `fieldbook_incomplete` (`details.missing_steps`) or `fieldbook_has_errors`. Warnings do not block. |
| `GET /books/{id}/timeline` | Activity, newest first: created, each saved entry with its one-line summary and officer, steps marked nothing to record, submitted. |

Saving validates with the same definition the screen renders: types and ranges, list
values against `master_lists`, `visible_if` (hidden answers are dropped), computed
fields (recalculated on the server), read-only defaults (the server value wins) and
the step's rules (`max_ref`, `lte_sum`, `date_vs_sowing`, `date_on_or_after`,
`date_not_before_ref`, `unique_across_entries`), each at `error` or `warning` level.

### Module 4 endpoints (built), under `/api/v1/radar`

Every read takes the same filters, so table, map, calendar, summary and export agree:
`crop` (`cotton` default, or `hemp`), `season_year` (default this year), `q` (SAWIE ID,
field ID or farmer name), `district`, `tehsil`, `village` (cotton), `county`, `region`
(hemp), `field_office_id`, `officer_id`, `status` (bucket), `pickup` (pickup state),
`ready_from`, `ready_to` (expected ready date), `scope` (`mine` default for officers;
`all` adds other officers' farmers read only; administrators always see all) and
`field_ids` (comma-separated).

| Method and path | Purpose |
| --- | --- |
| `GET /fields?sort=&page=&page_size=` | Rows, sorted and paginated on the server, plus `buckets`, `kpis`, `clock`, `facets` (filter options cascading district, tehsil, village or county, region, offices, officers) and `generated_at`. Buckets and KPIs are counted over every filter except `status`. Sort keys: `sawie_id`, `farmer`, `field_id`, `location`, `officer`, `area`, `sowing_date`, `das`, `status`, `expected_ready`, `pickup`, `estimated_kg`; a leading `-` sorts descending. |
| `GET /summary` | `buckets`, `kpis` and `clock` alone. |
| `GET /map` | GeoJSON FeatureCollection with status, overdue, milestone, pickup state, centroid and `can_request` per field. At most 2000 features, with `total` and `truncated`. |
| `GET /calendar?month=YYYY-MM` | Fields and estimated kg per expected-ready day of the month (harvested fields excluded, the date filters ignored), and the next 8 weeks of demand from this week. |
| `GET /export.csv` | The filtered rows (or `field_ids`), streamed as UTF-8 with a BOM and CRLF lines, named `radar_{crop}_{YYYY-MM-DD}.csv`: the table columns plus centroid latitude and longitude. |
| `POST /pickup-requests` | `{ crop, season_year, field_ids, preferred_date?, note? }` (201). Creates a request for each eligible field and returns `created` plus `skipped` with a code and reason for each other field. |
| `GET /pickup-requests?status=&crop=&season_year=&scope=&page=` | Requests, newest first, with `can_cancel`. |
| `POST /pickup-requests/{id}/cancel` | `{ reason }`. Only while `requested`. |

KPIs: ready now (status ready), ready within 14 days (growing or approaching with an
expected ready date within 14 days), pickup requested (requested or scheduled) and
overdue. Each carries `fields`, `area` (acres for cotton, hectares for hemp) and
`estimated_kg`.

### Module 5 endpoints (built), under `/api/v1/deliveries`

Filters for the list, stats and export: `crop`, `status`, `site_id`, `date_from`,
`date_to` (scheduled date), `officer_id`, `district` or `county`, `q` (delivery number,
farmer name, SAWIE ID, field ID or vehicle) and `scope` (`mine` default; `all` shows other
officers' deliveries read only, `can_act` false).

| Method and path | Purpose |
| --- | --- |
| `GET /inbox?crop=&scope=` | Radar requests still `requested`, with farmer, field, location, estimate and preferred date. |
| `POST /schedule` | `{ request_ids, site_id, scheduled_date, driver_name, driver_phone, vehicle_no, note? }` (201). One delivery per request with the same transport; returns `created` and `skipped` (code and reason). Calls `module_4.public_api.mark_pickup_scheduled`. |
| `GET /?page=&page_size=` | Deliveries plus `status_counts` (for every status under the other filters). |
| `GET /{id}` | One delivery with `history` and the crop's `thresholds`. Any officer may read; acting is scoped. |
| `PUT /{id}` | Edit site, date, driver, phone, vehicle or note, only while `scheduled`. |
| `POST /{id}/dispatch` | `scheduled` to `in_transit`; optional `field_weight_kg`, `note`. |
| `POST /{id}/receive` | `in_transit` to `delivered`; `weighbridge_weight_kg` (> 0), `moisture_pct` (0 to 100), `note` (required when the variance is flagged). Returns `{ delivery, warnings }`. Closes the load's Radar request (`mark_pickup_fulfilled`), so the field can be requested again. |
| `POST /{id}/cancel` | `{ reason }`; from `scheduled` or `in_transit`. Also cancels the Radar request (`mark_pickup_cancelled`), so the field can be requested again. |
| `POST /{id}/correct` | Administrators: `{ reason, weighbridge_weight_kg?, moisture_pct?, field_weight_kg? }` on a `delivered` record. Asks guard `delivery.can_correct`; audited with before and after. |
| `GET /{id}/slip.pdf` | One-page PDF for the driver with a QR of the delivery number. |
| `GET /stats` | Requests waiting, scheduled, in transit, delivered this week (count, kg, maunds), weight flags. |
| `GET /export.csv` | Filtered deliveries, UTF-8 with BOM. |

Variance: weighbridge minus the field weight (or the estimate when no field weight was
recorded), as kg and as a percentage rounded half up to 0.01. Level `ok` below the warn
threshold, `warn` from it, `flag` from the flag threshold (defaults 3 and 5 percent).
Moisture above the crop's limit returns a warning, not an error.

### Shared sites (built)

| Method and path | Response |
| --- | --- |
| `GET /api/v1/sites?crop=` | Active sites, by code. |
| `GET /api/v1/sites/{id}` | One site. |

### Module 6 endpoints (built), under `/api/v1/heaps`

`{key}` is a heap's primary key or its business ID (`BWP-G1-H01`).

| Method and path | Purpose |
| --- | --- |
| `GET /?crop=&site_id=&status=` | Heaps with deliveries count, input kg and bales made. |
| `POST /` | `{ site_id, note? }` (201). Opens a heap (cotton) or batch (hemp) with the config defaults. `warnings` says when another is already open at the site. |
| `GET /config` | The per-crop defaults (placeholders). |
| `GET /{key}` | Detail: totals (every formula), deliveries, contributions, bales, delivered deliveries pending at the site (while open) and `permissions`. |
| `PUT /{key}` | Ratio, bale unit, shiv and dust while open and before the first bale; the note while open. |
| `POST /{key}/deliveries` | `{ delivery_ids }`. Adds delivered, unassigned deliveries of the same site and crop; returns `added` and `skipped`. |
| `DELETE /{key}/deliveries/{delivery_id}?reason=` | While open and with no active bales (guard `delivery.can_unassign`). |
| `POST /{key}/bales` | `{ count }` (201). Sequential serials; refused beyond `max_bales`. |
| `POST /bales/{serial}/void` | Administrators, `{ reason }`, while the heap is open. |
| `POST /{key}/close` | `{ reason?, with_remainder? }`. See the close rules below. |
| `GET /{key}/contributors` | Farmer contribution. |
| `GET /{key}/export.csv` | Summary, deliveries with farmer shares, and bales (UTF-8 with BOM). |

Formulas (one module, `module_6/services/heap_calc.py`, Decimal): input = sum of
weighbridge weights; expected output = input x ratio; max bales = floor(expected / unit);
input per bale = unit / ratio; remaining input = max(0, input - bales made x input per
bale); remaining output = remaining input x ratio; can close when remaining output is
below one bale unit. Hemp adds expected shiv and dust; cotton adds maunds. Total bale
weight never exceeds expected output. Contribution percentages use the largest
remainder, so they add up to exactly 100.

Close rules: at least one delivery; with zero bales a reason is required; with output
still expected (remaining output of a bale or more) only an administrator may close,
with `with_remainder: true` and a reason, and the remainder figures go into the audit
log. A closed heap refuses every change with `heap_closed`.

### Module 7 endpoints (built), under `/api/v1/qr`

| Method and path | Purpose |
| --- | --- |
| `GET /public/{token}` | **Public**, no officer needed. The privacy-filtered trace (an allow-list: product, serial, weight, heap ID, season, site name and region, processing dates, programme and country, farm and field counts, districts or counties, harvest window, timeline, checks). `Cache-Control: public, max-age=60`, server cache 60 s, 30 lookups a minute per address. Unknown, revoked and malformed codes all answer the same 404 `qr_invalid` "This code is not valid". Each answer logs a scan after the response. |
| `GET /lots?crop=&site_id=` | `{ items, base_url, base_url_is_local }`: heaps and batches with their active code. |
| `GET /lots/{heap_id}/overview` | Code, trace URL, summary, scan counts, base URL. |
| `GET /bales?heap_id=` | Every bale (voided included) with code, status, prints and scans. |
| `GET /tokens/{token}/image.png?size=` | QR image, error correction M, 4-module quiet zone. |
| `GET /tokens/{token}/image.svg` | The same as SVG. |
| `POST /labels` | `{ serials }`. A4 PDF, 3 by 8 labels; counts a print for each and audits. |
| `GET /bales/{serial}/label.png` | One label as PNG; counts as a print. |
| `POST /images.zip` | `{ serials }`. QR PNGs named by serial. |
| `POST /tokens/{token}/revoke` | Administrators, `{ reason }`. |
| `POST /bales/{serial}/regenerate` | Administrators, `{ reason }`, active bales only. Revokes the old code and issues a new one. |
| `GET /trace/bale/{serial}`, `GET /trace/heap/{heap_id}` | Internal chain: bale, heap, deliveries, farmers with share (ID numbers masked unless the officer registered the farmer or is an administrator), fields with geometry and fieldbook log, checks. |
| `GET /resolve?q=` | A code, a bale serial, a heap ID or a trace URL to `{ kind, heap_id, bale_serial, token, token_status }`. Logs an internal scan when a code is involved. |
| `GET /scans/summary?heap_id=` | `{ total, public, internal, last_scan_at, active_tokens, generated_at }`. |

Checks: `fieldbooks_submitted` (every contributing field has a submitted fieldbook for the
season), `deliveries_weighed` (every delivery is delivered with a weighbridge weight),
`heap_closed`, and `mass_balance` (active bale weight does not exceed expected output).

### Module 9 endpoints (built), under `/api/v1/gate`

Every route takes `site_id` (and optional `crop`) except the entry routes, which are
addressed by key. Accepting calls Module 5's `receive_at_gate`; rejecting calls
`cancel_at_gate`, so the delivery and the gate entry never disagree.

| Method and path | Purpose |
| --- | --- |
| `GET /summary?site_id=&crop=` | `inbound`, `pending`, `accepted_today`, `rejected_today`, `net_kg_today` for the site |
| `GET /inbound?site_id=&crop=` | In-transit deliveries due at the site with no gate entry yet, longest wait first, with the farmer's name, field, vehicle and reference weight |
| `GET /entries?site_id=&status=&crop=&limit=&offset=` | `{ items, total }`, newest arrival first. `status` is `pending`, `accepted`, `rejected` or `decided` (either decision); `limit` at most 100 |
| `POST /entries` | `{ delivery_id, note? }` (201). Only an `in_transit` delivery without an entry. Publishes `gate.entry_created` |
| `GET /entries/{entry_id}` | One gate entry with the site code and name, and for a pending entry its reference weight and the tolerances in force |
| `POST /entries/{entry_id}/accept` | `{ gross_weight_kg, tare_weight_kg, moisture_pct, note? }`. Net = gross - tare; the delivery is received with that net weight. Returns `{ entry, warnings }`; a flagged variance needs a note (Module 5's rule) |
| `POST /entries/{entry_id}/reject` | `{ rejection_reason }` (3 to 500 characters). The delivery is cancelled with the same reason and the Radar request released |

`can_accept` and `can_reject` are true only while the entry is `pending`. A load
received or cancelled from the Deliveries screen resolves its pending gate entry too.

### Shared endpoints (built)

| Method and path | Response |
| --- | --- |
| `GET /api/health` | `{ status: "ok" or "degraded", app, version, environment, database: { reachable, dialect }, server_time }`. Always HTTP 200 while the process runs. |
| `GET /api/v1/master` | `{ keys: string[] }` |
| `GET /api/v1/master/{list_key}?country=&crop=` | `{ list_key, country, crop, items: [{ value, label, sort_order, country, crop }] }`. A scope filter keeps rows scoped to that value plus global rows (scope NULL). |
| `GET /api/v1/officers?country=&field_office_id=&role=&q=&page=&page_size=` | Page of officers (admins first) |
| `GET /api/v1/officers/me` | The acting officer: `{ id, code, full_name, role, country, field_office_id, field_office_name, is_admin }` |
| `GET /api/v1/officers/{id}` | One officer |
| `GET /api/v1/offices?country=` | Page of field offices |
| `GET /api/v1/offices/{id}` | One field office |

### Module 8 endpoints (built), under `/api/v1/settings`

Every route needs role `admin` (`admin_required`, 403) except `GET /public`, which is
open because the web app reads map tiles and the QR base URL before anyone is
identified, and `GET /me/preferences` and `PUT /me/preferences`, which every officer uses
for their own row.
Every write is audited and publishes `config.changed`.

| Method and path | Purpose |
| --- | --- |
| `GET /public` | Tiles, attribution, QR base URL, season labels. No secret, cached 60 s |
| `GET /registry` | Every declared setting with its value, source, version and validation |
| `GET /values/{key}` | One setting |
| `PUT /values/{key}` | Change one setting (`expected_version` for optimistic concurrency) |
| `DELETE /values/{key}` | Drop the override, back to `.env` or the default |
| `GET /history` | Recent changes, newest first (`key` narrows it) |
| `POST /history/{id}/restore` | Put a previous value back as a new change |
| `GET /officers` | Officers (`active`, `office_id`, `q`) |
| `POST /officers` | Add an officer (no password field exists anywhere) |
| `GET /officers/{id}` | One officer |
| `PUT /officers/{id}` | Change an officer |
| `POST /officers/{id}/activate` | Activate |
| `POST /officers/{id}/deactivate` | Deactivate (refused for the last admin or yourself) |
| `POST /officers/import` | CSV import (`dry_run=true` checks and writes nothing) |
| `GET /officers/export.csv` | Officers as CSV |
| `GET /offices`, `POST /offices`, `PUT /offices/{id}` | Field offices |
| `GET /sites`, `POST /sites`, `PUT /sites/{id}` | Ginners and processors |
| `DELETE /sites/{id}` | Delete a site nothing uses |
| `GET /lists` | Every dropdown list with its size and what requires it |
| `GET /lists/{key}/values` | Values of one list, with usage counts |
| `POST /lists/{key}/values` | Add a value (the key is derived and then fixed) |
| `PUT /lists/{key}/values/{id}` | Edit the label, or activate and deactivate |
| `DELETE /lists/{key}/values/{id}` | Delete a value nothing uses |
| `POST /lists/{key}/reorder` | Save a new order |
| `POST /lists/{key}/import` | CSV import with `dry_run` |
| `GET /lists/{key}/export.csv` | One list as CSV |
| `GET /locations/tree` | Country, province, district, tehsil (UK: postcode area to county) |
| `POST /locations`, `PUT /locations/{id}`, `DELETE /locations/{id}` | Add, rename or deactivate, delete |
| `GET /locations/{id}/rename-preview` | How many farmers a rename would move |
| `POST /locations/merge-preview`, `POST /locations/merge` | Merge one place into another |
| `POST /locations/import`, `GET /locations/export.csv` | CSV in and out |
| `GET /config/{block}` | `clock`, `delivery`, `heap` or `alerts`, from the owning module |
| `PUT /config/{block}` | Change it through the owning module (`alerts` is read-only here) |
| `POST /config/clock/preview` | Fields that would change readiness bucket |
| `GET /permissions` | The role matrix, generated from `core.permissions` |
| `GET /audit` | The audit log, paged and filtered |
| `GET /audit/facets` | The entities, actions and officers present, for the filters |
| `GET /audit/export.csv` | The filtered log as CSV (formula-safe) |
| `GET /backups/status` | Whether backups are taken here, and why not when they are not |
| `GET /backups`, `POST /backups`, `DELETE /backups/{id}` | List, take, delete |
| `GET /backups/{id}/download` | The file |
| `POST /backups/{id}/restore` | Restore (typed confirmation, safety copy, maintenance mode) |
| `GET /system` | Versions, database, record counts and health checks |
| `GET /system/dummy`, `POST /system/dummy/remove` | Seeded placeholders, and removing the unused ones |
| `POST /qr/test-url` | Check the public base URL answers |
| `POST /map/test-tiles` | Fetch one tile from a provider |
| `GET /me/preferences`, `PUT /me/preferences` | The acting officer's own display choices |


### Stable error codes

| Code | HTTP | Meaning |
| --- | --- | --- |
| `bad_request` | 400 | Malformed request |
| `unauthorized` | 401 | Generic authentication failure |
| `officer_required` | 401 | No `X-Officer-Id` (production) or default officer missing (development) |
| `officer_not_found` | 401 | `X-Officer-Id` does not match an officer (the frontend clears its stored choice) |
| `forbidden` | 403 | Generic permission failure |
| `officer_inactive` | 403 | Acting officer is deactivated |
| `admin_required` | 403 | Endpoint needs role `admin` |
| `not_found` | 404 | Unknown route |
| `officer_not_found_by_id` | 404 | `GET /officers/{id}` miss |
| `field_office_not_found` | 404 | `GET /offices/{id}` miss |
| `master_list_not_found` | 404 | Unknown `list_key` |
| `unknown_setting` | 404 | No setting with that key is declared in the registry |
| `unknown_list` | 404 | Unknown `list_key` in Settings |
| `site_not_found`, `office_not_found`, `backup_not_found` | 404 | Settings record miss |
| `stale_version` | 409 | Someone saved this setting or config block first; the current value is returned |
| `duplicate_code` | 409 | An officer, office or site already has that code |
| `invalid_setting` | 422 | The value does not satisfy its declared validation |
| `code_locked` | 422 | A site code cannot change once heaps carry it |
| `site_in_use`, `value_in_use` | 422 | Refused: deactivate instead of deleting |
| `self_deactivation` | 422 | An administrator cannot deactivate their own account |
| `last_admin` | 422 | The last active administrator cannot be removed or demoted |
| `confirmation_required` | 422 | A restore needs the phrase RESTORE typed exactly |
| `backup_not_supported` | 422 | Backups are managed by the database host, not by SAWIE |
| `maintenance` | 503 | A restore is replacing the database; writes are refused for a few seconds |
| `method_not_allowed` | 405 | |
| `conflict` | 409 | Generic conflict |
| `guard_denied` | 409 | A guard denied without its own code; `details.reasons` lists every denial |
| `validation_error` | 422 | Input failed validation |
| `internal_error` | 500 | Unexpected failure; `details.request_id` identifies the log lines |

### Module 1 error codes (built)

| Code | HTTP | Meaning |
| --- | --- | --- |
| `dashboard_crop_invalid`, `dashboard_scope_invalid`, `dashboard_range_invalid` | 422 | Bad filter value, or a range that starts after it ends |
| `dashboard_range_incomplete`, `dashboard_range_too_long` | 422 | A custom range without both ends, or longer than two years |
| `dashboard_metric_invalid`, `dashboard_interval_invalid` | 422 | Unknown time-series metric or interval |

### Module 2 error codes (built)

| Code | HTTP | Meaning |
| --- | --- | --- |
| `farmer_not_found` | 404 | Unknown farmer id |
| `field_not_found` | 404 | Unknown field id, or the field is soft deleted |
| `location_not_found` | 404 | Unknown province, district or tehsil code |
| `farmer_duplicate_id_number` | 409 | That ID number already belongs to another SAWIE ID |
| `farmer_duplicate_licence_no` | 409 | That Home Office licence number is already recorded |
| `farmer_crop_mismatch` | 409 | The farmer is registered in the other crop programme |
| `field_overlap` | 409 | The boundary overlaps an active field; `details.conflicts` lists every one |
| `field_has_fieldbook`, `field_has_delivery` | 409 | A guard denied the delete or reshape: a submitted fieldbook (Module 3) or a delivery (Module 5, once built) |
| `field_geometry_invalid` | 422 | Not a usable single-ring GeoJSON Polygon |
| `field_self_intersection` | 422 | The boundary crosses itself |
| `field_vertex_limit` | 422 | More than 500 corners |
| `field_outside_country` | 422 | Drawn outside the farmer's country |
| `field_area_too_small` | 422 | Below 100 m2 |
| `field_area_too_large` | 422 | Above 500 ha |
| `field_pin_invalid`, `field_pin_outside` | 422 | The pin is unusable, or more than 50 m from the field |
| `master_value_invalid` | 422 | A dropdown value is not in the master list that feeds it |
| `field_office_invalid` | 422 | Unknown or inactive field office |
| `field_office_country_mismatch` | 422 | The office belongs to the other crop programme |
| `rate_limited` | 429 | Too many lookups; `details.retry_after_seconds` |

### Module 5 error codes (built)

| Code | HTTP | Meaning |
| --- | --- | --- |
| `delivery_not_found`, `site_not_found` | 404 or 422 | Unknown delivery or site |
| `delivery_forbidden` | 403 | Another officer's farmer |
| `delivery_admin_only` | 403 | Corrections are for administrators |
| `invalid_transition` | 409 | The status machine does not allow it; `details.from`, `to`, `allowed` |
| `delivery_locked` | 409 | Editing is only for scheduled deliveries |
| `delivery_not_delivered` | 409 or 422 | Correcting, or assigning to a heap, a delivery that is not delivered |
| `site_crop_mismatch` | 422 | The site takes the other crop |
| `delivery_date_past`, `delivery_weight_invalid`, `delivery_moisture_invalid`, `delivery_flag_note_required`, `delivery_reason_required` | 422 | Input rules; field errors in `details.fields` |
| `delivery_wrong_site`, `delivery_wrong_crop`, `delivery_already_assigned`, `delivery_not_assigned` | 422 | Heap assignment rules |
| `field_has_delivery` | 409 | Guard: the field has a delivery that is not cancelled |

Skip codes in a scheduling result: `pickup_not_found`, `pickup_not_waiting`,
`delivery_forbidden`, `site_crop_mismatch`.

### Module 6 error codes (built)

| Code | HTTP | Meaning |
| --- | --- | --- |
| `heap_not_found`, `bale_not_found`, `heap_delivery_not_found` | 404 | Unknown heap, bale, or a delivery not in that heap |
| `heap_admin_only` | 403 | Voiding bales and closing with a remainder are for administrators |
| `heap_closed` | 409 | The heap is closed (also the `delivery.can_correct` and `delivery.can_unassign` denial) |
| `heap_has_bales` | 409 | Guard `delivery.can_unassign`: the heap already has active bales |
| `heap_bale_limit`, `heap_mass_balance` | 409 | More bales than the expected output allows |
| `heap_values_frozen` | 409 | Ratio or unit changed after the first bale |
| `heap_has_remainder` | 409 | Output is still expected; close with remainder instead |
| `heap_empty` | 409 | Closing without any delivery |
| `bale_already_voided` | 409 | |
| `heap_reason_required`, `heap_value_invalid`, `heap_bale_count_invalid`, `heap_no_deliveries` | 422 | Input rules |

### Module 7 error codes (built)

| Code | HTTP | Meaning |
| --- | --- | --- |
| `qr_invalid` | 404 | Public page: unknown, revoked or malformed code (one identical body for all) |
| `rate_limited` | 429 | Too many public lookups; `details.retry_after_seconds` |
| `qr_token_not_found`, `qr_not_found` | 404 | Unknown code (internal), or nothing matches a Find query |
| `qr_admin_only` | 403 | Revoke and regenerate are for administrators |
| `qr_token_revoked` | 409 | The code is already revoked |
| `qr_bale_not_active` | 409 or 422 | Regenerating for a voided bale, or printing a bale with no active code |
| `qr_reason_required`, `qr_reason_too_long`, `qr_query_empty`, `qr_no_bales`, `qr_too_many` | 422 | Input rules (at most 480 labels at a time) |

### Module 9 error codes (built)

| Code | HTTP | Meaning |
| --- | --- | --- |
| `gate_entry_not_found` | 404 | Unknown gate entry |
| `gate_entry_exists` | 409 | That delivery already has a gate entry |
| `invalid_gate_status` | 409 | Accepting or rejecting an entry that is already decided |
| `gate_delivery_not_in_transit` | 422 | Only an in-transit delivery can arrive at the gate |
| `gate_weight_invalid` | 422 | Gross is not above tare, so the net is zero or less |
| `gate_reason_required`, `gate_reason_too_long` | 422 | Rejecting needs a reason of 3 to 500 characters |
| `gate_note_too_long` | 422 | The note is over 1,000 characters |
| `site_not_found` | 422 | Unknown or inactive site |

Accepting and rejecting surface Module 5's own codes (`delivery_flag_note_required`,
`invalid_transition`) because Module 5 decides whether the delivery may move.

### Module 4 error codes (built)

| Code | HTTP | Meaning |
| --- | --- | --- |
| `pickup_not_found` | 404 | Unknown pickup request |
| `pickup_forbidden` | 403 | The request belongs to another officer's farmer |
| `pickup_not_cancellable` | 409 | Only a request still `requested` can be cancelled by an officer |
| `pickup_not_open` | 409 | Module 5 tried to schedule or fulfil a closed request |
| `pickup_reason_required`, `pickup_reason_too_long` | 422 | Cancelling needs a reason of at most 500 characters |
| `pickup_no_fields`, `pickup_too_many`, `pickup_note_too_long` | 422 | Bad bulk request |
| `radar_crop_invalid`, `radar_status_invalid`, `radar_pickup_invalid`, `radar_scope_invalid`, `radar_sort_invalid`, `radar_month_invalid` | 422 | Bad filter value |
| `field_has_pickup_request` | 409 | Guard on `field.can_delete`: the field has an open pickup request |

Skip codes in a bulk result (not errors): `field_not_found`, `pickup_forbidden`
(another officer's farmer), `pickup_not_ready` (not ready or harvested),
`pickup_already_open`.

### Module 3 error codes (built)

| Code | HTTP | Meaning |
| --- | --- | --- |
| `fieldbook_not_found` | 404 | Unknown fieldbook, or a draft that was deleted |
| `fieldbook_source_missing` | 404 | The book's farmer or field no longer exists in Module 2 |
| `fieldbook_schema_not_found` | 404 | No form definition for that crop |
| `fieldbook_step_unknown` | 404 | The step is not in this crop's definition |
| `fieldbook_entry_not_found` | 404 | No entry at that index |
| `photo_not_found` | 404 | Unknown photo, or its file is missing |
| `fieldbook_forbidden` | 403 | The farmer belongs to another officer |
| `fieldbook_delete_forbidden` | 403 | Only the creator or an administrator may delete a draft |
| `fieldbook_locked` | 409 | The book is submitted; every write is refused |
| `fieldbook_stale` | 409 | `X-Fieldbook-Version` is out of date; `details.expected`, `details.current` |
| `fieldbook_crop_mismatch` | 409 | The crop sent does not match the farmer's programme |
| `fieldbook_step_repeatable`, `fieldbook_step_single` | 409 | The single-step endpoint was used for a repeatable step, or the reverse |
| `fieldbook_step_required` | 409 | That step cannot be marked as nothing to record |
| `fieldbook_step_has_entries` | 409 | Delete the entries before marking nothing to record |
| `fieldbook_incomplete` | 409 | Submit refused; `details.missing_steps` |
| `fieldbook_has_errors` | 409 | Submit refused; `details.errors` lists the blocking problems |
| `photo_limit` | 409 | More than 8 photos; `details.limit` |
| `photo_too_large` | 413 | A file is over 8 MB |
| `photo_invalid`, `photo_type_not_allowed`, `photo_missing` | 422 | Not a readable image, not JPEG/PNG/WebP, or no file sent |
| `validation_error` | 422 | Answers failed the step's definition; `details.fields[]` with `field` (`key`, or `key.part`) and `message` |

Modules add their own codes to this table when they are built.

## 2. Events

Published with `core.events.bus.publish(name, payload, officer_id=..., session=...)`.
Delivery is synchronous, in registration order, inside the publisher's transaction.
A failing handler is logged with its traceback, the remaining handlers still run, and
then `EventHandlerError` is raised so the whole unit of work rolls back. Payloads are
plain JSON values (IDs are strings, timestamps ISO 8601). Every payload also travels
with `event.officer_id` and `event.occurred_at`.

| Event | Publisher | Payload |
| --- | --- | --- |
| `farmer.registered` | 2 | `{ farmer_id, sawie_id, crop, country, field_office_id }` |
| `farmer.updated` | 2 | `{ farmer_id, sawie_id, changed: string[] }` |
| `field.created` | 2 | `{ field_id, field_code, farmer_id, area_m2, bbox: [minLng, minLat, maxLng, maxLat] }` |
| `field.updated` | 2 | `{ field_id, field_code, farmer_id, changed: string[], geometry_changed: bool }` |
| `field.deleted` | 2 | `{ field_id, field_code, farmer_id }` (soft delete) |
| `fieldbook.step_saved` | 3 | `{ fieldbook_id, field_id, season_year, step_key, entry_index }` |
| `fieldbook.submitted` | 3 | `{ fieldbook_id, field_id, farmer_id, season_year }` |
| `fieldbook.ready_for_pickup` | 3 | `{ fieldbook_id, field_id, farmer_id, season_year, crop, entry_index, picking_number, estimated_kg, ready_at }`; fired when a harvest (cotton) or baling (hemp) entry changes to ready Yes, once per entry. `picking_number` is null for hemp; `estimated_kg` is yield x area sown x 40 for cotton, total straw weight for hemp. |
| `pickup.requested` | 4 | `{ pickup_request_id, request_no, field_id, farmer_id, crop, season_year, estimated_quantity_kg, quantity_is_estimate, preferred_date }` |
| `pickup.cancelled` | 4 | the same plus `{ reason, previous_status }` |
| `delivery.scheduled` | 5 | `{ delivery_id, delivery_no, pickup_request_id, field_id, farmer_id, site_id, crop, season_year, scheduled_date }` |
| `delivery.dispatched` | 5 | the same identity fields plus `{ dispatched_at, field_weight_kg }` |
| `delivery.delivered` | 5 | the same identity fields plus `{ weighbridge_weight_kg, moisture_pct, variance_level, delivered_at }` |
| `delivery.cancelled` | 5 | the same identity fields plus `{ reason, previous_status }` |
| `delivery.corrected` | 5 | the same identity fields plus `{ weighbridge_weight_kg, moisture_pct, reason }`; an administrator's correction of a delivered record |
| `heap.opened` | 6 | `{ heap_pk, heap_id, kind, crop, site_id }` (`kind` is `heap` or `batch`) |
| `heap.closed` | 6 | `{ heap_pk, heap_id, crop, site_id, total_input_kg, bale_count, with_remainder }` |
| `bale.created` | 6 | `{ bale_id, bale_serial, heap_id, heap_pk, weight_kg, crop }`, one event per bale |
| `bale.voided` | 6 | `{ bale_id, bale_serial, heap_id, reason }` |
| `qr.scanned` | 7 | `{ qr_token_id, token_type, heap_id, bale_serial, channel, scanned_at }`, published from the scan's own session after the response |
| `config.changed` | 8 | `{ key, group }`; `key` is a setting key (`map.tile_provider`), a config block key (`config.crop_clock`) or a reference-data name (`sites`). Every cache of a resolved value drops it. Crop-clock blocks published by Modules 3, 5 and 6 also name `crops` (the crops whose clock changed). |
| `officer.created` | 8 | `{ officer_id, code, full_name, role }` |
| `officer.updated` | 8 | `{ officer_id, code, changed: string[] }` |
| `officer.deactivated` | 8 | `{ officer_id, code, active }` (also published when an officer is activated again) |
| `list.changed` | 8 | `{ list_key, action }` where action is `created`, `updated`, `deleted` or `reordered` |
| `location.changed` | 8 | `{ country, level }` |
| `backup.created` | 8 | `{ filename, size_bytes, kind }` (`kind` is `manual` or `safety`) |
| `backup.restored` | 8 | `{ filename, safety_backup }` |
| `gate.entry_created` | 9 | `{ gate_entry_id, delivery_id, delivery_no, site_id, crop, status, net_weight_kg, moisture_pct }` (weights null on arrival) |
| `gate.entry_accepted` | 9 | the same plus `{ warnings }` from the delivery receipt |
| `gate.entry_rejected` | 9 | the same plus `{ reason }` |

Naming in payloads: `*_id` is the UUID primary key and `*_code`, `*_no` or `sawie_id`
the human-readable business ID. Two exceptions keep the prompt's names: `heap_id` is the
heap's business ID (for example `BWP-G1-H01`), with `heap_pk` for its key, and
`bale_serial` is the bale's business ID.

The list is enforced in code: `core.events.KNOWN_EVENTS` rejects any other name, and
a test compares it with this table. Adding an event means updating both.

Planned subscriptions (registered in each module's `events.register`):

| Subscriber | Listens to | Purpose |
| --- | --- | --- |
| 3 Fieldbook (registered) | `field.deleted` | soft-remove that field's draft fieldbooks (a submitted book blocks the delete) |
| 4 Harvest Radar (registered) | `fieldbook.ready_for_pickup`, `fieldbook.step_saved`, `field.created`, `field.updated` | drop cached radar views (now and after the publisher commits) |
| 4 Harvest Radar (registered) | `field.deleted` | cancel the field's open pickup requests (an administrator override; the guard normally blocks the delete) |
| 5 Deliveries (registered) | `pickup.cancelled` | cancel the delivery still moving for that request |
| 5 Deliveries (registered) | `field.deleted` | cancel deliveries still moving for a removed field (administrator override) |
| 6 Heap (registered) | `delivery.delivered`, `delivery.cancelled` | nothing stored to refresh: pending lists and totals are computed on read |
| 7 QR Tracing (registered) | `heap.opened`, `bale.created` | issue the code, once (idempotent) |
| 7 QR Tracing (registered) | `bale.voided` | revoke the bale's code |
| 7 QR Tracing (registered) | `heap.closed` | drop cached public pages for that heap |
| 9 Gate Reception (registered) | `delivery.delivered`, `delivery.cancelled` | resolve a still-pending gate entry when the load was received or cancelled in Deliveries, so it never stays open twice |
| 9 Gate Reception (registered) | `delivery.corrected` | copy an administrator's corrected weight and moisture onto the accepted gate entry, and note the correction |
| 1 Dashboard (registered) | every event | drop the cached sections, now and after the publisher commits |

## 3. Guards

`core.guards.guards.enforce(name, **context)` raises a 409 with every denial reason.

| Guard | Context | Registered by | Denies when |
| --- | --- | --- | --- |
| `field.can_delete` | `field_id`, `session` | 3, 4, 5 | a submitted fieldbook exists (3, `field_has_fieldbook`), an open pickup request exists (4, `field_has_pickup_request`) or a delivery that is not cancelled (5, `field_has_delivery`) |
| `field.can_edit_geometry` | `field_id`, `session` | 3, 5 | a submitted fieldbook exists (3, `field_has_fieldbook`) or a delivery that is not cancelled (5, `field_has_delivery`) |
| `delivery.can_correct` | `delivery_id`, `heap_id`, `session` | 6 | the delivery is in a closed heap (`heap_closed`) |
| `delivery.can_unassign` | `delivery_id`, `heap_id`, `session` | 6 | the heap is closed (`heap_closed`) or has active bales (`heap_has_bales`) |

Module 2 calls both guards (on delete and on a geometry change) and never imports
Modules 3 to 5. The caller passes its own `session` so a check reads inside the same
transaction; opening a second SQLite connection there would wait on the caller's write
lock (D-045). A draft fieldbook does not block either action. The 409 carries every
denial reason at once. Moving only the pin is not a geometry change and is not guarded.

## 4. Public APIs

A module's `public_api.py` is the only file other modules may import. Functions take
plain arguments plus a `Session`, and return frozen dataclass DTOs (never ORM rows).
Planned signatures:

### Module 2 Register Farmer (built)

Sensitive values (the full ID number and phone) are returned only when the caller asks
for them **and** is allowed to see them: the officer who registered the farmer, or an
administrator. Everyone else gets the masked form, and `sensitive_included` says which
was returned, so a careless caller leaks nothing.

```python
@dataclass(frozen=True)
class FarmerDTO:
    id: str; sawie_id: int; name: str; crop: str; country: str
    field_office_id: str; registered_by: str | None
    id_number: str; phone: str | None; sensitive_included: bool
    home_office_licence_no: str | None = None   # hemp; added for Module 3 (D-047)

# Added for Module 4 (D-059): every active field with its farmer, in one query.
# FieldSourceDTO: id, field_id, farmer_id, sawie_id, farmer_name, father_name, farm_name, crop,
# country, province, district, tehsil, village, county, region, field_office_id, registered_by,
# area_acre, area_ha, pin_lat, pin_lng, bbox, geometry (only with include_geometry=True).
def list_field_sources(session, *, crop: str | None = None, include_geometry: bool = False) -> list[FieldSourceDTO]

@dataclass(frozen=True)
class FieldDTO:
    id: str; field_id: str; farmer_id: str
    area_m2: float; area_acre: float; area_ha: float; vertex_count: int
    pin_lat: float; pin_lng: float; bbox: tuple[float, float, float, float]

@dataclass(frozen=True)
class SeasonProfileDTO:
    farmer_id: str; season_year: int; variety: str; tenure: str
    previous_crop: str | None; updated_at: datetime

def get_farmer(session, farmer_id, *, include_sensitive=False, officer_id=None) -> FarmerDTO | None
def get_farmer_by_sawie_id(session, sawie_id, *, include_sensitive=False, officer_id=None) -> FarmerDTO | None
def get_farmers(session, farmer_ids) -> dict[str, FarmerDTO]
def search_farmers(session, query=None, *, officer_id=None, crop=None, limit=20) -> list[FarmerDTO]
def list_farmers_for_officer(session, officer_id) -> list[FarmerDTO]
def count_farmers(session, *, country=None, crop=None) -> int

def get_field(session, field_id) -> FieldDTO | None          # accepts the UUID or 1001-01
def get_fields(session, field_ids) -> dict[str, FieldDTO]
def list_fields_for_farmer(session, farmer_id) -> list[FieldDTO]
def list_fields(session, *, bbox=None, crop=None, limit=2000) -> list[FieldDTO]
def list_fields_in_bbox(session, bbox, *, crop=None) -> list[FieldDTO]
def get_field_geometry(session, field_id) -> dict | None     # GeoJSON Polygon
def total_area_m2(session, *, country=None, crop=None) -> float

def get_season_profile(session, farmer_id, season_year) -> SeasonProfileDTO | None
```

Soft-deleted fields are invisible to every function above. `sawie_id` is an integer
here and in event payloads, because it is a number rather than a coded string.

### Module 3 Fieldbook (built)
```python
@dataclass(frozen=True)
class FieldbookSummaryDTO: id: str; field_id: str; field_code: str; farmer_id: str; crop: str; season_year: int; status: str; locked: bool; schema_version: str; steps_complete: int; steps_total: int; submitted_at: datetime | None; ready_for_pickup_at: datetime | None
@dataclass(frozen=True)
class CropClockDTO: crop: str; approach_day: int; ready_day: int; window_end_day: int
@dataclass(frozen=True)
class CropStatusDTO: field_id: str; season_year: int; status: str; label: str; days_after_sowing: int | None; sowing_date: date | None; overdue: bool; next_milestone: str
@dataclass(frozen=True)
class ReadyForPickupDTO: fieldbook_id: str; field_id: str; field_code: str; farmer_id: str; crop: str; season_year: int; entry_index: int; picking_number: str | int | None; estimated_kg: float | None; ready_for_pickup_at: datetime | None
@dataclass(frozen=True)
class TimelineEventDTO: at: datetime; step_key: str | None; kind: str; summary: str; officer_id: str | None
@dataclass(frozen=True)
class EstimatedYieldDTO: field_id: str; season_year: int; crop: str; estimated_kg: float | None; seed_kg: float | None; straw_kg: float | None; yield_maunds_per_acre: float | None; area: float | None; area_unit: str

def has_fieldbook(session, field_id: str, season_year: int) -> bool
def get_fieldbook_summary(session, field_id: str, season_year: int) -> FieldbookSummaryDTO | None
def get_sowing_date(session, field_id: str, season_year: int) -> date | None
def get_crop_clock(session, crop: str) -> CropClockDTO | None
def get_crop_status(session, field_id: str, season_year: int, *, today: date | None = None) -> CropStatusDTO | None
def list_ready_for_pickup(session, *, crop: str | None = None, season_year: int | None = None, farmer_id: str | None = None) -> list[ReadyForPickupDTO]
def get_activity_timeline(session, field_id: str, season_year: int) -> list[TimelineEventDTO]
def get_estimated_yield(session, field_id: str, season_year: int) -> EstimatedYieldDTO | None
def is_submitted(session, field_id: str) -> bool   # any season; used by the guards

# Added for Module 4 (D-059): a fixed number of queries for any number of pairs.
@dataclass(frozen=True)
class FieldCropFactsDTO: field_id: str; season_year: int; fieldbook_id: str | None; fieldbook_status: str | None; crop: str | None; sowing_date: date | None; days_after_sowing: int | None; harvested: bool; ready_for_pickup: bool; ready_for_pickup_at: datetime | None; estimated_kg: float | None; status: str; overdue: bool; next_milestone: str
def get_crop_status_bulk(session, pairs: Sequence[tuple[str, int]], *, today: date | None = None) -> dict[tuple[str, int], FieldCropFactsDTO]
def get_crop_clocks(session) -> dict[str, CropClockDTO]
```

Crop status, from days after sowing (DAS) against `crop_clock_config`:
`no_sowing_data` (no sowing date), `growing` (DAS < approach), `approaching`
(approach <= DAS < ready), `ready` (ready <= DAS <= window end), `ready` with
`overdue=True` (past the window end), `harvested` (a harvest entry exists). The sowing
date is the cotton `sowing.sowing_date` or the hemp `sowing.drilling_date`. Soft-removed
drafts are invisible to every function.

### Module 4 Harvest Radar (built)
```python
@dataclass(frozen=True)
class PickupRequestDTO: id: str; request_no: str; field_id: str; field_code: str; farmer_id: str; crop: str; season_year: int; status: str; estimated_quantity_kg: float | None; quantity_is_estimate: bool; preferred_date: date | None; note: str | None; requested_by: str | None; requested_at: datetime; cancelled_at: datetime | None; cancel_reason: str | None; delivery_id: str | None
@dataclass(frozen=True)
class FieldReadinessDTO: field_id: str; field_code: str; farmer_id: str; crop: str; season_year: int; status: str; status_label: str; overdue: bool; sowing_date: date | None; days_after_sowing: int | None; expected_ready: date | None; next_milestone: str; estimated_kg: float | None; estimate_is_benchmark: bool; pickup_state: str
@dataclass(frozen=True)
class RadarQuery: crop: str = "cotton"; season_year: int | None = None; district: str | None = None; county: str | None = None; field_office_id: str | None = None; officer_id: str | None = None; pickup: str | None = None
@dataclass(frozen=True)
class RadarSummaryDTO: crop: str; season_year: int; area_unit: str; buckets: dict[str, int]; ready_now: RadarTotalsDTO; approaching_soon: RadarTotalsDTO; pickup_requested: RadarTotalsDTO; overdue: RadarTotalsDTO

def list_open_pickup_requests(session, *, crop: str | None = None, season_year: int | None = None) -> list[PickupRequestDTO]
def get_pickup_request(session, request_id: str) -> PickupRequestDTO | None
def mark_pickup_scheduled(session, request_id: str, delivery_id: str) -> PickupRequestDTO
def mark_pickup_fulfilled(session, request_id: str) -> PickupRequestDTO
def mark_pickup_cancelled(session, request_id: str, reason: str, *, officer_id: str | None = None) -> PickupRequestDTO
def get_radar_summary(session, query: RadarQuery | None = None) -> RadarSummaryDTO
def count_fields_by_status(session, query: RadarQuery | None = None) -> dict[str, int]
def get_field_readiness(session, field_id: str, season_year: int | None = None) -> FieldReadinessDTO | None
```

The `mark_*` functions change state in the caller's transaction and do not commit.
Pickup state shown on the radar: `not_requested`, `requested`, `scheduled`, `delivered`
(from `fulfilled`).

Readiness (the only implementation is `module_4/services/readiness.py`): Ready for pickup
= Yes in the fieldbook gives `ready`; otherwise a picking (cotton) or a cutting or baling
(hemp) gives `harvested`; otherwise no fieldbook or no sowing date gives
`no_sowing_data`; otherwise days after sowing below the approach day is `growing`, below
the ready day `approaching`, else `ready`. Overdue is a flag: not harvested and days
after sowing above the window end. Expected ready = sowing date + ready day.

### Module 5 Deliveries (built)
```python
@dataclass(frozen=True)
class DeliveryDTO: id: str; delivery_no: str; pickup_request_id: str; farmer_id: str; field_id: str; field_code: str; crop: str; season_year: int; status: str; site_id: str; heap_id: str | None; scheduled_date: date; vehicle_no: str; driver_name: str; dispatched_at: datetime | None; delivered_at: datetime | None; estimated_quantity_kg: float | None; field_weight_kg: float | None; weighbridge_weight_kg: float | None; moisture_pct: float | None; variance_pct: float | None; variance_level: str | None
@dataclass(frozen=True)
class DeliveryQuery: crop: str | None = None; status: str | None = None; site_id: str | None = None; heap_id: str | None = None; farmer_id: str | None = None

def list_deliveries(session, query: DeliveryQuery | None = None) -> list[DeliveryDTO]
def get_delivery(session, delivery_id: str) -> DeliveryDTO | None
def list_delivered_unassigned(session, site_id: str, crop: str) -> list[DeliveryDTO]
def assign_heap(session, delivery_id: str, heap_id: str, officer_id: str | None, *, site_id: str, crop: str) -> DeliveryDTO
def unassign_heap(session, delivery_id: str, officer_id: str | None, reason: str) -> DeliveryDTO   # asks delivery.can_unassign
def list_by_heap(session, heap_id: str) -> list[DeliveryDTO]
def get_delivery_stats(session, query: DeliveryQuery | None = None) -> DeliveryStatsDTO   # total, by_status, delivered_kg, delivered_maunds, weight_flags
def get_farmer_delivery_summary(session, farmer_id: str) -> FarmerDeliverySummaryDTO   # deliveries, delivered, delivered_kg, fields, heaps
def receive_at_gate(session, delivery_id, officer_id, *, gross_weight_kg, tare_weight_kg, moisture_pct, note=None) -> tuple[DeliveryDTO, list[str]]
def cancel_at_gate(session, delivery_id, officer_id, reason) -> DeliveryDTO
```
`assign_heap`, `unassign_heap`, `receive_at_gate` and `cancel_at_gate` change state in the
caller's transaction (no commit). `assign_heap` accepts only a delivered delivery without
a heap, at the heap's site and crop (`delivery_not_delivered`, `delivery_already_assigned`,
`delivery_wrong_site`, `delivery_wrong_crop`). `receive_at_gate` records the net weight
(gross minus tare) through the same receipt rules as `POST /deliveries/{id}/receive`,
including the flagged-variance note; Module 9 commits.

### Module 6 Heap (built)
```python
@dataclass(frozen=True)
class HeapDTO: id: str; heap_id: str; site_id: str; crop: str; kind: str; status: str; opened_at: datetime; closed_at: datetime | None; outturn_ratio_pct: float; bale_unit_kg: float; shiv_pct: float | None; dust_pct: float | None
@dataclass(frozen=True)
class BaleDTO: id: str; bale_serial: str; heap_id: str; seq: int; weight_kg: float; status: str; created_at: datetime; voided_at: datetime | None; void_reason: str | None

def get_heap(session, heap_id: str) -> HeapDTO | None                 # business ID or key
def list_heaps(session, query: HeapQuery | None = None) -> list[HeapDTO]  # crop, site_id, status
def list_open_heaps(session, site_id: str) -> list[HeapDTO]
def get_heap_totals(session, heap_id: str) -> HeapTotalsDTO | None    # input, expected output, max and made bales, remaining, can_close, shiv, dust
def list_bales(session, heap_id: str, *, include_voided: bool = False) -> list[BaleDTO]
def get_bale(session, serial: str) -> BaleDTO | None
def get_heap_lineage(session, heap_id: str) -> HeapLineageDTO | None  # farmers (kg, pct) -> fields (fieldbook, sowing date, delivery numbers, kg)
def get_site_inventory_summary(session, site_id: str) -> SiteInventoryDTO   # open and closed heaps, pending deliveries and kg, input, bales
```
Lineage is built only from the public APIs of Modules 2, 3 and 5.

### Module 7 QR Tracing (built)
```python
@dataclass(frozen=True)
class QrTokenDTO: token; token_type; bale_serial; heap_id; status; trace_url; label_print_count; created_at
@dataclass(frozen=True)
class ScanSummaryDTO: total; public; internal; last_scan_at
@dataclass(frozen=True)
class TokenQuery: heap_id: str | None = None; token_type: str | None = None

def get_token_for_bale(session, serial) -> QrTokenDTO | None          # the active code
def get_trace_for_token(session, token, *, public=True) -> dict | None # None when unknown or revoked
def get_scan_summary(session, query: TokenQuery | None = None) -> ScanSummaryDTO
def count_active_tokens(session, query: TokenQuery | None = None) -> int
```
`get_trace_for_token(public=False)` returns the internal chain as the administrator sees
it; callers must not show that to the public.

### Module 9 Gate Reception (built)
```python
@dataclass(frozen=True)
class GateEntryDTO: id; delivery_id; delivery_no; site_id; crop; status; arrived_at; net_weight_kg; moisture_pct; accepted_at; rejected_at; rejection_reason

def get_entry_for_delivery(session, delivery_id: str) -> GateEntryDTO | None   # whatever its status
def pending_count(session, site_id: str) -> int                               # loads waiting at the gate
```
Reads only. Every write goes through Module 9's router, which owns the transaction.

### Functions added for Module 1 (D-096)
All compute in SQL or from the module's own cached dataset, with a fixed number of
queries whatever the size of the database.

```python
# Module 2
def get_registration_totals(session, *, registered_by=None) -> RegistrationTotalsDTO  # farmers and fields by crop, areas in acres and hectares, farmers without a field
def count_farmers_without_field(session, *, crop=None, registered_by=None) -> int
def list_farmers_without_field(session, *, crop=None, registered_by=None, limit=5) -> list[FarmerRefDTO]
def registration_times(session, *, crop=None, registered_by=None, since=None, until=None) -> list[datetime]
def field_mapped_times(session, *, crop=None, registered_by=None, since=None, until=None) -> list[datetime]
def area_by_region(session, *, crop, registered_by=None, limit=8) -> list[RegionAreaDTO]   # district (cotton) or county (hemp)
def registrations_by_officer(session, *, crop=None) -> dict[str, OfficerRegistrationsDTO]

# Module 3
def count_fieldbooks_by_status(session, *, crop=None, season_year=None) -> dict[str, int]   # draft, submitted
def count_submitted_by_officer(session, *, crop=None, season_year=None) -> dict[str, int]
def count_step_completion(session, *, crop, season_year=None) -> list[StepCompletionDTO]   # in the form's order
def list_stale_drafts(session, *, updated_before, crop=None, season_year=None) -> list[StaleDraftDTO]
def list_licence_expiries(session, *, season_year=None) -> list[LicenceExpiryDTO]          # hemp field_info.licence_expiry

# Module 4
STATUSES, STATUS_LABELS, STATUS_READY, STATUS_HARVESTED, PICKUP_ALL, PICKUP_NOT_REQUESTED  # vocabulary re-exported
def list_readiness_rows(session, *, crop, season_year=None, officer_id=None, include_geometry=False) -> list[ReadinessRowDTO]
#   the radar's own dataset (cached 30 s), with fieldbook status and ready_since; reconciles with Radar by construction

# Module 5 (DeliveryQuery gains statuses, season_year, date_from, date_to, delivered_from, delivered_to, farmer_ids, variance_level, limit)
def get_delivery_totals(session, query=None) -> DeliveryTotalsDTO   # status counts, delivered, kg, maunds, average moisture, flags
def count_deliveries(session, query=None) -> int
def delivered_rows_in_range(session, *, crop=None, farmer_ids=None, season_year=None, delivered_from=None, delivered_to=None) -> list[tuple[datetime, float, float | None]]
def delivered_totals_by_heap(session, *, crop=None) -> dict[str, tuple[int, float, datetime | None]]

# Module 6
def list_heap_activity(session, *, crop=None, site_id=None) -> list[HeapActivityDTO]   # utilisation and last_activity_at
def get_programme_heap_summary(session, *, crop=None, site_id=None) -> ProgrammeHeapSummaryDTO
def count_bales(session, *, crop=None, site_id=None, since=None, until=None) -> int
def list_heap_ids(session, *, crop=None, site_id=None) -> list[str]

# Module 7
def get_scan_totals(session, *, crop=None, since=None, until=None) -> ScanTotalsDTO   # total, public, internal, last scan, live codes
```

Officer-scoped id lists are chunked (at most 500 per `IN`), so scoping stays inside
SQLite's parameter limit.

### Functions added for Module 8 (D-117)

Configuration belongs to the module whose rules use it. Settings never writes another
module's table: it calls these, which validate, audit, bump a version and let Settings
commit. `expected_version` is the version the screen loaded; a mismatch raises
`ConflictError` with code `stale_version` rather than overwriting another
administrator's change.

```python
# Module 1 (alert thresholds; each value is a settings key written through the
# Settings values API, so there is no update_config here)
CONFIG_KEY, KEYS                                   # setting key -> the constant it defaults to
def get_config(session=None) -> dict               # { key, version, values, defaults }
def ready_without_pickup_days(session=None) -> int
def heap_idle_days(session=None) -> int
def draft_fieldbook_idle_days(session=None) -> int
def licence_expiry_warning_days(session=None) -> int
def dispatch_grace_days(session=None) -> int

# Module 3 (crop clock)
def get_config(session) -> dict                                   # { key, version, crops: {crop: {approach_day, ready_day, window_end_day}} }
def update_config(session, values, officer_id, expected_version=None) -> dict
def preview_config_change(session, values) -> dict                # { fields_examined, fields_moving, before, after, moves }

# Module 5 (delivery tolerances)
def get_config(session) -> dict                                   # { key, version, crops: {crop: {variance_warn_pct, variance_flag_pct, moisture_warn_pct}} }
def update_config(session, values, officer_id, expected_version=None) -> dict

# Module 6 (heap and batch defaults; an open heap keeps the values it froze when opened)
def get_config(session) -> dict                                   # { key, version, crops: {crop: {default_outturn_ratio_pct, default_bale_unit_kg, default_shiv_pct, default_dust_pct}} }
def update_config(session, values, officer_id, expected_version=None) -> dict

# Module 2 (locations are stored on the farmer, so a rename has to move them)
def count_farmers_at_location(session, column, name) -> int
def replace_location_value(session, column, old, new, officer_id) -> int   # one transaction, audited
```

### Module 1 Dashboard
Beyond the alert thresholds above, it exposes no public API; it only reads the
functions of other modules. It subscribes to every event in `KNOWN_EVENTS` to drop its
cache, and publishes none.

### Module 8 Settings (built)

```python
def get_public_config(session=None) -> dict          # tiles, QR base URL, programme labels; no secret
def get_setting(key, session=None) -> Any            # database override, then .env, then default
def get_officer_preferences(session, officer_id) -> dict
def list_active_officers(session, office_id=None) -> list[dict]
def is_maintenance_mode() -> bool                    # True while a restore replaces the database
def maintenance_reason() -> str
```

A module that needs one configurable number calls `core.app_settings.get_setting`
directly instead, so nothing has to import Module 8 to read a value.

## 5. Frontend contracts

* `src/core/api/client.ts` is the only place that calls `fetch`. It sends `X-Officer-Id`
  and turns every failure into `ApiError { status, code, message, details, fieldErrors }`.
* `useMasterList(listKey, { country, crop })` is the only source of dropdown options.
* A module is imported only through its `index.ts` (enforced by ESLint
  `no-restricted-imports`), which exports `meta` and the default page component, plus any
  read-only API a screen of another module needs (Module 3's fieldbook lists, Module 8's
  staff list, Module 1's notifications).

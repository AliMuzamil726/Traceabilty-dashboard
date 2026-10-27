# SAWIE data model

This is the single source of truth for every table the product will have. Prompt 1
built the shared tables (marked **built**); every other table is **planned** and is
created by the prompt that builds its owning module, using exactly these names,
columns and relations.

## Conventions (all tables)

| Rule | Detail |
| --- | --- |
| Primary keys | `id` is a string UUID (`String(36)`). The API never assumes integer keys. |
| Business IDs | Human-readable IDs (`sawie_id`, `field_id`, ...) are separate unique columns, allocated by `core.ids` counters. |
| Timestamps | `created_at`, `updated_at` on every mutable table, stored in UTC via `UTCDateTime`; the API returns ISO 8601 with offset. |
| Actors | `created_by`, `updated_by` hold officer ids on every table written by officers. |
| Geometry | GeoJSON in a JSON column plus `bbox_min_lng`, `bbox_min_lat`, `bbox_max_lng`, `bbox_max_lat` float columns for viewport queries. No PostGIS yet. |
| Units | Stored in SI: area in square metres (`area_m2`), mass in kilograms (`*_kg`). Display units (acres, maunds, hectares, tonnes) are a frontend concern. |
| Soft delete | Tables that need it have `deleted_at` (nullable) and `deleted_by`. Queries exclude soft-deleted rows by default. |
| Country / crop | `country` is ISO 3166-1 alpha-2 (`PK`, `GB`). `crop` is `cotton` or `hemp`. Cotton implies PK, hemp implies GB in this phase. |
| Dropdown values | Columns fed by a dropdown store the master-list `value` (stable code), never the label. |
| Portability | Portable SQLAlchemy types only, so `DATABASE_URL` alone switches SQLite to Supabase Postgres. |

## Relationship chain

```
field_offices 1--* officers
                     | (created_by on everything)
farmers 1--* farmer_season_profiles
farmers 1--* fields 1--* fieldbooks 1--* fieldbook_entries
                              |     1--* fieldbook_step_status
                              |     1--* fieldbook_photos
                              |
                     (ready for pickup, seen by Harvest Radar)
                              |
pickup_requests 1--* deliveries *--1 sites (ginner or processor)
                              |
deliveries *--1 heaps   (deliveries.heap_id holds the heap's business ID)
heaps *--1 sites
heaps 1--* bales 1--1 qr_tokens 1--* qr_scan_log
```

A QR scan resolves `qr_tokens -> bales -> heaps -> deliveries -> fields -> farmers`.

## Ownership

| Owner | Tables |
| --- | --- |
| shared (built) | `officers`, `field_offices`, `master_lists`, `locations`, `audit_log`, `id_counters`, `sites` |
| Module 2 Register Farmer (built) | `farmers`, `farmer_season_profiles`, `fields`, `uk_postcode_cache` |
| Module 3 Fieldbook | `fieldbooks`, `fieldbook_entries`, `fieldbook_step_status`, `fieldbook_photos`, `crop_clock_config` |
| Module 4 Harvest Radar | `pickup_requests` |
| Module 5 Deliveries | `deliveries`, `delivery_status_history`, `delivery_config` |
| Module 6 Heap | `heaps`, `bales`, `heap_config` |
| Module 7 QR Tracing | `qr_tokens`, `qr_scan_log` |
| Module 1 Dashboard | none (reads through other modules' `public_api`) |
| Module 8 Settings (built) | `settings_history`, `officer_preferences`, `backups` (and `app_settings`, which lives in shared so `core.app_settings` can read it for every module, D-116) |

Only the owner writes its tables. Other modules read them through the owner's
`public_api.py` and react to changes through events.

Settings is the one module that edits data it does not own, and it does so through the
owner rather than the table: the shared reference tables through
`shared/repositories/`, and `crop_clock_config`, `delivery_config` and `heap_config`
only through Module 3, 5 and 6's `get_config` / `update_config` (D-117).

## Shared tables (built)

### `field_offices`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| code | str(32) unique | e.g. `PK-MUL` |
| name | str(120) | e.g. `Multan Field Office` |
| country | str(2) | indexed |
| province, district | str(120) null | display text |
| location_id | FK `locations.id` null | most specific location |
| is_dummy | bool | true for seeded placeholder offices |
| active | bool | |
| created_at, updated_at, created_by, updated_by | | |

### `officers`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | seeded rows use UUID5 of `code` (stable across resets) |
| code | str(32) unique | e.g. `PK-MUL-01`, `ADMIN-01` |
| full_name | str(120) | |
| email, phone | str null | |
| role | str(16) | `officer` or `admin` |
| country | str(2) | indexed |
| field_office_id | FK `field_offices.id` null | null for admins |
| is_dummy, active | bool | |
| created_at, updated_at, created_by, updated_by | | |

### `master_lists`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| list_key | str(64) | e.g. `country`, `crop`; later `tenure`, `variety`, ... |
| value | str(64) | stable code stored in business tables |
| label | str(160) | English display text |
| sort_order | int | |
| country | str(2) null | scope; null = all countries |
| crop | str(32) null | scope; null = all crops |
| active | bool | inactive options are hidden but old data keeps its value |
| created_at, updated_at, created_by, updated_by | | |

Index `(list_key, country, crop)`. Uniqueness of `(list_key, value, country, crop)` is
enforced in the repository (NULL scopes defeat SQL unique indexes).
Seeded now: `country` (PK, GB) and `crop` (cotton scoped to PK, hemp scoped to GB).

### `locations`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| country | str(2) | |
| level | str(16) | `province`, `district`, `tehsil` |
| code | str(64) unique | e.g. `PK-PB-MUL` |
| name | str(120) | |
| parent_id | FK `locations.id` null | |
| sort_order, active | | |
| created_at, updated_at | | |

UK mapping of the three levels: region, county, local authority district.

Seeded by Module 2 (`scripts/seed_data/locations_pk.json`, marked as seed data to be
verified): all 7 Pakistani provinces and territories, all 158 districts (36 in Punjab),
and tehsils for the cotton-belt districts of Punjab and Sindh. Districts with no seeded
tehsils are expected: the form always offers "Other (type manually)". Villages are
deliberately never seeded.

### `audit_log`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| entity | str(64) | e.g. `farmer`, `field`, `delivery` |
| entity_id | str(64) | |
| action | str(32) | `create`, `update`, `delete`, `state_change` |
| officer_id | str null | indexed |
| diff | JSON | `{field: {"from": old, "to": new}}` |
| request_id | str null | correlates with logs |
| created_at | UTC | |

### `id_counters`
| Column | Type | Notes |
| --- | --- | --- |
| key | str(64) PK | e.g. `sawie_id:PK` |
| value | bigint | last issued number |
| updated_at | UTC | |

Planned counter keys and formats:

| Key | Format | Example | Status |
| --- | --- | --- | --- |
| `sawie_id` | `{1000 + n}` | `1001` | built |
| `field_id:{sawie_id}` | `{sawie_id}-{n:02}` | `1001-03` | built |
| `delivery_id:{year}` | `DLV-{year}-{n:06}` | `DLV-2026-000042` | planned |
| `heap_id:{country}:{year}` | cotton `HEP-PK-{year}-{n:04}`, hemp `BAT-GB-{year}-{n:04}` | `HEP-PK-2026-0003` | planned |
| `bale_id:{heap_id}` | `{heap_id}-B{n:03}` | `HEP-PK-2026-0003-B014` | planned |

The SAWIE ID is a plain number with no country or crop in it, counted once across both
programmes and starting at 1001 (`core.ids` counts from 1, so `module_2.services.ids`
adds a base of 1000). One person keeps one SAWIE ID for life, so nothing inside it can
go stale. The field ID is counted per farmer, which is why reading `1001-03` tells an
officer whose field it is; a deleted field's number is never reissued because the
counter is never rewound. See DECISIONS D-027.

## Module 2: Register Farmer (built)

Personal data (permanent) and crop data (per season) are deliberately separate, so a
farmer who comes back next season gets a new season profile rather than a duplicate
record. The uniqueness key for a person is `farmers.id_number_norm`.

### `farmers`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| sawie_id | int unique, indexed | allocated on registration, never reissued |
| crop | str(16) | `cotton` or `hemp`; decides country, form and lists |
| country | str(2) | derived from crop (cotton PK, hemp GB) |
| id_number_norm | str(64) unique | digits for a CNIC, upper-case alphanumerics for a hemp ID; the identity key |
| id_number_display | str(64) | as the officer reads it (`12345-1234567-1`) |
| name | str(60) | title-cased on save |
| father_name | str(60) null | cotton only |
| farm_name | str(80) null | hemp only |
| phone_norm | str(20) null | E.164 (`+923001234567`) |
| phone_display | str(24) null | local form (`0300-1234567`, `07700 900123`) |
| province, district, tehsil | str(120) null | cotton; names as entered, since a tehsil may be typed |
| village | str(120) null | cotton; typed by the officer, never seeded |
| location_id | FK `locations.id` null | most specific seeded location chosen; null when the tehsil was typed |
| home_office_licence_no | str(30) unique null | hemp |
| postcode_norm | str(10) null | hemp, `LN4 3QP` (upper case, one space) |
| county, region | str(120) null | hemp; from the postcode lookup, or typed only when it failed |
| field_office_id | FK `field_offices.id` | registering office; must be in the farmer's country |
| registered_by | str(36) null | officer who first registered this farmer; never changes |
| created_at, updated_at, created_by, updated_by | | |

Indexes: `(crop, field_office_id)`, `registered_by`, `name`, `(tehsil, village)`.

### `farmer_season_profiles`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| farmer_id | FK `farmers.id` | cascade delete |
| season_year | int | defaults to the current year |
| variety | str(64) | master list `variety`, scoped by crop |
| tenure | str(32) | master list `tenure`, scoped by crop |
| previous_crop | str(64) null | master list `previous_crop`, scoped by country |
| notes | text null | |
| created_at, updated_at, created_by, updated_by | | |

Unique `(farmer_id, season_year)`. A second registration in the same season updates
this row; a registration in a new season adds one.

### `fields`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| field_id | str(32) unique | business ID `{sawie_id}-{nn}` |
| farmer_id | FK `farmers.id` | cascade delete |
| geometry | JSON (JSONB on Postgres) | single-ring GeoJSON Polygon, WGS84 |
| bbox_min_lat, bbox_min_lng, bbox_max_lat, bbox_max_lng | float | indexed together; the overlap prefilter |
| pin_lat, pin_lng | float | representative point, or a pin inside or within 50 m of the boundary |
| vertex_count | int | distinct corners, at most 500 |
| area_m2, area_acre, area_ha | float | computed server-side in the centroid's UTM zone |
| deleted_at, deleted_by | | soft delete, blocked by guard `field.can_delete` |
| created_at, updated_at, created_by, updated_by | | |

Indexes: `(bbox_min_lng, bbox_min_lat, bbox_max_lng, bbox_max_lat)`, `(farmer_id, deleted_at)`.

Geometry rules are enforced in `module_2/services/geometry.py`: a closed single ring,
at least 3 distinct corners, no self-intersection (rejected, never repaired), inside
the farmer's country, between 100 m2 and 500 ha, and no overlap beyond 0.01 m2 with any
other active field. Editing geometry is blocked by guard `field.can_edit_geometry`.

### `uk_postcode_cache`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| postcode_norm | str(10) unique | `LN4 3QP` |
| county, region | str(120) null | |
| source | str(32) | `postcodes_io` or `area_table` |
| fetched_at | UTC | |

The coarse fallback table of about 120 postcode areas is not a table in the database:
it ships as `backend/module_2/data/uk_postcode_areas.json` and is marked as seed data
still to be verified.

## Module 3: Fieldbook (built)

A fieldbook is one field's diary for one season. What each step asks is not in these
tables: it is in the crop's form definition (`backend/module_3/form_definitions/
cotton.json` and `hemp.json`), and `fieldbook_entries.data` holds the answers keyed by
the definition's field keys. Module 3 never joins Module 2's tables; `field_id` and
`farmer_id` are Module 2 UUIDs read through `module_2.public_api`.

### `fieldbooks`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| field_id | str(36) | Module 2 `fields.id` (no foreign key, see D-043) |
| field_code | str(32) | the readable field ID, e.g. `1001-01`, copied at creation |
| farmer_id | str(36) | Module 2 `farmers.id`, indexed |
| crop | str(16) | `cotton` or `hemp`, from the farmer; decides the definition |
| season_year | int | |
| status | str(16) | `draft` or `submitted` |
| current_step | str(64) null | the next step that is not done, for resuming |
| schema_version | str(16) | definition version the book was created with, e.g. `2026.1` |
| version | int | concurrency token, +1 on every write (see `X-Fieldbook-Version`) |
| locked | bool | true once submitted; every write is refused after that |
| submitted_at, submitted_by | UTC null, str null | |
| ready_for_pickup_at | UTC null | first time a harvest (cotton) or baling (hemp) entry said ready |
| deleted_at | UTC null | soft removal when the field is removed in Module 2 |
| created_at, updated_at, created_by, updated_by | | |

Unique `(field_id, season_year)`: one book per field per season (D-042).

### `fieldbook_entries`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| fieldbook_id | FK `fieldbooks.id` (cascade) | |
| step_key | str(64) | a step key from the definition |
| entry_index | int | 0 for single steps; 0..n for repeatable steps (not renumbered on delete) |
| data | JSON | cleaned answers: hidden fields dropped, computed fields filled |
| completed | bool | |
| updated_by | str(36) null | |
| created_at, updated_at | | |

Unique `(fieldbook_id, step_key, entry_index)`.

### `fieldbook_step_status`
| Column | Type | Notes |
| --- | --- | --- |
| fieldbook_id | PK, FK `fieldbooks.id` (cascade) | |
| step_key | PK str(64) | |
| status | str(16) | `not_started`, `in_progress`, `complete` or `not_applicable` |
| updated_at, updated_by | | |

A single step is complete once saved; a repeatable step once it has one entry. A step
whose definition allows it can be `not_applicable` ("Nothing to record for this step").

### `fieldbook_photos`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| fieldbook_id | FK `fieldbooks.id` (cascade) | at most 8 per book |
| file_path, thumb_path | str(255) | relative to `UPLOAD_DIR`, under `uploads/fieldbook/{fieldbook_id}/` |
| original_name | str(255) | |
| mime | str(32) | `image/jpeg`, `image/png` or `image/webp`, from the content |
| size_bytes | int | at most 8 MB |
| width, height | int null | after EXIF orientation is applied |
| uploaded_by, uploaded_at | | |

### `crop_clock_config`
Owned by Module 3 (it computes crop status for its own editor); Harvest Radar reads it
through `module_3.public_api.get_crop_clock`. Seeded on startup.

| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| crop | str(16) unique | |
| approach_day | int | days after sowing when the crop starts approaching harvest |
| ready_day | int | days after sowing when it is ready |
| window_end_day | int | last day of the harvest window; later is "ready, overdue" |
| created_at, updated_at, created_by, updated_by | | |

Seed: cotton 120 / 135 / 200, hemp 80 / 95 / 125.

## Module 4: Harvest Radar (built)

Radar owns one table. Everything else it shows (status, days after sowing, expected
ready date, estimated quantity) is computed on each read from Module 2's
`list_field_sources` and Module 3's `get_crop_status_bulk` and `get_crop_clocks`, and
cached for 30 seconds.

### `pickup_requests`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| request_no | str(16) unique | `PR-0001`, from the `pickup_request` id counter |
| field_id | str(36) | Module 2 field id (no foreign key, as in Module 3) |
| field_code | str(32) | readable field ID, copied at creation |
| farmer_id | str(36) | indexed |
| crop | str(16) | |
| season_year | int | |
| status | str(16) | `requested`, `scheduled`, `fulfilled` or `cancelled` |
| estimated_quantity_kg | float null | from the fieldbook yield, or the crop benchmark |
| quantity_is_estimate | bool | true when the benchmark was used |
| preferred_date | date null | |
| note | text null | at most 1000 characters |
| requested_by, requested_at | | |
| cancelled_by, cancelled_at, cancel_reason | null | |
| delivery_id | str(36) null | set by Module 5 through `mark_pickup_scheduled` |
| updated_at | UTC | |

Partial unique index `uq_pickup_open_per_field_season` on `(field_id, season_year)`
where `status IN ('requested', 'scheduled')`: at most one open request per field and
season. The service checks the same rule first inside its transaction.

## Shared: `sites` (built with Module 5)

Shared because Deliveries, Heap and QR Tracing all point at it. Read through
`GET /api/v1/sites?crop=`. Seeded with dummy sites marked `is_dummy`.

| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | stable UUID5 of the code |
| code | str(32) unique | for example `BWP-G1`, `UK-P1`; also the prefix of heap IDs |
| name | str(120) | |
| type | str(16) | `ginner` (cotton) or `processor` (hemp) |
| crop | str(16) | a delivery's crop must match its site's |
| country | str(2) | decides how the driver's phone is checked |
| address, region | null | |
| is_dummy, active | bool | |
| created_at, updated_at, created_by, updated_by | | |

Seed: ginners `BWP-G1`, `BWP-G2`, `BWP-G3` (Bahawalpur) and `MUX-G1` (Multan) for
cotton; processors `UK-P1` (Norfolk) and `UK-P2` (Lincolnshire) for hemp.

## Module 5: Deliveries (built)

All weights are kilograms; cotton screens also show maunds (1 maund = 40 kg).

### `deliveries`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| delivery_no | str(16) unique | `DL-0001`, from the `delivery` id counter |
| pickup_request_id | str(36) | Module 4 request it fulfils |
| farmer_id, field_id | str(36) | Module 2 ids (no foreign key) |
| field_code | str(32) | readable field ID, copied at scheduling |
| crop, season_year | | from the request |
| status | str(16) | `scheduled`, `in_transit`, `delivered`, `cancelled` |
| site_id | FK `sites.id` | same crop as the delivery |
| heap_id | str(32) null | the heap's business ID (for example `BWP-G1-H01`), set by Module 6 |
| scheduled_date | date | today or later when scheduled |
| driver_name, driver_phone, vehicle_no | | phone stored as E.164; vehicle uppercased |
| dispatched_at, delivered_at | UTC null | |
| estimated_quantity_kg | float null | from the pickup request |
| field_weight_kg | float null | optional, at dispatch |
| weighbridge_weight_kg | float null | at the gate, above 0 |
| moisture_pct | float null | 0 to 100 |
| variance_kg, variance_pct, variance_level | null | against the field weight, else the estimate; level `ok`, `warn`, `flag` |
| note, cancel_reason | text null | |
| created_by, updated_by, created_at, updated_at | | |

### `delivery_status_history`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| delivery_id | FK `deliveries.id` (cascade) | |
| from_status | str(16) null | null for the first row |
| to_status | str(16) | a correction is a row from `delivered` to `delivered` |
| officer_id | str(36) null | |
| at | UTC | |
| note | text null | |

### `delivery_config`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| crop | str(16) unique | |
| variance_warn_pct | float | default 3 |
| variance_flag_pct | float | default 5 |
| moisture_warn_pct | float | cotton 12, hemp 16 |

Seeded at startup; existing rows are never overwritten.

## Module 6: Heap (built)

A heap (cotton, at a ginner) or batch (hemp, at a processor). Deliveries join a heap
through `deliveries.heap_id` (owned by Module 5, set through its public API), so there is
no separate link table.

### `heaps`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| heap_id | str(32) unique | site code, `-H` (cotton) or `-BT` (hemp), 2-digit per-site counter: `BWP-G1-H01`, `UK-P1-BT01` |
| site_id | FK `sites.id` | one site and one crop per heap |
| crop | str(16) | from the site |
| status | str(8) | `open` or `closed` |
| opened_at, opened_by, closed_at, closed_by | | |
| close_reason | text null | required with a remainder or with no bales |
| outturn_ratio_pct, bale_unit_kg | float | copied from `heap_config` at opening; frozen once the first bale exists |
| shiv_pct, dust_pct | float null | hemp only |
| note | text null | |
| created_at, updated_at, created_by, updated_by | | |

The per-site counter lives in `id_counters` under `heap:{site code}`.

### `bales`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| bale_serial | str(48) unique | `{heap_id}-001`, sequential per heap, never reused after a void |
| heap_pk | FK `heaps.id` (cascade) | |
| seq | int | unique per heap |
| weight_kg | float | the heap's bale unit |
| status | str(8) | `active` or `voided` |
| void_reason, voided_by, voided_at | null | |
| created_by, created_at | | |

### `heap_config`
| Column | Type | Notes |
| --- | --- | --- |
| crop | str(16) unique | |
| default_outturn_ratio_pct | float | cotton 34, hemp 25 |
| default_bale_unit_kg | float | cotton 170, hemp 250 |
| default_shiv_pct, default_dust_pct | float null | hemp 55 and 15 |

Seed values are placeholders to confirm with the business; editable later in Settings.

## Module 7: QR Tracing (built)

Codes are issued from events (`heap.opened`, `bale.created`), never typed in. Heaps and
bales are referenced by their business IDs (`heap_id`, `bale_serial`), the identifiers the
events carry; Module 7 never writes to another module's tables.

### `qr_tokens`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| token | str(16) unique | 12 characters of RFC 4648 base32 (`A-Z`, `2-7`) from `secrets`; about 60 bits, never derived from a serial |
| token_type | str(8) | `bale` or `heap` (a heap code also stands for a hemp batch) |
| bale_serial | str(48) null, indexed | set for bale codes |
| heap_id | str(32), indexed | business ID of the heap or batch, for both types |
| status | str(8) | `active` or `revoked`. At most one active code per bale or heap (enforced in the service) |
| created_by, created_at | | `created_by` is the officer behind the event |
| revoked_by, revoked_at, revoke_reason | null | set by a revoke, a regenerate or a bale being voided |
| label_print_count | int | label sheets and label PNGs that included this code |
| last_printed_at | UTC null | |

The trace link is not stored: it is built as `{PUBLIC_BASE_URL}/trace/{token}` when needed,
so correcting the base URL fixes every code already printed.

### `qr_scan_log`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| token_id | FK `qr_tokens.id`, indexed | |
| scanned_at | UTC | |
| channel | str(8) | `public` (the scan page) or `internal` (Find a code) |
| ip_hash | str(64) null | SHA-256 of `QR_IP_SALT` + address; never the address |
| user_agent_family | str(32) null | a coarse family such as `Safari mobile`, never the full string |

## Module 8: Settings (built)

### `app_settings` (shared folder, Module 8 is the only writer)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | |
| `key` | text, unique | A key declared in `module_8/registry.py`; an unknown key is refused |
| `value` | JSON | Whatever the declaration says the type is |
| `version` | int | Bumped on every write; a save sends the version it loaded |
| `created_by`, `updated_by` | uuid | Officer |
| `created_at`, `updated_at` | timestamp | |

A row exists only where an administrator has overridden something. With no row, the
value comes from `.env` and then the declared default, so a fresh install behaves
exactly as it did before any of this was configurable.

### `settings_history`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | |
| `key` | text, indexed with `changed_at` | Setting or config block |
| `old_value`, `new_value` | JSON | |
| `changed_by` | uuid | Officer |
| `changed_at` | timestamp | |
| `reason` | text, nullable | What the administrator typed |

Append-only. Restoring a previous value writes a new row rather than removing one.

### `officer_preferences`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | |
| `officer_id` | uuid, unique, cascade | One row per officer |
| `sidebar_collapsed` | bool | |
| `table_density` | text | `comfortable` or `compact` |
| `default_crop` | text, nullable | Null means every crop |

### `backups`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | |
| `filename` | text, unique | The file in `backend/backups/` |
| `size_bytes` | bigint | |
| `created_by` | uuid | Officer |
| `created_at` | timestamp | |
| `note` | text, nullable | |
| `kind` | text | `manual`, or `safety` for the copy taken before a restore |

The index, not the backup: the file on disk is the backup. A row whose file has gone is
listed and marked rather than hidden.

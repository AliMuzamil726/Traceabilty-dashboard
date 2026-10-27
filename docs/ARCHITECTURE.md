# SAWIE architecture

## 1. System overview

```
 Browser (React SPA, port 5173)
   |  /api/*  (Vite dev proxy)
   v
 FastAPI app (Uvicorn, 127.0.0.1:8000)
   app/        composition root: create_app, lifespan, explicit module registry
   core/       config, database, errors, events, guards, ids, audit, logging, pagination, deps
   shared/     officers, field offices, master lists, locations, audit log, id counters
   module_1..7 one package per product module (module_8 Settings: meta only)
   |
   v
 SQLAlchemy 2  ->  SQLite file backend/data/sawie.db   (later: Supabase Postgres)
```

The product is a modular monolith: one deployable backend and one SPA, split into
eight modules with hard boundaries that are checked by tests.

## 2. Backend layering

Inside every module:

```
router.py      HTTP only: parse input, call a service, shape the response
   |
services.py    business rules, transactions (commit), events, guards, audit
               (a built module may use a services/ package instead; Modules 2 to 6 do)
   |
repository.py  the only code that builds SQL for this module's tables
   |
models.py      SQLAlchemy tables owned by this module
schemas.py     Pydantic request/response models
public_api.py  the only file other modules may import (returns DTOs)
events.py      PUBLISHES list + register(bus, guards) for subscriptions and guard checks
meta.py        number, name, folder, route prefix, API prefix, status, build order
tests/         module tests
```

Routers never receive a `Session`; they depend on a service (or, for shared reference
data, a repository) built from the request session.

### Import rules (enforced by `backend/tests/test_architecture.py`)

| Package | May import |
| --- | --- |
| `module_N` | stdlib, third-party, `core`, `shared`, `module_N.*`, `module_M.public_api` |
| `core` | stdlib, third-party, `shared.models` and `shared.repositories` (for IDs, audit and the officer dependency) |
| `shared` | stdlib, third-party, `core` |
| `app` | everything (composition root) |

`core`, `shared` and `scripts` never import any `module_*`. Modules never import `app`.

### Cross-module communication

1. **Public API**: `from module_2.public_api import get_field` returns a frozen DTO.
2. **Events**: `bus.publish("field.created", {...}, session=session)`; subscribers are
   registered at startup by `app.registry.register_event_handlers`.
3. **Guards**: an upstream owner asks downstream modules for permission
   (`guards.enforce("field.can_delete", field_id=..., session=...)`) without importing
   them. The caller passes its session so checks read inside its transaction (D-045).

### Transactions

`core.deps.get_db` opens a session per request and never commits. Service methods
that write call `session.commit()` themselves, so a failing commit becomes an error
response instead of a silent post-response failure. Event handlers run inside the
publisher's transaction; a handler failure rolls the whole unit of work back. Anything
uncommitted is rolled back when the session closes.

On SQLite every transaction starts with `BEGIN IMMEDIATE` (write lock up front, 30 s
busy timeout, WAL journal). That makes `core.ids` counters race-free. On Postgres the
same `UPDATE ... RETURNING` takes a row lock, so no code changes are needed.

### Officer context

No login yet. `core.deps.get_current_officer` reads `X-Officer-Id`:

* header present: the officer must exist (401 `officer_not_found`) and be active (403);
* header absent in development/test: the officer with `DEFAULT_OFFICER_CODE`;
* header absent in production: 401 `officer_required`.

`require_admin` builds on it. When login arrives, this dependency and the frontend
OfficerSwitcher are the only pieces that change.

### Startup sequence (`app/lifespan.py`)

1. Create `backend/data` and the upload folder.
2. Import every model (`app.registry.import_all_models`) and `create_all` tables.
3. Clear and register event handlers and guards for every module.
4. If `SEED_ON_START=true`, run the idempotent reference seed (it inserts only missing
   rows), then each module's own `seed.run(session)` (D-049).

Shutdown clears handlers and disposes the engine.

### Database portability

* Only `DATABASE_URL` selects the database. Relative SQLite paths resolve against `backend/`.
* Portable types only; geometry is GeoJSON in JSON plus four bbox floats.
* `UTCDateTime` rejects naive datetimes and always returns aware UTC values.
* String UUID primary keys. Seeded rows use UUID5 so their IDs survive a reset.
* Alembic is scaffolded (`backend/alembic.ini`, `backend/migrations/`) and wired to the
  settings and models. Until the move to Supabase, tables are created by `create_all`;
  the first Alembic revision will be the Supabase baseline.

## 3. Frontend architecture

```
src/
  app/            App, router, providers, moduleRegistry, layout (AppShell, Sidebar, Topbar, PageContainer)
  core/           api client and errors, query client, stores (officer, ui), hooks, utils
  design-system/  tokens.css, components, motion
  shared/         cross-module components (OfficerSwitcher, ModulePlaceholder, ErrorBoundary, NotFound, PipelineTracker)
  module_1..8/    index.ts, module.meta.ts, pages, components, hooks, api, store, types, tests
```

* **Routing**: `moduleRegistry.ts` lists all eight modules (number, name, icon, path,
  status, loader). `router.tsx` creates one lazy route per routable module, each wrapped
  in an ErrorBoundary and a Suspense skeleton, plus a NotFound catch-all. A module is
  mounted at `<path>/*` and owns the routes beneath it, so Module 2's own `<Routes>`
  holds its list, form, profile and field pages.
* **Server state**: TanStack Query. 4xx errors are not retried.
* **Client state**: Zustand. `officerStore` (persisted acting officer) and `uiStore`
  (persisted sidebar collapse, transient mobile drawer).
* **Forms**: react-hook-form + zod. Dropdown options come from `useMasterList`.
* **Isolation**: ESLint `no-restricted-imports` forbids `@/module_M/*` deep imports from
  another module; use `@/module_M` (its `index.ts`).
* **Motion**: Framer Motion inside `MotionConfig reducedMotion="user"`.
* **Maps**: Leaflet with Leaflet-Geoman for drawing and markercluster for clustering,
  all driven through a design-system toolbar. Their stylesheets are not imported:
  `src/design-system/map.css` vendors the layout rules with brand colours (DECISIONS
  D-034). Tile sources live in `src/module_2/map/tileLayers.ts`.
* **API base**: `VITE_API_BASE_URL` (default `/api`), proxied to port 8000 by Vite.

## 4. Module status

| No | Module | Status now | Build order |
| --- | --- | --- | --- |
| 1 | Dashboard | **active** (read only, owns no tables) | 7 |
| 2 | Register Farmer | **active** | 1 |
| 3 | Fieldbook | **active** | 2 |
| 4 | Harvest Radar | **active** | 3 |
| 5 | Deliveries | **active** | 4 |
| 6 | Heap | **active** | 5 |
| 7 | QR Tracing | **active** (plus the public page `/trace/:token`, outside the app shell) | 6 |
| 8 | Settings | deferred (meta only, disabled in the sidebar) | later |

When a module is built, set `STATUS = "active"` in `backend/module_N/meta.py` and
`status: 'active'` in `frontend/src/module_N/module.meta.ts`; the sidebar pill
disappears and the next placeholder by build order shows "In build".

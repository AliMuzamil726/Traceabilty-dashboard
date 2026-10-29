# Audit report

Independent final audit and hardening of SAWIE. The audit was first written when Modules 1
to 7 were built; Modules 8 (Settings) and 9 (Gate Reception) have since been completed and
are included in the current checks and counts below. No audit finding is still open.

## Summary

Fourteen findings were recorded. Four were High or Medium security and access issues found
by tests written for the audit (F-09 to F-12); two High dependency findings were cleared by
upgrades (F-01, F-02). Every Critical and High finding is fixed and has a regression test.
Nothing Critical was found. Two Low items are accepted with reasons.

Final gate, all green: backend pytest (whole suite, 940 tests), ruff, pip-audit (no known
vulnerabilities), frontend lint (zero warnings), typecheck, 266 frontend unit tests,
production build, colour audit. `npm audit --omit=dev` is clean; seven advisories remain in
Tailwind 3 build tooling only (F-03).

## Method

1. Static review: dependency audit, import boundaries, contracts against code, route
   protection, export paths, validators.
2. Clean-machine run: backend and frontend installed from the requirement files and lock
   file, built and tested. The Windows `.bat` launchers were NOT run here (the audit
   environment is Linux); the owner tests them on Windows. Recorded as untested.
3. End to end scenarios through the HTTP API (`backend/tests/test_scenarios.py`): the
   cotton chain with a 6 percent weighbridge variance, double receive refused, cross
   officer field deletion refused, hemp registration with the offline postcode fallback.
   Re-registration and the guards on edit and delete are covered by the module suites.
4. Loophole checklist, with new tests in `backend/tests/test_audit_security.py`: CSV
   injection, cross officer reads and writes, identity header in production, error
   bodies without stack traces, CORS, uploads, the public trace page, Unicode digits.
5. Fix, prove, document: each fix has a test and a decision (D-109 to D-114).

## Findings

| ID | Area | Severity | Finding | Fix | Proof | Status |
|---|---|---|---|---|---|---|
| F-01 | Dependencies | High | 83 known vulnerabilities in Starlette 0.48 (via FastAPI <0.120), Pillow 11 and pytest 8 | requirements.txt: fastapi 0.161, Pillow 13, pytest 9; Starlette 1.9 | pip-audit (no known vulnerabilities) | Fixed |
| F-02 | Dependencies | High | Vite 5 dev server (run by frontend.bat) path traversal and fs.deny bypass on Windows; React Router 6 open redirect; Vitest 2 / tinypool critical (dev) | Vite 8, Vitest 5, React Router 7, plugin-react 6; Node minimum raised to 22.12 (Node 18 and 20 are end of life) in package.json, frontend.bat and README | npm audit --omit=dev (0); full frontend suite | Fixed |
| F-03 | Dependencies | Low | braces and postcss-selector-parser advisories inside Tailwind 3 (CSS build only) | Needs Tailwind 4, a config rewrite | - | Accepted |
| F-04 | Architecture | Medium | Architecture test accepted a bare `import module_M`, after which `module_M.models` is reachable | Checker rejects it | tests/test_architecture.py::test_checker_detects_violations | Fixed |
| F-05 | Contracts | Medium | Nothing compared CONTRACTS.md with the code; `list_field_sources` was only a commented line | New contracts test (events, publishers, public API, routes); doc fixed | tests/test_contracts.py | Fixed |
| F-06 | Tests | Low | Starlette 1.9 test client deprecation warning on every run | Filtered in pyproject (test-only) | - | Fixed |
| F-07 | Consistency | Low | The Cotton/Hemp pair is written as a literal in five filter controls | The two programmes are code paths, not master data (D-109) | - | Accepted |
| F-08 | Consistency | Low | Module 3 aggregate used the literal "complete" next to an existing constant | Uses STEP_COMPLETE | module_1 funnel tests | Fixed |
| F-09 | Security | Medium | CSV exports wrote typed text (village, vehicle, notes) unescaped, so `=...` ran as a formula in a spreadsheet | core/csvsafe.py used by modules 4, 5, 6 | tests/test_audit_security.py::TestCsvInjection | Fixed |
| F-10 | Validation | Medium | Non-ASCII digits passed ID and phone checks and then failed to match stored values | ascii_digits folding, [0-9] patterns | tests/test_audit_security.py::TestUnicodeDigits | Fixed |
| F-11 | Access | High | Any officer could edit another officer's farmer or reshape and delete their fields | module_2 permissions (D-110) | tests/test_audit_security.py::TestCrossOfficerAccess | Fixed |
| F-12 | Access | High | Four Module 6 routes (heap list, config, contributors, CSV) did not require an identified officer | Depends(get_current_officer) | test_every_module_route_requires_the_acting_officer | Fixed |
| F-13 | Tests | Low | Two tests tried a live postcodes.io call (the offline fallback made them pass) | Not changed; the fallback is the behaviour under test | tests/test_scenarios.py | Accepted |
| F-14 | Tests | Low | The public-page rate limit test left the limiter full, so the next public test saw 429 | Limiter reset around each public test | tests/test_audit_security.py::TestPublicTrace | Fixed |

## Performance

Measured on the 10,000 farmer seed (20,000 fields, 50,000 deliveries, 500 heaps); see
`docs/TESTING.md`. Cotton dashboard views are under 400 ms p95; the all crops overview and
alerts reach about 450 ms p95 cold; the first read after a write is about 3 s while the
Harvest Radar dataset rebuilds. Query counts are asserted in tests so they cannot grow
unnoticed.

## Residual risks

* Identity is an `X-Officer-Id` header. Anyone who can reach the API can claim any officer
  (see KNOWN_LIMITATIONS.md). This is the largest risk and is closed only by Login.
* Checklist items covered by existing module tests rather than new audit tests:
  concurrent ID counters and overlap races (`module_2/tests/test_concurrency.py`),
  geometry and area, overlap edge cases. They were not re-derived in this audit.
* Not exercised in this audit: a PostgreSQL run (no Docker available; the portability
  steps are in NEXT_STEPS.md), a Playwright run of the browser suites, and a manual
  contrast, focus and 360/768/1440 width review (Prompt 10 covers the visual pass).
* Seed data is dummy data; field offices and tehsils are not a complete national list.

# Repository Guidelines

## Global Environment Rules

Never use the system-level Python environment as the project runtime, and never install, remove, upgrade, or reconfigure packages in it. Treat system Python as read-only.

Use `uv` high-level commands for all Python-related project work, prioritizing `uv init`, `uv venv`, `uv add`, `uv remove`, `uv sync`, and `uv run`. Unless explicitly requested, do not use `uv pip`, direct `python`, or `pip` for project environments, dependency management, or script execution.

Use `pnpm` and `pnpm dlx` for all Node-related work. Do not use `npm` or `npx` for dependency installation, script execution, or one-off CLI usage.

Do not create another Python virtual environment, Node environment, or similar nested runtime environment inside an existing project environment. Reuse the current project environment by default unless explicitly requested otherwise.

Communicate with users in Simplified Chinese by default. Final review reports should also be written in Simplified Chinese by default. This does not apply to code, technical identifiers, paths, commands, proper nouns, or rule files that should remain in their original language.

## Project Overview

FilamentManager is a local 3D printer operations and filament inventory app for Bambu Lab LAN workflows. It ingests printer MQTT telemetry, derives device/AMS state, synchronizes filament SKU and spool inventory, stores local history in SQLite, and exposes a Vue 3 UI for operations, inventory, debugging, maintenance, and notifications.

Local runtime data such as `filament_manager.db`, backups, support bundles, media outputs, real printer serial numbers, access codes, and private network details must not be committed.

## Core Code Map

Backend code lives in `backend/src/filament_manager`:

- `main.py`: FastAPI application entrypoint and router registration.
- `schemas.py`: Pydantic request/response contracts used by API routes.
- `api/routes.py`: general printer, status, debug, export, maintenance, storage, and operational routes.
- `api/filament_routes.py`: filament brand, type/series, SKU, stock, spool, conflict, and inventory routes.
- `api/helpers.py`: shared API response and redaction helpers.
- `db/models.py`: SQLAlchemy ORM models, enum-like state mappings, and model properties.
- `db/session.py`: engine/session setup and lightweight SQLite schema backfill. Any schema-affecting model change usually also needs this file.
- `mqtt/client.py`: LAN MQTT client behavior.
- `mqtt/parser.py`: pure parsing and normalization of printer/AMS payloads.
- `mqtt/state_machine.py`: print state transition helpers.
- `services/mqtt_processing.py`: MQTT ingestion orchestration, raw message persistence, parser fan-out, event emission, and downstream service calls.
- `services/inventory.py`: filament business rules, SKU matching/creation, spool lifecycle, AMS slot binding, UID conflict handling, and stock decrement logic.
- `services/inventory_serializers.py`: filament API serialization. Keep presentation shaping here instead of duplicating it in routes.
- `services/device_status.py`: device dashboard/status snapshot derivation from telemetry.
- `services/ams.py`: AMS unit/slot read models, labels, history, and dashboard-facing helpers.
- `services/print_log.py`, `metrics.py`, `events.py`, `notifications.py`, `maintenance.py`, `storage.py`, `camera.py`, `exporting.py`, `database_retention.py`: domain-specific services.
- `services/device_status_constants.py`, `inventory_constants.py`: shared constants and vocabulary.
- `data/`: bundled static data such as HMS code tables.

Frontend code lives in `frontend/vue/src`:

- `main.ts`, `App.vue`: Vue app bootstrap and shell.
- `api.ts`: backend API client; keep HTTP shape changes centralized here.
- `types.ts`: shared frontend TypeScript types matching backend API responses.
- `stores/`: Pinia setup-style stores, named `useXxxStore`, with matching `*.spec.ts` tests where practical.
- `views/`: page-level Vue SFCs such as dashboard, AMS, inventory, storage, debug, notifications, events, maintenance, and print log.
- `components/`: shared reusable UI components.
- `styles/`: domain/page CSS modules plus layout/responsive/shared widget styles.
- `app/` and `composables/`: frontend-only helpers for preferences, navigation, metrics, bootstrap, and event streams.
- `i18n.json`: user-facing strings.

Backend tests and payload fixtures live in `test/`. Frontend unit tests live beside source files as `*.spec.ts`; frontend e2e tests live in `frontend/vue/e2e`.

## Core Flows

MQTT ingestion flow:

1. API or MQTT client hands payloads to `services/mqtt_processing.py`.
2. Raw payloads are persisted for debug/retention.
3. `mqtt/parser.py` extracts printer and AMS facts without database side effects.
4. `device_status.py`, `ams.py`, `inventory.py`, `print_log.py`, `metrics.py`, and notification/event services update their domains.

Filament/AMS inventory flow:

1. Parser identifies AMS slot state, material, series, color, `tray_uuid`/`tag_uid`, `remain`, and raw payload.
2. Inventory service decides whether to bind, reuse, create, unload, or ignore a spool.
3. SKU matching uses brand/type-series/color/weight/tray info rules before auto-creating review-required SKUs.
4. Serializer exposes stable API fields for the frontend.

AMS/RFID state rules:

- `remain=-1` means remaining percentage is unavailable, not that RFID is still reading.
- RFID/transition blocking should be based on explicit slot state, `ams_status`, `tray_reading_bits`, `tray_read_done_bits`, and absence of stable filament payload.
- Do not create phantom spools from transition frames without material/color/identity payload.
- Store raw AMS slot payload in `config.ams_raw` when syncing spools.
- `last_ams_remain_percent` should represent only `0..100`; invalid or negative raw values should serialize as `null` while remaining available in `config.ams_raw`.

## Build, Test, and Development Commands

Use `uv` for Python and `pnpm` for Node work.

```bash
uv run --project backend uvicorn filament_manager.main:app --reload --host 127.0.0.1 --port 8000
```

Starts the FastAPI backend with local SQLite defaults.

```bash
uv run --project backend --extra dev pytest
```

Runs backend pytest tests from `test/`.

```bash
cd frontend/vue && pnpm dev
cd frontend/vue && pnpm test:unit
cd frontend/vue && pnpm build
```

Starts Vite, runs Vitest unit tests, and type-checks plus builds the Vue app.

For focused backend verification, prefer targeted pytest files first, for example:

```bash
uv run --project backend --extra dev pytest test/test_parser.py test/test_mqtt_processing.py test/test_inventory_api.py
```

Then run the full relevant suite when touching shared parser, database, inventory, serializer, or route behavior.

## Coding Style & Naming Conventions

Backend code targets Python 3.11+, uses type hints, SQLAlchemy ORM models, and Pydantic schemas. Keep FastAPI route functions thin: they should validate inputs, call service functions, and serialize results. Business logic belongs in `services/`; payload normalization belongs in `mqtt/parser.py` or service-local helpers.

Prefer existing local helpers such as `_clean_text`, color normalization, SKU matching helpers, serializer helpers, and event helpers over ad hoc parsing or duplicated response shaping. Add new abstractions only when they remove real duplication or match an existing domain pattern.

Service functions should be named by action and domain, for example `process_ams_slot_filament`, `upsert_print_log_from_snapshot`, or `record_metric_samples_from_push_status`. Private helpers use `_snake_case`. Keep mutable JSON config keys documented by nearby code/tests, especially for filament spool `config`.

Database changes require coordinated updates to `db/models.py`, `db/session.py`, relevant `schemas.py`, serializers, routes/services, and tests. This project does not use a separate migration framework; `db/session.py` carries lightweight SQLite backfill logic.

Frontend code uses Vue 3 SFCs, setup-style Pinia stores, and TypeScript. Store names follow `useXxxStore`; specs should use matching `*.spec.ts` filenames. Keep `api.ts` and `types.ts` aligned with backend response shapes. Avoid breaking view/component contracts unless the user-facing change requires it.

UI work should follow the existing operational dashboard style: dense, scannable, local-tool oriented, and consistent with the current component/style files. Prefer existing CSS modules and shared components over one-off styling. Do not introduce broad visual redesigns while making narrow behavior fixes.

## Testing Guidelines

Backend tests use pytest and FastAPI `TestClient`; add focused regression tests near related behavior in `test/test_*.py`. Synthetic MQTT payloads belong in `test/fixtures/` when reused across tests.

Frontend tests use Vitest, Vue Test Utils, and jsdom; add or update store/component specs when changing frontend state, API mapping, derived values, or visible behavior.

For parser/MQTT/inventory changes, cover:

- pure parser behavior in `test/test_parser.py`;
- ingestion and event behavior in `test/test_mqtt_processing.py`;
- API-visible filament and inventory effects in `test/test_inventory_api.py`;
- device dashboard effects in `test/test_device_dashboard.py` or `test/test_non_inventory_features.py` when relevant.

Before submitting broad changes, run backend pytest plus `pnpm test:unit` and `pnpm build`. For frontend flows with routing or browser-only behavior, run `cd frontend/vue && pnpm test:e2e` when practical.

## Commit & Pull Request Guidelines

History follows Conventional Commit style with scopes, often in Chinese, such as `feat(filament): ...`, `fix(ams): ...`, `test(*): ...`, and `refactor(frontend): ...`. Keep commits focused by domain.

PRs should describe the user-facing change, list verification commands, link relevant issues, and include screenshots for visible UI changes. Mention database/schema implications explicitly when `db/models.py`, `db/session.py`, or API schemas change.

## Security & Configuration Tips

Never commit real printer access codes, serial numbers, local databases, backup archives, support bundles containing private data, or private network details. API responses should keep sensitive fields redacted. Run the app only on trusted local networks unless deployment security has been reviewed.

Printer interaction features should default to read-only or reversible behavior. Be careful with MQTT command handling, media access, support bundles, and exports because they can expose sensitive local device information.

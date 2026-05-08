# Repository Guidelines

## Project Structure & Module Organization

FilamentManager is a local 3D printer operations and filament management app. Backend code lives in `backend/src/filament_manager`, with FastAPI routes, SQLAlchemy models, MQTT parsing, and business services grouped by domain. Vue 3 frontend code lives in `frontend/vue/src`, with Pinia stores in `src/stores`, page views in `src/views`, shared components in `src/components`, styles in `src/styles`, and brand assets in `src/assets`. Backend tests and synthetic payload fixtures live in `test/`. Local runtime data such as `filament_manager.db`, backups, and generated outputs must not be committed.

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

## Coding Style & Naming Conventions

Backend code targets Python 3.11+, uses type hints, SQLAlchemy ORM models, and service functions named by action/domain, for example `process_ams_slot_filament`. Frontend code uses Vue SFCs, setup-style Pinia stores, and TypeScript. Store names follow `useXxxStore`; specs use matching `*.spec.ts` files. Keep view/component contracts stable unless the change explicitly requires a UI API update.

## Testing Guidelines

Backend tests use pytest and FastAPI `TestClient`; add tests near related behavior in `test/test_*.py`. Frontend tests use Vitest, Vue Test Utils, and jsdom. Add focused happy-path and regression tests for stores, API behavior, parsing, MQTT processing, and UI helpers. Before submitting broad changes, run backend pytest plus `pnpm test:unit` and `pnpm build`.

## Commit & Pull Request Guidelines

History follows Conventional Commit style with scopes, often in Chinese, such as `feat(filament): ...`, `fix(ams): ...`, `test(*): ...`, and `refactor(frontend): ...`. Keep commits focused by domain. PRs should describe the user-facing change, list verification commands, link relevant issues, and include screenshots for visible UI changes.

## Security & Configuration Tips

Never commit real printer access codes, serial numbers, local databases, backup archives, or private network details. API responses should keep sensitive fields redacted. Run the app only on trusted local networks unless deployment security has been reviewed.

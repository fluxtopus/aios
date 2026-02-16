# Repository Guidelines

## Project Structure & Module Organization
This repository is a monorepo for Fluxtopus services, UIs, and SDKs.

- `apps/`: deployable backend services (`tentacle`, `inkpass`, `mimic`), each with `src/`, `tests/`, and migrations.
- `frontends/`: Next.js/React apps (`tentacle-ui`, `mimic-ui`, `fluxos-landing`).
- `packages/`: shared SDKs/libraries (Python and TypeScript).
- `scripts/`: repo automation (notably `run-all-tests.sh` and package publish scripts).
- `docs/architecture/`: architecture decisions and guardrails.

For Tentacle changes, preserve DDD layering in `apps/tentacle/src/{domain,application,infrastructure,api}`.

## Build, Test, and Development Commands
From repository root:

- `cp .env.example .env && make dev`: start local stack with Docker Compose.
- `make logs`: follow service logs.
- `make stop`: stop local stack.
- `make test-all`: run Docker-based monorepo tests (`./scripts/run-all-tests.sh`).
- `./scripts/run-all-tests.sh --unit`: backend unit tests only.
- `./scripts/run-all-tests.sh --e2e`: Playwright E2E (currently `frontends/fluxos-landing`).
- `make build-python-packages`: build Python packages in `packages/` via `uv`.

Frontend examples:
- `cd frontends/tentacle-ui && npm run dev`
- `cd frontends/tentacle-ui && npm run test`

## Coding Style & Naming Conventions
- Python: 4-space indentation, `snake_case` modules/functions, `PascalCase` classes, and type hints for new/edited code.
- Tests: use `test_*.py`, `Test*`, and `test_*` naming (enforced in service `pytest.ini` files).
- Python package tooling uses `ruff`/`mypy` (and in some packages `black`) with `line-length = 100`.
- Frontend: React components in `PascalCase` files (for example `DeliveryDashboard.tsx`), utility/state modules in `camelCase`.

## Testing Guidelines
- Backends use `pytest` with strict markers and coverage reporting against `src`.
- Add or update tests whenever behavior changes; include unit coverage first, then integration/E2E if flow-level behavior changes.
- For focused backend checks, run service-specific pytest commands via Docker Compose before opening a PR.

## Commit & Pull Request Guidelines
- Follow the existing commit style: short, imperative subject lines; optional scoped prefixes where useful (for example `fix(ci): ...`).
- Keep commits focused by concern (service/UI/package).
- Branch naming rule: never prefix branch names with `codex/` or any other harness/provider label.
- Use `.github/pull_request_template.md`: include **What**, **Why**, **How to test**, and complete checklist items.
- PR messaging rule: do not include links or references to Claude, Codex, or any other AI provider/harness in PR titles, descriptions, or comments.
- Never commit secrets (`.env`, API keys, private keys). Update docs when behavior or setup changes.

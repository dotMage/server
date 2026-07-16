# Changelog

All notable changes to dotmage-server are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The API contract is versioned by URL (`/api/v1`) — breaking it requires `/api/v2` and a
PR in the private `dotmage-spec` repo, never a silent release.

## [Unreleased]

### Added
- AK rotation (spec L): key generations per blob, `rotate/begin|status|complete`,
  rotation-gated blob replacement; pushes are refused mid-rotation with a clear 409.
- Team-of-one user model (spec E.9): `users`/`invitations` tables, automatic migration
  of existing accounts (owner user backfilled, devices linked), `GET /whoami`,
  `DOTMAGE_MODE=solo|team` (default solo — team endpoints hidden).
- Startup schema migrator: additive `ALTER TABLE` for new columns (no alembic needed).
- Team invitations (spec K): `POST /users/invite`, two-step redeem/complete with sealed
  AK the server cannot open; one-time tokens with TTL.
- Role enforcement on every write: owner/editor/viewer; last-owner protection;
  `PATCH/DELETE /users/{id}` for role changes and offboarding (wraps dropped, devices
  revoked, rotation flagged as required).
- Audit log attributes every action to a user; `GET /audit` returns the user name.
- Docker images are multi-arch: `linux/amd64` + `linux/arm64` (Raspberry Pi, ARM VPS).
- Backup & restore runbook (why E2E means no server-side recovery, cron schedule,
  `PRAGMA integrity_check`, step-by-step restore) published at
  https://dotmage.github.io/docs/#backup; linked from README and the `install.sh` outro.

### Changed

### Fixed
- README backup command used the `sqlite3` CLI, which the Docker image doesn't ship —
  replaced with the working Python online-backup one-liner.
- `install.sh` now checks Docker daemon access (`docker info`) right after detecting
  compose and exits with a clear message (sudo / `usermod -aG docker` + relogin) instead
  of dying silently mid-install; `up -d` errors are no longer hidden by `2>/dev/null`.

### Security

## 2026-07-06

### Fixed
- Enrollment tokens (incl. the web-admin login token) now carry the issuing user's
  identity: a token minted by an editor enrolls a device as that editor, not the owner.

### Added
- `install.sh` interactively asks for mode (solo/team) and server name at deploy
  (falls back to `DOTMAGE_MODE` / `DOTMAGE_SERVER_NAME` env vars when set).
- `DOTMAGE_SERVER_NAME` — optional display name advertised in `/health`; clients adopt it
  as the default server name so members don't have to rename after joining.

## 2026-07-01

### Added
- `DELETE /api/v1/apps/{name}` — delete an application with all environments.

### Fixed
- Bootstrap secret is no longer regenerated when an account already exists.
- App names containing `/` (folders) work in all URL paths.

## 2026-06-11

### Added
- Bootstrap device registration flow, scoped CI tokens.

## 2026-06-09

Initial deployable release: FastAPI API per spec Appendix B, SQLite storage, Docker image
(ghcr.io), one-liner install, bundled web admin.

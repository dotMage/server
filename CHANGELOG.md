# Changelog

All notable changes to dotmage-server are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The API contract is versioned by URL (`/api/v1`) — breaking it requires `/api/v2` and a
[dotmage-spec](https://github.com/dotMage/dotmage-spec) PR, never a silent release.

## [Unreleased]

### Added

### Changed

### Fixed

### Security

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

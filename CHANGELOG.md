# Changelog

## [v1.2.0] - 2026-04-24
### Added
- **Alembic auto-migration on startup**: Backend now runs `alembic upgrade head` on container start and validates schema drift via `validate_schema_drift()`.
- **Access Policies system**: Full CRUD for access policy assignments, bandwidth profiles, and resolution preview. Replaces legacy privilege map.
- **Device Registry with bulk CSV**: Import/export device registry templates as CSV (UTF-8 BOM) with category support and name column.
- **Network Segments**: Segment-based authorization with CIDR math, exception ranges, and CIR precedence.
- **CIR (Committed Information Rate) management**: Dedicated CIR profiles, assignment workflow, and RADIUS authorization precedence.
- **FreeRADIUS policy updates**: `nas_based_authorization` with SQL-Group resolution and group hydration.
- **Radius-tests regression suite**: Deterministic seeds and precondition probes for authorization matrix and MAC priority scenarios.
- **JIT endpoint normalization**: Unified under `/users/jit-requests/{username}/approve`.

### Changed
- **Schema migrations**: 5 new Alembic migrations for privilege_map_mac, integrity_math, rename_user_nas_privilege_map, remove_iam_module, device_registry_name.
- **Database schema**: `device_registry` table with name, `access_policy_assignments` replacing legacy privilege_map, dropped IAM tables.
- **Frontend routing**: New `/access-policies`, `/network-segments`, `/devices` routes; redirects from legacy paths.
- **Template download**: CSV format (not XLSX) with UTF-8 BOM for Excel compatibility.

### Fixed
- **Runtime schema drift detection**: `KNOWN_EXCEPTIONS` extracted to `backend/app/db/exceptions.py` for ORM-only/virtual columns.
- **NAS cascade updates**: IP changes on NAS now cascade to all related access policy assignments.

## [v1.1.1] - 2026-03-29
### Added
- English-native Master Repositor Pitch (`README.md`).
- `docs/01-nas-provisioning.md`: User manual with NAS creation and Huntgroup Mermaid.js routing diagram.
- `docs/02-iso27001-privilege-map.md`: Security authorization flow for NAS-Based Privilege Maps with ISO 27001 constraints.
- `docs/03-jit-break-glass.md`: Complete sequence diagram defining the JIT Break-Glass operator request, execution, and expiration.

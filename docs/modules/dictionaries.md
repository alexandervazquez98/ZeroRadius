---
goal: Document the Dictionary Management module so an AI agent can CRUD RADIUS vendor/custom dictionary files, upload them, and fetch attributes/enums.
audience: agent + human
prerequisites:
  - At least one custom dictionary file present in `backend/dictionaries/`
  - The `radius-server` container running (for built-in dictionaries)
inputs:
  - JWT
outputs:
  - Files in `backend/dictionaries/` (surfaced to the radius-server volume)
  - FreeRADIUS auto-restarted after each change
---

# Module — Dictionaries

> **Scope:** `/dictionary/*` (router) + `frontend/src/pages/Dictionaries.jsx`
> + `backend/app/services/dictionary_loader.py` +
> the mounted volume `./backend/dictionaries/ → /etc/raddb/custom_dictionaries`.

## 1. Purpose

Manage **custom** RADIUS dictionaries (vendor-specific ATTRIBUTE / VALUE
declarations). Combined with the FreeRADIUS built-in dictionaries, the
attribute selector in the Groups UI consumes them.

The module also exposes **read-only** access to the FreeRADIUS built-in
dictionaries (`/dictionary/builtin/*`) and to recent FreeRADIUS log lines
(`/dictionary/radius-logs`).

## 2. URL surface

Base path: `/dictionary`

| Method | Path | Roles | Notes |
|---|---|---|---|
| `GET` | `/files` | any active user | List custom dictionary filenames |
| `POST` | `/upload` | any active user | Upload (multipart/form-data); auto-converts v4 types; restarts radius |
| `POST` | `/rename?old_name=…&new_name=…` | any active user | Rename + restart radius |
| `DELETE` | `/{filename}` | any active user | Delete + restart radius |
| `GET` | `/content/{filename}` | any active user | Read raw content |
| `PUT` | `/content/{filename}` | any active user | Overwrite content + restart radius |
| `GET` | `/builtin` | any active user | List built-in dictionary files (skipping Motorola — replaced by custom Cambium) |
| `GET` | `/builtin/{filename}` | any active user | Read built-in content (filename pattern-enforced) |
| `GET` | `/attributes` | any active user | Merged custom + built-in attribute list |
| `GET` | `/values/{attribute_name}` | any active user | Enum values for a given attribute |
| `GET` | `/radius-logs?lines=N` | `admin` / `superadmin` | Filtered FreeRADIUS logs for diagnosis |

## 3. Custom dictionary CRUD

### 3.1 Upload

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

curl -sS -X POST http://localhost:8000/dictionary/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./cambium_supplement.dict" | jq .
```

**Expected output:**

```json
{
  "message": "Dictionary cambium_supplement.dict uploaded successfully. 2 FreeRADIUS 4.x type(s) were auto-converted to 3.x equivalents."
}
```

**Failure:**

```json
{ "detail": "File too large. Maximum size is 1MB." }   // size cap
{ "detail": "Path '...' contains invalid characters" } // validation
```

After every upload / rename / delete / content-update, the `radius-server`
container is restarted (FreeRADIUS only loads dictionaries at startup).

### 3.2 Content

The content endpoints return and accept the raw `*.dict` file as a string.
Pydantic validates: filename pattern, no `..`, no absolute paths.

## 4. Built-in dictionaries

Read-only introspection of FreeRADIUS built-in vendor dictionaries
(`/usr/share/freeradius/dictionary.*`):

- `/builtin` returns `[{filename, vendor}]` for each `dictionary.<vendor>`,
  except `dictionary` (the global index) and `dictionary.motorola*`
  (disabled by the Dockerfile in favour of custom Cambium).
- `/builtin/{filename}` is path-traversal-safe via a regex check
  (`dictionary\.[a-zA-Z0-9._-]+`).

## 5. Attribute & value queries

- `/attributes` returns the merged catalogue (custom > built-in precedence;
  built-ins tagged with a `[Sistema] dictionary.*` prefix in the `dictionary`
  field for UI grouping).
- `/values/{attribute_name}` returns `[{name, value}]` enums for selectors.

## 6. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `503 "Could not read built-in dictionaries from radius-server"` | `radius-server` container is down | `docker compose up -d radius` |
| `413 "File too large"` | Upload > 1 MB | Split or compress |
| `400 "Invalid built-in dictionary filename"` | Filename outside `dictionary\.[a-zA-Z0-9._-]+` | Use built-in naming |
| After upload the radius-server keeps using the old attribute | Restart may have failed | `docker compose logs radius`; `/dictionary/radius-logs?lines=200` for diagnosis |

## 7. Cross-references

- **Architecture / docker socket mount (used for restart):** [`docs/architecture.md`](../architecture.md#3-process-level-integration)
- **RADIUS log viewer:** [`docs/04-live-log-viewer.md`](../04-live-log-viewer.md)
- **Groups UI (consumer of /attributes + /values):** [`docs/modules/groups.md` *](https://github.com/alexandervazquez98/ZeroRadius/blob/main/frontend/src/pages/Groups.jsx) *(module doc not yet written; see JSDoc in the file)*

---
goal: Document the Admin Users management module so an AI agent can CRUD operators and unlock locked accounts.
audience: agent + human
prerequisites:
  - Running stack; at least one superadmin exists (`scripts.seed_admin`)
  - Understanding of the role hierarchy: `superadmin > admin > auditor`
inputs:
  - JWT (superadmin required for all mutations; admin can read the list)
outputs:
  - `admin_users` rows; lockout state cleared via `POST /{id}/unlock`
---

# Module — Admin Users

> **Scope:** `/admin-users/*` (router) + `frontend/src/pages/AdminUsers.jsx`
> + database table `admin_users` + `login_attempts` (lockout) +
> `app/middleware/force_password_change.py`.

## 1. Role hierarchy

| Role | Can | Cannot |
|---|---|---|
| `superadmin` | everything; can grant `superadmin` | — |
| `admin` | CRUD most resources; manage admin users (except superadmin) | grant `superadmin`; delete the bootstrap `admin` |
| `auditor` | read-only across all audit and reference data | mutate anything |
| (legacy `readonly`) | subset of reads | — |

The `superadmin` role can only be granted by an existing `superadmin`. Any
attempt to mint a `superadmin` from an `admin` → 403.

## 2. URL surface

Base path: `/admin-users`

| Method | Path | Roles | Notes |
|---|---|---|---|
| `GET` | `` | `admin` / `superadmin` | List all admin users |
| `POST` | `` | `superadmin` | Create (sets `force_password_change=1` automatically) |
| `PUT` | `/{id}` | `superadmin` | Update role / email / active / password |
| `DELETE` | `/{id}` | `superadmin` | Delete (cannot self-delete; cannot delete bootstrap `admin`) |
| `POST` | `/{id}/unlock` | `superadmin` | Clear locked-out state |

## 3. Bootstrap

```bash
# One-time, on a fresh volume
docker exec -it radius-backend python -m scripts.seed_admin \
    --username admin --password "BootStrap!2026"
```

The bootstrap admin is `superadmin`. **Cannot be deleted** (`400 Cannot delete super admin`).

## 4. Forced password change

`app/middleware/force_password_change.py` intercepts every authenticated
request: if `admin_users.force_password_change == 1`, all routes except
`POST /auth/change-password` and `/auth/token` return `403
{"detail": "Password change required"}` until the password is reset.

The toggle is set on creation and on PUT-with-password.

## 5. End-to-end agent run

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

# Create an admin role
curl -sS -X POST http://localhost:8000/admin-users \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "username": "ops1",
    "email": "ops1@example.com",
    "password": "Ops1StrongPwd!",
    "role": "admin",
    "is_active": true
  }' | jq .

# List
curl -sS -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/admin-users | jq .

# Unlock a user after too many failed attempts
curl -sS -X POST http://localhost:8000/admin-users/3/unlock \
  -H "Authorization: Bearer $TOKEN" | jq .
```

## 6. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `400 "Cannot delete your own account"` | Self-delete attempted | Delete a different account |
| `400 "Cannot delete super admin"` | Deleting the bootstrap admin | Rename the bootstrap user first; do not delete |
| `403 "Only superadmin can assign the superadmin role"` | Non-super trying to mint a superadmin | Escalate from a superadmin session |
| `403 "Password change required"` | Forced change is still pending | `POST /auth/change-password` |

## 7. Cross-references

- **Bootstrap script:** `backend/scripts/seed_admin.py`
- **Lockout service:** `backend/app/services/lockout.py`
- **Security:** [`docs/security-coverage.md`](../security-coverage.md#a04-insecure-design--authentication)

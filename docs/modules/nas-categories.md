---
goal: Document the NAS Categories module so an AI agent can manage categories and reason about the criticality field's effect on bulk operations.
audience: agent + human
prerequisites:
  - Read [`docs/05-nas-categories.md`](../05-nas-categories.md) for context (this module doc refreshes / supersedes it)
inputs:
  - JWT (admin/superadmin for mutations)
outputs:
  - `nas_categories` rows referenced by `nas.category_id` and Access Policies' `nas_category_id`
---

# Module — NAS Categories

> **Scope:** `/nas-categories/*` (router) + `frontend/src/components/...`
> + database table `nas_categories`.

## 1. Purpose

Group NAS devices by **type / location / vendor** for:

- Bulk operations (apply policy or audit to all devices in a category).
- Privilege mapping targets (Access Policies can target by category).
- Visual organisation of the NAS list.

## 2. URL surface

Base path: `/nas-categories`

| Method | Path | Roles |
|---|---|---|
| `GET` | `` | any active user |
| `GET` | `/{id}` | any active user |
| `POST` | `` | `admin` / `superadmin` |
| `PUT` | `/{id}` | `admin` / `superadmin` |
| `DELETE` | `/{id}` | `superadmin` |

## 3. Schema

`NasCategory`:

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `name` | str unique | "Core Routers", "WiFi Controllers", … |
| `description` | str \| null | |
| `criticality` | enum | `standard` \| `restricted` \| `critical` |
| `vendor` | str \| null | Reference only ("Cisco", "Juniper", …) |
| `created_at` | datetime | Server-set |

## 4. Criticality

| Value | Meaning |
|---|---|
| `standard` | Regular network devices |
| `restricted` | Additional approval required for access |
| `critical` | High-security infrastructure (core routers, firewalls) with strict controls |

The value is shown in the NAS list ordering (`ORDER BY c.criticality DESC`).

## 5. End-to-end agent run

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

# List categories
curl -sS -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/nas-categories | jq .

# Create
curl -sS -X POST http://localhost:8000/nas-categories \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "WiFi-AP",
    "description": "Branch wireless controllers",
    "criticality": "standard",
    "vendor": "Cambium"
  }' | jq .
```

## 6. Cross-references

- **NAS devices linking to a category:** `nas.category_id` (FK).
- **Access Policies targeting by category:** [`docs/modules/access-policies.md`](access-policies.md#5-validation-rules-enforced-at-the-api)
- **Legacy documentation (refresh):** [`docs/05-nas-categories.md`](../05-nas-categories.md)
- **Database:** [`docs/database.md` → nas_categories](../database.md#3-zeroradius-domain-tables)

---
goal: Document the global rate-limiting policy applied to the ZeroRadius API so an AI agent can predict why a request was throttled and what to do about it.
audience: agent + human
prerequisites:
  - Read [`docs/security-coverage.md`](../security-coverage.md)
inputs: none
outputs: per-route limit configuration (`slowapi` `Limiter.limit(...)` decorators)
---

# Module — Rate Limiting

> **Scope:** `backend/app/core/limiter.py` + global exception handler in
> `app/main.py` + per-route `@limiter.limit("X/minute")` decorators across
> all routers.

## 1. Mechanism

- Library: [slowapi](https://slowapi.readthedocs.io/).
- Storage: in-memory (single-process Uvicorn). Sufficient for the default
  1-worker deployment; a Redis backend is the next step for cluster scale-out.
- Headers: when a request hits the limit, the response carries
  `Retry-After` and the 429 body matches `RateLimitExceeded`.

```python
# app/main.py
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

## 2. Per-route policy

| Endpoint | Limit |
|---|---|
| `GET /api/v1/syslog/builtin` | `60/minute` |
| `GET /api/v1/syslog/attributes` | `60/minute` |
| `GET /api/v1/syslog/values/{attr}` | `60/minute` |
| `POST /api/v1/syslog/upload` | `10/minute` |
| `POST /api/v1/syslog/rename` | `10/minute` |
| `DELETE /api/v1/syslog/{filename}` | `10/minute` |
| `PUT /api/v1/syslog/content/{filename}` | `10/minute` |
| `GET /api/v1/syslog/radius-logs` | `30/minute` |
| `GET /api/v1/access-policies/bandwidth-profiles` | `60/minute` |
| `POST /api/v1/access-policies/bandwidth-profiles` | `30/minute` |
| `PUT /api/v1/access-policies/bandwidth-profiles/{name}` | `30/minute` |
| `DELETE /api/v1/access-policies/bandwidth-profiles/{name}` | `30/minute` |
| `GET /api/v1/access-policies/assignments` | `60/minute` |
| `POST /api/v1/access-policies/assignments` | `120/minute` |
| `POST /api/v1/access-policies/assignments/bulk` | `120/minute` |
| `PUT /api/v1/access-policies/assignments/{id}` | `120/minute` |
| `DELETE /api/v1/access-policies/assignments/{id}` | `120/minute` |
| `POST /api/v1/access-policies/preview` | `60/minute` |
| `GET /api/v1/circuits` | `60/minute` |
| `GET /api/v1/circuits/resolve` | `30/minute` |
| `GET /api/v1/circuits/{id}` | `60/minute` |
| `POST /api/v1/circuits` | `30/minute` |
| `PUT /api/v1/circuits/{id}` | `30/minute` |
| `DELETE /api/v1/circuits/{id}` | `30/minute` |
| `GET /api/v1/network-segments` | `60/minute` |
| `POST /api/v1/network-segments` | `30/minute` |
| `PUT /api/v1/network-segments/{id}` | `30/minute` |
| `DELETE /api/v1/network-segments/{id}` | `30/minute` |
| `GET /api/v1/admin-users` | `60/minute` |
| `POST /api/v1/admin-users` | `30/minute` |
| `PUT /api/v1/admin-users/{id}` | `30/minute` |
| `DELETE /api/v1/admin-users/{id}` | `30/minute` |
| `POST /api/v1/admin-users/{id}/unlock` | `30/minute` |
| `GET /api/v1/device-registry` | `60/minute` |
| `GET /api/v1/device-registry/stats` | `60/minute` |
| `GET /api/v1/device-registry/{id}` | `60/minute` |
| `POST /api/v1/device-registry` | `30/minute` |
| `PUT /api/v1/device-registry/{id}` | `30/minute` |
| `DELETE /api/v1/device-registry/{id}` | `30/minute` |
| `POST /api/v1/device-registry/bulk` | `10/minute` |
| `POST /api/v1/device-registry/bulk/csv` | `10/minute` |
| `GET /api/v1/device-registry/bulk/template` | `30/minute` |
| `GET /api/v1/audit/admin` | `60/minute` |
| `GET /api/v1/audit/access` | `60/minute` |
| `GET /api/v1/audit/export` | `20/minute` |

## 3. Failure handling

```json
HTTP/1.1 429 Too Many Requests
Retry-After: 60

{"detail": "Rate limit exceeded: 60 per 1 minute"}
```

## 4. Operational guidance for agents

- **Back off and retry**: when a write returns 429 with `Retry-After`, wait
  that long before retrying.
- **Bulk endpoints** are intentionally restricted (`10/minute` or
  `30/minute`). Don't try to script many simultaneous bulk imports — queue
  them.
- **Read-vs-write imbalance**: the read endpoint is generally allowed
  double the budget of the write endpoint.
- **Cluster-mode caveat**: the limiter is in-memory per Uvicorn worker; if
  you run multiple workers behind a load balancer, switch to a Redis backend
  to share state (planned for v1.4).

## 5. Cross-references

- **Security tests:** [`docs/security-coverage.md`](../security-coverage.md) — `test_security_a04_auth.py` exercises the lockout+rate-limit combined path.

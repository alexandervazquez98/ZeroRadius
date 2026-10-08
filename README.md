# ZeroRadius 🌐

ZeroRadius is a modern, full-stack, state-driven management interface for the **FreeRADIUS** AAA Server. Built to abstract the severe complexities, flat-file hell, and UX pitfalls of traditional legacy managers (like daloRADIUS), it offers a React-driven frontend and an asynchronous Python/FastAPI backend designed for enterprise networks and ISPs.

![ZeroRadius Version](https://img.shields.io/badge/version-1.3.1-blue)
![Architecture](https://img.shields.io/badge/infrastructure-Docker_Compose-blueviolet)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![React](https://img.shields.io/badge/react-19-61dafb)
![FreeRADIUS](https://img.shields.io/badge/freeradius-3.2.3-orange)

## 🚀 Why ZeroRadius over daloRADIUS?

Historically, operating daloRADIUS meant fighting with raw SQL schemas, clunky 2000s PHP interfaces, and manual dictionary editing to provision modern devices. **ZeroRadius changes the paradigm:**
- **Visual Macro Builders:** Drag and drop RADIUS attributes instead of manually typing `radgroupreply` statements. Syntax constraints are strictly validated by `pyrad`.
- **Zero-Trust Identity Mapping:** Granular, NAS-based privilege scopes (ISO 27001 compliant) instead of granting global network access for every administrator.
- **RESTful Asynchronous Backend:** Built entirely on modern FastAPI + SQLAlchemy 2.0 Async, enabling massive high-concurrency without breaking a sweat.
- **Multi-Category Privilege Resolution:** Map users by exact IP, segment CIDR, exception range, or NAS category — with deterministic precedence. See [`docs/modules/access-policies.md`](docs/modules/access-policies.md).

## 🏗 Architecture & Stack (5 containers)

| Container | Image / Build | Purpose | Exposed ports |
|---|---|---|---|
| `radius-db` | `mariadb:10.11` | Standard FreeRADIUS schema extended with ZeroRadius identity tables | (internal 3306) |
| `radius-server` | `freeradius/freeradius-server:3.2.3` (in-repo Dockerfile) | 100% SQL-driven FreeRADIUS with custom NAS-based authorization policy | `1812/udp`, `1813/udp` |
| `radius-backend` | FastAPI + SQLAlchemy Async (in-repo Dockerfile) | REST + WebSocket API; Docker SDK access for log streaming | `8000` (via Nginx proxy) |
| `radius-syslog` | rsyslog forwarder (in-repo Dockerfile) | Forwards network device syslog into the audit database | `514/udp` |
| `radius-frontend` | React + Vite + Tailwind (in-repo Dockerfile) | Containerized UI served by Nginx | `3009` (HTTP), `443` (HTTPS) |

For a detailed component view, see [`docs/architecture.md`](docs/architecture.md).

## 📚 Official Documentation & User Manuals

### AI-Agent Onboarding
- [**00. Agent Quickstart**](docs/00-agent-quickstart.md) — clone → deploy → smoke-test → full pyramid in <10 minutes. Self-validating commands.

### Architecture & Operations
- [**Architecture**](docs/architecture.md) — components, networking, data flow, dependencies
- [**Deployment**](docs/deployment.md) — docker-compose stacks, env vars, secrets, troubleshooting
- [**Database**](docs/database.md) — schema reference, Alembic migrations, SQL views
- [**Testing**](docs/testing.md) — layered pyramid (Vitest + pytest + pyrad + Playwright)
- [**Security Coverage**](docs/security-coverage.md) — A01–A10 threat catalog with test mapping

### Feature Manuals
- [**01. NAS Provisioning & Huntgroups**](docs/01-nas-provisioning.md) — onboard hardware and segment by category
- [**02. ISO 27001 Privilege Map & RBAC**](docs/02-iso27001-privilege-map.md) — historical reference (deprecated; use Access Policies below)
- [**03. JIT "Break-Glass" Workflow**](docs/03-jit-break-glass.md) — timed operator elevation via `Expiration` attribute
- [**04. Live RADIUS Log Viewer**](docs/04-live-log-viewer.md) — WebSocket streaming of Access-Request events
- [**05. NAS Categories Management**](docs/05-nas-categories.md) — bulk operations + privilege mapping targets
- [**06. CIR Configuration**](docs/06-cir-configuration-manual.md) — *(legacy pointer — see [Modules / Access Policies](docs/modules/access-policies.md) for the current unified implementation)*

### Modules (per-feature reference for AI agents)
- [**Access Policies**](docs/modules/access-policies.md) *(Phase 2 — under construction)*
- [**Device Registry**](docs/modules/device-registry.md) *(Phase 2)*
- [**Network Segments**](docs/modules/network-segments.md) *(Phase 2)*
- [**NAS Categories**](docs/modules/nas-categories.md) *(Phase 2)*
- **Other modules** *(Phase 2)*

### Simulation Recipes for NACs registered in the system
*(Phase 3 — under construction)*

### Backwards Compatibility Notes

The codebase has unified what used to be called "Privilege Map" and "CIR Manager" into a single **Access Policies** module (PR #59, released in v1.3.0). Use [`docs/modules/access-policies.md`](docs/modules/access-policies.md) for the current source of truth. Older paths like `/privilege-map` may still resolve via legacy routing but the canonical path is now `/access-policies`.

## 🛠 Deployment & Setup

Quickstart:

```bash
# 1. Clone and configure environment
git clone https://github.com/alexandervazquez98/ZeroRadius.git
cd ZeroRadius
cp .env.example .env
$EDITOR .env  # fill MYSQL_*, SECRET_KEY, SYSLOG_API_KEY

# 2. Boot the full stack (5 containers)
docker compose up -d --build

# 3. Bootstrap the first superadmin account
docker exec -it radius-backend python -m scripts.seed_admin \
    --username admin --password "MyS3cur3P@ss!"

# 4. Validate readiness
curl -sS http://localhost:8000/health    # → {"status":"ok"}
open http://localhost:3009               # log in with bootstrap credentials
```

For full deployment options (Linux variant, test stack, TLS certs, secret rotation), see [`docs/deployment.md`](docs/deployment.md).

## ⚖️ Versioning

This release is **v1.3.1**. See [`CHANGELOG.md`](CHANGELOG.md) for the full history. The current version is also emitted by `GET /system/version` (backend) and shown in the footer (frontend).

## 🤝 For AI Agents and Automation

If you are an AI agent reading this repo to autonomously deploy, test, or simulate against registered NACs:
1. Start with [`docs/00-agent-quickstart.md`](docs/00-agent-quickstart.md).
2. All operational docs follow a self-validating contract: each step includes the expected output so you can stop and ask the human only on real divergence.
3. The [`docs/testing.md`](docs/testing.md) document catalogues fast vs. heavy test layers and how to skip infrastructure-dependent tests when the environment is not available.

---

Built with care for network operators who prefer SQL-driven, deterministic authorization flows over flighty web abstractions.

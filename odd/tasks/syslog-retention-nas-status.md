# Syslog retention and NAS reporting status

Objective: keep `syslog_events` partitions maintained with 3-month retention and show how many registered NAS are not sending syslog.
Branch: `feat/syslog-retention-nas-status` · Delivery: ask-on-risk · Runners: `./scripts/test-backend-fast.sh`, `./scripts/test-frontend-fast.sh`

## Specs

- S1 — "Vamos a crear esas particiones": monthly partitions of `syslog_events` must keep being created ahead of time (the static ones in `init.sql` end at `p202612`), so events never pile up in `pmax`.
- S2 — "vamos a almacenar 3 meses de logs de cada equipo": partitions older than the retention window (default 3 months, table-wide) are dropped automatically. User: "no importa borrar syslog historicos ya que aun no lo implemento en produccion".
- S3 — "cada NAS registrado debe de estar enviando logs, entonces ocupo algun indicador que me diga cuantos NAS no estan enviando informacion via syslogs". Threshold: "24 horas sin recibir algun mensaje" (configurable).
- S4 — The indicator is visible in the Syslog dashboard (count + list of silent NAS with last seen time).

Assumptions: retention is table-wide by monthly partition (keeps current month + previous 3 full months); a NAS whose `nasname` is a CIDR counts as reporting if any IP in that network sent syslog.

## Tasks

| ID | Specs | Route | Status | Commit |
|----|-------|-------|--------|--------|
| T1 | S1, S2 | inline | done (15 unit tests; verifier PASS, 0 blockers, A1/A2 hardened) | adf0ad4 |
| T2 | S3 | inline | done (7 integration tests RED 404 -> GREEN) | 24d5c2b |
| T3 | S4 | inline | done (3 Vitest RED import -> GREEN; 63/63 suite; vite build ok) | 358cdfc |

Risk: T1 item 1 (drops stored data by partition).

## Log

- L1 (2026-11-23, user): "Vamos a crear esas particiones, vamos a almacenar 3 meses de logs de cada equipo, ademas cada NAS registrado debe de estar enviando logs, entonces ocupo algun indicador que me diga cuantos NAS no estan enviando informacion via syslogs"
- L2 (2026-11-23, user): "24 horas sin recibir algun mensaje y como dices, no todos los equipos generan mensajes constantemente, no importa borrar syslog historicos ya que aun no lo implemento en produccino tienes libre albeldrio"
- L3: Test DB is in-memory SQLite, so partition DDL is unit-tested through a pure planner; live MySQL check goes to `dev` only with user confirmation.
- L4: Backend suite 542 passed, 2 failed, 2 skipped (--ignore tests/unit/test_auth_service.py: imports `jose`, not in requirements). Both failures (test_models_regression_parity access_policy_assignments) also fail at d5edc95 -> pre-existing.
- L5: Local env: repo backend/.venv is a Windows venv and frontend has no node_modules; tests ran from a scratch venv (no mysqlclient) and a scratch frontend copy. SQLite test DB cannot autoincrement BIGINT PK, so nas-status tests insert events directly.
- L6: Next: live MariaDB check of REORGANIZE/DROP on `dev` (needs user confirmation); Engram mirror pending (auto-mode blocked mem_save).
- L7: Independent verifier: S1/S2/S3 PASS, 630k planner cases, 0 blockers. Applied A1 (negative env -> default, not 0) and A2 (months ahead capped at 24). A3-A6 left as advisories.

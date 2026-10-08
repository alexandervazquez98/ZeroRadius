---
goal: Validate that each of the 16 vendor scenarios in `test_radius_vendor_scenarios.py` produces the expected verdict at the live FreeRADIUS server (not just in the mocked test).
audience: agent + human
prerequisites:
  - Healthy stack + admin JWT
  - `radius-tests/fixtures/seed_vendor_scenarios.sql` applied
  - NAS rows for each test scenario (`192.168.10.50` for proxy scenarios, etc.)
inputs:
  - vendor user rows + NAS rows
outputs:
  - 16 `radtest`-style Access-Accept / Reject verdicts, one per scenario
backout: drops seeded rows; the migration leaves the schema in place
---

# Simulation 02 — VSA Vendor Scenarios

> **Scope:** the 16 vendor scenarios introduced by commit `9e39084`
> (Cisco WLC, Dahua CCTV, Proxy-MAC, generic IP). Mirrors
> `radius-tests/test_radius_vendor_scenarios.py` so what passes in pytest
> also passes at the FreeRADIUS / MariaDB integration level.

## 1. Apply the seed

```bash
docker exec -i radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" \
    < radius-tests/fixtures/seed_vendor_scenarios.sql
```

**Expected output:** the apply completes with no errors. Verify the user
count:

```bash
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  SELECT COUNT(*) AS vendor_users
  FROM radcheck
  WHERE username LIKE 'vendor_%';
"
```

**Expected:** ~16 rows.

## 2. Probe each scenario (Cisco WLC pattern)

```bash
USERNAME="vendor_cisco_wlc_a"
PASSWORD="ciscopass!"
NAS_IP="192.168.20.10"   # set per-scenario in the table below
SECRET="vendor-cisco-wlc-secret"

docker exec radius-server bash -c "
  radtest $USERNAME $PASSWORD $NAS_IP 0 $SECRET 0 127.0.0.1
"
```

**Expected output:** ends with `Received Access-Accept Id N from $NAS_IP:1812`.

## 3. Scenario matrix

These mirror `test_radius_vendor_scenarios.py`. Run the matching rows.

| # | Vendor | User | NAS-IP | Group / reply |
|---|---|---|---|---|
| 1 | Cisco WLC | `vendor_cisco_wlc_a` | `192.168.20.10` | `Cisco-WLC-AVPair` |
| 2 | Cisco WLC | `vendor_cisco_wlc_b` | `192.168.20.11` | w/ `Called-Station-Id` |
| 3 | Cisco WLC | `vendor_cisco_wlc_c` | `192.168.20.12` | w/ `NAS-Identifier` |
| … | (see test file) | … | … | … |
| 14 | Dahua CCTV | `vendor_dahua_cctv_a` | `192.168.30.10` | `Dahua-*` VSA |
| 15 | Dahua CCTV | `vendor_dahua_cctv_b` | `192.168.30.11` | w/ `NAS-Port-Type` |
| 16 | Generic IP | `vendor_generic_ip_a` | `192.168.40.10` | simple `Reply-Message` |

> Run the file directly to enumerate scenarios:
>
> ```bash
> cd radius-tests
> pytest test_radius_vendor_scenarios.py -v --collect-only
> docker exec radius-server bash -c '
>   for u in $(mysql -h db -N -uroot -p"$MYSQL_ROOT_PASSWORD" \
>     -e "SELECT username FROM radcheck WHERE username LIKE \"vendor_%\"" 2>/dev/null); do
>     # replay… (you adapt this to per-user password and NAS-IP from the test)
>   done
> '
> ```

## 4. Validate via the live log viewer

`docker exec radius-server tail -F /var/log/freeradius/radius.log` (or the
WebSocket log viewer) should show one `Access-Accept` per scenario with
proper `NAS-IP-Address`, `Called-Station-Id`, `NAS-Identifier`, `NAS-Port-Type`
attributes.

## 5. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `Unknown VSA` from FreeRADIUS | Vendor dictionary not loaded | `/dictionary/upload` for the vendor `.dict` file |
| All scenarios `Access-Reject` | Seed didn't apply (table empty) | Re-run `seed_vendor_scenarios.sql` |
| `radpostauth` shows wrong `reply` attribute | Custom dictionary not picked up | `/dictionary/radius-logs?lines=100` for the last FreeRADIUS startup |
| Cisco WLC `shell:priv-lvl=15` reply missing or `Unknown VSA (Vendor-9/Cisco)` | `dictionary.cisco` not loaded in radius-server | This file ships in the repo at `backend/dictionaries/dictionary.cisco` (minimal `VENDOR Cisco 9` / `Cisco-AVPair 1 string`). If you replaced it via the UI, re-upload or re-drop-in; if it never loaded, run `docker exec radius-server grep Cisco-AVPair /etc/raddb/dictionary` and `/dictionary/builtin` to inspect |

## 6. Backout

```bash
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  DELETE FROM radcheck WHERE username LIKE 'vendor_%';
  DELETE FROM radusergroup WHERE username LIKE 'vendor_%';
  DELETE FROM radgroupreply WHERE groupname LIKE 'Vendor-%' OR groupname LIKE 'Cisco-%' OR groupname LIKE 'Dahua-%';
"
```

## Cross-references

- **Vendor test file:** [`radius-tests/test_radius_vendor_scenarios.py`](../../../radius-tests/test_radius_vendor_scenarios.py)
- **Dictionary module:** [`docs/modules/dictionaries.md`](../modules/dictionaries.md)
- **Vendor v4 type auto-convert:** [`docs/modules/dictionaries.md` § 3.1](../modules/dictionaries.md#31-upload)
- **Related:** [`docs/simulation/03-cambium-proxy-baseline.md`](03-cambium-proxy-baseline.md)

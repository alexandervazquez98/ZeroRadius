# RADIUS Protocol Tests

> **Status:** Refreshed for v1.3.0. Six test files (was three at v1.1.1). The
> `preconditions` probe guards against false positives when FreeRADIUS is
> reachable but `nas_based_authorization` is disabled.

Tests of the **RADIUS protocol** simulation using **pyrad**. They verify
authentication `Access-Request / Accept / Reject` and VSA handling at the
UDP level — i.e. they exercise the full FreeRADIUS + MariaDB pipeline
end-to-end.

## Prerequisites

- Python 3.11+
- Docker (to bring up FreeRADIUS)

## Installation

```bash
cd radius-tests/
pip install -r requirements.txt
```

## Bring up FreeRADIUS with Docker

The tests require a FreeRADIUS server running with the test users configured.

### Option A — Project docker compose (recommended)

The repository's root `docker-compose.yml` already has a `radius-server`
service. Make sure it is up:

```bash
# From the repository root
docker compose up radius-server -d
```

### Option B — Standalone FreeRADIUS for tests

```bash
docker run -d \
  --name freeradius-test \
  -p 1812:1812/udp \
  -p 1813:1813/udp \
  -e TESTING=yes \
  freeradius/freeradius-server:3.2

# Add a test user
docker exec freeradius-test bash -c "
  echo 'testuser Cleartext-Password := \"testpassword\"' \
    >> /etc/freeradius/3.0/mods-config/files/authorize
"
docker restart freeradius-test
```

### Verify the server is ready

```bash
radtest testuser testpassword 127.0.0.1 0 testing123
# Expected:
#   Sent Access-Request Id 1 from 0.0.0.0:... to 127.0.0.1:1812
#   Received Access-Accept Id 1 from 127.0.0.1:1812
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `RADIUS_HOST` | `127.0.0.1` | FreeRADIUS server IP |
| `RADIUS_PORT` | `1812` | UDP authentication port |
| `RADIUS_SECRET` | `testing123` | Shared secret for the test NAS |
| `RADIUS_MATRIX_PROBE_USER` | `segment_admin_a` | Precondition probe user |
| `RADIUS_MATRIX_PROBE_PASS` | `testpassword` | Probe password |
| `RADIUS_MATRIX_PROBE_NAS_IP` | `192.168.10.50` | NAS-IP that must resolve via the exact-IP rule |

```bash
# Remote server example
RADIUS_HOST=192.168.1.100 RADIUS_SECRET=mysecret pytest radius-tests/
```

## Run the tests

```bash
# All RADIUS tests (requires a running FreeRADIUS)
pytest radius-tests/ -v

# One test file at a time
pytest radius-tests/test_radius_auth.py -v
pytest radius-tests/test_radius_vsa.py -v
pytest radius-tests/test_radius_mac_priority.py -v
pytest radius-tests/test_radius_network_segments.py -v
pytest radius-tests/test_radius_preconditions.py -v
pytest radius-tests/test_radius_vendor_scenarios.py -v

# Deterministic segment/CIDR/CIR matrix (run via python -m pytest for Windows portability)
cd radius-tests
python -m pytest -m radius test_radius_network_segments.py -v
```

## Test files (six)

| File | Purpose | Count (approx.) |
|---|---|---|
| `test_radius_auth.py` | Basic Access-Request / Accept / Reject | ~6 |
| `test_radius_vsa.py` | VSA — Cisco `AVPair` validation | ~8 |
| `test_radius_mac_priority.py` | Cambium AP proxy baseline (direct vs proxied MAC priority) | ~10 |
| `test_radius_network_segments.py` | Deterministic segment precedence / CIDR / CIR matrix | ~25 |
| `test_radius_preconditions.py` | Probe contract (`nas_based_authorization` + seed) | ~5 |
| `test_radius_vendor_scenarios.py` | Cisco WLC, Dahua CCTV, Proxy-MAC, generic IP (16 scenarios added in `9e39084`) | 16 |

Total: ~70 RADIUS protocol scenarios.

## Deterministic seed for authorization matrix

The matrix of precedence / CIR scenarios uses an explicit seed at:
`radius-tests/fixtures/seed_authorization_matrix.sql`.

Expected objects (created by the seed; required by the probe and suite):

- Users: `segment_admin_a`, `segment_reader_b`
- Winning-rule markers: `MATRIX-EXACT-*`, `MATRIX-RANGE-*`, `MATRIX-BASE-*`, `MATRIX-FALLBACK-*`
- CIR (Access-Accept): `Cambium-Canopy-HPDLCIR`, `Cambium-Canopy-HPULCIR`

The `authorization_matrix_seed` fixture verifies that this contract exists
before the matrix runs. **Fail fast** if any expected object is missing.

## Cambium AP proxy baseline (real `.212` environment)

A second deterministic seed (`radius-tests/fixtures/seed_mac_priority.sql`)
backs the `test_radius_mac_priority.py` suite.

Coverage of the baseline:

- Direct AP login vs SM-via-proxy (same NAS-IP, differentiated by
  `Calling-Station-Id`).
- Reader group with one reply attribute (`Cambium-Canopy-UserLevel := 1`).
- Reader group with two reply attributes (`UserLevel` + `UserMode`),
  hydrated natively.
- Group with both `radgroupcheck` and `radgroupreply`.
- Zero-trust Access-Reject when no mapping matches.

Note on the current baseline:

- `nas_based_authorization` still resolves `SQL-Group` correctly.
- Group attribute hydration in `Access-Accept` happens through the native
  `rlm_sql` path.

## Vendor-specific baseline

A third deterministic seed (`radius-tests/fixtures/seed_vendor_scenarios.sql`)
backs the `test_radius_vendor_scenarios.py` suite, exercising Cisco WLC,
Dahua CCTV, proxy-MAC, and generic IP variants. Required by the `9e39084`
commit.

## Probe of precondition (active wiring)

The `radius_policy_precondition` fixture separates three cases:

1. **Server unreachable / timeout** → `pytest.skip` (infra not available).
2. **Server reachable but expected marker / CIR missing** →
   `pytest.fail("nas_based_authorization disabled or seed missing")`.
3. **Server + wiring + seed OK** → runs the precedence matrix.

This prevents false positives when FreeRADIUS is up but not actually running
`nas_based_authorization`.

## Excluding RADIUS tests from the main suite

RADIUS tests are marked `@pytest.mark.radius`. To run the backend without
requiring FreeRADIUS:

```bash
# From backend/
pytest -m "not radius" -v
```

## Behaviour when FreeRADIUS is not available

When the server does not respond, the `skip_if_no_radius` fixture detects it
and **skips** the test automatically with a clear message (does **not** fail):

```
SKIPPED [1] conftest.py:XX: FreeRADIUS server not reachable at 127.0.0.1:1812.
Run with Docker: see radius-tests/README.md
```

When the server is reachable but the expected marker / CIR does not appear
in the probe reply, the matrix fails explicitly:

```
nas_based_authorization disabled or seed missing
```

## Layout

```
radius-tests/
├── conftest.py                                   # fixtures
├── pytest.ini                                    # markers (radius)
├── test_radius_auth.py
├── test_radius_vsa.py
├── test_radius_mac_priority.py
├── test_radius_network_segments.py
├── test_radius_preconditions.py
├── test_radius_vendor_scenarios.py
├── dictionary                                    # FreeRADIUS test dictionary
├── fixtures/
│   ├── seed_authorization_matrix.sql
│   ├── seed_mac_priority.sql
│   └── seed_vendor_scenarios.sql
├── requirements.txt                              # pyrad, pytest
└── README.md                                     # this file
```

## Cross-references

- **Architecture / auth flow:** [`docs/architecture.md` § 2.2](../docs/architecture.md#22-nac--radius-authentication)
- **FreeRADIUS policy file:** `radius/policy.d/nas_based_authorization`
- **Backend pytest markers:** [`docs/testing.md`](../docs/testing.md#markers)
- **Live log viewer (post-auth trail):** [`docs/04-live-log-viewer.md`](../docs/04-live-log-viewer.md)

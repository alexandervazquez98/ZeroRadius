# CIR Configuration and Behavior — **LEGACY POINTER**

> **This document is superseded.** What used to be called "CIR Manager" was
> unified into the **Access Policies** module in v1.3.0 (PR #59). The CIR
> resolution logic now lives under `/api/v1/circuits` (the **Circuits**
> module), driven by `AccessPolicyAssignment.cir_id`.
>
> **Canonical references:**
> - Access Policies (unified module): [`docs/modules/access-policies.md`](modules/access-policies.md)
> - Circuits (CIR model + resolution): [`docs/modules/circuits.md`](modules/circuits.md)
> - Bandwidth profiles (CIR parameters): [`docs/modules/access-policies.md` § 2](modules/access-policies.md#2-url-surface)
>
> The original document is preserved below for historical / archaeological
> purposes — its claims about "no CIR UI" no longer hold (there is now a
> dedicated `CircuitPage.jsx` and router `circuits.py`).

---

<!--
  BEGIN LEGACY CONTENT (preserved; do not edit for accuracy — represents
  the state at v1.2.0 before the unified module landed).
-->

## 1) Is there a dedicated CIR UI?

**No.** There is currently **no dedicated CIR page, wizard, or metrics
dashboard** in the frontend. *(NOTE: this was true at v1.2.0; the
`CircuitPage.jsx` and the circuits/circuit_service.py module shipped in
v1.3.0.)*

What existed at v1.2.0 was an indirect flow:

- CIR values were stored as normal **RADIUS group reply attributes** (e.g.
  `Cambium-Canopy-HPDLCIR`, `Cambium-Canopy-HPULCIR`) in **Groups**.
- A user/target was mapped to a **RADIUS group** in **Access Policies**.
- During authentication, FreeRADIUS policy `nas_based_authorization` resolved
  the winning group (`SQL-Group`) and the SQL module hydrated group
  attributes into `Access-Accept`.

## 2) Where admins started in the app (pre-v1.3.0)

1. **Groups** (`/groups`) — define or edit the RADIUS group attributes that
   contain CIR values.
2. **NAS Devices** (`/nas`) — ensure NAS entries exist and are categorised
   correctly when using category fallback.
3. **Network Segments** (`/network-segments`) — optional but recommended if
   using segment/base/exception targeting.
4. **Access Policies** (`/privilege-map`) — bind user + target to the
   RADIUS group that contains CIR attributes.

> **Paths at v1.2.0:** the Access Policies route was `/privilege-map`. It is
> now `/access-policies`. See
> [`docs/modules/access-policies.md`](modules/access-policies.md).

## 3) Step-by-step flow (pre-v1.3.0 path)

### Step A — Define CIR attributes in a RADIUS group

1. Go to **Groups**.
2. Select or create a group (policy).
3. Add **Reply** attributes with CIR values:
   - `Cambium-Canopy-HPDLCIR := 5000`
   - `Cambium-Canopy-HPULCIR := 2000`

### Step B — Bind user to the CIR-carrying group via Access Policies

1. Go to **Access Policies**.
2. Select user.
3. Create policy targeting the desired NAS IP / segment / category.
4. Set **RADIUS Group (Policy)** to the group configured in Step A.

At authentication time, the winning policy decides the `SQL-Group`, and CIR
attributes were hydrated from that group's reply attributes by `rlm_sql`.

## 4) Priority / precedence rules (still in force in v1.3.0)

The same chain applied:

1. **Exact NAS IP** (most specific)
2. **Segment exception range** (narrower ranges preferred)
3. **Segment base policy** (more-specific CIDR preferred)
4. **Category fallback** (via `nas_cidr_ranges` view)
5. **No match → reject** (`Reply-Message: Access denied: NAS not authorized for this user`)

> **Now formalized in:** [`docs/modules/access-policies.md` § 4](modules/access-policies.md#4-precedence--priority--fallback-chain).

## 5) Known limitations at v1.2.0 (now resolved in v1.3.0)

| Limitation then | Resolution now |
|---|---|
| No dedicated CIR editor | `frontend/src/pages/CircuitPage.jsx` |
| No CIR telemetry screen | *(planned, `sdd/cir-metrics-ui`)* |
| CIR validation generic | `BandwidthProfile` validates down/up/burst |
| Category target behind Advanced/Legacy | Category now a first-class target option |
| Runtime verification indirect | `/api/v1/circuits/resolve` returns the trace |

## Reference implementation points (still relevant)

- Backend/API: `backend/app/routers/{groups,privilege_map,network_segments}.py`
- FreeRADIUS policy: `radius/policy.d/nas_based_authorization`
- SQL view: `database/init.sql` → `nas_cidr_ranges`

<!--
  END LEGACY CONTENT
-->

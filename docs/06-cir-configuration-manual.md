# CIR Configuration and Behavior (Current Implementation)

This manual documents how CIR is configured and applied **today** in ZeroRadius, based on the current codebase.

## 1) Is there a dedicated CIR UI?

**No.** There is currently **no dedicated CIR page, wizard, or metrics dashboard** in the frontend.

What exists today is an indirect flow:

- CIR values are stored as normal **RADIUS group reply attributes** (for example `Cambium-Canopy-HPDLCIR`, `Cambium-Canopy-HPULCIR`) in **Groups**.
- A user/target is mapped to a **RADIUS group** in **Access Policies**.
- During authentication, FreeRADIUS policy `nas_based_authorization` resolves the winning group (`SQL-Group`) and the SQL module hydrates group attributes into `Access-Accept`.

---

## 2) Where admins start in the app

From the left sidebar, the operational path is:

1. **Groups** (`/groups`) — define or edit the RADIUS group attributes that contain CIR values.
2. **NAS Devices** (`/nas`) — ensure NAS entries exist and are categorized correctly when using category fallback.
3. **Network Segments** (`/network-segments`) — optional but recommended if using segment/base/exception targeting.
4. **Access Policies** (`/privilege-map`) — bind user + target to the RADIUS group that contains CIR attributes.

> Role notes (current behavior):
>
> - **Access Policies view**: `auditor`, `admin`, `superadmin`
> - **Access Policies create/update**: `admin`, `superadmin`
> - **Network Segments create/update**: `admin`, `superadmin`

---

## 3) Step-by-step flow (current path)

### Step A — Define CIR attributes in a RADIUS group

1. Go to **Groups**.
2. Select or create a group (policy).
3. Add **Reply** attributes with CIR values, for example:
   - `Cambium-Canopy-HPDLCIR := 5000`
   - `Cambium-Canopy-HPULCIR := 2000`
   - (optional) `Cambium-Canopy-LPDLCIR`, `Cambium-Canopy-LPULCIR`

Important: CIR is currently handled as generic group attributes. The UI does not enforce CIR-specific validation beyond regular attribute/value entry.

### Step B — Prepare targeting data

Depending on how you want policy matching to work:

- **Exact NAS IP**: make sure the NAS IP exists as targetable value.
- **Segment base/exception**:
  1. Create the segment in **Network Segments** (name + CIDR).
  2. If using exceptions, define start/end IP ranges under that segment when creating Access Policies.
- **Category fallback**:
  1. Ensure NAS has a category in **NAS Devices**.
  2. Ensure a category-based policy exists in Access Policies.

### Step C — Bind user to the CIR-carrying group

1. Go to **Access Policies**.
2. Select user.
3. Create policy with a target mode:
   - `Network Segment` (base)
   - `IP or Range (Exception)`
   - `Specific NAS / IPs (Legacy)`
   - `Category` (shown via **Advanced / Legacy Compatibility** in create flow)
4. Set **RADIUS Group (Policy)** to the group configured in Step A.
5. Save policy.

At authentication time, the winning policy decides the `SQL-Group`, and CIR attributes are hydrated from that group’s reply attributes by `rlm_sql`.

---

## 4) Priority / precedence rules (enforced at runtime)

Current precedence is implemented in `radius/policy.d/nas_based_authorization`:

1. **Exact NAS IP or segment exception range** (most specific)
   - Exact `nas_ip` wins first.
   - If range exceptions apply, narrower ranges are preferred (ordered by range size).
2. **Segment base policy**
   - If no exact/range match, resolve by segment CIDR containment.
   - More specific segment CIDR (larger prefix length) is preferred.
3. **Category fallback**
   - If no segment/IP match, resolve NAS category via `nas_cidr_ranges` view.
4. **No match => reject**
   - Request is rejected with `Reply-Message: Access denied: NAS not authorized for this user`.

After a winning group is selected, group attributes are hydrated from `radgroupcheck`/`radgroupreply` through the SQL module.

Native hydration is the official/default path. `nas_based_authorization` resolves `control:SQL-Group`, and the SQL module hydrates `radgroupcheck`/`radgroupreply` attributes in the authorize flow.

---

## 5) What this improves operationally

- **Deterministic authorization path**: predictable winner between exact IP, exception, segment base, and category fallback.
- **Centralized CIR control**: operators edit CIR values once at group level, then reuse via policy mappings.
- **Safer authorization behavior**: if no valid mapping exists, access is rejected (Zero Trust posture).
- **Scalable targeting**: supports granular exceptions plus broader segment/category patterns.

---

## 6) Known limitations / current gaps

1. **No CIR-specific UX**
   - No dedicated CIR editor, templates, validation panel, or preview.

2. **No CIR telemetry screen**
   - No built-in CIR metrics page/graph showing effective rates per auth event.

3. **CIR validation is generic**
   - CIR values are entered as plain attribute values in Groups; domain validation is limited.

4. **Category target discoverability in Access Policies**
   - In create mode, category targeting is exposed through **Advanced / Legacy Compatibility**, not as a first-class main option.

5. **Runtime verification is indirect**
   - Operators validate effects via RADIUS logs/tests rather than a dedicated “effective CIR” UI.

---

## 7) Reference implementation points

- Frontend
  - `frontend/src/components/Layout.jsx` (navigation entry points)
  - `frontend/src/pages/Policies.jsx` (group attributes UI)
  - `frontend/src/pages/PrivilegeMap.jsx` (targeting + policy-group binding)
  - `frontend/src/pages/NetworkSegments.jsx` (segment CRUD)

- Backend/API
  - `backend/app/routers/groups.py` (group reply/check CRUD)
  - `backend/app/routers/privilege_map.py` (policy mapping CRUD and validations)
  - `backend/app/routers/network_segments.py` (segment validation/overlap protections)
  - `database/init.sql` (`nas_cidr_ranges` view)

- FreeRADIUS policy
  - `radius/policy.d/nas_based_authorization` (precedence and CIR reply hydration)

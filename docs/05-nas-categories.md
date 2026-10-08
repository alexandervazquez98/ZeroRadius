# NAS Categories Management

> **Status:** Refreshed. This document is the human-facing counterpart to
> [`docs/modules/nas-categories.md`](modules/nas-categories.md). The module
> doc has the API contract and the agent-runnable recipe; this doc has the
> UI / operational playbook.

ZeroRadius introduces **NAS Categories** to organise and manage groups of
similar Network Access Servers (NAS). Categories enable streamlined bulk
operations, simplified privilege mapping, and better organisational
visibility.

## Why NAS Categories?

In large-scale network deployments, administrators often need to manage
hundreds of devices across multiple locations or types. NAS Categories solve
several challenges:

- **Bulk Operations:** Apply policies to entire categories at once instead
  of individual devices.
- **Privilege Mapping:** Assign user privileges based on category (e.g.,
  "All Core Routers") rather than specific IPs.
- **Visual Organization:** Filter and search NAS devices by category in the
  dashboard.
- **Vendor-Specific Configurations:** Group devices by vendor for tailored
  attribute sets.

## Creating a NAS Category

The UI: **NAS Devices → Settings icon → Manage Categories → Add Category**.

The API: [`docs/modules/nas-categories.md` § 5](modules/nas-categories.md#5-end-to-end-agent-run).

| Field | Description | Required |
|-------|-------------|----------|
| **Name** | Category identifier (e.g., "Core Routers") | Yes |
| **Description** | Brief description | No |
| **Criticality** | `standard` / `restricted` / `critical` | Yes |
| **Vendor** | Reference only (e.g., Cisco, Juniper) | No |

### Criticality Levels

- **Standard** — regular devices, standard access.
- **Restricted** — additional approval required for access.
- **Critical** — high-security infrastructure (core routers, firewalls).
  Sort order: criticality DESC (most-critical first).

## Assigning Categories to NAS Devices

When creating or editing a NAS device, select the **Category** dropdown.
The category is stored in `nas.category_id` and used throughout the system
for filtering and privilege evaluation.

## Using Categories in Privilege Mapping

In **Access Policies**, you can map a user to an entire category instead of
a specific IP. This is particularly useful for:

- **Network operators** who need access to all devices in a region.
- **Vendor support** who may need temporary access to all devices of a
  specific type.
- **Departmental segmentation** grouping devices by department or location.

### Example Workflow

1. Create categories: "Branch Offices", "Data Center", "WiFi Controllers".
2. Assign NAS devices to their respective categories.
3. In **Access Policies**, create category-based mappings:
   - User `jsmith` → Category "Data Center" → Group "DC-Admins"
   - User `jsmith` → IP `10.1.1.50` → Group "DC-Specific" (exception)

## Best Practices

1. **Naming Conventions:** Use consistent naming (e.g., `DC-Core`, `Branch-LA`).
2. **Criticality:** Assign `critical` only to essential infrastructure.
3. **Audit Review:** Regularly review category assignments.
4. **Documentation:** Use the description field to document the purpose of
   each category.

## Cross-references

- **Module / API:** [`docs/modules/nas-categories.md`](modules/nas-categories.md)
- **API endpoints:** [`docs/api-reference.md`](api-reference.md)
- **Access Policies precedence:** [`docs/modules/access-policies.md`](modules/access-policies.md#4-precedence--priority--fallback-chain)
- **Device Registry (uses category_id too):** [`docs/modules/device-registry.md`](modules/device-registry.md)

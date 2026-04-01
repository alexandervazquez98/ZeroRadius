# NAS Categories Management

ZeroRadius introduces **NAS Categories** to organize and manage groups of similar Network Access Servers (NAS) devices. Categories enable streamlined bulk operations, simplified privilege mapping, and better organizational visibility.

## Why NAS Categories?

In large-scale network deployments, administrators often need to manage hundreds of devices across multiple locations or types. NAS Categories solve several challenges:

- **Bulk Operations:** Apply policies to entire categories at once instead of individual devices
- **Privilege Mapping:** Assign user privileges based on category (e.g., "All Core Routers") rather than specific IPs
- **Visual Organization:** Filter and search NAS devices by category in the dashboard
- **Vendor-Specific Configurations:** Group devices by vendor for tailored attribute sets

## Creating a NAS Category

1. Navigate to the **NAS Devices** module
2. Click the **Settings** icon (or "Manage Categories" button)
3. In the Category Manager panel, click **Add Category**
4. Fill in the details:

| Field | Description | Required |
|-------|-------------|----------|
| **Name** | Category identifier (e.g., "Core Routers", "WiFi Controllers") | Yes |
| **Description** | Brief description of the category | No |
| **Criticality** | Security level: `standard`, `restricted`, or `critical` | Yes |
| **Vendor** | Device vendor for reference (e.g., Cisco, Juniper) | No |

### Criticality Levels

- **Standard:** Regular network devices with standard access requirements
- **Restricted:** Devices requiring additional approval for access
- **Critical:** High-security infrastructure (core routers, firewalls) with strict access controls

## Assigning Categories to NAS Devices

When creating or editing a NAS device, you can assign it to a category:

1. In the NAS form, select the **Category** dropdown
2. Choose the appropriate category
3. Save the NAS device

The category is stored in the `nas` table's `category_id` field and used throughout the system for filtering and privilege evaluation.

## Using Categories in Privilege Mapping

Instead of mapping a user to specific IP addresses, you can map them to an entire category. This is particularly useful for:

- **Network Operators:** Who need access to all devices in a region
- **Vendor Support:** Who may need temporary access to all devices of a specific type
- **Departmental Segmentation:** Grouping devices by department or location

### Example Workflow

1. Create categories: "Branch Offices", "Data Center", "WiFi Controllers"
2. Assign NAS devices to their respective categories
3. In **Privilege Map**, create category-based mappings:
   - User "jsmith" → Category "Data Center" → Group "DC-Admins"
   - User "jsmith" → IP "10.1.1.50" → Group "DC-Specific" (exception)

The system evaluates IP-based mappings first, then falls back to category-based mappings.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/nas-categories` | List all NAS categories |
| GET | `/api/v1/nas-categories/{id}` | Get a specific category |
| POST | `/api/v1/nas-categories` | Create a new category |
| PUT | `/api/v1/nas-categories/{id}` | Update a category |
| DELETE | `/api/v1/nas-categories/{id}` | Delete a category |

### Schema

```python
# Request/Response schema
{
    "id": 1,
    "name": "Core Routers",
    "description": "Primary core routing infrastructure",
    "criticality": "critical",
    "vendor": "Cisco",
    "created_at": "2026-04-01T10:00:00Z"
}
```

## Best Practices

1. **Naming Conventions:** Use consistent naming (e.g., "DC-Core", "Branch-LA", "WiFi-HQ")
2. **Criticality:** Assign `critical` only to essential infrastructure
3. **Audit Review:** Regularly review category assignments to ensure accuracy
4. **Documentation:** Use the description field to document the purpose of each category

# Module — RADIUS user passwords

How ZeroRadius stores, resets and hands over RADIUS user passwords
(`radcheck` password rows). Admin panel accounts are a different module:
see [`admin-users.md`](admin-users.md).

## 1. Write-only passwords

- The API never returns a password value: password rows come back with
  `value: null` and `has_password: true` (#101 A). The Users page shows
  "(password set)".
- Audit entries for password rows store `"value": "***"`.
- Settable types: `Cleartext-Password`, `MD5-Password`, `NT-Password`.
  Which NAS each type works with is in
  [`docs/01-nas-provisioning.md`](../01-nas-provisioning.md#3-vendor-notes).

## 2. Admin reset (#101 B)

Users → key button on a password row → **Reset password**:

- **Set password**: type it once (never echoed back).
- **Generate password**: the server creates one and shows it **once**.

API: `POST /users/check/{id}/reset-password`. Audited as `PASSWORD_RESET`
without the value. A reset revokes any pending setup link.

## 3. Self-service setup link (#101 C)

For users who should choose their own password, so the operator never
knows it.

1. Users → key button → choose the password type → **Generate setup link**.
2. The modal shows the URL `https://<zeroradius>/setup-password/<token>`
   **once**. Copy it and send it to the user by email yourself; ZeroRadius
   does not send email.
3. **The user's current password is blocked immediately.** The user
   cannot authenticate on any NAS until they open the link and set a new
   password.
4. The user opens the link (no login), enters the password twice, and it
   is stored with the type chosen in step 1.

Rules:

| Rule | Behavior |
|---|---|
| Lifetime | 72 hours from generation |
| Use | Once. A second attempt gets "already used" |
| New link for the same user | Replaces the previous one ("replaced or cancelled") |
| Admin reset while pending | Cancels the link |
| Link expires unused | The user stays blocked; generate a new link or reset the password |
| Storage | Only the SHA-256 of the token is stored (`password_setup_links`) |

The Users table shows the latest link of each password row:

- **Setup link pending · by `<admin>` · valid until `<date>`**: the URL still works.
- **Setup link expired `<date>` · by `<admin>`**: the URL no longer works.
- **Set via link `<date>` · by `<admin>`**: the user already set the password.

Audit: `PASSWORD_SETUP_LINK_CREATED` (admin, type, expiry) and
`PASSWORD_SETUP_LINK_USED` (user, type, who created the link). Neither
records the token or the password.

API: `POST /users/check/{id}/setup-link` (admin/superadmin), public
`GET`/`POST /password-setup/{token}`. See
[`docs/api-reference.md`](../api-reference.md).

## 4. Cross-references

- [`docs/api-reference.md`](../api-reference.md)
- [`docs/modules/audit.md`](audit.md)
- [`docs/01-nas-provisioning.md`](../01-nas-provisioning.md)

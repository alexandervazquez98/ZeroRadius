-- Deterministic seed for huntgroup-enforcement regression coverage (closes #92).
-- Scope: radgroupcheck enforcement in the FreeRADIUS authorize section.
-- Four scenarios:
--   1. oficina-admin has radgroupcheck NAS-IP-Address == 192.168.1.10
--      + radgroupreply shell:priv-lvl=15 → matching NAS → Access-Accept
--   2. oficina-admin (same group) → non-matching NAS → Access-Reject
--   3. branch-read has NO radgroupcheck rows + radgroupreply priv-lvl=1
--      → Access-Accept (regression guard)
--   4. carlos.ruiz has NO radusergroup row → Access-Accept (regression guard)

START TRANSACTION;

-- Clean previous deterministic objects
DELETE FROM radgroupreply
WHERE groupname IN (
  'grp_huntgroup_oficina_admin',
  'grp_huntgroup_branch_read'
);

DELETE FROM radgroupcheck
WHERE groupname IN (
  'grp_huntgroup_oficina_admin',
  'grp_huntgroup_branch_read'
);

DELETE FROM radusergroup
WHERE username IN (
  'juan.perez',
  'maria.lopez',
  'carlos.ruiz'
);

DELETE FROM radcheck
WHERE username IN (
  'juan.perez',
  'maria.lopez',
  'carlos.ruiz'
);

DELETE FROM access_policy_assignments
WHERE username IN (
  'juan.perez',
  'maria.lopez',
  'carlos.ruiz'
);

-- Users for huntgroup enforcement matrix
INSERT INTO radcheck (username, attribute, op, value) VALUES
('juan.perez', 'Cleartext-Password', ':=', 'testpassword'),
('maria.lopez', 'Cleartext-Password', ':=', 'testpassword'),
('carlos.ruiz', 'Cleartext-Password', ':=', 'testpassword');

-- Groups (reply side) and check side for oficina-admin
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
('grp_huntgroup_oficina_admin', 'Cisco-AVPair', ':=', 'shell:priv-lvl=15'),
('grp_huntgroup_branch_read', 'Cisco-AVPair', ':=', 'shell:priv-lvl=1');

-- oficina-admin: locked to a single NAS-IP (the enforcement rule)
INSERT INTO radgroupcheck (groupname, attribute, op, value) VALUES
('grp_huntgroup_oficina_admin', 'NAS-IP-Address', '==', '192.168.1.10');

-- branch-read: NO radgroupcheck rows (regression guard — must keep returning accept)
-- (intentionally no INSERT INTO radgroupcheck for grp_huntgroup_branch_read)

-- radusergroup wiring
-- juan.perez belongs to oficina-admin (the group with a check rule)
-- maria.lopez belongs to branch-read (the group with no check rule)
-- carlos.ruiz intentionally has NO radusergroup row
INSERT INTO radusergroup (username, groupname, priority) VALUES
('juan.perez', 'grp_huntgroup_oficina_admin', 0),
('maria.lopez', 'grp_huntgroup_branch_read', 0);

-- access_policy_assignments (target_key follows backend AccessPolicyAssignment.compute_target_key())
-- safe(val) => "<len>:<value>" and NULL => "4:None"
INSERT INTO access_policy_assignments
  (username, target_key, nas_ip, calling_station_id, radius_group, privilege_level, is_active)
VALUES
  -- juan.perez @ 192.168.1.10 (matching NAS — should pass check)
  (
    'juan.perez',
    SHA2(CONCAT(
      '10:juan.perez|12:192.168.1.10|4:None|4:None|4:None|4:None|4:None'
    ), 256),
    '192.168.1.10',
    NULL,
    'grp_huntgroup_oficina_admin',
    '15',
    1
  ),
  -- juan.perez @ 192.168.1.50 (mismatching NAS — should fail check under fixed config)
  (
    'juan.perez',
    SHA2(CONCAT(
      '10:juan.perez|12:192.168.1.50|4:None|4:None|4:None|4:None|4:None'
    ), 256),
    '192.168.1.50',
    NULL,
    'grp_huntgroup_oficina_admin',
    '15',
    1
  ),
  -- maria.lopez @ 192.168.1.50 (regression: group with no check must still accept)
  (
    'maria.lopez',
    SHA2(CONCAT(
      '11:maria.lopez|12:192.168.1.50|4:None|4:None|4:None|4:None|4:None'
    ), 256),
    '192.168.1.50',
    NULL,
    'grp_huntgroup_branch_read',
    '1',
    1
  ),
  -- carlos.ruiz @ 192.168.1.50 (regression: user with no radusergroup must still accept)
  (
    'carlos.ruiz',
    SHA2(CONCAT(
      '11:carlos.ruiz|12:192.168.1.50|4:None|4:None|4:None|4:None|4:None'
    ), 256),
    '192.168.1.50',
    NULL,
    'grp_huntgroup_branch_read',
    '1',
    1
  );

COMMIT;

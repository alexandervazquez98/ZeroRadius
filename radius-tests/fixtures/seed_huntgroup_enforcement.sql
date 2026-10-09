-- Deterministic seed for huntgroup enforcement testing (closes #92).
-- Scope: verify that radgroupcheck rows are enforced at the FreeRADIUS
-- authorize section. A user authenticating against a NAS that fails any
-- of the group's check items is rejected.
--
-- Four spec scenarios (from spec.md):
--   1) juan.perez + oficina-admin (radgroupcheck NAS-IP=192.168.1.10)
--      + matching NAS-IP (192.168.1.10) -> Access-Accept with reply attrs
--   2) juan.perez + oficina-admin (radgroupcheck NAS-IP=192.168.1.10)
--      + non-matching NAS-IP (192.168.1.50) -> Access-Reject
--   3) maria.lopez + branch-read (no radgroupcheck) -> Access-Accept
--   4) carlos.ruiz (no radusergroup, access_policy_assignments only)
--      + branch-read (no radgroupcheck) -> Access-Accept (regression guard)
--
-- Usage:
--   docker exec -i zeroradius-test-db mysql -utest_user -ptest_password zeroradius_test < seed_huntgroup_enforcement.sql
--   docker restart zeroradius-test-radius

START TRANSACTION;

-- Clean previous huntgroup enforcement objects
DELETE FROM access_policy_assignments WHERE username IN (
    'juan.perez',
    'maria.lopez',
    'carlos.ruiz'
);

DELETE FROM radusergroup WHERE username IN (
    'juan.perez',
    'maria.lopez',
    'carlos.ruiz'
);

DELETE FROM radcheck WHERE username IN (
    'juan.perez',
    'maria.lopez',
    'carlos.ruiz'
);

DELETE FROM radgroupreply WHERE groupname IN (
    'oficina-admin',
    'branch-read'
);

DELETE FROM radgroupcheck WHERE groupname IN (
    'oficina-admin',
    'branch-read'
);

DELETE FROM nas WHERE shortname IN (
    'huntgroup-test-runner',
    'huntgroup-matching-nas',
    'huntgroup-mismatching-nas'
);

-- Users for spec scenarios
INSERT INTO radcheck (username, attribute, op, value) VALUES
('juan.perez', 'Cleartext-Password', ':=', 'testpassword'),
('maria.lopez', 'Cleartext-Password', ':=', 'testpassword'),
('carlos.ruiz', 'Cleartext-Password', ':=', 'testpassword');

-- Groups
-- oficina-admin: enforces NAS-IP == 192.168.1.10 (radgroupcheck)
INSERT INTO radgroupcheck (groupname, attribute, op, value) VALUES
('oficina-admin', 'NAS-IP-Address', '==', '192.168.1.10');

INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
('oficina-admin', 'Reply-Message', ':=', 'HUNTGROUP-OFICINA-ADMIN'),
('oficina-admin', 'Cisco-AVPair', ':=', 'shell:priv-lvl=15'),
('branch-read', 'Reply-Message', ':=', 'HUNTGROUP-BRANCH-READ'),
('branch-read', 'Cisco-AVPair', ':=', 'shell:priv-lvl=1');

-- radusergroup for scenarios 1, 2, 3
-- juan.perez + maria.lopez use radusergroup. carlos.ruiz does NOT (scenario 4).
INSERT INTO radusergroup (username, groupname, priority) VALUES
('juan.perez', 'oficina-admin', 0),
('maria.lopez', 'branch-read', 0);

-- access_policy_assignments for each user
-- Scenario 1: juan.perez routes to oficina-admin from 192.168.1.10
-- Scenario 2: juan.perez routes to oficina-admin from 192.168.1.50 (mismatch)
-- Scenario 3: maria.lopez routes to branch-read from 192.168.1.50
-- Scenario 4: carlos.ruiz routes to branch-read from 192.168.1.50 (no radusergroup)
INSERT INTO access_policy_assignments
    (username, target_key, nas_ip, calling_station_id, radius_group, privilege_level, is_active)
VALUES
    ('juan.perez', SHA2(CONCAT('juan.perez|12:192.168.1.10|4:None|4:None|4:None|4:None|4:None'), 256), '192.168.1.10', NULL, 'oficina-admin', '15', 1),
    ('juan.perez', SHA2(CONCAT('juan.perez|12:192.168.1.50|4:None|4:None|4:None|4:None|4:None'), 256), '192.168.1.50', NULL, 'oficina-admin', '15', 1),
    ('maria.lopez', SHA2(CONCAT('maria.lopez|12:192.168.1.50|4:None|4:None|4:None|4:None|4:None'), 256), '192.168.1.50', NULL, 'branch-read', '1', 1),
    ('carlos.ruiz', SHA2(CONCAT('carlos.ruiz|12:192.168.1.50|4:None|4:None|4:None|4:None|4:None'), 256), '192.168.1.50', NULL, 'branch-read', '1', 1);

-- NAS entries required for FreeRADIUS to accept the test requests.
-- Without these, requests from these IPs are dropped before reaching
-- nas_based_authorization (FreeRADIUS rejects unknown clients).
-- 127.0.0.1 is the test client (the runner), 192.168.1.10 is the matching
-- NAS in scenario 1, 192.168.1.50 is the mismatching NAS in scenario 2
-- and the source for scenarios 3 and 4.
INSERT INTO nas (nasname, shortname, type, secret, description) VALUES
('127.0.0.1', 'huntgroup-test-runner', 'other', 'testing123', 'Huntgroup test runner NAS client'),
('192.168.1.10', 'huntgroup-matching-nas', 'Cisco', 'testing123', 'Matching NAS for oficina-admin'),
('192.168.1.50', 'huntgroup-mismatching-nas', 'Cisco', 'testing123', 'Mismatching NAS / branch-read source')
ON DUPLICATE KEY UPDATE shortname=VALUES(shortname);

COMMIT;

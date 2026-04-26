-- Seed for vendor-specific RADIUS test scenarios.
-- Covers: Proxy-MAC via parent NAS, Cisco WLC, Dahua CCTV, Generic IP devices.
-- Uses radusergroup + access_policy_assignments for authorization.
--
-- Usage:
--   docker exec -i zeroradius-test-db mysql -utest_user -ptest_password zeroradius_test < seed_vendor_scenarios.sql
--   docker restart zeroradius-test-radius

START TRANSACTION;

-- Clean previous vendor scenario objects
DELETE FROM radusergroup WHERE username IN (
    'proxy_child_device',
    'cisco_wlc_admin',
    'cisco_wlc_operator',
    'dahua_camera_lobby',
    'dahua_camera_entrance',
    'dahua_unknown_camera',
    'genericPrinter'
);

DELETE FROM radcheck WHERE username IN (
    'proxy_child_device',
    'cisco_wlc_admin',
    'cisco_wlc_operator',
    'dahua_camera_lobby',
    'dahua_camera_entrance',
    'dahua_unknown_camera',
    'genericPrinter'
);

DELETE FROM radgroupreply WHERE groupname IN (
    'grp_proxy_child',
    'grp_cisco_wlc_priv',
    'grp_cisco_wlc_operator',
    'grp_dahua_camera',
    'grp_generic_device'
);

DELETE FROM radgroupcheck WHERE groupname IN (
    'grp_proxy_child',
    'grp_cisco_wlc_priv',
    'grp_cisco_wlc_operator',
    'grp_dahua_camera',
    'grp_generic_device'
);

DELETE FROM access_policy_assignments WHERE username IN (
    'proxy_child_device',
    'cisco_wlc_admin',
    'cisco_wlc_operator',
    'dahua_camera_lobby',
    'dahua_camera_entrance',
    'genericPrinter'
);

-- Users for Proxy-MAC via parent NAS scenario
INSERT INTO radcheck (username, attribute, op, value) VALUES
('proxy_child_device', 'Cleartext-Password', ':=', 'testpassword');

INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
('grp_proxy_child', 'Reply-Message', ':=', 'PROXY-CHILD');

INSERT INTO radusergroup (username, groupname, priority) VALUES
('proxy_child_device', 'grp_proxy_child', 0);

INSERT INTO access_policy_assignments
    (username, target_key, nas_ip, calling_station_id, radius_group, privilege_level, is_active)
VALUES
    ('proxy_child_device', SHA2(CONCAT('proxy_child_device|12:10.10.10.1|4:None|4:None|4:None|4:None|4:None'), 256), '10.10.10.1', NULL, 'grp_proxy_child', '10', 1);


-- Users for Cisco WLC scenario
INSERT INTO radcheck (username, attribute, op, value) VALUES
('cisco_wlc_admin', 'Cleartext-Password', ':=', 'testpassword'),
('cisco_wlc_operator', 'Cleartext-Password', ':=', 'testpassword');

INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
('grp_cisco_wlc_priv', 'Reply-Message', ':=', 'CISCO-WLC-PRIV'),
('grp_cisco_wlc_priv', 'Reply-Message', ':=', 'privilege-level=15'),
('grp_cisco_wlc_operator', 'Reply-Message', ':=', 'CISCO-WLC-OPERATOR');

INSERT INTO radusergroup (username, groupname, priority) VALUES
('cisco_wlc_admin', 'grp_cisco_wlc_priv', 0),
('cisco_wlc_operator', 'grp_cisco_wlc_operator', 0);

INSERT INTO access_policy_assignments
    (username, target_key, nas_ip, calling_station_id, radius_group, privilege_level, is_active)
VALUES
    ('cisco_wlc_admin', SHA2(CONCAT('cisco_wlc_admin|12:192.168.1.101|4:None|4:None|4:None|4:None|4:None'), 256), '192.168.1.101', NULL, 'grp_cisco_wlc_priv', '15', 1),
    ('cisco_wlc_operator', SHA2(CONCAT('cisco_wlc_operator|12:192.168.1.101|4:None|4:None|4:None|4:None|4:None'), 256), '192.168.1.101', NULL, 'grp_cisco_wlc_operator', '5', 1);


-- Users for Dahua CCTV scenario
INSERT INTO radcheck (username, attribute, op, value) VALUES
('dahua_camera_lobby', 'Cleartext-Password', ':=', 'testpassword'),
('dahua_camera_entrance', 'Cleartext-Password', ':=', 'testpassword'),
('dahua_unknown_camera', 'Cleartext-Password', ':=', 'testpassword');

INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
('grp_dahua_camera', 'Reply-Message', ':=', 'DAHUA-CAMERA');

INSERT INTO radusergroup (username, groupname, priority) VALUES
('dahua_camera_lobby', 'grp_dahua_camera', 0),
('dahua_camera_entrance', 'grp_dahua_camera', 0);

INSERT INTO access_policy_assignments
    (username, target_key, nas_ip, calling_station_id, radius_group, privilege_level, is_active)
VALUES
    ('dahua_camera_lobby', SHA2(CONCAT('dahua_camera_lobby|12:192.168.2.1|4:None|4:None|4:None|4:None|4:None'), 256), '192.168.2.1', NULL, 'grp_dahua_camera', '3', 1),
    ('dahua_camera_entrance', SHA2(CONCAT('dahua_camera_entrance|12:192.168.2.1|4:None|4:None|4:None|4:None|4:None'), 256), '192.168.2.1', NULL, 'grp_dahua_camera', '3', 1);


-- Users for Generic IP device scenario (printer, sensor, etc.)
INSERT INTO radcheck (username, attribute, op, value) VALUES
('genericPrinter', 'Cleartext-Password', ':=', 'testpassword');

INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
('grp_generic_device', 'Reply-Message', ':=', 'GENERIC-DEVICE');

INSERT INTO radusergroup (username, groupname, priority) VALUES
('genericPrinter', 'grp_generic_device', 0);

INSERT INTO access_policy_assignments
    (username, target_key, nas_ip, calling_station_id, radius_group, privilege_level, is_active)
VALUES
    ('genericPrinter', SHA2(CONCAT('genericPrinter|12:192.168.3.1|4:None|4:None|4:None|4:None|4:None'), 256), '192.168.3.1', NULL, 'grp_generic_device', '1', 1);

-- NAS entries required for vendor scenarios
INSERT INTO nas (nasname, shortname, type, secret, description) VALUES
('10.10.10.1', 'test-proxy-nas', 'other', 'testing123', 'Test Proxy NAS'),
('192.168.1.101', 'test-cisco-nas', 'Cisco', 'testing123', 'Test Cisco NAS'),
('192.168.2.1', 'test-dahua-nas', 'other', 'testing123', 'Test Dahua NAS'),
('192.168.3.1', 'test-printer-nas', 'other', 'testing123', 'Test Printer NAS')
ON DUPLICATE KEY UPDATE shortname=VALUES(shortname);

COMMIT;
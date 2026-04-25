-- Seed for MAC vs IP priority testing
START TRANSACTION;

DELETE FROM radcheck WHERE username = 'mac_user';
DELETE FROM radgroupreply WHERE groupname IN ('grp_mac_priority', 'grp_ip_proxy');
DELETE FROM user_nas_privilege_map WHERE username = 'mac_user';

INSERT INTO radcheck (username, attribute, op, value) VALUES
('mac_user', 'Cleartext-Password', ':=', 'testpassword');

INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
('grp_mac_priority', 'Reply-Message', ':=', 'PRIORITY-MAC'),
('grp_ip_proxy', 'Reply-Message', ':=', 'PROXY-IP');

-- Priority test:
-- Rule 1: User at NAS IP 192.168.1.11 (AP) -> High permission (grp_ip_proxy)
-- Rule 2: User with MAC 0A-00-3E-45-76-4A -> Specific permission (grp_mac_priority)
-- If MAC priority works, the SM should get grp_mac_priority even if NAS IP matches.

INSERT INTO user_nas_privilege_map
  (username, nas_ip, calling_station_id, radius_group, privilege_level, is_active)
VALUES
  ('mac_user', '192.168.1.11', NULL, 'grp_ip_proxy', '15', 1),
  ('mac_user', NULL, '0A-00-3E-45-76-4A', 'grp_mac_priority', '7', 1);

COMMIT;

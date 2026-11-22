-- Deterministic seed for MikroTik support (#99, #96).
--
-- Scenario: a RouterOS NAS (TEST-NET-1 192.0.2.30, RFC 5737) and a user
-- stored as NT-Password. The user's policy group replies with
-- Mikrotik-Group := full, which needs backend/dictionaries/dictionary.mikrotik.
--   1) mt.nt + correct password over PAP -> Access-Accept + Mikrotik-Group=full
--   2) mt.nt + wrong password            -> Access-Reject
--
-- Intended for the ephemeral docker-compose.test.yml database. NAS rows are
-- inserted only if their address does not exist yet (nas.nasname is not
-- unique, see #98); only this seed's own user, group and NAS shortname are
-- deleted.
--
-- Usage:
--   docker exec -i zeroradius-test-db mysql -utest_user -ptest_password zeroradius_test < seed_mikrotik.sql
--   docker restart zeroradius-test-radius

START TRANSACTION;

DELETE FROM access_policy_assignments WHERE username = 'mt.nt';
DELETE FROM radusergroup WHERE username = 'mt.nt';
DELETE FROM radcheck WHERE username = 'mt.nt';
DELETE FROM radgroupreply WHERE groupname = 'mikrotik-full';
DELETE FROM nas WHERE shortname = 'mikrotik-test-nas';

-- NT-Password = MD4(UTF-16LE('testpassword')), as the backend stores it.
INSERT INTO radcheck (username, attribute, op, value) VALUES
('mt.nt', 'NT-Password', ':=', 'd32a2901011176349b41d406dcc95a90');

INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
('mikrotik-full', 'Mikrotik-Group', ':=', 'full'),
('mikrotik-full', 'Reply-Message', ':=', 'MIKROTIK-FULL');

INSERT INTO access_policy_assignments
    (username, target_key, nas_ip, calling_station_id, radius_group, privilege_level, is_active)
VALUES
    ('mt.nt', SHA2(CONCAT('mt.nt|10:192.0.2.30|4:None|4:None|4:None|4:None|4:None'), 256), '192.0.2.30', NULL, 'mikrotik-full', NULL, 1);

INSERT INTO nas (nasname, shortname, type, secret, description)
SELECT '127.0.0.1', 'mikrotik-test-runner', 'other', 'testing123', 'MikroTik test runner NAS client'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM nas WHERE nasname = '127.0.0.1');

INSERT INTO nas (nasname, shortname, type, secret, description)
SELECT '192.0.2.30', 'mikrotik-test-nas', 'mikrotik', 'testing123', 'RouterOS test NAS'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM nas WHERE nasname = '192.0.2.30');

COMMIT;

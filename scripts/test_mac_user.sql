INSERT INTO nas (nasname, shortname, secret, type) VALUES ('127.0.0.1', 'localhost', 'testing1230000000000000000000000', 'other');
INSERT INTO radcheck (username, attribute, op, value) VALUES ('mac_user1', 'Cleartext-Password', ':=', 'Secret123!');
INSERT INTO user_nas_privilege_map (username, target_key, calling_station_id, radius_group, is_active) VALUES ('mac_user1', 'mac_user1_mac', 'aabbccddeeff', 'cir_test', 1);

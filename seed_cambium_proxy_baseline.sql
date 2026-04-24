-- Deterministic seed for real Cambium AP proxy baseline coverage.
-- Scope: AP direct vs SM proxy, single vs dual reply attrs, check+reply, zero-trust reject.

START TRANSACTION;

-- Clean previous deterministic objects
DELETE FROM radgroupreply
WHERE groupname IN (
  'grp_baseline_ap_direct',
  'grp_baseline_sm_lector_single',
  'grp_baseline_sm_lector_dual',
  'grp_baseline_sm_check_reply'
);

DELETE FROM radgroupcheck
WHERE groupname IN (
  'grp_baseline_ap_direct',
  'grp_baseline_sm_lector_single',
  'grp_baseline_sm_lector_dual',
  'grp_baseline_sm_check_reply'
);

DELETE FROM radcheck
WHERE username IN (
  'baseline_ap_operator',
  'baseline_sm_lector_single',
  'baseline_sm_lector_dual',
  'baseline_sm_check_reply',
  'baseline_zero_trust'
);

DELETE FROM user_nas_privilege_map
WHERE username IN (
  'baseline_ap_operator',
  'baseline_sm_lector_single',
  'baseline_sm_lector_dual',
  'baseline_sm_check_reply',
  'baseline_zero_trust'
);

-- Users
INSERT INTO radcheck (username, attribute, op, value) VALUES
('baseline_ap_operator', 'Cleartext-Password', ':=', 'testpassword'),
('baseline_sm_lector_single', 'Cleartext-Password', ':=', 'testpassword'),
('baseline_sm_lector_dual', 'Cleartext-Password', ':=', 'testpassword'),
('baseline_sm_check_reply', 'Cleartext-Password', ':=', 'testpassword'),
('baseline_zero_trust', 'Cleartext-Password', ':=', 'testpassword');

-- Groups (reply side)
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
('grp_baseline_ap_direct', 'Reply-Message', ':=', 'BASELINE-AP-DIRECT'),
('grp_baseline_ap_direct', 'Cambium-Canopy-UserLevel', ':=', '3'),

('grp_baseline_sm_lector_single', 'Reply-Message', ':=', 'BASELINE-SM-LECTOR-SINGLE'),
('grp_baseline_sm_lector_single', 'Cambium-Canopy-UserLevel', ':=', '1'),

('grp_baseline_sm_lector_dual', 'Reply-Message', ':=', 'BASELINE-SM-LECTOR-DUAL'),
('grp_baseline_sm_lector_dual', 'Cambium-Canopy-UserLevel', ':=', '1'),
('grp_baseline_sm_lector_dual', 'Cambium-Canopy-UserMode', ':=', '1'),

('grp_baseline_sm_check_reply', 'Reply-Message', ':=', 'BASELINE-SM-CHECK-REPLY'),
('grp_baseline_sm_check_reply', 'Cambium-Canopy-UserLevel', ':=', '1');

-- Group check + reply case (must pass with NAS-Port=0)
INSERT INTO radgroupcheck (groupname, attribute, op, value) VALUES
('grp_baseline_sm_check_reply', 'NAS-Port', '==', '0');

-- Access-policy assignments used by nas_based_authorization
-- AP direct baseline
INSERT INTO user_nas_privilege_map
  (username, nas_ip, calling_station_id, radius_group, privilege_level, is_active)
VALUES
  ('baseline_ap_operator', '192.168.88.1', NULL, 'grp_baseline_ap_direct', '15', 1);

-- Same AP as proxy: direct AP mapping + SM-specific mapping by Calling-Station-Id
INSERT INTO user_nas_privilege_map
  (username, nas_ip, calling_station_id, radius_group, privilege_level, is_active)
VALUES
  ('baseline_sm_lector_single', '192.168.88.1', NULL, 'grp_baseline_ap_direct', '15', 1),
  ('baseline_sm_lector_single', NULL, 'aabbccddeeff', 'grp_baseline_sm_lector_single', '1', 1),

  ('baseline_sm_lector_dual', '192.168.88.1', NULL, 'grp_baseline_ap_direct', '15', 1),
  ('baseline_sm_lector_dual', NULL, '001122334455', 'grp_baseline_sm_lector_dual', '1', 1),

  ('baseline_sm_check_reply', NULL, 'deaddeadbeef', 'grp_baseline_sm_check_reply', '1', 1);

-- baseline_zero_trust intentionally has credentials but no policy mapping.

COMMIT;

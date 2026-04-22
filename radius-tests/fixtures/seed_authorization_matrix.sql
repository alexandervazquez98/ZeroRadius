-- Deterministic seed for cir-access-metrics-test-plan.
-- Scope: segment/CIDR/NAS precedence + CIR-bearing Access-Accept attributes.

START TRANSACTION;

-- Compatibility shim for environments that still run older privilege-map schema.
ALTER TABLE user_nas_privilege_map
  ADD COLUMN IF NOT EXISTS segment_target_key VARCHAR(255) NULL,
  ADD COLUMN IF NOT EXISTS target_start_ip VARCHAR(45) NULL,
  ADD COLUMN IF NOT EXISTS target_end_ip VARCHAR(45) NULL;

-- Clean previous deterministic objects
DELETE FROM radgroupreply
WHERE groupname IN (
  'grp_matrix_exact_a',
  'grp_matrix_range_a',
  'grp_matrix_base_a',
  'grp_matrix_fallback_a',
  'grp_matrix_exact_b',
  'grp_matrix_range_b',
  'grp_matrix_base_b',
  'grp_matrix_fallback_b'
);

DELETE FROM radgroupcheck
WHERE groupname IN (
  'grp_matrix_exact_a',
  'grp_matrix_range_a',
  'grp_matrix_base_a',
  'grp_matrix_fallback_a',
  'grp_matrix_exact_b',
  'grp_matrix_range_b',
  'grp_matrix_base_b',
  'grp_matrix_fallback_b'
);

DELETE FROM radcheck
WHERE username IN ('segment_admin_a', 'segment_reader_b');

DELETE FROM user_nas_privilege_map
WHERE username IN ('segment_admin_a', 'segment_reader_b');

DELETE FROM network_segments
WHERE name IN ('matrix-shared-segment');

DELETE FROM nas
WHERE shortname IN ('matrix-fallback-net', 'matrix-test-runner');

DELETE FROM nas_categories
WHERE name IN ('matrix-fallback-category');

-- Users for deterministic matrix
INSERT INTO radcheck (username, attribute, op, value) VALUES
('segment_admin_a', 'Cleartext-Password', ':=', 'testpassword'),
('segment_reader_b', 'Cleartext-Password', ':=', 'testpassword');

-- Groups and visible markers
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
('grp_matrix_exact_a', 'Reply-Message', ':=', 'MATRIX-EXACT-A'),
('grp_matrix_exact_a', 'Cambium-Canopy-HPDLCIR', ':=', '5000'),
('grp_matrix_exact_a', 'Cambium-Canopy-HPULCIR', ':=', '2000'),

('grp_matrix_range_a', 'Reply-Message', ':=', 'MATRIX-RANGE-A'),
('grp_matrix_range_a', 'Cambium-Canopy-HPDLCIR', ':=', '4500'),
('grp_matrix_range_a', 'Cambium-Canopy-HPULCIR', ':=', '1800'),

('grp_matrix_base_a', 'Reply-Message', ':=', 'MATRIX-BASE-A'),
('grp_matrix_fallback_a', 'Reply-Message', ':=', 'MATRIX-FALLBACK-A'),

('grp_matrix_exact_b', 'Reply-Message', ':=', 'MATRIX-EXACT-B'),
('grp_matrix_range_b', 'Reply-Message', ':=', 'MATRIX-RANGE-B'),
('grp_matrix_base_b', 'Reply-Message', ':=', 'MATRIX-BASE-B'),
('grp_matrix_fallback_b', 'Reply-Message', ':=', 'MATRIX-FALLBACK-B');

-- Category fallback target via nas_cidr_ranges view source tables
INSERT INTO nas_categories (name, description, criticality, vendor)
VALUES ('matrix-fallback-category', 'Deterministic category fallback', 'standard', 'matrix');

SET @matrix_category_id := (
  SELECT id FROM nas_categories WHERE name = 'matrix-fallback-category' LIMIT 1
);

INSERT INTO nas (nasname, shortname, type, secret, description, category_id)
VALUES ('10.0.0.0/24', 'matrix-fallback-net', 'other', 'testing123', 'Matrix fallback category CIDR', @matrix_category_id);

-- Allow deterministic test runners (host/container) to authenticate as NAS clients
-- Office server runner source currently resolves to 172.18.0.1.
INSERT INTO nas (nasname, shortname, type, secret, description, category_id)
VALUES ('172.18.0.1', 'matrix-test-runner', 'other', 'testing123', 'Deterministic test runner NAS client', @matrix_category_id);

INSERT INTO network_segments (name, cidr, description)
VALUES ('matrix-shared-segment', '192.168.10.0/24', 'Shared CIDR for inverse user exceptions');

SET @matrix_segment_id := (
  SELECT id FROM network_segments WHERE name = 'matrix-shared-segment' LIMIT 1
);

-- User A: exact > range > base > fallback
INSERT INTO user_nas_privilege_map
  (username, nas_ip, nas_category_id, segment_id, target_start_ip, target_end_ip, radius_group, privilege_level, is_active)
VALUES
  ('segment_admin_a', '192.168.10.50', NULL, NULL, NULL, NULL, 'grp_matrix_exact_a', '15', 1),
  ('segment_admin_a', NULL, NULL, @matrix_segment_id, '192.168.10.60', '192.168.10.69', 'grp_matrix_range_a', '15', 1),
  ('segment_admin_a', NULL, NULL, @matrix_segment_id, NULL, NULL, 'grp_matrix_base_a', '7', 1),
  ('segment_admin_a', NULL, @matrix_category_id, NULL, NULL, NULL, 'grp_matrix_fallback_a', '5', 1);

-- User B: inverse-range profile on same shared CIDR
INSERT INTO user_nas_privilege_map
  (username, nas_ip, nas_category_id, segment_id, target_start_ip, target_end_ip, radius_group, privilege_level, is_active)
VALUES
  ('segment_reader_b', '192.168.10.51', NULL, NULL, NULL, NULL, 'grp_matrix_exact_b', '7', 1),
  ('segment_reader_b', NULL, NULL, @matrix_segment_id, '192.168.10.70', '192.168.10.79', 'grp_matrix_range_b', '7', 1),
  ('segment_reader_b', NULL, NULL, @matrix_segment_id, NULL, NULL, 'grp_matrix_base_b', '3', 1),
  ('segment_reader_b', NULL, @matrix_category_id, NULL, NULL, NULL, 'grp_matrix_fallback_b', '1', 1);

COMMIT;

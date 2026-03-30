-- E2E test user seed for ZeroRadius
-- Password: TestPassword1! (bcrypt hash generated with Python 3.11 + passlib)
INSERT INTO admin_users (username, hashed_password, is_active, force_password_change, role)
VALUES (
  'test_superadmin',
  '$2b$12$6Jp4M5p19oaoIhLBn44cYO5EHZdXJ/bIvfM4AuilA293WAy8b78dm',
  1,
  0,
  'superadmin'
)
ON DUPLICATE KEY UPDATE
  hashed_password = '$2b$12$6Jp4M5p19oaoIhLBn44cYO5EHZdXJ/bIvfM4AuilA293WAy8b78dm',
  is_active = 1,
  force_password_change = 0;

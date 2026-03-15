-- Migration 004: Add role column to admin_users table for RBAC
-- T03: ISO 27001 A.5.15, A.5.18

ALTER TABLE admin_users
  ADD COLUMN IF NOT EXISTS email VARCHAR(255) NULL AFTER username,
  ADD COLUMN IF NOT EXISTS role VARCHAR(32) NOT NULL DEFAULT 'admin' AFTER email;

-- Set the first/oldest admin user as superadmin
UPDATE admin_users 
SET role = 'superadmin' 
WHERE id = (SELECT MIN(id) FROM (SELECT id FROM admin_users) t);

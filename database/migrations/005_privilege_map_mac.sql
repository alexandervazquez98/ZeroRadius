-- Migration 005: Add calling_station_id (MAC) support to user_nas_privilege_map
-- REQ-DB-005: Support MAC-based targeting to solve NAS Proxy ambiguity

ALTER TABLE user_nas_privilege_map
  ADD COLUMN IF NOT EXISTS calling_station_id VARCHAR(50) NULL AFTER nas_ip;

-- Update unique constraints: we want to allow rules for the same user + IP + MAC combination.
-- The existing uq_user_nas_ip constraint is (username, nas_ip).
-- Since MySQL 8.x handles multiple NULLs in unique constraints as distinct, 
-- but we want to allow (user, IP, NULL) and (user, NULL, MAC) and (user, IP, MAC).

ALTER TABLE user_nas_privilege_map
  DROP INDEX IF EXISTS uq_user_nas_ip;

ALTER TABLE user_nas_privilege_map
  ADD UNIQUE INDEX uq_user_nas_ip_mac (username, nas_ip, calling_station_id);

-- Add index for performance in RADIUS lookup
ALTER TABLE user_nas_privilege_map
  ADD INDEX idx_unpm_mac (calling_station_id);

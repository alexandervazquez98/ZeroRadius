-- Migration 006: Fix Data Integrity (NULLs in Unique) and CIDR Math
-- REQ-DB-006: target_key hash for absolute uniqueness
-- REQ-DB-007: Correct bitmask math for non-canonical CIDRs

START TRANSACTION;

-- 1. Add target_key for absolute uniqueness (Solves NULL != NULL issue in composite indexes)
ALTER TABLE user_nas_privilege_map
    ADD COLUMN target_key VARCHAR(128) NULL AFTER username;

-- Populate existing rows (deterministic hash)
UPDATE user_nas_privilege_map
SET target_key = SHA2(CONCAT(
    username, '|',
    COALESCE(nas_ip, ''), '|',
    COALESCE(calling_station_id, ''), '|',
    COALESCE(nas_category_id, '0'), '|',
    COALESCE(segment_id, '0'), '|',
    COALESCE(target_start_ip, ''), '|',
    COALESCE(target_end_ip, '')
), 256);

ALTER TABLE user_nas_privilege_map
    MODIFY COLUMN target_key VARCHAR(128) NOT NULL,
    ADD UNIQUE INDEX uq_unpm_target_key (target_key);

-- Drop old unreliable indexes
ALTER TABLE user_nas_privilege_map DROP INDEX IF EXISTS uq_user_nas_ip;
ALTER TABLE user_nas_privilege_map DROP INDEX IF EXISTS uq_user_nas_ip_mac;
ALTER TABLE user_nas_privilege_map DROP INDEX IF EXISTS uq_user_nas_cat;
ALTER TABLE user_nas_privilege_map DROP INDEX IF EXISTS uq_user_segment_target;

-- 2. Fix nas_cidr_ranges math (Apply bitmask to handle non-canonical nasname entries)
CREATE OR REPLACE VIEW nas_cidr_ranges AS
SELECT
    n.id,
    n.nasname,
    n.category_id,
    nc.name        AS category_name,
    nc.criticality AS category_criticality,
    -- Apply mask to net_start: (ip & (0xFFFFFFFF << (32 - mask)))
    (INET_ATON(SUBSTRING_INDEX(n.nasname, '/', 1)) & 
     (0xFFFFFFFF << (32 - CAST(
            CASE WHEN LOCATE('/', n.nasname) > 0
                THEN SUBSTRING_INDEX(n.nasname, '/', -1)
                ELSE '32'
            END AS UNSIGNED)))) AS net_start,
    -- net_end is net_start + size - 1
    (INET_ATON(SUBSTRING_INDEX(n.nasname, '/', 1)) & 
     (0xFFFFFFFF << (32 - CAST(
            CASE WHEN LOCATE('/', n.nasname) > 0
                THEN SUBSTRING_INDEX(n.nasname, '/', -1)
                ELSE '32'
            END AS UNSIGNED)))) 
        + POW(2, 32 - CAST(
            CASE WHEN LOCATE('/', n.nasname) > 0
                THEN SUBSTRING_INDEX(n.nasname, '/', -1)
                ELSE '32'
            END AS UNSIGNED)) - 1              AS net_end,
    CAST(
        CASE WHEN LOCATE('/', n.nasname) > 0
            THEN SUBSTRING_INDEX(n.nasname, '/', -1)
            ELSE '32'
        END AS UNSIGNED)                       AS prefix_len
FROM nas n
JOIN nas_categories nc ON n.category_id = nc.id;

COMMIT;

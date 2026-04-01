-- Migration 004: NAS Categories feature
-- Date: 2026-04-01
-- Feature: nas-categories (SDD)
--
-- Adds:
--   • nas_categories table — structured device classification
--   • nas.category_id FK
--   • user_nas_privilege_map: nas_ip extended to NULL/VARCHAR(50),
--     nas_category_id FK, updated unique constraints
--   • nas_cidr_ranges VIEW for CIDR-aware policy lookup
--
-- Safe to run on existing DBs — all changes are additive.
-- Existing rows in user_nas_privilege_map keep their nas_ip value (backwards compatible).

-- ─────────────────────────────────────────────
-- Step 1: Create nas_categories table
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS nas_categories (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(64)  NOT NULL UNIQUE,
    description VARCHAR(200) NULL,
    criticality ENUM('critical','standard','restricted') NOT NULL DEFAULT 'standard',
    vendor      VARCHAR(64)  NULL,
    created_at  DATETIME(6)  DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_nc_name (name),
    INDEX idx_nc_criticality (criticality)
) ENGINE=InnoDB;

-- ─────────────────────────────────────────────
-- Step 2: Add category_id to nas table
-- ─────────────────────────────────────────────
ALTER TABLE nas
    ADD COLUMN category_id INT NULL DEFAULT NULL AFTER zone_id,
    ADD KEY fk_nas_category (category_id),
    ADD CONSTRAINT fk_nas_category
        FOREIGN KEY (category_id) REFERENCES nas_categories(id) ON DELETE SET NULL;

-- ─────────────────────────────────────────────
-- Step 3: Extend user_nas_privilege_map
-- ─────────────────────────────────────────────

-- 3a. Drop old unique constraint (nas_ip was NOT NULL, single key)
ALTER TABLE user_nas_privilege_map DROP INDEX uq_user_nas;

-- 3b. Extend nas_ip: allow NULL + support CIDR notation
ALTER TABLE user_nas_privilege_map
    MODIFY COLUMN nas_ip VARCHAR(50) NULL;

-- 3c. Add category-based targeting column
ALTER TABLE user_nas_privilege_map
    ADD COLUMN nas_category_id INT NULL DEFAULT NULL AFTER nas_ip,
    ADD INDEX idx_unpm_category (nas_category_id),
    ADD CONSTRAINT fk_unpm_category
        FOREIGN KEY (nas_category_id) REFERENCES nas_categories(id) ON DELETE SET NULL;

-- 3d. Add targeted unique constraints (separate for IP vs category modes)
ALTER TABLE user_nas_privilege_map
    ADD UNIQUE KEY uq_user_nas_ip  (username, nas_ip),
    ADD UNIQUE KEY uq_user_nas_cat (username, nas_category_id);

-- ─────────────────────────────────────────────
-- Step 4: Create CIDR resolution view
-- ─────────────────────────────────────────────
-- Used by FreeRADIUS nas_based_authorization policy Step 2 (category fallback).
-- Handles both plain IPs (prefix_len defaults to 32) and CIDR notation (e.g. 10.53.1.0/24).
CREATE OR REPLACE VIEW nas_cidr_ranges AS
SELECT
    n.id,
    n.nasname,
    n.category_id,
    nc.name        AS category_name,
    nc.criticality AS category_criticality,
    INET_ATON(SUBSTRING_INDEX(n.nasname, '/', 1)) AS net_start,
    INET_ATON(SUBSTRING_INDEX(n.nasname, '/', 1))
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

-- Migration 003: Create new compliance tables for ISO 27001
-- REQ-DB-005: radius_reply_audit
-- REQ-DB-006: user_nas_privilege_map
-- Also creates login_attempts (for lockout service)

-- Table: login_attempts (account lockout — ISO 27001 A.5.17)
CREATE TABLE IF NOT EXISTS login_attempts (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64) NOT NULL,
    ip_address      VARCHAR(45) NULL,
    attempted_at    DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    success         TINYINT(1)  NOT NULL DEFAULT 0,
    INDEX idx_username_time (username, attempted_at)
) ENGINE=InnoDB;

-- Table: radius_reply_audit (extended reply attribute audit — ISO 27001 A.5.15, A.8.2, A.5.18)
CREATE TABLE IF NOT EXISTS radius_reply_audit (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64)  NOT NULL,
    nas_ip          VARCHAR(15)  NULL,
    nas_identifier  VARCHAR(64)  NULL,
    radius_group    VARCHAR(64)  NULL,
    reply_attributes JSON        NULL,
    privilege_level VARCHAR(32)  NULL,
    event_type      VARCHAR(32)  NULL,
    created_at      DATETIME(6)  DEFAULT CURRENT_TIMESTAMP(6),
    admin_user      VARCHAR(255) NULL,
    old_value       TEXT         NULL,
    new_value       TEXT         NULL,
    record_hash     VARCHAR(71)  NULL,
    INDEX idx_rra_username (username),
    INDEX idx_rra_nas_ip (nas_ip),
    INDEX idx_rra_created_at (created_at)
) ENGINE=InnoDB;

-- Table: user_nas_privilege_map (NAS-based access control — ISO 27001 A.5.15, A.8.2)
CREATE TABLE IF NOT EXISTS user_nas_privilege_map (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64)  NOT NULL,
    nas_ip          VARCHAR(15)  NOT NULL,
    nas_identifier  VARCHAR(64)  NULL,
    nas_vendor      VARCHAR(64)  NULL,
    radius_group    VARCHAR(64)  NOT NULL,
    privilege_level VARCHAR(32)  NULL,
    justification   TEXT         NULL,
    approved_by     VARCHAR(255) NULL,
    review_date     DATETIME     NULL,
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    created_at      DATETIME(6)  DEFAULT CURRENT_TIMESTAMP(6),
    updated_at      DATETIME(6)  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_user_nas (username, nas_ip),
    INDEX idx_unpm_nas_ip (nas_ip),
    INDEX idx_unpm_is_active (is_active),
    INDEX idx_unpm_review_date (review_date)
) ENGINE=InnoDB;

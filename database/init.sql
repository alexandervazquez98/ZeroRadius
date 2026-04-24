-- FreeRADIUS schema with ISO 27001:2022 compliance enhancements
-- Updated: 2026-04-09 (syslog-compliance: Phase 2 - syslog_events table)

CREATE TABLE IF NOT EXISTS radcheck (
  id int(11) unsigned NOT NULL auto_increment,
  username varchar(64) NOT NULL default '',
  attribute varchar(64)  NOT NULL default '',
  op char(2) NOT NULL DEFAULT '==',
  value varchar(253) NOT NULL default '',
  PRIMARY KEY  (id),
  KEY username (username(32))
);

CREATE TABLE IF NOT EXISTS radreply (
  id int(11) unsigned NOT NULL auto_increment,
  username varchar(64) NOT NULL default '',
  attribute varchar(64) NOT NULL default '',
  op char(2) NOT NULL DEFAULT '=',
  value varchar(253) NOT NULL default '',
  PRIMARY KEY  (id),
  KEY username (username(32))
);

CREATE TABLE IF NOT EXISTS radusergroup (
  username varchar(64) NOT NULL default '',
  groupname varchar(64) NOT NULL default '',
  priority int(11) NOT NULL default '1',
  KEY username (username(32))
);

CREATE TABLE IF NOT EXISTS radgroupcheck (
  id int(11) unsigned NOT NULL auto_increment,
  groupname varchar(64) NOT NULL default '',
  attribute varchar(64)  NOT NULL default '',
  op char(2) NOT NULL DEFAULT '==',
  value varchar(253)  NOT NULL default '',
  PRIMARY KEY  (id),
  KEY groupname (groupname(32))
);

CREATE TABLE IF NOT EXISTS radgroupreply (
  id int(11) unsigned NOT NULL auto_increment,
  groupname varchar(64) NOT NULL default '',
  attribute varchar(64)  NOT NULL default '',
  op char(2) NOT NULL DEFAULT '=',
  value varchar(253)  NOT NULL default '',
  PRIMARY KEY  (id),
  KEY groupname (groupname(32))
);

CREATE TABLE IF NOT EXISTS nas (
  id int(10) NOT NULL auto_increment,
  nasname varchar(128) NOT NULL,
  shortname varchar(32),
  type varchar(30) DEFAULT 'other',
  ports int(5),
  secret varchar(60) DEFAULT 'secret' NOT NULL,
  server varchar(64),
  community varchar(50),
  description varchar(200) DEFAULT 'RADIUS Client',
  category_id int(11) NULL DEFAULT NULL,
  PRIMARY KEY (id),
  KEY nasname (nasname),
  KEY fk_nas_category (category_id)
);

-- T08: radacct enhanced with nasidentifier, privilege_level, vendor_reply_attrs (ISO 27001 A.8.15)
CREATE TABLE IF NOT EXISTS radacct (
  radacctid bigint(21) NOT NULL auto_increment,
  acctsessionid varchar(64) NOT NULL default '',
  acctuniqueid varchar(32) NOT NULL default '',
  username varchar(64) NOT NULL default '',
  groupname varchar(64) NOT NULL default '',
  realm varchar(64) default '',
  nasipaddress varchar(15) NOT NULL default '',
  nasidentifier varchar(64) default NULL,
  nasportid varchar(15) default NULL,
  nasporttype varchar(32) default NULL,
  privilege_level varchar(32) default NULL,
  vendor_reply_attrs JSON default NULL,
  acctstarttime datetime NULL default NULL,
  acctupdatetime datetime NULL default NULL,
  acctstoptime datetime NULL default NULL,
  acctinterval int(12) default NULL,
  acctsessiontime int(12) unsigned default NULL,
  acctauthentic varchar(32) default NULL,
  connectinfo_start varchar(50) default NULL,
  connectinfo_stop varchar(50) default NULL,
  acctinputoctets bigint(20) default NULL,
  acctoutputoctets bigint(20) default NULL,
  calledstationid varchar(50) NOT NULL default '',
  callingstationid varchar(50) NOT NULL default '',
  acctterminatecause varchar(32) NOT NULL default '',
  servicetype varchar(32) default NULL,
  framedprotocol varchar(32) default NULL,
  framedipaddress varchar(15) NOT NULL default '',
  PRIMARY KEY  (radacctid),
  UNIQUE KEY acctuniqueid (acctuniqueid),
  KEY username (username),
  KEY framedipaddress (framedipaddress),
  KEY acctsessionid (acctsessionid),
  KEY acctsessiontime (acctsessiontime),
  KEY acctstarttime (acctstarttime),
  KEY acctinterval (acctinterval),
  KEY acctstoptime (acctstoptime),
  KEY nasipaddress (nasipaddress)
);

-- T07: radpostauth enhanced with NAS traceability and integrity hash (ISO 27001 A.8.15, A.5.33)
-- authdate is DATETIME(6) with no ON UPDATE — immutable after insert
CREATE TABLE IF NOT EXISTS radpostauth (
  id int(11) NOT NULL auto_increment,
  username varchar(64) NOT NULL default '',
  pass varchar(64) NOT NULL default '',
  reply varchar(32) NOT NULL default '',
  authdate DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  nas_ip_address varchar(15) NOT NULL DEFAULT '',
  nas_identifier varchar(64) NULL,
  nas_port INT NULL,
  calling_station_id varchar(50) NULL,
  called_station_id varchar(50) NULL,
  reply_message TEXT NULL,
  event_source varchar(32) NOT NULL DEFAULT 'radius',
  integrity_hash varchar(71) NULL,
  PRIMARY KEY  (id),
  KEY idx_nas_ip (nas_ip_address),
  KEY idx_calling_station (calling_station_id)
);

-- Custom Audit Table for the Web Admin Application
CREATE TABLE IF NOT EXISTS app_audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    admin_user VARCHAR(255) NOT NULL,
    target_user VARCHAR(255),
    action VARCHAR(50) NOT NULL, -- CREATE, UPDATE, DELETE, AUTH-001..ADMIN-009
    table_affected VARCHAR(50) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- T03: admin_users with role column for RBAC (ISO 27001 A.5.15, A.5.18)
CREATE TABLE IF NOT EXISTS admin_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'admin',
    hashed_password VARCHAR(255) NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    force_password_change TINYINT(1) NOT NULL DEFAULT 1,
    UNIQUE KEY idx_username (username)
);

-- T04: login_attempts for account lockout (ISO 27001 A.5.17)
CREATE TABLE IF NOT EXISTS login_attempts (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64) NOT NULL,
    ip_address      VARCHAR(45) NULL,
    attempted_at    DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    success         TINYINT(1)  NOT NULL DEFAULT 0,
    INDEX idx_username_time (username, attempted_at)
) ENGINE=InnoDB;

-- T05: radius_reply_audit — extended audit table (ISO 27001 A.5.15, A.8.2, A.5.18)
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

-- T06: access_policy_assignments — NAS-based access control (ISO 27001 A.5.15, A.8.2)
-- nas-categories: nas_ip extended to VARCHAR(50) and made nullable;
--   nas_category_id added for category-based entries (either nas_ip OR nas_category_id required).
CREATE TABLE IF NOT EXISTS access_policy_assignments (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64)  NOT NULL,
    target_key      VARCHAR(128) NOT NULL,
    nas_ip          VARCHAR(50)  NULL,                  -- NULL when using category-based mapping
    calling_station_id VARCHAR(50) NULL,
    nas_category_id INT          NULL DEFAULT NULL,     -- NULL when using IP-based mapping
    segment_id      INT          NULL DEFAULT NULL,
    segment_target_key VARCHAR(128) NOT NULL DEFAULT '',
    target_start_ip VARCHAR(50)  NULL,
    target_end_ip   VARCHAR(50)  NULL,
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
    UNIQUE KEY uq_unpm_target_key (target_key),
    INDEX idx_unpm_nas_ip     (nas_ip),
    INDEX idx_unpm_calling_station_id (calling_station_id),
    INDEX idx_unpm_category   (nas_category_id),
    INDEX idx_unpm_is_active  (is_active),
    INDEX idx_unpm_review_date (review_date)
) ENGINE=InnoDB;

-- T09: nas_categories — structured device categorization (nas-categories feature)
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

-- T10: device_registry — known endpoint devices (SMs, CPEs) by MAC with category
-- Enables RADIUS Step 1.5: MAC → device category → user category policy.
CREATE TABLE IF NOT EXISTS device_registry (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    mac             VARCHAR(50)  NOT NULL,
    category_id     INT          NULL DEFAULT NULL,
    nas_ip          VARCHAR(50)  NULL DEFAULT NULL,
    description     VARCHAR(200) NULL DEFAULT NULL,
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    created_at      DATETIME(6)  DEFAULT CURRENT_TIMESTAMP(6),
    updated_at      DATETIME(6)  DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY uq_device_mac (mac),
    INDEX idx_device_category (category_id),
    INDEX idx_device_nas_ip   (nas_ip),
    INDEX idx_device_active   (is_active)
) ENGINE=InnoDB;

ALTER TABLE device_registry ADD CONSTRAINT fk_device_category
    FOREIGN KEY (category_id) REFERENCES nas_categories(id) ON DELETE SET NULL;

-- syslog-compliance: Phase 2 - syslog_events table with partitioning by month
-- Partitioning strategy: PARTITION BY RANGE (YEAR(received_at) * 100 + MONTH(received_at))
-- Hash chain fields: previous_hash, hash (SHA256)
CREATE TABLE IF NOT EXISTS syslog_events (
    id BIGINT AUTO_INCREMENT,
    received_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    device_ip VARCHAR(45) NOT NULL,
    facility INT NULL,
    severity INT NULL,
    program VARCHAR(64) NULL,
    message TEXT NOT NULL,
    previous_hash VARCHAR(64) NULL,
    hash VARCHAR(64) NULL,
    PRIMARY KEY (id, received_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
PARTITION BY RANGE (YEAR(received_at) * 100 + MONTH(received_at)) (
    PARTITION p202604 VALUES LESS THAN (202605),
    PARTITION p202605 VALUES LESS THAN (202606),
    PARTITION p202606 VALUES LESS THAN (202607),
    PARTITION p202607 VALUES LESS THAN (202608),
    PARTITION p202608 VALUES LESS THAN (202609),
    PARTITION p202609 VALUES LESS THAN (202610),
    PARTITION p202610 VALUES LESS THAN (202611),
    PARTITION p202611 VALUES LESS THAN (202612),
    PARTITION p202612 VALUES LESS THAN (202701),
    PARTITION pmax VALUES LESS THAN MAXVALUE
);

-- Indexes for syslog_events
CREATE INDEX idx_syslog_device_ip ON syslog_events(device_ip);
CREATE INDEX idx_syslog_received_at ON syslog_events(received_at);
CREATE INDEX idx_syslog_severity ON syslog_events(severity);
CREATE INDEX idx_syslog_facility ON syslog_events(facility);

-- IAM & NAC RBAC tables

CREATE TABLE IF NOT EXISTS network_segments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    cidr VARCHAR(50) NOT NULL,
    description TEXT NULL,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_ns_name (name)
) ENGINE=InnoDB;

-- Add FK for nas.category_id to nas_categories
ALTER TABLE nas ADD CONSTRAINT fk_nas_category FOREIGN KEY (category_id) REFERENCES nas_categories(id) ON DELETE SET NULL;

-- Add FK for access_policy_assignments.nas_category_id to nas_categories
ALTER TABLE access_policy_assignments ADD CONSTRAINT fk_unpm_category FOREIGN KEY (nas_category_id) REFERENCES nas_categories(id) ON DELETE SET NULL;

-- Add FK for access_policy_assignments.segment_id to network_segments
-- FIX #55: Changed from ON DELETE SET NULL to ON DELETE RESTRICT to enforce:
-- 1. DB-level protection against orphaned privilege-map rows
-- 2. Matches API-level protection (router checks before delete)
-- 3. Consistent behavior regardless of delete path (API vs direct SQL)
ALTER TABLE access_policy_assignments ADD CONSTRAINT fk_unpm_segment FOREIGN KEY (segment_id) REFERENCES network_segments(id) ON DELETE RESTRICT;

-- nas_cidr_ranges VIEW: pre-computes network range boundaries for CIDR-aware policy lookup.
-- Used by the FreeRADIUS nas_based_authorization policy (Step 2: category fallback).
-- LOCATE check handles plain IPs (no slash) by defaulting prefix_len to 32.
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

-- ============================================================================
-- Fix for Linux host networking: ensure radius user can connect via loopback
-- When radius uses network_mode:host, it connects from 127.0.0.1/localhost
-- Also allow connections from Docker bridge network (172.18.0.0/16)
-- ============================================================================
CREATE USER IF NOT EXISTS 'radius'@'127.0.0.1' IDENTIFIED BY 'your-radius-db-password-here';
CREATE USER IF NOT EXISTS 'radius'@'localhost' IDENTIFIED BY 'your-radius-db-password-here';
CREATE USER IF NOT EXISTS 'radius'@'%' IDENTIFIED BY 'your-radius-db-password-here';
GRANT ALL PRIVILEGES ON radius.* TO 'radius'@'127.0.0.1';
GRANT ALL PRIVILEGES ON radius.* TO 'radius'@'localhost';
GRANT ALL PRIVILEGES ON radius.* TO 'radius'@'%';
FLUSH PRIVILEGES;

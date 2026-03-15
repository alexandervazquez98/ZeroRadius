-- Migration 001: Enhance radpostauth table for ISO 27001 A.8.15, A.5.33
-- REQ-DB-001: Add NAS traceability columns
-- REQ-DB-002: Change authdate to be immutable (no ON UPDATE)

-- Add new columns for NAS context traceability
ALTER TABLE radpostauth
  ADD COLUMN IF NOT EXISTS nas_ip_address   VARCHAR(15)   NOT NULL DEFAULT '' AFTER authdate,
  ADD COLUMN IF NOT EXISTS nas_identifier   VARCHAR(64)   NULL AFTER nas_ip_address,
  ADD COLUMN IF NOT EXISTS nas_port         INT           NULL AFTER nas_identifier,
  ADD COLUMN IF NOT EXISTS calling_station_id VARCHAR(50) NULL AFTER nas_port,
  ADD COLUMN IF NOT EXISTS called_station_id  VARCHAR(50) NULL AFTER calling_station_id,
  ADD COLUMN IF NOT EXISTS reply_message    TEXT          NULL AFTER called_station_id,
  ADD COLUMN IF NOT EXISTS event_source     VARCHAR(32)   NOT NULL DEFAULT 'radius' AFTER reply_message,
  ADD COLUMN IF NOT EXISTS integrity_hash   VARCHAR(71)   NULL AFTER event_source;

-- Fix authdate: remove ON UPDATE so timestamp is immutable after insert (REQ-DB-002)
ALTER TABLE radpostauth
  MODIFY COLUMN authdate DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6);

-- Add index for common query patterns
ALTER TABLE radpostauth
  ADD INDEX IF NOT EXISTS idx_nas_ip (nas_ip_address),
  ADD INDEX IF NOT EXISTS idx_calling_station (calling_station_id);

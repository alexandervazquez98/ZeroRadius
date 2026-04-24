-- Migration 009: Add nullable name to device_registry
-- Keeps backward compatibility with existing historical rows.

START TRANSACTION;

ALTER TABLE device_registry
    ADD COLUMN name VARCHAR(120) NULL DEFAULT NULL AFTER mac;

COMMIT;

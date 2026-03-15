-- Migration 002: Enhance radacct table for ISO 27001 A.8.15
-- REQ-DB-004: Add NAS identifier, privilege level, and vendor reply attributes

ALTER TABLE radacct
  ADD COLUMN IF NOT EXISTS nasidentifier     VARCHAR(64)   NULL AFTER nasipaddress,
  ADD COLUMN IF NOT EXISTS privilege_level   VARCHAR(32)   NULL AFTER nasporttype,
  ADD COLUMN IF NOT EXISTS vendor_reply_attrs JSON          NULL AFTER privilege_level;

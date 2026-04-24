-- Migration 007: Drop redundant unique constraints from access_policy_assignments
-- REQ-DB-007: target_key is the single source of uniqueness
--
-- uq_user_nas_ip (username, nas_ip) and uq_user_nas_cat (username, nas_category_id)
-- are incomplete — they don't include calling_station_id, so they block creating
-- multiple MAC-specific policies for the same user+NAS-IP (e.g. SM proxy scenario).
--
-- uq_user_segment_target (username, segment_id, segment_target_key) is also redundant
-- since target_key already encodes all those fields.
--
-- target_key (SHA-256 of all targeting fields) is the only constraint needed.

START TRANSACTION;

ALTER TABLE access_policy_assignments
    DROP INDEX IF EXISTS uq_user_nas_ip,
    DROP INDEX IF EXISTS uq_user_nas_cat,
    DROP INDEX IF EXISTS uq_user_segment_target;

COMMIT;

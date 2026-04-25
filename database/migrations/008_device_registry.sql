-- Migration 008: Device Registry
-- Stores known endpoint devices (SMs, CPEs, etc.) by MAC with a category assignment.
-- Enables RADIUS Step 1.5: resolve Calling-Station-Id → device category → user policy.
-- Solves the 1000+ SM problem: register MACs once here, policy map references category only.

START TRANSACTION;

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
    INDEX idx_device_active   (is_active),
    CONSTRAINT fk_device_category
        FOREIGN KEY (category_id) REFERENCES nas_categories(id) ON DELETE SET NULL
) ENGINE=InnoDB;

COMMIT;

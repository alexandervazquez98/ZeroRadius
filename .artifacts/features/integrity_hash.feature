# Feature: Integrity Hash SHA-256 for Authentication Records
# ISO Control: A.5.33 (CRÍTICA)
# Sources: REQ-DB-003, REQ-BE-002

Feature: Hash de integridad SHA-256 en registros de autenticación
  Como auditor de seguridad
  Quiero que cada registro de autenticación tenga un hash SHA-256
  Para detectar modificaciones no autorizadas (control ISO A.5.33)

  Scenario: Hash almacenado coincide con hash recalculado para registro intacto
    Given un registro en radpostauth recién insertado con:
      | username          | jperez             |
      | authdate          | 2026-01-01T10:00:00.000000 |
      | nas_ip_address    | 192.168.1.254      |
      | reply             | Access-Accept      |
      | calling_station_id | 10.10.5.22        |
    When el sistema recalcula el hash SHA-256 sobre los campos críticos del registro
    Then el hash calculado coincide exactamente con el valor en integrity_hash del registro
    And el valor integrity_hash comienza con "sha256:"
    And el valor integrity_hash tiene 71 caracteres (7 prefijo + 64 hex)

  Scenario: Hash detecta tampering cuando un campo es modificado directamente en BD
    Given existe un registro íntegro en radpostauth con integrity_hash almacenado
    When alguien modifica directamente el campo reply de "Access-Accept" a "Access-Reject" en la BD
    And el verificador de integridad recalcula el hash para ese registro
    Then el hash calculado es diferente del integrity_hash almacenado
    And se genera una alerta en los logs del sistema indicando tampering

  Scenario: El orden de campos en el dict no afecta el hash (forma canónica)
    Given los mismos datos de autenticación en dos representaciones con diferente orden de claves
    When se calcula el hash SHA-256 para ambas representaciones
    Then ambos hashes son idénticos

  Scenario: Campo ausente en el record no genera error sino hash consistente
    Given un registro con solo el campo username definido (faltan campos opcionales)
    When se calcula el hash SHA-256
    Then no se genera excepción KeyError
    And el hash comienza con "sha256:"

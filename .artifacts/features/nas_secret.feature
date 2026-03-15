# Feature: NAS Shared Secret Minimum Length Validation
# ISO Controls: A.5.17, SEC-02 (ALTA)
# Source: REQ-BE-006

Feature: Validación de longitud mínima del secreto compartido NAS
  Como sistema de gestión RADIUS
  Quiero rechazar secretos NAS de menos de 32 caracteres
  Para garantizar seguridad criptográfica del enlace NAS-servidor (control ISO A.5.17)

  Scenario: Crear NAS con secreto demasiado corto es rechazado
    Given un admin autenticado con permisos de escritura sobre NAS
    When llama a POST /api/nas con payload:
      | server   | 10.1.1.1     |
      | shortname | router-01   |
      | secret   | corto123     |
      | nastype  | cisco        |
    Then recibe HTTP 422
    And el mensaje de error contiene "NAS shared secret must be at least 32 characters"
    And no se crea ningún NAS en la base de datos

  Scenario: Crear NAS con secreto de exactamente 32 caracteres es aceptado
    Given un admin autenticado con permisos de escritura sobre NAS
    When llama a POST /api/nas con payload:
      | server   | 10.1.1.2                          |
      | shortname | router-02                        |
      | secret   | abcdefghij1234567890ABCDEFGHIJ12  |
      | nastype  | cisco                             |
    Then recibe HTTP 201
    And el NAS es creado exitosamente
    And se registra un evento ADMIN-005 en app_audit_log

  Scenario: Actualizar NAS con secreto corto es rechazado
    Given existe un NAS "10.1.1.3" con secreto válido
    And un admin autenticado intenta actualizarlo
    When llama a PUT /api/nas/1 con payload {"secret": "short"}
    Then recibe HTTP 422
    And el mensaje de error contiene "at least 32 characters"

  Scenario: Cambio de secreto NAS genera evento ADMIN-009
    Given existe un NAS "10.1.1.4" con secreto válido
    And un admin autenticado
    When actualiza el secreto con un nuevo valor de 32+ caracteres
    Then el NAS es actualizado exitosamente
    And se registra un evento ADMIN-009 en app_audit_log indicando cambio de secreto

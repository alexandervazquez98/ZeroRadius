# Feature: Account Lockout after Failed Login Attempts
# ISO Control: A.8.16, SEC-07 (CRÍTICA)
# Source: REQ-BE-003

Feature: Account lockout tras 5 intentos fallidos
  Como sistema de seguridad
  Quiero bloquear temporalmente cuentas tras múltiples intentos fallidos
  Para prevenir ataques de fuerza bruta (control ISO A.8.16)

  Background:
    Given el usuario "jperez" existe en la base de datos con contraseña correcta "ValidPass123!"
    And no hay intentos de login previos para "jperez"

  Scenario: Cuenta bloqueada tras 5 intentos fallidos en ventana de 10 minutos
    Given el usuario "jperez" realiza 5 intentos de login con contraseña incorrecta en 8 minutos
    When realiza el sexto intento de login con contraseña incorrecta
    Then recibe HTTP 429
    And el mensaje de error contiene "Account temporarily locked"
    And el mensaje de error contiene "15 minutes"

  Scenario: Bloqueo expira automáticamente tras 15 minutos
    Given la cuenta "jperez" fue bloqueada hace 16 minutos por exceso de intentos fallidos
    When el usuario intenta login con la contraseña correcta "ValidPass123!"
    Then el login es exitoso con HTTP 200
    And la respuesta contiene un JWT válido con campo "role"

  Scenario: Superadmin puede desbloquear una cuenta bloqueada inmediatamente
    Given la cuenta "jperez" está bloqueada (5+ intentos fallidos recientes)
    And el superadmin "admin_root" está autenticado
    When el superadmin llama a POST /api/admin-users/{id}/unlock para "jperez"
    Then recibe HTTP 200
    And la cuenta "jperez" queda desbloqueada inmediatamente
    And se registra un evento ADMIN-002 en el log de auditoría

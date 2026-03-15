# Feature: Role-Based Access Control (RBAC)
# ISO Controls: A.5.16, SOD-01..06 (ALTA)
# Sources: REQ-BE-004, REQ-DB-008

Feature: Sistema de roles RBAC en todos los endpoints
  Como administrador del sistema
  Quiero que los endpoints respeten el rol del usuario autenticado
  Para implementar separación de funciones (control ISO A.5.16)

  Background:
    Given el sistema tiene usuarios con los siguientes roles:
      | username     | role       |
      | admin_root   | superadmin |
      | admin_user   | admin      |
      | helpdesk_usr | helpdesk   |
      | auditor_usr  | auditor    |
      | readonly_usr | readonly   |

  # ── Audit read access ──────────────────────────────────────────────────────

  Scenario Outline: Todos los roles pueden leer el log de auditoría
    Given el usuario "<username>" con role "<role>" está autenticado
    When llama a GET /api/audit/access
    Then recibe HTTP 200

    Examples:
      | username     | role       |
      | admin_root   | superadmin |
      | admin_user   | admin      |
      | helpdesk_usr | helpdesk   |
      | auditor_usr  | auditor    |
      | readonly_usr | readonly   |

  # ── SIEM export ────────────────────────────────────────────────────────────

  Scenario: Auditor puede exportar logs en formato SIEM
    Given el usuario "auditor_usr" con role "auditor" está autenticado
    When llama a GET /api/audit/export?format=json
    Then recibe HTTP 200
    And la respuesta es un array JSON con campos de SIEM

  Scenario: Helpdesk no puede exportar logs
    Given el usuario "helpdesk_usr" con role "helpdesk" está autenticado
    When llama a GET /api/audit/export?format=json
    Then recibe HTTP 403
    And el body contiene {"detail": "Insufficient permissions"}

  # ── Admin users management ────────────────────────────────────────────────

  Scenario: Auditor no puede eliminar usuarios RADIUS
    Given el usuario "auditor_usr" con role "auditor" está autenticado
    When llama a DELETE /api/users/1
    Then recibe HTTP 403
    And el body contiene {"detail": "Insufficient permissions"}

  Scenario: Admin no puede crear otros admin users
    Given el usuario "admin_user" con role "admin" está autenticado
    When llama a POST /api/admin-users con payload {"username":"new","role":"admin"}
    Then recibe HTTP 403

  # ── VSA high-privilege guard ──────────────────────────────────────────────

  Scenario: Admin no puede asignar Cisco priv-lvl=15 (alto privilegio)
    Given el usuario "admin_user" con role "admin" está autenticado
    And existe un grupo "grp_cisco_admin" con NAS vendor "Cisco"
    When llama a PUT /api/groups/grp_cisco_admin con reply_attributes=[{"name":"Cisco-AVPair","value":"shell:priv-lvl=15"}]
    Then recibe HTTP 403
    And el mensaje indica "Only superadmin can assign level-15 or equivalent high-privilege VSA"

  Scenario: Superadmin puede asignar atributos de alto privilegio
    Given el usuario "admin_root" con role "superadmin" está autenticado
    And existe un grupo "grp_cisco_admin" con NAS vendor "Cisco"
    When llama a PUT /api/groups/grp_cisco_admin con reply_attributes=[{"name":"Cisco-AVPair","value":"shell:priv-lvl=15"}]
    Then recibe HTTP 200
    And se registra un evento ADMIN-006 en app_audit_log

  # ── Privilege map access ──────────────────────────────────────────────────

  Scenario: Auditor puede ver el mapa de privilegios pero no crear entradas
    Given el usuario "auditor_usr" con role "auditor" está autenticado
    When llama a GET /api/privilege-map
    Then recibe HTTP 200
    When llama a POST /api/privilege-map con datos válidos
    Then recibe HTTP 403

# Feature: User-NAS Privilege Map Management
# ISO Controls: A.5.18, A.8.2 (CRÍTICA)
# Sources: REQ-DB-006, REQ-FE-002

Feature: Gestión del mapa de privilegios usuario-NAS
  Como administrador de seguridad
  Quiero gestionar qué usuarios tienen qué privilegios en qué dispositivos NAS
  Para cumplir el principio de mínimo privilegio (control ISO A.5.18)

  Background:
    Given el sistema tiene la tabla user_nas_privilege_map creada
    And existen usuarios con roles: superadmin "admin_root", admin "admin_user", auditor "auditor_usr"

  Scenario: Admin crea un mapeo usuario-NAS con todos los campos requeridos
    Given el usuario "admin_user" con role "admin" está autenticado
    When llama a POST /api/privilege-map con payload:
      | username        | jperez             |
      | nas_ip          | 10.1.1.1           |
      | nas_vendor      | Cisco              |
      | radius_group    | grp_admin_cisco    |
      | privilege_level | level-15           |
      | justification   | Proyecto red-core  |
      | approved_by     | admin_user         |
      | review_date     | 2027-01-01         |
    Then recibe HTTP 201
    And el registro aparece en GET /api/privilege-map con is_active=1
    And se registra un evento ADMIN-002 en app_audit_log

  Scenario: Mapeo con review_date dentro de 30 días muestra badge "Revisión próxima"
    Given existe un mapeo activo con review_date en 15 días para "jperez"
    When el superadmin navega a la página /privilege-map
    Then el registro de "jperez" se muestra con badge "Revisión próxima" en amarillo

  Scenario: Mapeo vencido (review_date en el pasado) muestra badge "Vencido"
    Given existe un mapeo activo con review_date ayer para "jperez"
    When el superadmin navega a la página /privilege-map
    Then el registro de "jperez" se muestra con badge "Vencido" en rojo
    And el registro aparece en el endpoint GET /api/privilege-map?overdue_review=true

  Scenario: Auditor puede ver mapeos pero no crear ni eliminar
    Given el usuario "auditor_usr" con role "auditor" está autenticado
    When navega a GET /api/privilege-map
    Then recibe HTTP 200 con la lista de mapeos
    When intenta POST /api/privilege-map con datos válidos
    Then recibe HTTP 403
    When intenta DELETE /api/privilege-map/1
    Then recibe HTTP 403

  Scenario: UNIQUE KEY impide duplicar mapeo mismo usuario+NAS
    Given existe un mapeo activo: usuario "jperez" → NAS "10.1.1.1"
    When se intenta crear otro mapeo para "jperez" → NAS "10.1.1.1"
    Then el sistema rechaza con HTTP 409 o 422 indicando duplicado

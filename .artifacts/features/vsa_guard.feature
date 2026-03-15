# Feature: VSA Vendor Consistency Guard
# ISO Controls: REQ-VSA-02, A.8.2 (ALTA)
# Sources: REQ-BE-007, REQ-BE-008

Feature: Guardia de consistencia VSA por fabricante
  Como sistema RADIUS
  Quiero rechazar atributos VSA de fabricante incorrecto
  Para mantener integridad de políticas de autorización (control ISO A.8.2)

  # ── Vendor consistency ────────────────────────────────────────────────────

  Scenario: Atributo Cisco en NAS Cisco pasa validación
    Given un NAS registrado con vendor "Cisco"
    And un grupo "grp_cisco_ops" destinado a ese NAS
    When se intenta asignar el atributo "Cisco-AVPair" con valor "shell:priv-lvl=1"
    Then la validación pasa sin errores
    And el atributo es guardado exitosamente

  Scenario: Atributo Cisco en NAS Juniper es rechazado
    Given un NAS registrado con vendor "Juniper"
    And un grupo "grp_juniper_ops" destinado a ese NAS
    When se intenta asignar el atributo "Cisco-AVPair" con valor "shell:priv-lvl=15"
    Then el sistema rechaza con HTTP 422
    And el mensaje de error contiene "Cisco-AVPair"
    And el mensaje de error contiene "Juniper"

  Scenario: Atributo Fortinet en NAS Fortinet pasa validación
    Given un NAS registrado con vendor "Fortinet"
    And un grupo "grp_fortinet_ops" destinado a ese NAS
    When se intenta asignar el atributo "Fortinet-Group-Name" con valor "super_admin_profile"
    Then la validación pasa sin errores

  Scenario: Atributo Fortinet en NAS Cisco es rechazado
    Given un NAS registrado con vendor "Cisco"
    When se intenta asignar el atributo "Fortinet-Group-Name" con valor "super_admin_profile"
    Then el sistema rechaza con HTTP 422

  # ── High-privilege guard ──────────────────────────────────────────────────

  Scenario: Huawei priv-15 detectado como alto privilegio
    Given un conjunto de atributos: [{"name": "Huawei-Exec-Privilege", "value": "15"}]
    When el servicio evalúa si son de alto privilegio
    Then check_high_privilege retorna True

  Scenario: Cisco priv-1 no es considerado alto privilegio
    Given un conjunto de atributos: [{"name": "Cisco-AVPair", "value": "shell:priv-lvl=1"}]
    When el servicio evalúa si son de alto privilegio
    Then check_high_privilege retorna False

  Scenario: Atributos RFC estándar son válidos en cualquier vendor
    Given un NAS registrado con vendor "Cisco"
    When se intenta asignar el atributo "Service-Type" con valor "NAS-Prompt-User"
    Then la validación pasa sin errores
    When se intenta asignar el atributo "Session-Timeout" con valor "3600" en un NAS "Juniper"
    Then la validación pasa sin errores

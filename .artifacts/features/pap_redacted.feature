# Feature: PAP Password Redaction in radpostauth
# ISO Control: A.5.17 (CRÍTICA)
# Source: REQ-RADIUS-001

Feature: Contraseña PAP redactada en radpostauth
  Como sistema RADIUS
  Quiero que el campo pass en radpostauth nunca contenga la contraseña real
  Para proteger credenciales en reposo (control ISO A.5.17)

  Scenario: Autenticación PAP almacena [REDACTED] en lugar de la contraseña
    Given FreeRADIUS está configurado con el postauth_query actualizado
    When un usuario se autentica exitosamente usando PAP con contraseña "MiContraseña123"
    Then la fila insertada en radpostauth tiene pass='[REDACTED]'
    And el campo pass no contiene "MiContraseña123"

  Scenario: Autenticación fallida PAP también almacena [REDACTED]
    Given FreeRADIUS está configurado con el postauth_query actualizado
    When un usuario intenta autenticarse con contraseña incorrecta "ContraseñaInválida"
    Then la fila insertada en radpostauth (Access-Reject) tiene pass='[REDACTED]'
    And consultando SELECT pass FROM radpostauth WHERE username=? el resultado es siempre '[REDACTED]'

  Scenario: Campos NAS son populados en el mismo postauth_query
    Given FreeRADIUS está configurado con el postauth_query actualizado
    When un usuario se autentica desde el NAS 192.168.1.254 identificado como "router-core-01"
    Then la fila en radpostauth tiene:
      | nas_ip_address   | 192.168.1.254 |
      | nas_identifier   | router-core-01 |
      | event_source     | radius         |
      | pass             | [REDACTED]     |

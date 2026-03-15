# Feature: SIEM JSON Export Endpoint
# ISO Control: A.8.16 (ALTA)
# Source: REQ-BE-005

Feature: Exportación de logs en formato SIEM
  Como auditor de seguridad
  Quiero exportar los logs del sistema en formato JSON estructurado
  Para integración con herramientas SIEM externas (control ISO A.8.16)

  Background:
    Given existen 500 eventos de autenticación entre 2026-01-01 y 2026-01-31
    And el usuario "auditor_usr" con role "auditor" está autenticado
    And el usuario "helpdesk_usr" con role "helpdesk" está autenticado

  Scenario: Auditor exporta logs en formato JSON con filtro de fecha
    Given el usuario "auditor_usr" está autenticado
    When llama a GET /api/audit/export?format=json&from=2026-01-01&to=2026-01-31
    Then recibe HTTP 200
    And el Content-Type es "application/json"
    And la respuesta es un array de 500 eventos
    And cada evento tiene la estructura SIEM:
      | campo                              | tipo    |
      | event_id                           | string  |
      | event_version                      | string  |
      | timestamp_utc                      | string  |
      | ntp_synchronized                   | boolean |
      | identity.username                  | string  |
      | access_request.nas_ip_address      | string  |
      | access_request.nas_identifier      | string  |
      | authorization_result.decision      | string  |
      | audit.record_hash                  | string  |
      | audit.tamper_evident               | boolean |

  Scenario: Helpdesk no puede exportar logs SIEM
    Given el usuario "helpdesk_usr" está autenticado
    When llama a GET /api/audit/export?format=json
    Then recibe HTTP 403
    And el body contiene {"detail": "Insufficient permissions"}

  Scenario: Cada exportación genera evento ADMIN-008 en el log de auditoría
    Given el usuario "auditor_usr" está autenticado
    When llama a GET /api/audit/export?format=json
    Then se registra un evento ADMIN-008 en app_audit_log
    And el evento incluye el username del auditor y la IP de origen

  Scenario: Exportación con filtro de tipo de evento retorna solo eventos del tipo solicitado
    Given existen eventos AUTH y ADMIN en el sistema
    When llama a GET /api/audit/export?format=json&event_type=AUTH
    Then todos los eventos en la respuesta tienen event_id comenzando con "AUTH"
    And no hay eventos con event_id comenzando con "ADMIN" o "ACCT"

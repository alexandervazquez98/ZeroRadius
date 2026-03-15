# Specs: iso27001-compliance-improvements
**Change**: ISO/IEC 27001:2022 Compliance Improvements  
**Project**: RADIUS-gestor  
**Date**: 2026-03-14  
**Status**: Draft  

---

## Scope
Delta specs covering 18 compliance gaps across 3 phases. Only new/changed behavior is specified here — existing compliant behavior is not re-specified.

---

## Phase 1 — Database & RADIUS Layer

### REQ-DB-001 — radpostauth: campos de trazabilidad NAS
**ISO Control**: A.8.15 (CRÍTICA)  
**Title**: La tabla radpostauth debe registrar el contexto completo del NAS origen

**Acceptance Scenarios**:
- **GIVEN** un Access-Accept llega desde NAS 192.168.1.254 (router-core-01) iniciado por 10.10.5.22  
  **WHEN** FreeRADIUS inserta en radpostauth  
  **THEN** los campos nas_ip_address='192.168.1.254', nas_identifier='router-core-01', calling_station_id='10.10.5.22', event_source='radius' son NOT NULL en el registro
- **GIVEN** un Access-Reject por contraseña inválida  
  **WHEN** se inserta en radpostauth  
  **THEN** reply_message contiene el motivo de rechazo y event_source='radius'

**Schema delta**:
```sql
ALTER TABLE radpostauth
  ADD COLUMN nas_ip_address   VARCHAR(15)   NOT NULL DEFAULT '' AFTER authdate,
  ADD COLUMN nas_identifier   VARCHAR(64)   NULL AFTER nas_ip_address,
  ADD COLUMN nas_port         INT           NULL AFTER nas_identifier,
  ADD COLUMN calling_station_id VARCHAR(50) NULL AFTER nas_port,
  ADD COLUMN called_station_id  VARCHAR(50) NULL AFTER calling_station_id,
  ADD COLUMN reply_message    TEXT          NULL AFTER called_station_id,
  ADD COLUMN event_source     VARCHAR(32)   NOT NULL DEFAULT 'radius' AFTER reply_message,
  ADD COLUMN integrity_hash   VARCHAR(71)   NULL AFTER event_source;
```

---

### REQ-DB-002 — radpostauth: authdate inmutable
**ISO Control**: A.5.33 (CRÍTICA)  
**Title**: El timestamp de autenticación no debe ser modificable por actualizaciones posteriores

**Acceptance Scenarios**:
- **GIVEN** un registro en radpostauth con authdate='2026-01-01 10:00:00.123456'  
  **WHEN** se ejecuta UPDATE radpostauth SET reply='X' WHERE id=1  
  **THEN** authdate permanece '2026-01-01 10:00:00.123456' sin cambios
- **GIVEN** un nuevo Access-Request procesado  
  **WHEN** FreeRADIUS inserta el registro  
  **THEN** authdate se almacena como DATETIME(6) en UTC

**Schema delta**:
```sql
ALTER TABLE radpostauth
  MODIFY COLUMN authdate DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6);
-- (eliminar ON UPDATE CURRENT_TIMESTAMP)
```

---

### REQ-DB-003 — radpostauth: hash de integridad SHA-256
**ISO Control**: A.5.33 (CRÍTICA)  
**Title**: Cada registro de autenticación debe tener un hash SHA-256 para detección de tampering

**Acceptance Scenarios**:
- **GIVEN** un registro en radpostauth recién insertado  
  **WHEN** se recalcula el hash SHA-256 sobre (username, authdate, nas_ip_address, reply, calling_station_id)  
  **THEN** el resultado coincide con integrity_hash almacenado en el registro
- **GIVEN** un registro cuyo campo reply fue modificado directamente en BD  
  **WHEN** el servicio de verificación de integridad calcula el hash  
  **THEN** el hash calculado difiere del integrity_hash almacenado → alerta de tampering

---

### REQ-DB-004 — radacct: campos extendidos de sesión
**ISO Control**: A.8.15 (ALTA)  
**Title**: La tabla radacct debe registrar el identificador NAS, nivel de privilegio y atributos VSA

**Schema delta**:
```sql
ALTER TABLE radacct
  ADD COLUMN nasidentifier     VARCHAR(64)   NULL AFTER nasipaddress,
  ADD COLUMN privilege_level   VARCHAR(32)   NULL AFTER nasporttype,
  ADD COLUMN vendor_reply_attrs JSON          NULL AFTER privilege_level;
```

**Acceptance Scenarios**:
- **GIVEN** una sesión Accounting-Start con Cisco-AVPair shell:priv-lvl=15  
  **WHEN** FreeRADIUS inserta en radacct  
  **THEN** privilege_level='level-15' y vendor_reply_attrs contiene el JSON del atributo VSA

---

### REQ-DB-005 — Tabla radius_reply_audit
**ISO Controls**: A.5.15, A.8.2, A.5.18 (CRÍTICA)  
**Title**: Debe existir una tabla de auditoría extendida de Reply Attributes por sesión

**Schema**:
```sql
CREATE TABLE radius_reply_audit (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    radacctid         BIGINT          NOT NULL,
    username          VARCHAR(64)     NOT NULL,
    nas_ip            VARCHAR(15)     NOT NULL,
    nas_identifier    VARCHAR(64)     NULL,
    auth_timestamp    DATETIME(6)     NOT NULL,
    reply_attr_name   VARCHAR(128)    NOT NULL,
    reply_attr_value  TEXT            NOT NULL,
    vendor_id         INT             NULL,
    vendor_name       VARCHAR(64)     NULL,
    privilege_context VARCHAR(128)    NULL,
    created_at        DATETIME(6)     DEFAULT CURRENT_TIMESTAMP(6),
    record_hash       VARCHAR(71)     NULL,
    INDEX idx_username_ts (username, auth_timestamp),
    INDEX idx_nas_ip (nas_ip),
    FOREIGN KEY (radacctid) REFERENCES radacct(radacctid)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED
  COMMENT='Auditoría extendida de Reply Attributes por sesión RADIUS';
```

**Acceptance Scenarios**:
- **GIVEN** un Access-Accept con Cisco-AVPair shell:priv-lvl=15 enviado al NAS 10.1.1.1  
  **WHEN** la sesión es contabilizada (Accounting-Start)  
  **THEN** existe una fila en radius_reply_audit con vendor_name='Cisco', vendor_id=9, reply_attr_value='shell:priv-lvl=15'

---

### REQ-DB-006 — Tabla user_nas_privilege_map
**ISO Controls**: A.5.18, A.8.2 (CRÍTICA)  
**Title**: Debe existir una tabla de mapeo autorizado usuario-NAS-privilegio

**Schema**:
```sql
CREATE TABLE user_nas_privilege_map (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64)     NOT NULL,
    nas_ip          VARCHAR(15)     NOT NULL,
    nas_identifier  VARCHAR(64)     NULL,
    nas_vendor      VARCHAR(32)     NULL,
    radius_group    VARCHAR(64)     NOT NULL,
    privilege_level VARCHAR(32)     NOT NULL,
    justification   TEXT            NULL,
    approved_by     VARCHAR(64)     NOT NULL,
    approved_date   DATETIME        NOT NULL,
    review_date     DATETIME        NOT NULL,
    is_active       TINYINT(1)      DEFAULT 1,
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_nas (username, nas_ip),
    INDEX idx_review_date (review_date)
) ENGINE=InnoDB COMMENT='Mapeo autorizado usuario-NAS-privilegio — A.5.18';
```

**Acceptance Scenarios**:
- **GIVEN** un admin intenta asignar al usuario jperez el grupo grp_admin_cisco para el NAS 10.1.1.1  
  **WHEN** el endpoint POST /api/privilege-map es llamado con los datos requeridos (approved_by, review_date)  
  **THEN** el registro es creado con is_active=1 y aparece en la tabla
- **GIVEN** un mapeo activo cuya review_date ya pasó  
  **WHEN** el sistema consulta privilegios pendientes de revisión  
  **THEN** el mapeo aparece en el listado de accesos a revisar

---

### REQ-DB-007 — Tabla login_attempts
**ISO Control**: A.8.16, SEC-07 (CRÍTICA)  
**Title**: Debe existir una tabla para rastrear intentos de login fallidos y bloqueos

**Schema**:
```sql
CREATE TABLE login_attempts (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64)     NOT NULL,
    ip_address      VARCHAR(45)     NULL,
    attempted_at    DATETIME(6)     DEFAULT CURRENT_TIMESTAMP(6),
    success         TINYINT(1)      NOT NULL DEFAULT 0,
    INDEX idx_username_time (username, attempted_at)
) ENGINE=InnoDB;
```

---

### REQ-DB-008 — Columna role en admin_users
**ISO Control**: A.5.16, SOD-01..06 (ALTA)  
**Title**: La tabla admin_users debe tener un campo role para RBAC

**Schema delta**:
```sql
ALTER TABLE admin_users
  ADD COLUMN role VARCHAR(32) NOT NULL DEFAULT 'admin' AFTER email;
-- Valores válidos: superadmin, admin, helpdesk, auditor, readonly
```

**Acceptance Scenarios**:
- **GIVEN** el primer usuario admin creado al bootstrap  
  **WHEN** se consulta su rol  
  **THEN** role='superadmin'
- **GIVEN** un usuario con role='helpdesk'  
  **WHEN** intenta acceder a POST /api/users o PUT /api/groups  
  **THEN** recibe HTTP 403 Forbidden

---

### REQ-RADIUS-001 — Eliminar contraseña PAP de radpostauth
**ISO Control**: A.5.17 (CRÍTICA)  
**Title**: El campo pass en radpostauth NO debe almacenar la contraseña en texto claro

**Acceptance Scenarios**:
- **GIVEN** un usuario se autentica con PAP  
  **WHEN** FreeRADIUS inserta en radpostauth  
  **THEN** el campo pass contiene '[REDACTED]' y no la contraseña real
- **GIVEN** cualquier método de autenticación  
  **WHEN** se consulta radpostauth  
  **THEN** el campo pass nunca contiene una cadena que coincida con la contraseña real del usuario

**File**: `radius/sql` — postauth_query: reemplazar `%{User-Password:-Chap-Password}` por `'[REDACTED]'`

---

### REQ-RADIUS-002 — Campos NAS en postauth_query
**ISO Control**: A.8.15 (CRÍTICA)  
**Title**: La query de postauth debe insertar los campos NAS en radpostauth

**File**: `radius/sql` — postauth_query debe incluir nas_ip_address=%{NAS-IP-Address}, nas_identifier=%{NAS-Identifier}, calling_station_id=%{Calling-Station-Id}

---

## Phase 2 — Backend Security Layer

### REQ-BE-001 — Códigos de evento estructurados
**ISO Control**: A.8.15 (ALTA)  
**Title**: El servicio de auditoría debe clasificar cada evento con un código canónico

**Event codes**:
| Código | Trigger |
|--------|---------|
| AUTH-001 | Access-Accept registrado |
| AUTH-002 | Access-Reject genérico |
| AUTH-003 | Reject por usuario inexistente |
| AUTH-004 | Reject por contraseña inválida |
| AUTH-005 | Reject por NAS no autorizado |
| AUTH-006 | Reject por secreto compartido incorrecto |
| AUTH-007 | Timeout de autenticación |
| ACCT-001 | Accounting-Start |
| ACCT-002 | Accounting-Stop con duración |
| ACCT-003 | Interim-Update |
| ACCT-004 | Sesión sin Accounting-Stop (huérfana) |
| ADMIN-001 | Creación de usuario |
| ADMIN-002 | Modificación de atributos de usuario |
| ADMIN-003 | Eliminación/deshabilitación de usuario |
| ADMIN-004 | Modificación de grupo o perfil RADIUS |
| ADMIN-005 | Adición/modificación de NAS |
| ADMIN-006 | Modificación de atributos VSA |
| ADMIN-007 | Acceso a consola administrativa (login) |
| ADMIN-008 | Exportación de datos/logs |
| ADMIN-009 | Cambio de secreto compartido de NAS |

**Acceptance Scenarios**:
- **GIVEN** un admin modifica un grupo RADIUS  
  **WHEN** el endpoint PUT /api/groups/{id} es ejecutado  
  **THEN** se genera un evento ADMIN-004 en app_audit_log con los valores anteriores y nuevos
- **GIVEN** un admin hace login exitoso  
  **WHEN** POST /api/auth/login retorna 200  
  **THEN** se registra un evento ADMIN-007 con username, ip_address y timestamp

---

### REQ-BE-002 — Hash SHA-256 de integridad en registros de auditoría
**ISO Control**: A.5.33 (CRÍTICA)  
**Title**: El servicio de auditoría debe calcular y almacenar un hash SHA-256 de cada registro

**Algorithm**:
```python
campos_criticos = sorted([username, timestamp_utc, nas_ip, reply/action, calling_station_id])
payload = json.dumps({k: str(v) for k, v in campos}, sort_keys=True, ensure_ascii=True)
hash = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
```

**Acceptance Scenarios**:
- **GIVEN** un registro de radpostauth recién creado  
  **WHEN** el sistema recalcula el hash con los mismos campos  
  **THEN** el hash calculado == integrity_hash del registro
- **GIVEN** se modifica directamente el campo reply en BD  
  **WHEN** el verificador de integridad corre  
  **THEN** el hash no coincide → se genera una alerta en los logs del sistema

---

### REQ-BE-003 — Account lockout tras 5 intentos fallidos
**ISO Control**: A.8.16, SEC-07 (CRÍTICA)  
**Title**: Una cuenta debe bloquearse temporalmente tras 5 intentos de login fallidos en 10 minutos

**Acceptance Scenarios**:
- **GIVEN** un usuario intenta login 5 veces con contraseña incorrecta en 8 minutos  
  **WHEN** realiza el sexto intento  
  **THEN** recibe HTTP 429 con mensaje "Account temporarily locked. Try again after 15 minutes."
- **GIVEN** una cuenta bloqueada hace 16 minutos  
  **WHEN** el usuario intenta login con credenciales correctas  
  **THEN** el login es exitoso y el bloqueo ha expirado
- **GIVEN** una cuenta está bloqueada  
  **WHEN** un superadmin llama a POST /api/admin-users/{id}/unlock  
  **THEN** la cuenta es desbloqueada inmediatamente y se registra un evento ADMIN-002

---

### REQ-BE-004 — Sistema de roles RBAC
**ISO Controls**: A.5.16, SOD-01..06 (ALTA)  
**Title**: Todos los endpoints del backend deben respetar el rol del usuario autenticado

**Permission matrix**:
| Endpoint category | superadmin | admin | helpdesk | auditor | readonly |
|---|---|---|---|---|---|
| GET /api/audit/* | ✅ | ✅ | ✅ (sin datos sensibles) | ✅ | ✅ |
| POST/PUT/DELETE /api/users | ✅ | ✅ | ❌ | ❌ | ❌ |
| POST/PUT/DELETE /api/groups | ✅ | ✅ | ❌ | ❌ | ❌ |
| POST/PUT/DELETE /api/nas | ✅ | ✅ | ❌ | ❌ | ❌ |
| PUT /api/groups (VSA nivel 15+) | ✅ | ❌ | ❌ | ❌ | ❌ |
| POST/PUT/DELETE /api/admin-users | ✅ | ❌ | ❌ | ❌ | ❌ |
| GET /api/audit/export | ✅ | ✅ | ❌ | ✅ | ❌ |
| POST /api/privilege-map | ✅ | ✅ | ❌ | ❌ | ❌ |

**Acceptance Scenarios**:
- **GIVEN** un usuario con role='auditor' autenticado  
  **WHEN** llama a DELETE /api/users/{id}  
  **THEN** recibe HTTP 403 con body {"detail": "Insufficient permissions"}
- **GIVEN** un admin (no superadmin) intenta asignar Cisco-AVPair shell:priv-lvl=15  
  **WHEN** llama a PUT /api/groups/{id}  
  **THEN** recibe HTTP 403 con body {"detail": "Only superadmin can assign level-15 privileges"}

---

### REQ-BE-005 — SIEM JSON export endpoint
**ISO Control**: A.8.16 (ALTA)  
**Title**: El sistema debe proveer un endpoint para exportar logs en formato JSON estructurado para SIEM

**Endpoint**: `GET /api/audit/export`  
**Query params**: `format=json|csv`, `from=ISO8601`, `to=ISO8601`, `event_type=AUTH|ACCT|ADMIN`  
**Required role**: auditor, admin, superadmin

**Response format** (per event):
```json
{
  "event_id": "AUTH-001",
  "event_version": "1.0",
  "timestamp_utc": "2026-01-15T14:32:01.452817Z",
  "ntp_synchronized": true,
  "identity": { "username": "jperez", "user_group": "network-ops" },
  "access_request": { "nas_ip_address": "192.168.1.254", "nas_identifier": "router-core-01", "nas_vendor": "Cisco", "calling_station_id": "10.10.5.22" },
  "authorization_result": { "decision": "Access-Accept", "reply_attributes": [], "privilege_level": "level-15" },
  "audit": { "record_hash": "sha256:...", "tamper_evident": true }
}
```

**Acceptance Scenarios**:
- **GIVEN** existen 500 eventos entre 2026-01-01 y 2026-01-31  
  **WHEN** GET /api/audit/export?format=json&from=2026-01-01&to=2026-01-31  
  **THEN** responde HTTP 200 con Content-Type: application/json y un array de 500 eventos en el formato SIEM
- **GIVEN** un helpdesk intenta exportar  
  **WHEN** llama al endpoint  
  **THEN** recibe HTTP 403

---

### REQ-BE-006 — Validación de secreto NAS mínimo 32 caracteres
**ISO Control**: A.5.17, SEC-02 (ALTA)  
**Title**: No se debe poder crear/actualizar un NAS con secreto compartido menor a 32 caracteres

**Acceptance Scenarios**:
- **GIVEN** un admin intenta crear un NAS con secret='corto123'  
  **WHEN** llama a POST /api/nas  
  **THEN** recibe HTTP 422 con error "NAS shared secret must be at least 32 characters"
- **GIVEN** un secret de 32 caracteres aleatorios  
  **WHEN** se crea el NAS  
  **THEN** se crea exitosamente y se registra evento ADMIN-005

---

### REQ-BE-007 — Guardia de consistencia VSA por fabricante
**ISO Control**: REQ-VSA-02 (ALTA)  
**Title**: No se debe poder asignar atributos VSA de un fabricante a un NAS de otro fabricante

**Vendor-attribute mapping**:
- Vendor Cisco (9): Cisco-AVPair
- Vendor Juniper (2636): Juniper-Local-User-Name  
- Vendor Fortinet (12356): Fortinet-Group-Name, Fortinet-Vdom-Name
- Vendor Huawei (2011): Huawei-Exec-Privilege

**Acceptance Scenarios**:
- **GIVEN** un NAS registrado con vendor='Juniper'  
  **WHEN** se intenta asignar el atributo Cisco-AVPair a un grupo destinado a ese NAS  
  **THEN** el sistema rechaza con HTTP 422 "VSA Cisco-AVPair is not compatible with NAS vendor Juniper"
- **GIVEN** un grupo con Fortinet-Group-Name asignado a un NAS Fortinet  
  **WHEN** se valida la consistencia  
  **THEN** la validación pasa sin errores

---

### REQ-BE-008 — Guardia de alto privilegio VSA (level-15)
**ISO Controls**: A.8.2, REQ-VSA-03 (ALTA)  
**Title**: Los atributos de nivel administrador solo pueden ser asignados por superadmin a grupos con justificación documentada

**Acceptance Scenarios**:
- **GIVEN** un admin (no superadmin) intenta asignar Cisco-AVPair shell:priv-lvl=15  
  **WHEN** llama a PUT /api/groups/{id}  
  **THEN** recibe HTTP 403 "Only superadmin can assign level-15 or equivalent high-privilege VSA"
- **GIVEN** un superadmin asigna shell:priv-lvl=15 a un grupo  
  **WHEN** la operación es exitosa  
  **THEN** se genera evento ADMIN-006 con los valores anteriores y nuevos del atributo

---

### REQ-BE-009 — Endpoint de estado NTP
**ISO Control**: A.8.17 (ALTA)  
**Title**: El sistema debe exponer el estado de sincronización NTP del servidor

**Endpoint**: `GET /api/system/ntp-status`  
**Required role**: admin, superadmin

**Response**:
```json
{
  "synchronized": true,
  "offset_ms": 2.4,
  "stratum": 2,
  "reference_server": "ntp-interno-01.corp",
  "last_sync": "2026-03-14T23:00:00Z",
  "alert": false
}
```

**Acceptance Scenarios**:
- **GIVEN** el servidor tiene chrony/ntpd corriendo con offset < 500ms  
  **WHEN** GET /api/system/ntp-status  
  **THEN** responde {synchronized: true, alert: false}
- **GIVEN** el offset NTP supera 500ms  
  **WHEN** GET /api/system/ntp-status  
  **THEN** responde {synchronized: false, alert: true} y se genera una alerta en logs

---

## Phase 3 — Frontend + FreeRADIUS Policy

### REQ-FE-001 — Tabla de auditoría con columnas NAS
**ISO Control**: A.8.15 (ALTA)  
**Title**: La pestaña de auditoría de accesos debe mostrar NAS IP y Calling Station ID

**Acceptance Scenarios**:
- **GIVEN** la página Audit está abierta en la pestaña "Access Logs"  
  **WHEN** se cargan registros de radpostauth  
  **THEN** la tabla muestra columnas: Timestamp | Username | NAS IP | NAS Identifier | Calling Station | Result | Event Code
- **GIVEN** se filtra por NAS IP '192.168.1.254'  
  **WHEN** el filtro es aplicado  
  **THEN** solo se muestran registros donde nas_ip_address='192.168.1.254'

---

### REQ-FE-002 — Página de mapeo usuario-NAS-privilegio
**ISO Controls**: A.5.18, A.8.2 (ALTA)  
**Title**: Debe existir una página de administración del mapeo usuario-NAS-privilegio

**Acceptance Scenarios**:
- **GIVEN** un superadmin navega a /privilege-map  
  **WHEN** la página carga  
  **THEN** se muestra una tabla con todas las entradas de user_nas_privilege_map con columnas: Username | NAS IP | Vendor | Group | Privilege Level | Review Date | Status
- **GIVEN** la review_date de un mapeo está dentro de 30 días  
  **WHEN** la página carga  
  **THEN** el registro se muestra con badge "Revisión próxima" en amarillo
- **GIVEN** un superadmin hace click en "New Mapping"  
  **WHEN** completa el formulario con username, nas_ip, radius_group, privilege_level, justification, approved_by, review_date  
  **THEN** el mapeo es creado y aparece en la tabla
- **GIVEN** un auditor navega a /privilege-map  
  **WHEN** la página carga  
  **THEN** puede ver los mapeos pero no tiene botones de crear/editar/eliminar

---

### REQ-FE-003 — UI con restricciones por rol
**ISO Control**: SOD-01..06 (ALTA)  
**Title**: La interfaz de usuario debe ocultar o deshabilitar funcionalidades según el rol del usuario autenticado

**Acceptance Scenarios**:
- **GIVEN** un usuario autenticado con role='helpdesk'  
  **WHEN** navega a la aplicación  
  **THEN** el menú de navegación NO muestra: Admin Users, Groups (write), NAS (write); solo muestra: Audit (read-only), Users (read-only)
- **GIVEN** un usuario con role='auditor'  
  **WHEN** intenta acceder a /admin-users directamente por URL  
  **THEN** es redirigido a /unauthorized
- **GIVEN** el token JWT contiene role='superadmin'  
  **WHEN** la aplicación carga  
  **THEN** todos los elementos de menú y botones de acción están visibles y habilitados

---

### REQ-RADIUS-003 — Política NAS-condicional en FreeRADIUS (unlang)
**ISO Controls**: A.8.3, A.5.18 (ALTA)  
**Title**: FreeRADIUS debe aplicar políticas de autorización condicionales por NAS-IP-Address

**File**: `radius/policy.d/nas_based_authorization`

**Acceptance Scenarios**:
- **GIVEN** el usuario jperez se autentica desde el NAS 10.1.1.1 (Cisco admin)  
  **WHEN** FreeRADIUS evalúa la política  
  **THEN** el grupo asignado es grp_admin_cisco y el VSA Cisco-AVPair=shell:priv-lvl=15 es enviado
- **GIVEN** el mismo usuario jperez se autentica desde NAS 10.1.1.2 (Cisco readonly)  
  **WHEN** FreeRADIUS evalúa la política  
  **THEN** el grupo asignado es grp_readonly_cisco con privilegio nivel 1
- **GIVEN** un usuario se autentica desde un NAS no registrado en clients.conf  
  **WHEN** FreeRADIUS evalúa la política  
  **THEN** el resultado es Access-Reject con Reply-Message="Access denied: NAS not authorized" y se registra AUTH-005

---

## Non-functional Requirements

### REQ-NF-001 — Performance
- La validación de hash SHA-256 no debe añadir más de 5ms de latencia al procesamiento de cada evento de auditoría
- El endpoint SIEM export debe soportar hasta 10,000 registros por respuesta con paginación

### REQ-NF-002 — Backward compatibility
- Las migraciones de BD deben ser reversibles (Alembic downgrade)
- Los nuevos campos en radpostauth y radacct deben tener DEFAULT values para no romper la query de FreeRADIUS hasta que sea actualizada

### REQ-NF-003 — Observability
- Todo evento de bloqueo de cuenta debe aparecer en los logs de aplicación (INFO level)
- Los errores de validación VSA deben aparecer como WARNING en los logs
- Las alertas de NTP offset > 500ms deben aparecer como ERROR en los logs

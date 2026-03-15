# Especificaciones Técnicas de Logging y Monitoreo para Sistema RADIUS/daloRADIUS
## Cumplimiento ISO/IEC 27001:2022 — Dominio A.8 (Controles Tecnológicos)

---

> **Clasificación del Documento:** Confidencial — Uso Interno  
> **Versión:** 1.0  
> **Fecha de Emisión:** 2025  
> **Revisión:** Anual o ante cambios materiales en la arquitectura  
> **Propietario:** Oficial de Seguridad de la Información (CISO)  
> **Audiencia:** Equipo de Seguridad TI, Arquitectura de Red, Auditoría Interna

---

## Tabla de Contenidos

1. [Introducción y Objetivos](#1-introducción-y-objetivos)
2. [Alcance y Arquitectura de Referencia](#2-alcance-y-arquitectura-de-referencia)
3. [Matriz de Requisitos de Control — Mapeo ISO 27001:2022](#3-matriz-de-requisitos-de-control--mapeo-iso-270012022)
4. [Requisitos de Logging y Monitoreo — Control A.8.15 / A.8.16](#4-requisitos-de-logging-y-monitoreo--control-a815--a816)
5. [Especificaciones Técnicas de Registro en daloRADIUS](#5-especificaciones-técnicas-de-registro-en-daloradius)
6. [Gestión de Attributes/Replies por Fabricante](#6-gestión-de-attributesreplies-por-fabricante)
7. [Segregación de Funciones y Múltiples Niveles de Acceso](#7-segregación-de-funciones-y-múltiples-niveles-de-acceso)
8. [Protección de Registros y Sincronización de Tiempo (NTP)](#8-protección-de-registros-y-sincronización-de-tiempo-ntp)
9. [Recomendaciones de Seguridad y Retención](#9-recomendaciones-de-seguridad-y-retención)
10. [Glosario](#10-glosario)
11. [Referencias Normativas](#11-referencias-normativas)

---

## 1. Introducción y Objetivos

### 1.1 Contexto

La gestión de acceso a infraestructura de TI mediante el protocolo RADIUS (Remote Authentication Dial-In User Service) constituye un componente crítico dentro del modelo de control de acceso de la organización. La implementación de daloRADIUS como interfaz de gestión, en un entorno multimarca y multimodelo con lógica de privilegios diferenciados por equipo destino, introduce una complejidad operativa que exige un marco de registro y monitoreo robusto y auditable.

El presente documento define las especificaciones técnicas y normativas que debe satisfacer el sistema de logging de acceso para cumplir con los requisitos de la norma **ISO/IEC 27001:2022**, garantizando trazabilidad, integridad y disponibilidad de los registros de auditoría.

### 1.2 Objetivos del Documento

- **OBJ-01:** Definir los requisitos mínimos y recomendados de logging para el flujo de autenticación y autorización RADIUS/daloRADIUS.
- **OBJ-02:** Establecer la estructura de los registros para garantizar trazabilidad completa: quién, cuándo, desde dónde, hacia dónde y con qué nivel de privilegio.
- **OBJ-03:** Especificar la gestión de atributos de respuesta RADIUS personalizados por fabricante (VSA — Vendor-Specific Attributes), asegurando la integridad del control de acceso.
- **OBJ-04:** Definir los mecanismos de protección, retención e integridad de los registros de log.
- **OBJ-05:** Establecer los controles para la segregación de funciones en contextos de múltiples niveles de acceso por usuario.
- **OBJ-06:** Proveer una matriz de trazabilidad entre los controles implementados y los requerimientos de la ISO/IEC 27001:2022.

### 1.3 Principios Rectores

| Principio | Descripción |
|-----------|-------------|
| **No repudio** | Todo evento de acceso debe ser atribuible de forma inequívoca a una identidad verificada |
| **Completitud** | Los registros deben capturar la totalidad del ciclo de vida de una sesión de acceso |
| **Integridad** | Los logs deben ser protegidos contra modificación o eliminación no autorizada |
| **Disponibilidad** | Los registros deben estar disponibles para auditoría dentro de los tiempos de retención definidos |
| **Mínimo privilegio** | Los atributos de respuesta deben reflejar únicamente el nivel de acceso necesario por contexto |

---

## 2. Alcance y Arquitectura de Referencia

### 2.1 Alcance

Este documento aplica a todos los componentes involucrados en el flujo de autenticación, autorización y contabilización (AAA) mediante RADIUS, incluyendo:

- Servidor RADIUS (FreeRADIUS u otro) gestionado mediante daloRADIUS
- Equipos de red de acceso (NAS — Network Access Servers) de múltiples fabricantes
- Sistemas de almacenamiento y correlación de logs (SIEM)
- Infraestructura de sincronización de tiempo (NTP)
- Repositorios de identidad (LDAP, Active Directory u equivalente)

### 2.2 Arquitectura de Referencia

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PLANO DE GESTIÓN                             │
│  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │   daloRADIUS    │◄──►│  FreeRADIUS      │◄──►│  LDAP / AD   │  │
│  │  (Web UI/API)   │    │  (AAA Engine)    │    │  (IdP)       │  │
│  └─────────────────┘    └──────┬───────────┘    └───────────────┘  │
│           │                    │                                     │
│           │             ┌──────▼───────────┐                        │
│           │             │  Base de Datos   │                        │
│           │             │  (radacct/radlog)│                        │
│           │             └──────────────────┘                        │
└───────────┼────────────────────────────────────────────────────────┘
            │
            ▼ Exportación de Logs (Syslog/API)
┌─────────────────────────────────────────────────────────────────────┐
│                     PLANO DE MONITOREO                              │
│  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │   SIEM          │◄──►│  Log Aggregator  │◄───│  NTP Server   │  │
│  │  (Correlación)  │    │  (Centralización)│    │  (Tiempo)     │  │
│  └─────────────────┘    └──────────────────┘    └───────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
            ▲
            │ Auth/Accounting (RADIUS UDP 1812/1813)
┌─────────────────────────────────────────────────────────────────────┐
│                   PLANO DE DATOS (NAS)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Router      │  │  Switch      │  │ Firewall │  │  VPN GW   │  │
│  │  (Cisco)     │  │  (Juniper)   │  │  (F5)   │  │  (Fortinet)│  │
│  └──────────────┘  └──────────────┘  └──────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 Flujo AAA — Ciclo de Vida del Acceso

```
Usuario/Admin ──► [1] Access-Request ──► RADIUS Server
                                              │
                                    [2] Consulta BD / LDAP
                                              │
                                    [3] Evaluación de Política
                                         (Usuario + NAS-IP)
                                              │
                              ┌───────────────┴──────────────┐
                              │                               │
                    [4a] Access-Accept              [4b] Access-Reject
                    + Reply Attributes              + Reply-Message
                              │                               │
                    [5] Accounting-Start            [5] Log de Rechazo
                              │
                    [6] Sesión Activa
                              │
                    [7] Accounting-Stop
                    (con estadísticas de sesión)
```

---

## 3. Matriz de Requisitos de Control — Mapeo ISO 27001:2022

La siguiente tabla correlaciona cada control de la norma ISO/IEC 27001:2022 con los requisitos específicos implementados en el sistema RADIUS/daloRADIUS.

| ID Control ISO 27001:2022 | Nombre del Control | Aplicabilidad en RADIUS/daloRADIUS | Requisito Técnico Asociado | Prioridad |
|---|---|---|---|---|
| **A.5.15** | Control de Acceso | Gestión de perfiles de acceso y atributos RADIUS por usuario y NAS | Tabla `radreply`; políticas por `NAS-IP-Address` | **CRÍTICA** |
| **A.5.16** | Gestión de Identidad | Ciclo de vida de cuentas de usuario en daloRADIUS y sincronización con IdP | Auditoría de altas, bajas y modificaciones en `radcheck` | **CRÍTICA** |
| **A.5.17** | Información de Autenticación | Protección de credenciales (CHAP/EAP-TLS vs PAP) y gestión de secretos compartidos RADIUS | Prohibición de PAP; uso de EAP o CHAP; rotación de `nas.secret` | **CRÍTICA** |
| **A.5.18** | Derechos de Acceso | Implementación del principio de mínimo privilegio mediante atributos de respuesta | VSA por perfil; revisión periódica de `radgroupreply` | **ALTA** |
| **A.8.2** | Derechos de Acceso Privilegiado | Control de acceso a nivel 15 (Cisco) o equivalente en otros fabricantes | Mapeo de `Cisco-AVPair` con `shell:priv-lvl=15` solo a perfiles autorizados | **CRÍTICA** |
| **A.8.15** | Registro de Actividades (Logging) | Registro completo del ciclo AAA: Access-Request, Accept/Reject, Accounting | Campos mínimos en `radacct` y `radpostauth`; exportación a SIEM | **CRÍTICA** |
| **A.8.16** | Actividades de Monitoreo | Monitoreo continuo de intentos fallidos, cambios de perfil y anomalías | Reglas de correlación en SIEM; alertas automáticas | **ALTA** |
| **A.8.17** | Sincronización de Relojes | NTP para garantizar la secuencia temporal correcta de los eventos | Configuración de NTP en servidor RADIUS y todos los NAS | **ALTA** |
| **A.8.3** | Restricción de Acceso a la Información | Segmentación de acceso basada en el equipo destino (NAS-IP) | Políticas condicionales por `NAS-IP-Address` o `NAS-Identifier` | **ALTA** |
| **A.5.33** | Protección de Registros | Integridad e inmutabilidad de los logs de RADIUS | Permisos restrictivos sobre tablas de log; replicación a SIEM inmutable | **CRÍTICA** |
| **A.5.34** | Privacidad y Protección de Datos Personales | Tratamiento de username y datos de sesión conforme a normativas de privacidad | Pseudonimización en logs de largo plazo; control de acceso a `radacct` | **MEDIA** |
| **A.8.9** | Gestión de la Configuración | Control de cambios sobre perfiles RADIUS, grupos y atributos VSA | Registro de cambios en daloRADIUS con usuario responsable y timestamp | **ALTA** |
| **A.5.30** | Disponibilidad de TI | Alta disponibilidad del servidor RADIUS para garantizar la continuidad del acceso | Redundancia RADIUS (primario/secundario); monitoreo de disponibilidad | **ALTA** |

---

## 4. Requisitos de Logging y Monitoreo — Control A.8.15 / A.8.16

### 4.1 Eventos de Auditoría Obligatorios

El sistema debe registrar **todos** los eventos del ciclo AAA sin excepción. La siguiente clasificación establece los eventos mínimos requeridos:

#### 4.1.1 Eventos de Autenticación (Access-Request)

| Código Evento | Descripción | Criticidad | Acción Requerida |
|---|---|---|---|
| `AUTH-001` | Intento de autenticación exitoso (Access-Accept) | ALTA | Registro + Correlación SIEM |
| `AUTH-002` | Intento de autenticación fallido (Access-Reject) | ALTA | Registro + Alerta si > umbral |
| `AUTH-003` | Autenticación rechazada por usuario inexistente | ALTA | Registro + Alerta inmediata |
| `AUTH-004` | Autenticación rechazada por contraseña inválida | ALTA | Registro + Bloqueo progresivo |
| `AUTH-005` | Autenticación rechazada por NAS no autorizado | CRÍTICA | Registro + Alerta inmediata |
| `AUTH-006` | Solicitud de acceso con secreto compartido incorrecto | CRÍTICA | Registro + Alerta inmediata |
| `AUTH-007` | Timeout de autenticación (no response) | MEDIA | Registro |

#### 4.1.2 Eventos de Contabilización (Accounting)

| Código Evento | Descripción | Criticidad | Acción Requerida |
|---|---|---|---|
| `ACCT-001` | Inicio de sesión (Accounting-Start) | ALTA | Registro obligatorio |
| `ACCT-002` | Fin de sesión (Accounting-Stop) con duración | ALTA | Registro obligatorio |
| `ACCT-003` | Actualización de sesión (Interim-Update) | MEDIA | Registro |
| `ACCT-004` | Sesión sin Accounting-Stop correspondiente | ALTA | Alerta + Investigación |

#### 4.1.3 Eventos de Administración (daloRADIUS)

| Código Evento | Descripción | Criticidad | Acción Requerida |
|---|---|---|---|
| `ADMIN-001` | Creación de usuario en daloRADIUS | ALTA | Registro + Aprobación workflow |
| `ADMIN-002` | Modificación de atributos de usuario | ALTA | Registro con valores anteriores y nuevos |
| `ADMIN-003` | Eliminación / deshabilitación de usuario | ALTA | Registro + Notificación |
| `ADMIN-004` | Modificación de grupo o perfil RADIUS | CRÍTICA | Registro con diff de cambios |
| `ADMIN-005` | Adición/modificación de NAS (cliente RADIUS) | CRÍTICA | Registro + Notificación |
| `ADMIN-006` | Modificación de atributos VSA por fabricante | CRÍTICA | Registro con auditoría completa |
| `ADMIN-007` | Acceso a la consola administrativa de daloRADIUS | ALTA | Registro de sesión completa |
| `ADMIN-008` | Exportación de datos de cuentas o logs | ALTA | Registro + Aprobación |
| `ADMIN-009` | Cambio de secreto compartido de NAS | CRÍTICA | Registro + Notificación inmediata |

### 4.2 Estructura de Registro — Principio de Trazabilidad Total

Cada registro de log debe responder las cinco dimensiones de trazabilidad:

```
┌─────────────────────────────────────────────────────────┐
│          DIMENSIONES DE TRAZABILIDAD COMPLETA           │
├──────────────┬──────────────────────────────────────────┤
│  QUIÉN       │  Username + NAS-Identifier (origen)      │
│  CUÁNDO      │  Timestamp UTC (ISO 8601) + NTP sync     │
│  DESDE DÓNDE │  NAS-IP-Address + Calling-Station-Id     │
│  HACIA DÓNDE │  NAS-IP-Address + Called-Station-Id      │
│  QUÉ NIVEL   │  Reply Attributes (VSA por fabricante)   │
└──────────────┴──────────────────────────────────────────┘
```

---

## 5. Especificaciones Técnicas de Registro en daloRADIUS

### 5.1 Tablas de Base de Datos — Campos Obligatorios

#### 5.1.1 Tabla `radpostauth` — Registro de Autenticación

Esta tabla registra todos los intentos de autenticación, tanto exitosos como fallidos.

| Campo | Tipo | Descripción | Obligatorio | Ejemplo |
|---|---|---|---|---|
| `id` | BIGINT AUTO_INCREMENT | Identificador único del registro | Sí | `10045231` |
| `username` | VARCHAR(64) | Nombre de usuario que realiza el intento | Sí | `jperez` |
| `pass` | VARCHAR(64) | **No almacenar en texto plano.** Usar hash o campo vacío | Sí | `[REDACTED]` |
| `reply` | VARCHAR(32) | Resultado: `Access-Accept` o `Access-Reject` | Sí | `Access-Accept` |
| `authdate` | DATETIME(6) | Timestamp con microsegundos en UTC | Sí | `2025-06-15 14:32:01.452817` |
| `nas_ip_address` | VARCHAR(15) | IP del NAS que origina la solicitud | Sí | `192.168.1.254` |
| `nas_identifier` | VARCHAR(64) | Nombre del equipo NAS (hostname) | Recomendado | `router-core-01` |
| `nas_port` | INT | Puerto del NAS desde donde se autentica | Recomendado | `0` |
| `calling_station_id` | VARCHAR(50) | IP o MAC de la estación del cliente | Recomendado | `10.10.5.22` |
| `called_station_id` | VARCHAR(50) | IP o identificador del equipo destino | Recomendado | `192.168.1.254` |
| `framed_ip_address` | VARCHAR(15) | IP asignada al usuario (si aplica) | Condicional | `10.20.1.50` |
| `class` | VARCHAR(64) | Clase de sesión para correlación | Recomendado | `MGMT-NETWORK-OPS` |
| `reply_message` | TEXT | Mensaje de respuesta en caso de rechazo | Recomendado | `Invalid credentials` |
| `event_source` | VARCHAR(32) | Origen del evento: `radius`, `daloradius` | Sí | `radius` |
| `integrity_hash` | VARCHAR(64) | Hash SHA-256 del registro para detección de tampering | Recomendado | `a3f4b2...` |

#### 5.1.2 Tabla `radacct` — Registro de Contabilización (Accounting)

Esta tabla es el registro principal de trazabilidad de sesiones activas y cerradas.

| Campo | Tipo | Descripción | Obligatorio | Ejemplo |
|---|---|---|---|---|
| `radacctid` | BIGINT AUTO_INCREMENT | Identificador único de la sesión | Sí | `5023901` |
| `acctsessionid` | VARCHAR(64) | ID de sesión generado por el NAS | Sí | `0000003E` |
| `acctuniqueid` | VARCHAR(32) | ID único calculado por RADIUS | Sí | `8f3a21bc...` |
| `username` | VARCHAR(64) | Usuario autenticado | Sí | `jperez` |
| `realm` | VARCHAR(64) | Realm del usuario si aplica | Condicional | `corp.empresa.com` |
| `nasipaddress` | VARCHAR(15) | IP del NAS | Sí | `192.168.1.254` |
| `nasidentifier` | VARCHAR(64) | Hostname del NAS | Sí | `router-core-01` |
| `nasportid` | VARCHAR(15) | Puerto de acceso | Sí | `tty0` |
| `nasporttype` | VARCHAR(32) | Tipo de puerto: `Virtual`, `Async`, etc. | Sí | `Virtual` |
| `acctstarttime` | DATETIME(6) | Timestamp de inicio de sesión UTC | Sí | `2025-06-15 14:32:01.452817` |
| `acctstoptime` | DATETIME(6) | Timestamp de fin de sesión UTC | Condicional | `2025-06-15 15:10:44.001200` |
| `acctsessiontime` | INT | Duración total en segundos | Condicional | `2322` |
| `acctterminatecause` | VARCHAR(32) | Causa de terminación de sesión | Condicional | `User-Request` |
| `calledstationid` | VARCHAR(50) | Identificador del equipo destino | Sí | `192.168.1.254` |
| `callingstationid` | VARCHAR(50) | IP de origen del administrador | Sí | `10.10.5.22` |
| `framedipaddress` | VARCHAR(15) | IP asignada al usuario | Condicional | `10.20.1.50` |
| `acctstartdelay` | INT | Retardo en el inicio de contabilización | Diagnóstico | `0` |
| `connectinfo_start` | VARCHAR(128) | Información de conexión al inicio | Recomendado | `Cisco IOS 15.x` |
| `privilege_level` | VARCHAR(32) | Nivel de privilegio otorgado (campo extendido) | Sí | `level-15` |
| `vendor_reply_attrs` | TEXT JSON | Atributos VSA incluidos en el Access-Accept | Sí | Ver sección 6 |

#### 5.1.3 Registro Extendido de Atributos de Respuesta

Se debe implementar una tabla adicional o campo JSON para almacenar los atributos de respuesta otorgados en cada sesión:

```sql
CREATE TABLE radius_reply_audit (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    radacctid       BIGINT NOT NULL,          -- FK a radacct.radacctid
    username        VARCHAR(64) NOT NULL,
    nas_ip          VARCHAR(15) NOT NULL,
    nas_identifier  VARCHAR(64),
    auth_timestamp  DATETIME(6) NOT NULL,
    reply_attr_name VARCHAR(128) NOT NULL,     -- Nombre del atributo
    reply_attr_value TEXT NOT NULL,            -- Valor del atributo
    vendor_id       INT,                       -- PEN del fabricante (IANA)
    vendor_name     VARCHAR(64),              -- Nombre del fabricante
    privilege_context VARCHAR(128),           -- Contexto de privilegio
    created_at      DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    record_hash     VARCHAR(64),              -- SHA-256 del registro
    INDEX idx_username_ts (username, auth_timestamp),
    INDEX idx_nas_ip (nas_ip),
    FOREIGN KEY (radacctid) REFERENCES radacct(radacctid)
) ENGINE=InnoDB
  ROW_FORMAT=COMPRESSED
  COMMENT='Auditoría extendida de Reply Attributes por sesión RADIUS';
```

### 5.2 Formato de Log para Exportación — Estructura JSON Estandarizada

Todos los logs exportados al SIEM deben seguir el siguiente esquema JSON normalizado:

```json
{
  "event_id": "AUTH-001",
  "event_version": "1.0",
  "timestamp_utc": "2025-06-15T14:32:01.452817Z",
  "ntp_synchronized": true,
  "clock_offset_ms": 2,

  "identity": {
    "username": "jperez",
    "realm": "corp.empresa.com",
    "user_group": "network-ops",
    "authentication_method": "CHAP"
  },

  "access_request": {
    "nas_ip_address": "192.168.1.254",
    "nas_identifier": "router-core-01",
    "nas_vendor": "Cisco",
    "nas_model": "ASR1001-X",
    "nas_port": "tty0",
    "nas_port_type": "Virtual",
    "calling_station_id": "10.10.5.22",
    "called_station_id": "192.168.1.254"
  },

  "authorization_result": {
    "decision": "Access-Accept",
    "reply_attributes": [
      {
        "vendor": "Cisco",
        "vendor_id": 9,
        "attribute": "Cisco-AVPair",
        "value": "shell:priv-lvl=15"
      },
      {
        "vendor": "Standard",
        "vendor_id": 0,
        "attribute": "Service-Type",
        "value": "NAS-Prompt-User"
      }
    ],
    "privilege_level": "level-15",
    "privilege_context": "FULL_ACCESS_NETWORK_OPS"
  },

  "session": {
    "session_id": "0000003E",
    "unique_id": "8f3a21bc4d9e1022",
    "start_time": "2025-06-15T14:32:01.452817Z",
    "stop_time": "2025-06-15T15:10:44.001200Z",
    "duration_seconds": 2322,
    "termination_cause": "User-Request"
  },

  "audit": {
    "log_source": "freeradius-01.corp.empresa.com",
    "log_collector": "siem-aggregator-01",
    "record_hash": "sha256:a3f4b2c1d9e8f7a6b5c4d3e2f1a0b9c8...",
    "tamper_evident": true
  }
}
```

---

## 6. Gestión de Attributes/Replies por Fabricante

### 6.1 Problema de Complejidad Multifabricante

En entornos multimarca, el sistema RADIUS debe gestionar Vendor-Specific Attributes (VSA) con semánticas distintas para otorgar niveles equivalentes de privilegio. El riesgo principal es la **divergencia silenciosa**: el servidor RADIUS entrega un atributo que el NAS no reconoce, resultando en un nivel de acceso diferente al esperado — ya sea inferior (denegación funcional) o superior (escalación de privilegios).

### 6.2 Catálogo de Atributos VSA por Fabricante

#### 6.2.1 Cisco IOS / IOS-XE / IOS-XR

| Nivel de Acceso | Atributo RADIUS | Valor | Tipo |
|---|---|---|---|
| Solo lectura (nivel 1) | `Cisco-AVPair` | `shell:priv-lvl=1` | VSA (Vendor 9) |
| Operador (nivel 7) | `Cisco-AVPair` | `shell:priv-lvl=7` | VSA (Vendor 9) |
| Administrador completo (nivel 15) | `Cisco-AVPair` | `shell:priv-lvl=15` | VSA (Vendor 9) |
| Acceso exec restringido | `Cisco-AVPair` | `shell:roles="network-operator"` | VSA (Vendor 9) — NX-OS |
| Acceso completo NX-OS | `Cisco-AVPair` | `shell:roles="network-admin"` | VSA (Vendor 9) — NX-OS |

#### 6.2.2 Juniper Junos

| Nivel de Acceso | Atributo RADIUS | Valor | Tipo |
|---|---|---|---|
| Solo lectura | `Juniper-Local-User-Name` | `readonly-user` | VSA (Vendor 2636) |
| Operador | `Juniper-Local-User-Name` | `operator-user` | VSA (Vendor 2636) |
| Administrador completo | `Juniper-Local-User-Name` | `superuser` | VSA (Vendor 2636) |
| Clases personalizadas | `Juniper-Local-User-Name` + `Framed-Filter-Id` | Clase definida en Junos | VSA combinado |

#### 6.2.3 Fortinet FortiGate

| Nivel de Acceso | Atributo RADIUS | Valor | Tipo |
|---|---|---|---|
| Solo lectura | `Fortinet-Group-Name` | `readonly_profile` | VSA (Vendor 12356) |
| Operador | `Fortinet-Group-Name` | `operator_profile` | VSA (Vendor 12356) |
| Administrador | `Fortinet-Group-Name` | `super_admin_profile` | VSA (Vendor 12356) |
| Dominio virtual | `Fortinet-Vdom-Name` | `nombre_vdom` | VSA (Vendor 12356) |

#### 6.2.4 Huawei VRP

| Nivel de Acceso | Atributo RADIUS | Valor | Tipo |
|---|---|---|---|
| Visitante | `Huawei-Exec-Privilege` | `0` | VSA (Vendor 2011) |
| Monitoreo | `Huawei-Exec-Privilege` | `1` | VSA (Vendor 2011) |
| Operador | `Huawei-Exec-Privilege` | `3` | VSA (Vendor 2011) |
| Administrador | `Huawei-Exec-Privilege` | `15` | VSA (Vendor 2011) |

#### 6.2.5 Atributos Estándar RFC 2865 / RFC 2868 (Aplicables a todos los fabricantes)

| Atributo | Tipo Valor | Propósito de Auditoría |
|---|---|---|
| `Service-Type` | `NAS-Prompt-User` / `Administrative-User` | Tipo de servicio otorgado |
| `Session-Timeout` | Integer (segundos) | Tiempo máximo de sesión |
| `Idle-Timeout` | Integer (segundos) | Timeout por inactividad |
| `Filter-Id` | String | Nombre de ACL/política aplicada |
| `Class` | String | Etiqueta de clase para correlación en accounting |
| `Reply-Message` | String | Mensaje enviado al usuario |

### 6.3 Política de Registro de VSA — Requisitos de Integridad

**REQ-VSA-01 — Registro obligatorio de todos los atributos de respuesta:**
Cada `Access-Accept` debe registrar la totalidad de los VSA enviados al NAS, incluyendo nombre del atributo, valor, vendor ID (IANA PEN) y vendor name.

**REQ-VSA-02 — Validación de consistencia NAS-Atributo:**
Antes de persistir el log, el sistema debe verificar que los VSA enviados corresponden al fabricante del NAS receptor. Enviar un atributo Cisco a un NAS Juniper debe generar una alerta de configuración.

**REQ-VSA-03 — Prohibición de atributos de alto privilegio sin grupo autorizado:**
Los atributos que confieran acceso de nivel administrador (e.g., `priv-lvl=15`, `superuser`, `super_admin_profile`) solo pueden ser enviados a usuarios miembros de grupos con aprobación explícita documentada en el sistema de gestión de identidades.

**REQ-VSA-04 — Auditoría de cambios en tablas de atributos:**
Toda modificación en las tablas `radreply` y `radgroupreply` debe generar un evento `ADMIN-006` con los valores previos y nuevos, el usuario administrador responsable y un timestamp preciso.

**REQ-VSA-05 — Pruebas de validación post-cambio:**
Tras cualquier modificación de atributos VSA, se debe ejecutar un test de autenticación controlado (`radtest` o equivalente) y registrar el resultado como evidencia de validación.

### 6.4 Estructura de Configuración en daloRADIUS — `radgroupreply`

```sql
-- Ejemplo: Perfil para administradores Cisco (nivel 15)
-- Grupo: grp_admin_cisco
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
  ('grp_admin_cisco', 'Cisco-AVPair',   ':=', 'shell:priv-lvl=15'),
  ('grp_admin_cisco', 'Service-Type',   ':=', 'NAS-Prompt-User'),
  ('grp_admin_cisco', 'Session-Timeout',':=', '3600'),
  ('grp_admin_cisco', 'Idle-Timeout',   ':=', '900');

-- Ejemplo: Perfil para operadores Juniper (readonly)
-- Grupo: grp_oper_juniper
INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES
  ('grp_oper_juniper', 'Juniper-Local-User-Name', ':=', 'readonly-user'),
  ('grp_oper_juniper', 'Service-Type',            ':=', 'NAS-Prompt-User'),
  ('grp_oper_juniper', 'Session-Timeout',         ':=', '1800'),
  ('grp_oper_juniper', 'Idle-Timeout',            ':=', '600');
```

---

## 7. Segregación de Funciones y Múltiples Niveles de Acceso por Usuario

### 7.1 Modelo de Múltiples Privilegios por Usuario

La norma ISO/IEC 27001:2022 en su control **A.5.18 (Derechos de Acceso)** y **A.8.2 (Derechos de Acceso Privilegiado)** requiere que el acceso privilegiado sea estrictamente controlado y justificado. En el contexto de este sistema, un único usuario puede poseer niveles de acceso diferentes dependiendo del equipo destino, lo cual requiere un modelo de políticas condicionales.

### 7.2 Modelo de Política Condicional por NAS

El servidor RADIUS debe implementar políticas condicionales que otorguen diferentes atributos de respuesta según el `NAS-IP-Address` o `NAS-Identifier` del equipo destino:

```
Política de Autorización:
═══════════════════════════════════════════════════════════════
IF (Username == "jperez") AND (NAS-IP == "10.1.1.1")      → grp_admin_cisco
IF (Username == "jperez") AND (NAS-IP == "10.1.1.2")      → grp_readonly_cisco
IF (Username == "jperez") AND (NAS-IP == "10.2.0.1")      → grp_oper_juniper
IF (Username == "jperez") AND (NAS-IP NOT IN whitelist)    → Access-Reject
═══════════════════════════════════════════════════════════════
```

**Implementación en FreeRADIUS (`unlang`):**

```unlang
# /etc/freeradius/3.0/policy.d/nas_based_authorization

nas_based_authorization {
    # Verificar si el NAS está en la lista de equipos autorizados
    if (!(&NAS-IP-Address || &NAS-Identifier)) {
        reject
    }

    # Política basada en NAS-IP-Address
    switch &NAS-IP-Address {
        case "10.1.1.1" {
            update control {
                Auth-Type := ldap
                Ldap-Group := "grp_admin_cisco"
            }
        }
        case "10.1.1.2" {
            update control {
                Auth-Type := ldap
                Ldap-Group := "grp_readonly_cisco"
            }
        }
        case "10.2.0.1" {
            update control {
                Auth-Type := ldap
                Ldap-Group := "grp_oper_juniper"
            }
        }
        default {
            # NAS no reconocido — rechazar y alertar
            update reply {
                Reply-Message := "Access denied: NAS not authorized"
            }
            reject
        }
    }
}
```

### 7.3 Tabla de Mapeo Usuario-NAS-Privilegio

Se recomienda mantener una tabla de auditoría del mapeo autorizado, que sirva como referencia para revisiones periódicas de acceso:

```sql
CREATE TABLE user_nas_privilege_map (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64) NOT NULL,
    nas_ip          VARCHAR(15) NOT NULL,
    nas_identifier  VARCHAR(64),
    nas_vendor      VARCHAR(32),
    radius_group    VARCHAR(64) NOT NULL,
    privilege_level VARCHAR(32) NOT NULL,
    justification   TEXT,
    approved_by     VARCHAR(64) NOT NULL,
    approved_date   DATETIME NOT NULL,
    review_date     DATETIME NOT NULL,       -- Fecha de revisión periódica
    is_active       TINYINT(1) DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_nas (username, nas_ip),
    INDEX idx_review_date (review_date)
) ENGINE=InnoDB
  COMMENT='Mapeo autorizado de usuario-NAS-privilegio para control A.5.18';
```

### 7.4 Controles de Segregación de Funciones

| Control | Descripción | Implementación |
|---|---|---|
| **SOD-01** | Separación entre quien define perfiles y quien aprueba el acceso | Workflow de doble aprobación en daloRADIUS o sistema externo |
| **SOD-02** | Administrador de RADIUS no puede asignarse privilegios a sí mismo | Regla de negocio en daloRADIUS; revisión por segundo aprobador |
| **SOD-03** | Revisión periódica de accesos privilegiados (nivel 15 o equivalente) | Auditoría trimestral de `user_nas_privilege_map` |
| **SOD-04** | Separación entre cuentas de administración de RADIUS y cuentas de acceso a equipos | Cuentas distintas; prohibición de uso de cuenta personal para administrar RADIUS |
| **SOD-05** | Acceso de emergencia (break-glass) con auditoría reforzada | Cuenta de emergencia con alertas inmediatas y revisión post-uso |
| **SOD-06** | Prohibición de cuentas compartidas | Cada cuenta en `radcheck` debe tener un único titular identificado |

### 7.5 Proceso de Revisión de Accesos Privilegiados

```
Ciclo de Revisión de Accesos (Control A.5.18):

  [TRIMESTRAL]
       │
       ▼
  Generar reporte de user_nas_privilege_map
       │
       ▼
  Revisor (no-admin RADIUS) valida vigencia de cada mapeo
       │
       ├──► Acceso justificado y vigente ──► Actualizar review_date
       │
       ├──► Acceso sin justificación ──► Solicitar justificación en 5 días hábiles
       │                                    └──► Sin respuesta: revocar acceso
       │
       └──► Acceso ya no requerido ──► Revocar y registrar evento ADMIN-003
```

---

## 8. Protección de Registros y Sincronización de Tiempo (NTP)

### 8.1 Protección de la Integridad de los Registros (Control A.5.33)

#### 8.1.1 Mecanismos de Protección en Base de Datos

**REQ-PROT-01 — Permisos mínimos sobre tablas de log:**

```sql
-- Usuario de aplicación RADIUS: solo INSERT y SELECT sobre tablas de log
GRANT SELECT, INSERT ON radius_db.radacct        TO 'radiusd'@'localhost';
GRANT SELECT, INSERT ON radius_db.radpostauth     TO 'radiusd'@'localhost';
GRANT SELECT, INSERT ON radius_db.radius_reply_audit TO 'radiusd'@'localhost';

-- Prohibir explícitamente UPDATE y DELETE
REVOKE UPDATE, DELETE ON radius_db.radacct        FROM 'radiusd'@'localhost';
REVOKE UPDATE, DELETE ON radius_db.radpostauth    FROM 'radiusd'@'localhost';

-- Usuario de auditoría: solo SELECT
GRANT SELECT ON radius_db.* TO 'audit_reader'@'audit-server';
```

**REQ-PROT-02 — Hash de integridad por registro:**

Cada registro insertado en `radpostauth` y `radacct` debe incluir un hash SHA-256 calculado sobre los campos críticos (username + timestamp + nas_ip + reply + atributos de respuesta). Este hash permite detectar modificaciones posteriores.

```python
import hashlib
import json

def calculate_record_hash(record: dict, fields: list) -> str:
    """Calcula hash SHA-256 de los campos críticos de un registro."""
    canonical = {k: str(record[k]) for k in sorted(fields) if k in record}
    payload = json.dumps(canonical, ensure_ascii=True, sort_keys=True)
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()

# Campos críticos para el hash de autenticación
AUTH_CRITICAL_FIELDS = [
    "username", "authdate", "nas_ip_address",
    "reply", "calling_station_id"
]
```

**REQ-PROT-03 — Replicación a SIEM inmutable:**

Los registros deben ser exportados a un sistema SIEM o repositorio de logs inmutable (write-once) dentro de un máximo de **60 segundos** desde su generación. Una vez en el SIEM, los registros no deben poder ser modificados ni eliminados por ningún rol, incluyendo administradores.

**REQ-PROT-04 — Separación de administración:**

El administrador del servidor RADIUS y el administrador del sistema de logging/SIEM deben ser roles y personas distintas. Ningún administrador de RADIUS debe tener acceso de escritura al repositorio de logs centralizado.

#### 8.1.2 Controles de Acceso a daloRADIUS

| Rol daloRADIUS | Permisos sobre Logs | Permisos sobre Configuración |
|---|---|---|
| `superadmin` | Lectura | Escritura completa (con auditoría) |
| `admin` | Lectura | Escritura sobre usuarios y grupos (sin VSA de alto privilegio) |
| `helpdesk` | Lectura (sin datos sensibles) | Sin permisos |
| `auditor` | Lectura completa | Sin permisos |
| `readonly` | Lectura limitada | Sin permisos |

### 8.2 Sincronización de Tiempo — NTP (Control A.8.17)

La precisión temporal es crítica para la trazabilidad forense. Un drift de tiempo entre el servidor RADIUS y los NAS puede romper la correlación de eventos y comprometer la validez de los registros como evidencia.

#### 8.2.1 Requisitos de Sincronización NTP

| Requisito | Especificación | Justificación |
|---|---|---|
| **NTP-01** | El servidor RADIUS debe sincronizar con un servidor NTP interno Stratum 2 o superior | Garantizar precisión del timestamp UTC en todos los registros |
| **NTP-02** | Todos los NAS deben sincronizar al mismo servidor NTP interno | Eliminar divergencias temporales entre fuentes de log |
| **NTP-03** | El drift de tiempo máximo tolerable es de **±500 ms** entre el servidor RADIUS y cada NAS | Threshold mínimo para correlación SIEM confiable |
| **NTP-04** | Ante una pérdida de sincronización NTP de más de 5 minutos, se debe generar una alerta | Prevenir acumulación de registros con timestamps incorrectos |
| **NTP-05** | Los logs deben almacenarse siempre en **UTC** (no hora local) | Eliminar ambigüedad por cambios de horario de verano |
| **NTP-06** | El servidor NTP interno debe sincronizar con fuentes externas confiables (pool.ntp.org, time.cloudflare.com) | Asegurar trazabilidad desde fuentes de tiempo authoritativas |

#### 8.2.2 Configuración de NTP en FreeRADIUS (Linux)

```bash
# /etc/chrony.conf — Configuración de chrony para el servidor RADIUS
server ntp-interno-01.corp.empresa.com iburst prefer
server ntp-interno-02.corp.empresa.com iburst
pool pool.ntp.org iburst

# Limitar ajustes de tiempo para evitar saltos bruscos
makestep 1.0 3
maxdistance 1.5

# Log de sincronización (para auditoría de NTP)
log tracking measurements statistics
logdir /var/log/chrony

# Permitir ajuste solo desde interfaces de administración
bindcmdaddress 127.0.0.1
```

#### 8.2.3 Verificación de Sincronización NTP

```bash
# Verificar estado de sincronización en el servidor RADIUS
chronyc tracking
chronyc sources -v

# Alerta si el offset supera 500ms (script de monitoreo)
#!/bin/bash
OFFSET=$(chronyc tracking | grep "System time" | awk '{print $4}')
THRESHOLD=0.500
if (( $(echo "$OFFSET > $THRESHOLD" | bc -l) )); then
    logger -t ntp_monitor "ALERT: NTP offset ${OFFSET}s exceeds threshold ${THRESHOLD}s"
    # Enviar alerta a SIEM
fi
```

---

## 9. Recomendaciones de Seguridad y Retención

### 9.1 Política de Retención de Logs

La política de retención debe balancear los requisitos normativos, operacionales y de privacidad:

| Tipo de Log | Retención Mínima | Retención Recomendada | Soporte | Justificación Normativa |
|---|---|---|---|---|
| `radpostauth` (autenticaciones) | 12 meses | 24 meses | Hot/Warm storage | ISO 27001 A.8.15; investigación de incidentes |
| `radacct` (sesiones activas/cerradas) | 12 meses | 24 meses | Hot/Warm storage | Trazabilidad de sesiones; investigaciones forenses |
| `radius_reply_audit` (atributos VSA) | 24 meses | 36 meses | Warm/Cold storage | Evidencia de qué privilegios se otorgaron |
| `user_nas_privilege_map` (mapeo autorizado) | 36 meses | 60 meses | Cold storage | Evidencia de auditoría de derechos de acceso |
| Logs de administración daloRADIUS | 24 meses | 36 meses | Warm storage | Cambios de configuración y política |
| Logs de SIEM correlacionados | 12 meses (hot) | 36 meses (cold) | Escalonado | Capacidad de investigación retrospectiva |

> **Nota:** Los períodos de retención deben revisarse ante requisitos legales locales específicos (e.g., normativas de protección de datos, regulaciones sectoriales financieras o telecomunicaciones) que puedan exigir plazos distintos.

### 9.2 Recomendaciones de Seguridad Operativa

#### 9.2.1 Hardening del Servidor RADIUS

| ID | Recomendación | Prioridad |
|---|---|---|
| **SEC-01** | Deshabilitar PAP como método de autenticación; usar CHAP, MS-CHAPv2 o EAP-TLS | CRÍTICA |
| **SEC-02** | Implementar secretos compartidos RADIUS de mínimo 32 caracteres aleatorios por NAS | CRÍTICA |
| **SEC-03** | Rotar secretos compartidos de NAS con frecuencia mínima anual o ante cambio de personal con acceso | ALTA |
| **SEC-04** | Restringir el acceso al puerto UDP 1812/1813 mediante firewall solo a IPs de NAS autorizados | CRÍTICA |
| **SEC-05** | Implementar rate limiting de Access-Request por NAS y por username para mitigar ataques de fuerza bruta | ALTA |
| **SEC-06** | Habilitar TLS (RadSec — RFC 6614) para el transporte de paquetes RADIUS donde sea posible | ALTA |
| **SEC-07** | Configurar bloqueo temporal de cuentas tras N intentos fallidos consecutivos (máximo 5) | ALTA |
| **SEC-08** | Implementar lista de control de NAS (whitelist de `clients.conf`) con revisión semestral | ALTA |
| **SEC-09** | Separar el servidor RADIUS en una VLAN de gestión dedicada sin acceso directo desde redes de usuarios | ALTA |
| **SEC-10** | Aplicar cifrado en reposo para la base de datos de daloRADIUS (TDE o cifrado de volumen) | ALTA |

#### 9.2.2 Alertas y Umbrales de Monitoreo

| Condición de Alerta | Umbral | Severidad | Acción |
|---|---|---|---|
| Intentos fallidos de autenticación por usuario | > 5 en 10 minutos | ALTA | Bloqueo temporal + alerta SIEM |
| Intentos fallidos desde una misma IP (NAS desconocido) | > 3 en 5 minutos | CRÍTICA | Bloqueo IP + alerta inmediata |
| Acceso otorgado con atributo de nivel 15 (o equivalente) | Siempre | ALTA | Registro + notificación a equipo de seguridad |
| Sesión de acceso superior a la duración máxima definida | > `Session-Timeout` + 10% | MEDIA | Alerta + verificación |
| Sesión sin Accounting-Stop tras fin esperado | > 15 minutos post-timeout | ALTA | Alerta + investigación |
| Pérdida de sincronización NTP | Offset > 500ms | ALTA | Alerta + corrección inmediata |
| Modificación de tablas `radreply`/`radgroupreply` | Cualquier cambio | ALTA | Alerta + revisión por segundo par |
| Acceso a daloRADIUS fuera del horario laboral | Horario no autorizado | ALTA | Alerta inmediata |

#### 9.2.3 Pruebas Periódicas de Integridad

| Prueba | Frecuencia | Responsable |
|---|---|---|
| Validación de hashes de integridad en registros de log | Mensual | Equipo de Seguridad |
| Prueba de autenticación controlada por NAS para validar VSA | Tras cada cambio + mensual | Administrador RADIUS |
| Revisión de accesos privilegiados activos | Trimestral | Auditoría Interna |
| Revisión de NAS autorizados vs. activos | Semestral | Administrador RADIUS |
| Prueba de recuperación desde repositorio de logs | Anual | Equipo de Seguridad |
| Simulación de escenario de acceso no autorizado (red team) | Anual | Equipo de Seguridad |

### 9.3 Consideraciones de Privacidad y Datos Personales (Control A.5.34)

Los logs de RADIUS contienen datos personales (username, IP de origen, timestamps de actividad). Se deben aplicar las siguientes medidas:

- **Pseudonimización en largo plazo:** Para logs con retención superior a 24 meses que se muevan a cold storage, considerar la sustitución del username por un hash unidireccional (conservando la clave de reversión en bóveda segura).
- **Control de acceso granular:** El acceso a `calling_station_id` e información de sesión debe estar restringido a roles con necesidad operacional justificada.
- **Inventario de datos personales:** Los campos `username`, `calling_station_id` y `framed_ip_address` deben estar documentados en el registro de actividades de tratamiento (RoPA) de la organización.
- **Minimización de datos:** No registrar campos que no aporten valor de auditoría (e.g., contraseñas en cualquier forma).

---

## 10. Glosario

| Término | Definición |
|---|---|
| **AAA** | Authentication, Authorization, Accounting — Marco de control de acceso tripartito |
| **CHAP** | Challenge Handshake Authentication Protocol — Protocolo de autenticación por desafío |
| **daloRADIUS** | Interfaz web de gestión para servidores FreeRADIUS |
| **EAP-TLS** | Extensible Authentication Protocol — Transport Layer Security; método de autenticación por certificado |
| **FreeRADIUS** | Implementación open-source del servidor RADIUS más utilizada en entornos empresariales |
| **NAS** | Network Access Server — Equipo de red que actúa como cliente RADIUS |
| **NTP** | Network Time Protocol — Protocolo de sincronización de tiempo en red |
| **PAP** | Password Authentication Protocol — Protocolo inseguro de autenticación en texto plano |
| **PEN** | Private Enterprise Number — Número asignado por IANA a fabricantes para identificar VSA |
| **RADIUS** | Remote Authentication Dial-In User Service — Protocolo AAA (RFC 2865) |
| **RadSec** | RADIUS sobre TLS/DTLS — Extensión segura del protocolo RADIUS (RFC 6614) |
| **RoPA** | Record of Processing Activities — Registro de actividades de tratamiento de datos personales |
| **SIEM** | Security Information and Event Management — Sistema de correlación y análisis de eventos de seguridad |
| **Stratum** | Nivel de precisión en la jerarquía NTP (Stratum 0 = reloj atómico; Stratum 1 = servidor conectado a él) |
| **TDE** | Transparent Data Encryption — Cifrado transparente de base de datos |
| **VSA** | Vendor-Specific Attributes — Atributos RADIUS extendidos específicos de cada fabricante (RFC 2865, §5.26) |

---

## 11. Referencias Normativas

| Referencia | Descripción |
|---|---|
| **ISO/IEC 27001:2022** | Sistemas de Gestión de Seguridad de la Información — Requisitos |
| **ISO/IEC 27002:2022** | Controles de Seguridad de la Información — Código de Prácticas |
| **RFC 2865** | Remote Authentication Dial In User Service (RADIUS) |
| **RFC 2866** | RADIUS Accounting |
| **RFC 2868** | RADIUS Attributes for Tunnel Protocol Support |
| **RFC 2869** | RADIUS Extensions |
| **RFC 3579** | RADIUS Support for EAP |
| **RFC 5176** | Dynamic Authorization Extensions to RADIUS |
| **RFC 6614** | Transport Layer Security (TLS) Encryption for RADIUS (RadSec) |
| **RFC 8907** | TACACS+ Protocol — Alternativa complementaria para administración de dispositivos |
| **NIST SP 800-92** | Guide to Computer Security Log Management |
| **CIS Controls v8 — Control 8** | Audit Log Management |
| **Cisco IOS Security Guide** | AAA Configuration Reference |
| **Juniper Junos RADIUS Guide** | Access Control and Authentication |

---

*Fin del Documento*

---

> **Control de Versiones**
>
> | Versión | Fecha | Autor | Descripción del Cambio |
> |---|---|---|---|
> | 1.0 | 2026 | Zero-co | Versión inicial del documento |
>
> **Aprobaciones Requeridas:** CISO — Responsable de Arquitectura de Red — Auditoría Interna

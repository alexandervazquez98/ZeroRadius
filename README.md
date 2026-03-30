# FreeRADIUS Management System

Este sistema es una solución completa para la gestión y administración de un servidor AAA (Authentication, Authorization, Accounting) basado en **FreeRADIUS**. Proporciona una interfaz web moderna para gestionar usuarios, grupos, dispositivos NAS y auditoría, abstrayendo la complejidad de la base de datos SQL subyacente.

## 🏗 Arquitectura

El sistema está contenerizado con Docker y compuesto por:

1.  **Frontend (React + Vite)**:
    *   Interfaz de usuario para administradores.
    *   Gestiona usuarios, NAS, sesiones activas y logs.
    *   Se comunica con el Backend vía API REST.

2.  **Backend (FastAPI)**:
    *   API RESTful escrita en Python.
    *   Gestiona la lógica de negocio y la conexión segura a la base de datos.
    *   Implementa la lógica de auditoría personalizada (`app_audit_log`).
    *   Expone endpoints para CRUD de tablas RADIUS (`radcheck`, `radreply`, `nas`, `radacct`).

3.  **RADIUS Server (FreeRADIUS)**:
    *   Servidor estándar FreeRADIUS (v3.2.3).
    *   Configurado para leer autenticación y configuración directamente de SQL.
    *   Sin archivos de texto complejos; toda la lógica reside en la BD.

4.  **Database (MariaDB)**:
    *   Almacena el esquema estándar de FreeRADIUS + tablas de la aplicación.

## Flujos Principales

### Autenticación de Usuarios
*   El NAS envía la petición al contenedor FreeRADIUS.
*   FreeRADIUS consulta las tablas `radcheck` y `radgroupcheck` en MariaDB.
*   Si la validación pasa, consulta `radreply` y `radgroupreply` para obtener los atributos de configuración (Velocidad, VLAN, Tiempo).
*   FreeRADIUS responde al NAS con `Access-Accept` + Atributos.

### Mapa de Privilegios (Privilege Map) - ISO 27001
El sistema implementa un control de acceso estricto basado en identidad de red (NAS) para cumplir con los controles **A.5.15 y A.8.3 de la ISO/IEC 27001:2022**.
En lugar de conceder acceso global a todos los equipos de red, el Privilege Map restringe el acceso de manera granular:
*   **Propósito:** Define exactamente qué usuario puede acceder a qué equipo (NAS IP), y con qué grupo/nivel de privilegios (RADIUS Group).
*   **Autorización Dinámica:** Durante el login, la política `nas_based_authorization` en FreeRADIUS consulta la tabla `user_nas_privilege_map`. Si existe un mapeo activo para el usuario y la IP del NAS desde donde intenta entrar, su grupo RADIUS predeterminado se reemplaza dinámicamente por el grupo autorizado para ese equipo. Si no hay mapeo, el acceso se rechaza.
*   **Auditoría y Revisión (A.8.2):** Cada mapeo requiere un aprobador (`Approved By`), una justificación de negocio (`Justification`) y una fecha de revisión obligatoria (`Review Date`), garantizando que los accesos privilegiados sean revocados cuando ya no se necesiten.

### Gestión de "Huntgroups" (Lógica Multi-NAS)
*   Se utiliza la flexibilidad de SQL para asignar usuarios a grupos específicos según el NAS.
*   En el Frontend, se pueden crear condiciones para que un grupo solo sea válido si la petición viene de una IP de NAS específica (Atributo `NAS-IP-Address` en `radgroupcheck`).

### Control de Acceso de Red IAM/RBAC (N-Dimensional)
El sistema incluye un motor avanzado de políticas IAM que aprovisiona atributos para múltiples dispositivos simultáneamente:
*   **Múltiples Hardware Zones**: Permite aplicar atributos de aprovisionamiento (QoS, VLAN, VRF) según marcas y perfiles utilizando las sentencias nativas de FreeRADIUS.
*   **Workflow "Break-Glass" (JIT)**: Soporte de elevación de privilegios Just-In-Time para soporte especializado. Inyecta el atributo `Expiration` calculando el TTL solicitado, permitiendo operar como superusuario de red solo durante el período de ventana de mantenimiento o resolución de incidentes aprobado.
*   **Building de Macros Visuales**: Editor dinámico para construir directivas RADIUS sin programar diccionarios SQL, validando la semántica contra `pyrad` y compilando el resultado optimizado en la tabla `radgroupreply`.

## 🛠 Despliegue

```bash
# Iniciar todo el stack
docker-compose up -d --build
```

*   **Frontend**: http://localhost:3000
*   **Backend Docs**: http://localhost:8000/docs

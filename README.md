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

## 🚀 Flujos Principales

### Autenticación de Usuarios
*   El NAS envía la petición al contenedor FreeRADIUS.
*   FreeRADIUS consulta las tablas `radcheck` y `radgroupcheck` en MariaDB.
*   Si la validación pasa, consulta `radreply` y `radgroupreply` para obtener los atributos de configuración (Velocidad, VLAN, Tiempo).
*   FreeRADIUS responde al NAS con `Access-Accept` + Atributos.

### Gestión de "Huntgroups" (Lógica Multi-NAS)
*   Se utiliza la flexibilidad de SQL para asignar usuarios a grupos específicos según el NAS.
*   En el Frontend, se pueden crear condiciones para que un grupo solo sea válido si la petición viene de una IP de NAS específica (Atributo `NAS-IP-Address` en `radgroupcheck`).

## 🛠 Despliegue

```bash
# Iniciar todo el stack
docker-compose up -d --build
```

*   **Frontend**: http://localhost:3000
*   **Backend Docs**: http://localhost:8000/docs

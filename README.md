# ZeroRadius 🌐

ZeroRadius is a modern, full-stack, state-driven management interface for the **FreeRADIUS** AAA Server. Built to abstract the severe complexities, flat-file hell, and UX pitfalls of traditional legacy managers (like daloRADIUS), it offers a React-driven frontend and an asynchronous Python/FastAPI backend designed for enterprise networks and ISPs.

![ZeroRadius Version](https://img.shields.io/badge/version-1.2.0-blue)
![Architecture](https://img.shields.io/badge/infrastructure-Docker_Compose-blueviolet)

## 🚀 Why ZeroRadius over daloRADIUS?

Historically, operating daloRADIUS meant fighting with raw SQL schemas, clunky 2000s PHP interfaces, and manual dictionary editing to provision modern devices. **ZeroRadius changes the paradigm:**
- **Visual Macro Builders:** Drag and drop RADIUS attributes instead of manually typing `radgroupreply` statements. Syntax constraints are strictly validated by `pyrad`.
- **Zero-Trust Identity Mapping:** Granular, NAS-based privilege scopes (ISO 27001 compliant) instead of granting global network access for every administrator.
- **RESTful Asynchronous Backend:** Built entirely on modern FastAPI + SQLAlchemy 2.0 Async, enabling massive high-concurrency without breaking a sweat.

## 🏗 Architecture & Stack 

ZeroRadius is fully containerized and consists of four main pillars:

1. **Frontend (React + Vite + TailwindCSS)**:
   - Consumer-grade UI/UX for network administrators.
   - Manages Users, Accounts, NAS Devices, Active Sessions, Audit Logs, and **NAS Categories**.
   - **Real-time RADIUS Log Viewer** accessible from the header for live Access-Request monitoring.
   - **Privilege Map** with category-based targeting for ISO 27001 compliance.
   - Communicates with the Backend via REST APIs and WebSockets.

2. **Backend (FastAPI)**:
   - High-throughput REST API written in Python.
   - Manages business logic and direct connection to the AAA MariaDB.
   - **WebSocket log streaming** endpoint for real-time FreeRADIUS log monitoring via Docker SDK.
   - Executes custom localized Audit Trails (`app_audit_log`).

3. **RADIUS AAA Server (FreeRADIUS v3.2.3)**:
   - Standard FreeRADIUS configured for 100% SQL-driven operation. No local `users` or text-based configurations. All network policies reside dynamically inside MariaDB.

4. **Database (MariaDB)**:
   - Stores the standard FreeRADIUS schemas extended with ZeroRadius custom identity management tables.

### Advanced: Anti-Proxy Strategy for Major NAS

**El Problema:**
Cuando un NAS Mayor (por ejemplo, un Access Point o un Switch) hace de proxy RADIUS para los dispositivos conectados detrás de él (como SMs o Modems), envía las peticiones de autenticación utilizando su propia IP (`NAS-IP-Address`). Si otorgamos permisos genéricos de `Admin` basados únicamente en esa IP, involuntariamente estaríamos dándole permisos de `Admin` a todos los dispositivos detrás de él, ya que heredarían la regla genérica.

**La Solución: Priority Engine de ZeroRadius**
Para aislar el acceso al NAS Mayor del acceso a los dispositivos proxificados sin tener que cargar la MAC de miles de equipos en la base de datos, utilizamos el sistema de prioridades de ZeroRadius:

- Al loguearse directamente al NAS Mayor, este generalmente no envía su MAC (`Calling-Station-Id`). En FreeRADIUS, podemos inyectar una MAC ficticia (ej. `00:00:00:00:00:00`) para estas peticiones directas.
- Al loguearse a un dispositivo proxificado (ej. SM), el NAS sí reenvía la MAC real del dispositivo.

Aprovechando este comportamiento, creamos el siguiente flujo:
- **Regla 1 (Direct NAS Access - Prioridad 0):** Se crea una política muy específica (Target: `mac_plus_ip`) que asocia la IP del NAS Mayor + la MAC ficticia (`00:00:00:00:00:00`). A esta regla le otorgamos el perfil de `Admin`.
- **Regla 2 (Proxied Devices - Prioridad 2):** Se crea una política genérica o de fallback (Target: `nas_ip`) asociando solo la IP del NAS Mayor (dejando la MAC vacía). A esta regla le otorgamos un perfil restrictivo como `ReadOnly` o derechamente acceso denegado.

De esta manera, logramos aislamiento seguro y genérico sin esfuerzo administrativo adicional.

## 📚 Official Documentation & User Manuals
The project relies on localized, flowchart-driven Markdown manuals to ensure network administrators can confidently provision networks.

- [**01. NAS Provisioning & Huntgroups**](docs/01-nas-provisioning.md) - How to onboard hardware, segment network devices, and categorize NAS devices by type/location using **NAS Categories**.
- [**02. ISO 27001 Privilege Map & RBAC**](docs/02-iso27001-privilege-map.md) - Deep dive into ZeroRadius's Identity Access Management (IAM), explaining how general authentication tokens are converted into restricted, hardware-specific group roles dynamically during login. **Now supports category-based targeting**.
- [**03. JIT "Break-Glass" Workflow**](docs/03-jit-break-glass.md) - Understanding Just-In-Time role elevation logic. How operators request timed root-access and how the `Expiration` attribute is injected into the AAA workflow.
- [**04. Live RADIUS Log Viewer**](docs/04-live-log-viewer.md) - Real-time monitoring of Access-Request events (Accept/Reject) via WebSocket streaming from the FreeRADIUS container.
- [**05. NAS Categories Management**](docs/05-nas-categories.md) - Managing NAS device categories for streamlined provisioning and bulk operations.

## 🛠 Deployment & Setup

Deploying the stack is native and self-contained via Docker.

```bash
# Clone the repository
git clone https://github.com/alexandervazquez98/ZeroRadius.git
cd ZeroRadius

# Initialize the stack
docker-compose up -d --build
```

- **Frontend Application**: [http://localhost:3000](http://localhost:3000)
- **Backend Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

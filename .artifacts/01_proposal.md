# Proposal: iso27001-compliance-improvements
**Change**: ISO/IEC 27001:2022 Compliance Improvements  
**Project**: RADIUS-gestor  
**Date**: 2026-03-14  
**Status**: Approved  

---

## Intent

RADIUS-gestor actúa como GUI de gestión para FreeRADIUS en un entorno multimarca. Una auditoría contra ISO/IEC 27001:2022 identificó **18 brechas de cumplimiento**, de las cuales 6 son CRÍTICAS (riesgo inmediato):

1. Contraseñas PAP almacenadas en texto claro en `radpostauth` (A.5.17)
2. Timestamps de auditoría mutables via `ON UPDATE CURRENT_TIMESTAMP` (A.5.33)
3. Sin hashes de integridad SHA-256 en registros de log (A.5.33)
4. Sin lockout de cuentas — fuerza bruta ilimitada posible (A.8.16)
5. Tablas `radius_reply_audit` y `user_nas_privilege_map` inexistentes (A.5.18, A.8.2)
6. Sin sistema de roles — todos los admins tienen acceso total (SOD-01..06)

## Scope

### Incluido
- **Fase 1 — BD & RADIUS**: Migraciones Alembic, corrección de postauth_query, nuevas tablas
- **Fase 2 — Backend**: RBAC, hash SHA-256, lockout, SIEM export, guardas VSA, event codes
- **Fase 3 — Frontend + FreeRADIUS**: UI mejorada, página privilege map, política unlang NTP

### Excluido
- Integración con SIEM externo (solo export de datos)
- Migración de datos históricos en radpostauth/radacct
- Implementación de RadSec (TLS para RADIUS transport)
- Integración LDAP/Active Directory

## Approach

Iniciativa de cumplimiento en 3 fases secuenciales. Fase 1 es prerequisito de Fase 2 (nuevas columnas BD). Fase 3 puede desarrollarse en paralelo con Fase 2 una vez la BD esté migrada.

| Fase | Foco | Esfuerzo | Prerequisito |
|------|------|----------|--------------|
| 1 — DB & RADIUS | Schema + FreeRADIUS SQL | 2-3 días | Ninguno |
| 2 — Backend | FastAPI security layer | 5-7 días | Fase 1 |
| 3 — Frontend + Policy | React UI + unlang | 3-5 días | Fase 1 |

**Archivos afectados**: 25 total (8 nuevos, 17 modificados)

## Risk Assessment

| Riesgo | Mitigación |
|--------|-----------|
| Migración BD rompe FreeRADIUS queries | Nuevas columnas con DEFAULT, FreeRADIUS sigue funcionando hasta actualizar radius/sql |
| Política unlang rechaza autenticaciones legítimas | Desplegar en modo warn antes de enforce |
| Rol migration bloquea admins | Primer usuario migrado = superadmin por defecto |
| SHA-256 añade latencia | Cálculo asíncrono post-insert, no en el path crítico |

## Success Criteria

- [ ] 0 contraseñas en texto claro en radpostauth
- [ ] 100% de registros en radpostauth tienen integrity_hash válido
- [ ] Login bloqueado tras 5 intentos fallidos
- [ ] Roles diferenciados: superadmin, admin, helpdesk, auditor, readonly funcionando
- [ ] SIEM export endpoint retorna formato JSON estándar
- [ ] Tabla user_nas_privilege_map poblada y accesible desde UI
- [ ] FreeRADIUS unlang policy activa para NAS-conditional auth
- [ ] 0 errores LSP preexistentes en archivos modificados

## Dependencies

- Alembic configurado (ya presente)
- MariaDB 10.11 (ya presente)
- FreeRADIUS con módulo sql habilitado (ya presente)
- pyrad para parsing de atributos RADIUS (ya presente)

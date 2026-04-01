/**
 * MSW v2 handlers — centralizados para todos los tests del frontend.
 *
 * La API usa axios con baseURL '/api', así que todos los paths
 * arrancan con /api/...
 *
 * Handlers cubiertos:
 *   POST /api/auth/token
 *   GET  /api/users
 *   POST /api/users/check
 *   GET  /api/groups/list
 *   GET  /api/groups/reply
 *   GET  /api/nas
 *   GET  /api/audit/access
 *   GET  /api/privilege-map
 */

import { http, HttpResponse } from 'msw'

// Token JWT falso para simular respuestas de autenticación exitosa
const MOCK_TOKEN = [
  btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' })),
  btoa(JSON.stringify({ sub: 'test_admin', role: 'superadmin', exp: 9999999999 })),
  'fakesignature',
].join('.')

export const handlers = [
  // -------------------------------------------------------------------------
  // Auth
  // -------------------------------------------------------------------------
  http.post('/api/auth/token', () => {
    return HttpResponse.json({
      access_token: MOCK_TOKEN,
      token_type: 'bearer',
    })
  }),

  // -------------------------------------------------------------------------
  // RADIUS Users
  // -------------------------------------------------------------------------
  http.get('/api/users', () => {
    return HttpResponse.json([
      { id: 1, username: 'jperez', attribute: 'Cleartext-Password', op: ':=', value: '***' },
      { id: 2, username: 'mgarcia', attribute: 'Cleartext-Password', op: ':=', value: '***' },
    ])
  }),

  http.post('/api/users/check', async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json(
      { id: 99, ...body },
      { status: 201 }
    )
  }),

  // -------------------------------------------------------------------------
  // Groups
  // -------------------------------------------------------------------------
  http.get('/api/groups/list', () => {
    return HttpResponse.json([
      { username: '', groupname: 'helpdesk_group', priority: 0 },
      { username: '', groupname: 'admin_group', priority: 0 },
    ])
  }),

  http.get('/api/groups/reply', () => {
    return HttpResponse.json([
      { id: 1, groupname: 'helpdesk_group', attribute: 'Service-Type', op: ':=', value: 'NAS-Prompt-User' },
    ])
  }),

  // -------------------------------------------------------------------------
  // NAS
  // -------------------------------------------------------------------------
  http.get('/api/nas', () => {
    return HttpResponse.json([
      { id: 1, nasname: '10.0.0.1', shortname: 'router-core', secret: '***', type: 'cisco', category_id: 1, category_name: 'AP_CAMBIUM' },
      { id: 2, nasname: '10.0.0.2', shortname: 'switch-access', secret: '***', type: 'other', category_id: null, category_name: null },
    ])
  }),

  // -------------------------------------------------------------------------
  // NAS Categories
  // -------------------------------------------------------------------------
  http.get('/api/nas-categories', () => {
    return HttpResponse.json([
      { id: 1, name: 'AP_CAMBIUM', criticality: 'critical', vendor: 'Cambium', description: 'Access Points Cambium 450i' },
      { id: 2, name: 'SM_CAMBIUM', criticality: 'standard', vendor: 'Cambium', description: 'Subscriber Modules Cambium 450i' },
    ])
  }),

  http.post('/api/nas-categories', async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json({ id: 99, ...body }, { status: 201 })
  }),

  http.delete('/api/nas-categories/:id', () => {
    return HttpResponse.json({ ok: true })
  }),

  // -------------------------------------------------------------------------
  // Audit
  // -------------------------------------------------------------------------
  http.get('/api/audit/access', () => {
    return HttpResponse.json([
      {
        id: 1,
        admin_user: 'test_admin',
        action: 'Login',
        table_affected: 'admin_users',
        timestamp: '2025-01-01T12:00:00Z',
        target_user: 'test_admin',
      },
    ])
  }),

  // -------------------------------------------------------------------------
  // Dictionary attributes (used by PoliciesPage)
  // -------------------------------------------------------------------------
  http.get('/api/dictionary/attributes', () => {
    return HttpResponse.json([
      { name: 'Service-Type', code: 6, type: 'integer', vendor: null, dictionary: 'radius' },
      { name: 'Idle-Timeout', code: 28, type: 'integer', vendor: null, dictionary: 'radius' },
    ])
  }),

  http.get('/api/groups/check', () => {
    return HttpResponse.json([])
  }),

  // -------------------------------------------------------------------------
  // Privilege Map
  // -------------------------------------------------------------------------
  http.get('/api/privilege-map', () => {
    return HttpResponse.json([
      {
        id: 1,
        username: 'jperez',
        nas_ip: '10.0.0.1',
        radius_group: 'admin_group',
        privilege_level: 'level-15',
        approved_by: 'superadmin',
        review_date: '2027-01-01',
        is_active: 1,
      },
    ])
  }),

  // -------------------------------------------------------------------------
  // Dictionary — built-in vendor dicts (read-only view)
  // -------------------------------------------------------------------------
  http.get('/api/dictionary/builtin', () => {
    return HttpResponse.json([
      { filename: 'dictionary.cisco',     vendor: 'cisco' },
      { filename: 'dictionary.microsoft', vendor: 'microsoft' },
      { filename: 'dictionary.mikrotik',  vendor: 'mikrotik' },
    ])
  }),

  http.get('/api/dictionary/builtin/:filename', ({ params }) => {
    return HttpResponse.json({
      filename: params.filename,
      content: `# Mock built-in dictionary: ${params.filename}\nATTRIBUTE\tTest-Attr\t1\tstring\n`,
      builtin: true,
    })
  }),
]

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

  http.post('/api/nas', async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json({ id: 99, ...body }, { status: 201 })
  }),

  http.delete('/api/nas/:id', () => {
    return HttpResponse.json({ ok: true })
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
  // Network Segments
  // -------------------------------------------------------------------------
  http.get('/api/network-segments', () => {
    return HttpResponse.json([
      { id: 1, name: 'Core Network', cidr: '10.0.0.0/8', description: 'Main core network block' },
      { id: 2, name: 'Branch Offices', cidr: '172.16.0.0/16', description: 'Branch networks' },
    ])
  }),

  http.post('/api/network-segments', async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json({ id: 99, ...body }, { status: 201 })
  }),

  http.put('/api/network-segments/:id', async ({ request, params }) => {
    const body = await request.json()
    return HttpResponse.json({ id: parseInt(params.id), ...body }, { status: 200 })
  }),

  http.delete('/api/network-segments/:id', () => {
    return HttpResponse.json({ ok: true })
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
        nas_category_id: null,
        nas_category_name: null,
        radius_group: 'admin_group',
        privilege_level: 'level-15',
        approved_by: 'superadmin',
        review_date: '2027-01-01',
        is_active: 1,
      },
      {
        id: 2,
        username: 'mgarcia',
        nas_ip: null,
        nas_category_id: 1,
        nas_category_name: 'AP_CAMBIUM',
        radius_group: 'helpdesk_group',
        privilege_level: 'level-5',
        approved_by: 'superadmin',
        review_date: '2028-01-01',
        is_active: 1,
      },
    ])
  }),

  http.post('/api/privilege-map', async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json({ ok: true, count: body.nas_ips ? body.nas_ips.length : 1 }, { status: 201 })
  }),

  http.post('/api/privilege-map/category', async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json({ id: 99, ...body }, { status: 201 })
  }),

  http.delete('/api/privilege-map/:id', () => {
    return HttpResponse.json({ ok: true })
  }),

  // -------------------------------------------------------------------------
  // CIR Manager
  // -------------------------------------------------------------------------
  http.get('/api/cir/profiles', () => {
    return HttpResponse.json([])
  }),

  http.post('/api/cir/profiles', async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json({ ...body, groupname: `cir_${String(body.name || '').toLowerCase()}` }, { status: 201 })
  }),

  http.put('/api/cir/profiles/:name', async ({ request, params }) => {
    const body = await request.json()
    return HttpResponse.json({ ...body, groupname: `cir_${params.name}` })
  }),

  http.delete('/api/cir/profiles/:name', () => {
    return HttpResponse.json({ ok: true })
  }),

  http.get('/api/cir/assignments', () => {
    return HttpResponse.json([])
  }),

  http.post('/api/cir/assignments', async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json({ id: 200, ...body }, { status: 201 })
  }),

  http.put('/api/cir/assignments/:id', async ({ request, params }) => {
    const body = await request.json()
    return HttpResponse.json({ id: Number(params.id), ...body })
  }),

  http.delete('/api/cir/assignments/:id', () => {
    return HttpResponse.json({ ok: true })
  }),

  http.post('/api/cir/preview', async ({ request }) => {
    const body = await request.json()
    if (body.username === 'missing') {
      return HttpResponse.json({
        resolution_path: 'none',
        mapping: null,
        profile: null,
        trace: [
          { step: 'exact_or_range', matched: false },
          { step: 'segment', matched: false },
          { step: 'category', matched: false },
        ],
      })
    }

    return HttpResponse.json({
      resolution_path: 'exact',
      mapping: { username: body.username, nas_ip: body.nas_ip, radius_group: 'cir_gold' },
      profile: {
        name: 'gold',
        groupname: 'cir_gold',
        downlink_high: '12000000',
        uplink_high: '6000000',
        downlink_low: '4000000',
        uplink_low: '2000000',
      },
      trace: [
        { step: 'exact_or_range', matched: true },
        { step: 'segment', matched: false },
        { step: 'category', matched: false },
      ],
    })
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

import React, { useMemo, useState } from 'react'

const EMPTY_FORM = {
  username: '',
  targetType: 'nas_ip',
  nas_ip: '',
  calling_station_id: '',
  segment_id: '',
  nas_category_id: '',
  target_start_ip: '',
  target_end_ip: '',
  radius_group: '',
}

function renderTarget(row) {
  if (row.calling_station_id && row.nas_ip) return `MAC: ${row.calling_station_id} @ NAS: ${row.nas_ip}`
  if (row.calling_station_id) return `MAC: ${row.calling_station_id}`
  if (row.nas_ip) return `NAS IP: ${row.nas_ip}`
  if (row.segment_id && row.target_start_ip && row.target_end_ip) {
    return `Segment Exception: ${row.target_start_ip}-${row.target_end_ip}`
  }
  if (row.segment_id) return `Segment: ${row.segment_name || row.segment_id}`
  if (row.nas_category_id) return `Category: ${row.nas_category_name || row.nas_category_id}`
  return 'Unknown'
}

function sameTarget(existing, draft) {
  if (draft.targetType === 'mac_plus_ip') return existing.calling_station_id === draft.calling_station_id && existing.nas_ip === draft.nas_ip
  if (draft.targetType === 'mac') return existing.calling_station_id === draft.calling_station_id && !existing.nas_ip
  if (draft.targetType === 'nas_ip') return existing.nas_ip === draft.nas_ip && !existing.calling_station_id
  if (draft.targetType === 'segment') {
    return String(existing.segment_id || '') === String(draft.segment_id || '') && !existing.target_start_ip
  }
  if (draft.targetType === 'range') {
    return (
      String(existing.segment_id || '') === String(draft.segment_id || '')
      && existing.target_start_ip === draft.target_start_ip
      && existing.target_end_ip === draft.target_end_ip
    )
  }
  if (draft.targetType === 'category') {
    return String(existing.nas_category_id || '') === String(draft.nas_category_id || '')
  }
  return false
}

export default function CIRAssignmentTable({
  assignments,
  profiles,
  segments,
  categories,
  canWrite,
  onSave,
}) {
  const [form, setForm] = useState(EMPTY_FORM)

  const byUser = useMemo(() => {
    return assignments.reduce((acc, row) => {
      if (!acc[row.username]) acc[row.username] = []
      acc[row.username].push(row)
      return acc
    }, {})
  }, [assignments])

  const submit = (event) => {
    event.preventDefault()
    if (!canWrite) return

    const payload = {
      username: form.username,
      radius_group: form.radius_group,
      is_active: 1,
      approved_by: 'cir-ui',
    }

    if (form.targetType === 'mac_plus_ip') {
      payload.calling_station_id = form.calling_station_id
      payload.nas_ip = form.nas_ip
    }
    if (form.targetType === 'mac') payload.calling_station_id = form.calling_station_id
    if (form.targetType === 'nas_ip') payload.nas_ip = form.nas_ip
    if (form.targetType === 'segment') payload.segment_id = Number(form.segment_id)
    if (form.targetType === 'range') {
      payload.segment_id = Number(form.segment_id)
      payload.target_start_ip = form.target_start_ip
      payload.target_end_ip = form.target_end_ip || form.target_start_ip
    }
    if (form.targetType === 'category') payload.nas_category_id = Number(form.nas_category_id)

    const existing = assignments.find((row) => row.username === form.username && sameTarget(row, form))
    if (existing) {
      const ok = window.confirm('This target already exists. Replace winner for this target key?')
      if (!ok) return
    }

    onSave(payload)
    setForm((prev) => ({ ...EMPTY_FORM, targetType: prev.targetType }))
  }

  return (
    <section className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
      <h3 className="text-lg font-black text-slate-800">Assignments</h3>

      {canWrite && (
        <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <label className="text-sm font-bold text-slate-700">
            Assign Username
            <input
              aria-label="Assign Username"
              className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
              value={form.username}
              onChange={(e) => setForm((prev) => ({ ...prev, username: e.target.value }))}
              required
            />
          </label>

          <label className="text-sm font-bold text-slate-700">
            Target Type
            <select
              aria-label="Target Type"
              className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
              value={form.targetType}
              onChange={(e) => setForm((prev) => ({ ...prev, targetType: e.target.value }))}
            >
              <option value="mac_plus_ip">MAC + NAS IP</option>
              <option value="mac">Global MAC</option>
              <option value="nas_ip">Legacy IP</option>
              <option value="segment">Segment</option>
              <option value="range">Range Exception</option>
              <option value="category">Category</option>
            </select>
          </label>

          <label className="text-sm font-bold text-slate-700">
            CIR Profile
            <select
              aria-label="CIR Profile"
              className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
              value={form.radius_group}
              onChange={(e) => setForm((prev) => ({ ...prev, radius_group: e.target.value }))}
              required
            >
              <option value="">-- select profile --</option>
              {profiles.map((profile) => (
                <option key={profile.groupname} value={profile.groupname}>
                  {profile.name}
                </option>
              ))}
            </select>
          </label>

          {(form.targetType === 'mac' || form.targetType === 'mac_plus_ip') && (
            <label className="text-sm font-bold text-slate-700">
              Target MAC
              <input
                aria-label="Target MAC"
                placeholder="0A:00:3E... or 0011.22..."
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
                value={form.calling_station_id}
                onChange={(e) => setForm((prev) => ({ ...prev, calling_station_id: e.target.value }))}
                onBlur={(e) => {
                  const clean = e.target.value.replace(/[:.-]/g, '').toLowerCase();
                  if (clean.length === 12) setForm((prev) => ({ ...prev, calling_station_id: clean }));
                }}
                required
              />
            </label>
          )}

          {(form.targetType === 'nas_ip' || form.targetType === 'mac_plus_ip') && (
            <label className="text-sm font-bold text-slate-700">
              Target NAS IP
              <input
                aria-label="Target NAS IP"
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
                value={form.nas_ip}
                onChange={(e) => setForm((prev) => ({ ...prev, nas_ip: e.target.value }))}
                required
              />
            </label>
          )}

          {form.targetType === 'segment' && (
            <label className="text-sm font-bold text-slate-700">
              Segment
              <select
                aria-label="Segment"
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
                value={form.segment_id}
                onChange={(e) => setForm((prev) => ({ ...prev, segment_id: e.target.value }))}
                required
              >
                <option value="">-- select segment --</option>
                {segments.map((segment) => (
                  <option key={segment.id} value={segment.id}>{segment.name}</option>
                ))}
              </select>
            </label>
          )}

          {form.targetType === 'category' && (
            <label className="text-sm font-bold text-slate-700">
              Category
              <select
                aria-label="Category"
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
                value={form.nas_category_id}
                onChange={(e) => setForm((prev) => ({ ...prev, nas_category_id: e.target.value }))}
                required
              >
                <option value="">-- select category --</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>{category.name}</option>
                ))}
              </select>
            </label>
          )}

          {form.targetType === 'range' && (
            <>
              <label className="text-sm font-bold text-slate-700">
                Segment
                <select
                  aria-label="Range Segment"
                  className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
                  value={form.segment_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, segment_id: e.target.value }))}
                  required
                >
                  <option value="">-- select segment --</option>
                  {segments.map((segment) => (
                    <option key={segment.id} value={segment.id}>{segment.name}</option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-bold text-slate-700">
                Start IP
                <input
                  aria-label="Range Start IP"
                  className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
                  value={form.target_start_ip}
                  onChange={(e) => setForm((prev) => ({ ...prev, target_start_ip: e.target.value }))}
                  required
                />
              </label>
              <label className="text-sm font-bold text-slate-700">
                End IP
                <input
                  aria-label="Range End IP"
                  className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
                  value={form.target_end_ip}
                  onChange={(e) => setForm((prev) => ({ ...prev, target_end_ip: e.target.value }))}
                />
              </label>
            </>
          )}

          <div className="md:col-span-3 flex justify-end">
            <button
              type="submit"
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-black hover:bg-indigo-700"
            >
              Save Assignment
            </button>
          </div>
        </form>
      )}

      <div className="space-y-2">
        {Object.keys(byUser).length === 0 ? (
          <p className="text-sm text-slate-500">No CIR assignments yet.</p>
        ) : (
          Object.entries(byUser).map(([username, rows]) => (
            <div key={username} className="border border-slate-200 rounded-lg p-3">
              <h4 className="font-black text-slate-700 mb-2">{username}</h4>
              <ul className="space-y-1 text-sm text-slate-600">
                {rows.map((row) => (
                  <li key={row.id}>
                    {renderTarget(row)} → <span className="font-bold">{row.radius_group}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))
        )}
      </div>
    </section>
  )
}

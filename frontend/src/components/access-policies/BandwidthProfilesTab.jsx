import React, { useEffect, useMemo, useState } from 'react'

const EMPTY_FORM = {
  name: '',
  downlink_high: '',
  uplink_high: '',
  downlink_low: '',
  uplink_low: '',
}

function isDirty(form, source) {
  return JSON.stringify(form) !== JSON.stringify(source)
}

export default function BandwidthProfilesTab({
  profiles,
  selectedProfile,
  onSelectProfile,
  onSave,
  canWrite,
  fieldErrors = {},
}) {
  const source = useMemo(() => selectedProfile || EMPTY_FORM, [selectedProfile])
  const [form, setForm] = useState(source)
  const [clientErrors, setClientErrors] = useState({})

  useEffect(() => {
    setForm(source)
    setClientErrors({})
  }, [source])

  useEffect(() => {
    const onBeforeUnload = (event) => {
      if (!canWrite) return
      if (!isDirty(form, source)) return
      event.preventDefault()
      event.returnValue = ''
    }

    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [form, source, canWrite])

  const mergedErrors = { ...fieldErrors, ...clientErrors }

  const handleSelect = (profileName) => {
    if (canWrite && isDirty(form, source)) {
      const ok = window.confirm('You have unsaved changes. Continue without saving?')
      if (!ok) return
    }
    const next = profiles.find((p) => p.name === profileName) || null
    onSelectProfile(next)
  }

  const validateClient = () => {
    const next = {}
    if (!form.name?.trim()) next.name = 'Profile Name is required'
    if (!form.downlink_high?.trim()) next.downlink_high = 'Downlink High is required'
    if (!form.uplink_high?.trim()) next.uplink_high = 'Uplink High is required'
    if (!form.downlink_low?.trim()) next.downlink_low = 'Downlink Low is required'
    if (!form.uplink_low?.trim()) next.uplink_low = 'Uplink Low is required'
    setClientErrors(next)
    return Object.keys(next).length === 0
  }

  const submit = (event) => {
    event.preventDefault()
    if (!canWrite) return
    if (!validateClient()) return
    onSave(form)
  }

  return (
    <section className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-lg font-black text-slate-800">Bandwidth Profiles</h3>
        <div>
          <label className="text-xs font-bold text-slate-500 mr-2">Existing profiles</label>
          <select
            aria-label="Existing Profiles"
            className="border border-slate-200 rounded-lg px-2 py-1 text-sm"
            value={selectedProfile?.name || ''}
            onChange={(e) => handleSelect(e.target.value)}
          >
            <option value="">-- New profile --</option>
            {profiles.map((profile) => (
              <option key={profile.groupname} value={profile.name}>
                {profile.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="text-sm font-bold text-slate-700">
          Profile Name
          <input
            aria-label="Profile Name"
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
            value={form.name}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            disabled={!canWrite || Boolean(selectedProfile)}
          />
          {mergedErrors.name && <span className="text-xs text-rose-600">{mergedErrors.name}</span>}
        </label>

        <label className="text-sm font-bold text-slate-700">
          Downlink High
          <input
            aria-label="Downlink High"
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
            value={form.downlink_high}
            onChange={(e) => setForm((prev) => ({ ...prev, downlink_high: e.target.value }))}
            disabled={!canWrite}
          />
          {mergedErrors.downlink_high && <span className="text-xs text-rose-600">{mergedErrors.downlink_high}</span>}
        </label>

        <label className="text-sm font-bold text-slate-700">
          Uplink High
          <input
            aria-label="Uplink High"
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
            value={form.uplink_high}
            onChange={(e) => setForm((prev) => ({ ...prev, uplink_high: e.target.value }))}
            disabled={!canWrite}
          />
          {mergedErrors.uplink_high && <span className="text-xs text-rose-600">{mergedErrors.uplink_high}</span>}
        </label>

        <label className="text-sm font-bold text-slate-700">
          Downlink Low
          <input
            aria-label="Downlink Low"
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
            value={form.downlink_low}
            onChange={(e) => setForm((prev) => ({ ...prev, downlink_low: e.target.value }))}
            disabled={!canWrite}
          />
          {mergedErrors.downlink_low && <span className="text-xs text-rose-600">{mergedErrors.downlink_low}</span>}
        </label>

        <label className="text-sm font-bold text-slate-700">
          Uplink Low
          <input
            aria-label="Uplink Low"
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
            value={form.uplink_low}
            onChange={(e) => setForm((prev) => ({ ...prev, uplink_low: e.target.value }))}
            disabled={!canWrite}
          />
          {mergedErrors.uplink_low && <span className="text-xs text-rose-600">{mergedErrors.uplink_low}</span>}
        </label>

        {canWrite && (
          <div className="md:col-span-2 flex justify-end">
            <button
              type="submit"
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-black hover:bg-indigo-700"
            >
              Save Profile
            </button>
          </div>
        )}
      </form>
    </section>
  )
}

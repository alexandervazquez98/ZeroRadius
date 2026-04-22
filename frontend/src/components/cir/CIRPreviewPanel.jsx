import React, { useState } from 'react'

export default function CIRPreviewPanel({ onPreview, isPending }) {
  const [username, setUsername] = useState('')
  const [nasIp, setNasIp] = useState('')
  const [mac, setMac] = useState('')
  const [result, setResult] = useState(null)

  const submit = async (event) => {
    event.preventDefault()
    const response = await onPreview({
      username,
      nas_ip: nasIp,
      calling_station_id: mac || undefined,
    })
    setResult(response)
  }

  return (
    <section className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
      <h3 className="text-lg font-black text-slate-800">Preview Resolution</h3>

      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
        <label className="text-sm font-bold text-slate-700">
          Preview Username
          <input
            aria-label="Preview Username"
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label className="text-sm font-bold text-slate-700">
          Preview MAC (Optional)
          <input
            aria-label="Preview MAC"
            placeholder="0A-00-3E-..."
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
            value={mac}
            onChange={(e) => setMac(e.target.value)}
          />
        </label>
        <label className="text-sm font-bold text-slate-700">
          Preview NAS IP
          <input
            aria-label="Preview NAS IP"
            className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2"
            value={nasIp}
            onChange={(e) => setNasIp(e.target.value)}
            required
          />
        </label>
        <button
          type="submit"
          className="h-10 px-4 bg-indigo-600 text-white rounded-lg text-sm font-black hover:bg-indigo-700 disabled:opacity-60"
          disabled={isPending}
        >
          Run Preview
        </button>
      </form>

      {result && result.resolution_path !== 'none' && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm">
          <p className="font-bold text-emerald-700">Winning profile: {result.profile?.name}</p>
          {result.mapping && (
            <p className="text-emerald-800">
              Winner target: {result.mapping.calling_station_id || result.mapping.nas_ip || result.mapping.segment_name || result.mapping.nas_category_name || 'resolved'}
            </p>
          )}
          <ul className="mt-2 text-emerald-800 list-disc list-inside">
            {result.trace?.map((item, index) => (
              <li key={`${item.step}-${index}`}>
                {item.step}: {item.matched ? 'matched' : 'not matched'} {item.detail ? `(${item.detail})` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result && result.resolution_path === 'none' && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-bold">No CIR match for this request.</p>
          <p>Runtime policy will fall back to non-CIR behavior.</p>
        </div>
      )}
    </section>
  )
}

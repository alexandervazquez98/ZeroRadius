import React, { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Cpu, Plus, Trash2, Edit2, X, Upload, CheckCircle, AlertTriangle, Search, Download } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import DeviceRegistryService from '../services/deviceRegistry'
import NasCategoriesService from '../services/nasCategoriesService'

const EMPTY_FORM = { mac: '', name: '', category_id: '', nas_ip: '', description: '', is_active: 1 }

export default function DeviceRegistryTab() {
    const { hasRole } = useAuth()
    const { showToast } = useToast()
    const queryClient = useQueryClient()
    const canWrite = hasRole(['superadmin', 'admin'])
    const canDelete = hasRole(['superadmin'])

    const [showModal, setShowModal] = useState(false)
    const [editItem, setEditItem] = useState(null)
    const [form, setForm] = useState(EMPTY_FORM)
    const [deleteTarget, setDeleteTarget] = useState(null)
    const [search, setSearch] = useState('')
    const [filterCategory, setFilterCategory] = useState('')
    const [showBulk, setShowBulk] = useState(false)
    const [bulkText, setBulkText] = useState('')
    const [bulkCategoryId, setBulkCategoryId] = useState('')
    const [bulkResult, setBulkResult] = useState(null)
    const fileInputRef = useRef(null)

    const invalidate = () => queryClient.invalidateQueries({ queryKey: ['device-registry'] })

    const { data: devices = [], isLoading } = useQuery({
        queryKey: ['device-registry'],
        queryFn: () => DeviceRegistryService.getAll(),
    })

    const { data: categories = [] } = useQuery({
        queryKey: ['nas-categories'],
        queryFn: NasCategoriesService.getAll,
    })

    const { data: stats } = useQuery({
        queryKey: ['device-registry', 'stats'],
        queryFn: DeviceRegistryService.getStats,
    })

    const createMutation = useMutation({
        mutationFn: DeviceRegistryService.create,
        onSuccess: () => { invalidate(); closeModal(); showToast('Device registered', 'success') },
        onError: (e) => showToast(e.response?.data?.detail || 'Error creating device', 'error'),
    })

    const updateMutation = useMutation({
        mutationFn: ({ id, data }) => DeviceRegistryService.update(id, data),
        onSuccess: () => { invalidate(); closeModal(); showToast('Device updated', 'success') },
        onError: (e) => showToast(e.response?.data?.detail || 'Error updating device', 'error'),
    })

    const deleteMutation = useMutation({
        mutationFn: DeviceRegistryService.remove,
        onSuccess: () => { invalidate(); setDeleteTarget(null); showToast('Device removed', 'success') },
        onError: (e) => showToast(e.response?.data?.detail || 'Error deleting device', 'error'),
    })

    const bulkMutation = useMutation({
        mutationFn: (payload) => DeviceRegistryService.bulkCreate(payload),
        onSuccess: (result) => {
            invalidate()
            setBulkResult(result)
            showToast(`Created: ${result.created}, Updated: ${result.updated}`, 'success')
        },
        onError: (e) => showToast(e.response?.data?.detail || 'Bulk import failed', 'error'),
    })

    const csvMutation = useMutation({
        mutationFn: ({ file, categoryId }) => DeviceRegistryService.bulkCsv(file, categoryId || null),
        onSuccess: (result) => {
            invalidate()
            setBulkResult(result)
            showToast(`Created: ${result.created}, Updated: ${result.updated}`, 'success')
        },
        onError: (e) => showToast(e.response?.data?.detail || 'CSV import failed', 'error'),
    })

    const openCreate = () => { setEditItem(null); setForm(EMPTY_FORM); setShowModal(true) }
    const openEdit = (item) => {
        setEditItem(item)
        setForm({
            mac: item.mac,
            name: item.name ?? '',
            category_id: item.category_id ?? '',
            nas_ip: item.nas_ip ?? '',
            description: item.description ?? '',
            is_active: item.is_active,
        })
        setShowModal(true)
    }
    const closeModal = () => { setShowModal(false); setEditItem(null); setForm(EMPTY_FORM) }

    const handleSubmit = (e) => {
        e.preventDefault()
        const payload = {
            mac: form.mac,
            name: form.name || null,
            category_id: form.category_id ? parseInt(form.category_id, 10) : null,
            nas_ip: form.nas_ip || null,
            description: form.description || null,
            is_active: form.is_active,
        }
        if (editItem) {
            updateMutation.mutate({ id: editItem.id, data: payload })
        } else {
            createMutation.mutate(payload)
        }
    }

    const handleBulkText = () => {
        const lines = bulkText.split('\n').map(l => l.trim()).filter(Boolean)
        const rowErrors = []
        const devices = lines.map(line => {
            const parts = line.split(',')
            const mac = parts[0]?.trim()
            const nasIp = parts[1]?.trim() || null
            const name = parts[2]?.trim() || null
            const description = parts[3]?.trim() || null
            const rowCategory = parts[4]?.trim()
            const parsedRowCategory = rowCategory ? parseInt(rowCategory, 10) : null

            if (!mac || !nasIp || !name || !description) {
                rowErrors.push(`Row "${line}": required format is mac,nas_ip,name,description[,category_id]`)
                return null
            }

            return {
                mac,
                nas_ip: nasIp,
                name,
                description,
                category_id: Number.isInteger(parsedRowCategory) ? parsedRowCategory : (bulkCategoryId ? parseInt(bulkCategoryId, 10) : null),
                is_active: 1,
            }
        }).filter(Boolean)

        if (rowErrors.length > 0) {
            showToast(rowErrors[0], 'error')
            return
        }

        bulkMutation.mutate({
            devices,
            category_id: bulkCategoryId ? parseInt(bulkCategoryId, 10) : null,
        })
    }

    const handleDownloadTemplate = async () => {
        try {
            const blob = await DeviceRegistryService.downloadBulkTemplate()
            const url = window.URL.createObjectURL(new Blob([blob], { type: 'text/csv;charset=utf-8-sig' }))
            const link = document.createElement('a')
            link.href = url
            link.setAttribute('download', 'device_registry_bulk_template.csv')
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            window.URL.revokeObjectURL(url)
        } catch (e) {
            showToast(e.response?.data?.detail || 'Template download failed', 'error')
        }
    }

    const handleCsvUpload = (e) => {
        const file = e.target.files?.[0]
        if (!file) return
        csvMutation.mutate({ file, categoryId: bulkCategoryId ? parseInt(bulkCategoryId, 10) : null })
        e.target.value = ''
    }

    const filtered = devices.filter(d => {
        const term = search.toLowerCase()
        const matchSearch = !term || d.mac.includes(term) ||
            (d.name || '').toLowerCase().includes(term) ||
            (d.description || '').toLowerCase().includes(term) ||
            (d.nas_ip || '').includes(term)
        const matchCat = !filterCategory || String(d.category_id) === filterCategory
        return matchSearch && matchCat
    })

    return (
        <div className="space-y-6 pb-10 px-4">
            <div className="py-4">
                <h2 className="text-3xl font-extrabold text-slate-800 tracking-tight flex items-center gap-3">
                    <Cpu className="text-indigo-600" size={32} />
                    Device Registry
                </h2>
                <p className="text-slate-500 mt-1 text-xs font-black uppercase tracking-widest opacity-60">
                    Register endpoint devices (SMs, CPEs) by MAC — assign to category for policy resolution
                </p>
            </div>

            {/* ── Info Box: What is the Device Registry? ─────────────────────── */}
            <div className="bg-indigo-50 border border-indigo-200 rounded-2xl p-4 mb-2">
                <div className="flex items-center gap-2 mb-2">
                    <Cpu size={15} className="text-indigo-500" />
                    <h3 className="text-xs font-black text-indigo-700 uppercase tracking-widest">What is the Device Registry?</h3>
                </div>
                <p className="text-sm text-slate-600 leading-relaxed">
                    The Device Registry solves <strong>MAC→category policy lookup</strong> in Step 1.5 of the RADIUS auth flow.
                    In RADIUS-proxy scenarios, parent NAS devices share an IP but endpoint devices have different MACs —
                    the registry maps each MAC to its category for policy resolution. Use <strong>NAS Devices</strong> to manage
                    RADIUS NAS/proxy configuration; use <strong>Device Registry</strong> to register endpoint devices (SMs, CPEs).
                </p>
            </div>

            {/* Stats + Actions */}
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div className="flex items-center gap-4 px-5 py-2.5 bg-white border border-slate-200 rounded-2xl shadow-sm text-xs font-black text-slate-500 uppercase tracking-widest">
                    <span className="flex items-center gap-1.5">
                        <Cpu size={13} className="text-indigo-400" />
                        {stats?.total ?? '…'} Devices
                    </span>
                    <span className="w-px h-4 bg-slate-200" />
                    <span className="flex items-center gap-1.5 text-emerald-600">
                        <CheckCircle size={13} /> {stats?.active ?? '…'} Active
                    </span>
                </div>
                {canWrite && (
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => { setShowBulk(true); setBulkResult(null) }}
                            className="flex items-center gap-2 px-4 py-2.5 bg-slate-100 text-slate-700 rounded-xl font-black text-xs hover:bg-slate-200 transition-colors"
                        >
                            <Upload size={15} /> Bulk Import
                        </button>
                        <button
                            onClick={openCreate}
                            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-xl font-black text-xs hover:bg-indigo-700 transition-colors shadow-sm"
                        >
                            <Plus size={16} /> Add Device
                        </button>
                    </div>
                )}
            </div>

            {/* Filters */}
            <div className="flex gap-3 items-center">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
                    <input
                        className="pl-8 pr-3 py-2 text-sm border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                        placeholder="Search MAC, name, description, IP…"
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                    />
                </div>
                <select
                    className="px-3 py-2 text-sm border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                    value={filterCategory}
                    onChange={e => setFilterCategory(e.target.value)}
                >
                    <option value="">All categories</option>
                    {categories.map(c => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
                </select>
            </div>

            {/* Table */}
            <div className="bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
                {isLoading ? (
                    <div className="flex items-center justify-center py-16">
                        <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                    </div>
                ) : filtered.length === 0 ? (
                    <div className="text-center py-16 text-slate-400">
                        <Cpu size={40} className="mx-auto mb-3 opacity-30" />
                        <p className="font-bold text-sm">No devices registered</p>
                        <p className="text-xs mt-1">Add devices manually or use Bulk Import</p>
                    </div>
                ) : (
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-slate-100 bg-slate-50">
                                <th className="text-left px-5 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest">MAC</th>
                                <th className="text-left px-5 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest">Name</th>
                                <th className="text-left px-5 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest">Category</th>
                                <th className="text-left px-5 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest">AP IP</th>
                                <th className="text-left px-5 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest">Description</th>
                                <th className="text-left px-5 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest">Status</th>
                                {canWrite && <th className="px-5 py-3" />}
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map(d => (
                                <tr key={d.id} className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
                                    <td className="px-5 py-3 font-mono text-xs font-bold text-slate-700">
                                        {d.mac.match(/.{1,2}/g).join(':')}
                                    </td>
                                    <td className="px-5 py-3 text-xs font-semibold text-slate-700">{d.name || '—'}</td>
                                    <td className="px-5 py-3">
                                        {d.category_name
                                            ? <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full text-[10px] font-black uppercase">{d.category_name}</span>
                                            : <span className="text-slate-400 text-xs">—</span>}
                                    </td>
                                    <td className="px-5 py-3 font-mono text-xs text-slate-500">{d.nas_ip || '—'}</td>
                                    <td className="px-5 py-3 text-xs text-slate-500">{d.description || '—'}</td>
                                    <td className="px-5 py-3">
                                        {d.is_active
                                            ? <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-[10px] font-black">Active</span>
                                            : <span className="px-2 py-0.5 bg-slate-100 text-slate-500 rounded-full text-[10px] font-black">Inactive</span>}
                                    </td>
                                    {canWrite && (
                                        <td className="px-5 py-3">
                                            <div className="flex items-center gap-2 justify-end">
                                                <button onClick={() => openEdit(d)} className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors">
                                                    <Edit2 size={13} />
                                                </button>
                                                {canDelete && (
                                                    <button onClick={() => setDeleteTarget(d)} className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors">
                                                        <Trash2 size={13} />
                                                    </button>
                                                )}
                                            </div>
                                        </td>
                                    )}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            {/* Create/Edit Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-slate-900/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
                    <div className="bg-white rounded-3xl w-full max-w-md shadow-2xl overflow-hidden">
                        <div className="p-6 bg-slate-50 border-b flex justify-between items-center">
                            <h3 className="text-lg font-black text-slate-800">
                                {editItem ? 'Edit Device' : 'Register Device'}
                            </h3>
                            <button onClick={closeModal} className="p-2 hover:bg-slate-200 rounded-full transition-colors text-slate-500">
                                <X size={18} />
                            </button>
                        </div>
                        <form onSubmit={handleSubmit} className="p-6 space-y-4">
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">MAC Address *</label>
                                <input
                                    required
                                    placeholder="e.g. 0A:00:3E:45:76:4A"
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm font-mono disabled:bg-slate-50 disabled:cursor-not-allowed"
                                    value={form.mac}
                                    onChange={e => setForm(f => ({ ...f, mac: e.target.value }))}
                                    disabled={!!editItem}
                                />
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Name</label>
                                <input
                                    placeholder="e.g. SM Torre Norte"
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                                    value={form.name}
                                    onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                                />
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Category</label>
                                <select
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm bg-white"
                                    value={form.category_id}
                                    onChange={e => setForm(f => ({ ...f, category_id: e.target.value }))}
                                >
                                    <option value="">— None —</option>
                                    {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                                </select>
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">AP IP (optional)</label>
                                <input
                                    placeholder="e.g. 192.168.1.11"
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm font-mono"
                                    value={form.nas_ip}
                                    onChange={e => setForm(f => ({ ...f, nas_ip: e.target.value }))}
                                />
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Description</label>
                                <input
                                    placeholder="e.g. SM Torre Norte"
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                                    value={form.description}
                                    onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                                />
                            </div>
                            <div className="flex items-center gap-3">
                                <input
                                    type="checkbox"
                                    id="dev-active"
                                    checked={form.is_active === 1}
                                    onChange={e => setForm(f => ({ ...f, is_active: e.target.checked ? 1 : 0 }))}
                                    className="w-4 h-4 rounded"
                                />
                                <label htmlFor="dev-active" className="text-sm font-bold text-slate-700">Active</label>
                            </div>
                            <div className="flex gap-3 pt-2">
                                <button type="button" onClick={closeModal} className="flex-1 px-4 py-2.5 border border-slate-200 rounded-xl text-sm font-bold text-slate-600 hover:bg-slate-50">Cancel</button>
                                <button type="submit" className="flex-1 px-4 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-bold hover:bg-indigo-700 transition-colors">
                                    {editItem ? 'Save' : 'Register'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Bulk Import Modal */}
            {showBulk && (
                <div className="fixed inset-0 bg-slate-900/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
                    <div className="bg-white rounded-3xl w-full max-w-lg shadow-2xl overflow-hidden">
                        <div className="p-6 bg-slate-50 border-b flex justify-between items-center">
                            <h3 className="text-lg font-black text-slate-800">Bulk Import Devices</h3>
                            <button onClick={() => setShowBulk(false)} className="p-2 hover:bg-slate-200 rounded-full text-slate-500">
                                <X size={18} />
                            </button>
                        </div>
                        <div className="p-6 space-y-4">
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Default Category</label>
                                <select
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm bg-white"
                                    value={bulkCategoryId}
                                    onChange={e => setBulkCategoryId(e.target.value)}
                                >
                                    <option value="">— None —</option>
                                    {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                                </select>
                            </div>

                            {/* CSV Upload */}
                            <div className="border-2 border-dashed border-slate-200 rounded-xl p-4 text-center">
                                <Upload size={24} className="mx-auto mb-2 text-slate-400" />
                                <p className="text-xs font-bold text-slate-600 mb-1">Upload CSV file</p>
                                <p className="text-[10px] text-slate-400 mb-3">Required columns: mac, nas_ip, name, description · Optional: category_id</p>
                                <div className="flex justify-center gap-2">
                                    <button
                                        type="button"
                                        onClick={() => fileInputRef.current?.click()}
                                        disabled={csvMutation.isPending}
                                        className="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg text-xs font-bold hover:bg-slate-200 transition-colors disabled:opacity-50"
                                    >
                                        {csvMutation.isPending ? 'Importing…' : 'Choose CSV'}
                                    </button>
                                    <button
                                        type="button"
                                        onClick={handleDownloadTemplate}
                                        className="px-4 py-2 bg-indigo-50 text-indigo-700 rounded-lg text-xs font-bold hover:bg-indigo-100 transition-colors"
                                    >
                                        <span className="inline-flex items-center gap-1.5"><Download size={12} /> Descargar template</span>
                                    </button>
                                </div>
                                <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleCsvUpload} />
                            </div>

                            <div className="text-center text-xs text-slate-400 font-bold">— or paste device list —</div>

                            {/* Text Paste */}
                            <div>
                                <p className="text-[10px] text-slate-400 mb-1.5">One per line: mac,nas_ip,name,description[,category_id]</p>
                                <textarea
                                    className="w-full px-3 py-2 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-xs font-mono h-32 resize-none"
                                    placeholder={"0a003e45764a,192.168.1.10,SM Torre Norte,Cliente premium\n0a003e45764b,192.168.1.11,SM Torre Sur,Backhaul secundario,2"}
                                    value={bulkText}
                                    onChange={e => setBulkText(e.target.value)}
                                />
                            </div>

                            {bulkResult && (
                                <div className={`p-3 rounded-xl text-xs font-bold ${bulkResult.errors.length > 0 ? 'bg-amber-50 border border-amber-200 text-amber-800' : 'bg-emerald-50 border border-emerald-200 text-emerald-800'}`}>
                                    <div className="flex items-center gap-2 mb-1">
                                        {bulkResult.errors.length > 0 ? <AlertTriangle size={14} /> : <CheckCircle size={14} />}
                                        Created: {bulkResult.created} · Updated: {bulkResult.updated} · Errors: {bulkResult.errors.length}
                                    </div>
                                    {bulkResult.errors.slice(0, 5).map((err, i) => (
                                        <div key={i} className="font-mono text-[10px] mt-0.5">{err}</div>
                                    ))}
                                    {bulkResult.errors.length > 5 && (
                                        <div className="text-[10px] mt-0.5">…and {bulkResult.errors.length - 5} more</div>
                                    )}
                                </div>
                            )}

                            <div className="flex gap-3">
                                <button onClick={() => setShowBulk(false)} className="flex-1 px-4 py-2.5 border border-slate-200 rounded-xl text-sm font-bold text-slate-600 hover:bg-slate-50">Close</button>
                                <button
                                    onClick={handleBulkText}
                                    disabled={!bulkText.trim() || bulkMutation.isPending}
                                    className="flex-1 px-4 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                                >
                                    {bulkMutation.isPending ? 'Importing…' : 'Import List'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Delete Confirm */}
            {deleteTarget && (
                <div className="fixed inset-0 bg-slate-900/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
                    <div className="bg-white rounded-3xl w-full max-w-sm shadow-2xl p-8 space-y-4">
                        <div className="w-14 h-14 rounded-full bg-rose-100 flex items-center justify-center mx-auto">
                            <AlertTriangle size={24} className="text-rose-600" />
                        </div>
                        <div className="text-center">
                            <h3 className="font-black text-slate-800 text-lg">Remove Device?</h3>
                            <p className="text-slate-500 text-sm mt-1 font-mono">{deleteTarget.mac}</p>
                        </div>
                        <div className="flex gap-3">
                            <button onClick={() => setDeleteTarget(null)} className="flex-1 px-4 py-2.5 border border-slate-200 rounded-xl text-sm font-bold text-slate-600 hover:bg-slate-50">Cancel</button>
                            <button
                                onClick={() => deleteMutation.mutate(deleteTarget.id)}
                                className="flex-1 px-4 py-2.5 bg-rose-600 text-white rounded-xl text-sm font-bold hover:bg-rose-700 transition-colors"
                            >
                                Remove
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

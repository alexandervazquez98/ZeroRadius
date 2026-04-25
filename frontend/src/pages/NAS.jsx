import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { Plus, Trash2, Tag, ChevronDown, ChevronUp, Settings2, Download } from 'lucide-react';
import NasCategoriesService from '../services/nasCategoriesService';
import { useToast } from '../context/ToastContext';

// ── Helpers ────────────────────────────────────────────────────────────────────

const CRITICALITY_BADGE = {
    critical:   'bg-rose-100 text-rose-700 border border-rose-200',
    restricted: 'bg-amber-100 text-amber-700 border border-amber-200',
    standard:   'bg-emerald-100 text-emerald-700 border border-emerald-200',
};

const EMPTY_CAT_FORM = { name: '', description: '', criticality: 'standard', vendor: '' };

// ── Page ───────────────────────────────────────────────────────────────────────

const NasPage = () => {
    const queryClient = useQueryClient();
    const { showToast } = useToast();

    // NAS modal state
    const [isOpen, setIsOpen] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [formData, setFormData] = useState({
        nasname: '', secret: '', shortname: '', type: 'other', category_id: '',
    });
    const [nasCategory, setNasCategory] = useState('AP');
    const [nasName, setNasName] = useState('');

    // Category manager state
    const [showCatManager, setShowCatManager] = useState(false);
    const [catForm, setCatForm] = useState(EMPTY_CAT_FORM);
    const [catError, setCatError] = useState('');

    // ── Queries ──────────────────────────────────────────────────────────────

    const { data: nasList = [], isLoading } = useQuery({
        queryKey: ['nas'],
        queryFn: () => api.get('/nas').then(r => r.data),
    });

    const { data: categories = [] } = useQuery({
        queryKey: ['nas-categories'],
        queryFn: NasCategoriesService.getAll,
    });

    // ── NAS Mutations ────────────────────────────────────────────────────────

    const createMutation = useMutation({
        mutationFn: (nas) => api.post('/nas', nas),
        onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['nas'] }); closeModal(); },
    });

    const updateMutation = useMutation({
        mutationFn: ({ id, data }) => api.put(`/nas/${id}`, data),
        onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['nas'] }); closeModal(); },
    });

    const deleteMutation = useMutation({
        mutationFn: (id) => api.delete(`/nas/${id}`),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['nas'] }),
    });

    // ── Category Mutations ───────────────────────────────────────────────────

    const createCatMutation = useMutation({
        mutationFn: NasCategoriesService.create,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['nas-categories'] });
            setCatForm(EMPTY_CAT_FORM);
            setCatError('');
        },
        onError: (err) => {
            setCatError(err?.response?.data?.detail || 'Error creating category');
        },
    });

    const deleteCatMutation = useMutation({
        mutationFn: NasCategoriesService.remove,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['nas-categories'] }),
        onError: (err) => {
            setCatError(err?.response?.data?.detail || 'Cannot delete — category may still be in use');
        },
    });

    // ── NAS Modal helpers ────────────────────────────────────────────────────

    const openEdit = (nas) => {
        setEditingId(nas.id);
        setFormData({
            nasname: nas.nasname,
            secret: nas.secret,
            shortname: nas.shortname,
            type: nas.type,
            category_id: nas.category_id || '',
        });
        if (nas.shortname && nas.shortname.includes('-')) {
            const parts = nas.shortname.split('-');
            const possibleCategory = parts[0];
            const cats = ['AP', 'SM', 'PTZ', 'SW', 'RTR', 'FW', 'WLC', 'OTHER'];
            if (cats.includes(possibleCategory)) {
                setNasCategory(possibleCategory);
                setNasName(parts.slice(1).join('-'));
            } else {
                setNasCategory('OTHER');
                setNasName(nas.shortname);
            }
        } else {
            setNasCategory('OTHER');
            setNasName(nas.shortname || '');
        }
        setIsOpen(true);
    };

    const closeModal = () => {
        setIsOpen(false);
        setEditingId(null);
        setFormData({ nasname: '', secret: '', shortname: '', type: 'other', category_id: '' });
        setNasCategory('AP');
        setNasName('');
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        const finalShortname = nasCategory === 'OTHER' ? nasName : `${nasCategory}-${nasName}`;
        const payload = {
            ...formData,
            shortname: finalShortname,
            category_id: formData.category_id ? parseInt(formData.category_id, 10) : null,
        };
        if (editingId) {
            updateMutation.mutate({ id: editingId, data: payload });
        } else {
            createMutation.mutate(payload);
        }
    };

    // ── Render ────────────────────────────────────────────────────────────────

    return (
        <div className="space-y-6 pb-10">

            {/* Header */}
            <div className="flex justify-between items-center">
                <h2 className="text-2xl font-bold text-slate-800">NAS Devices</h2>
                <div className="flex items-center gap-3">
                    <button
                        onClick={async () => {
                            try {
                                const response = await api.get('/nas/ca-certificate', { responseType: 'blob' });
                                const url = window.URL.createObjectURL(new Blob([response.data]));
                                const link = document.createElement('a');
                                link.href = url;
                                link.setAttribute('download', 'radius-ca.pem');
                                document.body.appendChild(link);
                                link.click();
                                link.remove();
                                window.URL.revokeObjectURL(url);
                            } catch (err) {
                                console.error('Failed to download CA certificate:', err);
                                showToast('Failed to download CA certificate', 'error');
                            }
                        }}
                        className="flex items-center gap-2 px-4 py-2 border border-slate-200 rounded-xl text-sm text-slate-600 hover:bg-slate-50 transition-colors"
                    >
                        <Download size={15} className="text-emerald-500" />
                        Download CA
                    </button>
                    <button
                        onClick={() => { setShowCatManager(c => !c); setCatError(''); }}
                        className="flex items-center gap-2 px-4 py-2 border border-slate-200 rounded-xl text-sm text-slate-600 hover:bg-slate-50 transition-colors"
                    >
                        <Tag size={15} className="text-violet-500" />
                        Categories
                        {showCatManager ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                    <button
                        onClick={() => { setEditingId(null); setIsOpen(true); }}
                        className="bg-indigo-600 text-white px-4 py-2 rounded-xl flex items-center gap-2 hover:bg-indigo-700 transition-colors"
                    >
                        <Plus size={18} />
                        Add NAS
                    </button>
                </div>
            </div>

            {/* ── Category Manager Panel ─────────────────────────────────────────── */}
            {showCatManager && (
                <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
                    <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center gap-2">
                        <Settings2 size={15} className="text-slate-400" />
                        <h3 className="text-xs font-black text-slate-600 uppercase tracking-widest">Device Categories</h3>
                        <span className="ml-auto text-xs text-slate-400 font-medium">{categories.length} total</span>
                    </div>

                    {/* Category list */}
                    <div className="divide-y divide-slate-50">
                        {categories.length === 0 && (
                            <div className="px-6 py-6 text-center text-sm text-slate-400">
                                No categories yet — add one below
                            </div>
                        )}
                        {categories.map(cat => (
                            <div key={cat.id} className="px-6 py-3 flex items-center gap-4 hover:bg-slate-50/60 transition-colors">
                                <span className={`text-[9px] font-black uppercase px-2 py-0.5 rounded-full flex-shrink-0 ${CRITICALITY_BADGE[cat.criticality] || CRITICALITY_BADGE.standard}`}>
                                    {cat.criticality}
                                </span>
                                <span className="font-bold text-sm text-slate-800">{cat.name}</span>
                                {cat.vendor && (
                                    <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded">{cat.vendor}</span>
                                )}
                                {cat.description && (
                                    <span className="text-xs text-slate-400 italic truncate max-w-xs hidden md:block">{cat.description}</span>
                                )}
                                <button
                                    title="Delete category"
                                    onClick={() => deleteCatMutation.mutate(cat.id)}
                                    className="ml-auto text-slate-300 hover:text-rose-500 transition-colors p-1.5 rounded-lg hover:bg-rose-50"
                                >
                                    <Trash2 size={13} />
                                </button>
                            </div>
                        ))}
                    </div>

                    {/* Add category form */}
                    <div className="px-6 py-5 bg-slate-50 border-t border-slate-200">
                        {catError && (
                            <div className="mb-3 p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700">
                                {catError}
                            </div>
                        )}
                        <div className="flex gap-3 items-end flex-wrap">
                            <div className="flex-1 min-w-36">
                                <label className="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Name *</label>
                                <input
                                    id="cat-name"
                                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                                    placeholder="AP_CAMBIUM_450I"
                                    value={catForm.name}
                                    onChange={e => setCatForm(f => ({ ...f, name: e.target.value }))}
                                />
                            </div>
                            <div className="w-36">
                                <label className="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Criticality</label>
                                <select
                                    id="cat-criticality"
                                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm"
                                    value={catForm.criticality}
                                    onChange={e => setCatForm(f => ({ ...f, criticality: e.target.value }))}
                                >
                                    <option value="standard">Standard</option>
                                    <option value="critical">Critical</option>
                                    <option value="restricted">Restricted</option>
                                </select>
                            </div>
                            <div className="w-32">
                                <label className="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Vendor</label>
                                <input
                                    id="cat-vendor"
                                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                                    placeholder="Cambium"
                                    value={catForm.vendor}
                                    onChange={e => setCatForm(f => ({ ...f, vendor: e.target.value }))}
                                />
                            </div>
                            <div className="flex-1 min-w-44">
                                <label className="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Description</label>
                                <input
                                    id="cat-desc"
                                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                                    placeholder="Access Point Cambium 450i series"
                                    value={catForm.description}
                                    onChange={e => setCatForm(f => ({ ...f, description: e.target.value }))}
                                />
                            </div>
                            <button
                                type="button"
                                id="cat-add-btn"
                                onClick={() => {
                                    if (!catForm.name.trim()) { setCatError('Name is required'); return; }
                                    setCatError('');
                                    createCatMutation.mutate(catForm);
                                }}
                                disabled={createCatMutation.isPending}
                                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-bold hover:bg-indigo-700 transition-colors disabled:opacity-50"
                            >
                                <Plus size={14} />
                                {createCatMutation.isPending ? 'Adding…' : 'Add'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ── NAS Card Grid ──────────────────────────────────────────────────── */}
            {isLoading ? (
                <div className="text-center py-16 text-slate-400">Loading devices…</div>
            ) : nasList.length === 0 ? (
                <div className="text-center py-16 text-slate-400">
                    <p className="text-lg font-semibold">No NAS devices registered</p>
                    <p className="text-sm mt-1">Add your first device with the button above.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {nasList.map((nas) => (
                        <div
                            key={nas.id}
                            className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 relative group hover:shadow-md transition-shadow"
                        >
                            {/* Hover actions */}
                            <div className="absolute top-4 right-4 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                    onClick={() => openEdit(nas)}
                                    className="text-slate-400 hover:text-blue-500 p-1.5 bg-slate-50 hover:bg-blue-50 rounded-lg transition-colors"
                                    title="Edit"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
                                    </svg>
                                </button>
                                <button
                                    onClick={() => deleteMutation.mutate(nas.id)}
                                    className="text-slate-400 hover:text-red-500 p-1.5 bg-slate-50 hover:bg-red-50 rounded-lg transition-colors"
                                    title="Delete"
                                >
                                    <Trash2 size={14} />
                                </button>
                            </div>

                            {/* Card header */}
                            <div className="flex items-start gap-3 mb-4 pr-14">
                                <div className="flex-1 min-w-0">
                                    <h3 className="font-bold text-base text-slate-800 truncate">
                                        {nas.shortname || <span className="italic text-slate-400 text-sm">Unnamed</span>}
                                    </h3>
                                    <p className="text-xs text-slate-500 font-mono mt-0.5">{nas.nasname}</p>
                                </div>
                                {nas.category_name && (
                                    <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 border border-violet-200 flex-shrink-0 mt-0.5">
                                        {nas.category_name}
                                    </span>
                                )}
                            </div>

                            {/* Card details */}
                            <div className="space-y-2">
                                <div className="flex justify-between text-xs">
                                    <span className="text-slate-400 font-medium">Type</span>
                                    <span className="font-bold text-slate-600 uppercase">{nas.type}</span>
                                </div>
                                <div className="flex justify-between text-xs">
                                    <span className="text-slate-400 font-medium">Secret</span>
                                    <span className="font-mono bg-slate-100 px-2 py-0.5 rounded text-slate-500">••••••</span>
                                </div>
                                {nas.zone_id && (
                                    <div className="flex justify-between text-xs">
                                        <span className="text-slate-400 font-medium">Zone</span>
                                        <span className="font-bold text-slate-600">#{nas.zone_id}</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* ── Modal: Create / Edit NAS ───────────────────────────────────────── */}
            {isOpen && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-3xl p-7 w-full max-w-lg shadow-2xl">
                        <h3 className="text-lg font-black text-slate-800 mb-5">
                            {editingId ? 'Edit NAS Client' : 'Add NAS Client'}
                        </h3>
                        <form onSubmit={handleSubmit} className="space-y-4">

                            {/* IP / CIDR */}
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">
                                    IP Address or CIDR *
                                </label>
                                <input
                                    id="nas-nasname"
                                    className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm font-mono outline-none focus:ring-2 focus:ring-indigo-500"
                                    value={formData.nasname}
                                    onChange={e => setFormData({ ...formData, nasname: e.target.value })}
                                    required
                                    placeholder="192.168.1.10  or  10.53.1.0/24"
                                />
                            </div>

                                {/* Shortname */}
                                <div>
                                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">
                                        Short Name
                                    </label>
                                    <input
                                        id="nas-shortname"
                                        className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                                        value={nasName}
                                        onChange={e => setNasName(e.target.value)}
                                        placeholder="e.g. Sector1-Norte"
                                        required
                                    />
                                </div>

                            {/* Type + Category */}
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Type</label>
                                    <select
                                        id="nas-type"
                                        className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm"
                                        value={formData.type}
                                        onChange={e => setFormData({ ...formData, type: e.target.value })}
                                    >
                                        <option value="other">Other</option>
                                        <option value="cisco">Cisco</option>
                                        <option value="mikrotik">Mikrotik</option>
                                        <option value="huawei">Huawei</option>
                                        <option value="ubiquiti">Ubiquiti</option>
                                        <option value="cambium">Cambium</option>
                                        <option value="dell">Dell</option>
                                        <option value="juniper">Juniper</option>
                                        <option value="hp">HP</option>
                                        <option value="fortinet">Fortinet</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">
                                        Category <span className="text-slate-300 font-normal normal-case tracking-normal">(optional)</span>
                                    </label>
                                    <select
                                        id="nas-category-id"
                                        className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm"
                                        value={formData.category_id}
                                        onChange={e => setFormData({ ...formData, category_id: e.target.value })}
                                    >
                                        <option value="">— None —</option>
                                        {categories.map(c => (
                                            <option key={c.id} value={c.id}>{c.name}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            {/* Secret */}
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">
                                    Shared Secret *
                                </label>
                                <input
                                    id="nas-secret"
                                    className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm font-mono outline-none focus:ring-2 focus:ring-indigo-500"
                                    value={formData.secret}
                                    onChange={e => setFormData({ ...formData, secret: e.target.value })}
                                    required
                                    minLength={32}
                                    placeholder="Minimum 32 characters"
                                />
                                <p className="text-xs text-slate-400 mt-1">
                                    Minimum 32 characters.{' '}
                                    {formData.secret.length > 0 && formData.secret.length < 32 && (
                                        <span className="text-rose-500">({formData.secret.length}/32)</span>
                                    )}
                                    {formData.secret.length >= 32 && (
                                        <span className="text-emerald-600">✓ {formData.secret.length} chars</span>
                                    )}
                                </p>
                            </div>

                            {(createMutation.isError || updateMutation.isError) && (
                                <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-700">
                                    {createMutation.error?.response?.data?.detail ||
                                        updateMutation.error?.response?.data?.detail ||
                                        'Error saving NAS. Check all fields.'}
                                </div>
                            )}

                            <div className="flex justify-end gap-3 pt-2">
                                <button
                                    type="button"
                                    onClick={closeModal}
                                    className="px-5 py-2.5 border border-slate-200 rounded-xl text-sm text-slate-600 hover:bg-slate-50 transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    id="nas-submit-btn"
                                    disabled={createMutation.isPending || updateMutation.isPending}
                                    className="px-5 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-black hover:bg-indigo-700 transition-colors disabled:opacity-50"
                                >
                                    {createMutation.isPending || updateMutation.isPending
                                        ? 'Saving…'
                                        : editingId ? 'Update' : 'Save'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default NasPage;

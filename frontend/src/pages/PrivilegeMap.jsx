import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Shield, Plus, Trash2, Edit2, X, AlertTriangle, Clock, Server, User, CheckCircle } from 'lucide-react';
import dayjs from 'dayjs';
import { useAuth } from '../context/AuthContext';
import PrivilegeMapService from '../services/privilegeMapService';

// Review badge helper
const ReviewBadge = ({ reviewDate }) => {
    if (!reviewDate) return null;
    const daysUntil = dayjs(reviewDate).diff(dayjs(), 'day');
    if (daysUntil < 0) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase bg-rose-100 text-rose-700 border border-rose-200">
                <AlertTriangle size={10} /> Overdue
            </span>
        );
    }
    if (daysUntil <= 30) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase bg-amber-100 text-amber-700 border border-amber-200">
                <Clock size={10} /> Review Soon
            </span>
        );
    }
    return null;
};

const EMPTY_FORM = {
    username: '',
    nas_ip: '',
    nas_vendor: '',
    radius_group: '',
    privilege_level: '',
    justification: '',
    approved_by: '',
    review_date: '',
    is_active: true,
};

const PrivilegeMapPage = () => {
    const { hasRole } = useAuth();
    const canWrite = hasRole(['superadmin', 'admin']);
    const canDelete = hasRole(['superadmin']);

    const queryClient = useQueryClient();
    const [showModal, setShowModal] = useState(false);
    const [editItem, setEditItem] = useState(null);
    const [form, setForm] = useState(EMPTY_FORM);
    const [deleteTarget, setDeleteTarget] = useState(null);
    const [filterUsername, setFilterUsername] = useState('');
    const [filterNasIp, setFilterNasIp] = useState('');

    const { data: items = [], isLoading } = useQuery({
        queryKey: ['privilege-map', filterUsername, filterNasIp],
        queryFn: () => PrivilegeMapService.getAll({
            username: filterUsername || undefined,
            nas_ip: filterNasIp || undefined,
        }),
    });

    const createMutation = useMutation({
        mutationFn: PrivilegeMapService.create,
        onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['privilege-map'] }); closeModal(); },
    });

    const updateMutation = useMutation({
        mutationFn: ({ id, data }) => PrivilegeMapService.update(id, data),
        onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['privilege-map'] }); closeModal(); },
    });

    const deleteMutation = useMutation({
        mutationFn: PrivilegeMapService.remove,
        onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['privilege-map'] }); setDeleteTarget(null); },
    });

    const openCreate = () => {
        setEditItem(null);
        setForm(EMPTY_FORM);
        setShowModal(true);
    };

    const openEdit = (item) => {
        setEditItem(item);
        setForm({
            username: item.username,
            nas_ip: item.nas_ip,
            nas_vendor: item.nas_vendor || '',
            radius_group: item.radius_group,
            privilege_level: item.privilege_level || '',
            justification: item.justification || '',
            approved_by: item.approved_by || '',
            review_date: item.review_date ? dayjs(item.review_date).format('YYYY-MM-DD') : '',
            is_active: item.is_active,
        });
        setShowModal(true);
    };

    const closeModal = () => {
        setShowModal(false);
        setEditItem(null);
        setForm(EMPTY_FORM);
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        const payload = {
            ...form,
            review_date: form.review_date || null,
        };
        if (editItem) {
            updateMutation.mutate({ id: editItem.id, data: payload });
        } else {
            createMutation.mutate(payload);
        }
    };

    const isMutating = createMutation.isPending || updateMutation.isPending;

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-10 px-4">
            {/* Header */}
            <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6 py-4">
                <div>
                    <h2 className="text-3xl font-extrabold text-slate-800 tracking-tight flex items-center gap-3">
                        <Shield className="text-indigo-600" size={32} />
                        Privilege Map
                    </h2>
                    <p className="text-slate-500 mt-1 uppercase text-[10px] font-black tracking-widest opacity-60">
                        User–NAS Authorization Matrix
                    </p>
                </div>

                <div className="flex flex-col sm:flex-row gap-3 items-center">
                    {/* Filters */}
                    <div className="relative">
                        <User className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} />
                        <input
                            className="pl-9 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm shadow-sm"
                            placeholder="Filter username..."
                            value={filterUsername}
                            onChange={e => setFilterUsername(e.target.value)}
                        />
                    </div>
                    <div className="relative">
                        <Server className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} />
                        <input
                            className="pl-9 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm shadow-sm"
                            placeholder="Filter NAS IP..."
                            value={filterNasIp}
                            onChange={e => setFilterNasIp(e.target.value)}
                        />
                    </div>

                    {canWrite && (
                        <button
                            onClick={openCreate}
                            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-xl font-black text-xs hover:bg-indigo-700 transition-colors shadow-sm"
                        >
                            <Plus size={16} /> Add Mapping
                        </button>
                    )}
                </div>
            </div>

            {/* Table */}
            <div className="bg-white rounded-3xl shadow-xl border border-slate-200 overflow-hidden ring-1 ring-slate-100">
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                            <tr>
                                <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">Username</th>
                                <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">NAS IP</th>
                                <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">Vendor</th>
                                <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">RADIUS Group</th>
                                <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">Priv Level</th>
                                <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">Review Date</th>
                                <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">Status</th>
                                {(canWrite || canDelete) && (
                                    <th className="px-6 py-5 text-center text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b w-28">Actions</th>
                                )}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 bg-white">
                            {isLoading ? (
                                <tr><td colSpan="8" className="px-6 py-24 text-center">
                                    <div className="flex flex-col items-center gap-4">
                                        <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
                                        <span className="font-bold text-slate-500">Loading mappings...</span>
                                    </div>
                                </td></tr>
                            ) : items.length === 0 ? (
                                <tr><td colSpan="8" className="px-6 py-24 text-center">
                                    <div className="flex flex-col items-center gap-4 opacity-40">
                                        <div className="p-5 bg-slate-100 rounded-3xl"><Shield size={64} /></div>
                                        <span className="text-xl font-bold">No privilege mappings defined</span>
                                    </div>
                                </td></tr>
                            ) : (
                                items.map(item => (
                                    <tr key={item.id} className="hover:bg-slate-50/70 transition-colors group">
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <span className="text-sm font-black text-slate-800">{item.username}</span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <span className="text-xs font-mono text-slate-700 bg-slate-100 px-2 py-1 rounded">{item.nas_ip}</span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                                            {item.nas_vendor || <span className="text-slate-300 italic">—</span>}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <span className="text-xs font-bold bg-indigo-50 text-indigo-700 px-2 py-1 rounded-full">{item.radius_group}</span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                                            {item.privilege_level || <span className="text-slate-300 italic">—</span>}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div className="flex flex-col gap-1">
                                                <span className="text-sm text-slate-600">
                                                    {item.review_date ? dayjs(item.review_date).format('DD MMM YYYY') : <span className="text-slate-300 italic">—</span>}
                                                </span>
                                                <ReviewBadge reviewDate={item.review_date} />
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            {item.is_active ? (
                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase bg-emerald-50 text-emerald-700 border border-emerald-100">
                                                    <CheckCircle size={10} /> Active
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase bg-slate-100 text-slate-500 border border-slate-200">
                                                    Inactive
                                                </span>
                                            )}
                                        </td>
                                        {(canWrite || canDelete) && (
                                            <td className="px-6 py-4 text-center">
                                                <div className="flex items-center justify-center gap-2">
                                                    {canWrite && (
                                                        <button
                                                            onClick={() => openEdit(item)}
                                                            className="p-2 text-slate-400 hover:text-indigo-600 bg-slate-100 hover:bg-indigo-50 rounded-lg transition-colors"
                                                            title="Edit"
                                                        >
                                                            <Edit2 size={15} />
                                                        </button>
                                                    )}
                                                    {canDelete && (
                                                        <button
                                                            onClick={() => setDeleteTarget(item)}
                                                            className="p-2 text-slate-400 hover:text-rose-600 bg-slate-100 hover:bg-rose-50 rounded-lg transition-colors"
                                                            title="Delete"
                                                        >
                                                            <Trash2 size={15} />
                                                        </button>
                                                    )}
                                                </div>
                                            </td>
                                        )}
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
                <div className="px-10 py-4 bg-slate-50 border-t border-slate-100">
                    <div className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em]">
                        Total mappings: {items.length}
                    </div>
                </div>
            </div>

            {/* Create/Edit Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-slate-900/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
                    <div className="bg-white rounded-3xl w-full max-w-2xl shadow-2xl overflow-hidden">
                        <div className="p-8 bg-slate-50 border-b flex justify-between items-center">
                            <h3 className="text-xl font-black text-slate-800">
                                {editItem ? 'Edit Mapping' : 'New Privilege Mapping'}
                            </h3>
                            <button onClick={closeModal} className="p-3 hover:bg-slate-200 rounded-full transition-colors text-slate-500">
                                <X size={20} />
                            </button>
                        </div>
                        <form onSubmit={handleSubmit} className="p-8 space-y-5 max-h-[70vh] overflow-y-auto">
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Username *</label>
                                    <input
                                        required
                                        className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                                        value={form.username}
                                        onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                                        placeholder="e.g. jdoe"
                                    />
                                </div>
                                <div>
                                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">NAS IP *</label>
                                    <input
                                        required
                                        className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm font-mono"
                                        value={form.nas_ip}
                                        onChange={e => setForm(f => ({ ...f, nas_ip: e.target.value }))}
                                        placeholder="e.g. 192.168.1.1"
                                    />
                                </div>
                                <div>
                                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">NAS Vendor</label>
                                    <select
                                        className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm bg-white"
                                        value={form.nas_vendor}
                                        onChange={e => setForm(f => ({ ...f, nas_vendor: e.target.value }))}
                                    >
                                        <option value="">-- Select vendor --</option>
                                        <option value="Cisco">Cisco</option>
                                        <option value="Juniper">Juniper</option>
                                        <option value="Huawei">Huawei</option>
                                        <option value="Fortinet">Fortinet</option>
                                        <option value="Generic">Generic</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">RADIUS Group *</label>
                                    <input
                                        required
                                        className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                                        value={form.radius_group}
                                        onChange={e => setForm(f => ({ ...f, radius_group: e.target.value }))}
                                        placeholder="e.g. grp_readonly"
                                    />
                                </div>
                                <div>
                                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Privilege Level</label>
                                    <input
                                        className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                                        value={form.privilege_level}
                                        onChange={e => setForm(f => ({ ...f, privilege_level: e.target.value }))}
                                        placeholder="e.g. level-1"
                                    />
                                </div>
                                <div>
                                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Review Date</label>
                                    <input
                                        type="date"
                                        className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                                        value={form.review_date}
                                        onChange={e => setForm(f => ({ ...f, review_date: e.target.value }))}
                                    />
                                </div>
                                <div>
                                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Approved By *</label>
                                    <input
                                        required
                                        className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                                        value={form.approved_by}
                                        onChange={e => setForm(f => ({ ...f, approved_by: e.target.value }))}
                                        placeholder="e.g. admin"
                                    />
                                </div>
                                <div className="flex items-center gap-3 pt-6">
                                    <input
                                        type="checkbox"
                                        id="is_active"
                                        checked={form.is_active}
                                        onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))}
                                        className="w-4 h-4 rounded accent-indigo-600"
                                    />
                                    <label htmlFor="is_active" className="text-sm font-bold text-slate-700">Active</label>
                                </div>
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Justification</label>
                                <textarea
                                    rows={3}
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm resize-none"
                                    value={form.justification}
                                    onChange={e => setForm(f => ({ ...f, justification: e.target.value }))}
                                    placeholder="Business justification for this access..."
                                />
                            </div>

                            {(createMutation.isError || updateMutation.isError) && (
                                <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-700 font-semibold">
                                    Error saving mapping. Please try again.
                                </div>
                            )}

                            <div className="flex gap-3 pt-2">
                                <button
                                    type="submit"
                                    disabled={isMutating}
                                    className="flex-1 py-3 bg-indigo-600 text-white rounded-xl font-black text-sm hover:bg-indigo-700 transition-colors disabled:opacity-50"
                                >
                                    {isMutating ? 'Saving...' : editItem ? 'Save Changes' : 'Create Mapping'}
                                </button>
                                <button
                                    type="button"
                                    onClick={closeModal}
                                    className="px-6 py-3 border border-slate-200 text-slate-600 rounded-xl font-black text-sm hover:bg-slate-50 transition-colors"
                                >
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Delete Confirmation */}
            {deleteTarget && (
                <div className="fixed inset-0 bg-slate-900/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
                    <div className="bg-white rounded-3xl w-full max-w-md shadow-2xl p-8 text-center space-y-6">
                        <div className="p-5 bg-rose-100 rounded-full w-fit mx-auto">
                            <Trash2 className="text-rose-600" size={32} />
                        </div>
                        <div>
                            <h3 className="text-xl font-black text-slate-800">Delete Mapping?</h3>
                            <p className="text-sm text-slate-500 mt-2">
                                Remove privilege mapping for <span className="font-bold text-slate-800">{deleteTarget.username}</span> on NAS <span className="font-mono font-bold text-slate-800">{deleteTarget.nas_ip}</span>?
                                This action cannot be undone.
                            </p>
                        </div>
                        <div className="flex gap-3">
                            <button
                                onClick={() => deleteMutation.mutate(deleteTarget.id)}
                                disabled={deleteMutation.isPending}
                                className="flex-1 py-3 bg-rose-600 text-white rounded-xl font-black text-sm hover:bg-rose-700 transition-colors disabled:opacity-50"
                            >
                                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                            </button>
                            <button
                                onClick={() => setDeleteTarget(null)}
                                className="flex-1 py-3 border border-slate-200 text-slate-600 rounded-xl font-black text-sm hover:bg-slate-50 transition-colors"
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export { ReviewBadge };
export default PrivilegeMapPage;

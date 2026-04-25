import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, Edit2, Zap } from 'lucide-react';
import CircuitsService from '../services/circuits';
import { useToast } from '../context/ToastContext';

const EMPTY_FORM = {
    name: '',
    circuit_id: '',
    carrier: '',
    type: 'ethernet',
    description: '',
    is_active: 1,
};

const CIRCUIT_TYPES = [
    { value: 'ethernet', label: 'Ethernet' },
    { value: 'mpls', label: 'MPLS' },
    { value: 'vpn', label: 'VPN' },
    { value: 'wireless', label: 'Wireless' },
    { value: 'other', label: 'Other' },
];

const CircuitPage = () => {
    const queryClient = useQueryClient();
    const { showToast } = useToast();

    const [showModal, setShowModal] = useState(false);
    const [editItem, setEditItem] = useState(null);
    const [form, setForm] = useState(EMPTY_FORM);

    const { data: circuits = [], isLoading } = useQuery({
        queryKey: ['circuits'],
        queryFn: CircuitsService.getAll,
    });

    const createMutation = useMutation({
        mutationFn: CircuitsService.create,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['circuits'] });
            closeModal();
            showToast('Circuit created successfully', 'success');
        },
        onError: (err) => showToast(err?.response?.data?.detail || 'Error creating circuit', 'error'),
    });

    const updateMutation = useMutation({
        mutationFn: ({ id, data }) => CircuitsService.update(id, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['circuits'] });
            closeModal();
            showToast('Circuit updated successfully', 'success');
        },
        onError: (err) => showToast(err?.response?.data?.detail || 'Error updating circuit', 'error'),
    });

    const deleteMutation = useMutation({
        mutationFn: CircuitsService.remove,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['circuits'] });
            showToast('Circuit deleted successfully', 'success');
        },
        onError: (err) => showToast(err?.response?.data?.detail || 'Error deleting circuit', 'error'),
    });

    const openCreate = () => {
        setEditItem(null);
        setForm(EMPTY_FORM);
        setShowModal(true);
    };

    const openEdit = (item) => {
        setEditItem(item);
        setForm({
            name: item.name,
            circuit_id: item.circuit_id,
            carrier: item.carrier || '',
            type: item.type || 'ethernet',
            description: item.description || '',
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
        if (editItem) {
            updateMutation.mutate({ id: editItem.id, data: form });
        } else {
            createMutation.mutate(form);
        }
    };

    return (
        <div className="space-y-6 pb-10 px-4">
            {/* Header */}
            <div className="flex justify-between items-center py-4">
                <div>
                    <h2 className="text-3xl font-extrabold text-slate-800 tracking-tight flex items-center gap-3">
                        <Zap className="text-amber-500" size={32} />
                        Circuit Identifier Records
                    </h2>
                    <p className="text-slate-500 mt-1 uppercase text-[10px] font-black tracking-widest opacity-60">
                        CIR-based access resolution for RADIUS authentication
                    </p>
                </div>
                <div>
                    <button
                        onClick={openCreate}
                        className="flex items-center gap-2 px-5 py-2.5 bg-amber-600 text-white rounded-xl font-black text-xs hover:bg-amber-700 transition-colors shadow-sm"
                    >
                        <Plus size={16} /> Add Circuit
                    </button>
                </div>
            </div>

            {/* List */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                {isLoading ? (
                    <div className="text-center py-16 text-slate-400">Loading circuits...</div>
                ) : circuits.length === 0 ? (
                    <div className="text-center py-16 opacity-50">
                        <Zap size={40} className="mx-auto mb-3 text-slate-400" />
                        <p className="font-black text-slate-500">No circuits found</p>
                        <button
                            onClick={openCreate}
                            className="mt-3 text-sm text-amber-600 font-bold hover:underline"
                        >
                            + Create the first circuit
                        </button>
                    </div>
                ) : (
                    <table className="min-w-full divide-y divide-slate-100">
                        <thead className="bg-slate-50">
                            <tr>
                                <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Name</th>
                                <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Circuit ID</th>
                                <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Carrier</th>
                                <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Type</th>
                                <th className="px-6 py-4 text-center text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Status</th>
                                <th className="px-6 py-4 text-center text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] w-24">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {circuits.map(item => (
                                <tr key={item.id} className="hover:bg-slate-50/70 transition-colors">
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <span className="text-sm font-bold text-slate-700">{item.name}</span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <span className="text-xs font-mono font-bold text-slate-700 bg-slate-100 px-2 py-1 rounded">
                                            {item.circuit_id}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <span className="text-sm text-slate-500">{item.carrier || <span className="italic opacity-50">—</span>}</span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                                            item.type === 'mpls' ? 'bg-blue-100 text-blue-700' :
                                            item.type === 'vpn' ? 'bg-purple-100 text-purple-700' :
                                            item.type === 'wireless' ? 'bg-green-100 text-green-700' :
                                            item.type === 'ethernet' ? 'bg-slate-100 text-slate-700' :
                                            'bg-gray-100 text-gray-700'
                                        }`}>
                                            {item.type}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 text-center">
                                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                                            item.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                                        }`}>
                                            {item.is_active ? 'Active' : 'Inactive'}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 text-center">
                                        <div className="flex items-center justify-center gap-2">
                                            <button
                                                onClick={() => openEdit(item)}
                                                className="p-2 text-slate-400 hover:text-amber-600 bg-slate-100 hover:bg-amber-50 rounded-lg transition-colors"
                                                title="Edit"
                                            >
                                                <Edit2 size={14} />
                                            </button>
                                            <button
                                                onClick={() => {
                                                    if (window.confirm(`Delete circuit ${item.name}?`)) {
                                                        deleteMutation.mutate(item.id);
                                                    }
                                                }}
                                                className="p-2 text-slate-400 hover:text-rose-600 bg-slate-100 hover:bg-rose-50 rounded-lg transition-colors"
                                                title="Delete"
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            {/* Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-slate-900/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
                    <div className="bg-white rounded-3xl w-full max-w-md shadow-2xl overflow-hidden">
                        <div className="p-6 bg-slate-50 border-b">
                            <h3 className="text-xl font-black text-slate-800">
                                {editItem ? 'Edit Circuit' : 'Add Circuit'}
                            </h3>
                        </div>
                        <form onSubmit={handleSubmit} className="p-6 space-y-4">
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Name *</label>
                                <input
                                    required
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-amber-500 text-sm"
                                    value={form.name}
                                    onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                                    placeholder="e.g. Main Backbone CIR"
                                />
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Circuit ID *</label>
                                <input
                                    required
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-amber-500 text-sm font-mono"
                                    value={form.circuit_id}
                                    onChange={e => setForm(f => ({ ...f, circuit_id: e.target.value }))}
                                    placeholder="e.g. CIR-2024-001"
                                />
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Carrier</label>
                                <input
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-amber-500 text-sm"
                                    value={form.carrier}
                                    onChange={e => setForm(f => ({ ...f, carrier: e.target.value }))}
                                    placeholder="e.g. Verizon, AT&T"
                                />
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Type *</label>
                                <select
                                    required
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-amber-500 text-sm"
                                    value={form.type}
                                    onChange={e => setForm(f => ({ ...f, type: e.target.value }))}
                                >
                                    {CIRCUIT_TYPES.map(t => (
                                        <option key={t.value} value={t.value}>{t.label}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Description</label>
                                <textarea
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-amber-500 text-sm resize-none"
                                    rows={3}
                                    value={form.description}
                                    onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                                    placeholder="Optional description"
                                />
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Status</label>
                                <div className="flex items-center gap-4">
                                    <label className="flex items-center gap-2 cursor-pointer">
                                        <input
                                            type="radio"
                                            name="is_active"
                                            value={1}
                                            checked={form.is_active === 1}
                                            onChange={() => setForm(f => ({ ...f, is_active: 1 }))}
                                            className="text-amber-600 focus:ring-amber-500"
                                        />
                                        <span className="text-sm font-bold text-slate-700">Active</span>
                                    </label>
                                    <label className="flex items-center gap-2 cursor-pointer">
                                        <input
                                            type="radio"
                                            name="is_active"
                                            value={0}
                                            checked={form.is_active === 0}
                                            onChange={() => setForm(f => ({ ...f, is_active: 0 }))}
                                            className="text-amber-600 focus:ring-amber-500"
                                        />
                                        <span className="text-sm font-bold text-slate-700">Inactive</span>
                                    </label>
                                </div>
                            </div>
                            <div className="flex justify-end gap-3 pt-4">
                                <button
                                    type="button"
                                    onClick={closeModal}
                                    className="px-5 py-2.5 border border-slate-200 rounded-xl text-sm font-bold text-slate-600 hover:bg-slate-50 transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={createMutation.isPending || updateMutation.isPending}
                                    className="px-5 py-2.5 bg-amber-600 text-white rounded-xl text-sm font-black hover:bg-amber-700 transition-colors disabled:opacity-50"
                                >
                                    {createMutation.isPending || updateMutation.isPending ? 'Saving...' : 'Save'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default CircuitPage;
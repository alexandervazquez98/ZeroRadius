import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, Edit2, Map, Shield } from 'lucide-react';
import NetworkSegmentsService from '../services/networkSegments';
import { useToast } from '../context/ToastContext';

const EMPTY_FORM = { name: '', cidr: '', description: '' };

const NetworkSegmentsPage = () => {
    const queryClient = useQueryClient();
    const { showToast } = useToast();

    const [showModal, setShowModal] = useState(false);
    const [editItem, setEditItem] = useState(null);
    const [form, setForm] = useState(EMPTY_FORM);

    const { data: segments = [], isLoading } = useQuery({
        queryKey: ['network-segments'],
        queryFn: NetworkSegmentsService.getAll,
    });

    const createMutation = useMutation({
        mutationFn: NetworkSegmentsService.create,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['network-segments'] });
            closeModal();
            showToast('Network segment created successfully', 'success');
        },
        onError: (err) => showToast(err?.response?.data?.detail || 'Error creating segment', 'error'),
    });

    const updateMutation = useMutation({
        mutationFn: ({ id, data }) => NetworkSegmentsService.update(id, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['network-segments'] });
            closeModal();
            showToast('Network segment updated successfully', 'success');
        },
        onError: (err) => showToast(err?.response?.data?.detail || 'Error updating segment', 'error'),
    });

    const deleteMutation = useMutation({
        mutationFn: NetworkSegmentsService.remove,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['network-segments'] });
            showToast('Network segment deleted successfully', 'success');
        },
        onError: (err) => showToast(err?.response?.data?.detail || 'Error deleting segment', 'error'),
    });

    const openCreate = () => {
        setEditItem(null);
        setForm(EMPTY_FORM);
        setShowModal(true);
    };

    const openEdit = (item) => {
        setEditItem(item);
        setForm({ name: item.name, cidr: item.cidr, description: item.description || '' });
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
                        <Map className="text-indigo-600" size={32} />
                        Network Segments
                    </h2>
                    <p className="text-slate-500 mt-1 uppercase text-[10px] font-black tracking-widest opacity-60">
                        Logical groupings of network blocks for Access Policies
                    </p>
                </div>
                <div>
                    <button
                        onClick={openCreate}
                        className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-xl font-black text-xs hover:bg-indigo-700 transition-colors shadow-sm"
                    >
                        <Plus size={16} /> Add Segment
                    </button>
                </div>
            </div>

            {/* List */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                {isLoading ? (
                    <div className="text-center py-16 text-slate-400">Loading segments...</div>
                ) : segments.length === 0 ? (
                    <div className="text-center py-16 opacity-50">
                        <Map size={40} className="mx-auto mb-3 text-slate-400" />
                        <p className="font-black text-slate-500">No network segments found</p>
                        <button
                            onClick={openCreate}
                            className="mt-3 text-sm text-indigo-600 font-bold hover:underline"
                        >
                            + Create the first segment
                        </button>
                    </div>
                ) : (
                    <table className="min-w-full divide-y divide-slate-100">
                        <thead className="bg-slate-50">
                            <tr>
                                <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Name</th>
                                <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">CIDR</th>
                                <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Description</th>
                                <th className="px-6 py-4 text-center text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] w-24">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {segments.map(item => (
                                <tr key={item.id} className="hover:bg-slate-50/70 transition-colors">
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <span className="text-sm font-bold text-slate-700">{item.name}</span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <span className="text-xs font-mono font-bold text-slate-700 bg-slate-100 px-2 py-1 rounded">
                                            {item.cidr}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className="text-sm text-slate-500">{item.description || <span className="italic opacity-50">No description</span>}</span>
                                    </td>
                                    <td className="px-6 py-4 text-center">
                                        <div className="flex items-center justify-center gap-2">
                                            <button
                                                onClick={() => openEdit(item)}
                                                className="p-2 text-slate-400 hover:text-indigo-600 bg-slate-100 hover:bg-indigo-50 rounded-lg transition-colors"
                                                title="Edit"
                                            >
                                                <Edit2 size={14} />
                                            </button>
                                            <button
                                                onClick={() => {
                                                    if (window.confirm(`Delete segment ${item.name}?`)) {
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
                                {editItem ? 'Edit Segment' : 'Add Segment'}
                            </h3>
                        </div>
                        <form onSubmit={handleSubmit} className="p-6 space-y-4">
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Name *</label>
                                <input
                                    required
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                                    value={form.name}
                                    onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                                    placeholder="e.g. Core Network"
                                />
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">CIDR *</label>
                                <input
                                    required
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm font-mono"
                                    value={form.cidr}
                                    onChange={e => setForm(f => ({ ...f, cidr: e.target.value }))}
                                    placeholder="e.g. 10.0.0.0/8"
                                />
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Description</label>
                                <textarea
                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm resize-none"
                                    rows={3}
                                    value={form.description}
                                    onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                                    placeholder="Optional description"
                                />
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
                                    className="px-5 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-black hover:bg-indigo-700 transition-colors disabled:opacity-50"
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

export default NetworkSegmentsPage;

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { Plus, Trash2 } from 'lucide-react';

const NasPage = () => {
    const queryClient = useQueryClient();
    const [isOpen, setIsOpen] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [formData, setFormData] = useState({ nasname: '', secret: '', shortname: '', type: 'other' });
    const [nasCategory, setNasCategory] = useState('AP');
    const [nasName, setNasName] = useState('');

    const { data: nasList, isLoading } = useQuery({
        queryKey: ['nas'],
        queryFn: () => api.get('/nas').then(r => r.data)
    });

    const createMutation = useMutation({
        mutationFn: (nas) => api.post('/nas', nas),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['nas'] });
            closeModal();
        }
    });

    const updateMutation = useMutation({
        mutationFn: ({ id, data }) => api.put(`/nas/${id}`, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['nas'] });
            closeModal();
        }
    });

    const deleteMutation = useMutation({
        mutationFn: (id) => api.delete(`/nas/${id}`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['nas'] });
        }
    });

    const openEdit = (nas) => {
        setEditingId(nas.id);
        setFormData({
            nasname: nas.nasname,
            secret: nas.secret,
            shortname: nas.shortname,
            type: nas.type
        });
        
        // Parse existing shortname into Category and Name
        if (nas.shortname && nas.shortname.includes('-')) {
            const parts = nas.shortname.split('-');
            const possibleCategory = parts[0];
            const categories = ['AP', 'SM', 'PTZ', 'SW', 'RTR', 'FW', 'WLC', 'OTHER'];
            if (categories.includes(possibleCategory)) {
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
        setFormData({ nasname: '', secret: '', shortname: '', type: 'other' });
        setNasCategory('AP');
        setNasName('');
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        
        // Construct shortname based on category and name
        const finalShortname = nasCategory === 'OTHER' ? nasName : `${nasCategory}-${nasName}`;
        const payload = { ...formData, shortname: finalShortname };

        if (editingId) {
            updateMutation.mutate({ id: editingId, data: payload });
        } else {
            createMutation.mutate(payload);
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <h2 className="text-2xl font-bold text-slate-800">NAS Devices</h2>
                <button
                    onClick={() => { setEditingId(null); setIsOpen(true); }}
                    className="bg-indigo-600 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-indigo-700"
                >
                    <Plus size={18} />
                    Add NAS
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {nasList?.map((nas) => (
                    <div key={nas.id} className="bg-white p-6 rounded-lg shadow-sm border border-slate-200 relative group">
                        <div className="absolute top-4 right-4 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                                onClick={() => openEdit(nas)}
                                className="text-slate-400 hover:text-blue-500 p-1 bg-slate-50 rounded"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>
                            </button>
                            <button
                                onClick={() => deleteMutation.mutate(nas.id)}
                                className="text-slate-400 hover:text-red-500 p-1 bg-slate-50 rounded"
                            >
                                <Trash2 size={18} />
                            </button>
                        </div>
                        <h3 className="font-bold text-lg mb-1 flex items-center gap-2">
                            {nas.shortname || 'Unnamed'}
                            {!nas.shortname && <span className="text-xs text-red-400 font-normal border border-red-200 px-1 rounded">No Shortname</span>}
                        </h3>
                        <p className="text-sm text-slate-500 mb-4 font-mono">{nas.nasname}</p>

                        <div className="space-y-2 text-sm text-slate-600">
                            <div className="flex justify-between">
                                <span>Type:</span>
                                <span className="font-medium">{nas.type}</span>
                            </div>
                            <div className="flex justify-between">
                                <span>Secret:</span>
                                <span className="font-mono bg-slate-100 px-2 rounded">****</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Modal */}
            {isOpen && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-lg p-6 w-full max-w-md shadow-xl">
                        <h3 className="text-lg font-bold mb-4">{editingId ? 'Edit NAS Client' : 'Add NAS Client'}</h3>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium mb-1">IP Address (NAS Name)</label>
                                <input
                                    className="w-full border rounded p-2"
                                    value={formData.nasname}
                                    onChange={e => setFormData({ ...formData, nasname: e.target.value })}
                                    required
                                    placeholder="192.168.1.10"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1">Short Name / Group (ISO Naming Convention)</label>
                                <div className="flex gap-2">
                                    <select
                                        className="w-1/3 border rounded p-2"
                                        value={nasCategory}
                                        onChange={e => setNasCategory(e.target.value)}
                                    >
                                        <option value="AP">AP</option>
                                        <option value="SM">SM</option>
                                        <option value="PTZ">PTZ</option>
                                        <option value="SW">Switch</option>
                                        <option value="RTR">Router</option>
                                        <option value="FW">Firewall</option>
                                        <option value="WLC">WLC</option>
                                        <option value="OTHER">Other/Custom</option>
                                    </select>
                                    <input
                                        className="w-2/3 border rounded p-2"
                                        value={nasName}
                                        onChange={e => setNasName(e.target.value)}
                                        placeholder="e.g. Sector1-Norte"
                                        required
                                    />
                                </div>
                                <p className="text-xs text-gray-500 mt-1">Resulting shortname: <span className="font-mono bg-slate-100 px-1 py-0.5 rounded">{nasCategory === 'OTHER' ? nasName : `${nasCategory}-${nasName}`}</span></p>
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1">Type</label>
                                <select
                                    className="w-full border rounded p-2"
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
                                    <option value="dlink">D-Link</option>
                                    <option value="tp-link">TP-Link</option>
                                    <option value="fortinet">Fortinet</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1">Shared Secret</label>
                                <input
                                    className="w-full border rounded p-2 font-mono"
                                    value={formData.secret}
                                    onChange={e => setFormData({ ...formData, secret: e.target.value })}
                                    required
                                    minLength={32}
                                    placeholder="Minimum 32 characters"
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                    Must be at least 32 characters. Use a strong random value.
                                    {formData.secret.length > 0 && formData.secret.length < 32 && (
                                        <span className="text-red-500 ml-1">({formData.secret.length}/32)</span>
                                    )}
                                    {formData.secret.length >= 32 && (
                                        <span className="text-green-600 ml-1">✓ {formData.secret.length} chars</span>
                                    )}
                                </p>
                            </div>
                            <div className="flex justify-end gap-2 mt-6">
                                <button type="button" onClick={closeModal} className="px-4 py-2 border rounded hover:bg-gray-50">Cancel</button>
                                <button type="submit" className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700">
                                    {editingId ? 'Update' : 'Save'}
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

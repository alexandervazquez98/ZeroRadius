import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { Plus, Trash2, Edit, X, Clock, ShieldAlert } from 'lucide-react';
import UserWizard from '../components/UserWizard';
import { useToast } from '../context/ToastContext';

const UsersPage = () => {
    const queryClient = useQueryClient();
    const { showToast } = useToast();
    const [isOpen, setIsOpen] = useState(false);
    const [newUser, setNewUser] = useState({ username: '', attribute: 'Cleartext-Password', op: ':=', value: '' });

    const [editingUser, setEditingUser] = useState(null);
    const [jitUser, setJitUser] = useState(null);
    const [jitData, setJitData] = useState({ hours: 1, reason: '' });

    const { data: users, isLoading } = useQuery({
        queryKey: ['users'],
        queryFn: () => api.get('/users').then(r => r.data)
    });

    const createMutation = useMutation({
        mutationFn: (user) => api.post('/users/check', user),
        onSuccess: () => {
            queryClient.invalidateQueries(['users']);
            setIsOpen(false);
            setNewUser({ username: '', attribute: 'Cleartext-Password', op: ':=', value: '' });
        }
    });

    const updateMutation = useMutation({
        mutationFn: (user) => api.put(`/users/check/${user.id}`, user),
        onSuccess: () => {
            queryClient.invalidateQueries(['users']);
            setEditingUser(null);
        }
    });

    const deleteMutation = useMutation({
        mutationFn: (id) => api.delete(`/users/check/${id}`),
        onSuccess: () => queryClient.invalidateQueries(['users'])
    });

    const jitMutation = useMutation({
        mutationFn: ({ username, hours }) => api.post(`/iam-nac/jit-requests/${username}/approve?ttl_hours=${hours}`),
        onSuccess: (data) => {
            showToast(data.data.message, 'success');
            setJitUser(null);
            setJitData({ hours: 1, reason: '' });
            queryClient.invalidateQueries(['users']);
        },
        onError: (err) => {
            showToast('Error JIT: ' + (err.response?.data?.detail || err.message), 'error');
        }
    });

    const handleJitSubmit = (e) => {
        e.preventDefault();
        jitMutation.mutate({ username: jitUser.username, hours: jitData.hours });
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        createMutation.mutate(newUser);
    };

    const handleUpdate = (e) => {
        e.preventDefault();
        updateMutation.mutate(editingUser);
    }

    if (isLoading) return <div>Loading...</div>;

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <h2 className="text-2xl font-bold text-slate-800">User Management</h2>
                <button
                    onClick={() => setIsOpen(true)}
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-blue-700"
                >
                    <Plus size={18} />
                    Add User
                </button>
            </div>

            <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Username</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Attribute</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Op</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Value</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {users?.map((user) => (
                            <tr key={user.id}>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">#{user.id}</td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{user.username}</td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{user.attribute}</td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 border rounded px-2 bg-gray-50">{user.op}</td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono">{user.value}</td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 flex gap-2">
                                    <button
                                        onClick={() => setJitUser(user)}
                                        className="text-rose-600 hover:text-rose-900 mr-2"
                                        title="Break-Glass: Elevación Temporal JIT"
                                    >
                                        <Clock size={18} />
                                    </button>
                                    <button
                                        onClick={() => setEditingUser(user)}
                                        className="text-blue-600 hover:text-blue-900"
                                    >
                                        <Edit size={18} />
                                    </button>
                                    <button
                                        onClick={() => deleteMutation.mutate(user.id)}
                                        className="text-red-600 hover:text-red-900"
                                    >
                                        <Trash2 size={18} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* User Wizard Modal */}
            {isOpen && (
                <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center p-4 z-50">
                    <UserWizard
                        onComplete={() => setIsOpen(false)}
                        onCancel={() => setIsOpen(false)}
                    />
                </div>
            )}

            {/* JIT Break-Glass Modal */}
            {jitUser && (
                <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-xl shadow-2xl w-full max-w-md animate-fadeIn overflow-hidden">
                        <div className="flex justify-between items-center p-4 border-b bg-rose-50">
                            <h3 className="text-lg font-black text-rose-800 flex items-center gap-2"><ShieldAlert size={20}/> Elevación JIT</h3>
                            <button onClick={() => setJitUser(null)} className="text-rose-500 hover:text-rose-700">
                                <X size={20} />
                            </button>
                        </div>
                        <form onSubmit={handleJitSubmit} className="p-6 space-y-4">
                            <p className="text-sm text-gray-600 mb-4 font-bold">
                                Elevando privilegios de <span className="text-indigo-600 font-mono">{jitUser.username}</span>.
                            </p>
                            <div>
                                <label className="block text-xs font-black text-slate-500 uppercase tracking-widest pl-1">Horas de Validez</label>
                                <div className="flex items-center gap-2 mt-1">
                                    <input
                                        type="number"
                                        min="1"
                                        max="72"
                                        className="w-full rounded-lg shadow-sm border p-3 font-mono text-lg focus:ring-2 focus:ring-rose-400 outline-none"
                                        value={jitData.hours}
                                        onChange={e => setJitData({ ...jitData, hours: parseInt(e.target.value) })}
                                        required
                                    />
                                    <span className="text-gray-500 font-bold">Horas</span>
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-black text-slate-500 uppercase tracking-widest pl-1">Motivo (Ticket/Aprobador)</label>
                                <textarea
                                    className="mt-1 block w-full rounded-lg shadow-sm border p-3 resize-none outline-none focus:ring-2 focus:ring-rose-400"
                                    value={jitData.reason}
                                    placeholder="Ej: INC-9902, Autorizo: Manager..."
                                    rows={2}
                                    onChange={e => setJitData({ ...jitData, reason: e.target.value })}
                                    required
                                />
                            </div>
                            <div className="flex justify-end gap-2 mt-6 pt-4 border-t">
                                <button type="button" onClick={() => setJitUser(null)} className="px-4 py-2 text-gray-600 bg-gray-100 rounded-lg font-bold hover:bg-gray-200">Cancelar</button>
                                <button type="submit" className="px-5 py-2 text-white bg-rose-600 rounded-lg font-black shadow-md hover:bg-rose-700 disabled:opacity-50" disabled={jitMutation.isPending || !jitData.reason || !jitData.hours}>
                                    {jitMutation.isPending ? 'Procesando...' : 'Otorgar Acceso de Emergencia'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Edit Modal */}
            {editingUser && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-lg shadow-lg w-full max-w-md">
                        <div className="flex justify-between items-center p-4 border-b">
                            <h3 className="text-lg font-bold">Edit User Attribute</h3>
                            <button onClick={() => setEditingUser(null)} className="text-gray-500 hover:text-gray-700">
                                <X size={20} />
                            </button>
                        </div>
                        <form onSubmit={handleUpdate} className="p-4 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Username</label>
                                <input
                                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm border p-2"
                                    value={editingUser.username}
                                    onChange={e => setEditingUser({ ...editingUser, username: e.target.value })}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Attribute</label>
                                <input
                                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm border p-2"
                                    value={editingUser.attribute}
                                    onChange={e => setEditingUser({ ...editingUser, attribute: e.target.value })}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Op</label>
                                <input
                                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm border p-2"
                                    value={editingUser.op}
                                    onChange={e => setEditingUser({ ...editingUser, op: e.target.value })}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Value</label>
                                <input
                                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm border p-2"
                                    value={editingUser.value}
                                    onChange={e => setEditingUser({ ...editingUser, value: e.target.value })}
                                />
                            </div>
                            <div className="flex justify-end gap-2 mt-4">
                                <button
                                    type="button"
                                    onClick={() => setEditingUser(null)}
                                    className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                                >
                                    Save Changes
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default UsersPage;

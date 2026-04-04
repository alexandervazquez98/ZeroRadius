import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { Plus, Trash2, Edit, RefreshCw, X } from 'lucide-react';
import { useToast } from '../context/ToastContext';

const AdminUsers = () => {
    const queryClient = useQueryClient();
    const { showToast } = useToast();
    const [isOpen, setIsOpen] = useState(false);
    const [isEditOpen, setIsEditOpen] = useState(false);
    const [newUser, setNewUser] = useState({ username: '', password: '', is_active: 1 });
    const [editingUser, setEditingUser] = useState(null);
    const [passwordReset, setPasswordReset] = useState('');

    const { data: users, isLoading } = useQuery({
        queryKey: ['admin-users'],
        queryFn: () => api.get('/admin-users').then(r => r.data)
    });

    const createMutation = useMutation({
        mutationFn: (user) => api.post('/admin-users', user),
        onSuccess: () => {
            queryClient.invalidateQueries(['admin-users']);
            setIsOpen(false);
            setNewUser({ username: '', password: '', is_active: 1 });
        },
        onError: (err) => {
            showToast(err.response?.data?.detail || "Error creating user", 'error');
        }
    });

    const updateMutation = useMutation({
        mutationFn: ({ id, data }) => api.put(`/admin-users/${id}`, data),
        onSuccess: () => {
            queryClient.invalidateQueries(['admin-users']);
            setIsEditOpen(false);
            setEditingUser(null);
            setPasswordReset('');
        }
    });

    const deleteMutation = useMutation({
        mutationFn: (id) => api.delete(`/admin-users/${id}`),
        onSuccess: () => queryClient.invalidateQueries(['admin-users']),
        onError: (err) => {
            showToast(err.response?.data?.detail || "Error deleting user", 'error');
        }
    });

    const handleCreate = (e) => {
        e.preventDefault();
        createMutation.mutate(newUser);
    };

    const handleUpdate = (e) => {
        e.preventDefault();
        const data = {
            is_active: editingUser.is_active
        };
        if (passwordReset) {
            data.password = passwordReset;
        }
        updateMutation.mutate({ id: editingUser.id, data });
    };

    const openEdit = (user) => {
        setEditingUser(user);
        setPasswordReset('');
        setIsEditOpen(true);
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <h2 className="text-2xl font-bold text-slate-800">System Administrators</h2>
                <button
                    onClick={() => setIsOpen(true)}
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-blue-700"
                >
                    <Plus size={18} />
                    Add Admin
                </button>
            </div>

            <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Username</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Force Change</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {users?.map((user) => (
                            <tr key={user.id}>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">#{user.id}</td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{user.username}</td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                                        {user.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                    {user.force_password_change ? 'Yes' : 'No'}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 flex gap-2">
                                    <button
                                        onClick={() => openEdit(user)}
                                        className="text-blue-600 hover:text-blue-900"
                                        title="Edit User"
                                    >
                                        <Edit size={18} />
                                    </button>
                                    <button
                                        onClick={() => deleteMutation.mutate(user.id)}
                                        className="text-red-600 hover:text-red-900"
                                        title="Delete User"
                                        disabled={user.username === 'admin'}
                                    >
                                        <Trash2 size={18} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Create Modal */}
            {isOpen && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-lg shadow-lg w-full max-w-md p-6">
                        <h3 className="text-lg font-bold mb-4">Add New Administrator</h3>
                        <form onSubmit={handleCreate} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Username</label>
                                <input
                                    className="mt-1 block w-full rounded-md border-gray-300 border p-2"
                                    value={newUser.username}
                                    onChange={e => setNewUser({ ...newUser, username: e.target.value })}
                                    required
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Password</label>
                                <input
                                    type="password"
                                    className="mt-1 block w-full rounded-md border-gray-300 border p-2"
                                    value={newUser.password}
                                    onChange={e => setNewUser({ ...newUser, password: e.target.value })}
                                    required
                                />
                            </div>
                            <div className="flex justify-end gap-2 mt-6">
                                <button
                                    type="button"
                                    onClick={() => setIsOpen(false)}
                                    className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                                >
                                    Create User
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Edit Modal */}
            {isEditOpen && editingUser && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-lg shadow-lg w-full max-w-md p-6">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-lg font-bold">Edit Administrator: {editingUser.username}</h3>
                            <button onClick={() => setIsEditOpen(false)}><X size={20} /></button>
                        </div>
                        <form onSubmit={handleUpdate} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Status</label>
                                <select
                                    className="mt-1 block w-full rounded-md border-gray-300 border p-2"
                                    value={editingUser.is_active}
                                    onChange={e => setEditingUser({ ...editingUser, is_active: parseInt(e.target.value) })}
                                >
                                    <option value={1}>Active</option>
                                    <option value={0}>Inactive</option>
                                </select>
                            </div>

                            <div className="border-t pt-4 mt-4">
                                <h4 className="text-sm font-medium text-gray-900 mb-2 flex items-center gap-2">
                                    <RefreshCw size={14} /> Reset Password
                                </h4>
                                <input
                                    type="password"
                                    placeholder="Enter new password to reset"
                                    className="mt-1 block w-full rounded-md border-gray-300 border p-2"
                                    value={passwordReset}
                                    onChange={e => setPasswordReset(e.target.value)}
                                />
                                <p className="text-xs text-gray-500 mt-1">Leave blank to keep current password.</p>
                            </div>

                            <div className="flex justify-end gap-2 mt-6">
                                <button
                                    type="button"
                                    onClick={() => setIsEditOpen(false)}
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

export default AdminUsers;

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { Plus, Trash2, Edit, X, Users as UsersIcon } from 'lucide-react';
import UserWizard from '../components/UserWizard';
import UserGroupsModal from '../components/UserGroupsModal';

const UsersPage = () => {
    const queryClient = useQueryClient();
    const [isOpen, setIsOpen] = useState(false);
    const [newUser, setNewUser] = useState({ username: '', attribute: 'Cleartext-Password', op: ':=', value: '' });

    const [editingUser, setEditingUser] = useState(null);
    const [selectedUserForGroups, setSelectedUserForGroups] = useState(null);

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
                                        onClick={() => setSelectedUserForGroups(user)}
                                        className="text-purple-600 hover:text-purple-900"
                                        title="Manage Groups"
                                    >
                                        <UsersIcon size={18} />
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

            {/* Groups Management Modal */}
            {selectedUserForGroups && (
                <UserGroupsModal
                    user={selectedUserForGroups}
                    onClose={() => setSelectedUserForGroups(null)}
                />
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

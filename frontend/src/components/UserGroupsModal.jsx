import React, { useState, useEffect } from 'react';
import GroupsService from '../services/groups';
import { Trash2, Plus, X, Users } from 'lucide-react';
import { useToast } from '../context/ToastContext';

const UserGroupsModal = ({ user, onClose }) => {
    const { showToast } = useToast();
    const [userGroups, setUserGroups] = useState([]);
    const [availableGroups, setAvailableGroups] = useState([]);
    const [selectedGroup, setSelectedGroup] = useState('');
    const [loading, setLoading] = useState(true);

    const username = user?.username;

    useEffect(() => {
        if (username) {
            loadData();
        }
    }, [username]);

    const loadData = async () => {
        setLoading(true);
        try {
            const [myGroups, allGroups] = await Promise.all([
                GroupsService.getUserGroups(username),
                GroupsService.getAllGroups()
            ]);
            setUserGroups(myGroups);
            setAvailableGroups(allGroups);
            if (allGroups.length > 0) setSelectedGroup(allGroups[0]);
        } catch (error) {
            console.error("Error loading groups:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleAddGroup = async () => {
        if (!selectedGroup) return;
        try {
            await GroupsService.assignUserToGroup(username, selectedGroup);
            await loadData(); // Refresh list
        } catch (error) {
            showToast('Failed to add group', 'error');
        }
    };

    const handleRemoveGroup = async (groupname) => {
        if (!confirm(`Are you sure you want to remove ${username} from ${groupname}?`)) return;
        try {
            await GroupsService.removeUserFromGroup(username, groupname);
            await loadData(); // Refresh list
        } catch (error) {
            showToast('Failed to remove group', 'error');
        }
    };

    if (!user) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-lg overflow-hidden">
                <div className="flex justify-between items-center p-4 border-b bg-gray-50">
                    <h3 className="text-lg font-bold flex items-center gap-2 text-slate-800">
                        <Users className="text-blue-600" size={24} />
                        Group Management: <span className="text-blue-600 font-mono">{username}</span>
                    </h3>
                    <button onClick={onClose} className="text-gray-500 hover:text-red-500 transition-colors">
                        <X size={24} />
                    </button>
                </div>

                <div className="p-6 space-y-6">
                    {/* Add Group Section */}
                    <div className="bg-blue-50 p-4 rounded-lg border border-blue-100">
                        <label className="block text-sm font-semibold text-blue-900 mb-2">Assign New Group</label>
                        <div className="flex gap-2">
                            <select
                                className="flex-1 rounded-md border-gray-300 shadow-sm border p-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                                value={selectedGroup}
                                onChange={(e) => setSelectedGroup(e.target.value)}
                            >
                                {availableGroups.map(g => (
                                    <option key={g} value={g}>{g}</option>
                                ))}
                            </select>
                            <button
                                onClick={handleAddGroup}
                                className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 flex items-center gap-2 font-medium shadow-sm transition-all active:scale-95"
                            >
                                <Plus size={18} />
                                Assign
                            </button>
                        </div>
                    </div>

                    {/* Current Groups List */}
                    <div>
                        <h4 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">Current Memberships</h4>

                        {loading ? (
                            <div className="text-center py-4 text-gray-500 italic">Loading groups...</div>
                        ) : userGroups.length === 0 ? (
                            <div className="text-center py-8 bg-gray-50 rounded-lg border border-dashed border-gray-300 text-gray-500">
                                This user is not assigned to any group.
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {userGroups.map((group, idx) => (
                                    <div key={idx} className="flex justify-between items-center p-3 bg-white border border-gray-200 rounded-lg hover:shadow-sm transition-shadow">
                                        <div className="flex items-center gap-3">
                                            <div className="bg-green-100 p-2 rounded-full">
                                                <Users size={16} className="text-green-600" />
                                            </div>
                                            <div>
                                                <p className="font-semibold text-gray-800">{group.groupname}</p>
                                                <p className="text-xs text-gray-400">Priority: {group.priority || 1}</p>
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => handleRemoveGroup(group.groupname)}
                                            className="text-gray-400 hover:text-red-600 p-2 rounded-full hover:bg-red-50 transition-all"
                                            title="Remove from group"
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                <div className="p-4 border-t bg-gray-50 text-right">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-gray-600 hover:text-gray-800 font-medium"
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
};

export default UserGroupsModal;

import api from '../api';

const GroupsService = {
    // Get all groups for a specific user
    getUserGroups: async (username) => {
        const response = await api.get(`/groups/user/${username}`);
        return response.data;
    },

    // Assign a user to a group
    assignUserToGroup: async (username, groupname) => {
        const response = await api.post('/groups/assign', {
            username,
            groupname
        });
        return response.data;
    },

    // Remove a user from a group
    removeUserFromGroup: async (username, groupname) => {
        const response = await api.delete(`/groups/user/${username}/${groupname}`);
        return response.data;
    },

    // Get all defined groups (for the dropdown)
    getAllGroups: async () => {
        const response = await api.get('/groups/list');
        return response.data.map(g => g.groupname);
    },

    // Get members of a specific group
    getGroupMembers: async (groupname) => {
        const response = await api.get(`/groups/members/${groupname}`);
        return response.data;
    },

    // Get group by name (replies + checks)
    getGroupByName: async (groupname) => {
        const response = await api.get(`/groups/by-name/${groupname}`);
        return response.data;
    },

    // Rename a group
    renameGroup: async (oldGroupname, newGroupname) => {
        const response = await api.put(`/groups/rename?old_groupname=${oldGroupname}&new_groupname=${newGroupname}`);
        return response.data;
    },

    // Update group reply attribute
    updateGroupReply: async (id, data) => {
        const response = await api.put(`/groups/reply/${id}`, data);
        return response.data;
    },

    // Update group check attribute
    updateGroupCheck: async (id, data) => {
        const response = await api.put(`/groups/check/${id}`, data);
        return response.data;
    },

    // Delete group reply attribute
    deleteGroupReply: async (id) => {
        const response = await api.delete(`/groups/reply/${id}`);
        return response.data;
    },

    // Delete group check attribute
    deleteGroupCheck: async (id) => {
        const response = await api.delete(`/groups/check/${id}`);
        return response.data;
    },

    // Create group reply attribute
    createGroupReply: async (data) => {
        const response = await api.post('/groups/reply', data);
        return response.data;
    },

    // Create group check attribute
    createGroupCheck: async (data) => {
        const response = await api.post('/groups/check', data);
        return response.data;
    }
};

export default GroupsService;

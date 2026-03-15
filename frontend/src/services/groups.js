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
    }
};

export default GroupsService;

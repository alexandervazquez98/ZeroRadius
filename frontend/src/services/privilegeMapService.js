import api from '../api';

const PrivilegeMapService = {
    getAll: async (filters = {}) => {
        const params = new URLSearchParams();
        if (filters.username) params.append('username', filters.username);
        if (filters.nas_ip) params.append('nas_ip', filters.nas_ip);
        if (filters.is_active !== undefined) params.append('is_active', filters.is_active);
        if (filters.overdue_review) params.append('overdue_review', 'true');
        const query = params.toString();
        const response = await api.get(`/privilege-map${query ? '?' + query : ''}`);
        return response.data;
    },

    create: async (data) => {
        const response = await api.post('/privilege-map', data);
        return response.data;
    },

    update: async (id, data) => {
        const response = await api.put(`/privilege-map/${id}`, data);
        return response.data;
    },

    remove: async (id) => {
        const response = await api.delete(`/privilege-map/${id}`);
        return response.data;
    }
};

export default PrivilegeMapService;

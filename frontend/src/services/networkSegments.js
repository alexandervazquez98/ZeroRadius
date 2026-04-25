import api from '../api';

const NetworkSegmentsService = {
    getAll: () => api.get('/network-segments').then(r => r.data),
    getById: (id) => api.get(`/network-segments/${id}`).then(r => r.data),
    create: (data) => api.post('/network-segments', data).then(r => r.data),
    update: (id, data) => api.put(`/network-segments/${id}`, data).then(r => r.data),
    remove: (id) => api.delete(`/network-segments/${id}`).then(r => r.data),
};

export default NetworkSegmentsService;

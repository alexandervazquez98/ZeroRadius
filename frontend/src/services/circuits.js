import api from '../api';

const CircuitsService = {
    getAll: () => api.get('/circuits').then(r => r.data),
    getById: (id) => api.get(`/circuits/${id}`).then(r => r.data),
    create: (data) => api.post('/circuits', data).then(r => r.data),
    update: (id, data) => api.put(`/circuits/${id}`, data).then(r => r.data),
    remove: (id) => api.delete(`/circuits/${id}`).then(r => r.data),
};

export default CircuitsService;
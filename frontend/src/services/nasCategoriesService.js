import api from '../api';

/**
 * Service for NAS Category CRUD — nas-categories feature.
 * Maps to /api/nas-categories endpoints.
 */
const NasCategoriesService = {
  getAll: async () => {
    const r = await api.get('/nas-categories');
    return r.data;
  },

  create: async (data) => {
    const r = await api.post('/nas-categories', data);
    return r.data;
  },

  update: async (id, data) => {
    const r = await api.put(`/nas-categories/${id}`, data);
    return r.data;
  },

  remove: async (id) => {
    const r = await api.delete(`/nas-categories/${id}`);
    return r.data;
  },
};

export default NasCategoriesService;

import api from '../api';

const DeviceRegistryService = {
  getAll: async (params = {}) => {
    const r = await api.get('/device-registry', { params });
    return r.data;
  },

  getStats: async () => {
    const r = await api.get('/device-registry/stats');
    return r.data;
  },

  create: async (data) => {
    const r = await api.post('/device-registry', data);
    return r.data;
  },

  update: async (id, data) => {
    const r = await api.put(`/device-registry/${id}`, data);
    return r.data;
  },

  remove: async (id) => {
    const r = await api.delete(`/device-registry/${id}`);
    return r.data;
  },

  bulkCreate: async (payload) => {
    const r = await api.post('/device-registry/bulk', payload);
    return r.data;
  },

  bulkCsv: async (file, defaultCategoryId) => {
    const form = new FormData();
    form.append('file', file);
    const params = defaultCategoryId ? { default_category_id: defaultCategoryId } : {};
    const r = await api.post('/device-registry/bulk/csv', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params,
    });
    return r.data;
  },
};

export default DeviceRegistryService;

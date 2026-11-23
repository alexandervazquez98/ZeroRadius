import api from '../api';

const NasService = {
  bulkCsv: async (file, { dryRun = false, defaultCategoryId = null } = {}) => {
    const form = new FormData();
    form.append('file', file);
    const params = { dry_run: dryRun };
    if (defaultCategoryId) params.default_category_id = defaultCategoryId;
    // axios sets the multipart Content-Type (with boundary) for FormData.
    const r = await api.post('/nas/bulk/csv', form, { params });
    return r.data;
  },

  downloadBulkTemplate: async () => {
    const r = await api.get('/nas/bulk/template', { responseType: 'blob' });
    return r.data;
  },
};

export default NasService;

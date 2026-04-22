import api from '../api'

function normalizeError(error) {
  const fallback = {
    message: 'Unexpected error',
    fieldErrors: {},
  }

  if (!error?.response) return fallback

  const detail = error.response.data?.detail
  if (Array.isArray(detail)) {
    const fieldErrors = {}
    for (const item of detail) {
      const field = item?.loc?.[item.loc.length - 1]
      if (field) fieldErrors[field] = item?.msg || 'Invalid value'
    }
    return {
      message: 'Validation error',
      fieldErrors,
    }
  }

  if (typeof detail === 'string') {
    return { message: detail, fieldErrors: {} }
  }

  return fallback
}

const CIRService = {
  normalizeError,

  async listProfiles() {
    const response = await api.get('/cir/profiles')
    return response.data
  },

  async createProfile(payload) {
    const response = await api.post('/cir/profiles', payload)
    return response.data
  },

  async updateProfile(profileName, payload) {
    const response = await api.put(`/cir/profiles/${profileName}`, payload)
    return response.data
  },

  async deleteProfile(profileName) {
    const response = await api.delete(`/cir/profiles/${profileName}`)
    return response.data
  },

  async listAssignments(username) {
    const params = new URLSearchParams()
    if (username) params.append('username', username)
    const query = params.toString()
    const response = await api.get(`/cir/assignments${query ? `?${query}` : ''}`)
    return response.data
  },

  async createAssignment(payload) {
    const response = await api.post('/cir/assignments', payload)
    return response.data
  },

  async updateAssignment(id, payload) {
    const response = await api.put(`/cir/assignments/${id}`, payload)
    return response.data
  },

  async deleteAssignment(id) {
    const response = await api.delete(`/cir/assignments/${id}`)
    return response.data
  },

  async preview(payload) {
    const response = await api.post('/cir/preview', payload)
    return response.data
  },

  async listSegments() {
    const response = await api.get('/network-segments')
    return response.data
  },

  async listCategories() {
    const response = await api.get('/nas-categories')
    return response.data
  },
}

export default CIRService

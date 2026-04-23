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

const AccessPoliciesService = {
  normalizeError,

  // Assignments
  async listAssignments(filters = {}) {
    const params = new URLSearchParams()
    if (filters.username) params.append('username', filters.username)
    if (filters.nas_ip) params.append('nas_ip', filters.nas_ip)
    if (filters.is_active !== undefined) params.append('is_active', filters.is_active)
    if (filters.overdue_review) params.append('overdue_review', 'true')
    
    const query = params.toString()
    const response = await api.get(`/access-policies/assignments${query ? '?' + query : ''}`)
    return response.data
  },

  async createAssignment(payload) {
    const response = await api.post('/access-policies/assignments', payload)
    return response.data
  },

  async createAssignmentBulk(payload) {
    const response = await api.post('/access-policies/assignments/bulk', payload)
    return response.data
  },

  async updateAssignment(id, payload) {
    const response = await api.put(`/access-policies/assignments/${id}`, payload)
    return response.data
  },

  async deleteAssignment(id) {
    const response = await api.delete(`/access-policies/assignments/${id}`)
    return response.data
  },

  // Bandwidth Profiles
  async listProfiles() {
    const response = await api.get('/access-policies/bandwidth-profiles')
    return response.data
  },

  async createProfile(payload) {
    const response = await api.post('/access-policies/bandwidth-profiles', payload)
    return response.data
  },

  async updateProfile(profileName, payload) {
    const response = await api.put(`/access-policies/bandwidth-profiles/${profileName}`, payload)
    return response.data
  },

  async deleteProfile(profileName) {
    const response = await api.delete(`/access-policies/bandwidth-profiles/${profileName}`)
    return response.data
  },

  // Preview
  async preview(payload) {
    const response = await api.post('/access-policies/preview', payload)
    return response.data
  },

  // Helpers
  async listSegments() {
    const response = await api.get('/network-segments')
    return response.data
  },

  async listCategories() {
    const response = await api.get('/nas-categories')
    return response.data
  }
}

export default AccessPoliciesService

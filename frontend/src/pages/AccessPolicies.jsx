import React, { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Shield } from 'lucide-react'

import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import AccessPoliciesService from '../services/accessPolicies'
import AssignmentsTab from '../components/access-policies/AssignmentsTab'
import BandwidthProfilesTab from '../components/access-policies/BandwidthProfilesTab'
import PreviewTab from '../components/access-policies/PreviewTab'

export default function AccessPolicies() {
  const queryClient = useQueryClient()
  const { hasRole } = useAuth()
  const { showToast } = useToast()

  const canWrite = hasRole(['superadmin', 'admin'])

  const [activeTab, setActiveTab] = useState('assignments')
  const [selectedProfile, setSelectedProfile] = useState(null)
  const [profileErrors, setProfileErrors] = useState({})

  const profilesQuery = useQuery({ queryKey: ['access-policies', 'bandwidth-profiles'], queryFn: AccessPoliciesService.listProfiles, retry: false })

  const profiles = profilesQuery.data || []

  const invalidateProfiles = () => {
    queryClient.invalidateQueries({ queryKey: ['access-policies', 'bandwidth-profiles'] })
  }

  const saveProfileMutation = useMutation({
    mutationFn: async (payload) => {
      if (selectedProfile) {
        return AccessPoliciesService.updateProfile(selectedProfile.name, payload)
      }
      return AccessPoliciesService.createProfile(payload)
    },
    onSuccess: () => {
      setProfileErrors({})
      showToast('Bandwidth profile saved', 'success')
      invalidateProfiles()
    },
    onError: (error) => {
      const normalized = AccessPoliciesService.normalizeError(error)
      setProfileErrors(normalized.fieldErrors || {})
      showToast(normalized.message || 'Failed to save profile', 'error')
    },
  })

  const previewMutation = useMutation({
    mutationFn: AccessPoliciesService.preview,
    onError: (error) => {
      showToast(AccessPoliciesService.normalizeError(error).message, 'error')
    },
  })

  const selectedFromLatest = useMemo(() => {
    if (!selectedProfile) return null
    return profiles.find((item) => item.groupname === selectedProfile.groupname) || null
  }, [profiles, selectedProfile])

  return (
    <div className="space-y-6 pb-10 px-4">
      {/* Header handled partially in AssignmentsTab, but let's centralize the main title here */}
      <div className="py-4">
        <h2 className="text-3xl font-extrabold text-slate-800 tracking-tight flex items-center gap-3">
          <Shield className="text-indigo-600" size={32} />
          Access Policies
        </h2>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('assignments')}
            className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'assignments'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            Assignments
          </button>
          <button
            onClick={() => setActiveTab('profiles')}
            className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'profiles'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            Bandwidth Profiles
          </button>
          <button
            onClick={() => setActiveTab('preview')}
            className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'preview'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            Preview Resolution
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      <div className="pt-4">
        {activeTab === 'assignments' && <AssignmentsTab />}
        
        {activeTab === 'profiles' && (
          <BandwidthProfilesTab
            profiles={profiles}
            selectedProfile={selectedFromLatest}
            onSelectProfile={setSelectedProfile}
            onSave={(payload) => saveProfileMutation.mutate(payload)}
            canWrite={canWrite}
            fieldErrors={profileErrors}
          />
        )}

        {activeTab === 'preview' && (
          <PreviewTab
            isPending={previewMutation.isPending}
            onPreview={async (payload) => previewMutation.mutateAsync(payload)}
          />
        )}
      </div>
    </div>
  )
}

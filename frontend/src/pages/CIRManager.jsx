import React, { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Gauge } from 'lucide-react'

import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import CIRService from '../services/cirService'
import CIRProfileForm from '../components/cir/CIRProfileForm'
import CIRAssignmentTable from '../components/cir/CIRAssignmentTable'
import CIRPreviewPanel from '../components/cir/CIRPreviewPanel'

export default function CIRManager() {
  const queryClient = useQueryClient()
  const { hasRole } = useAuth()
  const { showToast } = useToast()

  const canWrite = hasRole(['superadmin', 'admin'])

  const [selectedProfile, setSelectedProfile] = useState(null)
  const [profileErrors, setProfileErrors] = useState({})

  const profilesQuery = useQuery({ queryKey: ['cir', 'profiles'], queryFn: CIRService.listProfiles, retry: false })
  const assignmentsQuery = useQuery({ queryKey: ['cir', 'assignments'], queryFn: () => CIRService.listAssignments(), retry: false })
  const segmentsQuery = useQuery({ queryKey: ['cir', 'segments'], queryFn: CIRService.listSegments, retry: false })
  const categoriesQuery = useQuery({ queryKey: ['cir', 'categories'], queryFn: CIRService.listCategories, retry: false })

  const hasError = profilesQuery.isError || assignmentsQuery.isError || segmentsQuery.isError || categoriesQuery.isError

  const profiles = profilesQuery.data || []
  const assignments = assignmentsQuery.data || []
  const segments = segmentsQuery.data || []
  const categories = categoriesQuery.data || []

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['cir'] })
  }

  const saveProfileMutation = useMutation({
    mutationFn: async (payload) => {
      if (selectedProfile) {
        return CIRService.updateProfile(selectedProfile.name, payload)
      }
      return CIRService.createProfile(payload)
    },
    onSuccess: () => {
      setProfileErrors({})
      showToast('CIR profile saved', 'success')
      invalidate()
    },
    onError: (error) => {
      const normalized = CIRService.normalizeError(error)
      setProfileErrors(normalized.fieldErrors || {})
      showToast(normalized.message || 'Failed to save profile', 'error')
    },
  })

  const saveAssignmentMutation = useMutation({
    mutationFn: CIRService.createAssignment,
    onSuccess: () => {
      showToast('CIR assignment saved', 'success')
      invalidate()
    },
    onError: (error) => {
      showToast(CIRService.normalizeError(error).message, 'error')
    },
  })

  const previewMutation = useMutation({
    mutationFn: CIRService.preview,
    onError: (error) => {
      showToast(CIRService.normalizeError(error).message, 'error')
    },
  })

  const onRetry = async () => {
    await Promise.all([
      profilesQuery.refetch(),
      assignmentsQuery.refetch(),
      segmentsQuery.refetch(),
      categoriesQuery.refetch(),
    ])
  }

  const selectedFromLatest = useMemo(() => {
    if (!selectedProfile) return null
    return profiles.find((item) => item.groupname === selectedProfile.groupname) || null
  }, [profiles, selectedProfile])

  return (
    <div className="space-y-6 pb-10 px-4">
      <div className="py-4">
        <h2 className="text-3xl font-extrabold text-slate-800 tracking-tight flex items-center gap-3">
          <Gauge className="text-indigo-600" size={32} />
          CIR Manager
        </h2>
        <p className="text-slate-500 mt-1 uppercase text-[10px] font-black tracking-widest opacity-60">
          Dedicated CIR profile, assignment and preview operations (v1)
        </p>
        <p className="text-xs text-slate-500 mt-2">
          v1 boundary: profile, assignment and preview only
        </p>
      </div>

      {hasError ? (
        <div className="bg-white rounded-2xl border border-rose-200 p-6 text-center space-y-3">
          <p className="font-black text-rose-700">Unable to load CIR data.</p>
          <p className="text-sm text-slate-500">Retry to recover without losing current changes.</p>
          <button
            onClick={onRetry}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-black hover:bg-indigo-700"
          >
            Retry
          </button>
        </div>
      ) : (
        <>
          {profiles.length === 0 && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              No CIR profiles yet
            </div>
          )}

          <CIRProfileForm
            profiles={profiles}
            selectedProfile={selectedFromLatest}
            onSelectProfile={setSelectedProfile}
            onSave={(payload) => saveProfileMutation.mutate(payload)}
            canWrite={canWrite}
            fieldErrors={profileErrors}
          />

          <CIRAssignmentTable
            assignments={assignments}
            profiles={profiles}
            segments={segments}
            categories={categories}
            canWrite={canWrite}
            onSave={(payload) => saveAssignmentMutation.mutate(payload)}
          />

          <CIRPreviewPanel
            isPending={previewMutation.isPending}
            onPreview={async (payload) => previewMutation.mutateAsync(payload)}
          />
        </>
      )}
    </div>
  )
}

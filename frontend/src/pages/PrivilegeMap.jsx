import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
    Shield, Plus, Trash2, Edit2, X, AlertTriangle, Clock,
    Server, User, CheckCircle, ChevronRight, Search, Tag, Map, HelpCircle
} from 'lucide-react';
import dayjs from 'dayjs';
import api from '../api';
import { useAuth } from '../context/AuthContext';
import PrivilegeMapService from '../services/privilegeMapService';
import GroupsService from '../services/groups';
import NasCategoriesService from '../services/nasCategoriesService';
import NetworkSegmentsService from '../services/networkSegments';

// ── Helpers ──────────────────────────────────────────────────────────────────

export const ReviewBadge = ({ reviewDate }) => {
    if (!reviewDate) return null;
    const daysUntil = dayjs(reviewDate).diff(dayjs(), 'day');
    if (daysUntil < 0)
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase bg-rose-100 text-rose-700 border border-rose-200">
                <AlertTriangle size={10} /> Overdue
            </span>
        );
    if (daysUntil <= 30)
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase bg-amber-100 text-amber-700 border border-amber-200">
                <Clock size={10} /> Review Soon
            </span>
        );
    return null;
};

const vendorBadge = (vendor) => {
    if (!vendor) return 'bg-slate-100 text-slate-500';
    const v = vendor.toLowerCase();
    if (v.includes('cisco'))    return 'bg-blue-100 text-blue-700';
    if (v.includes('cambium'))  return 'bg-emerald-100 text-emerald-700';
    if (v.includes('juniper'))  return 'bg-orange-100 text-orange-700';
    if (v.includes('mikrotik')) return 'bg-purple-100 text-purple-700';
    return 'bg-slate-100 text-slate-500';
};

const EMPTY_FORM = {
    username: '',
    mapping_mode: 'segment', // 'segment' | 'ip_range' | 'category' | 'ip'
    segment_id: null,
    target_start_ip: '',
    target_end_ip: '',
    nas_category_id: null,
    nas_ips: [],
    nas_ip: '',
    nas_vendor: '',
    radius_group: '',
    privilege_level: '',
    justification: '',
    approved_by: '',
    review_date: '',
    is_active: true,
};

// ── Page ─────────────────────────────────────────────────────────────────────

const PrivilegeMapPage = () => {
    const { user, hasRole } = useAuth();
    const canWrite  = hasRole(['superadmin', 'admin']);
    const canDelete = hasRole(['superadmin']);
    const queryClient = useQueryClient();

    // UI state
    const [selectedUser,  setSelectedUser]  = useState(null);
    const [userSearch,    setUserSearch]    = useState('');
    const [showModal,     setShowModal]     = useState(false);
    const [editItem,      setEditItem]      = useState(null);
    const [form,          setForm]          = useState(EMPTY_FORM);
    const [deleteTarget,  setDeleteTarget]  = useState(null);
    const [nasSearchTerm, setNasSearchTerm] = useState('');
    const [showAdvanced,  setShowAdvanced]  = useState(false);

    // ── Data ──────────────────────────────────────────────────────────────────

    const { data: allMappings = [], isLoading } = useQuery({
        queryKey: ['privilege-map'],
        queryFn: () => PrivilegeMapService.getAll({}),
    });

    const { data: usersList = [] } = useQuery({
        queryKey: ['users'],
        queryFn: () => api.get('/users').then(r => r.data),
    });

    const { data: nasList = [] } = useQuery({
        queryKey: ['nas'],
        queryFn: () => api.get('/nas').then(r => r.data),
    });

    const { data: groupsList = [] } = useQuery({
        queryKey: ['groups'],
        queryFn: GroupsService.getAllGroups,
    });

    const { data: categoriesList = [] } = useQuery({
        queryKey: ['nas-categories'],
        queryFn: NasCategoriesService.getAll,
    });

    const { data: segmentsList = [] } = useQuery({
        queryKey: ['network-segments'],
        queryFn: NetworkSegmentsService.getAll,
    });

    // ── Derived state ─────────────────────────────────────────────────────────

    const userGroups = useMemo(() => {
        const map = {};
        allMappings.forEach(m => {
            if (!map[m.username]) map[m.username] = { total: 0, active: 0, overdue: 0 };
            map[m.username].total++;
            if (m.is_active) map[m.username].active++;
            if (m.review_date && dayjs(m.review_date).isBefore(dayjs())) map[m.username].overdue++;
        });
        return map;
    }, [allMappings]);

    const filteredUsers = useMemo(() =>
        Object.keys(userGroups)
            .filter(u => u.toLowerCase().includes(userSearch.toLowerCase()))
            .sort(),
        [userGroups, userSearch]
    );

    const selectedMappings = useMemo(() =>
        selectedUser ? allMappings.filter(m => m.username === selectedUser) : [],
        [allMappings, selectedUser]
    );

    const totalOverdue = allMappings.filter(
        m => m.review_date && dayjs(m.review_date).isBefore(dayjs())
    ).length;

    const filteredNasList = nasList.filter(n => {
        const term = nasSearchTerm.toLowerCase();
        return n.nasname.toLowerCase().includes(term) ||
            (n.shortname && n.shortname.toLowerCase().includes(term));
    });

    // ── Mutations ─────────────────────────────────────────────────────────────

    const invalidate = () => queryClient.invalidateQueries({ queryKey: ['privilege-map'] });

    const createMutation = useMutation({
        mutationFn: PrivilegeMapService.create,
        onSuccess: () => { invalidate(); closeModal(); },
    });

    const createSingleMutation = useMutation({
        mutationFn: PrivilegeMapService.createCategory, // This endpoint handles all single creations
        onSuccess: () => { invalidate(); closeModal(); },
    });

    const updateMutation = useMutation({
        mutationFn: ({ id, data }) => PrivilegeMapService.update(id, data),
        onSuccess: () => { invalidate(); closeModal(); },
    });

    const deleteMutation = useMutation({
        mutationFn: PrivilegeMapService.remove,
        onSuccess: () => { invalidate(); setDeleteTarget(null); },
    });

    // ── Modal helpers ─────────────────────────────────────────────────────────

    const openCreate = (preselectedUser = null) => {
        setEditItem(null);
        setNasSearchTerm('');
        setShowAdvanced(false);
        setForm({ ...EMPTY_FORM, nas_ips: [], username: preselectedUser || '', approved_by: user?.sub || '' });
        setShowModal(true);
    };

    const openEdit = (item) => {
        setEditItem(item);
        setNasSearchTerm('');
        let mode = 'ip';
        if (item.segment_id) mode = item.target_start_ip ? 'ip_range' : 'segment';
        else if (item.nas_category_id) mode = 'category';
        
        setShowAdvanced(mode === 'category');
        
        setForm({
            username: item.username,
            mapping_mode: mode,
            segment_id: item.segment_id || null,
            target_start_ip: item.target_start_ip || '',
            target_end_ip: item.target_end_ip || '',
            nas_category_id: item.nas_category_id || null,
            nas_ip: item.nas_ip || '',
            nas_ips: [],
            nas_vendor: item.nas_vendor || '',
            radius_group: item.radius_group,
            privilege_level: item.privilege_level || '',
            justification: item.justification || '',
            approved_by: item.approved_by || '',
            review_date: item.review_date ? dayjs(item.review_date).format('YYYY-MM-DD') : '',
            is_active: item.is_active,
        });
        setShowModal(true);
    };

    const closeModal = () => { setShowModal(false); setEditItem(null); setNasSearchTerm(''); setForm(EMPTY_FORM); };

    const handleSubmit = (e) => {
        e.preventDefault();
        
        const payload = {
            username: form.username,
            radius_group: form.radius_group,
            privilege_level: form.privilege_level || undefined,
            justification: form.justification || undefined,
            approved_by: form.approved_by,
            review_date: form.review_date || null,
            is_active: form.is_active,
            nas_vendor: form.nas_vendor || undefined,
        };

        if (form.mapping_mode === 'segment') {
            payload.segment_id = form.segment_id;
        } else if (form.mapping_mode === 'ip_range') {
            payload.segment_id = form.segment_id;
            payload.target_start_ip = form.target_start_ip;
            payload.target_end_ip = form.target_end_ip || form.target_start_ip; // single IP if end is empty
        } else if (form.mapping_mode === 'category') {
            payload.nas_category_id = form.nas_category_id;
        } else if (form.mapping_mode === 'ip' && editItem) {
            payload.nas_ip = form.nas_ip;
        }

        if (editItem) {
            updateMutation.mutate({ id: editItem.id, data: payload });
        } else if (form.mapping_mode === 'ip') {
            // Bulk IP creation
            const bulkPayload = { ...payload, nas_ips: form.nas_ips };
            createMutation.mutate(bulkPayload);
        } else {
            // Single creation (Segment, Exception, Category)
            createSingleMutation.mutate(payload);
        }
    };

    const toggleNasSelection = (ip, vendor) => {
        setForm(f => {
            const isSelected = f.nas_ips.includes(ip);
            const newIps = isSelected ? f.nas_ips.filter(v => v !== ip) : [...f.nas_ips, ip];
            return {
                ...f,
                nas_ips: newIps,
                nas_vendor: newIps.length === 1 && !isSelected ? vendor : (newIps.length > 1 ? 'Multiple' : ''),
            };
        });
    };

    const toggleSelectAllFiltered = () => {
        setForm(f => {
            const allIps = filteredNasList.map(n => n.nasname);
            const allSel = allIps.every(ip => f.nas_ips.includes(ip));
            if (allSel) return { ...f, nas_ips: f.nas_ips.filter(ip => !allIps.includes(ip)) };
            return { ...f, nas_ips: Array.from(new Set([...f.nas_ips, ...allIps])), nas_vendor: 'Multiple' };
        });
    };

    const isUsernameLocked = editItem !== null || (selectedUser !== null && form.username === selectedUser);

    // ── Render ────────────────────────────────────────────────────────────────

    return (
        <div className="space-y-6 pb-10 px-4">

            {/* Header */}
            <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 py-4">
                <div>
                    <h2 className="text-3xl font-extrabold text-slate-800 tracking-tight flex items-center gap-3">
                        <Shield className="text-indigo-600" size={32} />
                        Access Policies
                    </h2>
                    <p className="text-slate-500 mt-1 uppercase text-[10px] font-black tracking-widest opacity-60">
                        Manage User Authorization per Segment and Device
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    {/* Global stats */}
                    <div className="flex items-center gap-4 px-5 py-2.5 bg-white border border-slate-200 rounded-2xl shadow-sm text-xs font-black text-slate-500 uppercase tracking-widest">
                        <span className="flex items-center gap-1.5">
                            <User size={13} className="text-indigo-400" />
                            {Object.keys(userGroups).length} Users
                        </span>
                        <span className="w-px h-4 bg-slate-200" />
                        <span className="flex items-center gap-1.5">
                            <Server size={13} className="text-indigo-400" />
                            {allMappings.length} Policies
                        </span>
                        {totalOverdue > 0 && (
                            <>
                                <span className="w-px h-4 bg-slate-200" />
                                <span className="flex items-center gap-1.5 text-rose-600">
                                    <AlertTriangle size={13} /> {totalOverdue} Overdue
                                </span>
                            </>
                        )}
                    </div>
                    {canWrite && (
                        <button
                            onClick={() => openCreate(selectedUser)}
                            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-xl font-black text-xs hover:bg-indigo-700 transition-colors shadow-sm"
                        >
                            <Plus size={16} /> Add Policy
                        </button>
                    )}
                </div>
            </div>

            {/* Split pane */}
            <div className="flex gap-6 items-start">

                {/* ── LEFT: User list ── */}
                <div className="w-72 flex-shrink-0 bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden sticky top-6">
                    {/* Search */}
                    <div className="p-3 border-b border-slate-100 bg-slate-50">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
                            <input
                                className="w-full pl-8 pr-3 py-2 text-sm bg-white border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500"
                                placeholder="Search users..."
                                value={userSearch}
                                onChange={e => setUserSearch(e.target.value)}
                            />
                        </div>
                    </div>

                    {/* List */}
                    <div className="overflow-y-auto max-h-[calc(100vh-260px)]">
                        {isLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                            </div>
                        ) : filteredUsers.length === 0 ? (
                            <div className="text-center py-10 text-slate-400">
                                <User size={32} className="mx-auto mb-2 opacity-40" />
                                <p className="text-xs font-bold">No users with policies</p>
                            </div>
                        ) : (
                            filteredUsers.map(username => {
                                const stats = userGroups[username];
                                const isSelected = selectedUser === username;
                                return (
                                    <button
                                        key={username}
                                        onClick={() => setSelectedUser(username)}
                                        className={`w-full flex items-center gap-3 px-4 py-3.5 text-left transition-all border-b border-slate-100 last:border-0 group ${
                                            isSelected
                                                ? 'bg-indigo-600 text-white'
                                                : 'hover:bg-slate-50 text-slate-700'
                                        }`}
                                    >
                                        {/* Avatar */}
                                        <div className={`w-9 h-9 rounded-xl flex items-center justify-center text-sm font-black flex-shrink-0 ${
                                            isSelected ? 'bg-white/20 text-white' : 'bg-indigo-100 text-indigo-700'
                                        }`}>
                                            {username[0].toUpperCase()}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className={`text-sm font-black truncate ${isSelected ? 'text-white' : 'text-slate-800'}`}>
                                                {username}
                                            </div>
                                            <div className={`text-[10px] mt-0.5 font-bold ${isSelected ? 'text-white/70' : 'text-slate-400'}`}>
                                                {stats.total} Policies · {stats.active} active
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-1.5 flex-shrink-0">
                                            {stats.overdue > 0 && (
                                                <span className={`text-[10px] px-1.5 py-0.5 rounded font-black ${
                                                    isSelected ? 'bg-white/20 text-white' : 'bg-rose-100 text-rose-700'
                                                }`}>
                                                    ⚠ {stats.overdue}
                                                </span>
                                            )}
                                            <ChevronRight size={14} className={isSelected ? 'text-white/60' : 'text-slate-300 group-hover:text-slate-500'} />
                                        </div>
                                    </button>
                                );
                            })
                        )}
                    </div>
                </div>

                {/* ── RIGHT: Detail panel ── */}
                <div className="flex-1 min-w-0">
                    {!selectedUser ? (
                        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 flex flex-col items-center justify-center py-28 gap-4 opacity-40">
                            <div className="p-6 bg-slate-100 rounded-3xl">
                                <Shield size={56} className="text-slate-400" />
                            </div>
                            <div className="text-center">
                                <p className="text-lg font-black text-slate-600">Select a user</p>
                                <p className="text-sm text-slate-400 mt-1">Choose a user from the left panel to view their Access Policies</p>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {/* User header bar */}
                            <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-5 flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="w-12 h-12 rounded-2xl bg-indigo-100 flex items-center justify-center text-xl font-black text-indigo-700">
                                        {selectedUser[0].toUpperCase()}
                                    </div>
                                    <div>
                                        <h3 className="text-xl font-black text-slate-800">{selectedUser}</h3>
                                        <p className="text-[10px] text-slate-400 font-black uppercase tracking-widest mt-0.5">
                                            {selectedMappings.length} Polic{selectedMappings.length !== 1 ? 'ies' : 'y'} &nbsp;·&nbsp;
                                            {selectedMappings.filter(m => m.is_active).length} active
                                        </p>
                                    </div>
                                </div>
                                {canWrite && (
                                    <button
                                        onClick={() => openCreate(selectedUser)}
                                        className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-xl font-black text-xs hover:bg-indigo-700 transition-colors shadow-sm"
                                    >
                                        <Plus size={15} /> Add Policy
                                    </button>
                                )}
                            </div>

                            {/* NAS mappings table */}
                            <div className="bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
                                {selectedMappings.length === 0 ? (
                                    <div className="text-center py-16 opacity-50">
                                        <Server size={40} className="mx-auto mb-3 text-slate-400" />
                                        <p className="font-black text-slate-500">No policies for this user</p>
                                        {canWrite && (
                                            <button
                                                onClick={() => openCreate(selectedUser)}
                                                className="mt-3 text-sm text-indigo-600 font-bold hover:underline"
                                            >
                                                + Create first policy
                                            </button>
                                        )}
                                    </div>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <table className="min-w-full divide-y divide-slate-100">
                                            <thead className="bg-slate-50">
                                                <tr>
                                                    <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Target</th>
                                                    <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Vendor</th>
                                                    <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">RADIUS Group</th>
                                                    <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Priv Level</th>
                                                    <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Review</th>
                                                    <th className="px-6 py-4 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Status</th>
                                                    {(canWrite || canDelete) && (
                                                        <th className="px-6 py-4 text-center text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] w-24">Actions</th>
                                                    )}
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-slate-100">
                                                {selectedMappings.map(item => (
                                                    <tr key={item.id} className="hover:bg-slate-50/70 transition-colors group">
                                                         <td className="px-6 py-4 whitespace-nowrap">
                                                             <div className="flex flex-col gap-1">
                                                                 {item.segment_id ? (
                                                                     <div className="flex items-center gap-2">
                                                                         <Map size={14} className="text-indigo-500 flex-shrink-0" />
                                                                         <span className="text-xs font-bold text-indigo-700 bg-indigo-50 border border-indigo-100 px-2 py-1 rounded">
                                                                             {item.segment_name || `Segment #${item.segment_id}`}
                                                                         </span>
                                                                     </div>
                                                                 ) : item.nas_category_id ? (
                                                                     <div className="flex items-center gap-2">
                                                                         <Tag size={13} className="text-violet-400 flex-shrink-0" />
                                                                         <span className="text-xs font-bold text-violet-700 bg-violet-50 border border-violet-100 px-2 py-1 rounded">
                                                                             {item.nas_category_name || `Category #${item.nas_category_id}`}
                                                                         </span>
                                                                     </div>
                                                                 ) : (
                                                                     <div className="flex items-center gap-2">
                                                                         <Server size={14} className="text-slate-400 flex-shrink-0" />
                                                                         <span className="text-xs font-mono font-bold text-slate-700 bg-slate-100 px-2 py-1 rounded">
                                                                             {item.nas_ip}
                                                                         </span>
                                                                     </div>
                                                                 )}
                                                                 
                                                                 {/* Sub-target for Exceptions */}
                                                                 {item.target_start_ip && (
                                                                     <div className="flex items-center gap-1 pl-6">
                                                                         <span className="text-[10px] text-slate-400 font-mono">
                                                                             {item.target_start_ip} {item.target_end_ip && item.target_end_ip !== item.target_start_ip ? `- ${item.target_end_ip}` : ''}
                                                                         </span>
                                                                     </div>
                                                                 )}
                                                             </div>
                                                             {item.nas_identifier && (
                                                                 <div className="text-[10px] text-slate-400 mt-0.5 pl-5">{item.nas_identifier}</div>
                                                             )}
                                                         </td>
                                                        <td className="px-6 py-4 whitespace-nowrap">
                                                            {item.nas_vendor ? (
                                                                <span className={`text-[10px] font-black uppercase px-2 py-1 rounded-full ${vendorBadge(item.nas_vendor)}`}>
                                                                    {item.nas_vendor}
                                                                </span>
                                                            ) : <span className="text-slate-300 italic text-sm">—</span>}
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap">
                                                            <span className="text-xs font-bold bg-indigo-50 text-indigo-700 px-2 py-1 rounded-full">
                                                                {item.radius_group}
                                                            </span>
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-slate-600">
                                                            {item.privilege_level || <span className="text-slate-300 italic">—</span>}
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap">
                                                            <div className="flex flex-col gap-1">
                                                                <span className="text-sm text-slate-600">
                                                                    {item.review_date
                                                                        ? dayjs(item.review_date).format('DD MMM YYYY')
                                                                        : <span className="text-slate-300 italic">—</span>}
                                                                </span>
                                                                <ReviewBadge reviewDate={item.review_date} />
                                                            </div>
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap">
                                                            {item.is_active ? (
                                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase bg-emerald-50 text-emerald-700 border border-emerald-100">
                                                                    <CheckCircle size={10} /> Active
                                                                </span>
                                                            ) : (
                                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase bg-slate-100 text-slate-500 border border-slate-200">
                                                                    Inactive
                                                                </span>
                                                            )}
                                                        </td>
                                                        {(canWrite || canDelete) && (
                                                            <td className="px-6 py-4 text-center">
                                                                <div className="flex items-center justify-center gap-2">
                                                                    {canWrite && (
                                                                        <button
                                                                            onClick={() => openEdit(item)}
                                                                            className="p-2 text-slate-400 hover:text-indigo-600 bg-slate-100 hover:bg-indigo-50 rounded-lg transition-colors"
                                                                            title="Edit"
                                                                        >
                                                                            <Edit2 size={14} />
                                                                        </button>
                                                                    )}
                                                                    {canDelete && (
                                                                        <button
                                                                            onClick={() => {
                                                                                if (window.confirm('Delete this policy?')) {
                                                                                    deleteMutation.mutate(item.id);
                                                                                }
                                                                            }}
                                                                            className="p-2 text-slate-400 hover:text-rose-600 bg-slate-100 hover:bg-rose-50 rounded-lg transition-colors"
                                                                            title="Delete"
                                                                        >
                                                                            <Trash2 size={14} />
                                                                        </button>
                                                                    )}
                                                                </div>
                                                            </td>
                                                        )}
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* ── Modal: Create / Edit ── */}
            {showModal && (
                <div className="fixed inset-0 bg-slate-900/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
                    <div className="bg-white rounded-3xl w-full max-w-3xl shadow-2xl overflow-hidden">
                        <div className="p-8 bg-slate-50 border-b flex justify-between items-center">
                            <h3 className="text-xl font-black text-slate-800">
                                {editItem
                                    ? 'Edit Policy'
                                    : `New Policy${form.username ? ` for ${form.username}` : ''}`}
                            </h3>
                            <button onClick={closeModal} className="p-3 hover:bg-slate-200 rounded-full transition-colors text-slate-500">
                                <X size={20} />
                            </button>
                        </div>
                        <form onSubmit={handleSubmit} className="p-8 space-y-5 max-h-[75vh] overflow-y-auto">
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                                {/* Left: Target Selection */}
                                <div className="space-y-5">
                                    <div>
                                        <label htmlFor="pm-username" className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Username *</label>
                                        <select
                                            id="pm-username"
                                            required
                                            className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm bg-white disabled:bg-slate-50 disabled:text-slate-500 disabled:cursor-not-allowed"
                                            value={form.username}
                                            onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                                            disabled={isUsernameLocked}
                                        >
                                            <option value="">-- Select User --</option>
                                            {usersList.map(u => (
                                                <option key={u.id || u.username} value={u.username}>{u.username}</option>
                                            ))}
                                        </select>
                                    </div>

                                    <div>
                                        <label className="flex items-center justify-between text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">
                                            {editItem ? (
                                                <span>Target</span>
                                            ) : (
                                                <span>Target Mode *</span>
                                            )}
                                        </label>

                                        {!editItem && (
                                            <div className="grid grid-cols-2 gap-2 mb-3">
                                                <button
                                                    type="button"
                                                    onClick={() => setForm(f => ({ ...f, mapping_mode: 'segment', nas_category_id: null, nas_ips: [] }))}
                                                    className={`px-3 py-2 border rounded-xl text-xs font-bold transition-colors ${
                                                        form.mapping_mode === 'segment' ? 'bg-indigo-50 border-indigo-200 text-indigo-700 shadow-sm' : 'bg-white text-slate-600 hover:bg-slate-50'
                                                    }`}
                                                >
                                                    Network Segment
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setForm(f => ({ ...f, mapping_mode: 'ip_range', nas_category_id: null, nas_ips: [] }))}
                                                    className={`px-3 py-2 border rounded-xl text-xs font-bold transition-colors ${
                                                        form.mapping_mode === 'ip_range' ? 'bg-indigo-50 border-indigo-200 text-indigo-700 shadow-sm' : 'bg-white text-slate-600 hover:bg-slate-50'
                                                    }`}
                                                >
                                                    IP or Range (Exception)
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setForm(f => ({ ...f, mapping_mode: 'ip', nas_category_id: null }))}
                                                    className={`col-span-2 px-3 py-2 border rounded-xl text-xs font-bold transition-colors ${
                                                        form.mapping_mode === 'ip' ? 'bg-indigo-50 border-indigo-200 text-indigo-700 shadow-sm' : 'bg-white text-slate-600 hover:bg-slate-50'
                                                    }`}
                                                >
                                                    Specific NAS / IPs (Legacy)
                                                </button>
                                            </div>
                                        )}

                                        {/* Target Content */}
                                        {editItem ? (
                                            /* Edit mode read-only target display */
                                            form.mapping_mode === 'segment' || form.mapping_mode === 'ip_range' ? (
                                                <div className="p-4 border border-slate-200 rounded-xl bg-slate-50">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <Map size={14} className="text-indigo-500" />
                                                        <span className="text-sm font-bold text-slate-700">
                                                            {segmentsList.find(s => s.id === form.segment_id)?.name || `Segment #${form.segment_id}`}
                                                        </span>
                                                    </div>
                                                    {form.mapping_mode === 'ip_range' && (
                                                        <div className="text-xs font-mono text-slate-500 pl-6">
                                                            Exception: {form.target_start_ip} {form.target_end_ip && form.target_end_ip !== form.target_start_ip ? `- ${form.target_end_ip}` : ''}
                                                        </div>
                                                    )}
                                                </div>
                                            ) : form.mapping_mode === 'category' ? (
                                                <div className="flex items-center gap-2 px-4 py-3 border border-slate-200 rounded-xl bg-slate-50">
                                                    <Tag size={13} className="text-violet-400" />
                                                    <span className="text-sm font-bold text-violet-700">
                                                        {categoriesList.find(c => c.id === form.nas_category_id)?.name || `Category #${form.nas_category_id}`}
                                                    </span>
                                                </div>
                                            ) : (
                                                <input
                                                    className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none text-sm font-mono bg-slate-50 text-slate-500 cursor-not-allowed"
                                                    value={form.nas_ip}
                                                    disabled
                                                />
                                            )
                                        ) : (
                                            /* Create Mode Inputs */
                                            <div className="space-y-3">
                                                {(form.mapping_mode === 'segment' || form.mapping_mode === 'ip_range') && (
                                                    <select
                                                        required
                                                        className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm bg-white"
                                                        value={form.segment_id || ''}
                                                        onChange={e => setForm(f => ({ ...f, segment_id: e.target.value ? parseInt(e.target.value, 10) : null }))}
                                                    >
                                                        <option value="">-- Select Parent Segment --</option>
                                                        {segmentsList.map(s => (
                                                            <option key={s.id} value={s.id}>{s.name} ({s.cidr})</option>
                                                        ))}
                                                    </select>
                                                )}

                                                {form.mapping_mode === 'ip_range' && (
                                                    <div className="grid grid-cols-2 gap-2">
                                                        <div>
                                                            <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Start IP / Single IP</label>
                                                            <input
                                                                required
                                                                placeholder="e.g. 10.0.1.50"
                                                                className="w-full px-3 py-2 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm font-mono"
                                                                value={form.target_start_ip}
                                                                onChange={e => setForm(f => ({ ...f, target_start_ip: e.target.value }))}
                                                            />
                                                        </div>
                                                        <div>
                                                            <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">End IP (optional)</label>
                                                            <input
                                                                placeholder="e.g. 10.0.1.60"
                                                                className="w-full px-3 py-2 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm font-mono"
                                                                value={form.target_end_ip}
                                                                onChange={e => setForm(f => ({ ...f, target_end_ip: e.target.value }))}
                                                            />
                                                        </div>
                                                    </div>
                                                )}

                                                {form.mapping_mode === 'ip' && (
                                                    <div className="border border-slate-200 rounded-xl overflow-hidden bg-white flex flex-col h-64">
                                                        <div className="p-2 border-b border-slate-100 bg-slate-50">
                                                            <input
                                                                type="text"
                                                                placeholder="Search by IP or Shortname..."
                                                                className="w-full px-3 py-1.5 text-sm bg-white border border-slate-200 rounded-lg outline-none focus:border-indigo-500"
                                                                value={nasSearchTerm}
                                                                onChange={e => setNasSearchTerm(e.target.value)}
                                                            />
                                                        </div>
                                                        {filteredNasList.length > 0 && (
                                                            <div className="px-3 py-2 border-b border-slate-100 bg-slate-50 flex justify-between items-center">
                                                                <span className="text-xs text-slate-500 font-medium">Selected: {form.nas_ips.length}</span>
                                                                <button type="button" onClick={toggleSelectAllFiltered} className="text-xs font-bold text-indigo-600 hover:text-indigo-700">
                                                                    Toggle All Filtered
                                                                </button>
                                                            </div>
                                                        )}
                                                        <div className="flex-1 overflow-y-auto p-2 space-y-1">
                                                            {filteredNasList.map(n => (
                                                                <label key={n.nasname} className="flex items-center gap-3 p-2 hover:bg-slate-50 rounded-lg cursor-pointer">
                                                                    <input
                                                                        type="checkbox"
                                                                        checked={form.nas_ips.includes(n.nasname)}
                                                                        onChange={() => toggleNasSelection(n.nasname, n.type)}
                                                                        className="w-4 h-4 rounded accent-indigo-600"
                                                                    />
                                                                    <div className="flex flex-col">
                                                                        <span className="text-sm font-mono font-bold text-slate-700">{n.nasname}</span>
                                                                        <span className="text-xs text-slate-500">{n.shortname || 'Unnamed'}</span>
                                                                    </div>
                                                                </label>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                                
                                                {form.mapping_mode === 'category' && (
                                                    <select
                                                        required
                                                        className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-violet-500 text-sm bg-white"
                                                        value={form.nas_category_id || ''}
                                                        onChange={e => setForm(f => ({ ...f, nas_category_id: e.target.value ? parseInt(e.target.value, 10) : null }))}
                                                    >
                                                        <option value="">-- Select Category --</option>
                                                        {categoriesList.map(c => (
                                                            <option key={c.id} value={c.id}>{c.name}</option>
                                                        ))}
                                                    </select>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                    {!editItem && (
                                        <div className="pt-2">
                                            <button 
                                                type="button" 
                                                onClick={() => setShowAdvanced(!showAdvanced)}
                                                className="text-xs font-bold text-slate-400 hover:text-slate-600 flex items-center gap-1"
                                            >
                                                <HelpCircle size={12} /> 
                                                {showAdvanced ? 'Hide advanced targets' : 'Advanced / Legacy Compatibility'}
                                            </button>
                                            
                                            {showAdvanced && form.mapping_mode !== 'category' && (
                                                <div className="mt-3 p-3 border border-dashed border-slate-300 rounded-xl bg-slate-50">
                                                    <p className="text-xs text-slate-500 mb-2">Targeting by Legacy Categories</p>
                                                    <button
                                                        type="button"
                                                        onClick={() => setForm(f => ({ ...f, mapping_mode: 'category', nas_ips: [] }))}
                                                        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-xs font-bold bg-white text-slate-600 hover:bg-slate-100"
                                                    >
                                                        Switch to Category Target
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>

                                {/* Right: Policy Rules & Metadata */}
                                <div className="space-y-4">
                                    <div>
                                        <label htmlFor="pm-radius-group" className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">RADIUS Group (Policy) *</label>
                                        <select
                                            id="pm-radius-group"
                                            required
                                            className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm bg-white"
                                            value={form.radius_group}
                                            onChange={e => setForm(f => ({ ...f, radius_group: e.target.value }))}
                                        >
                                            <option value="">-- Select Policy Group --</option>
                                            {groupsList.map(g => <option key={g} value={g}>{g}</option>)}
                                        </select>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Privilege Level</label>
                                            <input
                                                className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                                                value={form.privilege_level}
                                                onChange={e => setForm(f => ({ ...f, privilege_level: e.target.value }))}
                                                placeholder="e.g. 15"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Review Date</label>
                                            <input
                                                type="date"
                                                className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                                                value={form.review_date}
                                                onChange={e => setForm(f => ({ ...f, review_date: e.target.value }))}
                                            />
                                        </div>
                                    </div>

                                    <div>
                                        <label htmlFor="pm-approved-by" className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Approved By *</label>
                                        <input
                                            id="pm-approved-by"
                                            required
                                            className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                                            value={form.approved_by}
                                            onChange={e => setForm(f => ({ ...f, approved_by: e.target.value }))}
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1.5">Justification</label>
                                        <textarea
                                            className="w-full px-4 py-2.5 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 text-sm resize-none"
                                            rows={2}
                                            value={form.justification}
                                            onChange={e => setForm(f => ({ ...f, justification: e.target.value }))}
                                            placeholder="Reason for this access policy..."
                                        />
                                    </div>

                                    <div className="flex items-center justify-between pt-2">
                                        <div className="flex items-center gap-3">
                                            <input
                                                type="checkbox"
                                                id="is_active"
                                                checked={form.is_active}
                                                onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))}
                                                className="w-4 h-4 rounded accent-indigo-600"
                                            />
                                            <label htmlFor="is_active" className="text-sm font-bold text-slate-700">Policy is Active</label>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div className="flex justify-end gap-3 pt-6 border-t border-slate-100">
                                <button
                                    type="button"
                                    onClick={closeModal}
                                    className="px-6 py-2.5 border border-slate-200 rounded-xl text-sm font-bold text-slate-600 hover:bg-slate-50 transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={createMutation.isPending || updateMutation.isPending || createSingleMutation.isPending}
                                    className="px-6 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-black hover:bg-indigo-700 transition-colors disabled:opacity-50"
                                >
                                    {createMutation.isPending || updateMutation.isPending || createSingleMutation.isPending ? 'Saving...' : 'Save Policy'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default PrivilegeMapPage;
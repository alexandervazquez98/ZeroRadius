import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { Plus, Trash2, Layers, Shield, ArrowRight, X, Search, Edit2, Filter, FileText, Users as UsersIcon } from 'lucide-react';
import GroupManager from '../components/GroupManager'; // Reusing the editor logic if needed
import GroupsService from '../services/groups';

// --- SUB-COMPONENT: ATTRIBUTE SELECTOR (Reused from previous code, or imported) ---
// Ideally we should move AttributeSelector to a separate file, but for now copying it to keep it self-contained in this overhaul.
// --- SUB-COMPONENT: ATTRIBUTE SELECTOR ---
const AttributeSelector = ({ dictionary, onSelect, submitLabel = "Add" }) => {
    const queryClient = useQueryClient();
    const [selectedDict, setSelectedDict] = useState('');
    const [selectedAttr, setSelectedAttr] = useState('');
    const [op, setOp] = useState(':=');
    const [val, setVal] = useState('');
    const [isRenaming, setIsRenaming] = useState(false);
    const [newName, setNewName] = useState('');

    const renameMutation = useMutation({
        mutationFn: ({ oldName, newName }) => api.post(`/dictionary/rename?old_name=${oldName}&new_name=${newName}`),
        onSuccess: () => {
            queryClient.invalidateQueries(['dictionary']);
            setSelectedDict(newName);
            setIsRenaming(false);
        }
    });

    const handleRename = () => {
        if (selectedDict && newName && newName !== selectedDict) {
            renameMutation.mutate({ oldName: selectedDict, newName });
        }
    };

    const sources = useMemo(() => {
        if (!dictionary) return [];
        const sSet = new Set(dictionary.map(d => d.dictionary || 'Unknown'));
        return Array.from(sSet).sort();
    }, [dictionary]);

    const filteredAttributes = useMemo(() => {
        if (!dictionary || !selectedDict) return [];
        return dictionary.filter(d => d.dictionary === selectedDict);
    }, [dictionary, selectedDict]);

    const handleAdd = () => {
        if (selectedAttr && val) {
            onSelect({ attribute: selectedAttr, op, value: val });
            setVal('');
        }
    };

    if (!dictionary || dictionary.length === 0) {
        return <div className="p-4 bg-gray-50 border rounded text-xs text-gray-400 italic">Loading attributes...</div>;
    }

    return (
        <div className="bg-white p-4 rounded border mb-4 flex flex-col gap-3 shadow-sm">
            <div className="flex gap-2 items-center">
                <label className="text-xs font-bold text-gray-500 w-24 uppercase">Dictionary</label>
                {!isRenaming ? (
                    <div className="flex-1 flex gap-2">
                        <select
                            className="flex-1 border rounded p-2 text-sm"
                            value={selectedDict}
                            onChange={e => { setSelectedDict(e.target.value); setSelectedAttr(''); setNewName(e.target.value); }}
                        >
                            <option value="">-- Select Source ({sources.length}) --</option>
                            {sources.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                        {selectedDict && (
                            <button
                                onClick={() => setIsRenaming(true)}
                                className="p-2 text-gray-400 hover:text-indigo-600 border rounded"
                                title="Rename File"
                            >
                                <Edit2 size={14} />
                            </button>
                        )}
                    </div>
                ) : (
                    <div className="flex-1 flex gap-2 animate-fadeIn">
                        <input
                            className="flex-1 border rounded p-2 text-sm focus:ring-1 focus:ring-indigo-500"
                            value={newName}
                            onChange={e => setNewName(e.target.value)}
                        />
                        <button onClick={handleRename} className="bg-green-600 text-white p-2 rounded"><ArrowRight size={14} /></button>
                        <button onClick={() => setIsRenaming(false)} className="bg-gray-200 text-gray-600 p-2 rounded"><X size={14} /></button>
                    </div>
                )}
            </div>

            <div className="flex gap-2 items-center">
                <label className="text-xs font-bold text-gray-500 w-24 uppercase">Attribute</label>
                <select
                    className="flex-1 border rounded p-2 text-sm"
                    value={selectedAttr}
                    onChange={e => setSelectedAttr(e.target.value)}
                    disabled={!selectedDict}
                >
                    <option value="">-- Select Attribute ({filteredAttributes.length}) --</option>
                    {filteredAttributes.map(a => (
                        <option key={a.name} value={a.name}>
                            {a.name} ({a.type})
                        </option>
                    ))}
                </select>
            </div>
            <div className="flex gap-2 items-end">
                <div className="w-20">
                    <label className="block text-xs font-bold text-gray-500 mb-1 uppercase">Op</label>
                    <select className="w-full border rounded p-2 text-sm" value={op} onChange={e => setOp(e.target.value)}>
                        <option value=":=">:=</option>
                        <option value="=">=</option>
                        <option value="==">==</option>
                        <option value="+=">+=</option>
                        <option value="=~">=~</option>
                    </select>
                </div>
                <div className="flex-1">
                    <label className="block text-xs font-bold text-gray-500 mb-1 uppercase">Value</label>
                    <input className="w-full border rounded p-2 text-sm" placeholder="Value..." value={val} onChange={e => setVal(e.target.value)} />
                </div>
                <button onClick={handleAdd} disabled={!selectedAttr || !val} className="bg-indigo-600 text-white rounded px-4 py-2 hover:bg-indigo-700 disabled:opacity-50 font-medium h-[38px]">{submitLabel}</button>
            </div>
        </div>
    );
};

const PoliciesPage = () => {
    const queryClient = useQueryClient();
    const [viewMode, setViewMode] = useState('list'); // 'list' or 'edit'
    const [selectedPolicy, setSelectedPolicy] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

    // --- CREATE WIZARD STATE ---
    const [wizardData, setWizardData] = useState({ name: '', targetType: 'none', targetValue: '' });

    // --- DATA ---
    const { data: groupsList } = useQuery({ queryKey: ['groups', 'list'], queryFn: () => api.get('/groups/list').then(r => r.data) });
    const { data: allGroupChecks } = useQuery({ queryKey: ['groups', 'check'], queryFn: () => api.get('/groups/check').then(r => r.data) });
    const { data: allGroupReplies } = useQuery({ queryKey: ['groups', 'reply'], queryFn: () => api.get('/groups/reply').then(r => r.data) });
    const { data: nasList } = useQuery({ queryKey: ['nas'], queryFn: () => api.get('/nas').then(r => r.data) });
    const { data: dictionaryAttributes } = useQuery({ queryKey: ['dictionary', 'attributes'], queryFn: () => api.get('/dictionary/attributes').then(r => r.data) });

    // --- ACTIVE POLICY SPECIFIC DATA ---
    const { data: activeChecksQuery, isLoading: isLoadingActiveChecks } = useQuery({
        queryKey: ['groups', 'check', selectedPolicy],
        queryFn: () => api.get(`/groups/check?groupname=${selectedPolicy}`).then(r => r.data),
        enabled: !!selectedPolicy && viewMode === 'edit',
    });
    const { data: activeRepliesQuery, isLoading: isLoadingActiveReplies } = useQuery({
        queryKey: ['groups', 'reply', selectedPolicy],
        queryFn: () => api.get(`/groups/reply?groupname=${selectedPolicy}`).then(r => r.data),
        enabled: !!selectedPolicy && viewMode === 'edit',
    });

    const activeChecks = useMemo(() => activeChecksQuery || [], [activeChecksQuery]);
    const activeReplies = useMemo(() => activeRepliesQuery || [], [activeRepliesQuery]);

    // --- GROUP MEMBERS DATA ---
    const { data: groupMembers, isLoading: isLoadingMembers } = useQuery({
        queryKey: ['groups', 'members', selectedPolicy],
        queryFn: () => GroupsService.getGroupMembers(selectedPolicy),
        enabled: !!selectedPolicy && viewMode === 'edit',
    });

    // --- AGGREGATION FOR TABLE ---
    const policiesTable = useMemo(() => {
        if (!groupsList) return [];
        return groupsList.map(g => {
            const checks = allGroupChecks?.filter(c => c.groupname === g.groupname) || [];
            const replies = allGroupReplies?.filter(r => r.groupname === g.groupname) || [];

            // Find Scopes
            const nasCheck = checks.find(c => c.attribute === 'NAS-Identifier');
            const groupCheck = checks.find(c => c.attribute === 'FreeRADIUS-Client-Shortname');
            const descCheck = checks.find(c => c.attribute === 'Description');

            let scopeLabel = 'Global / Manual';
            if (nasCheck && groupCheck) {
                scopeLabel = `Hybrid: ${nasCheck.value} @ ${groupCheck.value}`;
            } else if (nasCheck) {
                scopeLabel = `NAS: ${nasCheck.value || 'Not set'}`;
            } else if (groupCheck) {
                scopeLabel = `Group: ${groupCheck.value || 'Not set'}`;
            }

            return {
                name: g.groupname,
                description: descCheck?.value || '',
                checkCount: checks.filter(c => c.attribute !== 'Description').length,
                replyCount: replies.length,
                scope: scopeLabel,
            };
        }).filter(p =>
            p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            p.description.toLowerCase().includes(searchQuery.toLowerCase())
        );
    }, [groupsList, allGroupChecks, allGroupReplies, searchQuery]);

    // --- MUTATIONS ---
    const invalidatePolicy = () => {
        queryClient.invalidateQueries(['groups']);
        queryClient.invalidateQueries(['groups', 'check', selectedPolicy]);
        queryClient.invalidateQueries(['groups', 'reply', selectedPolicy]);
    };

    const createCheckMutation = useMutation({ mutationFn: (item) => api.post('/groups/check', item), onSuccess: invalidatePolicy });
    const createReplyMutation = useMutation({ mutationFn: (item) => api.post('/groups/reply', item), onSuccess: invalidatePolicy });
    const deleteCheckMutation = useMutation({ mutationFn: (id) => api.delete(`/groups/check/${id}`), onSuccess: invalidatePolicy });
    const deleteReplyMutation = useMutation({ mutationFn: (id) => api.delete(`/groups/reply/${id}`), onSuccess: invalidatePolicy });
    const deletePolicyMutation = useMutation({
        mutationFn: (groupname) => api.delete(`/groups/policy?groupname=${groupname}`),
        onSuccess: () => {
            queryClient.invalidateQueries(['groups']);
            setViewMode('list');
            setSelectedPolicy(null);
        }
    });

    // --- HANDLERS ---
    const handleCreateSubmit = (e) => {
        e.preventDefault();
        if (!wizardData.name) return;

        // Optimistic handling
        // We create a check if scope is defined, else create a dummy check to persist
        // Then switch to edit mode
        const newName = wizardData.name.replace(/\s+/g, '-');

        if (wizardData.targetType === 'nas' && wizardData.targetValue) {
            createCheckMutation.mutate({ groupname: newName, attribute: 'NAS-Identifier', op: '==', value: wizardData.targetValue });
        } else if (wizardData.targetType === 'shortname' && wizardData.targetValue) {
            createCheckMutation.mutate({ groupname: newName, attribute: 'FreeRADIUS-Client-Shortname', op: '==', value: wizardData.targetValue });
        } else {
            createCheckMutation.mutate({ groupname: newName, attribute: 'Description', op: ':=', value: 'New Policy' });
        }

        setIsCreateModalOpen(false);
        setWizardData({ name: '', targetType: 'none', targetValue: '' });

        // Wait a bit or use OnSuccess to switch, but for UX let's just close modal. 
        // User will see it in table.
    };

    const deleteItem = (id, type) => {
        if (type === 'check') deleteCheckMutation.mutate(id);
        if (type === 'reply') deleteReplyMutation.mutate(id);
    }

    const handleScopeChange = (type, value) => {
        // 1. Identify existing of same type
        const attr = type === 'nas' ? 'NAS-Identifier' : 'FreeRADIUS-Client-Shortname';
        const existing = activeChecks.filter(c => c.attribute === attr);

        // 2. Clear same type
        const deletions = existing.map(c => api.delete(`/groups/check/${c.id}`));

        Promise.all(deletions).finally(() => {
            // 3. Create new if value provided
            if (value !== null && value !== undefined) {
                api.post('/groups/check', { groupname: selectedPolicy, attribute: attr, op: '==', value: value })
                    .then(invalidatePolicy);
            } else {
                invalidatePolicy();
            }
        });
    }

    const handleDescriptionSave = (val) => {
        const existing = activeChecks.filter(c => c.attribute === 'Description');
        const deletions = existing.map(c => api.delete(`/groups/check/${c.id}`));
        Promise.all(deletions).finally(() => {
            api.post('/groups/check', { groupname: selectedPolicy, attribute: 'Description', op: ':=', value: val })
                .then(invalidatePolicy);
        });
    }

    // --- RENDER: LIST VIEW ---
    if (viewMode === 'list') {
        return (
            <div className="space-y-6">
                {/* Header */}
                <div className="flex justify-between items-center bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                    <div>
                        <h2 className="text-2xl font-bold text-slate-800">Policies</h2>
                        <p className="text-sm text-slate-500">Manage network access policies and permissions.</p>
                    </div>
                    <button
                        onClick={() => setIsCreateModalOpen(true)}
                        className="bg-indigo-600 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-indigo-700 shadow-sm font-medium"
                    >
                        <Plus size={18} /> Create Policy
                    </button>
                </div>

                {/* Search & Toolbar */}
                <div className="flex gap-4 items-center">
                    <div className="relative flex-1 max-w-md">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                        <input
                            className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
                            placeholder="Search policies..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                </div>

                {/* Data Grid */}
                <div className="bg-white rounded-lg shadow border overflow-hidden">
                    <table className="w-full text-left">
                        <thead className="bg-slate-50 border-b">
                            <tr>
                                <th className="p-4 font-semibold text-gray-600 text-sm">Policy Name</th>
                                <th className="p-4 font-semibold text-gray-600 text-sm">Applies To (Scope)</th>
                                <th className="p-4 font-semibold text-gray-600 text-sm">Conditions</th>
                                <th className="p-4 font-semibold text-gray-600 text-sm">Replies</th>
                                <th className="p-4 font-semibold text-gray-600 text-sm text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y">
                            {policiesTable.length === 0 && (
                                <tr>
                                    <td colSpan="5" className="p-8 text-center text-gray-400">
                                        No policies found. Create one to get started.
                                    </td>
                                </tr>
                            )}
                            {policiesTable.map(p => (
                                <tr key={p.name} className="hover:bg-slate-50 transition-colors group">
                                    <td className="p-4">
                                        <div className="font-bold text-indigo-700">{p.name}</div>
                                        <div className="text-[10px] text-gray-400 truncate max-w-[200px]">{p.description || 'No description'}</div>
                                    </td>
                                    <td className="p-4 text-sm">
                                        {p.scope.includes('Manual') ? (
                                            <span className="text-gray-400 italic text-xs">{p.scope}</span>
                                        ) : (
                                            <span className={`px-2 py-1 rounded text-[10px] font-black uppercase tracking-tighter border ${p.scope.startsWith('Hybrid') ? 'bg-purple-50 text-purple-700 border-purple-100' : 'bg-blue-50 text-blue-700 border-blue-100'}`}>
                                                {p.scope}
                                            </span>
                                        )}
                                    </td>
                                    <td className="p-4 text-sm"><span className="bg-yellow-100 text-yellow-800 px-2 py-1 rounded-full text-xs font-bold">{p.checkCount}</span></td>
                                    <td className="p-4 text-sm"><span className="bg-green-100 text-green-800 px-2 py-1 rounded-full text-xs font-bold">{p.replyCount}</span></td>
                                    <td className="p-4 text-right">
                                        <div className="flex gap-2 justify-end">
                                            <button
                                                onClick={() => { setSelectedPolicy(p.name); setViewMode('edit'); }}
                                                className="p-2 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-all"
                                            >
                                                <Edit2 size={16} />
                                            </button>
                                            <button
                                                onClick={() => {
                                                    if (window.confirm(`Delete policy ${p.name}?`)) deletePolicyMutation.mutate(p.name);
                                                }}
                                                className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-all"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Create Modal */}
                {isCreateModalOpen && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
                        <div className="bg-white rounded-lg p-6 w-full max-w-md shadow-xl animate-fadeIn">
                            <h3 className="text-xl font-bold mb-4 text-gray-800">Create New Policy</h3>
                            <form onSubmit={handleCreateSubmit} className="space-y-4">
                                <div>
                                    <label className="block text-sm font-bold text-gray-700 mb-1">Policy Name</label>
                                    <input
                                        className="w-full border rounded p-2 focus:ring-2 focus:ring-blue-500 outline-none"
                                        placeholder="e.g. Premium-Access-Vlan10"
                                        value={wizardData.name}
                                        onChange={e => setWizardData({ ...wizardData, name: e.target.value })}
                                        required
                                    />
                                </div>
                                <div className="border-t pt-4">
                                    <label className="block text-sm font-bold text-gray-700 mb-2">Initial Scope</label>
                                    <div className="space-y-2">
                                        <label className="flex items-center gap-2 p-2 border rounded cursor-pointer hover:bg-gray-50">
                                            <input type="radio" name="targetType" checked={wizardData.targetType === 'none'} onChange={() => setWizardData({ ...wizardData, targetType: 'none', targetValue: '' })} />
                                            <span className="text-sm">Configure Later</span>
                                        </label>
                                        <label className="flex items-center gap-2 p-2 border rounded cursor-pointer hover:bg-gray-50">
                                            <input type="radio" name="targetType" checked={wizardData.targetType === 'shortname'} onChange={() => setWizardData({ ...wizardData, targetType: 'shortname', targetValue: '' })} />
                                            <div className="flex-1">
                                                <span className="text-sm block">By Group/Shortname</span>
                                                {wizardData.targetType === 'shortname' && (
                                                    <select className="w-full mt-1 border rounded p-1 text-sm bg-purple-50" value={wizardData.targetValue} onChange={e => setWizardData({ ...wizardData, targetType: 'shortname', targetValue: e.target.value })} onClick={(e) => e.stopPropagation()}>
                                                        <option value="">-- Select Shortname --</option>
                                                        {[...new Set(nasList?.map(n => n.shortname).filter(Boolean))].map(sn => <option key={sn} value={sn}>{sn}</option>)}
                                                    </select>
                                                )}
                                            </div>
                                        </label>
                                    </div>
                                </div>
                                <div className="flex justify-end gap-2 mt-6">
                                    <button type="button" onClick={() => setIsCreateModalOpen(false)} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded">Cancel</button>
                                    <button type="submit" className="px-4 py-2 bg-indigo-600 text-white font-bold rounded hover:bg-indigo-700 disabled:opacity-50" disabled={!wizardData.name}>Create</button>
                                </div>
                            </form>
                        </div>
                    </div>
                )}
            </div>
        );
    }

    // --- RENDER: EDIT VIEW ---

    return (
        <div className="h-[calc(100vh-6rem)] flex flex-col bg-white rounded-lg shadow">
            {/* Editor Header */}
            <div className="p-6 border-b flex justify-between items-center bg-slate-50">
                <div className="flex items-center gap-4">
                    <button onClick={() => setViewMode('list')} className="text-gray-500 hover:text-indigo-600 flex items-center gap-1 text-sm font-bold">
                        <ArrowRight className="rotate-180" size={16} /> Back
                    </button>
                    <div className="h-6 w-px bg-gray-300"></div>
                    <div className="flex flex-col">
                        <h2 className="text-2xl font-bold text-slate-800">{selectedPolicy}</h2>
                        <span className="text-xs text-green-600 flex items-center gap-1">● Auto-Saved</span>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => setViewMode('list')}
                        className="bg-indigo-600 text-white px-4 py-2 rounded-lg font-bold hover:bg-indigo-700 shadow-sm flex items-center gap-2"
                    >
                        Save & Close
                    </button>
                    <button onClick={() => { if (window.confirm('Delete Policy?')) deletePolicyMutation.mutate(selectedPolicy); }} className="text-red-500 hover:bg-red-50 px-3 py-2 rounded font-medium flex gap-2"><Trash2 size={18} /></button>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-8 bg-gray-50/30">
                <div className="max-w-6xl mx-auto space-y-6">

                    {/* DESCRIPTION & TITLE */}
                    <div className="bg-white border rounded-xl p-6 shadow-sm">
                        <div className="flex items-start gap-4">
                            <div className="p-3 bg-indigo-50 rounded-xl text-indigo-600">
                                <FileText size={24} />
                            </div>
                            <div className="flex-1">
                                <label className="block text-xs font-black text-gray-400 uppercase tracking-widest mb-1">Policy Description</label>
                                <textarea
                                    className="w-full border-none focus:ring-0 text-gray-600 text-sm p-0 placeholder:italic resize-none"
                                    placeholder="Enter circular purpose or notes for this policy..."
                                    rows={2}
                                    defaultValue={activeChecks.find(c => c.attribute === 'Description')?.value || ''}
                                    onBlur={(e) => handleDescriptionSave(e.target.value)}
                                />
                            </div>
                        </div>
                    </div>

                    {/* SCOPE MANAGER */}
                    <div className="bg-white border rounded-xl p-6 shadow-sm">
                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
                            <div>
                                <h3 className="font-bold text-lg text-gray-800">Operational Scope</h3>
                                <p className="text-sm text-gray-500 truncate max-w-md">
                                    Configure where this policy is enforced. You can combine a Group and a Specific NAS.
                                </p>
                            </div>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => handleScopeChange('shortname', activeChecks.some(c => c.attribute === 'FreeRADIUS-Client-Shortname') ? null : '')}
                                    className={`px-4 py-2 rounded-lg text-xs font-bold border transition-all ${activeChecks.some(c => c.attribute === 'FreeRADIUS-Client-Shortname') ? 'bg-indigo-600 text-white border-indigo-600 shadow-md' : 'bg-white text-gray-600 border-gray-200'}`}
                                >
                                    {activeChecks.some(c => c.attribute === 'FreeRADIUS-Client-Shortname') ? '✓ Group Scope Active' : '+ Add Group Scope'}
                                </button>
                                <button
                                    onClick={() => handleScopeChange('nas', activeChecks.some(c => c.attribute === 'NAS-Identifier') ? null : '')}
                                    className={`px-4 py-2 rounded-lg text-xs font-bold border transition-all ${activeChecks.some(c => c.attribute === 'NAS-Identifier') ? 'bg-blue-600 text-white border-blue-600 shadow-md' : 'bg-white text-gray-600 border-gray-200'}`}
                                >
                                    {activeChecks.some(c => c.attribute === 'NAS-Identifier') ? '✓ NAS Scope Active' : '+ Add NAS Scope'}
                                </button>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {/* SUB-VIEW: SHORTNAME PICKER */}
                            {activeChecks.some(c => c.attribute === 'FreeRADIUS-Client-Shortname') && (
                                <div className="flex flex-col gap-2 bg-indigo-50 p-4 rounded-xl border border-indigo-100 animate-fadeIn">
                                    <label className="text-[10px] font-black text-indigo-700 uppercase tracking-tighter">Target Client Group (Shortname):</label>
                                    <select
                                        className="w-full border rounded-lg p-2 text-sm bg-white outline-none focus:ring-2 focus:ring-indigo-300"
                                        value={activeChecks.find(c => c.attribute === 'FreeRADIUS-Client-Shortname')?.value || ''}
                                        onChange={(e) => handleScopeChange('shortname', e.target.value)}
                                    >
                                        <option value="">-- Select Shortname --</option>
                                        {[...new Set(nasList?.map(n => n.shortname).filter(Boolean))].map(sn => <option key={sn} value={sn}>{sn}</option>)}
                                    </select>
                                </div>
                            )}

                            {/* SUB-VIEW: NAS PICKER */}
                            {activeChecks.some(c => c.attribute === 'NAS-Identifier') && (
                                <div className="flex flex-col gap-2 bg-blue-50 p-4 rounded-xl border border-blue-100 animate-fadeIn">
                                    <label className="text-[10px] font-black text-blue-700 uppercase tracking-tighter">Target Specific NAS (Identifier):</label>
                                    <select
                                        className="w-full border rounded-lg p-2 text-sm bg-white outline-none focus:ring-2 focus:ring-blue-300"
                                        value={activeChecks.find(c => c.attribute === 'NAS-Identifier')?.value || ''}
                                        onChange={(e) => handleScopeChange('nas', e.target.value)}
                                    >
                                        <option value="">-- Select NAS Identifier --</option>
                                        {nasList?.map(n => <option key={n.nasname} value={n.nasname}>{n.nasname} ({n.shortname})</option>)}
                                    </select>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                        {/* LEFT: CONDITIONS */}
                        <div className="space-y-4">
                            <div className="flex items-center gap-2 mb-2">
                                <div className="bg-yellow-100 p-2 rounded text-yellow-700 shadow-sm"><Shield size={20} /></div>
                                <h3 className="font-bold text-lg text-gray-800">Access Conditions</h3>
                            </div>
                            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
                                <AttributeSelector dictionary={dictionaryAttributes} submitLabel="Add Condition" onSelect={item => createCheckMutation.mutate({ ...item, groupname: selectedPolicy })} />
                                <div className="space-y-2 mt-4">
                                    {activeChecks.filter(c => c.attribute !== 'Description').map(it => (
                                        <div key={it.id} className="bg-gray-50 p-3 border rounded-lg flex justify-between items-center group transition-all hover:border-yellow-300">
                                            <div className="font-mono text-xs">
                                                <span className="font-bold text-gray-700">{it.attribute}</span>
                                                <span className="mx-2 text-gray-400">{it.op}</span>
                                                <span className="bg-purple-100 text-purple-700 px-2 py-0.5 rounded">{it.value}</span>
                                            </div>
                                            <button onClick={() => deleteItem(it.id, 'check')} className="text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"><Trash2 size={16} /></button>
                                        </div>
                                    ))}
                                    {activeChecks.filter(c => c.attribute !== 'Description').length === 0 && <p className="text-center text-sm text-gray-400 italic py-2">No access conditions defined.</p>}
                                </div>
                            </div>
                        </div>

                        {/* RIGHT: PERMISSIONS */}
                        <div className="space-y-4">
                            <div className="flex items-center gap-2 mb-2">
                                <div className="bg-emerald-100 p-2 rounded text-emerald-700 shadow-sm"><Layers size={20} /></div>
                                <h3 className="font-bold text-lg text-gray-800">Permissions (Reply)</h3>
                            </div>
                            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
                                <AttributeSelector dictionary={dictionaryAttributes} submitLabel="Add Attribute" onSelect={item => createReplyMutation.mutate({ ...item, groupname: selectedPolicy })} />
                                <div className="space-y-2 mt-4">
                                    {activeReplies.map(it => (
                                        <div key={it.id} className="bg-gray-50 p-3 border rounded-lg flex justify-between items-center group transition-all hover:border-emerald-300">
                                            <div className="font-mono text-xs">
                                                <span className="font-bold text-gray-700">{it.attribute}</span>
                                                <span className="mx-2 text-gray-400">{it.op}</span>
                                                <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded">{it.value}</span>
                                            </div>
                                            <button onClick={() => deleteItem(it.id, 'reply')} className="text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"><Trash2 size={16} /></button>
                                        </div>
                                    ))}
                                    {activeReplies.length === 0 && <p className="text-center text-sm text-gray-400 italic py-2">No return attributes.</p>}
                                </div>
                            </div>

                            {/* ASSIGNED MEMBERS (NEW) */}
                            <div className="mt-8">
                                <div className="flex items-center gap-2 mb-2">
                                    <div className="bg-purple-100 p-2 rounded text-purple-700 shadow-sm"><UsersIcon size={20} /></div>
                                    <h3 className="font-bold text-lg text-gray-800">Assigned Users</h3>
                                </div>
                                <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
                                    {isLoadingMembers ? (
                                        <p className="text-gray-400 text-sm">Loading members...</p>
                                    ) : groupMembers?.length > 0 ? (
                                        <div className="flex flex-wrap gap-2">
                                            {groupMembers.map(m => (
                                                <div key={m.username} className="bg-purple-50 text-purple-900 pl-3 pr-1 py-1 rounded-full text-xs font-bold border border-purple-100 flex items-center gap-1 group hover:bg-purple-100 transition-colors">
                                                    {m.username}
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            if (window.confirm(`Remove ${m.username} from ${selectedPolicy}?`)) {
                                                                GroupsService.removeUserFromGroup(m.username, selectedPolicy)
                                                                    .then(() => queryClient.invalidateQueries(['groups', 'members', selectedPolicy]))
                                                                    .catch(() => alert('Failed to remove user'));
                                                            }
                                                        }}
                                                        className="p-1 rounded-full text-purple-400 hover:text-red-500 hover:bg-white transition-all ml-1"
                                                        title="Remove user from group"
                                                    >
                                                        <X size={14} />
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <p className="text-sm text-gray-400 italic">No users assigned to this group.</p>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PoliciesPage;

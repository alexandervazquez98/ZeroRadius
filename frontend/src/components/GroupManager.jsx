import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { Plus, Trash2, Layers, Shield, ArrowRight, Save, X, Server, Filter } from 'lucide-react';

// --- SUB-COMPONENT: ATTRIBUTE SELECTOR ---
const AttributeSelector = ({ dictionary, onSelect, submitLabel = "Add" }) => {
    const [selectedVendor, setSelectedVendor] = useState('');
    const [selectedAttr, setSelectedAttr] = useState('');
    const [op, setOp] = useState(':=');
    const [val, setVal] = useState('');

    // 1. Extract Unique Vendors
    const vendors = useMemo(() => {
        if (!dictionary) return [];
        const vSet = new Set(dictionary.map(d => d.vendor || 'IETF (Standard)'));
        return Array.from(vSet).sort();
    }, [dictionary]);

    // 2. Filter Attributes by Selected Vendor
    const filteredAttributes = useMemo(() => {
        if (!dictionary) return [];
        const vendorKey = selectedVendor === 'IETF (Standard)' ? null : selectedVendor;
        return dictionary.filter(d => d.vendor === vendorKey);
    }, [dictionary, selectedVendor]);

    const handleAdd = () => {
        if (selectedAttr && val) {
            onSelect({ attribute: selectedAttr, op, value: val });
            setVal(''); // Clear value only, maybe keep vendor/attr for rapid entry? No, clear mostly.
        }
    };

    return (
        <div className="bg-white p-4 rounded border mb-4 flex flex-col gap-3">
            <div className="flex gap-2 items-center">
                <label className="text-xs font-bold text-gray-500 w-16 uppercase">Vendor</label>
                <select
                    className="flex-1 border rounded p-2 text-sm"
                    value={selectedVendor}
                    onChange={e => { setSelectedVendor(e.target.value); setSelectedAttr(''); }}
                >
                    <option value="">-- Select Vendor / Standard --</option>
                    {vendors.map(v => <option key={v} value={v}>{v}</option>)}
                </select>
            </div>

            <div className="flex gap-2 items-center">
                <label className="text-xs font-bold text-gray-500 w-16 uppercase">Attribute</label>
                <select
                    className="flex-1 border rounded p-2 text-sm"
                    value={selectedAttr}
                    onChange={e => setSelectedAttr(e.target.value)}
                    disabled={!selectedVendor}
                >
                    <option value="">-- Select Attribute --</option>
                    {filteredAttributes.map(a => (
                        <option key={a.name} value={a.name}>{a.name} ({a.type})</option>
                    ))}
                </select>
            </div>

            <div className="flex gap-2 items-end">
                <div className="w-20">
                    <label className="block text-xs font-bold text-gray-500 mb-1 uppercase">Op</label>
                    <select
                        className="w-full border rounded p-2 text-sm"
                        value={op}
                        onChange={e => setOp(e.target.value)}
                    >
                        <option value=":=">:=</option>
                        <option value="=">=</option>
                        <option value="==">==</option>
                        <option value="+=">+=</option>
                    </select>
                </div>
                <div className="flex-1">
                    <label className="block text-xs font-bold text-gray-500 mb-1 uppercase">Value</label>
                    <input
                        className="w-full border rounded p-2 text-sm"
                        placeholder="Value..."
                        value={val}
                        onChange={e => setVal(e.target.value)}
                    />
                </div>
                <button
                    onClick={handleAdd}
                    disabled={!selectedAttr || !val}
                    className="bg-blue-600 text-white rounded px-4 py-2 hover:bg-blue-700 disabled:opacity-50 font-medium h-[38px]"
                >
                    {submitLabel}
                </button>
            </div>
        </div>
    );
};


const GroupManager = () => {
    const queryClient = useQueryClient();
    const [selectedGroup, setSelectedGroup] = useState(null);
    const [newItem, setNewItem] = useState({ attribute: '', op: ':=', value: '', scopeTab: 'nas' });
    const [newPolicyName, setNewPolicyName] = useState('');

    // --- DATA FETCHING ---
    const { data: groupsList } = useQuery({ queryKey: ['groups', 'list'], queryFn: () => api.get('/groups/list').then(r => r.data) });
    const { data: groupChecks } = useQuery({ queryKey: ['groups', 'check'], queryFn: () => api.get('/groups/check').then(r => r.data) });
    const { data: groupReplies } = useQuery({ queryKey: ['groups', 'reply'], queryFn: () => api.get('/groups/reply').then(r => r.data) });
    const { data: nasList } = useQuery({ queryKey: ['nas'], queryFn: () => api.get('/nas').then(r => r.data) });
    const { data: dictionaryAttributes } = useQuery({ queryKey: ['dictionary', 'attributes'], queryFn: () => api.get('/dictionary/attributes').then(r => r.data) });

    // --- MUTATIONS ---
    const createCheckMutation = useMutation({
        mutationFn: (item) => api.post('/groups/check', item),
        onSuccess: () => queryClient.invalidateQueries(['groups'])
    });
    const createReplyMutation = useMutation({
        mutationFn: (item) => api.post('/groups/reply', item),
        onSuccess: () => queryClient.invalidateQueries(['groups'])
    });
    const deleteCheckMutation = useMutation({
        mutationFn: (id) => api.delete(`/groups/check/${id}`),
        onSuccess: () => queryClient.invalidateQueries(['groups'])
    });
    const deleteReplyMutation = useMutation({
        mutationFn: (id) => api.delete(`/groups/reply/${id}`),
        onSuccess: () => queryClient.invalidateQueries(['groups'])
    });

    const deletePolicyMutation = useMutation({
        mutationFn: (groupname) => api.delete(`/groups/policy?groupname=${groupname}`),
        onSuccess: () => {
            queryClient.invalidateQueries(['groups']);
            setSelectedGroup(null);
        }
    });

    const activeChecks = groupChecks?.filter(i => i.groupname === selectedGroup) || [];
    const activeReplies = groupReplies?.filter(i => i.groupname === selectedGroup) || [];

    const handleCreatePolicy = (e) => {
        e.preventDefault();
        if (newPolicyName) {
            setSelectedGroup(newPolicyName);
            setNewPolicyName('');
        }
    };

    const handleDeletePolicy = () => {
        if (window.confirm(`Are you sure you want to delete policy "${selectedGroup}"? This will remove all conditions and permissions.`)) {
            deletePolicyMutation.mutate(selectedGroup);
        }
    };

    return (
        <div className="flex h-[calc(100vh-6rem)] gap-6">
            {/* LEFT SIDEBAR */}
            <div className="w-1/3 bg-white rounded-lg shadow flex flex-col">
                <div className="p-4 border-b">
                    <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                        <Layers className="text-blue-600" size={20} /> Policies
                    </h2>
                </div>
                <div className="p-4 border-b bg-gray-50">
                    <form onSubmit={handleCreatePolicy} className="flex gap-2">
                        <input
                            className="flex-1 border rounded p-2 text-sm"
                            placeholder="New Policy Name..."
                            value={newPolicyName}
                            onChange={e => setNewPolicyName(e.target.value)}
                        />
                        <button type="submit" className="bg-blue-600 text-white rounded p-2 hover:bg-blue-700"><Plus size={18} /></button>
                    </form>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    {groupsList?.map(g => (
                        <div
                            key={g.groupname}
                            onClick={() => setSelectedGroup(g.groupname)}
                            className={`p-3 rounded-lg cursor-pointer flex justify-between items-center transition-colors ${selectedGroup === g.groupname ? 'bg-blue-50 border border-blue-200 shadow-sm' : 'hover:bg-gray-50'}`}
                        >
                            <span className={`font-medium ${selectedGroup === g.groupname ? 'text-blue-700' : 'text-gray-700'}`}>{g.groupname}</span>
                            <ArrowRight size={16} className={`text-gray-400 ${selectedGroup === g.groupname ? 'opacity-100' : 'opacity-0'}`} />
                        </div>
                    ))}
                </div>
            </div>

            {/* RIGHT MAIN AREA */}
            <div className="flex-1 bg-white rounded-lg shadow flex flex-col">
                {!selectedGroup ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
                        <Layers size={48} className="mb-4 text-gray-200" />
                        <p>Select or create a policy to configure.</p>
                    </div>
                ) : (
                    <div className="flex flex-col h-full">
                        <div className="p-6 border-b flex justify-between items-start bg-slate-50">
                            <div>
                                <h2 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
                                    {selectedGroup}
                                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full font-normal">Active Policy</span>
                                </h2>
                                <p className="text-sm text-gray-500 mt-1">Configure access rules and attributes.</p>
                            </div>
                            <div className="flex gap-2">
                                <button
                                    onClick={handleDeletePolicy}
                                    className="text-red-600 hover:bg-red-50 px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-1 border border-transparent hover:border-red-200 transition-colors"
                                >
                                    <Trash2 size={16} /> Delete Policy
                                </button>
                                <button onClick={() => setSelectedGroup(null)} className="text-gray-400 hover:text-gray-600 p-2"><X /></button>
                            </div>
                        </div>

                        <div className="flex-1 overflow-y-auto p-6 space-y-8">

                            {/* CONDITIONS (CHECKS) */}
                            <div className="border border-yellow-200 bg-yellow-50 rounded-lg p-6">
                                <h3 className="text-lg font-bold text-yellow-800 mb-4 flex items-center gap-2">
                                    <Shield size={20} /> Access Conditions (Checks)
                                </h3>
                                <p className="text-sm text-yellow-700 mb-4">Define <b>Who</b> or <b>Where</b> this policy applies. If these conditions aren't met, the policy is ignored.</p>

                                {/* NAS Selector: Tabs for Scope */}
                                <div className="bg-white p-4 rounded border mb-4 flex flex-col gap-3">
                                    <h4 className="text-xs font-bold text-gray-500 uppercase flex justify-between items-center">
                                        Policy Scope
                                        <div className="flex bg-gray-100 rounded p-1">
                                            <button
                                                className={`px-3 py-1 text-xs rounded transition-colors ${!newItem.scopeTab || newItem.scopeTab === 'nas' ? 'bg-white shadow text-blue-600 font-bold' : 'text-gray-500'}`}
                                                onClick={() => setNewItem({ ...newItem, scopeTab: 'nas' })}
                                            >
                                                Specific NAS
                                            </button>
                                            <button
                                                className={`px-3 py-1 text-xs rounded transition-colors ${newItem.scopeTab === 'shortname' ? 'bg-white shadow text-purple-600 font-bold' : 'text-gray-500'}`}
                                                onClick={() => setNewItem({ ...newItem, scopeTab: 'shortname' })}
                                            >
                                                By Shortname (Dynamic)
                                            </button>
                                        </div>
                                    </h4>

                                    {/* TAB 1: SPECIFIC NAS */}
                                    {(!newItem.scopeTab || newItem.scopeTab === 'nas') && (
                                        <div className="flex flex-col gap-2 animate-fadeIn">
                                            <p className="text-xs text-gray-400">Select specific devices. Static list.</p>
                                            <div className="h-32 overflow-y-auto border rounded p-2 text-sm bg-gray-50 grid grid-cols-2 gap-2">
                                                {nasList?.map(nas => (
                                                    <label key={nas.id} className="flex items-center gap-2 cursor-pointer hover:bg-white p-1 rounded">
                                                        <input
                                                            type="checkbox"
                                                            value={nas.nasname}
                                                            className="nas-checkbox rounded text-blue-600"
                                                        />
                                                        <div className="flex flex-col leading-none">
                                                            <span className="font-medium">{nas.shortname || 'Unknown'}</span>
                                                            <span className="text-[10px] text-gray-400">{nas.nasname}</span>
                                                        </div>
                                                    </label>
                                                ))}
                                            </div>
                                            <button
                                                className="bg-blue-600 text-white text-xs font-bold py-2 px-3 rounded hover:bg-blue-700 self-start"
                                                onClick={() => {
                                                    const checkboxes = document.querySelectorAll('.nas-checkbox:checked');
                                                    const values = Array.from(checkboxes).map(cb => cb.value);
                                                    if (values.length === 0) return;

                                                    if (values.length === 1) {
                                                        createCheckMutation.mutate({ groupname: selectedGroup, attribute: 'NAS-Identifier', op: '==', value: values[0] });
                                                    } else {
                                                        const regex = `^(${values.join('|')})$`;
                                                        createCheckMutation.mutate({ groupname: selectedGroup, attribute: 'NAS-Identifier', op: '=~', value: regex });
                                                    }
                                                    checkboxes.forEach(cb => cb.checked = false);
                                                }}
                                            >
                                                Add Condition for Selected
                                            </button>
                                        </div>
                                    )}

                                    {/* TAB 2: BY SHORTNAME */}
                                    {newItem.scopeTab === 'shortname' && (
                                        <div className="flex flex-col gap-2 animate-fadeIn">
                                            <p className="text-xs text-purple-600 bg-purple-50 p-2 rounded border border-purple-100">
                                                <b>Dynamic Rule:</b> Any NAS (current or future) with this Shortname will automatically inherit this policy.
                                            </p>
                                            <div className="flex gap-2 items-center">
                                                <select
                                                    className="flex-1 border rounded p-2 text-sm"
                                                    id="shortname-select"
                                                >
                                                    <option value="">-- Select Device Group/Shortname --</option>
                                                    {(() => {
                                                        const uniqueShortnames = [...new Set(nasList?.map(n => n.shortname).filter(Boolean))];
                                                        return uniqueShortnames.map(sn => <option key={sn} value={sn}>{sn}</option>);
                                                    })()}
                                                </select>
                                                <button
                                                    className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 font-bold text-xs"
                                                    onClick={() => {
                                                        const val = document.getElementById('shortname-select').value;
                                                        if (val) createCheckMutation.mutate({ groupname: selectedGroup, attribute: 'FreeRADIUS-Client-Shortname', op: '==', value: val });
                                                    }}
                                                >
                                                    Add Dynamic Rule
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Dictionary Selector for Checks */}
                                <AttributeSelector
                                    dictionary={dictionaryAttributes}
                                    submitLabel="Add Condition"
                                    onSelect={(item) => createCheckMutation.mutate({ ...item, groupname: selectedGroup })}
                                />

                                <div className="space-y-2 mt-4">
                                    {activeChecks.map(item => (
                                        <div key={item.id} className="flex justify-between items-center bg-white p-3 rounded border shadow-sm">
                                            <div className="font-mono text-sm">
                                                <span className="font-bold text-gray-700">{item.attribute}</span>
                                                <span className="mx-2 text-gray-400">{item.op}</span>
                                                <span className="bg-gray-100 px-2 py-1 rounded">{item.value}</span>
                                            </div>
                                            <button onClick={() => deleteCheckMutation.mutate(item.id)} className="text-red-400 hover:text-red-600"><Trash2 size={16} /></button>
                                        </div>
                                    ))}
                                    {activeChecks.length === 0 && <p className="text-sm text-center text-gray-500 italic">No conditions configured (Applies unconditionally).</p>}
                                </div>
                            </div>

                            {/* PERMISSIONS (REPLIES) */}
                            <div className="border border-green-200 bg-green-50 rounded-lg p-6">
                                <h3 className="text-lg font-bold text-green-800 mb-4 flex items-center gap-2">
                                    <Layers size={20} /> Permissions (Attributes)
                                </h3>
                                <p className="text-sm text-green-700 mb-4">Define <b>What</b> parameters are returned to the NAS (VLANs, Bandwidth, Vendors).</p>

                                {/* Dictionary Selector for Replies */}
                                <AttributeSelector
                                    dictionary={dictionaryAttributes}
                                    submitLabel="Add Permission"
                                    onSelect={(item) => createReplyMutation.mutate({ ...item, groupname: selectedGroup })}
                                />

                                <div className="space-y-2 mt-4">
                                    {activeReplies.map(item => (
                                        <div key={item.id} className="flex justify-between items-center bg-white p-3 rounded border shadow-sm">
                                            <div className="font-mono text-sm">
                                                <span className="font-bold text-gray-700">{item.attribute}</span>
                                                <span className="mx-2 text-gray-400">{item.op}</span>
                                                <span className="bg-gray-100 px-2 py-1 rounded text-blue-600">{item.value}</span>
                                            </div>
                                            <button onClick={() => deleteReplyMutation.mutate(item.id)} className="text-red-400 hover:text-red-600"><Trash2 size={16} /></button>
                                        </div>
                                    ))}
                                    {activeReplies.length === 0 && <p className="text-sm text-center text-gray-500 italic">No attributes configured.</p>}
                                </div>
                            </div>

                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default GroupManager;

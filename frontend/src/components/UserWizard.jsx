import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { Check, User, Shield, Activity, Save, Plus, Trash2 } from 'lucide-react';

const UserWizard = ({ onComplete, onCancel }) => {
    const queryClient = useQueryClient();
    const [step, setStep] = useState(1);
    const [userData, setUserData] = useState({
        username: '',
        password: '',
        passwordType: 'Cleartext-Password'
    });
    const [customAttributes, setCustomAttributes] = useState([]);
    const [newAttr, setNewAttr] = useState({ attribute: '', op: ':=', value: '' });

    // Fetch Dictionary Attributes for Step 2
    const { data: dictionaryAttributes } = useQuery({
        queryKey: ['dictionary', 'attributes'],
        queryFn: () => api.get('/dictionary/attributes').then(r => r.data)
    });

    const steps = [
        { id: 1, title: 'Identity', icon: User },
        { id: 2, title: 'Attributes', icon: Activity },
    ];

    const handleAddAttribute = () => {
        if (newAttr.attribute && newAttr.value) {
            setCustomAttributes([...customAttributes, { ...newAttr }]);
            setNewAttr({ attribute: '', op: ':=', value: '' });
        }
    };

    const handleRemoveAttribute = (idx) => {
        setCustomAttributes(customAttributes.filter((_, i) => i !== idx));
    };

    const submitMutation = useMutation({
        mutationFn: async () => {
            // 1. Create User Check (Password)
            await api.post('/users/check', {
                username: userData.username,
                attribute: userData.passwordType,
                op: ':=',
                value: userData.password
            });

            // 2. Add Custom Reply Attributes
            for (const attr of customAttributes) {
                await api.post('/users/reply', {
                    username: userData.username,
                    attribute: attr.attribute,
                    op: attr.op,
                    value: attr.value
                });
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries(['users']);
            onComplete();
        }
    });

    return (
        <div className="bg-white rounded-lg shadow-lg max-w-2xl w-full flex flex-col h-[600px]">
            {/* Header */}
            <div className="p-6 border-b flex justify-between items-center bg-slate-50 rounded-t-lg">
                <h2 className="text-xl font-bold text-slate-800">Create New User</h2>
                <div className="flex gap-2">
                    {steps.map((s, i) => (
                        <div key={s.id} className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm ${step === s.id ? 'bg-blue-100 text-blue-700 font-bold' : 'text-gray-400'}`}>
                            <s.icon size={16} />
                            <span>{s.title}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Content Body */}
            <div className="flex-1 p-8 overflow-y-auto">
                {step === 1 && (
                    <div className="space-y-4 max-w-sm mx-auto">
                        <h3 className="text-lg font-semibold text-center mb-6">User Credentials</h3>
                        <div>
                            <label htmlFor="wizard-username" className="block text-sm font-medium mb-1">Username</label>
                            <input
                                id="wizard-username"
                                className="w-full border rounded-lg p-3 focus:ring-2 focus:ring-blue-500 outline-none"
                                value={userData.username}
                                onChange={e => setUserData({ ...userData, username: e.target.value })}
                                autoFocus
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-1">Password Check Type</label>
                            <select
                                className="w-full border rounded-lg p-3 bg-white"
                                value={userData.passwordType}
                                onChange={e => setUserData({ ...userData, passwordType: e.target.value })}
                            >
                                <option value="Cleartext-Password">Cleartext-Password</option>
                                <option value="MD5-Password">MD5-Password</option>
                            </select>
                        </div>
                        <div>
                            <label htmlFor="wizard-password" className="block text-sm font-medium mb-1">Password</label>
                            <input
                                id="wizard-password"
                                type="password"
                                className="w-full border rounded-lg p-3 focus:ring-2 focus:ring-blue-500 outline-none"
                                value={userData.password}
                                onChange={e => setUserData({ ...userData, password: e.target.value })}
                            />
                        </div>
                    </div>
                )}

                {step === 2 && (
                    <div className="space-y-6">
                        <div className="text-center">
                            <h3 className="text-lg font-semibold">Custom Reply Attributes</h3>
                            <p className="text-sm text-gray-500">Add specific attributes returned to the NAS for this user only.</p>
                        </div>

                        {/* Add Form */}
                        <div className="flex gap-2 bg-gray-50 p-3 rounded-lg items-end">
                            <div className="flex-1">
                                <label className="text-xs text-gray-500 block mb-1">Attribute Name</label>
                                <input
                                    list="attributes-list"
                                    className="w-full border rounded p-2 text-sm"
                                    placeholder="e.g. Framed-IP-Address"
                                    value={newAttr.attribute}
                                    onChange={e => setNewAttr({ ...newAttr, attribute: e.target.value })}
                                />
                                <datalist id="attributes-list">
                                    {dictionaryAttributes?.map(attr => (
                                        <option key={attr.name} value={attr.name}>{attr.name} ({attr.type})</option>
                                    ))}
                                </datalist>
                            </div>

                            <div className="w-24">
                                <label className="text-xs text-gray-500 block mb-1">Operator</label>
                                <select
                                    className="w-full border rounded p-2 text-sm"
                                    value={newAttr.op}
                                    onChange={e => setNewAttr({ ...newAttr, op: e.target.value })}
                                >
                                    <option value=":=">:=</option>
                                    <option value="+=">+=</option>
                                    <option value="=">=</option>
                                </select>
                            </div>

                            <div className="flex-1">
                                <label className="text-xs text-gray-500 block mb-1">Value</label>
                                <input
                                    className="w-full border rounded p-2 text-sm"
                                    placeholder="Value"
                                    value={newAttr.value}
                                    onChange={e => setNewAttr({ ...newAttr, value: e.target.value })}
                                />
                            </div>

                            <button
                                onClick={handleAddAttribute}
                                className="bg-blue-600 text-white rounded px-3 py-2 hover:bg-blue-700 h-[38px]"
                            >
                                <Plus size={18} />
                            </button>
                        </div>

                        {/* List */}
                        <div className="border rounded-lg overflow-hidden">
                            <table className="w-full text-sm text-left">
                                <thead className="bg-gray-100">
                                    <tr>
                                        <th className="p-2">Attribute</th>
                                        <th className="p-2">Op</th>
                                        <th className="p-2">Value</th>
                                        <th className="p-2"></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {customAttributes.map((attr, idx) => (
                                        <tr key={idx} className="border-t">
                                            <td className="p-2 font-mono">{attr.attribute}</td>
                                            <td className="p-2">{attr.op}</td>
                                            <td className="p-2 font-mono">{attr.value}</td>
                                            <td className="p-2 text-right">
                                                <button onClick={() => handleRemoveAttribute(idx)} className="text-red-500 hover:text-red-700"><Trash2 size={16} /></button>
                                            </td>
                                        </tr>
                                    ))}
                                    {customAttributes.length === 0 && (
                                        <tr><td colSpan="4" className="p-4 text-center text-gray-400">No custom attributes added.</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>

            {/* Footer / Controls */}
            <div className="p-6 border-t bg-slate-50 rounded-b-lg flex justify-between">
                <button
                    onClick={() => {
                        if (step > 1) setStep(step - 1);
                        else onCancel();
                    }}
                    className="px-6 py-2 text-gray-600 hover:bg-gray-200 rounded-lg font-medium transition-colors"
                >
                    {step === 1 ? 'Cancel' : 'Back'}
                </button>

                <button
                    onClick={() => {
                        if (step < 2) setStep(step + 1);
                        else submitMutation.mutate();
                    }}
                    disabled={step === 1 && (!userData.username || !userData.password)}
                    className="px-8 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {step === 2 ? (submitMutation.isPending ? 'Saving...' : 'Create User') : 'Next'}
                    {step === 2 && <Save size={18} />}
                </button>
            </div>
        </div>
    );
};

export default UserWizard;

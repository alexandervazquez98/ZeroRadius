import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { Plus, Trash2, Shield, Server, Map, AlertCircle } from 'lucide-react';

const IAM = () => {
    const queryClient = useQueryClient();
    const [activeTab, setActiveTab] = useState('matrix'); // 'roles', 'zones', 'matrix'

    // Queries
    const { data: roles } = useQuery({
        queryKey: ['iam', 'roles'],
        queryFn: () => api.get('/iam-nac/roles').then(r => r.data)
    });

    const { data: zones } = useQuery({
        queryKey: ['iam', 'zones'],
        queryFn: () => api.get('/iam-nac/zones').then(r => r.data)
    });

    const { data: macros } = useQuery({
        queryKey: ['iam', 'macros'],
        queryFn: () => api.get('/iam-nac/macros').then(r => r.data)
    });

    const { data: matrix } = useQuery({
        queryKey: ['iam', 'matrix'],
        queryFn: () => api.get('/iam-nac/matrix-assign').then(r => r.data)
    });

    // Mutations
    const addRole = useMutation({
        mutationFn: (name) => api.post('/iam-nac/roles', { name, description: '' }),
        onSuccess: () => queryClient.invalidateQueries(['iam', 'roles'])
    });
    const deleteRole = useMutation({
        mutationFn: (id) => api.delete(`/iam-nac/roles/${id}`),
        onSuccess: () => {
            queryClient.invalidateQueries(['iam', 'roles']);
            queryClient.invalidateQueries(['iam', 'matrix']);
        }
    });

    const addZone = useMutation({
        mutationFn: (name) => api.post('/iam-nac/zones', { name, description: '' }),
        onSuccess: () => queryClient.invalidateQueries(['iam', 'zones'])
    });
    const deleteZone = useMutation({
        mutationFn: (id) => api.delete(`/iam-nac/zones/${id}`),
        onSuccess: () => {
            queryClient.invalidateQueries(['iam', 'zones']);
            queryClient.invalidateQueries(['iam', 'matrix']);
        }
    });

    const assignMatrix = useMutation({
        mutationFn: (assignment) => api.post('/iam-nac/matrix-assign', assignment),
        onSuccess: () => queryClient.invalidateQueries(['iam', 'matrix'])
    });

    // Sub-components
    const renderRoles = () => {
        return (
            <div className="bg-white rounded-lg shadow border p-6 max-w-2xl mx-auto">
                <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2"><Shield className="text-indigo-600"/> Gestor de Roles IAM</h3>
                <form onSubmit={e => {
                    e.preventDefault();
                    const val = e.target.roleName.value;
                    if(val) { addRole.mutate(val); e.target.reset(); }
                }} className="flex gap-2 mb-6">
                    <input name="roleName" className="border rounded p-2 flex-1 outline-none focus:ring-2 focus:ring-indigo-500" placeholder="Ej: Soporte L1" required />
                    <button type="submit" className="bg-indigo-600 text-white px-4 rounded hover:bg-indigo-700 font-bold flex items-center gap-1"><Plus size={18}/> Add Role</button>
                </form>
                <div className="space-y-2">
                    {roles?.map(r => (
                        <div key={r.id} className="flex justify-between items-center p-3 bg-gray-50 border rounded-lg hover:bg-gray-100 transition">
                            <span className="font-bold text-gray-700">{r.name}</span>
                            <button onClick={() => window.confirm('Quitar Rol?') && deleteRole.mutate(r.id)} className="text-red-500 hover:bg-red-50 p-2 rounded"><Trash2 size={16}/></button>
                        </div>
                    ))}
                    {roles?.length === 0 && <p className="text-sm text-gray-400 italic text-center py-4">No hay roles definidos.</p>}
                </div>
            </div>
        );
    };

    const renderZones = () => {
        return (
            <div className="bg-white rounded-lg shadow border p-6 max-w-2xl mx-auto">
                <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2"><Server className="text-blue-600"/> Hardware Zones (Zonas Físicas/Lógicas)</h3>
                <form onSubmit={e => {
                    e.preventDefault();
                    const val = e.target.zoneName.value;
                    if(val) { addZone.mutate(val); e.target.reset(); }
                }} className="flex gap-2 mb-6">
                    <input name="zoneName" className="border rounded p-2 flex-1 outline-none focus:ring-2 focus:ring-blue-500" placeholder="Ej: Núcleo (Core), Borde, CCTV" required />
                    <button type="submit" className="bg-blue-600 text-white px-4 rounded hover:bg-blue-700 font-bold flex items-center gap-1"><Plus size={18}/> Add Zone</button>
                </form>
                <div className="space-y-2">
                    {zones?.map(z => (
                        <div key={z.id} className="flex justify-between items-center p-3 bg-gray-50 border rounded-lg hover:bg-gray-100 transition">
                            <span className="font-bold text-gray-700">{z.name}</span>
                            <button onClick={() => window.confirm('Quitar Zona?') && deleteZone.mutate(z.id)} className="text-red-500 hover:bg-red-50 p-2 rounded"><Trash2 size={16}/></button>
                        </div>
                    ))}
                    {zones?.length === 0 && <p className="text-sm text-gray-400 italic text-center py-4">No hay zonas definidas.</p>}
                </div>
            </div>
        );
    };

    const renderMatrix = () => {
        if (!roles || !zones || !macros || !matrix) return <div className="p-8 text-center text-gray-400 animate-pulse">Cargando Matriz...</div>;
        
        if (roles.length === 0 || zones.length === 0) {
            return (
                <div className="bg-yellow-50 text-yellow-800 p-6 rounded-lg border border-yellow-200 flex flex-col items-center max-w-2xl mx-auto mt-8">
                    <AlertCircle size={32} className="mb-2 text-yellow-600" />
                    <h3 className="font-bold text-lg">Matriz No Disponible</h3>
                    <p className="text-sm">Necesitás definir al menos un Rol y una Zona para armar la matriz transversal.</p>
                </div>
            );
        }

        const getAssignedMacro = (roleId, zoneId) => {
            const assignment = matrix.find(m => m.role_id === roleId && m.zone_id === zoneId);
            return assignment ? assignment.policy_id : '';
        };

        return (
            <div className="bg-white rounded-lg shadow border overflow-hidden mt-4">
                <div className="p-6 border-b bg-slate-50 flex justify-between items-center">
                    <div>
                        <h3 className="text-xl font-black text-slate-800 mb-1 flex items-center gap-2"><Map className="text-purple-600"/> Matriz Transversal (RBAC x NAC)</h3>
                        <p className="text-sm text-gray-500">Asigná las "Macros de Política" según la intersección entre el Rol del Usuario (Fila) y la Zona del Hardware (Columna).</p>
                    </div>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse min-w-[800px]">
                        <thead>
                            <tr>
                                <th className="p-4 bg-slate-100 border-b border-r text-sm font-black text-slate-600 w-48 sticky left-0 z-10 shadow-[2px_0_0_0_#e2e8f0]">Roles \ Zonas</th>
                                {zones.map(z => (
                                    <th key={z.id} className="p-4 bg-slate-50 border-b border-r text-sm font-bold text-slate-700 text-center min-w-[200px] shadow-[inset_0_-2px_0_0_#cbd5e1]">
                                        {z.name}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {roles.map(r => (
                                <tr key={r.id} className="hover:bg-slate-50 transition-colors">
                                    <td className="p-4 border-b border-r bg-white font-bold text-indigo-700 sticky left-0 z-10 shadow-[2px_0_0_0_#e2e8f0]">
                                        {r.name}
                                    </td>
                                    {zones.map(z => {
                                        const currentVal = getAssignedMacro(r.id, z.id);
                                        return (
                                            <td key={z.id} className="p-3 border-b border-r text-center bg-white group hover:bg-indigo-50/30">
                                                <select 
                                                    className={`w-full border p-2 text-sm outline-none transition-colors rounded-md cursor-pointer
                                                        ${currentVal 
                                                            ? 'bg-purple-50 border-purple-200 text-purple-900 font-bold shadow-sm' 
                                                            : 'bg-gray-50 text-gray-400 border-gray-200 hover:border-gray-300'}`}
                                                    value={currentVal}
                                                    onChange={(e) => {
                                                        const p_id = e.target.value;
                                                        if(p_id) {
                                                            assignMatrix.mutate({ role_id: r.id, zone_id: z.id, policy_id: parseInt(p_id) });
                                                        }
                                                    }}
                                                >
                                                    <option value="">-- Denegado --</option>
                                                    {macros.map(m => (
                                                        <option key={m.id} value={m.id}>{m.name}</option>
                                                    ))}
                                                </select>
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        );
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex justify-between items-center bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                <div>
                    <h2 className="text-2xl font-black text-slate-800">Control IAM & Zonas</h2>
                    <p className="text-sm text-slate-500">Administración de identidades, zonas físicas de red y la matriz multidimensional N-Dimensional NAC.</p>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-6 border-b border-slate-200 px-2">
                <button 
                    onClick={() => setActiveTab('matrix')}
                    className={`pb-3 px-2 text-sm font-bold border-b-[3px] transition-colors ${activeTab === 'matrix' ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                >
                    Matriz Transversal
                </button>
                <button 
                    onClick={() => setActiveTab('roles')}
                    className={`pb-3 px-2 text-sm font-bold border-b-[3px] transition-colors ${activeTab === 'roles' ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                >
                    1. Definir Roles (Identity)
                </button>
                <button 
                    onClick={() => setActiveTab('zones')}
                    className={`pb-3 px-2 text-sm font-bold border-b-[3px] transition-colors ${activeTab === 'zones' ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                >
                    2. Definir Zonas (Hardware)
                </button>
            </div>

            {/* Content Container */}
            <div className="pt-2 animate-fadeIn">
                {activeTab === 'matrix' && renderMatrix()}
                {activeTab === 'roles' && renderRoles()}
                {activeTab === 'zones' && renderZones()}
            </div>
        </div>
    );
};

export default IAM;

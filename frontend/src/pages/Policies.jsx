import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { Plus, Trash2, ArrowRight, X, Search, FileText, ShieldAlert, Cpu, Save, Play, RefreshCw, Box } from 'lucide-react';

// --- SUB-COMPONENT: ATTRIBUTE SELECTOR ---
const AttributeSelector = ({ dictionary, onSelect }) => {
    const [selectedDict, setSelectedDict] = useState('');
    const [selectedAttr, setSelectedAttr] = useState('');
    const [op, setOp] = useState(':=');
    const [val, setVal] = useState('');

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
            onSelect({ name: selectedAttr, op, value: val }); // "name" instead of "attribute" to match JSON schema
            setVal('');
        }
    };

    if (!dictionary || dictionary.length === 0) {
        return <div className="p-4 bg-gray-50 border rounded text-xs text-gray-400 italic animate-pulse">Cargando diccionarios RADIUS...</div>;
    }

    return (
        <div className="bg-white p-5 rounded-xl border border-indigo-100 mb-6 shadow-sm flex flex-col md:flex-row gap-4">
            <div className="flex-1 space-y-3">
                <div className="flex gap-3">
                    <div className="flex-1">
                        <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest pl-1 block mb-1">Diccionario Vendor</label>
                        <select
                            className="w-full border p-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-300"
                            value={selectedDict}
                            onChange={e => { setSelectedDict(e.target.value); setSelectedAttr(''); }}
                        >
                            <option value="">-- Seleccionar Vendor --</option>
                            {sources.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                    </div>
                    <div className="flex-[2]">
                        <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest pl-1 block mb-1">Atributo Específico</label>
                        <select
                            className="w-full border p-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-300 disabled:opacity-50 disabled:bg-gray-100"
                            value={selectedAttr}
                            onChange={e => setSelectedAttr(e.target.value)}
                            disabled={!selectedDict}
                        >
                            <option value="">-- Buscar Atributo --</option>
                            {filteredAttributes.map(a => (
                                <option key={a.name} value={a.name}>
                                    {a.name} ({a.type})
                                </option>
                            ))}
                        </select>
                    </div>
                </div>
                <div className="flex gap-3 items-end">
                    <div className="w-24">
                        <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest pl-1 block mb-1">Operador</label>
                        <select className="w-full border p-2 rounded-lg text-sm bg-slate-50 font-mono text-center" value={op} onChange={e => setOp(e.target.value)}>
                            <option value=":=">:=</option>
                            <option value="=">=</option>
                            <option value="==">==</option>
                            <option value="+=">+=</option>
                        </select>
                    </div>
                    <div className="flex-1">
                        <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest pl-1 block mb-1">Valor VSA</label>
                        <input className="w-full border p-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-300 font-mono" placeholder="Ej: shell:priv-lvl=15" value={val} onChange={e => setVal(e.target.value)} />
                    </div>
                    <button 
                        onClick={handleAdd} 
                        disabled={!selectedAttr || !val} 
                        className="bg-indigo-600 text-white rounded-lg px-6 py-2 hover:bg-indigo-700 disabled:opacity-50 font-bold h-[38px] transition shadow-md"
                    >
                        Agregar VSA
                    </button>
                </div>
            </div>
        </div>
    );
};

// --- MAIN MACRO BUILDER COMPONENT ---
const PoliciesPage = () => {
    const queryClient = useQueryClient();
    const [viewMode, setViewMode] = useState('list'); // 'list' or 'edit'
    const [activeMacro, setActiveMacro] = useState(null); // the working copy of the macro for edit
    const [searchQuery, setSearchQuery] = useState('');
    const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
    const [wizardData, setWizardData] = useState({ name: '', description: '' });

    // Compile state tracking
    const [compileStatus, setCompileStatus] = useState({ id: null, msg: '', error: false });

    // --- DATA FETCHING ---
    const { data: macros, isLoading: macrosLoading } = useQuery({ 
        queryKey: ['iam', 'macros'], 
        queryFn: () => api.get('/iam-nac/macros').then(r => r.data) 
    });
    const { data: dictionaryAttributes } = useQuery({ 
        queryKey: ['dictionary', 'attributes'], 
        queryFn: () => api.get('/dictionary/attributes').then(r => r.data) 
    });

    // --- MUTATIONS ---
    const createMacro = useMutation({
        mutationFn: (data) => api.post('/iam-nac/macros', { 
            name: data.name, 
            description: data.description, 
            attributes_json: { attributes: [] } 
        }),
        onSuccess: () => {
            queryClient.invalidateQueries(['iam', 'macros']);
            setIsCreateModalOpen(false);
            setWizardData({ name: '', description: '' });
        }
    });

    const updateMacro = useMutation({
        mutationFn: (data) => api.put(`/iam-nac/macros/${data.id}`, data),
        onSuccess: (data) => {
            queryClient.invalidateQueries(['iam', 'macros']);
            setActiveMacro(data); // update local working copy
            alert('¡Macro Guardada Correctamente!');
        }
    });

    const deleteMacro = useMutation({
        mutationFn: (id) => api.delete(`/iam-nac/macros/${id}`),
        onSuccess: () => queryClient.invalidateQueries(['iam', 'macros'])
    });

    const compilePolicy = useMutation({
        mutationFn: (id) => api.post(`/iam-nac/compile/${id}`),
        onMutate: (id) => setCompileStatus({ id, msg: 'Compilando en NAS...', error: false }),
        onSuccess: (data, id) => {
            const compiled = data?.data?.attributes_compiled ?? 0;
            const groupName = data?.data?.compiled_group_name ?? '';
            setCompileStatus({ id, msg: `Compilación Exitosa. ${compiled} VSAs insertados → grupo "${groupName}" en RADIUS.`, error: false });
            setTimeout(() => setCompileStatus({ id: null, msg: '', error: false }), 5000);
        },
        onError: (err, id) => {
            setCompileStatus({ id, msg: `ERROR: ${err.response?.data?.detail || 'Fallo de compilación.'}`, error: true });
        }
    });

    // --- HANDLERS ---
    const handleAddAttribute = (attr) => {
        if (!activeMacro) return;
        const currentJson = activeMacro.attributes_json || { attributes: [] };
        const updatedMacro = {
            ...activeMacro,
            attributes_json: {
                ...currentJson,
                attributes: [...(currentJson.attributes || []), attr]
            }
        };
        setActiveMacro(updatedMacro);
    };

    const handleRemoveAttribute = (idx) => {
        if (!activeMacro) return;
        const currentJson = activeMacro.attributes_json || { attributes: [] };
        const updatedList = currentJson.attributes.filter((_, i) => i !== idx);
        const updatedMacro = {
            ...activeMacro,
            attributes_json: { ...currentJson, attributes: updatedList }
        };
        setActiveMacro(updatedMacro);
    };

    const handleSaveMacro = () => {
        if (!activeMacro) return;
        updateMacro.mutate(activeMacro);
    };

    // --- AGGREGATION ---
    const filteredMacros = useMemo(() => {
        if (!macros) return [];
        return macros.filter(m => 
            m.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
            (m.description || '').toLowerCase().includes(searchQuery.toLowerCase())
        );
    }, [macros, searchQuery]);

    // --- VIEW: LIST ---
    if (viewMode === 'list') {
        return (
            <div className="space-y-6 animate-fadeIn">
                <div className="flex justify-between items-center bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                    <div>
                        <h2 className="text-2xl font-black text-slate-800">Macro Policy Builder</h2>
                        <p className="text-sm text-slate-500">Diseñador visual de plantillas NAC de FreeRADIUS.</p>
                    </div>
                    <button
                        onClick={() => setIsCreateModalOpen(true)}
                        className="bg-indigo-600 text-white px-5 py-2 rounded-lg flex items-center gap-2 hover:bg-indigo-700 shadow font-bold"
                    >
                        <Plus size={18} /> Nueva Macro
                    </button>
                </div>

                <div className="flex gap-4 items-center">
                    <div className="relative flex-1 max-w-md">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                        <input
                            className="w-full pl-10 pr-4 py-3 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none shadow-sm"
                            placeholder="Buscar Macros por nombre..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filteredMacros.map(m => (
                        <div key={m.id} className="bg-white rounded-xl shadow border p-5 hover:shadow-lg transition-shadow border-t-4 border-t-indigo-500 relative group">
                            <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                                <Box className="text-indigo-400" size={18}/> {m.name}
                            </h3>
                            <p className="text-sm text-gray-500 mt-2 h-10 overflow-hidden">{m.description || <span className="italic text-gray-300">Sin descripción</span>}</p>
                            
                            <div className="mt-4 pt-4 border-t flex items-center justify-between">
                                <div className="text-xs font-bold text-gray-400 bg-gray-100 px-2 py-1 rounded">
                                    VSAs: {(m.attributes_json?.attributes || []).length}
                                </div>
                                <div className="flex gap-2">
                                    <button 
                                        onClick={() => { setActiveMacro(m); setViewMode('edit'); }}
                                        className="text-indigo-600 bg-indigo-50 px-3 py-1.5 rounded-md hover:bg-indigo-100 flex items-center gap-1 font-bold text-xs"
                                    >
                                        Diseñador
                                    </button>
                                </div>
                            </div>

                            {/* Hover Actions Float */}
                            <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                    onClick={() => compilePolicy.mutate(m.id)}
                                    title="Compilar en Core RADIUS"
                                    className="p-1.5 text-emerald-600 bg-emerald-50 rounded hover:bg-emerald-100"
                                >
                                    <Cpu size={16}/>
                                </button>
                                <button
                                    onClick={() => { if(window.confirm('Quemar esta Macro?')) deleteMacro.mutate(m.id); }}
                                    title="Eliminar"
                                    className="p-1.5 text-rose-500 bg-rose-50 rounded hover:bg-rose-100"
                                >
                                    <Trash2 size={16}/>
                                </button>
                            </div>

                            {/* Compilation Toast Overlay inside card */}
                            {compileStatus.id === m.id && (
                                <div className={`absolute bottom-0 left-0 right-0 p-2 text-xs font-bold text-center animate-slideUp
                                    ${compileStatus.error ? 'bg-rose-500 text-white' : 'bg-emerald-500 text-white'}`}>
                                    {compileStatus.msg}
                                </div>
                            )}
                        </div>
                    ))}
                    {filteredMacros.length === 0 && (
                        <div className="col-span-full py-12 text-center text-gray-400 font-bold">
                            No hay Macros definidas. Creá la primera para empezar a inyectar lógica NAC.
                        </div>
                    )}
                </div>

                {isCreateModalOpen && (
                    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4 z-50">
                        <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-2xl animate-fadeIn">
                            <h3 className="text-xl font-black mb-4 text-slate-800 flex items-center gap-2"><ShieldAlert className="text-indigo-600"/> Nueva Macro</h3>
                            <form onSubmit={(e) => { e.preventDefault(); createMacro.mutate(wizardData); }} className="space-y-4">
                                <div>
                                    <label className="text-xs font-black text-slate-500 uppercase tracking-widest pl-1">Nombre Unívoco</label>
                                    <input
                                        className="w-full mt-1 border rounded-lg p-3 outline-none focus:ring-2 focus:ring-indigo-500"
                                        placeholder="Ej: perfil_switches_core"
                                        value={wizardData.name}
                                        onChange={e => setWizardData({ ...wizardData, name: e.target.value.replace(/\s+/g, '_') })}
                                        required
                                    />
                                    <p className="text-[10px] items-center text-gray-400 mt-1 ml-1">Usar formato SNAKE_CASE, sin espacios.</p>
                                </div>
                                <div>
                                    <label className="text-xs font-black text-slate-500 uppercase tracking-widest pl-1">Propósito Comercial</label>
                                    <textarea
                                        className="w-full mt-1 border rounded-lg p-3 outline-none focus:ring-2 focus:ring-indigo-500 resize-none h-24"
                                        placeholder="Descripción funcional para el equipo de auditoría..."
                                        value={wizardData.description}
                                        onChange={e => setWizardData({ ...wizardData, description: e.target.value })}
                                    />
                                </div>
                                <div className="flex gap-2 justify-end pt-4 border-t">
                                    <button type="button" onClick={() => setIsCreateModalOpen(false)} className="px-4 py-2 text-gray-500 hover:bg-gray-100 rounded-lg font-bold">Cancelar</button>
                                    <button type="submit" className="px-6 py-2 bg-indigo-600 text-white font-black rounded-lg shadow-md hover:bg-indigo-700">Crear Base</button>
                                </div>
                            </form>
                        </div>
                    </div>
                )}
            </div>
        );
    }

    // --- VIEW: EDIT (BUILDER) ---
    if (!activeMacro) return null;
    const currentAttributes = activeMacro.attributes_json?.attributes || [];

    return (
        <div className="h-[calc(100vh-6rem)] flex flex-col bg-slate-50 rounded-lg overflow-hidden border border-slate-200 shadow-inner">
            {/* Header Toolbar */}
            <div className="bg-white p-4 border-b flex justify-between items-center z-10 shadow-sm relative">
                <div className="flex items-center gap-4">
                    <button onClick={() => setViewMode('list')} className="text-gray-400 hover:text-indigo-600 flex items-center gap-1 font-bold text-sm bg-gray-50 px-3 py-1.5 rounded-md border border-gray-100 transition-colors">
                        <ArrowRight className="rotate-180" size={16} /> Volver
                    </button>
                    <div className="h-6 w-px bg-slate-200"></div>
                    <div>
                        <input 
                            className="text-xl font-black text-slate-800 bg-transparent outline-none focus:border-b-2 focus:border-indigo-500 px-1 w-64 uppercase tracking-tight"
                            value={activeMacro.name}
                            onChange={(e) => setActiveMacro({...activeMacro, name: e.target.value.replace(/\s+/g, '_')})}
                            title="Editar Nombre de Macro"
                        />
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <button 
                        onClick={() => compilePolicy.mutate(activeMacro.id)}
                        className="bg-emerald-50 text-emerald-700 border border-emerald-200 px-4 py-2 rounded-lg font-bold hover:bg-emerald-100 flex items-center gap-2 shadow-sm transition-colors"
                        disabled={compilePolicy.isPending}
                    >
                        {compilePolicy.isPending ? <RefreshCw className="animate-spin" size={18}/> : <Cpu size={18} />} 
                        Compilar RADIUS
                    </button>
                    <button 
                        onClick={handleSaveMacro}
                        className="bg-indigo-600 text-white px-5 py-2 rounded-lg font-bold hover:bg-indigo-700 shadow-md flex items-center gap-2 transition-transform active:scale-95"
                    >
                        <Save size={18} /> Guardar (JSON)
                    </button>
                </div>
            </div>

            {/* Compile Overlay Notifier inside Edit */}
            {compileStatus.id === activeMacro.id && (
                <div className={`p-3 text-sm font-black text-center shadow-lg
                    ${compileStatus.error ? 'bg-rose-600 text-white' : 'bg-emerald-500 text-white'}`}>
                    {compileStatus.msg}
                </div>
            )}

            <div className="flex-1 overflow-y-auto p-6">
                <div className="max-w-5xl mx-auto space-y-6">
                    {/* Meta Info */}
                    <div className="bg-white border rounded-xl p-5 shadow-sm">
                        <label className="text-xs font-black text-slate-500 uppercase tracking-widest pl-1 mb-2 block">Descripción y Propósito Comercial</label>
                        <textarea
                            className="w-full bg-slate-50 border p-3 rounded-lg text-sm text-slate-700 outline-none focus:ring-2 focus:ring-indigo-200 resize-none h-20"
                            value={activeMacro.description}
                            onChange={(e) => setActiveMacro({...activeMacro, description: e.target.value})}
                        />
                    </div>

                    {/* VSA Builder */}
                    <div>
                        <h3 className="text-lg font-black text-slate-800 flex items-center gap-2 mb-4"><Box className="text-indigo-500" /> Atributos de Respuesta (VSA Matrix)</h3>
                        
                        <AttributeSelector 
                            dictionary={dictionaryAttributes} 
                            onSelect={handleAddAttribute} 
                        />

                        {/* Attribute List */}
                        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
                            <div className="bg-slate-100 border-b p-3 grid grid-cols-12 gap-4 text-xs font-black text-slate-500 uppercase tracking-widest">
                                <div className="col-span-5">Atributo RFC / Vendor</div>
                                <div className="col-span-2 text-center">Op</div>
                                <div className="col-span-4">Valor Inyectado</div>
                                <div className="col-span-1 text-center">Quitar</div>
                            </div>
                            
                            <div className="divide-y divide-slate-100">
                                {currentAttributes.map((attr, index) => (
                                    <div key={index} className="p-3 grid grid-cols-12 gap-4 items-center hover:bg-slate-50 transition-colors group">
                                        <div className="col-span-5 font-mono text-xs font-bold text-slate-700 break-words flex items-center gap-2">
                                            <div className="w-2 h-2 rounded-full bg-indigo-400 shrink-0"></div>
                                            {attr.name}
                                        </div>
                                        <div className="col-span-2 text-center">
                                            <span className="bg-indigo-50 text-indigo-700 font-mono text-xs px-2 py-1 rounded font-bold border border-indigo-100">{attr.op}</span>
                                        </div>
                                        <div className="col-span-4 font-mono text-xs text-sky-700 break-words bg-sky-50 px-2 py-1.5 rounded border border-sky-100">
                                            {attr.value}
                                        </div>
                                        <div className="col-span-1 flex justify-center">
                                            <button 
                                                onClick={() => handleRemoveAttribute(index)}
                                                className="p-1.5 text-slate-300 hover:text-rose-500 hover:bg-rose-50 rounded-md transition-all opacity-0 group-hover:opacity-100"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                                
                                {currentAttributes.length === 0 && (
                                    <div className="p-8 text-center text-slate-400 border-2 border-dashed border-slate-200 m-4 rounded-xl">
                                        <FileText size={48} className="mx-auto text-slate-200 mb-3" />
                                        <p className="font-bold text-slate-500">Macro Vacía</p>
                                        <p className="text-sm">Buscá y agregá atributos RADIUS usando el selector de arriba.</p>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Raw JSON viewer (Debug/Expert Mode hint) */}
                        <div className="mt-6 bg-slate-900 rounded-xl p-4 shadow-inner border border-slate-800">
                            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest pl-1 mb-2 block flex justify-between">
                                <span>Modo Crudo (JSON Backend Payload)</span>
                                <span className="text-emerald-500">Read Only</span>
                            </label>
                            <pre className="text-xs font-mono text-emerald-400 overflow-x-auto p-2 bg-black/30 rounded border border-slate-800/50">
                                {JSON.stringify(activeMacro.attributes_json, null, 2)}
                            </pre>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PoliciesPage;

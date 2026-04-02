import React, { useState, useMemo, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import GroupsService from '../services/groups';
import { Plus, Trash2, Search, ShieldAlert, Edit2, Folder, BookOpen, ChevronDown, X } from 'lucide-react';

// Combobox con búsqueda para atributos del diccionario
const AttributeCombobox = ({ options, value, onChange, disabled }) => {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState('');
    const containerRef = useRef(null);
    const inputRef = useRef(null);

    // Cerrar al clickar afuera
    useEffect(() => {
        const handler = (e) => {
            if (containerRef.current && !containerRef.current.contains(e.target)) {
                setOpen(false);
                setQuery('');
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    // Al abrir, hacer foco en el input de búsqueda
    useEffect(() => {
        if (open && inputRef.current) inputRef.current.focus();
    }, [open]);

    const filtered = useMemo(() => {
        if (!query) return options;
        const q = query.toLowerCase();
        return options.filter(o => o.name.toLowerCase().includes(q));
    }, [options, query]);

    const sistemaPart = filtered.filter(d => d.dictionary?.startsWith('[Sistema]'));
    const customPart  = filtered.filter(d => !d.dictionary?.startsWith('[Sistema]'));

    const selectedLabel = value
        ? options.find(o => o.name === value)?.name ?? value
        : 'Seleccionar atributo...';

    const handleSelect = (name) => {
        onChange(name);
        setOpen(false);
        setQuery('');
    };

    const handleClear = (e) => {
        e.stopPropagation();
        onChange('');
        setQuery('');
    };

    return (
        <div ref={containerRef} className="relative">
            {/* Trigger */}
            <button
                type="button"
                disabled={disabled}
                onClick={() => setOpen(o => !o)}
                className={`w-full mt-1 border rounded-lg p-2 flex items-center justify-between text-sm outline-none focus:ring-2 focus:ring-indigo-500 bg-white
                    ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:border-indigo-400'}
                    ${value ? 'text-slate-800' : 'text-slate-400'}`}
            >
                <span className="font-mono truncate">{selectedLabel}</span>
                <span className="flex items-center gap-1 ml-2 shrink-0">
                    {value && (
                        <span onClick={handleClear} className="text-slate-400 hover:text-rose-500 p-0.5 rounded">
                            <X size={12} />
                        </span>
                    )}
                    <ChevronDown size={14} className={`text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
                </span>
            </button>

            {/* Dropdown */}
            {open && (
                <div className="absolute z-50 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-xl overflow-hidden">
                    {/* Search input */}
                    <div className="p-2 border-b border-slate-100">
                        <div className="relative">
                            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                            <input
                                ref={inputRef}
                                type="text"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                placeholder="Buscar atributo..."
                                className="w-full pl-7 pr-3 py-1.5 text-sm border rounded-md outline-none focus:ring-2 focus:ring-indigo-400"
                            />
                        </div>
                    </div>

                    {/* Lista */}
                    <div className="max-h-52 overflow-y-auto text-sm">
                        {filtered.length === 0 ? (
                            <div className="px-3 py-4 text-center text-slate-400 text-xs">Sin resultados para "{query}"</div>
                        ) : (
                            <>
                                {sistemaPart.length > 0 && (
                                    <>
                                        <div className="px-3 py-1 text-xs font-black text-slate-400 uppercase tracking-widest bg-slate-50 sticky top-0">Sistema</div>
                                        {sistemaPart.map(o => (
                                            <button
                                                key={o.name}
                                                type="button"
                                                onClick={() => handleSelect(o.name)}
                                                className={`w-full text-left px-3 py-1.5 font-mono hover:bg-indigo-50 hover:text-indigo-700 transition-colors
                                                    ${value === o.name ? 'bg-indigo-50 text-indigo-700 font-bold' : 'text-slate-700'}`}
                                            >
                                                {o.name}
                                            </button>
                                        ))}
                                    </>
                                )}
                                {customPart.length > 0 && (
                                    <>
                                        <div className="px-3 py-1 text-xs font-black text-slate-400 uppercase tracking-widest bg-slate-50 sticky top-0">Custom</div>
                                        {customPart.map(o => (
                                            <button
                                                key={o.name}
                                                type="button"
                                                onClick={() => handleSelect(o.name)}
                                                className={`w-full text-left px-3 py-1.5 font-mono hover:bg-indigo-50 hover:text-indigo-700 transition-colors
                                                    ${value === o.name ? 'bg-indigo-50 text-indigo-700 font-bold' : 'text-slate-700'}`}
                                            >
                                                {o.name}
                                            </button>
                                        ))}
                                    </>
                                )}
                            </>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

// Combobox con búsqueda para vendors/diccionarios
const VendorCombobox = ({ options, value, onChange }) => {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState('');
    const containerRef = useRef(null);
    const inputRef = useRef(null);

    // Cerrar al clickar afuera
    useEffect(() => {
        const handler = (e) => {
            if (containerRef.current && !containerRef.current.contains(e.target)) {
                setOpen(false);
                setQuery('');
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    // Al abrir, hacer foco en el input de búsqueda
    useEffect(() => {
        if (open && inputRef.current) inputRef.current.focus();
    }, [open]);

    const filtered = useMemo(() => {
        if (!query) return options;
        const q = query.toLowerCase();
        return options.filter(o => o.toLowerCase().includes(q));
    }, [options, query]);

    const handleSelect = (val) => {
        onChange(val);
        setOpen(false);
        setQuery('');
    };

    const handleClear = (e) => {
        e.stopPropagation();
        onChange('');
        setQuery('');
    };

    return (
        <div ref={containerRef} className="relative">
            {/* Trigger */}
            <button
                type="button"
                onClick={() => setOpen(o => !o)}
                className={`w-full mt-1 border rounded-lg p-2 flex items-center justify-between text-sm outline-none focus:ring-2 focus:ring-indigo-500 bg-white cursor-pointer hover:border-indigo-400
                    ${value ? 'text-slate-800' : 'text-slate-400'}`}
            >
                <span className={value ? 'font-mono truncate' : 'truncate'}>
                    {value || 'Todos los diccionarios'}
                </span>
                <span className="flex items-center gap-1 ml-2 shrink-0">
                    {value && (
                        <span onClick={handleClear} className="text-slate-400 hover:text-rose-500 p-0.5 rounded">
                            <X size={12} />
                        </span>
                    )}
                    <ChevronDown size={14} className={`text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
                </span>
            </button>

            {/* Dropdown */}
            {open && (
                <div className="absolute z-50 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-xl overflow-hidden">
                    {/* Search input */}
                    <div className="p-2 border-b border-slate-100">
                        <div className="relative">
                            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                            <input
                                ref={inputRef}
                                type="text"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                placeholder="Buscar diccionario..."
                                className="w-full pl-7 pr-3 py-1.5 text-sm border rounded-md outline-none focus:ring-2 focus:ring-indigo-400"
                            />
                        </div>
                    </div>

                    {/* Lista */}
                    <div className="max-h-52 overflow-y-auto text-sm">
                        {filtered.length === 0 ? (
                            <div className="px-3 py-4 text-center text-slate-400 text-xs">Sin resultados para "{query}"</div>
                        ) : (
                            <>
                                <button
                                    type="button"
                                    onClick={() => handleSelect('')}
                                    className={`w-full text-left px-3 py-1.5 hover:bg-indigo-50 hover:text-indigo-700 transition-colors
                                        ${value === '' ? 'bg-indigo-50 text-indigo-700 font-bold' : 'text-slate-400'}`}
                                >
                                    Todos los diccionarios
                                </button>
                                {filtered.map(o => (
                                    <button
                                        key={o}
                                        type="button"
                                        onClick={() => handleSelect(o)}
                                        className={`w-full text-left px-3 py-1.5 font-mono hover:bg-indigo-50 hover:text-indigo-700 transition-colors
                                            ${value === o ? 'bg-indigo-50 text-indigo-700 font-bold' : 'text-slate-700'}`}
                                    >
                                        {o}
                                    </button>
                                ))}
                            </>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

const PoliciesPage = () => {
    const queryClient = useQueryClient();
    const [selectedGroup, setSelectedGroup] = useState(null);
    const [groupSearchQuery, setGroupSearchQuery] = useState('');
    const [isEditGroupModalOpen, setIsEditGroupModalOpen] = useState(false);
    const [groupFormData, setGroupFormData] = useState({ oldName: '', newName: '' });
    const [isAttributeModalOpen, setIsAttributeModalOpen] = useState(false);
    const [attributeFormData, setAttributeFormData] = useState({
        type: 'reply',
        groupname: '',
        attribute: '',
        op: ':=',
        value: '',
        editId: null
    });
    
    // Create group modal state
    const [isCreateGroupModalOpen, setIsCreateGroupModalOpen] = useState(false);
    const [newGroupName, setNewGroupName] = useState('');

    // Dictionary selector state
    const [selectedVendor, setSelectedVendor] = useState('');

    // Fetch dictionary attributes
    const { data: dictionaryAttributes } = useQuery({
        queryKey: ['dictionary', 'attributes'],
        queryFn: () => api.get('/dictionary/attributes').then(r => r.data)
    });

    // Get unique vendors from dictionary
    const vendors = useMemo(() => {
        if (!dictionaryAttributes) return [];
        const vSet = new Set(dictionaryAttributes.map(d => d.dictionary || 'Unknown'));
        return Array.from(vSet).sort();
    }, [dictionaryAttributes]);

    // Get attributes for selected vendor
    const vendorAttributes = useMemo(() => {
        if (!dictionaryAttributes || !selectedVendor) return [];
        return dictionaryAttributes.filter(d => d.dictionary === selectedVendor);
    }, [dictionaryAttributes, selectedVendor]);

    // All attribute options: all dict attrs when no vendor filter, else filtered by vendor
    const allAttributeOptions = useMemo(() => {
        if (!dictionaryAttributes) return [];
        if (!selectedVendor) return dictionaryAttributes;
        return dictionaryAttributes.filter(d => d.dictionary === selectedVendor);
    }, [dictionaryAttributes, selectedVendor]);

    const { data: rawGroups, isLoading } = useQuery({
        queryKey: ['groups', 'list'],
        queryFn: () => api.get('/groups/list').then(r => r.data)
    });

    const { data: groupDetails } = useQuery({
        queryKey: ['groups', 'by-name', selectedGroup],
        queryFn: () => GroupsService.getGroupByName(selectedGroup),
        enabled: !!selectedGroup
    });

    const renameGroupMutation = useMutation({
        mutationFn: ({ oldName, newName }) => GroupsService.renameGroup(oldName, newName),
        onSuccess: () => {
            queryClient.invalidateQueries(['groups', 'list']);
            setSelectedGroup(groupFormData.newName);
            setIsEditGroupModalOpen(false);
            setGroupFormData({ oldName: '', newName: '' });
            alert('Grupo renombrado correctamente');
        },
        onError: (err) => alert(err.response?.data?.detail || 'Error al renombrar')
    });

    const deleteGroupReplyMutation = useMutation({
        mutationFn: (id) => GroupsService.deleteGroupReply(id),
        onSuccess: () => queryClient.invalidateQueries(['groups', 'by-name', selectedGroup])
    });

    const deleteGroupCheckMutation = useMutation({
        mutationFn: (id) => GroupsService.deleteGroupCheck(id),
        onSuccess: () => queryClient.invalidateQueries(['groups', 'by-name', selectedGroup])
    });

    const createGroupAttributeMutation = useMutation({
        mutationFn: (data) => data.type === 'reply' 
            ? GroupsService.createGroupReply(data) 
            : GroupsService.createGroupCheck(data),
        onSuccess: () => {
            queryClient.invalidateQueries(['groups', 'by-name', selectedGroup]);
            setIsAttributeModalOpen(false);
            setAttributeFormData({ type: 'reply', groupname: '', attribute: '', op: ':=', value: '', editId: null });
        },
        onError: (err) => alert(err.response?.data?.detail || 'Error al crear atributo')
    });

    const updateGroupAttributeMutation = useMutation({
        mutationFn: ({ id, type, data }) => type === 'reply' 
            ? GroupsService.updateGroupReply(id, data) 
            : GroupsService.updateGroupCheck(id, data),
        onSuccess: () => {
            queryClient.invalidateQueries(['groups', 'by-name', selectedGroup]);
            setIsAttributeModalOpen(false);
            setAttributeFormData({ type: 'reply', groupname: '', attribute: '', op: ':=', value: '', editId: null });
        },
        onError: (err) => alert(err.response?.data?.detail || 'Error al actualizar atributo')
    });

    const createGroupMutation = useMutation({
        mutationFn: async (groupname) => {
            await GroupsService.createGroupReply({
                groupname,
                attribute: 'Description',
                op: ':=',
                value: 'Created via UI'
            });
        },
        onSuccess: () => {
            queryClient.invalidateQueries(['groups', 'list']);
            setIsCreateGroupModalOpen(false);
            setNewGroupName('');
            alert('Grupo creado');
        },
        onError: (err) => alert(err.response?.data?.detail || 'Error al crear grupo')
    });

    const deleteEntireGroupMutation = useMutation({
        mutationFn: async (groupname) => {
            await api.delete(`/groups/policy?groupname=${groupname}`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries(['groups', 'list']);
            setSelectedGroup(null);
            alert('Grupo eliminado');
        },
        onError: (err) => alert(err.response?.data?.detail || 'Error al eliminar grupo')
    });

    const filteredGroups = (rawGroups || []).filter(g => 
        !groupSearchQuery || g.groupname.toLowerCase().includes(groupSearchQuery.toLowerCase())
    );

    return (
        <div className="space-y-6 animate-fadeIn">
            <div className="flex justify-between items-center bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                <div>
                    <h2 className="text-2xl font-black text-slate-800">Grupos RADIUS</h2>
                    <p className="text-sm text-slate-500">Gestión de grupos y atributos FreeRADIUS.</p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => setIsCreateGroupModalOpen(true)}
                        className="bg-indigo-600 text-white px-5 py-2 rounded-lg flex items-center gap-2 hover:bg-indigo-700 shadow font-bold"
                    >
                        <Plus size={18} /> Nuevo Grupo
                    </button>
                    <button
                        onClick={() => { 
                            if (!selectedGroup) return;
                            setAttributeFormData({ type: 'reply', groupname: selectedGroup, attribute: '', op: ':=', value: '', editId: null }); 
                            setIsAttributeModalOpen(true); 
                        }}
                        disabled={!selectedGroup}
                        className="bg-emerald-600 text-white px-5 py-2 rounded-lg flex items-center gap-2 hover:bg-emerald-700 shadow font-bold disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <Plus size={18} /> Agregar Atributo
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="bg-white rounded-xl shadow border p-4">
                    <h3 className="text-sm font-black text-slate-500 uppercase tracking-widest mb-3">Grupos Existentes</h3>
                    <div className="relative mb-3">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                        <input
                            className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                            placeholder="Buscar grupo..."
                            value={groupSearchQuery}
                            onChange={(e) => setGroupSearchQuery(e.target.value)}
                        />
                    </div>
                    <div className="space-y-1 max-h-[500px] overflow-y-auto">
                        {isLoading ? (
                            <div className="text-center text-gray-400 py-4">Cargando...</div>
                        ) : filteredGroups.length === 0 ? (
                            <div className="text-center text-gray-400 py-4">No hay grupos</div>
                        ) : (
                            filteredGroups.map(g => (
                                <div key={g.groupname} className={`p-3 rounded-lg cursor-pointer transition-colors flex items-center justify-between ${selectedGroup === g.groupname ? 'bg-indigo-50 border border-indigo-200' : 'hover:bg-slate-50 border border-transparent'}`}>
                                    <div onClick={() => setSelectedGroup(g.groupname)} className="flex-1">
                                        <div className="font-bold text-sm text-slate-700">{g.groupname}</div>
                                    </div>
                                    <button
                                        onClick={(e) => { e.stopPropagation(); setGroupFormData({ oldName: g.groupname, newName: g.groupname }); setIsEditGroupModalOpen(true); }}
                                        className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded"
                                        title="Renombrar"
                                    >
                                        <Edit2 size={14} />
                                    </button>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                <div className="col-span-2 bg-white rounded-xl shadow border p-4">
                    {!selectedGroup ? (
                        <div className="text-center text-gray-400 py-12">
                            <Folder size={48} className="mx-auto text-gray-200 mb-3" />
                            <p className="font-bold">Seleccioná un grupo</p>
                            <p className="text-sm">para ver y editar sus atributos</p>
                        </div>
                    ) : (
                        <>
                            <div className="flex justify-between items-center mb-4">
                                <h3 className="text-lg font-black text-slate-800">{selectedGroup}</h3>
                                <button
                                    onClick={() => { if(window.confirm(`¿Eliminar grupo "${selectedGroup}"?`)) deleteEntireGroupMutation.mutate(selectedGroup); }}
                                    className="text-rose-500 hover:bg-rose-50 p-2 rounded"
                                    title="Eliminar Grupo"
                                >
                                    <Trash2 size={18} />
                                </button>
                            </div>

                            <div className="mb-6">
                                <h4 className="text-sm font-black text-slate-500 uppercase tracking-widest mb-2 flex items-center gap-2">
                                    <ShieldAlert size={14} className="text-emerald-600"/> Atributos de Respuesta (Reply)
                                </h4>
                                <div className="border rounded-lg overflow-hidden">
                                    <div className="bg-slate-100 p-2 grid grid-cols-12 gap-2 text-xs font-black text-slate-500">
                                        <div className="col-span-4">Atributo</div>
                                        <div className="col-span-2 text-center">Op</div>
                                        <div className="col-span-5">Valor</div>
                                        <div className="col-span-1"></div>
                                    </div>
                                    <div className="divide-y">
                                        {(groupDetails?.replies || []).map(r => (
                                            <div key={r.id} className="p-2 grid grid-cols-12 gap-2 items-center text-sm hover:bg-slate-50">
                                                <div className="col-span-4 font-mono text-slate-700">{r.attribute}</div>
                                                <div className="col-span-2 text-center"><span className="bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded font-mono text-xs">{r.op}</span></div>
                                                <div className="col-span-5 font-mono text-slate-600 truncate" title={r.value}>{r.value}</div>
                                                <div className="col-span-1 flex gap-1 justify-end">
                                                    <button onClick={() => { setAttributeFormData({ type: 'reply', groupname: selectedGroup, attribute: r.attribute, op: r.op, value: r.value, editId: r.id }); setIsAttributeModalOpen(true); }} className="p-1 text-slate-400 hover:text-indigo-600"><Edit2 size={14} /></button>
                                                    <button onClick={() => deleteGroupReplyMutation.mutate(r.id)} className="p-1 text-slate-400 hover:text-rose-500"><Trash2 size={14} /></button>
                                                </div>
                                            </div>
                                        ))}
                                        {(groupDetails?.replies || []).length === 0 && <div className="p-4 text-center text-gray-400 text-sm">Sin atributos de respuesta</div>}
                                    </div>
                                </div>
                            </div>

                            <div>
                                <h4 className="text-sm font-black text-slate-500 uppercase tracking-widest mb-2 flex items-center gap-2">
                                    <Search size={14} className="text-amber-600"/> Atributos de Verificación (Check)
                                </h4>
                                <div className="border rounded-lg overflow-hidden">
                                    <div className="bg-slate-100 p-2 grid grid-cols-12 gap-2 text-xs font-black text-slate-500">
                                        <div className="col-span-4">Atributo</div>
                                        <div className="col-span-2 text-center">Op</div>
                                        <div className="col-span-5">Valor</div>
                                        <div className="col-span-1"></div>
                                    </div>
                                    <div className="divide-y">
                                        {(groupDetails?.checks || []).map(c => (
                                            <div key={c.id} className="p-2 grid grid-cols-12 gap-2 items-center text-sm hover:bg-slate-50">
                                                <div className="col-span-4 font-mono text-slate-700">{c.attribute}</div>
                                                <div className="col-span-2 text-center"><span className="bg-amber-50 text-amber-700 px-2 py-0.5 rounded font-mono text-xs">{c.op}</span></div>
                                                <div className="col-span-5 font-mono text-slate-600 truncate" title={c.value}>{c.value}</div>
                                                <div className="col-span-1 flex gap-1 justify-end">
                                                    <button onClick={() => { setAttributeFormData({ type: 'check', groupname: selectedGroup, attribute: c.attribute, op: c.op, value: c.value, editId: c.id }); setIsAttributeModalOpen(true); }} className="p-1 text-slate-400 hover:text-indigo-600"><Edit2 size={14} /></button>
                                                    <button onClick={() => deleteGroupCheckMutation.mutate(c.id)} className="p-1 text-slate-400 hover:text-rose-500"><Trash2 size={14} /></button>
                                                </div>
                                            </div>
                                        ))}
                                        {(groupDetails?.checks || []).length === 0 && <div className="p-4 text-center text-gray-400 text-sm">Sin atributos de verificación</div>}
                                    </div>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>

            {isEditGroupModalOpen && (
                <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-2xl">
                        <h3 className="text-xl font-black mb-4 text-slate-800 flex items-center gap-2"><Edit2 className="text-indigo-600"/> Renombrar Grupo</h3>
                        <div>
                            <label className="text-xs font-black text-slate-500 uppercase">Nombre Actual</label>
                            <input className="w-full mt-1 border rounded-lg p-3 bg-slate-100 font-mono" value={groupFormData.oldName} disabled />
                        </div>
                        <div className="mt-3">
                            <label className="text-xs font-black text-slate-500 uppercase">Nuevo Nombre</label>
                            <input
                                className="w-full mt-1 border rounded-lg p-3 outline-none focus:ring-2 focus:ring-indigo-500"
                                value={groupFormData.newName}
                                onChange={(e) => setGroupFormData({ ...groupFormData, newName: e.target.value.replace(/\s+/g, '_') })}
                            />
                        </div>
                        <div className="flex gap-2 justify-end pt-4 border-t mt-4">
                            <button type="button" onClick={() => setIsEditGroupModalOpen(false)} className="px-4 py-2 text-gray-500 hover:bg-gray-100 rounded-lg font-bold">Cancelar</button>
                            <button type="button" onClick={() => renameGroupMutation.mutate({ oldName: groupFormData.oldName, newName: groupFormData.newName })} className="px-6 py-2 bg-indigo-600 text-white font-black rounded-lg">Guardar</button>
                        </div>
                    </div>
                </div>
            )}

            {isCreateGroupModalOpen && (
                <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-2xl">
                        <h3 className="text-xl font-black mb-4 text-slate-800 flex items-center gap-2"><Plus className="text-indigo-600"/> Nuevo Grupo</h3>
                        <div>
                            <label className="text-xs font-black text-slate-500 uppercase">Nombre del Grupo</label>
                            <input
                                className="w-full mt-1 border rounded-lg p-3 outline-none focus:ring-2 focus:ring-indigo-500"
                                value={newGroupName}
                                onChange={(e) => setNewGroupName(e.target.value.replace(/\s+/g, '_'))}
                                placeholder="Ej: mi_nuevo_grupo"
                                autoFocus
                            />
                        </div>
                        <div className="flex gap-2 justify-end pt-4 border-t mt-4">
                            <button type="button" onClick={() => { setIsCreateGroupModalOpen(false); setNewGroupName(''); }} className="px-4 py-2 text-gray-500 hover:bg-gray-100 rounded-lg font-bold">Cancelar</button>
                            <button
                                type="button"
                                onClick={() => createGroupMutation.mutate(newGroupName.trim())}
                                disabled={newGroupName.trim() === ''}
                                className="px-6 py-2 bg-indigo-600 text-white font-black rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                            >Crear</button>
                        </div>
                    </div>
                </div>
            )}

            {isAttributeModalOpen && (
                <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-2xl">
                        <h3 className="text-xl font-black mb-4 text-slate-800 flex items-center gap-2">
                            {attributeFormData.editId ? <Edit2 className="text-indigo-600"/> : <Plus className="text-indigo-600"/>}
                            {attributeFormData.editId ? 'Editar' : 'Agregar'} Atributo
                        </h3>
                        <form onSubmit={(e) => { e.preventDefault(); if(attributeFormData.editId) { updateGroupAttributeMutation.mutate({ id: attributeFormData.editId, type: attributeFormData.type, data: attributeFormData }); } else { createGroupAttributeMutation.mutate(attributeFormData); }}} className="space-y-3">
                            <div>
                                <label className="text-xs font-black text-slate-500 uppercase">Diccionario (Vendor)</label>
                                <VendorCombobox
                                    options={vendors}
                                    value={selectedVendor}
                                    onChange={(val) => setSelectedVendor(val)}
                                />
                            </div>
                            <div>
                                <label className="text-xs font-black text-slate-500 uppercase">Tipo</label>
                                <select className="w-full mt-1 border rounded-lg p-2" value={attributeFormData.type} onChange={(e) => setAttributeFormData({ ...attributeFormData, type: e.target.value })}>
                                    <option value="reply">Reply (Respuesta)</option>
                                    <option value="check">Check (Verificación)</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-xs font-black text-slate-500 uppercase">Atributo</label>
                                <AttributeCombobox
                                    options={allAttributeOptions}
                                    value={attributeFormData.attribute}
                                    onChange={(val) => setAttributeFormData({ ...attributeFormData, attribute: val })}
                                    disabled={allAttributeOptions.length === 0}
                                />
                            </div>
                            <div>
                                <label className="text-xs font-black text-slate-500 uppercase">Operador</label>
                                <select className="w-full mt-1 border rounded-lg p-2" value={attributeFormData.op} onChange={(e) => setAttributeFormData({ ...attributeFormData, op: e.target.value })}>
                                    <option value=":=">:=</option>
                                    <option value="=">=</option>
                                    <option value="==">==</option>
                                    <option value="+=">+=</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-xs font-black text-slate-500 uppercase">Valor</label>
                                <input className="w-full mt-1 border rounded-lg p-2 outline-none focus:ring-2 focus:ring-indigo-500" placeholder="Valor" value={attributeFormData.value} onChange={(e) => setAttributeFormData({ ...attributeFormData, value: e.target.value })} required />
                            </div>
                            <div className="flex gap-2 justify-end pt-3 border-t">
                                <button type="button" onClick={() => setIsAttributeModalOpen(false)} className="px-4 py-2 text-gray-500 hover:bg-gray-100 rounded-lg font-bold">Cancelar</button>
                                <button type="submit" className="px-6 py-2 bg-indigo-600 text-white font-black rounded-lg">{attributeFormData.editId ? 'Actualizar' : 'Agregar'}</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default PoliciesPage;

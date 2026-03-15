import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api';
import { ShieldAlert, ShieldCheck, History, UserCog, Activity, Search, ChevronLeft, ChevronRight, Eye, X, Info, ArrowRight, Database, Hash, Type, Plus, Trash2, Edit2, Server, Download } from 'lucide-react';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { useAuth } from '../context/AuthContext';

dayjs.extend(relativeTime);

const AuditPage = () => {
    const [tab, setTab] = useState('access'); // 'access' or 'admin'
    const [search, setSearch] = useState('');
    const [nasIpFilter, setNasIpFilter] = useState('');
    const [page, setPage] = useState(0);
    const [selectedLog, setSelectedLog] = useState(null);
    const limit = 25;
    const { hasRole } = useAuth();
    const canExport = hasRole(['superadmin', 'admin', 'auditor']);

    useEffect(() => {
        setPage(0);
    }, [tab, search, nasIpFilter]);

    const buildAccessQueryParams = () => {
        const params = new URLSearchParams();
        params.append('skip', page * limit);
        params.append('limit', limit);
        if (search) params.append('search', search);
        if (nasIpFilter) params.append('nas_ip', nasIpFilter);
        return params.toString();
    };

    const { data: accessLogs, isLoading: isLoadingAccess } = useQuery({
        queryKey: ['audit', 'access', page, search, nasIpFilter],
        queryFn: () => api.get(`/audit/access?${buildAccessQueryParams()}`).then(r => r.data),
        enabled: tab === 'access',
        placeholderData: (previousData) => previousData
    });

    const { data: adminLogs, isLoading: isLoadingAdmin } = useQuery({
        queryKey: ['audit', 'admin', page, search],
        queryFn: () => api.get(`/audit/admin?skip=${page * limit}&limit=${limit}&search=${search}`).then(r => r.data),
        enabled: tab === 'admin',
        placeholderData: (previousData) => previousData
    });

    const isLoading = tab === 'access' ? isLoadingAccess : isLoadingAdmin;
    const logs = tab === 'access' ? accessLogs : adminLogs;

    const formatTime = (dateStr) => {
        const d = dayjs(dateStr);
        return {
            full: d.format('DD MMM YYYY, HH:mm:ss'),
            relative: d.fromNow(),
            tz: Intl.DateTimeFormat().resolvedOptions().timeZone
        };
    };

    const handleExport = (format) => {
        const token = localStorage.getItem('token');
        const url = `/api/audit/export?format=${format}`;
        const a = document.createElement('a');
        a.href = url;
        a.download = `audit_export.${format}`;
        fetch(url, { headers: { Authorization: `Bearer ${token}` } })
            .then(r => r.blob())
            .then(blob => {
                const objUrl = URL.createObjectURL(blob);
                a.href = objUrl;
                a.click();
                URL.revokeObjectURL(objUrl);
            });
    };

    const renderObject = (obj, colorClass) => {
        if (!obj) return null;
        const entries = typeof obj === 'object' ? Object.entries(obj) : [];

        if (entries.length === 0) return <div className="text-slate-400 italic">No detailed attributes</div>;

        return (
            <div className={`grid grid-cols-1 gap-2`}>
                {entries.map(([key, value]) => (
                    <div key={key} className={`flex items-center gap-3 p-3 rounded-xl border ${colorClass} bg-white/50 backdrop-blur-sm`}>
                        <div className="flex-1">
                            <label className="block text-[8px] font-black opacity-40 uppercase tracking-widest leading-none mb-1">{key}</label>
                            <div className="text-sm font-bold truncate" title={String(value)}>{String(value) || <span className="text-slate-300 italic font-medium">Empty Value</span>}</div>
                        </div>
                    </div>
                ))}
            </div>
        );
    };

    const renderDiffView = (log) => {
        const parse = (v) => {
            try { return JSON.parse(v); } catch (e) { return v; }
        };

        const oldData = parse(log.old_value);
        const newData = parse(log.new_value);

        return (
            <div className="space-y-6">
                {/* Visual Summary Card */}
                <div className={`p-4 rounded-2xl border-2 border-dashed flex items-center justify-between ${log.action === 'CREATE' ? 'border-indigo-100 bg-indigo-50/30' :
                    log.action === 'DELETE' ? 'border-rose-100 bg-rose-50/30' : 'border-amber-100 bg-amber-50/30'
                    }`}>
                    <div className="flex items-center gap-4">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${log.action === 'CREATE' ? 'bg-indigo-600 text-white' :
                            log.action === 'DELETE' ? 'bg-rose-600 text-white' : 'bg-amber-600 text-white'
                            }`}>
                            <Database size={20} />
                        </div>
                        <div>
                            <div className="text-xs font-black uppercase text-slate-800 tracking-wider">
                                {log.action === 'CREATE' ? 'New Entry Created' : log.action === 'DELETE' ? 'Record Removed' : 'Information Updated'}
                            </div>
                            <p className="text-[10px] text-slate-500 font-medium">Effect on table: <span className="font-bold text-slate-700">{log.table_affected}</span></p>
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="text-[10px] font-black text-slate-400 uppercase leading-none">Affected Subject</div>
                        <div className="text-lg font-black text-slate-800 tracking-tighter">{log.target_user || 'Global System'}</div>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-start">
                    {/* LEFT PANEL: BEFORE */}
                    {(log.action === 'DELETE' || log.action === 'UPDATE') && (
                        <div className="space-y-3">
                            <div className="flex items-center justify-between px-1">
                                <label className="text-[10px] font-black text-rose-500 uppercase tracking-widest">Original Data (-)</label>
                                <span className="text-[10px] font-bold text-slate-400 bg-slate-100 px-2 rounded">v.prev</span>
                            </div>
                            <div className="bg-rose-50/50 p-4 rounded-2xl border border-rose-100/50 space-y-4 shadow-inner">
                                {renderObject(oldData, "border-rose-100 text-rose-800")}
                            </div>
                        </div>
                    )}

                    {/* RIGHT PANEL: AFTER */}
                    {(log.action === 'CREATE' || log.action === 'UPDATE') && (
                        <div className="space-y-3">
                            <div className="flex items-center justify-between px-1">
                                <label className="text-[10px] font-black text-emerald-600 uppercase tracking-widest">New Deployment (+)</label>
                                <span className="text-[10px] font-bold text-slate-400 bg-slate-100 px-2 rounded">v.current</span>
                            </div>
                            <div className="bg-emerald-50/50 p-4 rounded-2xl border border-emerald-100/50 space-y-4 shadow-inner">
                                {renderObject(newData, "border-emerald-100 text-emerald-800")}
                            </div>
                        </div>
                    )}
                </div>

                {!oldData && !newData && <div className="p-12 bg-slate-50 rounded-3xl text-slate-400 italic text-center text-sm font-medium border-2 border-dashed border-slate-100">No attribute payload stored for this specific event.</div>}
            </div>
        );
    };

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-10 px-4">
            {/* Global Header */}
            <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6 py-4">
                <div>
                    <h2 className="text-3xl font-extrabold text-slate-800 tracking-tight flex items-center gap-3">
                        <History className="text-indigo-600" size={32} />
                        System Audit
                    </h2>
                    <p className="text-slate-500 mt-1 uppercase text-[10px] font-black tracking-widest opacity-60">Full Governance & Activity Traceability</p>
                </div>

                <div className="flex flex-col sm:flex-row gap-4 items-center">
                    <div className="flex p-1 bg-slate-100 rounded-xl w-full sm:w-fit shadow-inner">
                        <button
                            onClick={() => setTab('access')}
                            className={`flex-1 sm:flex-none flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg font-black transition-all text-xs ${tab === 'access' ? 'bg-white shadow-lg shadow-indigo-100 text-indigo-600' : 'text-slate-500 hover:text-slate-700'}`}
                        >
                            <Activity size={16} />
                            RADIUS ACCESS
                        </button>
                        <button
                            onClick={() => setTab('admin')}
                            className={`flex-1 sm:flex-none flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg font-black transition-all text-xs ${tab === 'admin' ? 'bg-white shadow-lg shadow-indigo-100 text-indigo-600' : 'text-slate-500 hover:text-slate-700'}`}
                        >
                            <UserCog size={16} />
                            ADMIN ACTIONS
                        </button>
                    </div>

                    <div className="relative w-full sm:w-64">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                        <input
                            placeholder={`Filter ${tab === 'access' ? 'identities' : 'actions'}...`}
                            className="pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 w-full transition-all shadow-sm focus:shadow-md"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>

                    {/* NAS IP filter — access tab only */}
                    {tab === 'access' && (
                        <div className="relative w-full sm:w-48">
                            <Server className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                            <input
                                placeholder="Filter NAS IP..."
                                className="pl-9 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 w-full transition-all shadow-sm focus:shadow-md text-sm"
                                value={nasIpFilter}
                                onChange={(e) => setNasIpFilter(e.target.value)}
                            />
                        </div>
                    )}

                    {/* SIEM Export button — auditor/admin/superadmin only */}
                    {canExport && (
                        <div className="relative group">
                            <button className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-xl font-black text-xs hover:bg-indigo-700 transition-colors shadow-sm">
                                <Download size={16} />
                                EXPORT
                            </button>
                            <div className="absolute right-0 top-full mt-1 bg-white border border-slate-200 rounded-xl shadow-lg overflow-hidden z-10 hidden group-hover:block">
                                <button
                                    onClick={() => handleExport('json')}
                                    className="block w-full px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 text-left"
                                >
                                    Export JSON
                                </button>
                                <button
                                    onClick={() => handleExport('csv')}
                                    className="block w-full px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 text-left"
                                >
                                    Export CSV
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <div className="bg-white rounded-3xl shadow-xl border border-slate-200 overflow-hidden ring-1 ring-slate-100">
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                            {tab === 'access' ? (
                                <tr>
                                    <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">Observed Time</th>
                                    <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">Identity</th>
                                    <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">Auth Result</th>
                                    <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">NAS IP</th>
                                    <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">Calling Station</th>
                                    <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">Event Source</th>
                                    <th className="px-6 py-5 text-center text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b w-20">Details</th>
                                </tr>
                            ) : (
                                <tr>
                                    <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b w-56">Transaction Time</th>
                                    <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">Operator</th>
                                    <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">Method</th>
                                    <th className="px-6 py-5 text-left text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b">Subject</th>
                                    <th className="px-6 py-5 text-center text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] border-b w-20">Inspect</th>
                                </tr>
                            )}
                        </thead>
                        <tbody className="divide-y divide-slate-100 bg-white">
                            {isLoading && !logs ? (
                                <tr><td colSpan="7" className="px-6 py-24 text-center"><div className="flex flex-col items-center gap-4"><div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div><span className="font-bold text-slate-500 text-lg">Retrieving Audit Data...</span></div></td></tr>
                            ) : logs?.length === 0 ? (
                                <tr><td colSpan="7" className="px-6 py-24 text-center"><div className="flex flex-col items-center gap-4 opacity-40"><div className="p-5 bg-slate-100 rounded-3xl"><History size={64} /></div><span className="text-xl font-bold">No Audit Footprint</span></div></td></tr>
                            ) : (
                                logs?.map(log => {
                                    const time = formatTime(tab === 'access' ? log.authdate : log.timestamp);
                                    return (
                                        <tr key={log.id} className="hover:bg-slate-50/70 transition-colors group">
                                            {tab === 'access' ? (
                                                <>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <div className="text-sm font-bold text-slate-600">{time.full}</div>
                                                        <div className="text-[9px] font-black text-slate-400 uppercase tracking-tighter flex items-center gap-1">
                                                            {time.relative} • {time.tz}
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-black text-slate-800">{log.username}</td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <span className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-tighter shadow-sm border ${log.reply === 'Access-Accept' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 'bg-rose-50 text-rose-700 border-rose-100'}`}>
                                                            {log.reply === 'Access-Accept' ? <ShieldCheck size={12} /> : <ShieldAlert size={12} />}
                                                            {log.reply}
                                                        </span>
                                                    </td>
                                                    {/* T28 — NAS IP column */}
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        {log.nas_ip_address ? (
                                                            <span className="text-xs font-mono text-slate-700 bg-slate-100 px-2 py-1 rounded">
                                                                {log.nas_ip_address}
                                                            </span>
                                                        ) : (
                                                            <span className="text-slate-300 text-xs italic">—</span>
                                                        )}
                                                    </td>
                                                    {/* T28 — Calling Station column */}
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <span className="text-xs font-mono text-slate-600">
                                                            {log.calling_station_id || <span className="text-slate-300 italic">—</span>}
                                                        </span>
                                                    </td>
                                                    {/* T28 — Event Source column */}
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        {log.event_source ? (
                                                            <span className="text-[10px] font-black uppercase bg-indigo-50 text-indigo-600 px-2 py-1 rounded-full">
                                                                {log.event_source}
                                                            </span>
                                                        ) : (
                                                            <span className="text-slate-300 text-xs italic">—</span>
                                                        )}
                                                    </td>
                                                    <td className="px-6 py-4 text-center cursor-pointer" onClick={() => setSelectedLog(log)}>
                                                        <button className="p-2 text-slate-400 hover:text-indigo-600 transition-colors bg-slate-100 rounded-lg"><Info size={18} /></button>
                                                    </td>
                                                </>
                                            ) : (
                                                <>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-bold text-slate-700">
                                                        <div>{time.full}</div>
                                                        <div className="text-[9px] font-black text-slate-400 uppercase opacity-60 flex items-center gap-1"><ArrowRight size={10} /> {time.relative}</div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <div className="flex items-center gap-3">
                                                            <div className="w-8 h-8 rounded-full bg-slate-800 text-white flex items-center justify-center text-[10px] font-black">{log.admin_user?.charAt(0).toUpperCase()}</div>
                                                            <span className="text-xs font-black text-slate-800 tracking-tight">{log.admin_user}</span>
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <div className="flex flex-col">
                                                            <span className={`px-2 py-0.5 rounded text-[10px] font-black tracking-widest text-center w-fit ${log.action === 'CREATE' ? 'bg-indigo-600 text-white' :
                                                                log.action === 'UPDATE' ? 'bg-amber-500 text-white' :
                                                                    log.action === 'DELETE' ? 'bg-rose-600 text-white' : 'bg-slate-800 text-white'
                                                                }`}>{log.action}</span>
                                                            <span className="mt-1 text-[9px] font-black text-slate-300 uppercase italic truncate max-w-[100px]">{log.table_affected}</span>
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-xs font-bold text-slate-600 uppercase tracking-tighter">{log.target_user || '-'}</td>
                                                    <td className="px-6 py-4 text-center">
                                                        <button onClick={() => setSelectedLog(log)} className="p-2 border border-slate-200 bg-white text-slate-400 rounded-xl group-hover:bg-indigo-600 group-hover:text-white group-hover:border-indigo-600 transition-all shadow-sm">
                                                            <Eye size={18} />
                                                        </button>
                                                    </td>
                                                </>
                                            )}
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>

                <div className="px-10 py-6 bg-slate-50 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-4">
                    <div className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-indigo-500 shadow-lg shadow-indigo-200"></span>
                        Sync Status: OK • Records: {logs?.length || 0}
                    </div>
                    <div className="flex items-center gap-3">
                        <button disabled={page === 0} onClick={() => setPage(p => Math.max(0, p - 1))} className="p-3 border-2 border-slate-200 rounded-2xl bg-white hover:border-indigo-400 hover:text-indigo-600 disabled:opacity-20 transition-all text-slate-600"><ChevronLeft size={20} /></button>
                        <div className="px-6 py-2.5 font-black text-slate-700 text-xs bg-white border-2 border-slate-100 rounded-2xl shadow-inner">PAGE {page + 1}</div>
                        <button disabled={!logs || logs.length < limit} onClick={() => setPage(p => p + 1)} className="p-3 border-2 border-slate-200 rounded-2xl bg-white hover:border-indigo-400 hover:text-indigo-600 disabled:opacity-20 transition-all text-slate-600"><ChevronRight size={20} /></button>
                    </div>
                </div>
            </div>

            {selectedLog && (
                <div className="fixed inset-0 bg-slate-900/90 backdrop-blur-md z-[100] flex items-center justify-center p-4 animate-fadeIn">
                    <div className="bg-white rounded-[2.5rem] w-full max-w-4xl shadow-2xl overflow-hidden animate-slideUp border border-white/20 ring-1 ring-black/5">
                        <div className="p-10 bg-slate-50 border-b flex justify-between items-center">
                            <div className="flex items-center gap-6">
                                <div className={`p-5 rounded-3xl shadow-lg ${tab === 'access' ? (selectedLog.reply === 'Access-Accept' ? 'bg-emerald-500 text-white' : 'bg-rose-500 text-white') : 'bg-indigo-600 text-white'}`}>
                                    {tab === 'access' ? <Activity size={28} /> : <UserLogIcon action={selectedLog.action} />}
                                </div>
                                <div>
                                    <h3 className="text-2xl font-black text-slate-800 tracking-tighter leading-none mb-2">Event Semantic Analysis</h3>
                                    <p className="text-[10px] text-slate-400 uppercase font-black tracking-[0.3em]">Immutable Record Trace • LogID {selectedLog.id}</p>
                                </div>
                            </div>
                            <button onClick={() => setSelectedLog(null)} className="p-4 bg-white border border-slate-100 text-slate-400 hover:text-rose-600 hover:border-rose-100 rounded-full transition-all shadow-sm hover:shadow-xl"><X size={24} /></button>
                        </div>

                        <div className="p-10 space-y-10 max-h-[75vh] overflow-y-auto custom-scrollbar">
                            {/* General Stats */}
                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
                                <div className="space-y-1">
                                    <div className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-widest"><UserCog size={12} /> Executor</div>
                                    <div className="text-base font-black text-slate-800 truncate">{tab === 'access' ? selectedLog.username : selectedLog.admin_user}</div>
                                </div>
                                <div className="space-y-1">
                                    <div className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-widest"><Activity size={12} /> Auth Method</div>
                                    <div className="text-base font-bold text-slate-800">{tab === 'access' ? 'RADIUS-PAP/MSCHAP' : 'Web Admin UI'}</div>
                                </div>
                                <div className="space-y-1">
                                    <div className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-widest"><History size={12} /> Time Context</div>
                                    <div className="text-base font-bold text-slate-800">{formatTime(tab === 'access' ? selectedLog.authdate : selectedLog.timestamp).full}</div>
                                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{formatTime(tab === 'access' ? selectedLog.authdate : selectedLog.timestamp).relative}</div>
                                </div>
                                <div className="space-y-1 text-right">
                                    <div className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-widest justify-end"><Database size={12} /> Persistence</div>
                                    <div className="text-base font-black text-indigo-600">{selectedLog.table_affected || 'Decision Store'}</div>
                                </div>
                            </div>

                            {/* NAS Details for access logs */}
                            {tab === 'access' && (selectedLog.nas_ip_address || selectedLog.calling_station_id) && (
                                <div className="p-6 bg-slate-50 rounded-2xl border border-slate-100 grid grid-cols-2 md:grid-cols-3 gap-4">
                                    <div className="space-y-1">
                                        <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-1"><Server size={10} /> NAS IP</div>
                                        <div className="text-sm font-mono font-bold text-slate-700">{selectedLog.nas_ip_address || '—'}</div>
                                    </div>
                                    <div className="space-y-1">
                                        <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest">NAS Identifier</div>
                                        <div className="text-sm font-mono font-bold text-slate-700">{selectedLog.nas_identifier || '—'}</div>
                                    </div>
                                    <div className="space-y-1">
                                        <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Calling Station</div>
                                        <div className="text-sm font-mono font-bold text-slate-700">{selectedLog.calling_station_id || '—'}</div>
                                    </div>
                                    <div className="space-y-1">
                                        <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Event Source</div>
                                        <div className="text-sm font-bold text-indigo-600">{selectedLog.event_source || '—'}</div>
                                    </div>
                                    {selectedLog.reply_message && (
                                        <div className="space-y-1 col-span-2">
                                            <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Reply Message</div>
                                            <div className="text-sm font-bold text-slate-700">{selectedLog.reply_message}</div>
                                        </div>
                                    )}
                                </div>
                            )}

                            <div className="pt-10 border-t border-slate-100">
                                <h4 className="text-[10px] font-black text-slate-800 uppercase tracking-[0.2em] mb-8 flex items-center gap-2">
                                    <ArrowRight size={14} className="text-indigo-600" /> Detailed Activity Footprint
                                </h4>
                                {tab === 'admin' ? renderDiffView(selectedLog) : (
                                    <div className="p-16 bg-slate-50/50 rounded-[3rem] border-2 border-dashed border-slate-200 text-center flex flex-col items-center gap-6">
                                        <div className={`p-6 rounded-full shadow-2xl ${selectedLog.reply === 'Access-Accept' ? 'bg-emerald-100 text-emerald-600' : 'bg-rose-100 text-rose-600'}`}>
                                            {selectedLog.reply === 'Access-Accept' ? <ShieldCheck size={56} /> : <ShieldAlert size={56} />}
                                        </div>
                                        <div>
                                            <div className="text-3xl font-black text-slate-800 tracking-tight uppercase leading-none">Access Attempt {selectedLog.reply?.split('-')[1]}ed</div>
                                            <p className="text-sm text-slate-400 font-medium max-w-sm mx-auto mt-4 leading-relaxed">The authentication protocol analyzed the credentials and properties for identity <span className="text-slate-800 font-bold">{selectedLog.username}</span>, resulting in this immutable terminal state.</p>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

const UserLogIcon = ({ action }) => {
    if (action === 'CREATE') return <Plus size={24} />;
    if (action === 'DELETE') return <Trash2 size={24} />;
    return <Edit2 size={24} />;
};

export default AuditPage;

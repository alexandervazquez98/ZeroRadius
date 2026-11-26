import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api';
import { parseServerTime, toServerTime } from '../utils/serverTime';
import { Search, Filter, CheckCircle, Clock, AlertCircle } from 'lucide-react';
import NasSyslogStatusCard from '../components/NasSyslogStatusCard';

const SEVERITY_LABELS = {
    0: 'Emergency',
    1: 'Alert',
    2: 'Critical',
    3: 'Error',
    4: 'Warning',
    5: 'Notice',
    6: 'Info',
    7: 'Debug',
};

const SEVERITY_COLORS = {
    0: 'bg-red-600 text-white',
    1: 'bg-red-500 text-white',
    2: 'bg-orange-500 text-white',
    3: 'bg-red-400 text-white',
    4: 'bg-yellow-500 text-white',
    5: 'bg-blue-500 text-white',
    6: 'bg-slate-500 text-white',
    7: 'bg-slate-300 text-slate-700',
};

const SyslogDashboard = () => {
    const [limit, setLimit] = useState(50);
    // Keyset pagination: cursors[i] fetches page i + 1 (null = newest page).
    const [cursors, setCursors] = useState([null]);
    const cursor = cursors[cursors.length - 1];
    const [filters, setFilters] = useState({
        start_date: '',
        end_date: '',
        device_ip: '',
        message: '',
        severity: '',
    });

    const buildQueryParams = () => {
        const params = { limit };
        if (cursor) params.cursor = cursor;
        if (filters.start_date) params.start_date = toServerTime(filters.start_date);
        if (filters.end_date) params.end_date = toServerTime(filters.end_date);
        if (filters.device_ip) params.device_ip = filters.device_ip;
        if (filters.message) params.message = filters.message;
        if (filters.severity !== '') params.severity = parseInt(filters.severity, 10);
        return params;
    };

    const { data, isLoading, error } = useQuery({
        queryKey: ['syslog', limit, cursor, filters],
        queryFn: () => api.get('/syslog', { params: buildQueryParams() }).then(r => r.data),
        staleTime: 30000,
    });

    const handleFilterChange = (key, value) => {
        setFilters(f => ({ ...f, [key]: value }));
        setCursors([null]);
    };

    const clearFilters = () => {
        setFilters({ start_date: '', end_date: '', device_ip: '', message: '', severity: '' });
        setCursors([null]);
    };

    const currentPage = cursors.length;
    const goOlder = () => data?.next_cursor && setCursors(c => [...c, data.next_cursor]);
    const goNewer = () => setCursors(c => (c.length > 1 ? c.slice(0, -1) : c));
    const errorMessage = error?.response?.data?.detail || error?.message;
    const formatWindow = (value) => parseServerTime(value).format('YYYY-MM-DD HH:mm');

    const getHashStatus = (event) => {
        if (!event.hash) return { status: 'pending', label: 'Pending', color: 'text-amber-500', bg: 'bg-amber-100' };
        if (event.previous_hash) return { status: 'verified', label: 'Verified', color: 'text-emerald-600', bg: 'bg-emerald-100' };
        return { status: 'pending', label: 'Pending', color: 'text-amber-500', bg: 'bg-amber-100' };
    };

    return (
        <div className="space-y-6 pb-10">
            <div className="flex justify-between items-center">
                <h2 className="text-2xl font-bold text-slate-800">Syslog Dashboard</h2>
                {data?.start_date && (
                    <span className="text-sm text-slate-500">
                        Showing {formatWindow(data.start_date)} → {formatWindow(data.end_date)}
                    </span>
                )}
            </div>

            <NasSyslogStatusCard />

            <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-4">
                <div className="flex items-center gap-2 mb-4">
                    <Filter size={16} className="text-slate-400" />
                    <h3 className="text-xs font-black text-slate-600 uppercase tracking-widest">Filters</h3>
                    <span className="text-xs text-slate-400">
                        Time range up to {data?.max_range_hours ?? 8} hours; leave dates empty for the last {data?.max_range_hours ?? 8} hours.
                    </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                    <div>
                        <label className="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Start Date</label>
                        <input
                            type="datetime-local"
                            className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                            value={filters.start_date}
                            onChange={e => handleFilterChange('start_date', e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">End Date</label>
                        <input
                            type="datetime-local"
                            className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                            value={filters.end_date}
                            onChange={e => handleFilterChange('end_date', e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Device IP (partial)</label>
                        <input
                            type="text"
                            className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-indigo-500"
                            placeholder="192.168"
                            value={filters.device_ip}
                            onChange={e => handleFilterChange('device_ip', e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Message (partial)</label>
                        <input
                            type="text"
                            className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                            placeholder="error, wan, etc."
                            value={filters.message}
                            onChange={e => handleFilterChange('message', e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Severity</label>
                        <select
                            className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm"
                            value={filters.severity}
                            onChange={e => handleFilterChange('severity', e.target.value)}
                        >
                            <option value="">All</option>
                            {Object.entries(SEVERITY_LABELS).map(([val, label]) => (
                                <option key={val} value={val}>{val} - {label}</option>
                            ))}
                        </select>
                    </div>
                    <div className="flex items-end">
                        <button
                            onClick={clearFilters}
                            className="w-full px-4 py-2 border border-slate-200 rounded-xl text-sm text-slate-600 hover:bg-slate-50 transition-colors"
                        >
                            Clear Filters
                        </button>
                    </div>
                </div>
            </div>

            {isLoading ? (
                <div className="text-center py-16 text-slate-400">Loading syslog events…</div>
            ) : error ? (
                <div className="text-center py-16 text-red-500">Error loading data: {errorMessage}</div>
            ) : data?.events?.length === 0 ? (
                <div className="text-center py-16 bg-white rounded-lg border border-dashed border-slate-300">
                    <p className="text-slate-500">No syslog events found.</p>
                </div>
            ) : (
                <>
                    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="min-w-full divide-y divide-slate-100">
                                <thead className="bg-slate-50">
                                    <tr>
                                        <th className="px-4 py-3 text-left text-[9px] font-black text-slate-400 uppercase tracking-widest">Timestamp</th>
                                        <th className="px-4 py-3 text-left text-[9px] font-black text-slate-400 uppercase tracking-widest">Device IP</th>
                                        <th className="px-4 py-3 text-left text-[9px] font-black text-slate-400 uppercase tracking-widest">Facility</th>
                                        <th className="px-4 py-3 text-left text-[9px] font-black text-slate-400 uppercase tracking-widest">Severity</th>
                                        <th className="px-4 py-3 text-left text-[9px] font-black text-slate-400 uppercase tracking-widest">Program</th>
                                        <th className="px-4 py-3 text-left text-[9px] font-black text-slate-400 uppercase tracking-widest">Message</th>
                                        <th className="px-4 py-3 text-left text-[9px] font-black text-slate-400 uppercase tracking-widest">Hash Status</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {data?.events?.map((event) => {
                                        const hashStatus = getHashStatus(event);
                                        return (
                                            <tr key={event.id} className="hover:bg-slate-50/60 transition-colors">
                                                <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-600">
                                                    {parseServerTime(event.received_at).format('YYYY-MM-DD HH:mm:ss')}
                                                </td>
                                                <td className="px-4 py-3 whitespace-nowrap text-xs font-mono text-slate-700">
                                                    {event.device_ip}
                                                </td>
                                                <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-500">
                                                    {event.facility ?? '-'}
                                                </td>
                                                <td className="px-4 py-3 whitespace-nowrap">
                                                    <span className={`text-[10px] font-black px-2 py-0.5 rounded-full ${SEVERITY_COLORS[event.severity] || 'bg-slate-200 text-slate-600'}`}>
                                                        {event.severity ?? '-'}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-500">
                                                    {event.program || '-'}
                                                </td>
                                                <td className="px-4 py-3 text-xs text-slate-600 max-w-md truncate" title={event.message}>
                                                    {event.message}
                                                </td>
                                                <td className="px-4 py-3 whitespace-nowrap">
                                                    <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-1 rounded-full ${hashStatus.bg} ${hashStatus.color}`}>
                                                        {hashStatus.status === 'verified' ? (
                                                            <CheckCircle size={12} />
                                                        ) : hashStatus.status === 'pending' ? (
                                                            <Clock size={12} />
                                                        ) : (
                                                            <AlertCircle size={12} />
                                                        )}
                                                        {hashStatus.label}
                                                    </span>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-slate-500">Rows per page:</span>
                            <select
                                value={limit}
                                onChange={e => { setLimit(parseInt(e.target.value, 10)); setCursors([null]); }}
                                className="border border-slate-200 rounded-lg px-2 py-1 text-sm"
                            >
                                <option value="25">25</option>
                                <option value="50">50</option>
                                <option value="100">100</option>
                                <option value="200">200</option>
                            </select>
                        </div>

                        <div className="flex items-center gap-2">
                            <span className="text-xs text-slate-500">Page {currentPage}</span>
                            <div className="flex gap-1">
                                <button
                                    onClick={goNewer}
                                    disabled={currentPage === 1}
                                    className="px-3 py-1 text-xs border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    Newer
                                </button>
                                <button
                                    onClick={goOlder}
                                    disabled={!data?.has_more}
                                    className="px-3 py-1 text-xs border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    Older
                                </button>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

export default SyslogDashboard;

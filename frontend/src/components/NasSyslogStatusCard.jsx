import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { parseServerTime } from '../utils/serverTime';
import { Server, ChevronDown, ChevronUp } from 'lucide-react';
import api from '../api';

/**
 * Shows how many registered NAS have not sent syslog within the backend
 * threshold (SYSLOG_SILENT_HOURS, default 24 h) and lists them on demand.
 */
const NasSyslogStatusCard = () => {
    const [expanded, setExpanded] = useState(false);

    const { data, isLoading, error } = useQuery({
        queryKey: ['syslog', 'nas-status'],
        queryFn: () => api.get('/syslog/nas-status').then(r => r.data),
        staleTime: 60000,
        refetchInterval: 300000,
    });

    if (isLoading) {
        return (
            <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-4 text-sm text-slate-400">
                Loading NAS syslog status...
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-4 text-sm text-red-500">
                Could not load NAS syslog status.
            </div>
        );
    }

    const silent = data.devices.filter(d => d.silent);
    const hasSilent = data.silent_count > 0;

    return (
        <div className={`bg-white border rounded-2xl shadow-sm p-4 ${hasSilent ? 'border-amber-300' : 'border-slate-200'}`}>
            <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-xl ${hasSilent ? 'bg-amber-100 text-amber-600' : 'bg-emerald-100 text-emerald-600'}`}>
                        <Server size={18} />
                    </div>
                    <div>
                        <h3 className="text-xs font-black text-slate-600 uppercase tracking-widest">
                            NAS not sending syslog
                        </h3>
                        <p className="text-[11px] text-slate-400">
                            {hasSilent
                                ? `No syslog in the last ${data.threshold_hours} h`
                                : 'All registered NAS are sending syslog'}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <span className={`text-2xl font-bold ${hasSilent ? 'text-amber-600' : 'text-emerald-600'}`}>
                        {`${data.silent_count} of ${data.total}`}
                    </span>
                    {hasSilent && (
                        <button
                            type="button"
                            onClick={() => setExpanded(e => !e)}
                            aria-expanded={expanded}
                            aria-label={expanded ? 'Hide silent NAS' : 'Show silent NAS'}
                            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100"
                        >
                            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </button>
                    )}
                </div>
            </div>

            {hasSilent && expanded && (
                <table className="w-full mt-4 text-sm">
                    <thead>
                        <tr className="text-left text-[9px] font-black text-slate-400 uppercase tracking-widest">
                            <th className="py-2">Name</th>
                            <th className="py-2">Address</th>
                            <th className="py-2">Last message</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {silent.map(d => (
                            <tr key={d.id}>
                                <td className="py-2 text-slate-700">{d.shortname || '-'}</td>
                                <td className="py-2 font-mono text-xs text-slate-500">{d.nasname}</td>
                                <td className="py-2 text-xs text-slate-500">
                                    {d.last_seen ? parseServerTime(d.last_seen).format('YYYY-MM-DD HH:mm') : 'Never'}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </div>
    );
};

export default NasSyslogStatusCard;

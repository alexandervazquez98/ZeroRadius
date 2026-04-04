import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { WifiOff, Clock } from 'lucide-react';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { useToast } from '../context/ToastContext';

dayjs.extend(relativeTime);

const SessionsPage = () => {
    const queryClient = useQueryClient();
    const { showToast } = useToast();
    const { data: sessions, isLoading } = useQuery({
        queryKey: ['sessions'],
        queryFn: () => api.get('/sessions/active').then(r => r.data),
        refetchInterval: 10000 // Poll every 10s
    });

    const disconnectMutation = useMutation({
        mutationFn: ({ username, framed_ip }) => api.post(`/sessions/${username}/disconnect`, null, { params: { framed_ip } }),
        onSuccess: (data) => {
            showToast(`Disconnect signal sent for ${data.data.user}`, 'info');
            queryClient.invalidateQueries(['sessions']);
        }
    });

    if (isLoading) return <div>Loading...</div>;

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold text-slate-800">Active Sessions</h2>

            {sessions?.length === 0 ? (
                <div className="text-center py-20 bg-white rounded-lg border border-dashed border-slate-300">
                    <p className="text-slate-500">No active sessions found.</p>
                </div>
            ) : (
                <div className="bg-white rounded-lg shadow overflow-hidden">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">IP Address</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">MAC Address</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Started</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Data (In/Out)</th>
                                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200">
                            {sessions?.map((s) => (
                                <tr key={s.radacctid}>
                                    <td className="px-6 py-4 whitespace-nowrap font-medium text-gray-900">{s.username}</td>
                                    <td className="px-6 py-4 whitespace-nowrap text-gray-500">{s.framedipaddress}</td>
                                    <td className="px-6 py-4 whitespace-nowrap text-gray-500 font-mono text-xs">{s.callingstationid}</td>
                                    <td className="px-6 py-4 whitespace-nowrap text-gray-500 flex items-center gap-1">
                                        <Clock size={14} />
                                        {dayjs(s.acctstarttime).fromNow()}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-gray-500 text-xs">
                                        <span className="text-green-600">↓ {s.acctinputoctets || 0}</span>
                                        <span className="mx-2">|</span>
                                        <span className="text-blue-600">↑ {s.acctoutputoctets || 0}</span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                                        <button
                                            onClick={() => disconnectMutation.mutate({ username: s.username, framed_ip: s.framedipaddress })}
                                            className="text-red-600 hover:text-red-900 flex items-center gap-1 ml-auto"
                                        >
                                            <WifiOff size={16} /> Disconnect
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

export default SessionsPage;

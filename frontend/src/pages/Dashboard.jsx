import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api';
import { Users, Server, Radio, Activity } from 'lucide-react';

const StatCard = ({ title, value, icon: Icon, color }) => (
    <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
        <div className="flex items-center justify-between">
            <div>
                <p className="text-sm font-medium text-slate-500">{title}</p>
                <p className="text-2xl font-bold mt-1">{value}</p>
            </div>
            <div className={`p-3 rounded-full ${color}`}>
                <Icon size={24} className="text-white" />
            </div>
        </div>
    </div>
);

const Dashboard = () => {
    // Queries to fetch stats (mocked counts for now or real if endpoints existed)
    // For MVP we can fetch lists and count length

    const { data: users } = useQuery({ queryKey: ['users'], queryFn: () => api.get('/users').then(r => r.data) });
    const { data: nas } = useQuery({ queryKey: ['nas'], queryFn: () => api.get('/nas').then(r => r.data) });
    const { data: sessions } = useQuery({ queryKey: ['sessions'], queryFn: () => api.get('/sessions/active').then(r => r.data) });

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold text-slate-800">System Overview</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard
                    title="Total Users"
                    value={users?.length || 0}
                    icon={Users}
                    color="bg-blue-500"
                />
                <StatCard
                    title="NAS Devices"
                    value={nas?.length || 0}
                    icon={Server}
                    color="bg-indigo-500"
                />
                <StatCard
                    title="Active Sessions"
                    value={sessions?.length || 0}
                    icon={Activity}
                    color="bg-green-500"
                />
                <StatCard
                    title="System Status"
                    value="Online"
                    icon={Radio}
                    color="bg-emerald-500"
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
                <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                    <h3 className="font-semibold text-lg mb-4">Recent Activity</h3>
                    <p className="text-slate-500 text-sm">Audit logs would appear here...</p>
                    {/* Placeholder for Audit Log widget */}
                </div>
                <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                    <h3 className="font-semibold text-lg mb-4">Traffic Overview</h3>
                    <div className="h-48 bg-slate-50 rounded flex items-center justify-center text-slate-400">
                        Chart Placeholder
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Dashboard;

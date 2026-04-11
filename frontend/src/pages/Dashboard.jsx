import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api';
import { Users, Server, Radio, Activity, Container, Cpu, HardDrive, Gauge } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';

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

const ResourceGauge = ({ label, value, icon: Icon, color }) => {
    const data = [{ value: value, color: color }];
    const remaining = 100 - value;

    return (
        <div className="bg-white p-4 rounded-lg shadow-sm border border-slate-200">
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <Icon size={18} className="text-slate-400" />
                    <span className="text-sm font-medium text-slate-600">{label}</span>
                </div>
                <span className="text-lg font-bold text-slate-800">{value}%</span>
            </div>
            <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${value}%`, backgroundColor: color }}
                />
            </div>
        </div>
    );
};

const COLORS = ['#10B981', '#EF4444', '#F59E0B', '#3B82F6'];

const Dashboard = () => {
    const { data: users } = useQuery({ 
        queryKey: ['users'], 
        queryFn: () => api.get('/users').then(r => r.data) 
    });
    const { data: nas } = useQuery({ 
        queryKey: ['nas'], 
        queryFn: () => api.get('/nas').then(r => r.data) 
    });
    const { data: sessions } = useQuery({ 
        queryKey: ['sessions'], 
        queryFn: () => api.get('/sessions/active').then(r => r.data),
        refetchInterval: 30000,
    });

    const { data: containers } = useQuery({
        queryKey: ['containers'],
        queryFn: () => api.get('/system/health/containers').then(r => r.data),
        refetchInterval: 30000,
    });

    const { data: resources } = useQuery({
        queryKey: ['systemResources'],
        queryFn: () => api.get('/system/health/resources').then(r => r.data),
        refetchInterval: 30000,
    });

    const containerChartData = containers ? [
        { name: 'Running', value: containers.running, color: '#10B981' },
        { name: 'Stopped', value: containers.stopped, color: '#EF4444' },
    ] : [];

    const memoryChartData = resources ? [
        { name: 'Used', value: resources.memory_used_gb, color: '#3B82F6' },
        { name: 'Free', value: Math.max(0, resources.memory_total_gb - resources.memory_used_gb), color: '#E5E7EB' },
    ] : [];

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

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                    <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
                        <Container size={20} className="text-slate-600" />
                        Container Status
                    </h3>
                    {containers ? (
                        <div className="flex items-center justify-between">
                            <div className="flex gap-6">
                                <div className="text-center">
                                    <p className="text-3xl font-bold text-emerald-600">{containers.running}</p>
                                    <p className="text-sm text-slate-500">Running</p>
                                </div>
                                <div className="text-center">
                                    <p className="text-3xl font-bold text-red-600">{containers.stopped}</p>
                                    <p className="text-sm text-slate-500">Stopped</p>
                                </div>
                                <div className="text-center">
                                    <p className="text-3xl font-bold text-slate-600">{containers.total}</p>
                                    <p className="text-sm text-slate-500">Total</p>
                                </div>
                            </div>
                            <div className="h-32 w-32">
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie
                                            data={containerChartData}
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={35}
                                            outerRadius={50}
                                            dataKey="value"
                                            label={({ name, value }) => `${name}: ${value}`}
                                        >
                                            {containerChartData.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={entry.color} />
                                            ))}
                                        </Pie>
                                        <Tooltip />
                                    </PieChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    ) : (
                        <p className="text-slate-400">Loading container status...</p>
                    )}
                </div>

                <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                    <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
                        <Gauge size={20} className="text-slate-600" />
                        System Resources
                    </h3>
                    {resources ? (
                        <div className="grid grid-cols-3 gap-4">
                            <ResourceGauge
                                label="CPU"
                                value={resources.cpu_percent}
                                icon={Cpu}
                                color={resources.cpu_percent > 80 ? '#EF4444' : resources.cpu_percent > 60 ? '#F59E0B' : '#3B82F6'}
                            />
                            <ResourceGauge
                                label="RAM"
                                value={resources.memory_percent}
                                icon={HardDrive}
                                color={resources.memory_percent > 80 ? '#EF4444' : resources.memory_percent > 60 ? '#F59E0B' : '#3B82F6'}
                            />
                            <ResourceGauge
                                label="Disk"
                                value={resources.disk_percent}
                                icon={HardDrive}
                                color={resources.disk_percent > 80 ? '#EF4444' : resources.disk_percent > 60 ? '#F59E0B' : '#3B82F6'}
                            />
                        </div>
                    ) : (
                        <p className="text-slate-400">Loading system resources...</p>
                    )}
                    {resources && (
                        <div className="mt-4 pt-4 border-t border-slate-100">
                            <p className="text-xs text-slate-500">
                                CPU: {resources.cpu_count} cores | RAM: {resources.memory_used_gb} / {resources.memory_total_gb} GB | Disk: {resources.disk_used_gb} / {resources.disk_total_gb} GB
                            </p>
                        </div>
                    )}
                </div>
            </div>

            {containers?.containers && containers.containers.length > 0 && (
                <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                    <h3 className="font-semibold text-lg mb-4">Container Details</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-200">
                                    <th className="text-left py-2 px-3 font-medium text-slate-600">Name</th>
                                    <th className="text-left py-2 px-3 font-medium text-slate-600">Status</th>
                                    <th className="text-right py-2 px-3 font-medium text-slate-600">CPU %</th>
                                    <th className="text-right py-2 px-3 font-medium text-slate-600">Memory</th>
                                    <th className="text-right py-2 px-3 font-medium text-slate-600">Network I/O</th>
                                </tr>
                            </thead>
                            <tbody>
                                {containers.containers.map((container) => (
                                    <tr key={container.id} className="border-b border-slate-100 hover:bg-slate-50">
                                        <td className="py-2 px-3 font-mono text-slate-700">{container.name}</td>
                                        <td className="py-2 px-3">
                                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                                                container.state === 'running' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
                                            }`}>
                                                {container.state}
                                            </span>
                                        </td>
                                        <td className="py-2 px-3 text-right text-slate-600">{container.cpu_percent}%</td>
                                        <td className="py-2 px-3 text-right text-slate-600">
                                            {container.memory_usage_mb} / {container.memory_limit_mb} MB
                                        </td>
                                        <td className="py-2 px-3 text-right text-slate-600">
                                            ↓ {container.network_rx_mb} MB | ↑ {container.network_tx_mb} MB
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                    <h3 className="font-semibold text-lg mb-4">Recent Activity</h3>
                    <p className="text-slate-500 text-sm">Audit logs would appear here...</p>
                </div>
                <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                    <h3 className="font-semibold text-lg mb-4">Memory Usage</h3>
                    {resources && resources.memory_total_gb > 0 ? (
                        <div className="h-48">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={memoryChartData} layout="vertical">
                                    <XAxis type="number" domain={[0, resources.memory_total_gb]} hide />
                                    <YAxis type="category" dataKey="name" width={50} />
                                    <Tooltip />
                                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                                        {memoryChartData.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={entry.color} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    ) : (
                        <div className="h-48 bg-slate-50 rounded flex items-center justify-center text-slate-400">
                            Loading...
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
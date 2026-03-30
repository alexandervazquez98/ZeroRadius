import React, { useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Users, Server, Radio, Activity, Shield, Layers, BookOpen, LogOut, UserCog, Map, Clock, ScrollText } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import NTPIndicator from './NTPIndicator';
import LogViewer from './LogViewer';

const Layout = () => {
    const location = useLocation();
    const { logout, user, role, hasRole } = useAuth();
    const navigate = useNavigate();
    const [logDrawerOpen, setLogDrawerOpen] = useState(false);

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    // All nav items with optional allowedRoles (undefined = everyone with auth)
    const navItems = [
        { name: 'Dashboard', path: '/', icon: LayoutDashboard },
        { name: 'Users', path: '/users', icon: Users },
        { name: 'NAS Devices', path: '/nas', icon: Server },
        { name: 'Active Sessions', path: '/sessions', icon: Activity },
        { name: 'Groups', path: '/groups', icon: Layers },
        { name: 'Privilege Map', path: '/privilege-map', icon: Map, allowedRoles: ['superadmin', 'admin', 'auditor'] },
        { name: 'IAM & Zonas', path: '/iam', icon: Shield, allowedRoles: ['superadmin', 'admin'] },
        { name: 'Dictionaries', path: '/dictionaries', icon: BookOpen },
        { name: 'Audit Logs', path: '/audit', icon: Shield },
        { name: 'System Users', path: '/admin-users', icon: UserCog, allowedRoles: ['superadmin'] },
    ];

    // Filter nav items based on role
    const visibleNavItems = navItems.filter(item =>
        !item.allowedRoles || hasRole(item.allowedRoles)
    );

    return (
        <div className="min-h-screen flex">
            {/* Sidebar */}
            <aside className="w-64 bg-slate-900 text-white flex flex-col">
                <div className="p-6 border-b border-slate-800">
                    <div className="flex items-center gap-2 font-bold text-xl">
                        <Radio className="text-blue-500" />
                        <span>RadiusMgr</span>
                    </div>
                </div>
                <nav className="flex-1 p-4 space-y-2">
                    {visibleNavItems.map((item) => {
                        const Icon = item.icon;
                        const isActive = location.pathname === item.path;
                        return (
                            <Link
                                key={item.path}
                                to={item.path}
                                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${isActive
                                    ? 'bg-blue-600 text-white'
                                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                                    }`}
                            >
                                <Icon size={20} />
                                <span>{item.name}</span>
                            </Link>
                        );
                    })}
                </nav>

                <div className="p-4 border-t border-slate-800">
                    <button
                        onClick={handleLogout}
                        className="flex items-center gap-3 px-4 py-3 w-full text-slate-400 hover:bg-red-900/20 hover:text-red-400 rounded-lg transition-colors"
                    >
                        <LogOut size={20} />
                        <span>Logout</span>
                    </button>
                    <div className="mt-4 text-xs text-slate-500 text-center">
                        v1.0.0
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-auto">
                <header className="bg-white shadow-sm h-16 flex items-center px-8 justify-between">
                    <h1 className="text-lg font-semibold text-gray-700">
                        {navItems.find(i => i.path === location.pathname)?.name || 'Radius Manager'}
                    </h1>
                    <div className="flex items-center gap-4">
                        {/* NTP status indicator — only for admin/superadmin */}
                        {hasRole(['admin', 'superadmin']) && <NTPIndicator />}
                        {/* Log viewer toggle — only for admin/superadmin */}
                        {hasRole(['admin', 'superadmin']) && (
                            <button
                                onClick={() => setLogDrawerOpen(o => !o)}
                                className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold transition-colors ${
                                    logDrawerOpen
                                        ? 'bg-indigo-50 border-indigo-200 text-indigo-600'
                                        : 'bg-slate-50 border-slate-200 text-slate-500 hover:bg-slate-100 hover:text-slate-700'
                                }`}
                                title="RADIUS Live Log"
                            >
                                <ScrollText size={14} />
                                <span className="hidden sm:inline">Logs</span>
                            </button>
                        )}
                        <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold text-xs uppercase">
                                {user?.username?.charAt(0) || 'A'}
                            </div>
                            {role && (
                                <span className="text-xs text-slate-500 capitalize hidden sm:block">{role}</span>
                            )}
                        </div>
                    </div>
                </header>
                <div className="p-8">
                    <Outlet />
                </div>
            </main>

            {/* Log viewer drawer — persists across navigation */}
            <LogViewer isOpen={logDrawerOpen} onClose={() => setLogDrawerOpen(false)} />
        </div>
    );
};

export default Layout;

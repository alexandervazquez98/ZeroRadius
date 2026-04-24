import React, { useState } from 'react'
import { Server, Cpu } from 'lucide-react'
import NasTab from './NasTab'
import DeviceRegistryTab from './DeviceRegistryTab'

const STORAGE_KEY = 'zr-network-devices-tab'

function loadActiveTab() {
    try {
        return localStorage.getItem(STORAGE_KEY) || 'nas'
    } catch {
        return 'nas'
    }
}

export default function NetworkDevices() {
    const [activeTab, setActiveTab] = useState(loadActiveTab)

    const handleTabChange = (tab) => {
        setActiveTab(tab)
        try {
            localStorage.setItem(STORAGE_KEY, tab)
        } catch {
            // ignore storage errors
        }
    }

    return (
        <div className="space-y-6 pb-10">
            {/* Header */}
            <div className="py-4">
                <h2 className="text-3xl font-extrabold text-slate-800 tracking-tight flex items-center gap-3">
                    <Server className="text-indigo-600" size={32} />
                    Network Devices
                </h2>
            </div>

            {/* Tabs */}
            <div className="border-b border-slate-200">
                <nav className="-mb-px flex space-x-8">
                    <button
                        onClick={() => handleTabChange('nas')}
                        className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors flex items-center gap-2 ${
                            activeTab === 'nas'
                                ? 'border-indigo-500 text-indigo-600'
                                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                        }`}
                    >
                        <Server size={15} />
                        NAS Devices
                    </button>
                    <button
                        onClick={() => handleTabChange('registry')}
                        className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors flex items-center gap-2 ${
                            activeTab === 'registry'
                                ? 'border-indigo-500 text-indigo-600'
                                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                        }`}
                    >
                        <Cpu size={15} />
                        Device Registry
                    </button>
                </nav>
            </div>

            {/* Tab Content */}
            <div>
                {activeTab === 'nas' && <NasTab />}
                {activeTab === 'registry' && <DeviceRegistryTab />}
            </div>
        </div>
    )
}

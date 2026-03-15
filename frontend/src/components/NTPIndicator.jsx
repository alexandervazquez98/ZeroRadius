import { useState, useEffect } from 'react';
import api from '../api';

/**
 * NTPIndicator — ISO 27001 A.8.17
 * Shows NTP synchronization status in the header.
 * Green dot = synced, Red dot = alert (offset > 500ms or not synced).
 * Polls every 5 minutes. Only visible to admin/superadmin (Layout handles role gating).
 */
function NTPIndicator() {
    const [status, setStatus] = useState(null);
    const [error, setError] = useState(false);

    const fetchStatus = async () => {
        try {
            const res = await api.get('/system/ntp-status');
            setStatus(res.data);
            setError(false);
        } catch (e) {
            setError(true);
        }
    };

    useEffect(() => {
        fetchStatus();
        // Poll every 5 minutes (300000ms)
        const interval = setInterval(fetchStatus, 300_000);
        return () => clearInterval(interval);
    }, []);

    if (!status && !error) return null; // Still loading

    const isAlert = error || !status?.synchronized || status?.alert;

    return (
        <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold cursor-default"
            style={{
                backgroundColor: isAlert ? '#FEF2F2' : '#F0FDF4',
                borderColor: isAlert ? '#FECACA' : '#BBF7D0',
                color: isAlert ? '#DC2626' : '#16A34A',
            }}
            title={
                error
                    ? 'NTP status unavailable'
                    : status
                    ? `NTP: ${status.synchronized ? 'Synced' : 'Not Synced'} | Offset: ${status.offset_ms?.toFixed(2)}ms | Server: ${status.reference_server || 'unknown'}`
                    : 'Loading NTP status...'
            }
        >
            <span
                className="w-2 h-2 rounded-full inline-block"
                style={{
                    backgroundColor: isAlert ? '#DC2626' : '#16A34A',
                    boxShadow: isAlert
                        ? '0 0 4px rgba(220, 38, 38, 0.6)'
                        : '0 0 4px rgba(22, 163, 74, 0.6)',
                }}
            />
            <span className="hidden sm:inline">NTP</span>
        </div>
    );
}

export default NTPIndicator;

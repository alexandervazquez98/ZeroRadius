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

    // NTP_SERVER not set on the backend: neutral, not an alarm.
    const notConfigured = !error && status?.configured === false;
    const isAlert = !notConfigured && (error || !status?.synchronized || status?.alert);
    const tone = notConfigured
        ? { bg: '#F8FAFC', border: '#E2E8F0', fg: '#64748B', dot: '#94A3B8', glow: 'none' }
        : isAlert
        ? { bg: '#FEF2F2', border: '#FECACA', fg: '#DC2626', dot: '#DC2626', glow: '0 0 4px rgba(220, 38, 38, 0.6)' }
        : { bg: '#F0FDF4', border: '#BBF7D0', fg: '#16A34A', dot: '#16A34A', glow: '0 0 4px rgba(22, 163, 74, 0.6)' };

    return (
        <div
            data-testid="ntp-indicator"
            data-state={notConfigured ? 'not-configured' : isAlert ? 'alert' : 'ok'}
            className="flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold cursor-default"
            style={{
                backgroundColor: tone.bg,
                borderColor: tone.border,
                color: tone.fg,
            }}
            title={
                error
                    ? 'NTP status unavailable'
                    : notConfigured
                    ? 'NTP check not configured (set NTP_SERVER on the backend)'
                    : status
                    ? `NTP: ${status.synchronized ? 'Synced' : 'Not Synced'} | Offset: ${status.offset_ms?.toFixed(2)}ms | Server: ${status.reference_server || 'unknown'}`
                    : 'Loading NTP status...'
            }
        >
            <span
                className="w-2 h-2 rounded-full inline-block"
                style={{
                    backgroundColor: tone.dot,
                    boxShadow: tone.glow,
                }}
            />
            <span className="hidden sm:inline">NTP</span>
        </div>
    );
}

export default NTPIndicator;

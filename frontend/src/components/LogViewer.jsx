import { useState, useEffect, useRef, useCallback } from 'react';
import { ScrollText, X, Trash2, Pause, Play, Search, ChevronDown, ChevronRight, WifiOff, Wifi } from 'lucide-react';

/**
 * LogViewer — Real-time FreeRADIUS log viewer (drawer component).
 *
 * Connects via WebSocket to /system/logs/stream, authenticates with JWT,
 * and displays Access-Request blocks as collapsible cards.
 *
 * Props:
 *   isOpen {boolean} — Whether the drawer is visible.
 *   onClose {function} — Callback to close the drawer.
 */

const MAX_EVENTS = 200;
const RECONNECT_BASE_MS = 2000;
const RECONNECT_MAX_MS = 30000;

function LogViewer({ isOpen, onClose }) {
    const [events, setEvents] = useState([]);
    const [connected, setConnected] = useState(false);
    const [paused, setPaused] = useState(false);
    const [filter, setFilter] = useState('');
    const [expandedIds, setExpandedIds] = useState(new Set());
    const [error, setError] = useState(null);

    const wsRef = useRef(null);
    const reconnectTimer = useRef(null);
    const reconnectDelay = useRef(RECONNECT_BASE_MS);
    const pausedRef = useRef(false);
    const eventsRef = useRef([]);
    const scrollRef = useRef(null);
    const autoScrollRef = useRef(true);

    // Keep pausedRef in sync
    useEffect(() => { pausedRef.current = paused; }, [paused]);

    const connectWs = useCallback(() => {
        // Clean up previous connection
        if (wsRef.current) {
            try { wsRef.current.close(); } catch { /* noop */ }
        }

        const token = localStorage.getItem('token');
        if (!token) {
            setError('No authentication token found');
            return;
        }

        // Build WebSocket URL relative to current host
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${proto}//${window.location.host}/api/system/logs/stream`;

        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            // Send JWT as first message (auth handshake)
            ws.send(token);
        };

        ws.onmessage = (msg) => {
            try {
                const data = JSON.parse(msg.data);

                // Handle auth response
                if (data.status === 'connected') {
                    setConnected(true);
                    setError(null);
                    reconnectDelay.current = RECONNECT_BASE_MS;
                    return;
                }

                // Handle errors from server
                if (data.error) {
                    setError(data.error);
                    setConnected(false);
                    return;
                }

                // Handle log event — always accumulate even if paused
                // (paused only stops visual scroll, not data collection)
                if (data.lines && data.verdict) {
                    const event = {
                        id: `${data.request_id}-${Date.now()}`,
                        ...data,
                    };

                    eventsRef.current = [...eventsRef.current, event].slice(-MAX_EVENTS);
                    setEvents([...eventsRef.current]);
                }
            } catch {
                // Non-JSON message — ignore
            }
        };

        ws.onclose = (e) => {
            setConnected(false);
            wsRef.current = null;

            // Don't reconnect on auth failures or intentional closes
            if (e.code === 4003 || e.code === 4001) {
                setError('Authentication failed — reconnect manually');
                return;
            }

            // Auto-reconnect with exponential backoff
            if (isOpen) {
                reconnectTimer.current = setTimeout(() => {
                    reconnectDelay.current = Math.min(
                        reconnectDelay.current * 1.5,
                        RECONNECT_MAX_MS
                    );
                    connectWs();
                }, reconnectDelay.current);
            }
        };

        ws.onerror = () => {
            // onclose will fire right after — handle reconnect there
        };
    }, [isOpen]);

    // Connect when drawer opens, disconnect when it closes
    useEffect(() => {
        if (isOpen) {
            connectWs();
        } else {
            if (wsRef.current) {
                try { wsRef.current.close(); } catch { /* noop */ }
                wsRef.current = null;
            }
            if (reconnectTimer.current) {
                clearTimeout(reconnectTimer.current);
            }
            setConnected(false);
        }

        return () => {
            if (wsRef.current) {
                try { wsRef.current.close(); } catch { /* noop */ }
            }
            if (reconnectTimer.current) {
                clearTimeout(reconnectTimer.current);
            }
        };
    }, [isOpen, connectWs]);

    // Auto-scroll to bottom on new events
    useEffect(() => {
        if (autoScrollRef.current && scrollRef.current && !paused) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [events, paused]);

    // Handle scroll — detect if user scrolled up to disable auto-scroll
    const handleScroll = () => {
        if (!scrollRef.current) return;
        const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
        autoScrollRef.current = scrollHeight - scrollTop - clientHeight < 60;
    };

    const handleClear = () => {
        eventsRef.current = [];
        setEvents([]);
        setExpandedIds(new Set());
    };

    const toggleExpand = (id) => {
        setExpandedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    // Filter events by search text
    const filteredEvents = filter
        ? events.filter(e =>
            e.lines.some(l => l.toLowerCase().includes(filter.toLowerCase())) ||
            e.verdict.toLowerCase().includes(filter.toLowerCase())
        )
        : events;

    // Format timestamp for display
    const fmtTime = (ts) => {
        try {
            const d = new Date(ts);
            return d.toLocaleTimeString('es-AR', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        } catch {
            return ts?.slice(11, 19) || '--:--:--';
        }
    };

    // Extract username from log lines
    const extractUsername = (lines) => {
        for (const line of lines) {
            const match = line.match(/User-Name\s*=\s*"?([^"\s]+)"?/i);
            if (match) return match[1];
        }
        return 'unknown';
    };

    // Extract NAS IP from log lines
    const extractNasIp = (lines) => {
        for (const line of lines) {
            const match = line.match(/from\s+([\d.]+):\d+/);
            if (match) return match[1];
        }
        return null;
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-y-0 right-0 w-[520px] max-w-full bg-slate-900 shadow-2xl z-50 flex flex-col border-l border-slate-700 animate-slideInRight">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-slate-800 border-b border-slate-700 shrink-0">
                <div className="flex items-center gap-3">
                    <ScrollText size={18} className="text-indigo-400" />
                    <h3 className="text-sm font-black text-white tracking-wide uppercase">RADIUS Live Log</h3>
                    <span
                        className={`flex items-center gap-1.5 text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            connected
                                ? 'bg-emerald-500/20 text-emerald-400'
                                : 'bg-rose-500/20 text-rose-400'
                        }`}
                    >
                        {connected ? <Wifi size={10} /> : <WifiOff size={10} />}
                        {connected ? 'Conectado' : 'Desconectado'}
                    </span>
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={handleClear}
                        className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
                        title="Limpiar buffer"
                    >
                        <Trash2 size={14} />
                    </button>
                    <button
                        onClick={() => setPaused(p => !p)}
                        className={`p-1.5 rounded transition-colors ${
                            paused
                                ? 'text-amber-400 bg-amber-500/20 hover:bg-amber-500/30'
                                : 'text-slate-400 hover:text-white hover:bg-slate-700'
                        }`}
                        title={paused ? 'Resumir auto-scroll' : 'Pausar auto-scroll'}
                    >
                        {paused ? <Play size={14} /> : <Pause size={14} />}
                    </button>
                    <button
                        onClick={onClose}
                        className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors ml-1"
                        title="Cerrar panel"
                    >
                        <X size={16} />
                    </button>
                </div>
            </div>

            {/* Filter bar */}
            <div className="px-3 py-2 bg-slate-800/50 border-b border-slate-700/50 shrink-0">
                <div className="relative">
                    <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
                    <input
                        type="text"
                        placeholder="Filtrar logs..."
                        value={filter}
                        onChange={e => setFilter(e.target.value)}
                        className="w-full pl-8 pr-3 py-1.5 bg-slate-700/50 border border-slate-600 rounded text-xs text-slate-200 placeholder-slate-500 outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
                    />
                </div>
                <div className="flex justify-between mt-1.5 text-[10px] text-slate-500">
                    <span>{filteredEvents.length} evento{filteredEvents.length !== 1 ? 's' : ''}</span>
                    <span>Buffer: {events.length}/{MAX_EVENTS}</span>
                </div>
            </div>

            {/* Error bar */}
            {error && (
                <div className="px-4 py-2 bg-rose-500/20 text-rose-300 text-xs font-semibold border-b border-rose-500/30 shrink-0">
                    ⚠ {error}
                </div>
            )}

            {/* Log entries */}
            <div
                ref={scrollRef}
                onScroll={handleScroll}
                className="flex-1 overflow-y-auto overflow-x-hidden px-3 py-2 space-y-1.5"
            >
                {filteredEvents.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-3">
                        <ScrollText size={40} className="text-slate-700" />
                        <p className="text-sm font-semibold">Esperando peticiones RADIUS...</p>
                        <p className="text-xs text-slate-600">Los eventos Access-Request aparecerán aquí en tiempo real.</p>
                    </div>
                )}

                {filteredEvents.map((event) => {
                    const isExpanded = expandedIds.has(event.id);
                    const isAccept = event.verdict === 'Accept';
                    const username = extractUsername(event.lines);
                    const nasIp = extractNasIp(event.lines);

                    return (
                        <div
                            key={event.id}
                            className={`rounded-lg border overflow-hidden transition-colors ${
                                isAccept
                                    ? 'border-emerald-500/30 bg-emerald-500/5'
                                    : 'border-rose-500/30 bg-rose-500/5'
                            }`}
                        >
                            {/* Summary row — always visible */}
                            <button
                                onClick={() => toggleExpand(event.id)}
                                className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/5 transition-colors"
                            >
                                {isExpanded
                                    ? <ChevronDown size={12} className="text-slate-400 shrink-0" />
                                    : <ChevronRight size={12} className="text-slate-400 shrink-0" />
                                }
                                <span
                                    className={`text-[10px] font-black px-1.5 py-0.5 rounded shrink-0 ${
                                        isAccept
                                            ? 'bg-emerald-500/20 text-emerald-400'
                                            : 'bg-rose-500/20 text-rose-400'
                                    }`}
                                >
                                    {isAccept ? 'ACCEPT' : 'REJECT'}
                                </span>
                                <span className="text-xs text-slate-300 font-mono truncate">
                                    {username}
                                </span>
                                {nasIp && (
                                    <span className="text-[10px] text-slate-500 font-mono shrink-0">
                                        ← {nasIp}
                                    </span>
                                )}
                                <span className="text-[10px] text-slate-600 ml-auto shrink-0">
                                    {fmtTime(event.timestamp)}
                                </span>
                                <span className="text-[10px] text-slate-600 shrink-0">
                                    ({event.lines.length}L)
                                </span>
                            </button>

                            {/* Expanded detail — full log block */}
                            {isExpanded && (
                                <div className="border-t border-slate-700/50 bg-black/30 px-3 py-2 max-h-64 overflow-y-auto">
                                    <pre className="text-[11px] leading-relaxed font-mono text-slate-400 whitespace-pre-wrap break-all">
                                        {event.lines.join('\n')}
                                    </pre>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Paused indicator overlay */}
            {paused && (
                <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-amber-500 text-black text-xs font-black px-4 py-1.5 rounded-full shadow-lg animate-pulse">
                    ⏸ AUTO-SCROLL PAUSADO
                </div>
            )}
        </div>
    );
}

export default LogViewer;

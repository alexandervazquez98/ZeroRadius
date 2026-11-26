import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { jwtDecode } from 'jwt-decode';
import { Clock, Lock } from 'lucide-react';
import api from '../api';
import { useAuth } from '../context/AuthContext';
import { setReauthHandler } from '../session/reauth';

const ACTIVITY_EVENTS = ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart', 'wheel'];

function tokenClaims() {
    try {
        return jwtDecode(localStorage.getItem('token') || '');
    } catch {
        return {};
    }
}

function tokenExpiryMs() {
    return (tokenClaims().exp || 0) * 1000;
}

// Refresh no earlier than half the token's lifetime, so a short idle timeout
// (ACCESS_TOKEN_EXPIRE_MINUTES <= 5) does not refresh on every tick.
function refreshLead(maxLeadMs) {
    const { exp, iat } = tokenClaims();
    if (!exp || !iat) return maxLeadMs;
    return Math.min(maxLeadMs, ((exp - iat) * 1000) / 2);
}

const REFRESH_RETRY_MS = 30 * 1000;

function formatRemaining(ms) {
    const total = Math.max(0, Math.ceil(ms / 1000));
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

/**
 * Keeps an active admin signed in and re-authenticates in place (#135).
 *
 * - While the admin is active, refreshes the token `refreshLeadMs` before it
 *   expires (POST /auth/refresh).
 * - When idle, warns `warnMs` before expiry with a countdown.
 * - On expiry, a rejected refresh, or any 401, shows a sign-in dialog over the
 *   current page, so unsaved state survives; failed requests are retried by
 *   the api interceptor once the admin signs in again.
 */
// tickMs: clock interval, capped at 1 s so the countdown stays live.
const SessionManager = ({ tickMs = 1000, refreshLeadMs = 5 * 60 * 1000, warnMs = 2 * 60 * 1000 }) => {
    const { user, login, logout, applyToken } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    const [mode, setMode] = useState(null); // null | 'warning' | 'capped' | 'reauth'
    const [now, setNow] = useState(Date.now());
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);

    const lastActivity = useRef(0);
    const lastRefresh = useRef(Date.now());
    const refreshing = useRef(false);
    const retryAfter = useRef(0); // back-off after a non-auth refresh failure
    const capped = useRef(false); // backend could not extend: absolute lifetime reached
    const waiters = useRef([]);
    const modeRef = useRef(mode);
    modeRef.current = mode;

    const openReauth = useCallback(() => {
        setError('');
        setPassword('');
        setMode('reauth');
    }, []);

    const refresh = useCallback(async () => {
        if (refreshing.current) return;
        refreshing.current = true;
        const before = tokenExpiryMs();
        try {
            const { data } = await api.post('/auth/refresh');
            applyToken(data.access_token);
            lastRefresh.current = Date.now();
            retryAfter.current = 0;
            capped.current = tokenExpiryMs() <= before;
            setMode(capped.current ? 'capped' : null);
        } catch (err) {
            if (err?.response?.status === 401) {
                openReauth();
            } else {
                // Network error, 429 or 5xx: keep the session, try again later.
                retryAfter.current = Date.now() + REFRESH_RETRY_MS;
                if (modeRef.current === 'warning') setMode(null);
            }
        } finally {
            refreshing.current = false;
        }
    }, [applyToken, openReauth]);

    // Activity tracking.
    useEffect(() => {
        const mark = () => {
            lastActivity.current = Date.now();
        };
        ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, mark, { passive: true }));
        return () => ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, mark));
    }, []);

    // 401 from any request: open the dialog and let the request wait on it.
    useEffect(() => {
        const unregister = setReauthHandler(
            () =>
                new Promise((resolve, reject) => {
                    waiters.current.push({ resolve, reject });
                    openReauth();
                })
        );
        return () => {
            unregister();
            // Never leave requests waiting on a dialog that no longer exists.
            const pending = waiters.current;
            waiters.current = [];
            pending.forEach((w) => w.reject(new Error('session-manager-unmounted')));
        };
    }, [openReauth]);

    // Expiry clock.
    useEffect(() => {
        const tick = () => {
            const current = Date.now();
            setNow(current);
            if (modeRef.current === 'reauth') return;
            const remaining = tokenExpiryMs() - current;
            if (remaining <= 0) {
                openReauth();
                return;
            }
            const active = lastActivity.current > lastRefresh.current;
            const canRefresh = !capped.current && current >= retryAfter.current;
            if (remaining <= refreshLead(refreshLeadMs) && active && canRefresh) {
                refresh();
            } else if (remaining <= warnMs && modeRef.current === null) {
                setMode(capped.current ? 'capped' : 'warning');
            }
        };
        tick();
        const id = setInterval(tick, Math.min(tickMs, 1000));
        return () => clearInterval(id);
    }, [tickMs, refreshLeadMs, warnMs, refresh, openReauth]);

    const settleWaiters = (ok) => {
        const pending = waiters.current;
        waiters.current = [];
        pending.forEach((w) => (ok ? w.resolve() : w.reject(new Error('signed-out'))));
    };

    const handleSignIn = async (e) => {
        e.preventDefault();
        setBusy(true);
        setError('');
        try {
            await login(user.username, password);
            lastRefresh.current = Date.now();
            capped.current = false;
            setPassword('');
            setMode(null);
            settleWaiters(true);
        } catch (err) {
            const detail = err?.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Sign-in failed. Try again.');
        } finally {
            setBusy(false);
        }
    };

    const handleSignOut = () => {
        settleWaiters(false);
        setMode(null);
        logout();
        navigate('/login', { replace: true, state: { from: location } });
    };

    if (!mode || !user) return null;

    const remaining = tokenExpiryMs() - now;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
            <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="session-dialog-title"
                className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl"
            >
                {mode === 'reauth' ? (
                    <form onSubmit={handleSignIn} className="space-y-4">
                        <div className="flex items-center gap-2">
                            <Lock size={18} className="text-indigo-600" />
                            <h2 id="session-dialog-title" className="text-lg font-bold text-slate-800">
                                Your session has expired
                            </h2>
                        </div>
                        <p className="text-sm text-slate-600">
                            Sign in again to continue. Your work on this page is kept.
                        </p>
                        <div className="text-sm">
                            <span className="text-slate-500">Signed in as </span>
                            <span className="font-semibold text-slate-800">{user.username}</span>
                        </div>
                        <div>
                            <label htmlFor="session-password" className="mb-1 block text-xs font-bold text-slate-600">
                                Password
                            </label>
                            <input
                                id="session-password"
                                type="password"
                                autoFocus
                                autoComplete="current-password"
                                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                            />
                        </div>
                        {error && <p className="text-sm text-red-600">{error}</p>}
                        <div className="flex justify-end gap-2">
                            <button
                                type="button"
                                onClick={handleSignOut}
                                className="rounded-xl border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
                            >
                                Sign out
                            </button>
                            <button
                                type="submit"
                                disabled={busy || !password}
                                className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                            >
                                Sign in
                            </button>
                        </div>
                    </form>
                ) : (
                    <div className="space-y-4">
                        <div className="flex items-center gap-2">
                            <Clock size={18} className="text-amber-500" />
                            <h2 id="session-dialog-title" className="text-lg font-bold text-slate-800">
                                Your session expires in {formatRemaining(remaining)}
                            </h2>
                        </div>
                        {mode === 'capped' ? (
                            <p className="text-sm text-slate-600">
                                Your session reached its maximum length. Sign in again to keep working.
                            </p>
                        ) : (
                            <p className="text-sm text-slate-600">You have been inactive. Keep working?</p>
                        )}
                        <div className="flex justify-end gap-2">
                            <button
                                type="button"
                                onClick={handleSignOut}
                                className="rounded-xl border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
                            >
                                Sign out
                            </button>
                            {mode === 'capped' ? (
                                <button
                                    type="button"
                                    onClick={openReauth}
                                    className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                                >
                                    Sign in again
                                </button>
                            ) : (
                                <button
                                    type="button"
                                    onClick={refresh}
                                    className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                                >
                                    Keep working
                                </button>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default SessionManager;

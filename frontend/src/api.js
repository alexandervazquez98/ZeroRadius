import axios from 'axios';
import { hasReauthHandler, requestReauth } from './session/reauth';

const api = axios.create({
    baseURL: '/api', // Proxied through nginx to backend:8000
});

// Request Interceptor: Attach Token
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Login and refresh 401s belong to their callers (invalid credentials,
// expired session) and must never open the re-auth flow.
const isAuthEndpoint = (url = '') => url.includes('/auth/token') || url.includes('/auth/refresh');

// Response Interceptor: on 401, re-authenticate in place and retry once (#135).
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const config = error.config || {};
        const isUnauthorized = error.response && error.response.status === 401;
        const isAlreadyOnLogin = window.location.pathname === '/login';

        if (!isUnauthorized || isAuthEndpoint(config.url) || isAlreadyOnLogin) {
            return Promise.reject(error);
        }

        if (hasReauthHandler() && !config._retriedAfterReauth) {
            try {
                await requestReauth();
            } catch {
                return Promise.reject(error); // admin signed out; the dialog navigates
            }
            config._retriedAfterReauth = true;
            return api(config);
        }

        // Outside the app shell (no SessionManager mounted): previous behavior.
        localStorage.removeItem('token');
        window.location.href = '/login';
        return Promise.reject(error);
    }
);

export default api;

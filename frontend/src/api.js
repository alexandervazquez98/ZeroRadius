import axios from 'axios';

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

// Response Interceptor: Handle 401 (Logout)
api.interceptors.response.use(
    (response) => response,
    (error) => {
        const isAuthEndpoint = error.config?.url?.includes('/auth/token');
        const isAlreadyOnLogin = window.location.pathname === '/login';

        // No redirigir si el 401 viene del login mismo (credenciales inválidas)
        // ni si ya estamos en /login — evita loops y permite mostrar el error
        if (error.response && error.response.status === 401 && !isAuthEndpoint && !isAlreadyOnLogin) {
            localStorage.removeItem('token');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

export default api;

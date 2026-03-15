import { createContext, useContext, useState, useEffect } from 'react';
import { jwtDecode } from "jwt-decode";
import api from '../api';

const AuthContext = createContext();

/**
 * Parse a JWT token and return user data including role.
 * Returns null if token is invalid.
 */
function parseToken(token) {
    if (!token) return null;
    try {
        const decoded = jwtDecode(token);
        return {
            username: decoded.sub,
            role: decoded.role || null,
            force_change: decoded.force_change || false,
        };
    } catch (e) {
        console.error("Invalid token", e);
        return null;
    }
}

export const AuthProvider = ({ children, initialToken }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Support initialToken prop for testing; otherwise read from localStorage
        const token = initialToken || localStorage.getItem('token');
        const parsed = parseToken(token);
        if (parsed) {
            setUser(parsed);
        } else if (token) {
            // Token was invalid
            localStorage.removeItem('token');
        }
        setLoading(false);
    }, [initialToken]);

    const login = async (username, password) => {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);

        const response = await api.post('/auth/token', formData);
        const { access_token } = response.data;

        localStorage.setItem('token', access_token);

        const parsed = parseToken(access_token);
        setUser(parsed);

        return jwtDecode(access_token);
    };

    const logout = () => {
        localStorage.removeItem('token');
        setUser(null);
    };

    /**
     * Check if the current user has one of the specified roles.
     * @param {string[]} roles - Array of allowed roles
     * @returns {boolean}
     */
    const hasRole = (roles) => {
        if (!user || !user.role) return false;
        return roles.includes(user.role);
    };

    // Expose role directly for convenience
    const role = user?.role || null;

    return (
        <AuthContext.Provider value={{ user, login, logout, loading, role, hasRole }}>
            {!loading && children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);

import React, { createContext, useContext, useState, useCallback } from 'react';
import Toast from '../components/Toast';

const ToastContext = createContext(null);

let _idCounter = 0;

function normalizeToastMessage(message) {
    if (message === null || message === undefined) return '';
    if (typeof message === 'string') return message;
    if (typeof message === 'number' || typeof message === 'boolean' || typeof message === 'bigint') {
        return String(message);
    }
    if (message instanceof Error) {
        return message.message || String(message);
    }
    try {
        return JSON.stringify(message);
    } catch {
        return String(message);
    }
}

export function ToastProvider({ children }) {
    const [toasts, setToasts] = useState([]);

    const showToast = useCallback((message, type = 'info', duration = 3000) => {
        const id = ++_idCounter;
        const safeMessage = normalizeToastMessage(message);
        setToasts(prev => [...prev, { id, message: safeMessage, type, duration }]);
    }, []);

    const removeToast = useCallback((id) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    return (
        <ToastContext.Provider value={{ showToast }}>
            {children}
            <Toast toasts={toasts} onRemove={removeToast} />
        </ToastContext.Provider>
    );
}

export function useToast() {
    const ctx = useContext(ToastContext);
    if (!ctx) {
        throw new Error('useToast must be used inside a ToastProvider');
    }
    return ctx;
}

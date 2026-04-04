import React, { useEffect, useRef } from 'react';

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

const STYLES = {
    success: {
        container: 'bg-green-50 border border-green-200 text-green-900',
        icon: 'text-green-600',
        bar: 'bg-green-500',
    },
    error: {
        container: 'bg-rose-50 border border-rose-200 text-rose-900',
        icon: 'text-rose-600',
        bar: 'bg-rose-500',
    },
    warning: {
        container: 'bg-amber-50 border border-amber-200 text-amber-900',
        icon: 'text-amber-600',
        bar: 'bg-amber-500',
    },
    info: {
        container: 'bg-blue-50 border border-blue-200 text-blue-900',
        icon: 'text-blue-600',
        bar: 'bg-blue-500',
    },
};

const ICONS = {
    success: (
        <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
    ),
    error: (
        <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
    ),
    warning: (
        <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
        </svg>
    ),
    info: (
        <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20A10 10 0 0012 2z" />
        </svg>
    ),
};

function ToastItem({ toast, onRemove }) {
    const { id, message, type, duration } = toast;
    const style = STYLES[type] ?? STYLES.info;
    const timerRef = useRef(null);
    const safeMessage = normalizeToastMessage(message);

    useEffect(() => {
        timerRef.current = setTimeout(() => onRemove(id), duration);
        return () => clearTimeout(timerRef.current);
    }, [id, duration, onRemove]);

    return (
        <div
            className={`relative flex items-start gap-3 px-4 py-3 rounded-lg shadow-md min-w-[260px] max-w-sm overflow-hidden animate-toast-in ${style.container}`}
            role="alert"
            aria-live="assertive"
        >
            <span className={style.icon}>{ICONS[type] ?? ICONS.info}</span>
            <p className="flex-1 text-sm font-medium leading-snug">{safeMessage}</p>
            <button
                onClick={() => onRemove(id)}
                className="shrink-0 opacity-60 hover:opacity-100 transition-opacity ml-1"
                aria-label="Dismiss notification"
            >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
            </button>
            {/* Progress bar */}
            <span
                className={`absolute bottom-0 left-0 h-0.5 ${style.bar} animate-toast-progress`}
                style={{ animationDuration: `${duration}ms` }}
            />
        </div>
    );
}

export default function Toast({ toasts, onRemove }) {
    if (!toasts.length) return null;

    return (
        <div className="fixed bottom-5 right-5 z-[9999] flex flex-col gap-3 items-end">
            {toasts.map(toast => (
                <ToastItem key={toast.id} toast={toast} onRemove={onRemove} />
            ))}
        </div>
    );
}

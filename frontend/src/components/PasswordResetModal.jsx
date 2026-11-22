import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { X, KeyRound } from 'lucide-react';
import api from '../api';
import { PASSWORD_TYPES, PASSWORD_TYPE_HELP } from '../constants/passwordTypes';

// Settable type matching the row's type (case-insensitive); legacy types the
// backend cannot hash (Crypt-Password, SSHA-Password, ...) default to NT-Password.
const defaultType = (attribute) =>
    PASSWORD_TYPES.find(t => t.toLowerCase() === (attribute || '').toLowerCase()) || 'NT-Password';

// Admin password reset for a radcheck password row (#101 B).
// The password is write-only: a typed one is never echoed back, and a
// generated one is shown once, then discarded when the modal closes.
const PasswordResetModal = ({ user, onClose }) => {
    const queryClient = useQueryClient();
    const [passwordType, setPasswordType] = useState(defaultType(user.attribute));
    const [password, setPassword] = useState('');
    const [generated, setGenerated] = useState(null);

    const resetMutation = useMutation({
        mutationFn: (body) => api.post(`/users/check/${user.id}/reset-password`, body).then(r => r.data),
        onSuccess: (data) => {
            queryClient.invalidateQueries(['users']);
            if (data.generated_password) {
                setGenerated(data.generated_password);
            } else {
                onClose();
            }
        },
    });

    const submitTyped = (e) => {
        e.preventDefault();
        resetMutation.mutate({ password, password_type: passwordType });
    };

    const error = resetMutation.error?.response?.data?.detail || resetMutation.error?.message;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg shadow-lg w-full max-w-md">
                <div className="flex justify-between items-center p-4 border-b">
                    <h3 className="text-lg font-bold">Reset password</h3>
                    <button onClick={onClose} className="text-gray-500 hover:text-gray-700" aria-label="Close">
                        <X size={20} />
                    </button>
                </div>
                {generated ? (
                    <div className="p-4 space-y-4">
                        <p className="text-sm text-gray-700">
                            New password for <span className="font-mono">{user.username}</span>. Copy it now: it will not be shown again.
                        </p>
                        <p className="font-mono text-lg bg-gray-100 rounded p-3 break-all select-all">{generated}</p>
                        <div className="flex justify-end">
                            <button
                                type="button"
                                onClick={onClose}
                                className="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                            >
                                Done
                            </button>
                        </div>
                    </div>
                ) : (
                    <form onSubmit={submitTyped} className="p-4 space-y-4">
                        <p className="text-sm text-gray-600">
                            Resetting <span className="font-mono">{user.username}</span>.
                        </p>
                        <div>
                            <label htmlFor="reset-password-type" className="block text-sm font-medium text-gray-700">Password type</label>
                            <select
                                id="reset-password-type"
                                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm border p-2 bg-white"
                                value={passwordType}
                                onChange={e => setPasswordType(e.target.value)}
                            >
                                {PASSWORD_TYPES.map(type => <option key={type} value={type}>{type}</option>)}
                            </select>
                            {PASSWORD_TYPE_HELP[passwordType] && (
                                <p className="mt-1 text-xs text-gray-500">{PASSWORD_TYPE_HELP[passwordType]}</p>
                            )}
                        </div>
                        <div>
                            <label htmlFor="reset-new-password" className="block text-sm font-medium text-gray-700">New password</label>
                            <input
                                id="reset-new-password"
                                type="password"
                                autoComplete="new-password"
                                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm border p-2"
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                            />
                        </div>
                        {error && <p className="text-sm text-red-600">{String(error)}</p>}
                        <div className="flex justify-between gap-2 mt-4">
                            <button
                                type="button"
                                disabled={resetMutation.isPending}
                                onClick={() => resetMutation.mutate({ generate: true, password_type: passwordType })}
                                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 flex items-center gap-2 disabled:opacity-50"
                            >
                                <KeyRound size={16} />
                                Generate password
                            </button>
                            <button
                                type="submit"
                                disabled={resetMutation.isPending || !password}
                                className="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                            >
                                Set password
                            </button>
                        </div>
                    </form>
                )}
            </div>
        </div>
    );
};

export default PasswordResetModal;

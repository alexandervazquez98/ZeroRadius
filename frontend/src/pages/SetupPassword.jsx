import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useParams } from 'react-router-dom';

// Public self-service password setup page (#101 C). The one-time token in the
// URL is the only credential: plain axios is used so an admin token stored
// in the same browser is never attached.
const setupApi = axios.create({ baseURL: '/api' });

const errorText = (err, fallback) => err?.response?.data?.detail || fallback;

const SetupPassword = () => {
    const { token } = useParams();
    const [info, setInfo] = useState(null);
    const [loadError, setLoadError] = useState('');
    const [password, setPassword] = useState('');
    const [confirm, setConfirm] = useState('');
    const [formError, setFormError] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [done, setDone] = useState(false);

    useEffect(() => {
        setupApi.get(`/password-setup/${encodeURIComponent(token)}`)
            .then(r => setInfo(r.data))
            .catch(err => setLoadError(errorText(err, 'This link is not valid')));
    }, [token]);

    const submit = async (e) => {
        e.preventDefault();
        setFormError('');
        if (password !== confirm) {
            setFormError('Passwords do not match');
            return;
        }
        setSubmitting(true);
        try {
            await setupApi.post(`/password-setup/${encodeURIComponent(token)}`, { password });
            setDone(true);
        } catch (err) {
            setFormError(errorText(err, 'Could not set the password'));
        } finally {
            setSubmitting(false);
        }
    };

    let body;
    if (done) {
        body = <p className="text-green-700">Your password has been set. You can now sign in to the network devices with it.</p>;
    } else if (loadError) {
        body = <p className="text-red-600">{loadError}</p>;
    } else if (!info) {
        body = <p className="text-gray-500">Checking link…</p>;
    } else {
        body = (
            <form onSubmit={submit} className="space-y-4">
                <p className="text-sm text-gray-600">
                    Set a new password for <span className="font-mono font-bold">{info.username}</span>.
                    This link works once and expires on {new Date(info.expires_at + 'Z').toLocaleString()}.
                </p>
                <div>
                    <label htmlFor="setup-password" className="block text-sm font-medium text-gray-700">New password</label>
                    <input
                        id="setup-password"
                        type="password"
                        autoComplete="new-password"
                        required
                        className="mt-1 block w-full rounded-md border p-2"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                    />
                </div>
                <div>
                    <label htmlFor="setup-confirm" className="block text-sm font-medium text-gray-700">Confirm password</label>
                    <input
                        id="setup-confirm"
                        type="password"
                        autoComplete="new-password"
                        required
                        className="mt-1 block w-full rounded-md border p-2"
                        value={confirm}
                        onChange={e => setConfirm(e.target.value)}
                    />
                </div>
                {formError && <p className="text-sm text-red-600">{formError}</p>}
                <button
                    type="submit"
                    disabled={submitting}
                    className="w-full py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                    Set password
                </button>
            </form>
        );
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-100 p-4">
            <div className="bg-white rounded-lg shadow-lg w-full max-w-md p-6 space-y-4">
                <h1 className="text-xl font-bold text-slate-800">Set your network password</h1>
                {body}
            </div>
        </div>
    );
};

export default SetupPassword;

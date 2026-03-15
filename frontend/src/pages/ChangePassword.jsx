import { useState } from 'react';
import api from '../api';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

const ChangePassword = () => {
    const [oldPassword, setOldPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const { logout } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (newPassword !== confirmPassword) {
            setError("New passwords do not match");
            return;
        }

        try {
            await api.post('/auth/change-password', {
                old_password: oldPassword,
                new_password: newPassword
            });
            setSuccess("Password changed successfully. Please login again.");
            setTimeout(() => {
                logout();
                navigate('/login');
            }, 2000);
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to change password");
        }
    };

    return (
        <div className="flex items-center justify-center min-h-screen bg-gray-100">
            <div className="px-8 py-6 mt-4 text-left bg-white shadow-lg rounded-xl w-96">
                <h3 className="text-2xl font-bold text-center text-red-600">Change Password Required</h3>
                <p className="text-center text-gray-500 mb-4">You must change your password to continue.</p>

                <form onSubmit={handleSubmit}>
                    <div className="mt-4">
                        <label className="block text-sm font-bold text-gray-700">Old Password</label>
                        <input
                            type="password"
                            className="w-full px-4 py-2 mt-2 border rounded-md focus:outline-none focus:ring-1 focus:ring-blue-600"
                            value={oldPassword}
                            onChange={(e) => setOldPassword(e.target.value)}
                            required
                        />
                    </div>
                    <div className="mt-4">
                        <label className="block text-sm font-bold text-gray-700">New Password</label>
                        <input
                            type="password"
                            className="w-full px-4 py-2 mt-2 border rounded-md focus:outline-none focus:ring-1 focus:ring-blue-600"
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                            required
                        />
                    </div>
                    <div className="mt-4">
                        <label className="block text-sm font-bold text-gray-700">Confirm New Password</label>
                        <input
                            type="password"
                            className="w-full px-4 py-2 mt-2 border rounded-md focus:outline-none focus:ring-1 focus:ring-blue-600"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            required
                        />
                    </div>

                    {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
                    {success && <p className="text-green-500 text-sm mt-2">{success}</p>}

                    <button className="w-full px-6 py-2 mt-4 text-white bg-red-600 rounded-lg hover:bg-red-700">
                        Update Password
                    </button>
                </form>
            </div>
        </div>
    );
};

export default ChangePassword;

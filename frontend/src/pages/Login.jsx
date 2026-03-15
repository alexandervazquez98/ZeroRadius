import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Lock, User } from 'lucide-react';

const Login = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const { login } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const user = await login(username, password);
            if (user.force_change) {
                navigate('/change-password');
            } else {
                navigate('/');
            }
        } catch (err) {
            setError('Invalid credentials');
        }
    };

    return (
        <div className="flex items-center justify-center min-h-screen bg-gray-100">
            <div className="px-8 py-6 mt-4 text-left bg-white shadow-lg rounded-xl w-96">
                <h3 className="text-2xl font-bold text-center text-gray-800">Login to RADIUS</h3>
                <form onSubmit={handleSubmit}>
                    <div className="mt-4">
                        <div className="flex flex-col">
                            <label className="mb-2 text-sm font-bold text-gray-700" htmlFor="username">
                                Username
                            </label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <User className="h-5 w-5 text-gray-400" />
                                </div>
                                <input
                                    type="text"
                                    placeholder="Username"
                                    className="w-full px-4 py-2 pl-10 mt-2 border rounded-md focus:outline-none focus:ring-1 focus:ring-blue-600"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    required
                                />
                            </div>
                        </div>
                        <div className="mt-4 flex flex-col">
                            <label className="mb-2 text-sm font-bold text-gray-700" htmlFor="password">
                                Password
                            </label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Lock className="h-5 w-5 text-gray-400" />
                                </div>
                                <input
                                    type="password"
                                    placeholder="Password"
                                    className="w-full px-4 py-2 pl-10 mt-2 border rounded-md focus:outline-none focus:ring-1 focus:ring-blue-600"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                />
                            </div>
                        </div>
                        {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
                        <div className="flex items-baseline justify-between">
                            <button className="w-full px-6 py-2 mt-4 text-white bg-blue-600 rounded-lg hover:bg-blue-900">Login</button>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default Login;

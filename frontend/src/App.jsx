import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import ProtectedRoute from './components/ProtectedRoute';
import RoleGuard from './components/RoleGuard';
import ErrorBoundary from './components/ErrorBoundary';
import Layout from './components/Layout';
import Login from './pages/Login';
import ChangePassword from './pages/ChangePassword';
import Dashboard from './pages/Dashboard';
import Users from './pages/Users';
import NAS from './pages/NAS';
import Sessions from './pages/Sessions';
import Groups from './pages/Groups';
import Audit from './pages/Audit';
import Dictionaries from './pages/Dictionaries';
import AdminUsers from './pages/AdminUsers';
import PrivilegeMap from './pages/PrivilegeMap';
import IAM from './pages/IAM';
import SyslogDashboard from './pages/SyslogDashboard';

/** Simple page shown when a user lacks permissions to access a route */
function Unauthorized() {
    return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 text-center px-4">
            <div className="w-20 h-20 rounded-full bg-rose-100 flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-10 h-10 text-rose-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 5.636a9 9 0 11-12.728 0M12 9v4m0 4h.01" />
                </svg>
            </div>
            <div>
                <h2 className="text-2xl font-black text-slate-800">Access Denied</h2>
                <p className="text-slate-500 mt-2 max-w-sm">You don't have permission to access this page. Contact your administrator if you believe this is an error.</p>
            </div>
        </div>
    );
}

function App() {
    return (
        <ToastProvider>
        <AuthProvider>
            <BrowserRouter>
                <Routes>
                    <Route path="/login" element={<ErrorBoundary><Login /></ErrorBoundary>} />
                    <Route path="/change-password" element={<ErrorBoundary><ChangePassword /></ErrorBoundary>} />

                    <Route path="/" element={
                        <ProtectedRoute>
                            <Layout />
                        </ProtectedRoute>
                    }>
                        <Route index element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
                        <Route path="users" element={<ErrorBoundary><Users /></ErrorBoundary>} />
                        <Route path="nas" element={<ErrorBoundary><NAS /></ErrorBoundary>} />
                        <Route path="sessions" element={<ErrorBoundary><Sessions /></ErrorBoundary>} />
                        <Route path="groups" element={<ErrorBoundary><Groups /></ErrorBoundary>} />
                        <Route path="audit" element={<ErrorBoundary><Audit /></ErrorBoundary>} />
                        <Route path="dictionaries" element={<ErrorBoundary><Dictionaries /></ErrorBoundary>} />
                        <Route path="iam" element={<ErrorBoundary><IAM /></ErrorBoundary>} />
                        <Route path="syslog" element={<ErrorBoundary><SyslogDashboard /></ErrorBoundary>} />

                        {/* Superadmin-only: System Users */}
                        <Route
                            path="admin-users"
                            element={
                                <ErrorBoundary>
                                    <RoleGuard allowedRoles={['superadmin']} fallback={<Unauthorized />}>
                                        <AdminUsers />
                                    </RoleGuard>
                                </ErrorBoundary>
                            }
                        />

                        {/* Privilege Map: superadmin, admin, auditor */}
                        <Route
                            path="privilege-map"
                            element={
                                <ErrorBoundary>
                                    <RoleGuard allowedRoles={['superadmin', 'admin', 'auditor']} fallback={<Unauthorized />}>
                                        <PrivilegeMap />
                                    </RoleGuard>
                                </ErrorBoundary>
                            }
                        />

                        <Route path="unauthorized" element={<Unauthorized />} />
                    </Route>

                    {/* Fallback */}
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </BrowserRouter>
        </AuthProvider>
        </ToastProvider>
    );
}

export default App;

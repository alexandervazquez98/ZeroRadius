import { useAuth } from '../context/AuthContext';

/**
 * RoleGuard — ISO 27001 A.5.15
 * Renders children only if the current user has one of the allowedRoles.
 * Otherwise renders the fallback (default: null).
 *
 * Usage:
 *   <RoleGuard allowedRoles={['superadmin', 'admin']}>
 *     <SensitiveComponent />
 *   </RoleGuard>
 *
 *   <RoleGuard allowedRoles={['superadmin']} fallback={<span>Access Denied</span>}>
 *     <SuperAdminPanel />
 *   </RoleGuard>
 */
function RoleGuard({ allowedRoles, fallback = null, children }) {
    const { role } = useAuth();
    if (!role || !allowedRoles.includes(role)) return fallback;
    return children;
}

export default RoleGuard;

import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import type { UserRole } from "../types";

export default function ProtectedRoute({ role, allowPasswordChange = false }: { role?: UserRole; allowPasswordChange?: boolean }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="grid min-h-screen place-items-center text-sm font-medium text-slate-500">Restoring your secure session…</div>;
  }
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) return <Navigate to={user.role === "admin" ? "/admin" : "/reviewer"} replace />;
  if (user.must_change_password && !allowPasswordChange) return <Navigate to="/change-password" replace />;
  return <Outlet />;
}

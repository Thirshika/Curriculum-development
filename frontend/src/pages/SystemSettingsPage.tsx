import { Link } from "react-router-dom";
import { KeyRound, ShieldCheck, UserRound } from "lucide-react";
import PortalLayout from "../components/PortalLayout";
import { useAuth } from "../auth/AuthContext";

export default function SystemSettingsPage() {
  const { user } = useAuth();
  return <PortalLayout role="admin">
    <div><p className="text-sm font-medium text-navy">ADMIN WORKSPACE</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">System settings</h1><p className="mt-2 text-sm text-slate-500">Manage your administrator account and access security.</p></div>
    <div className="mt-7 grid max-w-4xl gap-5 md:grid-cols-2">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
        <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-50 text-navy"><UserRound size={18} /></span><h2 className="font-bold text-ink">Administrator profile</h2></div>
        <dl className="mt-5 space-y-3 text-sm"><div><dt className="text-xs font-medium text-slate-500">Name</dt><dd className="mt-1 font-semibold text-slate-800">{user?.full_name ?? "—"}</dd></div><div><dt className="text-xs font-medium text-slate-500">Email</dt><dd className="mt-1 font-semibold text-slate-800">{user?.email ?? "—"}</dd></div><div><dt className="text-xs font-medium text-slate-500">Role</dt><dd className="mt-1 font-semibold capitalize text-slate-800">{user?.role ?? "—"}</dd></div></dl>
      </section>
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
        <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-50 text-emerald-700"><ShieldCheck size={18} /></span><h2 className="font-bold text-ink">Account security</h2></div>
        <p className="mt-4 text-sm leading-relaxed text-slate-600">Use a unique, strong password. Your administrator account does not expose credentials or authentication tokens in this workspace.</p>
        <Link to="/change-password" className="mt-5 inline-flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"><KeyRound size={15} />Change password</Link>
      </section>
    </div>
    <p className="mt-6 max-w-4xl rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-800">Platform-wide integrations and deployment settings are controlled by the server environment and are not editable from this administrator screen.</p>
  </PortalLayout>;
}

import { useEffect, useState } from "react";
import { ArrowUpRight, Building2, CircleCheck, FileText, MessageSquareText, Plus, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import StatCard from "../components/StatCard";
import { useAuth } from "../auth/AuthContext";
import type { AdminDashboardData } from "../types";

export default function AdminDashboard() {
  const { user } = useAuth();
  const [data, setData] = useState<AdminDashboardData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<AdminDashboardData>("/admin/dashboard")
      .then(({ data: dashboard }) => setData(dashboard))
      .catch(() => setError("Dashboard data could not be loaded. Please refresh to try again."));
  }, []);

  return <PortalLayout role="admin">
    <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
      <div><p className="text-sm font-medium text-navy">ADMIN WORKSPACE</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Good day, {user?.full_name.split(" ")[0]}</h1><p className="mt-2 text-sm text-slate-500">Your central overview of the curriculum review platform.</p></div>
      <Link to="/admin/universities" className="inline-flex items-center gap-2 rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#102f5e]"><Plus size={17} />Add university</Link>
    </div>
    {error && <div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard label="Universities" value={data?.total_universities ?? "—"} detail="Registered in the platform" icon={Building2} tone="blue" />
      <StatCard label="Reviewer accounts" value={data?.reviewer_accounts ?? "—"} detail="University reviewer logins" icon={UsersRound} tone="teal" />
      <StatCard label="Programmes" value={data?.total_programmes ?? "—"} detail="University-specific academic programmes" icon={FileText} tone="amber" />
      <StatCard label="Generated drafts" value={data?.total_curricula ?? "—"} detail="AI curriculum drafts ready for review" icon={CircleCheck} tone="green" />
    </div>
    <div className="mt-8 grid gap-5 xl:grid-cols-[1.45fr_0.85fr]">
      <section className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
        <div className="flex items-start justify-between"><div><h2 className="text-base font-bold text-ink">Platform setup</h2><p className="mt-1 text-sm text-slate-500">Build your secure academic review workspace, one step at a time.</p></div><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">Phases 1–8</span></div>
        <div className="mt-6 space-y-1">
          {[{ title: "Secure sign-in and session management", text: "Role-based access for administrators and university reviewers.", done: true }, { title: "Separate role-specific workspaces", text: "Admin and reviewer portals are protected independently.", done: true }, { title: "University and reviewer administration", text: "Create universities and reviewer accounts from the admin portal.", done: true }, { title: "Programme management", text: "Maintain the academic programme details used by curriculum planning.", done: true }, { title: "AI curriculum drafting", text: "Generate editable structured drafts for Admin review.", done: true }, { title: "Curriculum library and publishing", text: "Version, export, and securely publish curriculum documents to assigned university reviewers.", done: true }, { title: "Reviewer document review", text: "Reviewers can provide section comments, upload corrected files, and submit decisions.", done: true }, { title: "Admin feedback and revision workflow", text: "Reply to comments, resolve issues, compare versions, and republish revisions.", done: true }, { title: "Security and deployment readiness", text: "Production configuration, deployment assets, and final integration checks.", done: false }].map((item, index) => <div key={item.title} className="flex gap-4 border-b border-slate-100 py-4 last:border-0">
            <div className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-bold ${item.done ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{item.done ? <CircleCheck size={16} /> : `0${index + 1}`}</div>
            <div className="flex-1"><div className="flex flex-wrap items-center gap-2"><p className="text-sm font-semibold text-slate-800">{item.title}</p>{item.done && <span className="text-[10px] font-semibold uppercase tracking-wide text-emerald-700">Ready</span>}</div><p className="mt-1 text-xs leading-5 text-slate-500">{item.text}</p></div>
          </div>)}
        </div>
      </section>
      <section className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
        <h2 className="text-base font-bold text-ink">Curriculum studio</h2><p className="mt-1 text-sm text-slate-500">Manage generated drafts through publication to the assigned reviewer.</p>
        <Link to="/admin/curricula" className="mt-6 block rounded-xl bg-blue-50/80 p-4 transition hover:bg-blue-50"><div className="flex items-center justify-between"><span className="rounded-md bg-white px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-navy">Phase 6 · Ready</span><ArrowUpRight size={16} className="text-navy" /></div><h3 className="mt-4 text-sm font-bold text-ink">Curriculum library</h3><p className="mt-2 text-xs leading-5 text-slate-600">Review versions, edit snapshots, download Word/PDF documents, and publish a version to its assigned university reviewer.</p></Link>
        <div className="mt-4 flex items-center gap-3 rounded-xl border border-slate-100 p-4"><div className="grid h-9 w-9 place-items-center rounded-lg bg-slate-100 text-slate-500"><UsersRound size={17} /></div><div><p className="text-xs font-semibold text-slate-700">Built for multi-university scale</p><p className="mt-1 text-[11px] text-slate-500">University-level data isolation is foundational.</p></div></div>
        <Link to="/admin/reviews" className="mt-4 block rounded-xl border border-slate-200 p-4 transition hover:bg-slate-50"><div className="flex items-center justify-between"><span className="inline-flex items-center gap-2 text-sm font-bold text-ink"><MessageSquareText size={16} />Reviewer feedback</span><ArrowUpRight size={16} className="text-navy" /></div><p className="mt-2 text-xs leading-5 text-slate-500">Read comments and uploaded documents, reply, resolve feedback, compare versions, and manage revisions.</p></Link>
      </section>
    </div>
    {!data && !error && <p className="mt-5 text-xs text-slate-400">Loading platform metrics…</p>}
  </PortalLayout>;
}

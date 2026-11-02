import { useEffect, useState } from "react";
import { Bell, BookOpen, Clock3, Download, FileCheck2, History, RotateCcw, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import StatCard from "../components/StatCard";
import { useAuth } from "../auth/AuthContext";
import type { CurriculumNotification, ReviewerAssignment, ReviewerDashboardData } from "../types";

export default function ReviewerDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<ReviewerDashboardData | null>(null);
  const [error, setError] = useState("");
  const [assignments, setAssignments] = useState<ReviewerAssignment[]>([]);
  const [notifications, setNotifications] = useState<CurriculumNotification[]>([]);

  useEffect(() => {
    api.get<ReviewerDashboardData>("/reviewer/dashboard")
      .then(({ data: dashboard }) => setData(dashboard))
      .catch(() => setError("Your review overview could not be loaded. Please refresh to try again."));
    api.get<ReviewerAssignment[]>("/curricula/reviewer/assignments")
      .then(({ data: published }) => setAssignments(published))
      .catch(() => setError("Published curricula could not be loaded. Please refresh to try again."));
    api.get<CurriculumNotification[]>("/curricula/reviewer/notifications")
      .then(({ data: items }) => setNotifications(items))
      .catch(() => setError("Your notifications could not be loaded. Please refresh to try again."));
  }, []);

  async function download(assignment: ReviewerAssignment, format: "docx" | "pdf") {
    try {
      const { data } = await api.get(`/curricula/reviewer/assignments/${assignment.id}/download`, {
        params: { format },
        responseType: "blob",
      });
      const url = URL.createObjectURL(data as Blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${assignment.curriculum_title}-v${assignment.version_number}.${format}`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      if (axios.isAxiosError(reason)) setError(reason.response?.data?.detail ?? "The published document could not be downloaded.");
      else setError("The published document could not be downloaded.");
    }

  }

  async function markNotificationRead(notification: CurriculumNotification) {
    try {
      await api.post(`/curricula/reviewer/notifications/${notification.id}/read`);
      setNotifications((current) => current.map((item) =>
        item.id === notification.id ? { ...item, read_at: new Date().toISOString() } : item,
      ));
    } catch (reason) {
      if (axios.isAxiosError(reason)) setError(reason.response?.data?.detail ?? "The notification could not be updated.");
      else setError("The notification could not be updated.");
    }
  }

  return <PortalLayout role="reviewer">
    <div><p className="text-sm font-medium text-teal-700">REVIEWER WORKSPACE</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Welcome, {user?.full_name.split(" ")[0]}</h1><p className="mt-2 text-sm text-slate-500">{user?.university_name ?? "Your university"}{user?.college_name ? ` · ${user.college_name}` : ""} · Your assigned review workspace</p></div>
    {error && <div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    {notifications.length > 0 && <section aria-label="Notifications" className="mt-6 rounded-2xl border border-teal-100 bg-white p-5 shadow-card">
      <h2 className="flex items-center gap-2 text-sm font-bold text-ink"><Bell size={16} />Notifications</h2>
      <div className="mt-3 space-y-2">{notifications.map((notification) => <article key={notification.id} className={`flex items-start justify-between gap-3 rounded-lg p-3 ${notification.read_at ? "bg-slate-50" : "bg-teal-50"}`}>
        <div><p className="text-xs font-semibold text-slate-800">{notification.title}</p><p className="mt-1 text-xs leading-5 text-slate-600">{notification.message}</p><p className="mt-1 text-[10px] text-slate-400">{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(notification.created_at))}</p></div>
        {!notification.read_at && <button onClick={() => void markNotificationRead(notification)} className="shrink-0 text-[11px] font-semibold text-teal-800 hover:underline">Mark read</button>}
      </article>)}</div>
    </section>}
    <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard label="Assigned curricula" value={data?.assigned_curricula ?? "—"} detail="Available to your university" icon={BookOpen} tone="teal" />
      <StatCard label="Pending reviews" value={data?.pending_reviews ?? "—"} detail="Awaiting your review" icon={Clock3} tone="amber" />
      <StatCard label="Revision requested" value={data?.revision_requested ?? "—"} detail="Updated versions to revisit" icon={RotateCcw} tone="blue" />
      <StatCard label="Approved" value={data?.approved_curricula ?? "—"} detail="Reviews completed by your team" icon={FileCheck2} tone="green" />
    </div>
    <section className="mt-8 rounded-2xl border border-slate-200/80 bg-white shadow-card">
      <div className="flex flex-col justify-between gap-3 border-b border-slate-100 px-6 py-5 sm:flex-row sm:items-center"><div><h2 className="text-base font-bold text-ink">Assigned curricula</h2><p className="mt-1 text-sm text-slate-500">Curricula published specifically for your reviewer account.</p></div><span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-teal-50 px-2.5 py-1 text-[11px] font-semibold text-teal-800"><ShieldCheck size={13} />Private reviewer workspace</span></div>
      {assignments.length === 0 ? <div className="grid min-h-[280px] place-items-center px-6 py-12 text-center">
        <div className="max-w-sm"><div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-slate-50 text-slate-400"><History size={25} /></div><h3 className="mt-4 text-sm font-bold text-slate-800">No curricula assigned yet</h3><p className="mt-2 text-xs leading-5 text-slate-500">{data?.university_name ? `New curricula published to ${data.university_name} will appear here.` : "New curricula published to your university will appear here."}</p></div>
      </div> : <div className="divide-y divide-slate-100">{assignments.map((assignment) => <article key={assignment.id} className="flex flex-col justify-between gap-4 px-6 py-5 sm:flex-row sm:items-center">
        <div><h3 className="text-sm font-bold text-slate-800">{assignment.curriculum_title}</h3><p className="mt-1 text-xs text-slate-500">{assignment.programme_name} · Version {assignment.version_number} · {assignment.university_name}</p><p className="mt-1 text-xs text-slate-500">Status: {assignment.status.replace("_", " ")} · Credit validation: {assignment.validation_status}{assignment.deadline ? ` · Due ${assignment.deadline}` : ""}</p></div>
        <div className="flex flex-wrap gap-2"><button onClick={() => navigate(`/reviewer/assignments/${assignment.id}`)} className="inline-flex items-center gap-1.5 rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-xs font-semibold text-teal-800">Review</button><button onClick={() => void download(assignment, "docx")} className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-semibold text-slate-700"><Download size={14} />Word</button><button onClick={() => void download(assignment, "pdf")} className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-semibold text-slate-700"><Download size={14} />PDF</button></div>
      </article>)}</div>}
    </section>
    {!data && !error && <p className="mt-5 text-xs text-slate-400">Loading your review overview…</p>}
  </PortalLayout>;
}

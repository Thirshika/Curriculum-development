import { useEffect, useState } from "react";
import { AlertTriangle, Bell, CheckCircle2, Clock3, ExternalLink, History, UserCircle } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import { useAuth } from "../auth/AuthContext";
import type { CurriculumNotification, ReviewerAssignment, ReviewerReviewData } from "../types";

type ReviewerSection = "assigned" | "review" | "comments" | "compliance" | "history" | "notifications" | "profile";
const headings: Record<ReviewerSection, string> = {
  assigned: "Assigned Curricula",
  review: "Curriculum Review",
  comments: "Comments & Feedback",
  compliance: "Compliance Checklist",
  history: "Review History",
  notifications: "Notifications",
  profile: "My Profile",
};

function getErrorMessage(reason: unknown) {
  return axios.isAxiosError(reason)
    ? reason.response?.data?.detail ?? "The request could not be completed."
    : "The request could not be completed.";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function ReviewerWorkspacePage({ section }: { section: ReviewerSection }) {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [assignments, setAssignments] = useState<ReviewerAssignment[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [review, setReview] = useState<ReviewerReviewData | null>(null);
  const [notifications, setNotifications] = useState<CurriculumNotification[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const selectedAssignment = assignments.find((assignment) => assignment.id === selectedId);

  useEffect(() => {
    if (section === "profile") {
      setLoading(false);
      return;
    }
    if (section === "notifications") {
      api.get<CurriculumNotification[]>("/curricula/reviewer/notifications")
        .then(({ data }) => setNotifications(data))
        .catch((reason: unknown) => setError(getErrorMessage(reason)))
        .finally(() => setLoading(false));
      return;
    }
    api.get<ReviewerAssignment[]>("/curricula/reviewer/assignments")
      .then(({ data }) => {
        setAssignments(data);
        const requestedAssignmentId = new URLSearchParams(location.search).get("assignment_id");
        setSelectedId((current) => data.some((item) => item.id === current)
          ? current
          : data.find((item) => item.id === requestedAssignmentId)?.id ?? data[0]?.id ?? "");
      })
      .catch((reason: unknown) => setError(getErrorMessage(reason)))
      .finally(() => setLoading(false));
  }, [section, location.search]);

  useEffect(() => {
    if (!selectedId || section === "assigned" || section === "review" || section === "notifications" || section === "profile") {
      setReview(null);
      return;
    }
    setLoading(true);
    api.get<ReviewerReviewData>(`/reviews/assignments/${selectedId}`)
      .then(({ data }) => setReview(data))
      .catch((reason: unknown) => setError(getErrorMessage(reason)))
      .finally(() => setLoading(false));
  }, [selectedId, section]);

  async function markRead(notification: CurriculumNotification) {
    setError("");
    try {
      const { data } = await api.post<{ read_at: string }>(`/curricula/reviewer/notifications/${notification.id}/read`);
      setNotifications((current) => current.map((item) => item.id === notification.id ? { ...item, read_at: data.read_at } : item));
    } catch (reason) { setError(getErrorMessage(reason)); }
  }

  const title = headings[section];
  return <PortalLayout role="reviewer">
    <div><p className="text-sm font-medium text-teal-700">REVIEWER WORKSPACE</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">{title}</h1><p className="mt-2 text-sm text-slate-500">{user?.university_name ?? "Your university"}{user?.college_name ? ` · ${user.college_name}` : ""}</p></div>
    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

    {(section === "assigned" || section === "review") && <section className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card">
      <div className="border-b border-slate-100 px-5 py-4"><h2 className="font-bold text-ink">{section === "assigned" ? "Your assigned curricula" : "Curricula ready for review"}</h2><p className="mt-1 text-sm text-slate-500">Each assignment is scoped to your account and assigned college.</p></div>
      {loading ? <p className="p-6 text-sm text-slate-500">Loading assignments…</p> : assignments.length === 0
        ? <p className="p-8 text-center text-sm text-slate-500">No curricula have been assigned to you yet.</p>
        : <div className="divide-y divide-slate-100">{assignments.map((assignment) => <article key={assignment.id} className="flex flex-col justify-between gap-4 p-5 sm:flex-row sm:items-center">
          <div><h3 className="font-semibold text-slate-800">{assignment.curriculum_title}</h3><p className="mt-1 text-sm text-slate-500">{assignment.programme_name} · Version {assignment.version_number}</p><p className="mt-1 text-xs capitalize text-slate-500">{assignment.college_name ? `${assignment.college_name} · ` : ""}{assignment.status.replaceAll("_", " ")} · Credit validation: {assignment.validation_status}{assignment.deadline ? ` · Due ${assignment.deadline}` : ""}</p></div>
          <button onClick={() => navigate(`/reviewer/assignments/${assignment.id}`)} className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-teal-700 px-3 py-2 text-sm font-semibold text-white"><ExternalLink size={15} />Open review</button>
        </article>)}</div>}
    </section>}

    {["comments", "compliance", "history"].includes(section) && <div className="mt-6 grid gap-6 lg:grid-cols-[280px_1fr]">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card">
        <label className="text-xs font-semibold text-slate-600">Select assignment<select value={selectedId} onChange={(event) => setSelectedId(event.target.value)} className="mt-2 w-full rounded-lg border bg-white px-3 py-2.5 text-sm"><option value="">Choose curriculum</option>{assignments.map((assignment) => <option key={assignment.id} value={assignment.id}>{assignment.curriculum_title} · v{assignment.version_number}</option>)}</select></label>
        {selectedAssignment && <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-600"><p className="font-semibold text-slate-800">{selectedAssignment.programme_name}</p><p>{selectedAssignment.status.replaceAll("_", " ")}</p><Link to={`/reviewer/assignments/${selectedAssignment.id}`} className="mt-2 inline-flex items-center gap-1 font-semibold text-teal-800 hover:underline">Open full review<ExternalLink size={12} /></Link></div>}
      </section>
      <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
        {loading ? <p className="text-sm text-slate-500">Loading assignment details…</p> : !review ? <p className="text-sm text-slate-500">Select an assigned curriculum to view its {section === "comments" ? "comments and feedback" : section === "history" ? "review history" : "compliance evidence"}.</p> : <>
          {section === "comments" && <div><h2 className="font-bold text-ink">Comments &amp; feedback</h2>{review.comments.length === 0 ? <p className="mt-4 text-sm text-slate-500">No feedback has been recorded for this assignment.</p> : <div className="mt-4 space-y-4">{review.comments.map((comment) => <article key={comment.id} className="rounded-xl border border-slate-200 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-semibold text-slate-800">{comment.section_path || "General feedback"} <span className="ml-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] capitalize">{comment.priority}</span></p><span className="text-xs capitalize text-slate-500">{comment.status.replaceAll("_", " ")}</span></div><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{comment.body}</p><p className="mt-2 text-xs text-slate-400">{comment.author_name} · {formatDate(comment.created_at)}</p>{comment.replies.map((reply) => <div key={reply.id} className="mt-3 rounded-lg bg-teal-50 p-3"><p className="whitespace-pre-wrap text-sm text-slate-700">{reply.body}</p><p className="mt-2 text-xs text-slate-500">{reply.author_name} · {formatDate(reply.created_at)}</p></div>)}</article>)}</div>}</div>}
          {section === "history" && <div><h2 className="font-bold text-ink">Review history</h2>{review.history.length === 0 ? <p className="mt-4 text-sm text-slate-500">No review history is available yet.</p> : <ol className="mt-4 space-y-4">{review.history.map((entry) => <li key={entry.id} className="flex gap-3"><span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-teal-50 text-teal-800"><History size={15} /></span><div><p className="text-sm font-semibold capitalize text-slate-800">{entry.action.replaceAll("_", " ")}</p><p className="mt-1 text-xs text-slate-500">{entry.actor_name} · Version {entry.version_number} · {formatDate(entry.created_at)}</p>{Object.keys(entry.details).length > 0 && <p className="mt-1 text-xs text-slate-600">{Object.entries(entry.details).map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`).join(" · ")}</p>}</div></li>)}</ol>}</div>}
          {section === "compliance" && <div><h2 className="font-bold text-ink">Compliance checklist</h2><div className="mt-4 rounded-xl border border-blue-100 bg-blue-50 p-4"><p className="text-sm font-semibold text-slate-800">Credit validation: <span className="capitalize">{review.assignment.validation_status}</span></p><p className="mt-1 text-xs leading-5 text-slate-600">This status reports configured numeric credit checks only. It is not a full regulatory compliance approval.</p></div><div className="mt-4 space-y-2">{review.validation_checks.map((check, index) => <article key={`${check.rule_id ?? "check"}-${index}`} className={`rounded-lg p-3 ${check.passed ? "bg-emerald-50" : "bg-amber-50"}`}><p className="flex items-start gap-2 text-sm text-slate-700">{check.passed ? <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-700" /> : <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-700" />}{check.message}</p>{check.document_title && <p className="ml-6 mt-1 text-xs text-slate-500">Evidence: {check.document_title}{check.clause ? ` · ${check.clause}` : ""}{check.page_number ? ` · p. ${check.page_number}` : ""}</p>}</article>)}</div><h3 className="mt-6 text-sm font-bold text-slate-800">Regulatory references</h3>{review.regulatory_references.length === 0 ? <p className="mt-2 text-sm text-slate-500">No regulatory evidence is attached to this version.</p> : <div className="mt-3 space-y-3">{review.regulatory_references.map((reference) => <article key={reference.rule_id} className="rounded-xl border border-slate-200 p-4"><p className="text-sm font-semibold text-slate-800">{reference.title}</p><p className="mt-1 text-xs text-slate-500">{reference.issuing_authority} · Version {reference.version}{reference.clause ? ` · ${reference.clause}` : ""}{reference.page_number ? ` · p. ${reference.page_number}` : ""}</p><p className="mt-2 text-sm leading-6 text-slate-700">{reference.application}</p><details className="mt-2"><summary className="cursor-pointer text-xs font-semibold text-teal-800">View source evidence</summary><p className="mt-2 text-xs leading-5 text-slate-600">{reference.text}</p></details></article>)}</div>}</div>}
        </>}
      </section>
    </div>}

    {section === "notifications" && <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-card"><h2 className="flex items-center gap-2 font-bold text-ink"><Bell size={17} />Your notifications</h2>{loading ? <p className="mt-4 text-sm text-slate-500">Loading notifications…</p> : notifications.length === 0 ? <p className="mt-4 text-sm text-slate-500">You are all caught up. New assignment and feedback notices will appear here.</p> : <div className="mt-4 space-y-3">{notifications.map((notification) => <article key={notification.id} className={`rounded-xl p-4 ${notification.read_at ? "bg-slate-50" : "bg-teal-50"}`}><div className="flex items-start justify-between gap-3"><div><h3 className="text-sm font-semibold text-slate-800">{notification.title}</h3><p className="mt-1 text-sm leading-6 text-slate-600">{notification.message}</p><p className="mt-2 text-xs text-slate-400">{formatDate(notification.created_at)}</p>{notification.assignment_id && <button onClick={() => navigate(`/reviewer/assignments/${notification.assignment_id}`)} className="mt-2 text-xs font-semibold text-teal-800 hover:underline">Open assigned review</button>}</div>{!notification.read_at && <button onClick={() => void markRead(notification)} className="shrink-0 rounded-lg border border-teal-200 px-3 py-1.5 text-xs font-semibold text-teal-800">Mark read</button>}</div></article>)}</div>}</section>}

    {section === "profile" && <div className="mt-6 grid max-w-4xl gap-5 md:grid-cols-2"><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card"><div className="flex items-center gap-3"><UserCircle size={20} className="text-teal-800" /><h2 className="font-bold text-ink">Account details</h2></div><dl className="mt-5 space-y-4 text-sm"><div><dt className="text-xs text-slate-500">Full name</dt><dd className="mt-1 font-semibold text-slate-800">{user?.full_name ?? "—"}</dd></div><div><dt className="text-xs text-slate-500">Email</dt><dd className="mt-1 font-semibold text-slate-800">{user?.email ?? "—"}</dd></div><div><dt className="text-xs text-slate-500">Reviewer ID</dt><dd className="mt-1 font-semibold text-slate-800">{user?.username ?? "—"}</dd></div><div><dt className="text-xs text-slate-500">University / College</dt><dd className="mt-1 font-semibold text-slate-800">{user?.university_name ?? "—"}{user?.college_name ? ` · ${user.college_name}` : " · University-wide reviewer"}</dd></div></dl></section><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card"><div className="flex items-center gap-3"><Clock3 size={20} className="text-teal-800" /><h2 className="font-bold text-ink">Password &amp; security</h2></div><p className="mt-4 text-sm leading-6 text-slate-600">Update your password regularly and keep your sign-in details private.</p><Link to="/change-password" className="mt-5 inline-flex rounded-lg bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white">Change password</Link></section></div>}
  </PortalLayout>;
}

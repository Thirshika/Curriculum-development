import { useCallback, useEffect, useState } from "react";
import { ArrowDownToLine, ArrowUpRight, Bell, Check, CircleAlert, RefreshCw, RotateCcw, Send } from "lucide-react";
import { Link } from "react-router-dom";
import axios from "axios";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { CurriculumNotification, CurriculumVersion, ReviewComment, ReviewerReviewData, ReviewDocument, ReviewHistoryEntry } from "../types";

type ReviewFilter = "" | "pending" | "under_review" | "revision_requested" | "reviewer_recommended" | "reviewer_rejected" | "approved" | "rejected";
type VersionComparison = { path: string; before: string; after: string };

function messageFromError(error: unknown) {
  if (axios.isAxiosError(error)) return error.response?.data?.detail ?? "The request could not be completed.";
  return "The request could not be completed.";
}

function dateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function AdminFeedbackPage() {
  const [reviews, setReviews] = useState<ReviewerReviewData[]>([]);
  const [notifications, setNotifications] = useState<CurriculumNotification[]>([]);
  const [filter, setFilter] = useState<ReviewFilter>("");
  const [replies, setReplies] = useState<Record<string, string>>({});
  const [comparison, setComparison] = useState<{ curriculumId: string; versions: CurriculumVersion[]; from: number; to: number; changes: VersionComparison[] | null } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const loadData = useCallback(async (silent = false) => {
    if (!silent) setError("");
    try {
      const [reviewResponse, notificationResponse] = await Promise.all([
        api.get<ReviewerReviewData[]>("/reviews/assignments", {
          params: { status: filter || undefined, limit: 50 },
        }),
        api.get<CurriculumNotification[]>("/curricula/reviewer/notifications"),
      ]);
      setReviews(reviewResponse.data);
      setNotifications(notificationResponse.data);
    } catch (reason) {
      if (!silent) setError(messageFromError(reason));
    }
  }, [filter]);

  useEffect(() => {
    void loadData();
    const timer = window.setInterval(() => void loadData(true), 15000);
    return () => window.clearInterval(timer);
  }, [loadData]);

  async function submitReply(comment: ReviewComment) {
    const body = replies[comment.id]?.trim();
    if (!body) return;
    setBusy(comment.id);
    setError("");
    try {
      await api.post(`/reviews/comments/${comment.id}/replies`, { body });
      setReplies((current) => ({ ...current, [comment.id]: "" }));
      await loadData(true);
    } catch (reason) {
      setError(messageFromError(reason));
    } finally {
      setBusy(null);
    }
  }

  async function updateCommentStatus(comment: ReviewComment, status: "resolved" | "reopened") {
    setBusy(comment.id);
    setError("");
    try {
      await api.patch(`/reviews/comments/${comment.id}/status`, { status });
      await loadData(true);
    } catch (reason) {
      setError(messageFromError(reason));
    } finally {
      setBusy(null);
    }
  }

  async function recordFinalDecision(assignmentId: string, decision: "approved" | "rejected", reason?: string) {
    setBusy(assignmentId);
    setError("");
    try {
      await api.post(`/reviews/admin/assignments/${assignmentId}/final-decision`, { decision, reason: reason ?? null });
      await loadData(true);
    } catch (reason) {
      setError(messageFromError(reason));
    } finally {
      setBusy(null);
    }
  }

  async function markNotificationRead(notification: CurriculumNotification) {
    try {
      await api.post(`/curricula/reviewer/notifications/${notification.id}/read`);
      setNotifications((current) => current.map((item) =>
        item.id === notification.id ? { ...item, read_at: new Date().toISOString() } : item,
      ));
    } catch (reason) {
      setError(messageFromError(reason));
    }
  }

  async function downloadDocument(document: ReviewDocument) {
    try {
      const { data } = await api.get(`/reviews/documents/${document.id}/download`, { responseType: "blob" });
      const objectUrl = URL.createObjectURL(data as Blob);
      const anchor = window.document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = document.original_filename;
      anchor.click();
      URL.revokeObjectURL(objectUrl);
    } catch (reason) {
      setError(messageFromError(reason));
    }
  }

  async function uploadAdminDocument(assignmentId: string, file?: File) {
    if (!file) return;
    setBusy(assignmentId);
    setError("");
    try {
      const payload = new FormData();
      payload.append("file", file);
      await api.post(`/reviews/admin/assignments/${assignmentId}/documents`, payload, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      await loadData(true);
    } catch (reason) {
      setError(messageFromError(reason));
    } finally {
      setBusy(null);
    }
  }

  async function loadVersions(curriculumId: string) {
    setError("");
    try {
      const { data } = await api.get<CurriculumVersion[]>(`/curricula/${curriculumId}/versions`);
      setComparison({
        curriculumId,
        versions: data,
        from: data[0]?.version_number ?? 1,
        to: data[data.length - 1]?.version_number ?? 1,
        changes: null,
      });
    } catch (reason) {
      setError(messageFromError(reason));
    }
  }

  async function compareVersions() {
    if (!comparison || comparison.from === comparison.to) return;
    setBusy(comparison.curriculumId);
    setError("");
    try {
      const { data } = await api.get<{ changes: VersionComparison[] }>(`/reviews/curricula/${comparison.curriculumId}/compare`, {
        params: { from_version: comparison.from, to_version: comparison.to },
      });
      setComparison((current) => current ? { ...current, changes: data.changes } : current);
    } catch (reason) {
      setError(messageFromError(reason));
    } finally {
      setBusy(null);
    }
  }

  function renderHistory(history: ReviewHistoryEntry[]) {
    if (!history.length) return <p className="text-xs text-slate-400">No review history recorded yet.</p>;
    return <ol className="space-y-2">{history.map((event) => (
      <li key={event.id} className="flex items-start justify-between gap-3 text-xs">
        <span className="font-medium text-slate-700">{event.actor_name} · {event.action.replaceAll("_", " ")}</span>
        <time className="shrink-0 text-slate-400">{dateTime(event.created_at)}</time>
      </li>
    ))}</ol>;
  }

  function renderComment(comment: ReviewComment) {
    return <article key={comment.id} className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-bold text-slate-800">{comment.author_name}</p>
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${comment.priority === "high" ? "bg-rose-50 text-rose-700" : comment.priority === "low" ? "bg-slate-100 text-slate-600" : "bg-amber-50 text-amber-700"}`}>{comment.priority}</span>
            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold capitalize text-blue-700">{comment.status.replaceAll("_", " ")}</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400">Version {comment.version_number} · {dateTime(comment.submitted_at ?? comment.created_at)}</p>
        </div>
        {comment.status === "resolved"
          ? <button onClick={() => void updateCommentStatus(comment, "reopened")} disabled={busy === comment.id} className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 hover:underline disabled:opacity-50"><RotateCcw size={13} />Reopen</button>
          : <button onClick={() => void updateCommentStatus(comment, "resolved")} disabled={busy === comment.id} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 hover:underline disabled:opacity-50"><Check size={13} />Resolve</button>}
      </div>
      {comment.section_path && <p className="mt-3 text-xs font-semibold text-slate-500">Section: {comment.section_path}</p>}
      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{comment.body}</p>
      {comment.replies.length > 0 && <div className="mt-4 space-y-2 border-l-2 border-blue-100 pl-3">
        {comment.replies.map((reply) => <div key={reply.id} className="rounded-lg bg-blue-50/60 p-3">
          <p className="text-[11px] font-semibold text-slate-700">{reply.author_name} · {reply.author_role} · {dateTime(reply.created_at)}</p>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-5 text-slate-600">{reply.body}</p>
        </div>)}
      </div>}
      <form className="mt-4 flex flex-col gap-2 sm:flex-row" onSubmit={(event) => { event.preventDefault(); void submitReply(comment); }}>
        <input value={replies[comment.id] ?? ""} onChange={(event) => setReplies((current) => ({ ...current, [comment.id]: event.target.value }))} className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:outline-none" placeholder="Reply to this reviewer comment" maxLength={8000} />
        <button type="submit" disabled={!replies[comment.id]?.trim() || busy === comment.id} className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-navy px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"><Send size={13} />Reply</button>
      </form>
    </article>;
  }

  return <PortalLayout role="admin">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <p className="text-sm font-medium text-navy">PHASE 8 · FEEDBACK & APPROVALS</p>
        <h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Reviewer feedback</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">Review submitted comments and corrected documents, respond to reviewers, resolve feedback, and continue revisions without replacing prior versions.</p>
      </div>
      <button onClick={() => void loadData()} className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"><RefreshCw size={15} />Refresh</button>
    </div>

    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

    {notifications.length > 0 && <section className="mt-6 rounded-2xl border border-blue-100 bg-white p-5 shadow-card">
      <h2 className="flex items-center gap-2 text-sm font-bold text-ink"><Bell size={16} />Activity notifications</h2>
      <div className="mt-3 space-y-2">{notifications.slice(0, 8).map((notification) => <article key={notification.id} className={`flex items-start justify-between gap-4 rounded-lg p-3 ${notification.read_at ? "bg-slate-50" : "bg-blue-50"}`}>
        <div><p className="text-xs font-semibold text-slate-800">{notification.title}</p><p className="mt-1 text-xs leading-5 text-slate-600">{notification.message}</p><p className="mt-1 text-[10px] text-slate-400">{dateTime(notification.created_at)}</p></div>
        {!notification.read_at && <button onClick={() => void markNotificationRead(notification)} className="shrink-0 text-[11px] font-semibold text-navy hover:underline">Mark read</button>}
      </article>)}</div>
    </section>}

    <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-card sm:flex sm:items-center sm:justify-between">
      <div><h2 className="text-sm font-bold text-slate-800">Published review assignments</h2><p className="mt-1 text-xs text-slate-500">Updates automatically every 15 seconds.</p></div>
      <label className="mt-3 flex items-center gap-2 text-xs font-semibold text-slate-600 sm:mt-0">
        Status
        <select value={filter} onChange={(event) => setFilter(event.target.value as ReviewFilter)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium">
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="under_review">Under review</option>
          <option value="revision_requested">Revision requested</option>
          <option value="reviewer_recommended">Reviewer recommended</option>
          <option value="reviewer_rejected">Reviewer rejected</option>
          <option value="approved">Final approved</option>
          <option value="rejected">Final rejected</option>
        </select>
      </label>
    </section>

    <div className="mt-5 space-y-5">
      {reviews.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
        <CircleAlert className="mx-auto text-slate-300" size={28} />
        <h2 className="mt-3 text-sm font-bold text-slate-700">No matching review assignments</h2>
        <p className="mt-1 text-xs text-slate-500">Published assignments and reviewer feedback will appear here.</p>
      </div> : reviews.map((review) => {
        const { assignment } = review;
        const comments = review.comments.filter((item) => item.is_submitted);
        return <article key={assignment.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card">
          <div className="flex flex-col justify-between gap-4 border-b border-slate-100 bg-slate-50/70 px-5 py-5 lg:flex-row lg:items-center">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base font-bold text-ink">{assignment.curriculum_title}</h2>
                <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold uppercase text-blue-700">{assignment.status.replaceAll("_", " ")}</span>
              </div>
              <p className="mt-1 text-xs text-slate-500">{assignment.university_name} · {assignment.programme_name} · Version {assignment.version_number}</p>
              <p className="mt-1 text-[11px] text-slate-400">Published {dateTime(assignment.published_at)}{assignment.deadline ? ` · Due ${assignment.deadline}` : ""} · {comments.length} submitted comments</p>
              {assignment.status === "reviewer_recommended" && <p className="mt-1 text-[11px] font-semibold text-amber-700">Reviewer recommendation only — final approval is still required.</p>}
              {assignment.status === "approved" && <p className="mt-1 text-[11px] font-semibold text-emerald-700">Final approval recorded by an administrator.</p>}
            </div>
            <div className="flex flex-wrap gap-2">
              {assignment.status === "reviewer_recommended" && <button onClick={() => void recordFinalDecision(assignment.id, "approved")} disabled={busy === assignment.id} className="rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-800 disabled:opacity-50">Final approve</button>}
              {["reviewer_recommended", "reviewer_rejected", "revision_requested"].includes(assignment.status) && <button onClick={() => {
                const reason = window.prompt("Enter the reason for the final rejection:");
                if (reason?.trim()) void recordFinalDecision(assignment.id, "rejected", reason.trim());
              }} disabled={busy === assignment.id} className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50">Final reject</button>}
              <Link to={`/admin/curricula?curriculum_id=${assignment.curriculum_id}`} className="inline-flex items-center justify-center gap-2 rounded-lg bg-navy px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800"><ArrowUpRight size={14} />Edit / create revision</Link>
            </div>
          </div>

          <div className="grid gap-5 p-5 xl:grid-cols-[1.4fr_0.8fr]">
            <section>
              <h3 className="mb-3 text-sm font-bold text-slate-800">Reviewer comments</h3>
              {comments.length === 0 ? <p className="rounded-xl bg-slate-50 p-4 text-xs text-slate-500">No submitted comments on this version.</p> : <div className="space-y-3">{comments.map(renderComment)}</div>}
            </section>
            <aside className="space-y-5">
              <section>
                <h3 className="mb-3 text-sm font-bold text-slate-800">Version comparison</h3>
                {comparison?.curriculumId === assignment.curriculum_id
                  ? <div className="space-y-3 rounded-xl border border-slate-100 p-3">
                    <div className="grid grid-cols-2 gap-2">
                      <label className="text-[11px] font-semibold text-slate-500">From
                        <select value={comparison.from} onChange={(event) => setComparison({ ...comparison, from: Number(event.target.value), changes: null })} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs">
                          {comparison.versions.map((version) => <option key={version.id} value={version.version_number}>Version {version.version_number}</option>)}
                        </select>
                      </label>
                      <label className="text-[11px] font-semibold text-slate-500">To
                        <select value={comparison.to} onChange={(event) => setComparison({ ...comparison, to: Number(event.target.value), changes: null })} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs">
                          {comparison.versions.map((version) => <option key={version.id} value={version.version_number}>Version {version.version_number}</option>)}
                        </select>
                      </label>
                    </div>
                    <button onClick={() => void compareVersions()} disabled={comparison.from === comparison.to || busy === assignment.curriculum_id} className="w-full rounded-lg bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-200 disabled:opacity-50">Compare versions</button>
                    {comparison.changes && <div className="max-h-64 space-y-2 overflow-auto">
                      {comparison.changes.length === 0 ? <p className="text-xs text-slate-500">No content differences found.</p> : comparison.changes.map((change) => <div key={change.path} className="rounded-lg bg-slate-50 p-3">
                        <p className="break-all text-[10px] font-bold text-slate-600">{change.path}</p>
                        <p className="mt-1 break-words text-xs text-rose-700">− {change.before}</p>
                        <p className="mt-1 break-words text-xs text-emerald-700">+ {change.after}</p>
                      </div>)}
                    </div>}
                  </div>
                  : <button onClick={() => void loadVersions(assignment.curriculum_id)} className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-50">Load curriculum versions</button>}
              </section>
              <section>
                <h3 className="mb-3 text-sm font-bold text-slate-800">Uploaded documents</h3>
                {(assignment.status === "pending" || assignment.status === "under_review") && <label className="mb-3 inline-flex w-full cursor-pointer items-center justify-center rounded-lg border border-dashed border-slate-300 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50">
                  {busy === assignment.id ? "Uploading…" : "Attach revised PDF/DOCX"}
                  <input type="file" accept=".pdf,.docx" className="hidden" disabled={busy === assignment.id} onChange={(event) => {
                    void uploadAdminDocument(assignment.id, event.target.files?.[0]);
                    event.target.value = "";
                  }} />
                </label>}
                {review.documents.length === 0 ? <p className="rounded-xl bg-slate-50 p-4 text-xs text-slate-500">No review files uploaded.</p> : <ul className="space-y-2">{review.documents.map((document) => <li key={document.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-3">
                  <div className="min-w-0"><p className="truncate text-xs font-semibold text-slate-700">{document.original_filename}</p><p className="mt-1 text-[10px] text-slate-400">{document.uploader_name} · {(document.file_size / 1024).toFixed(1)} KB · {dateTime(document.created_at)}</p></div>
                  <button onClick={() => void downloadDocument(document)} aria-label={`Download ${document.original_filename}`} className="shrink-0 rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-navy"><ArrowDownToLine size={16} /></button>
                </li>)}</ul>}
              </section>
              <section>
                <h3 className="mb-3 text-sm font-bold text-slate-800">Review history</h3>
                <div className="rounded-xl bg-slate-50 p-4">{renderHistory(review.history)}</div>
              </section>
            </aside>
          </div>
        </article>;
      })}
    </div>
  </PortalLayout>;
}

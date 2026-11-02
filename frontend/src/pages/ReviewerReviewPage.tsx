import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { ArrowDownToLine, ArrowLeft, CheckCircle2, FileUp, MessageSquareText, Send, ShieldCheck } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { CurriculumCourse, CurriculumDraftContent, ReviewerReviewData } from "../types";

function CurriculumDocument({ content }: { content: CurriculumDraftContent }) {
  return <div className="mt-4 max-h-[760px] space-y-5 overflow-auto pr-1">
    <section className="rounded-xl bg-slate-50 p-4">
      <h3 className="text-sm font-bold text-slate-900">Programme overview</h3>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{content.programme_overview}</p>
    </section>
    {content.programme_educational_objectives.length > 0 && <section>
      <h3 className="text-sm font-bold text-slate-900">Educational objectives</h3>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">{content.programme_educational_objectives.map((objective, index) => <li key={`${index}-${objective}`}>{objective}</li>)}</ul>
    </section>}
    {content.programme_outcomes.length > 0 && <section>
      <h3 className="text-sm font-bold text-slate-900">Programme outcomes</h3>
      <div className="mt-2 space-y-2">{content.programme_outcomes.map((outcome) => <p key={outcome.code} className="rounded-lg border border-slate-100 p-3 text-sm leading-6 text-slate-700"><strong className="mr-2 text-slate-900">{outcome.code}</strong>{outcome.statement}</p>)}</div>
    </section>}
    {content.programme_specific_outcomes.length > 0 && <section>
      <h3 className="text-sm font-bold text-slate-900">Programme-specific outcomes</h3>
      <div className="mt-2 space-y-2">{content.programme_specific_outcomes.map((outcome) => <p key={outcome.code} className="rounded-lg border border-slate-100 p-3 text-sm leading-6 text-slate-700"><strong className="mr-2 text-slate-900">{outcome.code}</strong>{outcome.statement}</p>)}</div>
    </section>}
    <section>
      <h3 className="text-sm font-bold text-slate-900">Semester syllabus</h3>
      <div className="mt-3 space-y-4">{content.semesters.map((semester) => <article key={semester.semester_number} className="rounded-xl border border-slate-200 p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2"><h4 className="font-bold text-slate-900">Semester {semester.semester_number}: {semester.title}</h4><span className="text-xs font-medium text-slate-500">{content.credit_distribution.find((item) => item.semester_number === semester.semester_number)?.credits ?? "—"} credits</span></div>
        <div className="mt-3 space-y-3">{semester.courses.map((course) => <CourseCard key={`${semester.semester_number}-${course.course_code}`} course={course} />)}</div>
      </article>)}</div>
    </section>
    {content.regulatory_references.length > 0 && <section>
      <h3 className="text-sm font-bold text-slate-900">Regulatory references</h3>
      <div className="mt-2 space-y-2">{content.regulatory_references.map((reference, index) => <p key={`${reference.rule_id}-${index}`} className="rounded-lg bg-blue-50 p-3 text-sm leading-6 text-slate-700">{reference.application}</p>)}</div>
    </section>}
  </div>;
}

function CourseCard({ course }: { course: CurriculumCourse }) {
  return <details className="rounded-lg border border-slate-100 bg-white p-3">
    <summary className="cursor-pointer list-none"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="text-sm font-semibold text-slate-800">{course.course_code} · {course.title}</p><p className="mt-1 text-xs text-slate-500">{course.category} · {course.credits} credits</p></div><span className="text-xs font-medium text-teal-800">View syllabus</span></div></summary>
    <div className="mt-3 space-y-3 border-t border-slate-100 pt-3">
      <p className="text-sm leading-6 text-slate-600">{course.description}</p>
      {course.learning_objectives.length > 0 && <div><p className="text-xs font-bold uppercase tracking-wide text-slate-500">Learning objectives</p><ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">{course.learning_objectives.map((objective, index) => <li key={`${index}-${objective}`}>{objective}</li>)}</ul></div>}
      {course.course_outcomes.length > 0 && <div><p className="text-xs font-bold uppercase tracking-wide text-slate-500">Course outcomes</p><div className="mt-1 space-y-1">{course.course_outcomes.map((outcome) => <p key={outcome.code} className="text-sm text-slate-700"><strong>{outcome.code}:</strong> {outcome.statement}</p>)}</div></div>}
      {course.units.length > 0 && <div><p className="text-xs font-bold uppercase tracking-wide text-slate-500">Units and topics</p><div className="mt-1 space-y-2">{course.units.map((unit) => <div key={unit.unit_number} className="text-sm text-slate-700"><p className="font-medium">Unit {unit.unit_number}: {unit.title}</p><p className="mt-0.5 text-xs leading-5 text-slate-500">{unit.topics.join(" · ")}</p></div>)}</div></div>}
      <div className="grid gap-3 sm:grid-cols-3">{[
        { label: "Teaching methods", values: course.teaching_methods },
        { label: "Assessment methods", values: course.assessment_methods },
        { label: "Learning resources", values: course.learning_resources },
      ].map(({ label, values }) => <div key={label}><p className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</p><p className="mt-1 text-xs leading-5 text-slate-600">{values.join(" · ") || "Not specified"}</p></div>)}</div>
    </div>
  </details>;
}

export default function ReviewerReviewPage() {
  const { assignmentId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<ReviewerReviewData | null>(null);
  const [error, setError] = useState("");
  const [comment, setComment] = useState("");
  const [sectionPath, setSectionPath] = useState("");
  const [priority, setPriority] = useState<"low" | "normal" | "high">("normal");
  const [editingDraftId, setEditingDraftId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  async function loadReview() {
    if (!assignmentId) return;
    try {
      const { data: review } = await api.get<ReviewerReviewData>(`/reviews/assignments/${assignmentId}`);
      setData(review);
      setError("");
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "The review could not be loaded.";
      setError(message)
    }
  }

  useEffect(() => { void loadReview(); }, [assignmentId]);

  async function saveComment(isSubmitted: boolean) {
    if (!assignmentId || !comment.trim()) return;
    setSaving(true);
    setError("");
    try {
      const payload = {
        body: comment,
        section_path: sectionPath || null,
        priority,
        is_submitted: isSubmitted,
      };
      if (editingDraftId) await api.patch(`/reviews/comments/${editingDraftId}`, payload);
      else await api.post(`/reviews/assignments/${assignmentId}/comments`, payload);
      setComment("");
      setSectionPath("");
      setPriority("normal");
      setEditingDraftId(null);
      await loadReview();
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "The comment could not be saved.";
      setError(message);
    } finally {
      setSaving(false);
    }
  }

  async function uploadDocument(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!assignmentId || !file) return;
    setUploading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      await api.post(`/reviews/assignments/${assignmentId}/documents`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      await loadReview();
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "The document could not be uploaded.";
      setError(message);
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  async function downloadDocument(documentId: string, filename: string) {
    try {
      const { data } = await api.get(`/reviews/documents/${documentId}/download`, { responseType: "blob" });
      const objectUrl = URL.createObjectURL(data as Blob);
      const anchor = window.document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(objectUrl);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "The document could not be downloaded.";
      setError(message);
    }
  }

  async function completeDecision(decision: "revision_requested" | "reviewer_recommended" | "reviewer_rejected", message?: string) {
    if (!assignmentId) return;
    setSaving(true);
    setError("");
    try {
      await api.post(`/reviews/assignments/${assignmentId}/submit`, { decision, message: message || null });
      navigate("/reviewer", { replace: true });
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "The review decision could not be submitted.";
      setError(message);
    } finally {
      setSaving(false);
    }
  }

  if (!data) {
    return <PortalLayout role="reviewer"><div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">Loading review assignment…</div></PortalLayout>;
  }

  const canReview = data.assignment.status === "pending" || data.assignment.status === "under_review";
  const hasDraftComments = data.comments.some((item) => !item.is_submitted);
  const hasSubmittedComments = data.comments.some((item) => item.is_submitted);
  const hasUnresolvedComments = data.comments.some((item) => item.is_submitted && item.status !== "resolved");

  return <PortalLayout role="reviewer">
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-sm font-medium text-teal-700">DOCUMENT REVIEW</p>
        <h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">{data.assignment.curriculum_title}</h1>
        <p className="mt-1 text-sm text-slate-500">{data.assignment.programme_name} · Version {data.assignment.version_number}{data.assignment.college_name ? ` · ${data.assignment.college_name}` : ""}</p>
      </div>
      <Link to="/reviewer" className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"><ArrowLeft size={16} />Back to dashboard</Link>
    </div>

    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

    <div className="mt-6 grid gap-6 xl:grid-cols-[1.5fr_1fr]">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Syllabus under review</p>
            <h2 className="mt-1 text-lg font-bold text-slate-900">{data.assignment.programme_name}</h2>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-50 px-2.5 py-1 text-[11px] font-semibold text-teal-900"><ShieldCheck size={13} />Version {data.assignment.version_number}</span>
        </div>
        <CurriculumDocument content={data.curriculum_content} />
      </section>

      <aside className="space-y-6">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Submit your review</p>
          <div className="mt-4 space-y-3 text-sm text-slate-600">
            <div><span className="font-semibold text-slate-800">Status:</span> {data.assignment.status}</div>
            <div><span className="font-semibold text-slate-800">Deadline:</span> {data.assignment.deadline ?? "No deadline"}</div>
            <div><span className="font-semibold text-slate-800">University:</span> {data.assignment.university_name}</div>
          </div>
          {!canReview && <p className="mt-4 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-600">This review has been submitted. You can still read administrator replies, review history, and attached documents.</p>}
          {canReview && <div className="mt-5 flex flex-wrap gap-2">
            <button onClick={() => void completeDecision("revision_requested", "Please revise the submitted curriculum.")} className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-600" disabled={saving || !hasSubmittedComments || hasDraftComments}><MessageSquareText size={15} />Submit review — request changes</button>
            <button onClick={() => void completeDecision("reviewer_recommended", "Recommended for final approval after review.")} className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700" disabled={saving || hasDraftComments || hasUnresolvedComments}><CheckCircle2 size={15} />Submit review — recommend approval</button>
            <button onClick={() => {
              const reason = window.prompt("Enter the reason for rejecting this curriculum:");
              if (reason?.trim()) void completeDecision("reviewer_rejected", reason.trim());
            }} className="inline-flex items-center gap-2 rounded-lg border border-rose-200 px-3 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50" disabled={saving || hasDraftComments}>Submit review — reject</button>
          </div>}
          {canReview && <p className="mt-3 text-xs leading-5 text-slate-500">Save or submit all feedback first. Requesting changes requires at least one submitted comment. Approval recommendations require submitted comments to be resolved.</p>}
        </div>

        {canReview && <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Upload corrected docs</p>
          <label className="mt-3 inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm font-medium text-slate-700 hover:bg-slate-100">
            <FileUp size={16} />{uploading ? "Uploading…" : "Upload PDF or DOCX"}
            <input type="file" accept=".pdf,.docx" className="hidden" onChange={(event) => void uploadDocument(event)} />
          </label>
          {data.documents.length > 0 && <ul className="mt-4 space-y-2 text-sm text-slate-600">
            {data.documents.map((document) => (
              <li key={document.id} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2">
                <span className="truncate">{document.original_filename}</span>
                <button onClick={() => void downloadDocument(document.id, document.original_filename)} className="inline-flex items-center gap-1 text-teal-700 hover:underline"><ArrowDownToLine size={14} />Download</button>
              </li>
            ))}
          </ul>}
        </div>}
      </aside>
    </div>

    {canReview && <form onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void saveComment(true); }} className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-bold text-slate-900">{editingDraftId ? "Edit review draft" : "Add comments & correction suggestions"}</h2>
        <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-700">{data.comments.length} comments</span>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
        <div>
          <label className="block text-sm font-medium text-slate-700">Comment</label>
          <textarea value={comment} onChange={(event) => setComment(event.target.value)} rows={5} className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 focus:border-teal-400 focus:outline-none" placeholder="Add reviewer feedback, requested revisions, or approval notes." required />
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">Section</label>
            <input value={sectionPath} onChange={(event) => setSectionPath(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 focus:border-teal-400 focus:outline-none" placeholder="Programme overview / Semester 3 / Course Outcomes" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Priority</label>
            <select value={priority} onChange={(event) => setPriority(event.target.value as "low" | "normal" | "high")} className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 focus:border-teal-400 focus:outline-none">
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
            </select>
          </div>
        </div>
      </div>
      <div className="mt-4 flex justify-end">
        <button type="button" onClick={() => void saveComment(false)} disabled={saving || !comment.trim()} className="mr-2 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60">Save draft</button>
        <button type="submit" disabled={saving || !comment.trim()} className="inline-flex items-center gap-2 rounded-lg bg-navy px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"><Send size={15} />{saving ? "Submitting…" : "Submit feedback"}</button>
      </div>
    </form>}

    <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
      <h2 className="text-lg font-bold text-slate-900">Feedback log</h2>
      <div className="mt-4 space-y-3">
        {data.comments.length === 0 ? <p className="text-sm text-slate-500">No comments submitted yet.</p> : data.comments.map((item) => (
          <article key={item.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-800">{item.author_name}</p>
                <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">{item.priority} priority</p>
              </div>
              <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-semibold capitalize text-slate-700">{item.status}</span>
            </div>
            {item.section_path && <p className="mt-2 text-xs text-slate-500">Section: {item.section_path}</p>}
            <p className="mt-2 text-sm leading-6 text-slate-700">{item.body}</p>
            {!item.is_submitted && canReview && <button onClick={() => {
              setEditingDraftId(item.id);
              setComment(item.body);
              setSectionPath(item.section_path ?? "");
              setPriority(item.priority as "low" | "normal" | "high");
              window.scrollTo({ top: 0, behavior: "smooth" });
            }} className="mt-3 text-xs font-semibold text-teal-700 hover:underline">Edit saved draft</button>}
            {item.replies.map((reply) => <div key={reply.id} className="mt-3 rounded-lg bg-white p-3">
              <p className="text-[11px] font-semibold text-slate-600">{reply.author_name} · {reply.author_role}</p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{reply.body}</p>
            </div>)}
          </article>
        ))}
      </div>
    </section>
  </PortalLayout>;
}

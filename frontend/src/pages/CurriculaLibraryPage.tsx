import { FormEvent, useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Archive, Download, FileText, History, LoaderCircle, Search, Send, ShieldCheck, X } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { CurriculumDraftContent, CurriculumLibraryItem, CurriculumVersion, ReviewerAccount, University } from "../types";

function getErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) return error.response?.data?.detail ?? "The request could not be completed.";
  if (error instanceof SyntaxError) return "The curriculum editor contains invalid JSON.";
  return "The request could not be completed.";
}

function errorFilename(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const contentDisposition = error.response?.headers["content-disposition"] as string | undefined;
    const match = contentDisposition?.match(/filename="?([^";]+)"?/i);
    if (match?.[1]) return match[1];
  }
  return fallback;
}

export default function CurriculaLibraryPage() {
  const [searchParams] = useSearchParams();
  const [curricula, setCurricula] = useState<CurriculumLibraryItem[]>([]);
  const [selected, setSelected] = useState<CurriculumLibraryItem | null>(null);
  const [versions, setVersions] = useState<CurriculumVersion[]>([]);
  const [reviewers, setReviewers] = useState<ReviewerAccount[]>([]);
  const [universities, setUniversities] = useState<University[]>([]);
  const [reviewerId, setReviewerId] = useState("");
  const [deadline, setDeadline] = useState("");
  const [title, setTitle] = useState("");
  const [editor, setEditor] = useState("");
  const [viewedVersion, setViewedVersion] = useState<CurriculumVersion | null>(null);
  const [searchText, setSearchText] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [universityFilter, setUniversityFilter] = useState("");
  const [sortBy, setSortBy] = useState<"updated_at" | "title" | "university" | "programme">("updated_at");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadLibrary = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get<CurriculumLibraryItem[]>("/curricula", {
        params: {
          search: search || undefined,
          status: statusFilter || undefined,
          university_id: universityFilter || undefined,
          sort_by: sortBy,
          sort_order: "desc",
        },
      });
      setCurricula(data);
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [search, sortBy, statusFilter, universityFilter]);

  useEffect(() => { void loadLibrary(); }, [loadLibrary]);
  useEffect(() => {
    const curriculumId = searchParams.get("curriculum_id");
    const item = curricula.find((curriculum) => curriculum.id === curriculumId);
    if (item && selected?.id !== item.id) void selectCurriculum(item);
  }, [curricula, searchParams, selected?.id]);
  useEffect(() => {
    api.get<University[]>("/universities", { params: { limit: 100 } })
      .then(({ data }) => setUniversities(data))
      .catch((reason: unknown) => setError(getErrorMessage(reason)));
  }, []);

  async function selectCurriculum(item: CurriculumLibraryItem) {
    setSelected(item);
    setTitle(item.title);
    setViewedVersion(item.current_version);
    setEditor(JSON.stringify(item.current_version.content, null, 2));
    setError("");
    try {
      const [versionResponse, reviewerResponse] = await Promise.all([
        api.get<CurriculumVersion[]>(`/curricula/${item.id}/versions`),
        api.get<ReviewerAccount[]>("/reviewers", { params: { limit: 100 } }),
      ]);
      setVersions(versionResponse.data);
      const assigned = reviewerResponse.data.find((reviewer) =>
        reviewer.university_id === item.university_id &&
        reviewer.college_id === item.college_id &&
        reviewer.is_active &&
        !reviewer.must_change_password,
      );
      setReviewers(reviewerResponse.data.filter((reviewer) =>
        reviewer.university_id === item.university_id &&
        reviewer.college_id === item.college_id &&
        reviewer.is_active &&
        !reviewer.must_change_password,
      ));
      setReviewerId(assigned?.id ?? "");
    } catch (reason) {
      setError(getErrorMessage(reason));
    }
  }

  function chooseVersion(version: CurriculumVersion) {
    setViewedVersion(version);
    setEditor(JSON.stringify(version.content, null, 2));
  }

  async function saveVersion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const content = JSON.parse(editor) as CurriculumDraftContent;
      const { data } = await api.patch<CurriculumLibraryItem>(`/curricula/${selected.id}`, { title, content });
      setSelected(data);
      setTitle(data.title);
      setViewedVersion(data.current_version);
      setEditor(JSON.stringify(data.current_version.content, null, 2));
      setNotice(`Saved as version ${data.current_version_number}. Previous versions remain available in history.`);
      await loadLibrary();
      const { data: history } = await api.get<CurriculumVersion[]>(`/curricula/${selected.id}/versions`);
      setVersions(history);
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function download(format: "docx" | "pdf", versionNumber = viewedVersion?.version_number) {
    if (!selected || versionNumber === undefined) return;
    setBusy(true);
    setError("");
    try {
      const response = await api.get(`/curricula/${selected.id}/versions/${versionNumber}/export`, {
        params: { format },
        responseType: "blob",
      });
      const objectUrl = URL.createObjectURL(response.data as Blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = errorFilename(response, `${selected.title}-v${versionNumber}.${format}`);
      anchor.click();
      URL.revokeObjectURL(objectUrl);
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function publish(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !reviewerId) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const { data } = await api.post<{ warning: string | null }>(`/curricula/${selected.id}/publish`, {
        reviewer_id: reviewerId,
        college_id: selected.college_id,
        deadline: deadline || null,
      });
      setNotice(data.warning
        ? `Published to the assigned university reviewer. ${data.warning}`
        : "Published to the assigned reviewer for this university.");
      await loadLibrary();
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    if (!selected || !window.confirm(`Archive ${selected.title}? Existing published reviewer access will remain tied to its assigned version.`)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const { data } = await api.post<CurriculumLibraryItem>(`/curricula/${selected.id}/archive`);
      setSelected(data);
      setNotice("Curriculum archived. Existing reviewer assignments continue to reference their published version.");
      await loadLibrary();
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSearch(searchText.trim());
  }

  return <PortalLayout role="admin">
    <div>
      <p className="text-sm font-medium text-navy">PHASE 6 · LIBRARY & PUBLISHING</p>
      <h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Curriculum library</h1>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">Find generated curricula, inspect immutable version snapshots, edit into a new version, export Word/PDF documents, and publish a selected version to its university reviewer.</p>
    </div>
    {notice && <div role="status" className="mt-5 flex items-start justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"><span>{notice}</span><button aria-label="Dismiss" onClick={() => setNotice("")}><X size={15} /></button></div>}
    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.4fr)]">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
        <form className="flex gap-2" onSubmit={submitSearch}>
          <label className="relative flex-1"><span className="sr-only">Search curricula</span><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input className="form-input search-input" value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Search title, programme, year" /></label>
          <button className="rounded-lg bg-navy px-3 text-sm font-semibold text-white" aria-label="Search"><Search size={17} /></button>
        </form>
        <label className="mt-3 block text-xs font-medium text-slate-600">Status<select className="form-input mt-1.5" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="">All statuses</option><option value="draft">Draft</option><option value="published">Published</option><option value="archived">Archived</option></select></label>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-medium text-slate-600">University<select className="form-input mt-1.5" value={universityFilter} onChange={(event) => setUniversityFilter(event.target.value)}><option value="">All universities</option>{universities.map((university) => <option key={university.id} value={university.id}>{university.name}</option>)}</select></label>
          <label className="text-xs font-medium text-slate-600">Sort by<select className="form-input mt-1.5" value={sortBy} onChange={(event) => setSortBy(event.target.value as typeof sortBy)}><option value="updated_at">Recently updated</option><option value="title">Curriculum title</option><option value="programme">Programme</option><option value="university">University</option></select></label>
        </div>
        <div className="mt-4 space-y-2">
          {loading && <p className="py-8 text-center text-sm text-slate-400">Loading library…</p>}
          {!loading && curricula.length === 0 && <p className="py-8 text-center text-sm text-slate-500">No curricula found. Add a completed generation draft to the library first.</p>}
          {curricula.map((item) => <button key={item.id} onClick={() => void selectCurriculum(item)} className={`w-full rounded-xl border p-3 text-left transition ${selected?.id === item.id ? "border-blue-200 bg-blue-50" : "border-slate-100 hover:bg-slate-50"}`}>
            <div className="flex items-start justify-between gap-2"><span className="text-sm font-semibold text-slate-800">{item.title}</span><span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${item.status === "published" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>{item.status}</span></div>
            <p className="mt-1 text-xs text-slate-500">{item.university_name} · {item.programme_name} · {item.academic_year}</p>
            <p className="mt-1 text-[11px] text-slate-400">Version {item.current_version_number}</p>
          </button>)}
        </div>
      </section>

      {selected ? <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-5 shadow-card sm:p-6">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
          <div><h2 className="text-lg font-bold text-ink">{selected.title}</h2><p className="mt-1 text-xs text-slate-500">{selected.university_name} · {selected.programme_name} · {selected.academic_year} · viewing v{viewedVersion?.version_number ?? selected.current_version_number}</p></div>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => void download("docx")} disabled={busy} className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-semibold text-slate-700 disabled:opacity-50"><Download size={14} />Word</button>
            <button onClick={() => void download("pdf")} disabled={busy} className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-semibold text-slate-700 disabled:opacity-50"><Download size={14} />PDF</button>
            {selected.status !== "archived" && <button onClick={() => void archive()} disabled={busy} className="inline-flex items-center gap-1.5 rounded-lg border border-rose-100 px-3 py-2 text-xs font-semibold text-rose-700 disabled:opacity-50"><Archive size={14} />Archive</button>}
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2 border-b border-slate-100 pb-4">
          <History size={15} className="text-slate-400" />
          {versions.map((version) => <button key={version.id} onClick={() => chooseVersion(version)} className="rounded-md bg-slate-100 px-2 py-1 text-[11px] font-semibold text-slate-600 hover:bg-blue-50">v{version.version_number}</button>)}
        </div>
        {selected.status !== "archived" && <form onSubmit={saveVersion} className="mt-4">
          <label className="text-xs font-semibold text-slate-700">Curriculum name<input className="form-input mt-2" required minLength={2} maxLength={240} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
          <label className="text-xs font-semibold text-slate-700">Current curriculum JSON (saving creates a version)
            <textarea className="form-input mt-2 min-h-[420px] font-mono text-xs leading-5" spellCheck={false} value={editor} onChange={(event) => setEditor(event.target.value)} />
          </label>
          <div className="mt-3 flex justify-end"><button disabled={busy} className="rounded-lg bg-navy px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Save new version</button></div>
        </form>}
        {selected.status !== "archived" && <form onSubmit={publish} className="mt-5 rounded-xl border border-blue-100 bg-blue-50/60 p-4">
          <h3 className="flex items-center gap-2 text-sm font-bold text-ink"><ShieldCheck size={16} />Publish to university reviewer</h3>
          <p className="mt-1 text-xs leading-5 text-slate-600">Only reviewers assigned to {selected.university_name} are eligible. Publishing does not approve the curriculum.</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="text-xs font-medium text-slate-700">Assigned reviewer<select className="form-input mt-1.5" required value={reviewerId} onChange={(event) => setReviewerId(event.target.value)}><option value="">Select reviewer</option>{reviewers.map((reviewer) => <option key={reviewer.id} value={reviewer.id}>{reviewer.full_name} · {reviewer.college_name ?? "University-wide"} · {reviewer.email}</option>)}</select></label>
            <label className="text-xs font-medium text-slate-700">Review deadline (optional)<input className="form-input mt-1.5" type="date" value={deadline} onChange={(event) => setDeadline(event.target.value)} /></label>
          </div>
          {reviewers.length === 0 && <p className="mt-2 text-xs text-amber-800">An active reviewer with a completed first sign-in password change is required before publishing.</p>}
          <button disabled={busy || !reviewerId} className="mt-3 inline-flex items-center gap-2 rounded-lg bg-navy px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"><Send size={14} />Publish version {selected.current_version_number}</button>
        </form>}
        {selected.status === "published" && <p className="mt-3 flex items-center gap-2 text-xs text-emerald-700"><Archive size={14} />Latest version has been published.</p>}
      </section> : <section className="grid min-h-[400px] place-items-center rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center"><div><FileText size={28} className="mx-auto text-slate-300" /><h2 className="mt-3 text-sm font-semibold text-slate-700">Select a curriculum</h2><p className="mt-1 text-xs text-slate-500">Choose an item from the library to review versions, edit, export, or publish.</p></div></section>}
    </div>
    {busy && <p className="mt-4 inline-flex items-center gap-2 text-xs text-slate-500"><LoaderCircle size={14} className="animate-spin" />Working…</p>}
  </PortalLayout>;
}

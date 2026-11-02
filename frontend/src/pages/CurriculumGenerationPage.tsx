import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { AlertTriangle, ArrowUpRight, FileCheck2, Library, LoaderCircle, Save, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { CurriculumGeneration, Programme } from "../types";

function getErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) return error.response?.data?.detail ?? "The request could not be completed.";
  if (error instanceof SyntaxError) return "The curriculum editor contains invalid JSON.";
  return "The request could not be completed.";
}

function toEditorValue(job: CurriculumGeneration) {
  return job.curriculum ? JSON.stringify(job.curriculum, null, 2) : "";
}

export default function CurriculumGenerationPage() {
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [programmeId, setProgrammeId] = useState("");
  const [generations, setGenerations] = useState<CurriculumGeneration[]>([]);
  const [selected, setSelected] = useState<CurriculumGeneration | null>(null);
  const [editor, setEditor] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [libraryIds, setLibraryIds] = useState<string[]>([]);

  const loadGenerations = useCallback(async (id: string) => {
    if (!id) {
      setGenerations([]);
      setSelected(null);
      setEditor("");
      return;
    }
    const [{ data }, { data: libraryItems }] = await Promise.all([
      api.get<CurriculumGeneration[]>(`/ai-generation/programmes/${id}`),
      api.get<{ generation_job_id: string }[]>("/curricula", { params: { programme_id: id, limit: 100 } }),
    ]);
    setGenerations(data);
    setLibraryIds(libraryItems.map((item) => item.generation_job_id));
    setSelected(data[0] ?? null);
    setEditor(data[0] ? toEditorValue(data[0]) : "");
  }, []);

  useEffect(() => {
    async function loadProgrammes() {
      setLoading(true);
      try {
        const { data } = await api.get<Programme[]>("/programmes", { params: { status: "active", limit: 100 } });
        setProgrammes(data);
        setProgrammeId(data[0]?.id ?? "");
        setError("");
      } catch (reason) {
        setError(getErrorMessage(reason));
      } finally {
        setLoading(false);
      }
    }
    void loadProgrammes();
  }, []);

  useEffect(() => {
    if (!programmeId) return;
    void loadGenerations(programmeId).catch((reason: unknown) => setError(getErrorMessage(reason)));
  }, [loadGenerations, programmeId]);

  function chooseGeneration(job: CurriculumGeneration) {
    setSelected(job);
    setEditor(toEditorValue(job));
    setError("");
  }

  async function generate() {
    if (!programmeId) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const { data } = await api.post<CurriculumGeneration>(`/ai-generation/programmes/${programmeId}`);
      setSelected(data);
      setEditor(toEditorValue(data));
      setGenerations((current) => [data, ...current]);
      setNotice("Curriculum draft generated. Review the source evidence and credit checks before using it.");
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveDraft() {
    if (!selected) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const content: unknown = JSON.parse(editor);
      const { data } = await api.patch<CurriculumGeneration>(`/ai-generation/${selected.id}`, content);
      setSelected(data);
      setEditor(toEditorValue(data));
      setGenerations((current) => current.map((job) => job.id === data.id ? data : job));
      setNotice("Draft saved and its credit distribution recalculated.");
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setBusy(false);
    }

  }

  async function addToLibrary() {
    if (!selected) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.post("/curricula", { generation_job_id: selected.id });
      setLibraryIds((current) => [...current, selected.id]);
      setNotice("Curriculum draft added to the library. You can create new versions, export documents, and publish it there.");
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return <PortalLayout role="admin">
    <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
      <div>
        <p className="text-sm font-medium text-navy">PHASE 5 · AI-ASSISTED DRAFTING</p>
        <h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Curriculum generation</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">Generate a complete structured programme draft using its active, mapped, verified regulatory evidence. Every generated draft remains subject to Admin review.</p>
      </div>
      <Link to="/admin/programmes" className="inline-flex items-center gap-2 text-sm font-semibold text-navy hover:underline">Programme management <ArrowUpRight size={16} /></Link>
    </div>
    <div className="mt-5 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
      <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-700" />
      <p className="text-xs leading-5 text-amber-900"><strong>AI output is a draft, not regulatory approval.</strong> Programme details and retrieved verified excerpts are sent to the configured OpenAI API. Credit checks are recalculated deterministically from the configured verified constraints; a passed check is not full compliance approval.</p>
    </div>
    {notice && <div role="status" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div>}
    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

    <section className="mt-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-card sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <label className="flex-1 text-sm font-medium text-slate-700">Active programme
          <select className="form-input mt-2" value={programmeId} disabled={loading || busy} onChange={(event) => setProgrammeId(event.target.value)}>
            <option value="">Select a programme</option>
            {programmes.map((programme) => <option key={programme.id} value={programme.id}>{programme.university_name} · {programme.name} · {programme.academic_year}</option>)}
          </select>
        </label>
        <button onClick={() => void generate()} disabled={!programmeId || busy || loading} className="inline-flex items-center justify-center gap-2 rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#102f5e] disabled:cursor-not-allowed disabled:opacity-50">
          {busy ? <LoaderCircle className="animate-spin" size={16} /> : <Sparkles size={16} />}
          Generate complete draft
        </button>
      </div>
      {!loading && programmes.length === 0 && <p className="mt-4 text-sm text-slate-500">Create an active programme before generating a curriculum.</p>}
    </section>

    {generations.length > 0 && <div className="mt-6 flex flex-wrap gap-2" aria-label="Generation history">
      {generations.map((job) => <button key={job.id} onClick={() => chooseGeneration(job)} className={`rounded-lg border px-3 py-2 text-xs font-semibold ${selected?.id === job.id ? "border-blue-200 bg-blue-50 text-navy" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}>
        {new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(job.created_at))} · {job.status}
      </button>)}
    </div>}

    {selected && <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-card sm:p-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div><h2 className="text-base font-bold text-ink">Structured curriculum draft</h2><p className="mt-1 text-xs text-slate-500">Model {selected.model} · status {selected.status} · last updated {new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(selected.updated_at))}</p></div>
        {selected.status === "completed" && <div className="flex flex-wrap gap-2"><button onClick={() => void saveDraft()} disabled={busy} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"><Save size={16} />Save edited draft</button><button onClick={() => void addToLibrary()} disabled={busy || libraryIds.includes(selected.id)} className="inline-flex items-center justify-center gap-2 rounded-xl bg-navy px-3 py-2 text-sm font-semibold text-white hover:bg-[#102f5e] disabled:opacity-50"><Library size={16} />{libraryIds.includes(selected.id) ? "In curriculum library" : "Add to library"}</button></div>}
      </div>
      {selected.failure_reason && <p role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{selected.failure_reason}</p>}
      {selected.validation_status && <div className={`mt-4 rounded-lg p-3 text-sm ${selected.validation_status === "passed" ? "bg-emerald-50 text-emerald-800" : selected.validation_status === "failed" ? "bg-rose-50 text-rose-800" : "bg-amber-50 text-amber-900"}`}>
        <p className="font-semibold">Deterministic credit check: {selected.validation_status}</p>
        {selected.validation_checks.map((check, index) => <p key={`${check.rule_id ?? "none"}-${index}`} className="mt-1 text-xs">{check.message}</p>)}
      </div>}
      {selected.curriculum && <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <label className="text-sm font-semibold text-slate-700">Editable curriculum JSON
          <textarea className="form-input mt-2 min-h-[620px] font-mono text-xs leading-5" spellCheck={false} value={editor} onChange={(event) => setEditor(event.target.value)} />
        </label>
        <aside>
          <h3 className="flex items-center gap-2 text-sm font-bold text-ink"><FileCheck2 size={16} />Cited regulatory evidence</h3>
          <div className="mt-3 space-y-3">{selected.regulatory_references.map((reference) => <article key={reference.rule_id} className="rounded-xl border border-slate-200 p-3">
            <p className="text-xs font-semibold text-slate-800">{reference.title} · v{reference.version}</p>
            <p className="mt-1 text-[11px] text-slate-500">{reference.issuing_authority}{reference.clause ? ` · ${reference.clause}` : ""}{reference.page_number ? ` · page ${reference.page_number}` : ""}</p>
            <blockquote className="mt-2 border-l-2 border-blue-200 pl-2 text-xs leading-5 text-slate-600">{reference.text}</blockquote>
            <p className="mt-2 text-[11px] leading-5 text-navy">{reference.application}</p>
          </article>)}</div>
        </aside>
      </div>}
    </section>}
  </PortalLayout>;
}

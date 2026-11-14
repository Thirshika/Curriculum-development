import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { ArrowUpRight, Library, LoaderCircle, Save, Sparkles, Upload, X } from "lucide-react";
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
  const [sampleCurriculumFile, setSampleCurriculumFile] = useState<File | null>(null);
  const [sampleCurriculumUrl, setSampleCurriculumUrl] = useState("");
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

  useEffect(() => {
    if (!sampleCurriculumFile) {
      setSampleCurriculumUrl("");
      return;
    }

    const url = URL.createObjectURL(sampleCurriculumFile);
    setSampleCurriculumUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [sampleCurriculumFile]);

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
      const endpoint = `/ai-generation/programmes/${programmeId}`;
      let response;
      if (sampleCurriculumFile) {
        const formData = new FormData();
        formData.append("sample_curriculum", sampleCurriculumFile);
        response = await api.post<CurriculumGeneration>(endpoint, formData);
      } else {
        response = await api.post<CurriculumGeneration>(endpoint);
      }
      const { data } = response;
      setSelected(data);
      setEditor(toEditorValue(data));
      setGenerations((current) => [data, ...current]);
      setNotice("Curriculum draft generated. Review and edit the draft before using it.");
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
      setNotice("Draft saved.");
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
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">Generate a structured programme draft for Admin review and editing.</p>
      </div>
      <Link to="/admin/programmes" className="inline-flex items-center gap-2 text-sm font-semibold text-navy hover:underline">Programme management <ArrowUpRight size={16} /></Link>
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

    <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-card sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-ink">Sample Curriculum</h2>
          <p className="mt-1 text-sm text-slate-500">Upload a curriculum PDF for the AI to use as a structure and presentation reference.</p>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">
          <Upload size={16} />
          {sampleCurriculumFile ? "Choose another PDF" : "Upload sample curriculum"}
          <input
            type="file"
            accept=".pdf,application/pdf"
            className="sr-only"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
                setError("Choose a PDF file for the sample curriculum.");
                event.target.value = "";
                return;
              }
              setError("");
              setSampleCurriculumFile(file);
            }}
          />
        </label>
      </div>
      <p className="mt-3 text-xs text-slate-500">The selected PDF is sent to the AI only when you generate. Its text is used as a structure reference; Course Library remains authoritative for course names, semesters, and credits. The PDF is not stored by this app.</p>
      {sampleCurriculumFile && sampleCurriculumUrl && <div className="mt-4 overflow-hidden rounded-xl border border-slate-200">
        <div className="flex items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-4 py-2.5">
          <p className="truncate text-sm font-medium text-slate-700">{sampleCurriculumFile.name}</p>
          <button type="button" onClick={() => setSampleCurriculumFile(null)} aria-label="Remove sample curriculum" className="shrink-0 rounded-lg p-1.5 text-slate-500 hover:bg-slate-200 hover:text-slate-800">
            <X size={16} />
          </button>
        </div>
        <iframe title="Sample curriculum PDF preview" src={sampleCurriculumUrl} className="h-[70vh] min-h-[480px] w-full" />
      </div>}
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
      {selected.curriculum && <div className="mt-5">
        <label className="text-sm font-semibold text-slate-700">Editable curriculum JSON
          <textarea className="form-input mt-2 min-h-[620px] font-mono text-xs leading-5" spellCheck={false} value={editor} onChange={(event) => setEditor(event.target.value)} />
        </label>
      </div>}
    </section>}
  </PortalLayout>;
}

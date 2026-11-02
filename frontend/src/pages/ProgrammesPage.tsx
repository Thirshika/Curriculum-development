import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Check, ChevronDown, ChevronUp, CircleAlert, ClipboardCheck, Edit3, GraduationCap, Plus, Search, ShieldCheck, X } from "lucide-react";
import axios from "axios";
import { useLocation } from "react-router-dom";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { College, CreditValidation, Programme, RegulatoryDocument, University } from "../types";

type ProgrammeForm = {
  university_id: string;
  college_id: string;
  name: string;
  degree_type: string;
  specialization: string;
  level: Programme["level"];
  duration_years: string;
  semester_count: string;
  academic_year: string;
  qualification_level: string;
  regulatory_document_ids: string[];
};

const currentYear = new Date().getFullYear();
const emptyForm = (): ProgrammeForm => ({
  university_id: "",
  college_id: "",
  name: "",
  degree_type: "",
  specialization: "",
  level: "ug",
  duration_years: "4",
  semester_count: "8",
  academic_year: `${currentYear}-${currentYear + 1}`,
  qualification_level: "",
  regulatory_document_ids: [],
});

function getErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) return error.response?.data?.detail ?? "The request could not be completed.";
  return "The request could not be completed.";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function ProgrammesPage() {
  const location = useLocation();
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [universities, setUniversities] = useState<University[]>([]);
  const [colleges, setColleges] = useState<College[]>([]);
  const [documents, setDocuments] = useState<RegulatoryDocument[]>([]);
  const [searchText, setSearchText] = useState("");
  const [search, setSearch] = useState("");
  const [form, setForm] = useState<ProgrammeForm>(emptyForm);
  const [editing, setEditing] = useState<Programme | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [selectedProgramme, setSelectedProgramme] = useState<Programme | null>(null);
  const [semesterCredits, setSemesterCredits] = useState("");
  const [validations, setValidations] = useState<CreditValidation[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [offset, setOffset] = useState(0);
  const pageSize = 25;
  const moduleTitle = location.pathname === "/admin/rules"
    ? "Rules & Credit Engine"
    : location.pathname === "/admin/validation"
      ? "Validation & Compliance"
      : "Programme management";

  const loadProgrammes = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get<Programme[]>("/programmes", {
        params: { search: search || undefined, offset, limit: pageSize },
      });
      setProgrammes(data);
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [offset, search]);

  const loadLookups = useCallback(async () => {
    try {
      const [universityResponse, regulationResponse, collegeResponse] = await Promise.all([
        api.get<University[]>("/universities", { params: { limit: 100 } }),
        api.get<RegulatoryDocument[]>("/regulations", { params: { limit: 100 } }),
        api.get<College[]>("/colleges", { params: { limit: 100, status: "active" } }),
      ]);
      setUniversities(universityResponse.data);
      setDocuments(regulationResponse.data);
      setColleges(collegeResponse.data);
    } catch (reason) {
      setError(getErrorMessage(reason));
    }
  }, []);

  useEffect(() => { void loadProgrammes(); }, [loadProgrammes]);
  useEffect(() => { void loadLookups(); }, [loadLookups]);

  const availableDocuments = useMemo(() => documents.filter((document) =>
    (document.status === "ready" || form.regulatory_document_ids.includes(document.id)) &&
    (document.category !== "university" || document.university_id === form.university_id),
  ), [documents, form.university_id]);
  const availableColleges = colleges.filter((college) => college.university_id === form.university_id);

  function startCreate() {
    setEditing(null);
    setForm({ ...emptyForm(), university_id: universities.find((university) => university.status === "active")?.id ?? "" });
    setFormOpen(true);
    setSelectedProgramme(null);
    setError("");
  }

  function startEdit(programme: Programme) {
    setEditing(programme);
    setForm({
      university_id: programme.university_id,
      college_id: programme.college_id ?? "",
      name: programme.name,
      degree_type: programme.degree_type,
      specialization: programme.specialization ?? "",
      level: programme.level,
      duration_years: String(programme.duration_years),
      semester_count: String(programme.semester_count),
      academic_year: programme.academic_year,
      qualification_level: programme.qualification_level ?? "",
      regulatory_document_ids: programme.applicable_regulations
        .map((document) => document.document_id),
    });
    setFormOpen(true);
    setSelectedProgramme(null);
    setError("");
  }

  function setField<K extends keyof ProgrammeForm>(key: K, value: ProgrammeForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function toggleDocument(documentId: string) {
    setForm((current) => ({
      ...current,
      regulatory_document_ids: current.regulatory_document_ids.includes(documentId)
        ? current.regulatory_document_ids.filter((id) => id !== documentId)
        : [...current.regulatory_document_ids, documentId],
    }));
  }

  async function saveProgramme(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const body = {
      ...form,
      college_id: form.college_id || null,
      duration_years: Number(form.duration_years),
      semester_count: Number(form.semester_count),
      specialization: form.specialization.trim() || null,
      qualification_level: form.qualification_level.trim() || null,
    };
    try {
      if (editing) {
        const { university_id: _universityId, ...updates } = body;
        await api.patch(`/programmes/${editing.id}`, updates);
        setNotice("Programme structure updated.");
      } else {
        await api.post("/programmes", body);
        setNotice("Programme created.");
        setOffset(0);
        setSearch("");
        setSearchText("");
      }
      setFormOpen(false);
      setEditing(null);
      await loadProgrammes();
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setSaving(false);
    }
  }

  async function toggleStatus(programme: Programme) {
    const active = programme.status === "inactive";
    if (!window.confirm(`${active ? "Activate" : "Deactivate"} ${programme.name}?`)) return;
    try {
      await api.patch(`/programmes/${programme.id}`, { status: active ? "active" : "inactive" });
      setNotice(`Programme ${active ? "activated" : "deactivated"}.`);
      await loadProgrammes();
    } catch (reason) {
      setError(getErrorMessage(reason));
    }
  }

  async function openValidation(programme: Programme) {
    setSelectedProgramme(programme);
    setFormOpen(false);
    setError("");
    setValidations([]);
    setSemesterCredits(Array.from({ length: programme.semester_count }, () => "0").join(", "));
    try {
      const { data } = await api.get<CreditValidation[]>(`/programmes/${programme.id}/validations`, { params: { limit: 10 } });
      setValidations(data);
    } catch (reason) {
      setError(getErrorMessage(reason));
    }
  }

  async function validateCredits(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProgramme) return;
    const values = semesterCredits.split(",").map((value) => value.trim());
    if (values.length !== selectedProgramme.semester_count || values.some((value) => !value || !Number.isFinite(Number(value)) || Number(value) < 0)) {
      return setError(`Enter exactly ${selectedProgramme.semester_count} non-negative semester credit values, separated by commas.`);
    }
    setSaving(true);
    setError("");
    try {
      const { data } = await api.post<CreditValidation>(`/programmes/${selectedProgramme.id}/validate-credits`, {
        semester_credits: values.map(Number),
      });
      setValidations((current) => [data, ...current]);
      setNotice(data.status === "passed"
        ? `All ${data.configured_constraint_count} configured regulatory check(s) passed. This is not a full compliance approval.`
        : data.status === "failed"
          ? "One or more credit checks failed. See the evidence below."
          : "Validation is incomplete: no applicable verified numeric credit constraints are configured.");
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setSaving(false);
    }
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOffset(0);
    setSearch(searchText.trim());
  }

  return <PortalLayout role="admin">
    <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
      <div><p className="text-sm font-medium text-navy">ADMIN WORKSPACE</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">{moduleTitle}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">Configure programme credit requirements and run repeatable validation checks against numeric constraints explicitly linked to verified regulatory clauses.</p></div>
      <button onClick={startCreate} disabled={!universities.some((university) => university.status === "active")} className="inline-flex items-center justify-center gap-2 rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#102f5e] disabled:opacity-50"><Plus size={17} />Add programme</button>
    </div>
    <div className="mt-5 flex items-start gap-3 rounded-xl border border-blue-100 bg-blue-50/70 px-4 py-3"><ShieldCheck size={18} className="mt-0.5 shrink-0 text-navy" /><p className="text-xs leading-5 text-slate-600"><strong className="text-slate-800">No assumed credit rules.</strong> Credit validations only apply thresholds configured by an Admin from a verified, unconflicted rule in an active source document. Without applicable thresholds, the result is marked incomplete—not compliant.</p></div>
    {notice && <div role="status" className="mt-5 flex items-start justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"><span className="flex items-start gap-2"><Check className="mt-0.5 shrink-0" size={16} />{notice}</span><button aria-label="Dismiss" onClick={() => setNotice("")}><X size={15} /></button></div>}
    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

    {formOpen && <section className="mt-7 rounded-2xl border border-blue-100 bg-white p-5 shadow-card sm:p-6">
      <div className="flex items-start justify-between"><div><h2 className="text-base font-bold text-ink">{editing ? "Edit programme" : "Create programme"}</h2><p className="mt-1 text-sm text-slate-500">Define the academic structure and applicable regulatory source documents.</p></div><button onClick={() => setFormOpen(false)} aria-label="Close form" className="rounded-lg p-2 text-slate-400 hover:bg-slate-50"><X size={18} /></button></div>
      <form className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" onSubmit={saveProgramme}>
        <label className="text-sm font-medium text-slate-700">University<select className="form-input mt-2" required disabled={Boolean(editing)} value={form.university_id} onChange={(event) => { setField("university_id", event.target.value); setField("college_id", ""); setField("regulatory_document_ids", []); }}><option value="" disabled>Select an active university</option>{universities.filter((university) => university.status === "active").map((university) => <option key={university.id} value={university.id}>{university.name} ({university.code})</option>)}</select></label>
        <label className="text-sm font-medium text-slate-700">College<select className="form-input mt-2" value={form.college_id} onChange={(event) => setField("college_id", event.target.value)}><option value="">University-wide programme</option>{availableColleges.map((college) => <option key={college.id} value={college.id}>{college.name} ({college.code})</option>)}</select></label>
        <label className="text-sm font-medium text-slate-700 lg:col-span-2">Programme name<input className="form-input mt-2" required minLength={2} maxLength={240} value={form.name} onChange={(event) => setField("name", event.target.value)} placeholder="B.E. Computer Science and Engineering" /></label>
        <label className="text-sm font-medium text-slate-700">Degree type<input className="form-input mt-2" required minLength={2} maxLength={120} value={form.degree_type} onChange={(event) => setField("degree_type", event.target.value)} placeholder="B.E., B.Sc., M.A." /></label>
        <label className="text-sm font-medium text-slate-700">Specialization<input className="form-input mt-2" maxLength={200} value={form.specialization} onChange={(event) => setField("specialization", event.target.value)} placeholder="Computer Science and Engineering" /></label>
        <label className="text-sm font-medium text-slate-700">Programme level<select className="form-input mt-2" value={form.level} onChange={(event) => setField("level", event.target.value as Programme["level"])}><option value="ug">Undergraduate</option><option value="pg">Postgraduate</option><option value="doctoral">Doctoral</option><option value="certificate">Certificate</option><option value="diploma">Diploma</option><option value="other">Other</option></select></label>
        <label className="text-sm font-medium text-slate-700">Duration (years)<input className="form-input mt-2" type="number" min="0.01" max="12" step="0.25" required value={form.duration_years} onChange={(event) => setField("duration_years", event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Number of semesters<input className="form-input mt-2" type="number" min="1" max="24" step="1" required value={form.semester_count} onChange={(event) => setField("semester_count", event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Academic year<input className="form-input mt-2" required pattern="20[0-9]{2}-20[0-9]{2}" title="Use a year range such as 2027-2028" maxLength={9} value={form.academic_year} onChange={(event) => setField("academic_year", event.target.value)} placeholder="2027-2028" /></label>
        <label className="text-sm font-medium text-slate-700 lg:col-span-3">Qualification level<input className="form-input mt-2" maxLength={100} value={form.qualification_level} onChange={(event) => setField("qualification_level", event.target.value)} placeholder="Optional framework or qualification level label" /></label>
        <fieldset className="rounded-xl border border-slate-200 p-4 sm:col-span-2 lg:col-span-3"><legend className="px-1 text-sm font-semibold text-slate-700">Applicable regulatory documents</legend>{availableDocuments.length ? <div className="grid gap-2 sm:grid-cols-2">{availableDocuments.map((document) => <label key={document.id} className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-100 p-3 hover:bg-slate-50"><input className="mt-1 accent-navy" type="checkbox" checked={form.regulatory_document_ids.includes(document.id)} onChange={() => toggleDocument(document.id)} /><span><span className="block text-xs font-semibold text-slate-700">{document.title}</span><span className="mt-1 block text-[11px] text-slate-500">{document.issuing_authority} · v{document.version}{document.category === "university" ? ` · ${document.university_name}` : ""} · {document.verified_rules} verified rules</span></span></label>)}</div> : <p className="text-xs text-slate-500">No active regulatory sources are available. Upload sources in the regulatory knowledge base first.</p>}<p className="mt-3 text-[11px] leading-5 text-slate-500">Only active sources can be selected. University-specific regulations are limited to the selected university.</p></fieldset>
        <div className="flex justify-end gap-3 sm:col-span-2 lg:col-span-3"><button type="button" onClick={() => setFormOpen(false)} className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50">Cancel</button><button disabled={saving} className="rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{saving ? "Saving…" : editing ? "Save programme" : "Create programme"}</button></div>
      </form>
    </section>}

    {selectedProgramme && <section className="mt-7 rounded-2xl border border-blue-100 bg-white p-5 shadow-card sm:p-6">
      <div className="flex items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-wide text-navy">Deterministic credit validator</p><h2 className="mt-1 text-lg font-bold text-ink">{selectedProgramme.name}</h2><p className="mt-1 text-sm text-slate-500">{selectedProgramme.university_name} · {selectedProgramme.duration_years} years · {selectedProgramme.semester_count} semesters</p></div><button onClick={() => setSelectedProgramme(null)} aria-label="Close validator" className="rounded-lg p-2 text-slate-400 hover:bg-slate-50"><X size={18} /></button></div>
      <form onSubmit={validateCredits} className="mt-5"><label className="block text-sm font-medium text-slate-700">Credits per semester<input className="form-input mt-2" required value={semesterCredits} onChange={(event) => setSemesterCredits(event.target.value)} placeholder={`Enter ${selectedProgramme.semester_count} values separated by commas`} /><span className="mt-1.5 block text-xs font-normal text-slate-500">Enter exactly {selectedProgramme.semester_count} non-negative numeric values, in semester order. The total is calculated by the server.</span></label><div className="mt-4 flex justify-end"><button disabled={saving} className="inline-flex items-center gap-2 rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"><ClipboardCheck size={16} />{saving ? "Validating…" : "Run credit validation"}</button></div></form>
      {validations.length > 0 && <div className="mt-6 space-y-4">{validations.map((validation) => <article key={validation.id} className="rounded-xl border border-slate-200 p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm font-bold text-slate-800">Total credits: {validation.total_credits}</p><p className="mt-1 text-xs text-slate-500">Semester plan: {validation.semester_credits.join(" · ")}</p></div><div className="text-right"><span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${validation.status === "passed" ? "bg-emerald-50 text-emerald-700" : validation.status === "failed" ? "bg-rose-50 text-rose-700" : "bg-amber-50 text-amber-800"}`}>{validation.status}</span><p className="mt-1 text-[10px] text-slate-400">{formatDate(validation.created_at)}</p></div></div><div className="mt-4 space-y-2">{validation.checks.map((check, index) => <div key={`${check.rule_id ?? "structural"}-${index}`} className={`rounded-lg px-3 py-2.5 ${check.passed ? "bg-emerald-50/70" : validation.status === "incomplete" ? "bg-amber-50" : "bg-rose-50"}`}><div className="flex items-start gap-2"><span className={`mt-0.5 ${check.passed ? "text-emerald-700" : validation.status === "incomplete" ? "text-amber-700" : "text-rose-700"}`}>{check.passed ? <Check size={15} /> : <CircleAlert size={15} />}</span><div><p className="text-xs font-medium text-slate-700">{check.message}</p>{check.document_title && <p className="mt-1 text-[11px] text-slate-500">Evidence: {check.document_title}{check.clause ? ` · ${check.clause}` : ""}{check.page_number ? ` · p. ${check.page_number}` : ""} · v{check.version}</p>}</div></div></div>)}</div><p className="mt-3 text-[11px] leading-5 text-slate-500">A passed result means the configured checks passed only. It is not a full regulatory compliance approval.</p></article>)}</div>}
    </section>}

    <section className="mt-7 overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-card">
      <div className="flex flex-col justify-between gap-4 border-b border-slate-100 px-5 py-5 sm:flex-row sm:items-center sm:px-6"><div><h2 className="text-base font-bold text-ink">Academic programmes</h2><p className="mt-1 text-sm text-slate-500">University-specific programme structures and configured regulations.</p></div><form onSubmit={submitSearch} className="flex gap-2"><div className="relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} /><input className="form-input h-10 w-full pl-9 sm:w-64" value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Search programmes" /></div><button className="rounded-xl border border-slate-200 px-3 text-sm font-semibold text-slate-600 hover:bg-slate-50">Search</button></form></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[1050px] text-left text-sm"><thead className="bg-slate-50/80 text-[11px] font-semibold uppercase tracking-wide text-slate-500"><tr><th className="px-6 py-3">Programme</th><th className="px-6 py-3">University</th><th className="px-6 py-3">Structure</th><th className="px-6 py-3">Academic year</th><th className="px-6 py-3">Regulations</th><th className="px-6 py-3">Status</th><th className="px-6 py-3 text-right">Actions</th></tr></thead><tbody className="divide-y divide-slate-100">
        {loading && <tr><td colSpan={7} className="px-6 py-12 text-center text-sm text-slate-500">Loading programmes…</td></tr>}
        {!loading && programmes.length === 0 && <tr><td colSpan={7} className="px-6 py-14 text-center"><div className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-slate-50 text-slate-400"><GraduationCap size={21} /></div><p className="mt-3 text-sm font-semibold text-slate-700">No programmes found</p><p className="mt-1 text-xs text-slate-500">Create a programme for an active university to begin.</p></td></tr>}
        {!loading && programmes.map((programme) => <tr key={programme.id} className="hover:bg-slate-50/60"><td className="px-6 py-4"><p className="font-semibold text-slate-800">{programme.name}</p><p className="mt-1 text-xs text-slate-500">{programme.degree_type}{programme.specialization ? ` · ${programme.specialization}` : ""} · {programme.level.toUpperCase()}</p></td><td className="px-6 py-4"><p className="font-medium text-slate-700">{programme.university_name}</p><p className="mt-1 text-xs text-slate-500">{programme.university_code}</p></td><td className="px-6 py-4 text-slate-600">{programme.duration_years} years · {programme.semester_count} semesters</td><td className="px-6 py-4 text-slate-600">{programme.academic_year}</td><td className="px-6 py-4"><p className="text-xs font-medium text-slate-700">{programme.applicable_regulations.length} selected source{programme.applicable_regulations.length === 1 ? "" : "s"}</p><p className="mt-1 text-xs text-slate-500">{programme.applicable_regulations.reduce((sum, item) => sum + item.constraints.length, 0)} configured numeric checks</p></td><td className="px-6 py-4"><span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${programme.status === "active" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{programme.status}</span></td><td className="px-6 py-4"><div className="flex justify-end gap-2"><button onClick={() => void openValidation(programme)} className="rounded-lg border border-blue-100 px-2.5 py-2 text-xs font-semibold text-navy hover:bg-blue-50">Validate credits</button><button onClick={() => startEdit(programme)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"><Edit3 size={14} />Edit</button><button onClick={() => void toggleStatus(programme)} className={`rounded-lg px-2.5 py-2 text-xs font-semibold ${programme.status === "active" ? "border border-rose-100 text-rose-600 hover:bg-rose-50" : "border border-emerald-100 text-emerald-700 hover:bg-emerald-50"}`}>{programme.status === "active" ? "Deactivate" : "Activate"}</button></div></td></tr>)}
      </tbody></table></div>
      <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3 sm:px-6"><p className="text-xs text-slate-500">Showing {programmes.length ? offset + 1 : 0}–{offset + programmes.length}</p><div className="flex gap-2"><button disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - pageSize))} aria-label="Previous page" className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-2 text-xs font-semibold text-slate-600 disabled:opacity-40"><ChevronUp className="rotate-[-90deg]" size={15} />Previous</button><button disabled={programmes.length < pageSize || loading} onClick={() => setOffset(offset + pageSize)} aria-label="Next page" className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-2 text-xs font-semibold text-slate-600 disabled:opacity-40">Next<ChevronDown className="rotate-[-90deg]" size={15} /></button></div></div>
    </section>
  </PortalLayout>;
}

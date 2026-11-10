import { FormEvent, useCallback, useEffect, useState } from "react";
import { Check, Edit3, Plus, Search, X } from "lucide-react";
import axios from "axios";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { College, Programme, University } from "../types";

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
});

function getErrorMessage(error: unknown) {
  return axios.isAxiosError(error) ? error.response?.data?.detail ?? "The request could not be completed." : "The request could not be completed.";
}

export default function ProgrammesPage() {
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [universities, setUniversities] = useState<University[]>([]);
  const [colleges, setColleges] = useState<College[]>([]);
  const [searchText, setSearchText] = useState("");
  const [search, setSearch] = useState("");
  const [form, setForm] = useState<ProgrammeForm>(emptyForm);
  const [editing, setEditing] = useState<Programme | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [offset, setOffset] = useState(0);
  const pageSize = 25;

  const loadProgrammes = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get<Programme[]>("/programmes", { params: { search: search || undefined, offset, limit: pageSize } });
      setProgrammes(data);
    } catch (reason) { setError(getErrorMessage(reason)); }
    finally { setLoading(false); }
  }, [offset, search]);

  useEffect(() => { void loadProgrammes(); }, [loadProgrammes]);
  useEffect(() => {
    Promise.all([
      api.get<University[]>("/universities", { params: { limit: 100 } }),
      api.get<College[]>("/colleges", { params: { limit: 100, status: "active" } }),
    ]).then(([universityResponse, collegeResponse]) => {
      setUniversities(universityResponse.data);
      setColleges(collegeResponse.data);
    }).catch((reason: unknown) => setError(getErrorMessage(reason)));
  }, []);

  const availableColleges = colleges.filter((college) => college.university_id === form.university_id);

  function setField<K extends keyof ProgrammeForm>(key: K, value: ProgrammeForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function startCreate() {
    setEditing(null);
    setForm({ ...emptyForm(), university_id: universities.find((university) => university.status === "active")?.id ?? "" });
    setFormOpen(true);
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
    });
    setFormOpen(true);
    setError("");
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
        setNotice("Programme updated.");
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
    } catch (reason) { setError(getErrorMessage(reason)); }
    finally { setSaving(false); }
  }

  async function toggleStatus(programme: Programme) {
    const active = programme.status === "inactive";
    if (!window.confirm(`${active ? "Activate" : "Deactivate"} ${programme.name}?`)) return;
    try {
      await api.patch(`/programmes/${programme.id}`, { status: active ? "active" : "inactive" });
      setNotice(`Programme ${active ? "activated" : "deactivated"}.`);
      await loadProgrammes();
    } catch (reason) { setError(getErrorMessage(reason)); }
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOffset(0);
    setSearch(searchText.trim());
  }

  return <PortalLayout role="admin">
    <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
      <div><p className="text-sm font-medium text-navy">ADMIN WORKSPACE</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Programme management</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">Maintain the academic programme details used by curriculum planning and review.</p></div>
      <button onClick={startCreate} disabled={!universities.some((university) => university.status === "active")} className="inline-flex items-center justify-center gap-2 rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><Plus size={17} />Add programme</button>
    </div>
    {notice && <div role="status" className="mt-5 flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"><Check className="mt-0.5 shrink-0" size={16} />{notice}</div>}
    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    {formOpen && <section className="mt-7 rounded-2xl border border-blue-100 bg-white p-5 shadow-card sm:p-6">
      <div className="flex items-start justify-between"><div><h2 className="text-base font-bold text-ink">{editing ? "Edit programme" : "Create programme"}</h2><p className="mt-1 text-sm text-slate-500">Set the academic scope for this programme.</p></div><button onClick={() => setFormOpen(false)} aria-label="Close form" className="rounded-lg p-2 text-slate-400 hover:bg-slate-50"><X size={18} /></button></div>
      <form className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" onSubmit={saveProgramme}>
        <label className="text-sm font-medium text-slate-700">University<select className="form-input mt-2" required disabled={Boolean(editing)} value={form.university_id} onChange={(event) => { setField("university_id", event.target.value); setField("college_id", ""); }}><option value="" disabled>Select an active university</option>{universities.filter((university) => university.status === "active").map((university) => <option key={university.id} value={university.id}>{university.name} ({university.code})</option>)}</select></label>
        <label className="text-sm font-medium text-slate-700">College<select className="form-input mt-2" value={form.college_id} onChange={(event) => setField("college_id", event.target.value)}><option value="">University-wide programme</option>{availableColleges.map((college) => <option key={college.id} value={college.id}>{college.name} ({college.code})</option>)}</select></label>
        <label className="text-sm font-medium text-slate-700 lg:col-span-2">Programme name<input className="form-input mt-2" required minLength={2} maxLength={240} value={form.name} onChange={(event) => setField("name", event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Degree type<input className="form-input mt-2" required minLength={2} maxLength={120} value={form.degree_type} onChange={(event) => setField("degree_type", event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Specialization<input className="form-input mt-2" maxLength={200} value={form.specialization} onChange={(event) => setField("specialization", event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Programme level<select className="form-input mt-2" value={form.level} onChange={(event) => setField("level", event.target.value as Programme["level"])}><option value="ug">Undergraduate</option><option value="pg">Postgraduate</option><option value="doctoral">Doctoral</option><option value="certificate">Certificate</option><option value="diploma">Diploma</option><option value="other">Other</option></select></label>
        <label className="text-sm font-medium text-slate-700">Duration (years)<input className="form-input mt-2" type="number" min="0.01" max="12" step="0.25" required value={form.duration_years} onChange={(event) => setField("duration_years", event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Number of semesters<input className="form-input mt-2" type="number" min="1" max="24" step="1" required value={form.semester_count} onChange={(event) => setField("semester_count", event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Academic year<input className="form-input mt-2" required pattern="20[0-9]{2}-20[0-9]{2}" title="Use a year range such as 2027-2028" maxLength={9} value={form.academic_year} onChange={(event) => setField("academic_year", event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Qualification level<input className="form-input mt-2" maxLength={100} value={form.qualification_level} onChange={(event) => setField("qualification_level", event.target.value)} /></label>
        <div className="flex items-end gap-3 sm:col-span-2 lg:col-span-3"><button disabled={saving} className="rounded-xl bg-navy px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{saving ? "Saving…" : editing ? "Save changes" : "Create programme"}</button><button type="button" onClick={() => setFormOpen(false)} className="rounded-xl border border-slate-200 px-5 py-2.5 text-sm font-semibold text-slate-600">Cancel</button></div>
      </form>
    </section>}
    <section className="mt-7 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card">
      <form onSubmit={submitSearch} className="flex gap-2 border-b border-slate-100 p-4"><div className="relative flex-1"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} /><input value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Search programmes" className="search-input w-full rounded-lg border py-2 pr-3 text-sm" /></div><button className="rounded-lg bg-slate-100 px-4 text-sm font-semibold text-slate-700">Search</button></form>
      {loading ? <p className="p-8 text-sm text-slate-500">Loading programmes…</p> : programmes.length === 0 ? <p className="p-8 text-center text-sm text-slate-500">No programmes found.</p> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{["Programme", "University", "Academic year", "Status", "Actions"].map((item) => <th key={item} className="px-5 py-3 font-semibold">{item}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{programmes.map((programme) => <tr key={programme.id}><td className="px-5 py-4"><p className="font-semibold text-slate-800">{programme.name}</p><p className="mt-1 text-xs text-slate-500">{programme.degree_type} · {programme.semester_count} semesters</p></td><td className="px-5 py-4">{programme.university_name}</td><td className="px-5 py-4">{programme.academic_year}</td><td className="px-5 py-4 capitalize">{programme.status}</td><td className="px-5 py-4"><div className="flex gap-2"><button onClick={() => startEdit(programme)} className="inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs font-semibold"><Edit3 size={13} />Edit</button><button onClick={() => void toggleStatus(programme)} className="rounded-lg border px-2.5 py-1.5 text-xs font-semibold">{programme.status === "active" ? "Deactivate" : "Activate"}</button></div></td></tr>)}</tbody></table></div>}
      <div className="flex justify-between border-t border-slate-100 px-5 py-3"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))} className="text-sm font-semibold text-navy disabled:opacity-40">Previous</button><button disabled={programmes.length < pageSize} onClick={() => setOffset(offset + pageSize)} className="text-sm font-semibold text-navy disabled:opacity-40">Next</button></div>
    </section>
  </PortalLayout>;
}

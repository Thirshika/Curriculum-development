import { FormEvent, useCallback, useEffect, useState } from "react";
import { Building, Check, Plus, Search, X } from "lucide-react";
import axios from "axios";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { College, University } from "../types";

type CollegeForm = {
  university_id: string;
  name: string;
  code: string;
  address: string;
  state: string;
  district: string;
  contact_person: string;
  contact_email: string;
  phone_number: string;
  website: string;
};
const emptyForm = (): CollegeForm => ({
  university_id: "", name: "", code: "", address: "", state: "", district: "",
  contact_person: "", contact_email: "", phone_number: "", website: "",
});
const errorMessage = (reason: unknown) => axios.isAxiosError(reason)
  ? reason.response?.data?.detail ?? "The request could not be completed."
  : "The request could not be completed.";

export default function CollegesPage() {
  const [colleges, setColleges] = useState<College[]>([]);
  const [universities, setUniversities] = useState<University[]>([]);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [form, setForm] = useState<CollegeForm>(emptyForm);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<College | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get<College[]>("/colleges", { params: { search: search || undefined, limit: 100 } });
      setColleges(data);
    } catch (reason) { setError(errorMessage(reason)); }
  }, [search]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    api.get<University[]>("/universities", { params: { limit: 100 } })
      .then(({ data }) => setUniversities(data))
      .catch((reason: unknown) => setError(errorMessage(reason)));
  }, []);

  function startCreate() {
    setEditing(null);
    setForm({ ...emptyForm(), university_id: universities.find((item) => item.status === "active")?.id ?? "" });
    setFormOpen(true);
    setError("");
  }

  function startEdit(college: College) {
    setEditing(college);
    setForm({
      university_id: college.university_id, name: college.name, code: college.code,
      address: college.address ?? "", state: college.state ?? "", district: college.district ?? "",
      contact_person: college.contact_person ?? "", contact_email: college.contact_email ?? "",
      phone_number: college.phone_number ?? "", website: college.website ?? "",
    });
    setFormOpen(true);
    setError("");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const body = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value.trim() || null]));
    try {
      if (editing) {
        const { university_id: _universityId, code: _code, ...updates } = body;
        await api.patch(`/colleges/${editing.id}`, updates);
      } else {
        await api.post("/colleges", body);
      }
      setNotice(editing ? "College updated." : "College created.");
      setFormOpen(false);
      setEditing(null);
      setForm(emptyForm());
      await load();
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  }

  async function toggleStatus(college: College) {
    const next = college.status === "active" ? "inactive" : "active";
    if (!window.confirm(`${next === "inactive" ? "Deactivate" : "Activate"} ${college.name}?`)) return;
    try {
      await api.patch(`/colleges/${college.id}`, { status: next });
      setNotice(`${college.name} ${next}.`);
      await load();
    } catch (reason) { setError(errorMessage(reason)); }
  }

  return <PortalLayout role="admin">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div><p className="text-sm font-medium text-navy">ADMIN WORKSPACE</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">College management</h1><p className="mt-2 text-sm text-slate-500">Organize colleges under universities and assign college-scoped reviewer accounts.</p></div>
      <button onClick={startCreate} disabled={!universities.some((item) => item.status === "active")} className="inline-flex items-center gap-2 rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><Plus size={16} />Add college</button>
    </div>
    {notice && <div role="status" className="mt-5 flex justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"><span className="flex items-center gap-2"><Check size={16} />{notice}</span><button onClick={() => setNotice("")}><X size={15} /></button></div>}
    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    <form className="mt-6 flex gap-2" onSubmit={(event) => { event.preventDefault(); setSearch(searchInput.trim()); }}>
      <div className="relative max-w-lg flex-1"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} /><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search college, code, university" className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm" /></div>
      <button className="rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700">Search</button>
    </form>
    {formOpen && <form onSubmit={(event) => void save(event)} className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
      <h2 className="text-base font-bold text-ink">{editing ? "Edit college" : "Create college"}</h2>
      {error && <div role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {!editing && <label className="text-xs font-semibold text-slate-600">University<select required value={form.university_id} onChange={(event) => setForm({ ...form, university_id: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm">{universities.filter((item) => item.status === "active").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
        <label className="text-xs font-semibold text-slate-600">College name<input required minLength={2} maxLength={200} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">College code<input required disabled={Boolean(editing)} pattern="[A-Za-z0-9][A-Za-z0-9_-]*" maxLength={32} value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm disabled:bg-slate-100" /></label>
        <label className="text-xs font-semibold text-slate-600">Address<input value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">State<input value={form.state} onChange={(event) => setForm({ ...form, state: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">District<input value={form.district} onChange={(event) => setForm({ ...form, district: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">Contact person<input value={form.contact_person} onChange={(event) => setForm({ ...form, contact_person: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">Contact email<input type="email" value={form.contact_email} onChange={(event) => setForm({ ...form, contact_email: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">Phone<input value={form.phone_number} onChange={(event) => setForm({ ...form, phone_number: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">Website<input type="url" value={form.website} onChange={(event) => setForm({ ...form, website: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" /></label>
      </div>
      <div className="mt-5 flex justify-end gap-2"><button type="button" onClick={() => setFormOpen(false)} className="rounded-lg border px-4 py-2 text-sm">Cancel</button><button disabled={busy} className="rounded-lg bg-navy px-4 py-2 text-sm font-semibold text-white">{busy ? "Saving…" : "Save college"}</button></div>
    </form>}
    <div className="mt-6 overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-card">
      <table className="w-full min-w-[980px] text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{["College", "University", "Location", "Reviewer", "Programmes", "Curricula", "Status", "Actions"].map((item) => <th key={item} className="px-4 py-3 font-semibold">{item}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100">{colleges.map((college) => <tr key={college.id}>
          <td className="px-4 py-4"><div className="flex items-center gap-2 font-semibold text-slate-800"><Building size={15} />{college.name}</div><div className="mt-1 text-xs text-slate-400">{college.code}</div></td>
          <td className="px-4 py-4">{college.university_name}</td><td className="px-4 py-4 text-slate-500">{[college.district, college.state].filter(Boolean).join(", ") || "—"}</td>
          <td className="px-4 py-4">{college.reviewer_name ?? <span className="text-slate-400">Not assigned</span>}</td><td className="px-4 py-4">{college.programme_count}</td><td className="px-4 py-4">{college.assignment_count}</td>
          <td className="px-4 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${college.status === "active" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{college.status}</span></td>
          <td className="px-4 py-4"><div className="flex gap-2"><button onClick={() => startEdit(college)} className="rounded-lg border px-2.5 py-1.5 text-xs font-semibold">Edit</button><button onClick={() => void toggleStatus(college)} className="rounded-lg border px-2.5 py-1.5 text-xs font-semibold">{college.status === "active" ? "Deactivate" : "Activate"}</button></div></td>
        </tr>)}</tbody>
      </table>
      {colleges.length === 0 && <div className="px-6 py-12 text-center text-sm text-slate-500">No colleges yet. Create a college under an active university.</div>}
    </div>
  </PortalLayout>;
}

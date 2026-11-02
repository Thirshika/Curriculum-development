import { FormEvent, useCallback, useEffect, useState } from "react";
import { Building2, Check, ChevronLeft, ChevronRight, Edit3, Plus, Search, X } from "lucide-react";
import axios from "axios";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { University, UniversityFormData } from "../types";

const emptyForm: UniversityFormData = {
  name: "",
  code: "",
  address: "",
  contact_person: "",
  contact_email: "",
  phone_number: "",
  logo_url: "",
};

function getErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) return error.response?.data?.detail ?? "The request could not be completed.";
  return "The request could not be completed.";
}

export default function UniversitiesPage() {
  const [universities, setUniversities] = useState<University[]>([]);
  const [searchText, setSearchText] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [form, setForm] = useState<UniversityFormData>(emptyForm);
  const [editing, setEditing] = useState<University | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const pageSize = 25;

  const loadUniversities = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get<University[]>("/universities", {
        params: { search: search || undefined, offset, limit: pageSize },
      });
      setUniversities(data);
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [offset, search]);

  useEffect(() => { void loadUniversities(); }, [loadUniversities]);

  function startCreate() {
    setEditing(null);
    setForm(emptyForm);
    setError("");
    setFormOpen(true);
  }

  function startEdit(university: University) {
    setEditing(university);
    setForm({
      name: university.name,
      code: university.code,
      address: university.address ?? "",
      contact_person: university.contact_person ?? "",
      contact_email: university.contact_email ?? "",
      phone_number: university.phone_number ?? "",
      logo_url: university.logo_url ?? "",
    });
    setError("");
    setFormOpen(true);
  }

  async function submitForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const body = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value.trim() || null]));
    try {
      if (editing) {
        await api.patch(`/universities/${editing.id}`, {
          name: body.name,
          address: body.address,
          contact_person: body.contact_person,
          contact_email: body.contact_email,
          phone_number: body.phone_number,
          logo_url: body.logo_url,
        });
        setNotice("University details updated.");
      } else {
        await api.post("/universities", body);
        setNotice("University created.");
        setOffset(0);
        setSearch("");
        setSearchText("");
      }
      setFormOpen(false);
      setForm(emptyForm);
      setEditing(null);
      await loadUniversities();
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setSaving(false);
    }
  }

  async function toggleStatus(university: University) {
    const nextStatus = university.status === "active" ? "inactive" : "active";
    const confirmText = nextStatus === "inactive"
      ? `Deactivate ${university.name}? Its reviewer will also be deactivated.`
      : `Reactivate ${university.name}? Its reviewer must be activated separately.`;
    if (!window.confirm(confirmText)) return;
    setError("");
    setNotice("");
    try {
      await api.patch(`/universities/${university.id}/status`, { status: nextStatus });
      setNotice(`${university.name} ${nextStatus === "active" ? "activated" : "deactivated"}.`);
      await loadUniversities();
    } catch (reason) {
      setError(getErrorMessage(reason));
    }
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOffset(0);
    setSearch(searchText.trim());
  }

  return <PortalLayout role="admin">
    <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
      <div><p className="text-sm font-medium text-navy">ADMIN WORKSPACE</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">University management</h1><p className="mt-2 text-sm text-slate-500">Register universities and manage their profile and access status.</p></div>
      <button onClick={startCreate} className="inline-flex items-center justify-center gap-2 rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#102f5e]"><Plus size={17} />Add university</button>
    </div>

    {notice && <div role="status" className="mt-6 flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"><span className="flex items-center gap-2"><Check size={16} />{notice}</span><button aria-label="Dismiss" onClick={() => setNotice("")}><X size={15} /></button></div>}
    {error && !formOpen && <div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

    {formOpen && <section className="mt-7 rounded-2xl border border-blue-100 bg-white p-5 shadow-card sm:p-6">
      <div className="flex items-start justify-between"><div><h2 className="text-base font-bold text-ink">{editing ? "Edit university" : "Add a university"}</h2><p className="mt-1 text-sm text-slate-500">{editing ? `Update the details for ${editing.name}.` : "University codes are unique and cannot be changed after creation."}</p></div><button onClick={() => setFormOpen(false)} aria-label="Close form" className="rounded-lg p-2 text-slate-400 hover:bg-slate-50"><X size={18} /></button></div>
      <form className="mt-5 grid gap-4 sm:grid-cols-2" onSubmit={submitForm}>
        <label className="text-sm font-medium text-slate-700">University name<input className="form-input mt-2" required minLength={2} maxLength={200} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
        <label className="text-sm font-medium text-slate-700">University code<input className="form-input mt-2 uppercase" required minLength={2} maxLength={32} pattern="[A-Za-z0-9][A-Za-z0-9_-]*" disabled={Boolean(editing)} value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })} placeholder="ABC001" /><span className="mt-1 block text-xs font-normal text-slate-400">Letters, numbers, underscores, and hyphens.</span></label>
        <label className="text-sm font-medium text-slate-700 sm:col-span-2">Address<textarea className="form-input mt-2 min-h-20 resize-y" maxLength={4000} value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} /></label>
        <label className="text-sm font-medium text-slate-700">Contact person<input className="form-input mt-2" maxLength={160} value={form.contact_person} onChange={(event) => setForm({ ...form, contact_person: event.target.value })} /></label>
        <label className="text-sm font-medium text-slate-700">Contact email<input className="form-input mt-2" type="email" value={form.contact_email} onChange={(event) => setForm({ ...form, contact_email: event.target.value })} /></label>
        <label className="text-sm font-medium text-slate-700">Phone number<input className="form-input mt-2" type="tel" maxLength={32} value={form.phone_number} onChange={(event) => setForm({ ...form, phone_number: event.target.value })} /></label>
        <label className="text-sm font-medium text-slate-700">Logo URL<input className="form-input mt-2" type="url" maxLength={2048} value={form.logo_url} onChange={(event) => setForm({ ...form, logo_url: event.target.value })} placeholder="https://" /></label>
        {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700 sm:col-span-2">{error}</p>}
        <div className="flex justify-end gap-3 sm:col-span-2"><button type="button" onClick={() => setFormOpen(false)} className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50">Cancel</button><button disabled={saving} className="rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{saving ? "Saving…" : editing ? "Save changes" : "Create university"}</button></div>
      </form>
    </section>}

    <section className="mt-7 overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-card">
      <div className="flex flex-col justify-between gap-4 border-b border-slate-100 px-5 py-5 sm:flex-row sm:items-center sm:px-6"><div><h2 className="text-base font-bold text-ink">Universities</h2><p className="mt-1 text-sm text-slate-500">Profiles and assigned reviewer accounts.</p></div><form onSubmit={submitSearch} className="flex gap-2"><div className="relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} /><input className="form-input h-10 w-full pl-9 sm:w-64" value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Search name or code" /></div><button className="rounded-xl border border-slate-200 px-3 text-sm font-semibold text-slate-600 hover:bg-slate-50">Search</button></form></div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[840px] text-left text-sm">
          <thead className="bg-slate-50/80 text-[11px] font-semibold uppercase tracking-wide text-slate-500"><tr><th className="px-6 py-3">University</th><th className="px-6 py-3">Contact</th><th className="px-6 py-3">Reviewer</th><th className="px-6 py-3">Status</th><th className="px-6 py-3 text-right">Actions</th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {loading && <tr><td colSpan={5} className="px-6 py-12 text-center text-sm text-slate-500">Loading universities…</td></tr>}
            {!loading && universities.length === 0 && <tr><td colSpan={5} className="px-6 py-14 text-center"><div className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-slate-50 text-slate-400"><Building2 size={20} /></div><p className="mt-3 text-sm font-semibold text-slate-700">No universities found</p><p className="mt-1 text-xs text-slate-500">{search ? "Try another search, or add a new university." : "Create the first university to get started."}</p></td></tr>}
            {!loading && universities.map((university) => <tr key={university.id} className="hover:bg-slate-50/60">
              <td className="px-6 py-4"><div className="flex items-center gap-3"><div className="grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-xl bg-blue-50 text-navy">{university.logo_url ? <img src={university.logo_url} alt="" className="h-full w-full object-cover" /> : <Building2 size={18} />}</div><div><p className="font-semibold text-slate-800">{university.name}</p><p className="mt-1 text-xs font-medium text-slate-500">{university.code}</p></div></div></td>
              <td className="px-6 py-4"><p className="text-slate-700">{university.contact_person ?? "—"}</p><p className="mt-1 text-xs text-slate-500">{university.contact_email ?? university.phone_number ?? "No contact details"}</p></td>
              <td className="px-6 py-4">{university.reviewer_id ? <><p className="font-medium text-slate-700">{university.reviewer_name}</p><p className="mt-1 text-xs text-slate-500">{university.reviewer_email}</p></> : <span className="text-xs text-slate-400">Not assigned</span>}</td>
              <td className="px-6 py-4"><span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${university.status === "active" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{university.status}</span></td>
              <td className="px-6 py-4"><div className="flex justify-end gap-2"><button onClick={() => startEdit(university)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"><Edit3 size={14} />Edit</button><button onClick={() => void toggleStatus(university)} className={`rounded-lg px-2.5 py-2 text-xs font-semibold ${university.status === "active" ? "border border-rose-100 text-rose-600 hover:bg-rose-50" : "border border-emerald-100 text-emerald-700 hover:bg-emerald-50"}`}>{university.status === "active" ? "Deactivate" : "Activate"}</button></div></td>
            </tr>)}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3 sm:px-6"><p className="text-xs text-slate-500">Showing {universities.length ? offset + 1 : 0}–{offset + universities.length}</p><div className="flex gap-2"><button disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - pageSize))} aria-label="Previous page" className="rounded-lg border border-slate-200 p-2 text-slate-600 disabled:opacity-40"><ChevronLeft size={16} /></button><button disabled={universities.length < pageSize || loading} onClick={() => setOffset(offset + pageSize)} aria-label="Next page" className="rounded-lg border border-slate-200 p-2 text-slate-600 disabled:opacity-40"><ChevronRight size={16} /></button></div></div>
    </section>
  </PortalLayout>;
}

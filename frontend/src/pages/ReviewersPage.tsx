import { FormEvent, useCallback, useEffect, useState } from "react";
import { Check, Edit3, KeyRound, Search, ShieldCheck, UserPlus, UsersRound, X } from "lucide-react";
import axios from "axios";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { College, Reviewer, University } from "../types";

function getErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) return error.response?.data?.detail ?? "The request could not be completed.";
  return "The request could not be completed.";
}

export default function ReviewersPage() {
  const [reviewers, setReviewers] = useState<Reviewer[]>([]);
  const [universities, setUniversities] = useState<University[]>([]);
  const [colleges, setColleges] = useState<College[]>([]);
  const [searchText, setSearchText] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [universityId, setUniversityId] = useState("");
  const [collegeId, setCollegeId] = useState("");
  const [editingReviewer, setEditingReviewer] = useState<Reviewer | null>(null);
  const [resettingReviewer, setResettingReviewer] = useState<Reviewer | null>(null);
  const [resetPasswordValue, setResetPasswordValue] = useState("");
  const [confirmResetPassword, setConfirmResetPassword] = useState("");
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");

  const loadReviewers = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get<Reviewer[]>("/reviewers", { params: { search: search || undefined, limit: 100 } });
      setReviewers(data);
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [search]);

  const loadUniversities = useCallback(async () => {
    try {
      const { data } = await api.get<University[]>("/universities", { params: { limit: 100 } });
      setUniversities(data);
      setUniversityId((current) => data.some((item) => item.id === current && item.status === "active")
        ? current
        : data.find((item) => item.status === "active")?.id ?? "");
    } catch (reason) {
      setError(getErrorMessage(reason));
    }
  }, []);

  useEffect(() => { void loadReviewers(); }, [loadReviewers]);
  useEffect(() => { void loadUniversities(); }, [loadUniversities]);
  useEffect(() => {
    const timeout = window.setTimeout(() => setSearch(searchText.trim()), 250);
    return () => window.clearTimeout(timeout);
  }, [searchText]);
  useEffect(() => {
    api.get<College[]>("/colleges", { params: { limit: 100, status: "active" } })
      .then(({ data }) => setColleges(data))
      .catch((reason: unknown) => setError(getErrorMessage(reason)));
  }, []);

  async function createReviewer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.post<Reviewer>("/reviewers", {
        university_id: universityId,
        college_id: collegeId || null,
        full_name: name.trim(),
        email: email.trim(),
        password,
      });
      setNotice("Reviewer account created with the password you set.");
      setFormOpen(false);
      setName("");
      setEmail("");
      setPassword("");
      setConfirmPassword("");
      setCollegeId("");
      await Promise.all([loadReviewers(), loadUniversities()]);
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setSaving(false);
    }
  }

  async function resetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!resettingReviewer) return;
    if (resetPasswordValue !== confirmResetPassword) {
      setError("Passwords do not match.");
      return;
    }
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await api.post<Reviewer>(`/reviewers/${resettingReviewer.id}/reset-password`, { password: resetPasswordValue });
      setNotice(`Password reset for ${resettingReviewer.full_name}. Their active sessions were revoked.`);
      setResettingReviewer(null);
      setResetPasswordValue("");
      setConfirmResetPassword("");
      await loadReviewers();
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setSaving(false);
    }
  }

  async function toggleReviewer(reviewer: Reviewer) {
    const nextActive = !reviewer.is_active;
    if (!window.confirm(`${nextActive ? "Activate" : "Deactivate"} ${reviewer.full_name}?`)) return;
    setError("");
    setNotice("");
    try {
      await api.patch(`/reviewers/${reviewer.id}`, { is_active: nextActive });
      setNotice(`Reviewer ${nextActive ? "activated" : "deactivated"}.`);
      await loadReviewers();
    } catch (reason) {
      setError(getErrorMessage(reason));
    }
  }

  function startEdit(reviewer: Reviewer) {
    setFormOpen(false);
    setResettingReviewer(null);
    setEditingReviewer(reviewer);
    setEditName(reviewer.full_name);
    setEditEmail(reviewer.email);
    setError("");
  }

  async function saveReviewer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingReviewer) return;
    setSaving(true);
    setError("");
    try {
      await api.patch(`/reviewers/${editingReviewer.id}`, {
        full_name: editName.trim(),
        email: editEmail.trim(),
      });
      setNotice("Reviewer details updated.");
      setEditingReviewer(null);
      await loadReviewers();
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setSaving(false);
    }
  }

  function clearSearch() {
    setSearchText("");
    setSearch("");
  }

  const availableUniversities = universities.filter((item) => item.status === "active");
  const availableColleges = colleges.filter((item) => item.university_id === universityId && !item.reviewer_id);

  return <PortalLayout role="admin">
    <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
      <div><p className="text-sm font-medium text-navy">ADMIN WORKSPACE</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Reviewer management</h1><p className="mt-2 text-sm text-slate-500">Provision a university-wide reviewer or a reviewer scoped to one active college.</p></div>
      <button onClick={() => { setError(""); setFormOpen(!formOpen); setEditingReviewer(null); setResettingReviewer(null); }} disabled={!availableUniversities.length} className="inline-flex items-center justify-center gap-2 rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#102f5e] disabled:cursor-not-allowed disabled:opacity-50"><UserPlus size={17} />Create reviewer</button>
    </div>

    {notice && <div role="status" className="mt-6 flex items-start justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"><span className="flex items-start gap-2"><Check className="mt-0.5 shrink-0" size={16} />{notice}</span><button aria-label="Dismiss" onClick={() => setNotice("")}><X size={15} /></button></div>}
    {error && !formOpen && !resettingReviewer && <div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

    {editingReviewer && <section className="mt-6 rounded-2xl border border-blue-100 bg-white p-5 shadow-card sm:p-6">
      <div className="flex items-start justify-between"><div><h2 className="text-base font-bold text-ink">Edit reviewer account</h2><p className="mt-1 text-sm text-slate-500">{editingReviewer.university_name} · Username: {editingReviewer.username}</p></div><button onClick={() => setEditingReviewer(null)} aria-label="Close form" className="rounded-lg p-2 text-slate-400 hover:bg-slate-50"><X size={18} /></button></div>
      <form onSubmit={saveReviewer} className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium text-slate-700">Full name<input className="form-input mt-2" required minLength={2} maxLength={160} value={editName} onChange={(event) => setEditName(event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Email address<input className="form-input mt-2" type="email" required value={editEmail} onChange={(event) => setEditEmail(event.target.value)} /></label>
        {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700 sm:col-span-2">{error}</p>}
        <div className="flex justify-end gap-3 sm:col-span-2"><button type="button" onClick={() => setEditingReviewer(null)} className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50">Cancel</button><button disabled={saving} className="rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{saving ? "Saving…" : "Save changes"}</button></div>
      </form>
    </section>}

    {resettingReviewer && <section className="mt-6 rounded-2xl border border-blue-100 bg-white p-5 shadow-card sm:p-6">
      <div className="flex items-start justify-between"><div><h2 className="text-base font-bold text-ink">Reset reviewer password</h2><p className="mt-1 text-sm text-slate-500">Set a new password for {resettingReviewer.full_name}. Their active sessions will be revoked.</p></div><button type="button" onClick={() => { setResettingReviewer(null); setResetPasswordValue(""); setConfirmResetPassword(""); setError(""); }} aria-label="Close reset form" className="rounded-lg p-2 text-slate-400 hover:bg-slate-50"><X size={18} /></button></div>
      <form onSubmit={resetPassword} className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium text-slate-700">New password<input className="form-input mt-2" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={resetPasswordValue} onChange={(event) => setResetPasswordValue(event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Confirm new password<input className="form-input mt-2" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirmResetPassword} onChange={(event) => setConfirmResetPassword(event.target.value)} /></label>
        {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700 sm:col-span-2">{error}</p>}
        <div className="flex justify-end gap-3 sm:col-span-2"><button type="button" onClick={() => { setResettingReviewer(null); setResetPasswordValue(""); setConfirmResetPassword(""); setError(""); }} className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50">Cancel</button><button disabled={saving} className="rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{saving ? "Resetting…" : "Reset password"}</button></div>
      </form>
    </section>}

    {formOpen && <section className="mt-7 rounded-2xl border border-blue-100 bg-white p-5 shadow-card sm:p-6">
      <div className="flex items-start justify-between"><div><h2 className="text-base font-bold text-ink">Create reviewer account</h2><p className="mt-1 text-sm text-slate-500">Set a password with at least 12 characters for this account.</p></div><button onClick={() => setFormOpen(false)} aria-label="Close form" className="rounded-lg p-2 text-slate-400 hover:bg-slate-50"><X size={18} /></button></div>
      <form onSubmit={createReviewer} className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium text-slate-700">Full name<input className="form-input mt-2" required minLength={2} maxLength={160} value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Email address<input className="form-input mt-2" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Password<input className="form-input mt-2" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Confirm password<input className="form-input mt-2" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Assigned university<select className="form-input mt-2" required value={universityId} onChange={(event) => { setUniversityId(event.target.value); setCollegeId(""); }}><option value="" disabled>Select an active university</option>{availableUniversities.map((university) => <option key={university.id} value={university.id}>{university.name} ({university.code})</option>)}</select></label>
        <label className="text-sm font-medium text-slate-700">College scope (optional)<select className="form-input mt-2" value={collegeId} onChange={(event) => setCollegeId(event.target.value)}><option value="">University-wide reviewer</option>{availableColleges.map((college) => <option key={college.id} value={college.id}>{college.name} ({college.code})</option>)}</select></label>
        {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700 sm:col-span-2">{error}</p>}
        <div className="flex justify-end gap-3 sm:col-span-2"><button type="button" onClick={() => setFormOpen(false)} className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50">Cancel</button><button disabled={saving || !universityId} className="rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{saving ? "Creating…" : "Create account"}</button></div>
      </form>
    </section>}

    <div className="mt-7 grid gap-4 sm:grid-cols-2">
      <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card"><div className="flex items-center justify-between"><div><p className="text-sm font-medium text-slate-500">Reviewer accounts</p><p className="mt-2 text-3xl font-bold text-ink">{reviewers.length}</p></div><div className="grid h-11 w-11 place-items-center rounded-xl bg-teal-50 text-teal-700"><UsersRound size={20} /></div></div><p className="mt-3 text-xs text-slate-500">One assigned account per university.</p></div>
      <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card"><div className="flex items-center justify-between"><div><p className="text-sm font-medium text-slate-500">Active colleges without reviewers</p><p className="mt-2 text-3xl font-bold text-ink">{colleges.filter((item) => item.status === "active" && !item.reviewer_id).length}</p></div><div className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-navy"><ShieldCheck size={20} /></div></div><p className="mt-3 text-xs text-slate-500">College-scoped reviewer slots available.</p></div>
    </div>

    <section className="mt-7 overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-card">
      <div className="flex flex-col justify-between gap-4 border-b border-slate-100 px-5 py-5 sm:flex-row sm:items-center sm:px-6"><div><h2 className="text-base font-bold text-ink">Reviewer accounts</h2><p className="mt-1 text-sm text-slate-500">Account status, university assignment, and password access.</p></div><div className="relative w-full sm:w-72"><Search aria-hidden="true" className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} /><input aria-label="Search reviewer accounts" className="form-input search-input search-input-clear h-10 w-full" value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Reviewer, university, or college" />{searchText && <button type="button" aria-label="Clear search" onClick={clearSearch} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><X size={15} /></button>}</div></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm">
        <thead className="bg-slate-50/80 text-[11px] font-semibold uppercase tracking-wide text-slate-500"><tr><th className="px-6 py-3">Reviewer</th><th className="px-6 py-3">University / College</th><th className="px-6 py-3">Account status</th><th className="px-6 py-3">Password status</th><th className="px-6 py-3 text-right">Actions</th></tr></thead>
        <tbody className="divide-y divide-slate-100">
          {loading && <tr><td colSpan={5} className="px-6 py-12 text-center text-sm text-slate-500">Loading reviewer accounts…</td></tr>}
          {!loading && reviewers.length === 0 && <tr><td colSpan={5} className="px-6 py-14 text-center"><div className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-slate-50 text-slate-400"><UsersRound size={20} /></div><p className="mt-3 text-sm font-semibold text-slate-700">No reviewer accounts found</p><p className="mt-1 text-xs text-slate-500">{search ? "Try a different search or clear the filter." : "Add a university first, then provision its reviewer account."}</p></td></tr>}
          {!loading && reviewers.map((reviewer) => <tr key={reviewer.id} className="hover:bg-slate-50/60">
            <td className="px-6 py-4"><p className="font-semibold text-slate-800">{reviewer.full_name}</p><p className="mt-1 text-xs text-slate-500">{reviewer.email}</p><p className="mt-1 text-[11px] font-medium text-navy">Login username: {reviewer.username}</p></td>
            <td className="px-6 py-4"><p className="font-medium text-slate-700">{reviewer.university_name}</p><p className="mt-1 text-xs text-slate-500">{reviewer.college_name ? `College: ${reviewer.college_name}` : `University-wide · ${reviewer.university_code}`}</p></td>
            <td className="px-6 py-4"><span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${reviewer.is_active ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800"}`}>{reviewer.is_active ? "Active" : "Inactive · approval needed"}</span></td>
            <td className="px-6 py-4"><span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${reviewer.must_change_password ? "bg-amber-50 text-amber-800" : "bg-blue-50 text-blue-700"}`}>{reviewer.must_change_password ? "Password change required" : "Password set"}</span></td>
            <td className="px-6 py-4"><div className="flex justify-end gap-2"><button onClick={() => startEdit(reviewer)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"><Edit3 size={14} />Edit</button><button onClick={() => { setFormOpen(false); setEditingReviewer(null); setResettingReviewer(reviewer); setResetPasswordValue(""); setConfirmResetPassword(""); setError(""); setNotice(""); }} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"><KeyRound size={14} />Reset password</button><button onClick={() => void toggleReviewer(reviewer)} className={`rounded-lg px-2.5 py-2 text-xs font-semibold ${reviewer.is_active ? "border border-rose-100 text-rose-600 hover:bg-rose-50" : "border border-emerald-100 text-emerald-700 hover:bg-emerald-50"}`}>{reviewer.is_active ? "Deactivate" : "Activate"}</button></div></td>
          </tr>)}
        </tbody>
      </table></div>
      <div className="border-t border-slate-100 px-5 py-3 text-xs text-slate-500 sm:px-6">Showing {reviewers.length} reviewer account{reviewers.length === 1 ? "" : "s"}{reviewers.length === 100 ? " (first 100)" : ""}</div>
    </section>
  </PortalLayout>;
}

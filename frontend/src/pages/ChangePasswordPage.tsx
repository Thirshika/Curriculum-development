import { FormEvent, useState } from "react";
import { KeyRound } from "lucide-react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import api from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { User } from "../types";

export default function ChangePasswordPage() {
  const { user, updateUser, signOut } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (newPassword.length < 12) return setError("Choose a password with at least 12 characters.");
    if (newPassword !== confirmPassword) return setError("The new passwords do not match.");
    setSubmitting(true);
    try {
      const { data } = await api.post<User>("/auth/change-password", { current_password: currentPassword, new_password: newPassword });
      updateUser(data);
      navigate(data.role === "admin" ? "/admin" : "/reviewer", { replace: true });
    } catch (reason) {
      setError(axios.isAxiosError(reason) ? reason.response?.data?.detail ?? "Password update failed." : "Password update failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSignOut() {
    await signOut();
    navigate("/login", { replace: true });
  }

  return <main className="grid min-h-screen place-items-center bg-canvas px-5 py-12">
    <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-card sm:p-9">
      <div className="grid h-12 w-12 place-items-center rounded-xl bg-blue-50 text-navy"><KeyRound size={21} /></div>
      <h1 className="mt-6 text-2xl font-bold tracking-tight text-ink">Set a new password</h1>
      <p className="mt-2 text-sm leading-6 text-slate-500">For your account security, change the temporary password before continuing.</p>
      <form className="mt-7 space-y-4" onSubmit={handleSubmit}>
        <label className="block text-sm font-medium text-slate-700">Current password<input className="form-input mt-2" type="password" autoComplete="current-password" required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label>
        <label className="block text-sm font-medium text-slate-700">New password<input className="form-input mt-2" type="password" autoComplete="new-password" minLength={12} required value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /><span className="mt-1.5 block text-xs font-normal text-slate-500">Use at least 12 characters.</span></label>
        <label className="block text-sm font-medium text-slate-700">Confirm new password<input className="form-input mt-2" type="password" autoComplete="new-password" minLength={12} required value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></label>
        {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700">{error}</p>}
        <button disabled={submitting} className="w-full rounded-xl bg-navy px-4 py-3 text-sm font-semibold text-white hover:bg-[#102f5e] disabled:opacity-60">{submitting ? "Updating password…" : "Update password"}</button>
      </form>
      <button onClick={handleSignOut} className="mt-4 w-full py-2 text-sm font-medium text-slate-500 hover:text-slate-800">Sign out</button>
      <p className="mt-3 text-center text-xs text-slate-400">{user?.email}</p>
    </section>
  </main>;
}

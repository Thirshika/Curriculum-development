import { FormEvent, useState } from "react";
import { ArrowRight, BookOpenCheck, Eye, EyeOff, GraduationCap, ShieldCheck } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import axios from "axios";

export default function LoginPage({ role }: { role: "admin" | "reviewer" }) {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const user = await signIn(identifier, password, role);
      navigate(user.must_change_password ? "/change-password" : role === "admin" ? "/admin" : "/reviewer", { replace: true });
    } catch (reason) {
      if (axios.isAxiosError(reason)) setError(reason.response?.status === 401 ? "The email or password you entered is incorrect." : "We couldn't connect to the platform. Please try again.");
      else setError("Sign in failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return <main className="grid min-h-screen bg-white lg:grid-cols-[1.05fr_0.95fr]">
    <section className="relative hidden overflow-hidden bg-[#102c55] px-14 py-12 text-white lg:flex lg:flex-col lg:justify-between xl:px-20">
      <div className="absolute -right-36 -top-32 h-[490px] w-[490px] rounded-full border border-white/10" />
      <div className="absolute -right-16 -top-12 h-[330px] w-[330px] rounded-full border border-white/10" />
      <div className="absolute -bottom-48 -left-32 h-[480px] w-[480px] rounded-full bg-blue-400/10 blur-2xl" />
      <div className="relative flex items-center gap-3"><div className="grid h-11 w-11 place-items-center rounded-xl bg-white/10"><BookOpenCheck size={23} /></div><div><p className="font-semibold">Curriculum Hub</p><p className="text-xs text-blue-200">Academic review platform</p></div></div>
      <div className="relative max-w-[540px] py-14">
        <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium text-blue-100"><ShieldCheck size={14} />Secure academic workspace</span>
        <h1 className="mt-7 text-[42px] font-semibold leading-[1.16] tracking-tight xl:text-[50px]">Better curriculum, built through collaboration.</h1>
        <p className="mt-6 max-w-[440px] text-[15px] leading-7 text-blue-100/80">A trusted workspace for university teams to shape, review, and strengthen academic programmes together.</p>
        <div className="mt-10 flex items-center gap-4 rounded-2xl border border-white/10 bg-white/[0.06] p-4">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-white/10"><GraduationCap size={21} /></div>
          <div><p className="text-sm font-medium">Designed for academic teams</p><p className="mt-1 text-xs text-blue-100/70">One platform. Clear roles. Secure access.</p></div>
        </div>
      </div>
      <p className="relative text-xs text-blue-100/60">© {new Date().getFullYear()} Curriculum Hub · Secure access for authorized users</p>
    </section>
    <section className="flex min-h-screen items-center justify-center px-6 py-12 sm:px-12">
      <div className="w-full max-w-[420px]">
        <div className="mb-10 flex items-center gap-3 lg:hidden"><div className="grid h-10 w-10 place-items-center rounded-xl bg-navy text-white"><BookOpenCheck size={21} /></div><span className="font-bold text-ink">Curriculum Hub</span></div>
        <p className="text-sm font-semibold text-navy">{role === "admin" ? "ADMINISTRATOR ACCESS" : "REVIEWER ACCESS"}</p>
        <h2 className="mt-3 text-[32px] font-bold tracking-tight text-ink">{role === "admin" ? "Admin sign in" : "Reviewer sign in"}</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">{role === "admin" ? "Sign in to manage universities, reviewers, and curricula." : "Sign in to review curricula assigned to your institution."}</p>
        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          <label className="block"><span className="mb-2 block text-sm font-medium text-slate-700">{role === "admin" ? "Admin email address" : "Email address or unique Reviewer ID"}</span><input className="form-input" type={role === "admin" ? "email" : "text"} autoComplete="username" required value={identifier} onChange={(event) => setIdentifier(event.target.value)} placeholder={role === "admin" ? "admin@example.com" : "you@university.edu or ABC001-COLLEGE"} /></label>
          <label className="block"><span className="mb-2 block text-sm font-medium text-slate-700">Password</span><span className="relative block"><input className="form-input pr-12" type={showPassword ? "text" : "password"} autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" /><button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute inset-y-0 right-0 grid w-12 place-items-center text-slate-400 hover:text-slate-600" aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></span></label>
          {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700">{error}</p>}
          <button type="submit" disabled={submitting} className="flex w-full items-center justify-center gap-2 rounded-xl bg-navy px-4 py-3.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#102f5e] disabled:cursor-not-allowed disabled:opacity-60">{submitting ? "Signing in…" : "Sign in"}{!submitting && <ArrowRight size={17} />}</button>
        </form>
        <div className="mt-8 flex items-center gap-2 border-t border-slate-100 pt-5 text-xs leading-5 text-slate-500"><ShieldCheck size={16} className="shrink-0 text-emerald-600" />Your account is protected with secure, role-based access.</div>
        {role === "reviewer" ? <p className="mt-5 text-center text-sm text-slate-600">Need a reviewer account? <Link to="/reviewer/signup" className="font-semibold text-navy hover:underline">Sign up</Link></p> : null}
        <p className="mt-4 text-center text-xs text-slate-500">{role === "admin" ? "Are you a reviewer?" : "Are you an administrator?"} <Link to={role === "admin" ? "/login/reviewer" : "/login/admin"} className="font-semibold text-navy hover:underline">Use {role === "admin" ? "reviewer" : "admin"} sign in</Link></p>
      </div>
    </section>
  </main>;
}

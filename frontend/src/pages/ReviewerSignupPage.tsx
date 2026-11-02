import { FormEvent, useEffect, useState } from "react";
import { ArrowLeft, BookOpenCheck, Eye, EyeOff } from "lucide-react";
import { Link } from "react-router-dom";
import axios from "axios";
import api from "../api/client";

interface SignupCollegeOption {
  id: string;
  name: string;
  code: string;
}

interface SignupUniversityOption {
  id: string;
  name: string;
  code: string;
  university_wide_available: boolean;
  colleges: SignupCollegeOption[];
}

interface SignupOptions {
  universities: SignupUniversityOption[];
}

function getErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) return error.response?.data?.detail ?? "Signup could not be completed. Please try again.";
  return "Signup could not be completed. Please try again.";
}

export default function ReviewerSignupPage() {
  const [universities, setUniversities] = useState<SignupUniversityOption[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [optionError, setOptionError] = useState("");
  const [signupType, setSignupType] = useState<"existing" | "new">("existing");
  const [universityId, setUniversityId] = useState("");
  const [collegeId, setCollegeId] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [universityName, setUniversityName] = useState("");
  const [universityCode, setUniversityCode] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    api.get<SignupOptions>("/auth/signup-options")
      .then(({ data }) => {
        setUniversities(data.universities);
        setUniversityId(data.universities[0]?.id ?? "");
      })
      .catch((reason: unknown) => setOptionError(getErrorMessage(reason)))
      .finally(() => setLoadingOptions(false));
  }, []);

  const selectedUniversity = universities.find((university) => university.id === universityId);
  const availableColleges = selectedUniversity?.colleges ?? [];
  const canSignupExisting = universities.length > 0;
  const noExistingSlots = !loadingOptions && !optionError && !canSignupExisting;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const payload = {
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        ...(signupType === "existing"
          ? { university_id: universityId, college_id: collegeId || null }
          : { new_university_name: universityName.trim(), new_university_code: universityCode.trim() }),
      };
      await api.post("/auth/signup", payload);
      setSubmitted(true);
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setSubmitting(false);
    }
  }

  const selectedCollege = availableColleges.find((college) => college.id === collegeId);
  const selectedInstitutionDescription = selectedUniversity
    ? `Reviewer ID: ${collegeId && selectedCollege ? `${selectedUniversity.code}-${selectedCollege.code}` : selectedUniversity.code}`
    : "";

  return <main className="grid min-h-screen bg-white lg:grid-cols-[0.8fr_1.2fr]">
    <section className="hidden bg-[#102c55] px-12 py-14 text-white lg:flex lg:flex-col lg:justify-between">
      <div className="flex items-center gap-3"><div className="grid h-11 w-11 place-items-center rounded-xl bg-white/10"><BookOpenCheck size={23} /></div><div><p className="font-semibold">Curriculum Hub</p><p className="text-xs text-blue-200">Academic review platform</p></div></div>
      <div className="max-w-md"><p className="text-sm font-semibold text-blue-200">REVIEWER REGISTRATION</p><h1 className="mt-4 text-4xl font-semibold leading-tight">Join the academic review community.</h1><p className="mt-5 text-sm leading-7 text-blue-100/80">Register your reviewer account to collaborate with your university on curriculum review.</p></div>
      <p className="text-xs text-blue-100/60">Reviewer access is granted after administrator approval.</p>
    </section>
    <section className="flex min-h-screen items-center justify-center px-6 py-10 sm:px-12">
      <div className="w-full max-w-xl">
        <Link to="/login/reviewer" className="mb-8 inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-navy"><ArrowLeft size={16} />Back to reviewer sign in</Link>
        <div className="mb-6 flex items-center gap-3 lg:hidden"><div className="grid h-10 w-10 place-items-center rounded-xl bg-navy text-white"><BookOpenCheck size={21} /></div><span className="font-bold text-ink">Curriculum Hub</span></div>
        <p className="text-sm font-semibold text-navy">REVIEWER ACCOUNT</p>
        <h2 className="mt-2 text-3xl font-bold tracking-tight text-ink">Create your account</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">Your account will stay inactive until an administrator approves it.</p>

        {submitted ? <div role="status" className="mt-8 rounded-xl border border-emerald-200 bg-emerald-50 p-5 text-sm leading-6 text-emerald-900">
          <p className="font-semibold">Signup received</p>
          <p className="mt-1">An administrator must approve your reviewer account before you can sign in. For new institutions, the institution and reviewer account must both be approved.</p>
          <Link to="/login/reviewer" className="mt-4 inline-block font-semibold text-navy hover:underline">Go to reviewer sign in</Link>
        </div> : <form className="mt-7 space-y-4" onSubmit={handleSubmit}>
          <label className="block"><span className="mb-2 block text-sm font-medium text-slate-700">Full name</span><input className="form-input" required minLength={2} maxLength={160} autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} /></label>
          <label className="block"><span className="mb-2 block text-sm font-medium text-slate-700">Email address</span><input className="form-input" type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
          <label className="block"><span className="mb-2 block text-sm font-medium text-slate-700">Password <span className="font-normal text-slate-500">(at least 12 characters)</span></span><span className="relative block"><input className="form-input pr-12" type={showPassword ? "text" : "password"} required minLength={12} maxLength={128} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} /><button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute inset-y-0 right-0 grid w-12 place-items-center text-slate-400 hover:text-slate-600" aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></span></label>
          <fieldset className="space-y-3 rounded-xl border border-slate-200 p-4">
            <legend className="px-1 text-sm font-semibold text-slate-700">Institution</legend>
            <label className="flex items-start gap-3 text-sm text-slate-700"><input className="mt-1" type="radio" name="signupType" checked={signupType === "existing"} onChange={() => { setSignupType("existing"); setError(""); }} />Choose an existing university or college</label>
            <label className="flex items-start gap-3 text-sm text-slate-700"><input className="mt-1" type="radio" name="signupType" checked={signupType === "new"} onChange={() => { setSignupType("new"); setError(""); }} />Register a new university</label>
          </fieldset>
          {signupType === "existing" ? <>
            <label className="block"><span className="mb-2 block text-sm font-medium text-slate-700">University</span><select className="form-input" required disabled={loadingOptions || !canSignupExisting} value={universityId} onChange={(event) => { setUniversityId(event.target.value); setCollegeId(""); }}><option value="" disabled>{loadingOptions ? "Loading universities…" : "Select an available university"}</option>{universities.map((university) => <option key={university.id} value={university.id}>{university.name} ({university.code})</option>)}</select></label>
            {selectedUniversity && <label className="block"><span className="mb-2 block text-sm font-medium text-slate-700">Reviewer scope</span><select className="form-input" value={collegeId} onChange={(event) => setCollegeId(event.target.value)}><option value="" disabled={!selectedUniversity.university_wide_available}>{selectedUniversity.university_wide_available ? "University-wide reviewer" : "University-wide reviewer is already assigned"}</option>{availableColleges.map((college) => <option key={college.id} value={college.id}>{college.name} ({college.code})</option>)}</select></label>}
            {selectedInstitutionDescription && <p className="text-xs text-slate-500">{selectedInstitutionDescription}</p>}
            {noExistingSlots && <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-900">No available reviewer slots at existing universities. Choose new university if your institution is not listed.</p>}
            {optionError && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700">{optionError}</p>}
          </> : <>
            <label className="block"><span className="mb-2 block text-sm font-medium text-slate-700">University name</span><input className="form-input" required minLength={2} maxLength={200} value={universityName} onChange={(event) => setUniversityName(event.target.value)} /></label>
            <label className="block"><span className="mb-2 block text-sm font-medium text-slate-700">University code</span><input className="form-input" required minLength={2} maxLength={32} pattern="[A-Za-z0-9][A-Za-z0-9_-]*" value={universityCode} onChange={(event) => setUniversityCode(event.target.value)} /><span className="mt-1 block text-xs text-slate-500">Use letters, numbers, hyphens, or underscores. The code becomes your reviewer ID.</span></label>
          </>}
          {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700">{error}</p>}
          <button type="submit" disabled={submitting || (signupType === "existing" && (!canSignupExisting || !universityId || Boolean(selectedUniversity && !selectedUniversity.university_wide_available && !collegeId)))} className="flex w-full items-center justify-center gap-2 rounded-xl bg-navy px-4 py-3.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#102f5e] disabled:cursor-not-allowed disabled:opacity-60">{submitting ? "Submitting…" : "Request reviewer account"}</button>
        </form>}
        {!submitted && <p className="mt-6 text-center text-sm text-slate-600">Already registered? <Link to="/login/reviewer" className="font-semibold text-navy hover:underline">Sign in</Link></p>}
      </div>
    </section>
  </main>;
}

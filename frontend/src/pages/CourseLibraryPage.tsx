import { FormEvent, useCallback, useEffect, useState } from "react";
import { Pencil, Plus, Trash2, Upload, X } from "lucide-react";
import axios from "axios";
import { Link } from "react-router-dom";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { Course } from "../types";

type CourseForm = Omit<Course, "id" | "status">;
const emptyForm: CourseForm = {
  course_code: "", name: "", category: "", semester: 1,
  lecture_hours: "0", tutorial_hours: "0", practical_hours: "0", credits: "",
};
const errorMessage = (reason: unknown) => {
  if (!axios.isAxiosError(reason)) return "The request could not be completed.";
  const detail: unknown = reason.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => typeof item === "object" && item !== null && "msg" in item ? String(item.msg) : String(item)).join("; ");
  return "The request could not be completed.";
};

export default function CourseLibraryPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [form, setForm] = useState<CourseForm>(emptyForm);
  const [editingId, setEditingId] = useState("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [semester, setSemester] = useState("");
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvErrors, setCsvErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const courseResponse = await api.get<Course[]>("/courses", {
        params: {
          search: search || undefined,
          category: category || undefined,
          semester: semester || undefined,
          status: "active",
          limit: 500,
        },
      });
      setCourses(courseResponse.data);
      setError("");
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setLoading(false); }
  }, [category, search, semester]);

  useEffect(() => { void loadData(); }, [loadData]);
  useEffect(() => {
    const timer = window.setInterval(() => { void loadData(); }, 10000);
    return () => window.clearInterval(timer);
  }, [loadData]);

  function setField<K extends keyof CourseForm>(key: K, value: CourseForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submitCourse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const payload = {
        ...form,
        course_code: form.course_code.trim().toUpperCase(),
        name: form.name.trim(),
        category: form.category.trim(),
        lecture_hours: Number(form.lecture_hours),
        tutorial_hours: Number(form.tutorial_hours),
        practical_hours: Number(form.practical_hours),
        credits: Number(form.credits),
      };
      if (editingId) await api.patch(`/courses/${editingId}`, payload);
      else await api.post("/courses", payload);
      setNotice(editingId ? "Course updated." : "Course added to the library.");
      setEditingId("");
      setForm(emptyForm);
      await loadData();
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  }

  function editCourse(course: Course) {
    setEditingId(course.id);
    setForm({
      course_code: course.course_code,
      name: course.name,
      category: course.category,
      semester: course.semester,
      lecture_hours: course.lecture_hours,
      tutorial_hours: course.tutorial_hours,
      practical_hours: course.practical_hours,
      credits: course.credits,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function deleteCourse(course: Course) {
    if (!window.confirm(`Delete ${course.course_code} — ${course.name}?`)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.delete(`/courses/${course.id}`);
      setNotice(`${course.course_code} deleted.`);
      await loadData();
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  }

  async function importCsv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csvFile) return setError("Choose a CSV file to import.");
    setBusy(true);
    setError("");
    setNotice("");
    setCsvErrors([]);
    try {
      const body = new FormData();
      body.append("file", csvFile);
      const { data } = await api.post<{ imported: number; errors: string[] }>("/courses/import", body, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setNotice(`${data.imported} course(s) imported.`);
      setCsvErrors(data.errors);
      setCsvFile(null);
      await loadData();
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  }

  const inputClass = "form-input mt-1";
  return <PortalLayout role="admin">
    <div><p className="text-sm font-medium text-navy">STEP 3 · COURSE LIBRARY</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Course Library</h1><p className="mt-2 max-w-3xl text-sm text-slate-500">Courses with complete title, category, semester, L–T–P, and credit details are imported from uploaded regulation tables. You can also add courses manually or import a CSV. Shared credit limits are available in the <Link to="/admin/credit-table" className="font-semibold text-navy underline underline-offset-2">Credit Table</Link>.</p></div>
    {notice && <div role="status" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div>}
    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    {csvErrors.length > 0 && <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><p className="font-semibold">Some CSV rows were skipped:</p><ul className="mt-2 list-inside list-disc space-y-1">{csvErrors.map((message, index) => <li key={`${index}-${message}`}>{message}</li>)}</ul></div>}
    <div className="mt-6 grid min-w-0 items-start gap-5 2xl:grid-cols-[minmax(0,1fr)_minmax(320px,360px)]">
      <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
        <h2 className="flex items-center gap-2 font-bold text-ink">{editingId ? <Pencil size={17} /> : <Plus size={17} />}{editingId ? "Edit course" : "Add a course"}</h2>
        <form onSubmit={(event) => void submitCourse(event)} className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-xs font-semibold text-slate-600">Course code<input required minLength={2} maxLength={32} pattern="[A-Za-z0-9][A-Za-z0-9_-]*" value={form.course_code} onChange={(event) => setField("course_code", event.target.value)} className={inputClass} /></label>
          <label className="text-xs font-semibold text-slate-600 sm:col-span-2">Course title<input required minLength={2} maxLength={200} value={form.name} onChange={(event) => setField("name", event.target.value)} className={inputClass} /></label>
          <label className="text-xs font-semibold text-slate-600">Category<input required minLength={2} maxLength={100} value={form.category} onChange={(event) => setField("category", event.target.value)} className={inputClass} /></label>
          <label className="text-xs font-semibold text-slate-600">Semester<input required type="number" min="1" max="24" value={form.semester} onChange={(event) => setField("semester", Number(event.target.value))} className={inputClass} /></label>
          <label className="text-xs font-semibold text-slate-600">Lecture hours<input type="number" min="0" max="1000" step="0.01" value={form.lecture_hours} onChange={(event) => setField("lecture_hours", event.target.value)} className={inputClass} /></label>
          <label className="text-xs font-semibold text-slate-600">Tutorial hours<input type="number" min="0" max="1000" step="0.01" value={form.tutorial_hours} onChange={(event) => setField("tutorial_hours", event.target.value)} className={inputClass} /></label>
          <label className="text-xs font-semibold text-slate-600">Practical hours<input type="number" min="0" max="1000" step="0.01" value={form.practical_hours} onChange={(event) => setField("practical_hours", event.target.value)} className={inputClass} /></label>
          <label className="text-xs font-semibold text-slate-600">Credits<input required type="number" min="0.01" max="1000" step="0.01" value={form.credits} onChange={(event) => setField("credits", event.target.value)} className={inputClass} /></label>
          <div className="flex gap-2 sm:col-span-2 lg:col-span-4"><button disabled={busy} className="rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Saving…" : editingId ? "Save changes" : "Add course"}</button>{editingId && <button type="button" onClick={() => { setEditingId(""); setForm(emptyForm); }} className="inline-flex items-center gap-1 rounded-xl border px-4 py-2.5 text-sm font-semibold text-slate-600"><X size={15} />Cancel</button>}</div>
        </form>
      </section>
      <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
        <h2 className="flex items-center gap-2 font-bold text-ink"><Upload size={17} />Import courses from CSV</h2>

        <form onSubmit={(event) => void importCsv(event)} className="mt-4 space-y-3"><input required type="file" accept=".csv,text/csv" onChange={(event) => setCsvFile(event.target.files?.[0] ?? null)} className="form-input" /><button disabled={busy} className="w-full rounded-xl border border-navy px-4 py-2.5 text-sm font-semibold text-navy disabled:opacity-50">{busy ? "Importing…" : "Import CSV"}</button></form>
      </section>
    </div>
    <section className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4"><div><h2 className="font-bold text-ink">Course catalogue</h2><p className="mt-1 text-xs text-slate-500">{courses.length} active course(s) · includes courses imported from regulation PDFs.</p></div><form onSubmit={(event) => { event.preventDefault(); void loadData(); }} className="flex flex-wrap gap-2"><input aria-label="Search courses" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Code or title" className="rounded-lg border px-3 py-2 text-sm" /><input aria-label="Filter by category" value={category} onChange={(event) => setCategory(event.target.value)} placeholder="Category" className="w-32 rounded-lg border px-3 py-2 text-sm" /><input aria-label="Filter by semester" type="number" min="1" max="24" value={semester} onChange={(event) => setSemester(event.target.value)} placeholder="Semester" className="w-28 rounded-lg border px-3 py-2 text-sm" /><button className="rounded-lg bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-700">Filter</button></form></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[850px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Course</th><th className="px-4 py-3">Category</th><th className="px-4 py-3">Semester</th><th className="px-4 py-3">L–T–P</th><th className="px-4 py-3">Credits</th><th className="px-4 py-3">Actions</th></tr></thead><tbody className="divide-y divide-slate-100">{courses.map((course) => <tr key={course.id}><td className="px-5 py-3"><span className="font-semibold text-slate-800">{course.course_code}</span><span className="mt-0.5 block text-xs text-slate-500">{course.name}</span></td><td className="px-4 py-3">{course.category}</td><td className="px-4 py-3">{course.semester}</td><td className="px-4 py-3">{course.lecture_hours}–{course.tutorial_hours}–{course.practical_hours}</td><td className="px-4 py-3 font-semibold">{course.credits}</td><td className="px-4 py-3"><div className="flex gap-2"><button aria-label={`Edit ${course.course_code}`} onClick={() => editCourse(course)} className="rounded-lg border p-2 text-slate-600 hover:bg-slate-50"><Pencil size={14} /></button><button aria-label={`Delete ${course.course_code}`} disabled={busy} onClick={() => void deleteCourse(course)} className="rounded-lg border border-rose-100 p-2 text-rose-600 hover:bg-rose-50 disabled:opacity-50"><Trash2 size={14} /></button></div></td></tr>)}
        {!courses.length && <tr><td colSpan={6} className="px-5 py-12 text-center text-sm text-slate-500">{loading ? "Loading catalogue…" : "No active courses found."}</td></tr>}</tbody></table></div>
    </section>
  </PortalLayout>;
}

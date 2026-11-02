import { FormEvent, useCallback, useEffect, useState } from "react";
import { Archive, BookOpen, Check, Plus, Search, X } from "lucide-react";
import axios from "axios";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { Course, Programme } from "../types";

type CourseForm = {
  course_code: string; name: string; category: string; course_type: string; description: string;
  objectives: string; credits: string; lecture_hours: string; tutorial_hours: string; practical_hours: string;
  prerequisites: string; programme_ids: string[];
};
const emptyForm = (): CourseForm => ({
  course_code: "", name: "", category: "Major", course_type: "theory", description: "",
  objectives: "", credits: "3", lecture_hours: "3", tutorial_hours: "0", practical_hours: "0",
  prerequisites: "", programme_ids: [],
});
const errorMessage = (reason: unknown) => axios.isAxiosError(reason)
  ? reason.response?.data?.detail ?? "The request could not be completed."
  : "The request could not be completed.";

export default function CourseLibraryPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [form, setForm] = useState<CourseForm>(emptyForm);
  const [editing, setEditing] = useState<Course | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const loadCourses = useCallback(async () => {
    try {
      const { data } = await api.get<Course[]>("/courses", { params: { search: search || undefined, category: category || undefined, limit: 100 } });
      setCourses(data);
    } catch (reason) { setError(errorMessage(reason)); }
  }, [search, category]);

  useEffect(() => { void loadCourses(); }, [loadCourses]);
  useEffect(() => {
    api.get<Programme[]>("/programmes", { params: { status: "active", limit: 100 } })
      .then(({ data }) => setProgrammes(data))
      .catch((reason: unknown) => setError(errorMessage(reason)));
  }, []);

  function startEdit(course: Course) {
    setEditing(course);
    setForm({
      course_code: course.course_code, name: course.name, category: course.category, course_type: course.course_type,
      description: course.description, objectives: course.objectives.join("\n"), credits: String(course.credits),
      lecture_hours: String(course.lecture_hours), tutorial_hours: String(course.tutorial_hours),
      practical_hours: String(course.practical_hours), prerequisites: course.prerequisites.join(", "),
      programme_ids: course.programme_ids,
    });
    setFormOpen(true);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const body = {
      course_code: form.course_code.trim(), name: form.name.trim(), category: form.category.trim(),
      course_type: form.course_type.trim(), description: form.description.trim(),
      objectives: form.objectives.split("\n").map((item) => item.trim()).filter(Boolean),
      credits: Number(form.credits), lecture_hours: Number(form.lecture_hours),
      tutorial_hours: Number(form.tutorial_hours), practical_hours: Number(form.practical_hours),
      prerequisites: form.prerequisites.split(",").map((item) => item.trim()).filter(Boolean),
      programme_ids: form.programme_ids,
    };
    try {
      if (editing) await api.patch(`/courses/${editing.id}`, body);
      else await api.post("/courses", body);
      setNotice(editing ? "Course updated." : "Course added to the catalogue.");
      setFormOpen(false);
      setEditing(null);
      setForm(emptyForm());
      await loadCourses();
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  }

  async function toggleArchive(course: Course) {
    const status = course.status === "active" ? "archived" : "active";
    try {
      await api.patch(`/courses/${course.id}`, { status });
      setNotice(`${course.course_code} ${status}.`);
      await loadCourses();
    } catch (reason) { setError(errorMessage(reason)); }
  }

  return <PortalLayout role="admin">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div><p className="text-sm font-medium text-navy">ADMIN WORKSPACE</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Course library</h1><p className="mt-2 text-sm text-slate-500">Maintain reusable course definitions and map them to programmes.</p></div>
      <button onClick={() => { setEditing(null); setForm(emptyForm()); setFormOpen((value) => !value); }} className="inline-flex items-center gap-2 rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white"><Plus size={16} />Add course</button>
    </div>
    {notice && <div role="status" className="mt-5 flex justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"><span className="flex items-center gap-2"><Check size={16} />{notice}</span><button onClick={() => setNotice("")}><X size={15} /></button></div>}
    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    <div className="mt-6 flex flex-col gap-3 sm:flex-row">
      <form className="flex flex-1 gap-2" onSubmit={(event) => { event.preventDefault(); setSearch(searchText.trim()); }}>
        <div className="relative max-w-lg flex-1"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} /><input value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Search course code, name, description" className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm" /></div>
        <button className="rounded-xl border bg-white px-4 text-sm font-semibold">Search</button>
      </form>
      <select value={category} onChange={(event) => setCategory(event.target.value)} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"><option value="">All categories</option>{["Major", "Minor", "Multidisciplinary", "Ability Enhancement", "Skill Enhancement", "Value Added", "Internship", "Project", "Research"].map((item) => <option key={item}>{item}</option>)}</select>
    </div>
    {formOpen && <form onSubmit={(event) => void save(event)} className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
      <h2 className="text-base font-bold text-ink">{editing ? `Edit ${editing.course_code}` : "Add course to catalogue"}</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-xs font-semibold text-slate-600">Course code<input required disabled={Boolean(editing)} value={form.course_code} onChange={(event) => setForm({ ...form, course_code: event.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm disabled:bg-slate-100" /></label>
        <label className="text-xs font-semibold text-slate-600">Course name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">Category<select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5 text-sm">{["Major", "Minor", "Multidisciplinary", "Ability Enhancement", "Skill Enhancement", "Value Added", "Internship", "Project", "Research"].map((item) => <option key={item}>{item}</option>)}</select></label>
        <label className="text-xs font-semibold text-slate-600">Course type<select value={form.course_type} onChange={(event) => setForm({ ...form, course_type: event.target.value })} className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5 text-sm">{["theory", "practical", "theory_practical", "project", "internship"].map((item) => <option key={item}>{item}</option>)}</select></label>
        <label className="text-xs font-semibold text-slate-600">Credits<input type="number" min="0.01" step="0.01" required value={form.credits} onChange={(event) => setForm({ ...form, credits: event.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm" /></label>
        {(["lecture_hours", "tutorial_hours", "practical_hours"] as const).map((field) => <label key={field} className="text-xs font-semibold capitalize text-slate-600">{field.replace("_", " ")}<input type="number" min="0" step="0.5" value={form[field]} onChange={(event) => setForm({ ...form, [field]: event.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm" /></label>)}
        <label className="text-xs font-semibold text-slate-600 sm:col-span-2">Description<textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} rows={3} className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">Objectives (one per line)<textarea value={form.objectives} onChange={(event) => setForm({ ...form, objectives: event.target.value })} rows={3} className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">Prerequisite course codes<textarea value={form.prerequisites} onChange={(event) => setForm({ ...form, prerequisites: event.target.value })} placeholder="COURSE101, COURSE102" rows={2} className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm" /></label>
        <fieldset className="text-xs font-semibold text-slate-600 sm:col-span-2 lg:col-span-3"><legend>Map to programmes</legend><div className="mt-2 grid max-h-36 gap-2 overflow-auto sm:grid-cols-2">{programmes.map((programme) => <label key={programme.id} className="flex items-center gap-2 rounded-lg bg-slate-50 p-2 font-normal"><input type="checkbox" checked={form.programme_ids.includes(programme.id)} onChange={(event) => setForm({ ...form, programme_ids: event.target.checked ? [...form.programme_ids, programme.id] : form.programme_ids.filter((id) => id !== programme.id) })} />{programme.university_name} · {programme.name}</label>)}</div></fieldset>
      </div>
      <div className="mt-5 flex justify-end gap-2"><button type="button" onClick={() => setFormOpen(false)} className="rounded-lg border px-4 py-2 text-sm">Cancel</button><button disabled={busy} className="rounded-lg bg-navy px-4 py-2 text-sm font-semibold text-white">{busy ? "Saving…" : "Save course"}</button></div>
    </form>}
    <div className="mt-6 overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-card">
      <table className="w-full min-w-[960px] text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{["Course", "Category", "Type", "Credits", "Hours L/T/P", "Mapped programmes", "Status", "Actions"].map((item) => <th key={item} className="px-4 py-3 font-semibold">{item}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100">{courses.map((course) => <tr key={course.id}><td className="px-4 py-4"><div className="flex items-center gap-2 font-semibold text-slate-800"><BookOpen size={15} />{course.name}</div><div className="mt-1 text-xs text-slate-400">{course.course_code}</div></td><td className="px-4 py-4">{course.category}</td><td className="px-4 py-4">{course.course_type.replaceAll("_", " ")}</td><td className="px-4 py-4">{course.credits}</td><td className="px-4 py-4">{course.lecture_hours}/{course.tutorial_hours}/{course.practical_hours}</td><td className="px-4 py-4">{course.programme_ids.length}</td><td className="px-4 py-4">{course.status}</td><td className="px-4 py-4"><div className="flex gap-2"><button onClick={() => startEdit(course)} className="rounded-lg border px-2.5 py-1.5 text-xs font-semibold">Edit</button><button onClick={() => void toggleArchive(course)} className="rounded-lg border px-2.5 py-1.5 text-xs font-semibold"><Archive size={13} /></button></div></td></tr>)}</tbody>
      </table>
      {courses.length === 0 && <div className="px-6 py-12 text-center text-sm text-slate-500">No courses match. Add a reusable course to begin.</div>}
    </div>
  </PortalLayout>;
}

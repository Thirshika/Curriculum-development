import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, ClipboardCheck, FilePlus2, Plus, Save, Trash2 } from "lucide-react";
import axios from "axios";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { Course, CurriculumStructure, Programme } from "../types";

type StructureContent = CurriculumStructure["version"]["content"];
type StructureCourse = StructureContent["semesters"][number]["courses"][number];
const errorMessage = (reason: unknown) => axios.isAxiosError(reason)
  ? reason.response?.data?.detail ?? "The request could not be completed."
  : "The request could not be completed.";

function blankContent(semesterCount: number): StructureContent {
  return { semesters: Array.from({ length: semesterCount }, (_, index) => ({ semester_number: index + 1, courses: [] })) };
}

export default function CurriculumDesignerPage() {
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [structures, setStructures] = useState<CurriculumStructure[]>([]);
  const [selectedProgrammeId, setSelectedProgrammeId] = useState("");
  const [selectedStructureId, setSelectedStructureId] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState<StructureContent>({ semesters: [] });
  const [courseChoices, setCourseChoices] = useState<Record<number, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const selectedProgramme = programmes.find((programme) => programme.id === selectedProgrammeId);
  const selectedStructure = structures.find((structure) => structure.id === selectedStructureId);
  const validation = selectedStructure?.version.validation;
  const courseById = useMemo(() => new Map(courses.map((course) => [course.id, course])), [courses]);

  const loadData = useCallback(async () => {
    try {
      const [programmeResponse, courseResponse, structureResponse] = await Promise.all([
        api.get<Programme[]>("/programmes", { params: { status: "active", limit: 100 } }),
        api.get<Course[]>("/courses", { params: { status: "active", limit: 100 } }),
        api.get<CurriculumStructure[]>("/curriculum-structures", { params: { limit: 100 } }),
      ]);
      setProgrammes(programmeResponse.data);
      setCourses(courseResponse.data);
      setStructures(structureResponse.data);
    } catch (reason) { setError(errorMessage(reason)); }
  }, []);

  useEffect(() => { void loadData(); }, [loadData]);

  function startNew() {
    setSelectedStructureId("");
    setSelectedProgrammeId("");
    setTitle("");
    setContent({ semesters: [] });
    setError("");
    setNotice("");
  }

  function startEdit(structure: CurriculumStructure) {
    setSelectedStructureId(structure.id);
    setSelectedProgrammeId(structure.programme_id);
    setTitle(structure.title);
    setContent(structure.version.content);
    setError("");
    setNotice("");
  }

  function chooseProgramme(id: string) {
    const programme = programmes.find((item) => item.id === id);
    setSelectedProgrammeId(id);
    setContent(blankContent(programme?.semester_count ?? 0));
  }

  function addCourse(semesterIndex: number) {
    const courseId = courseChoices[semesterIndex];
    const course = courseById.get(courseId);
    if (!course) return;
    setContent((current) => ({
      ...current,
      semesters: current.semesters.map((semester, index) => index === semesterIndex
        ? { ...semester, courses: [...semester.courses, { course_id: course.id, credits: String(course.credits) }] }
        : semester),
    }));
  }

  function updateCourse(semesterIndex: number, courseIndex: number, update: Partial<StructureCourse>) {
    setContent((current) => ({
      ...current,
      semesters: current.semesters.map((semester, index) => index === semesterIndex
        ? { ...semester, courses: semester.courses.map((course, itemIndex) => itemIndex === courseIndex ? { ...course, ...update } : course) }
        : semester),
    }));
  }

  function removeCourse(semesterIndex: number, courseIndex: number) {
    setContent((current) => ({
      ...current,
      semesters: current.semesters.map((semester, index) => index === semesterIndex
        ? { ...semester, courses: semester.courses.filter((_, itemIndex) => itemIndex !== courseIndex) }
        : semester),
    }));
  }

  async function saveStructure() {
    if (!selectedProgrammeId || !title.trim()) {
      setError("Choose a programme and enter a structure title.");
      return;
    }
    if (content.semesters.some((semester) => semester.courses.length === 0)) {
      setError("Add at least one course to every semester before saving.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = { title: title.trim(), content };
      if (selectedStructureId) {
        await api.patch(`/curriculum-structures/${selectedStructureId}`, body);
        setNotice("A new immutable curriculum version was saved.");
      } else {
        const { data } = await api.post<CurriculumStructure>("/curriculum-structures", { programme_id: selectedProgrammeId, ...body });
        setSelectedStructureId(data.id);
        setNotice("Curriculum structure created.");
      }
      await loadData();
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  }

  async function runValidation() {
    if (!selectedStructureId) return;
    setBusy(true);
    setError("");
    try {
      await api.post(`/curriculum-structures/${selectedStructureId}/validate`);
      setNotice("Credit and course-category validation completed.");
      await loadData();
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  }

  return <PortalLayout role="admin">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div><p className="text-sm font-medium text-navy">ADMIN WORKSPACE</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Curriculum designer</h1><p className="mt-2 text-sm text-slate-500">Build semester plans from the reusable course library, validate credits, and preserve each saved revision.</p></div>
      <button onClick={startNew} className="inline-flex items-center gap-2 rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white"><FilePlus2 size={16} />New structure</button>
    </div>
    {notice && <div role="status" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div>}
    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    <div className="mt-6 grid gap-6 xl:grid-cols-[300px_1fr]">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card">
        <h2 className="font-bold text-ink">Saved structures</h2>
        <div className="mt-3 space-y-2">
          {structures.length === 0 && <p className="py-4 text-sm text-slate-500">No manual structures yet.</p>}
          {structures.map((structure) => <button key={structure.id} onClick={() => startEdit(structure)} className={`w-full rounded-xl border p-3 text-left ${selectedStructureId === structure.id ? "border-blue-300 bg-blue-50" : "border-slate-100 hover:bg-slate-50"}`}>
            <span className="block text-sm font-semibold text-ink">{structure.title}</span><span className="mt-1 block text-xs text-slate-500">{structure.programme_name} · v{structure.current_version}</span>
          </button>)}
        </div>
      </section>
      <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-xs font-semibold text-slate-600">Programme<select disabled={Boolean(selectedStructureId)} value={selectedProgrammeId} onChange={(event) => chooseProgramme(event.target.value)} className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5 text-sm disabled:bg-slate-100"><option value="">Select programme</option>{programmes.map((programme) => <option key={programme.id} value={programme.id}>{programme.name} · {programme.university_name}</option>)}</select></label>
          <label className="text-xs font-semibold text-slate-600">Structure title<input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. BSc Computer Science Curriculum" className="mt-1 w-full rounded-lg border px-3 py-2.5 text-sm" /></label>
        </div>
        {selectedProgramme && <div className="mt-5 space-y-4">
          {content.semesters.map((semester, semesterIndex) => <div key={semester.semester_number} className="rounded-xl border border-slate-200 p-4">
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div><h3 className="font-bold text-ink">Semester {semester.semester_number}</h3><p className="mt-1 text-xs text-slate-500">{semester.courses.reduce((total, course) => total + Number(course.credits || 0), 0).toFixed(2)} allocated credits</p></div>
              <div className="flex gap-2"><select value={courseChoices[semesterIndex] ?? ""} onChange={(event) => setCourseChoices((current) => ({ ...current, [semesterIndex]: event.target.value }))} className="min-w-0 rounded-lg border bg-white px-2 py-2 text-sm"><option value="">Choose library course</option>{courses.map((course) => <option key={course.id} value={course.id}>{course.course_code} — {course.name}</option>)}</select><button onClick={() => addCourse(semesterIndex)} className="inline-flex shrink-0 items-center gap-1 rounded-lg bg-blue-50 px-3 text-sm font-semibold text-navy"><Plus size={15} />Add</button></div>
            </div>
            {semester.courses.length === 0 ? <p className="mt-4 text-sm text-slate-400">No courses assigned to this semester.</p> : <div className="mt-3 divide-y divide-slate-100">
              {semester.courses.map((item, courseIndex) => {
                const course = courseById.get(item.course_id);
                return <div key={`${item.course_id}-${courseIndex}`} className="flex flex-wrap items-center gap-3 py-3">
                  <div className="min-w-[180px] flex-1"><p className="text-sm font-semibold text-ink">{course?.course_code ?? "Unknown course"} · {course?.name ?? item.course_id}</p><p className="mt-0.5 text-xs text-slate-500">{course?.category ?? "Category unavailable"} · {course?.course_type ?? ""}</p></div>
                  <label className="text-xs text-slate-500">Credits<input type="number" min="0.01" max="1000" step="0.01" value={item.credits} onChange={(event) => updateCourse(semesterIndex, courseIndex, { credits: event.target.value })} className="ml-2 w-24 rounded-md border px-2 py-1.5 text-sm text-ink" /></label>
                  <button aria-label={`Remove ${course?.course_code ?? "course"}`} onClick={() => removeCourse(semesterIndex, courseIndex)} className="rounded-lg p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600"><Trash2 size={16} /></button>
                </div>;
              })}
            </div>}
          </div>)}
        </div>}
        <div className="mt-5 flex flex-wrap gap-3">
          <button disabled={busy || !selectedProgramme} onClick={() => void saveStructure()} className="inline-flex items-center gap-2 rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><Save size={16} />{busy ? "Working…" : "Save structure"}</button>
          {selectedStructureId && <button disabled={busy} onClick={() => void runValidation()} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:opacity-50"><ClipboardCheck size={16} />Validate current version</button>}
        </div>
        {validation && <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-center gap-2"><span className={`rounded-full px-2.5 py-1 text-xs font-bold capitalize ${validation.status === "passed" ? "bg-emerald-100 text-emerald-800" : validation.status === "failed" ? "bg-rose-100 text-rose-800" : "bg-amber-100 text-amber-800"}`}>{validation.status}</span><span className="text-sm font-semibold text-ink">Total {validation.total_credits} credits · {validation.configured_constraint_count} regulatory constraints</span></div>
          <ul className="mt-3 space-y-2">{validation.checks.map((check, index) => <li key={`${check.kind}-${index}`} className="flex gap-2 text-sm text-slate-700">{check.passed ? <Check size={16} className="shrink-0 text-emerald-600" /> : <AlertTriangle size={16} className="shrink-0 text-amber-600" />}{check.message}</li>)}</ul>
          {validation.warnings?.map((warning) => <p key={warning} className="mt-2 text-sm text-amber-700">{warning}</p>)}
        </div>}
      </section>
    </div>
  </PortalLayout>;
}

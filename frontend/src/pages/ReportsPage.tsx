import { useEffect, useMemo, useState } from "react";
import { Download, FileSpreadsheet } from "lucide-react";
import axios from "axios";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { College, Course, CurriculumLibraryItem, Programme, University } from "../types";

type ReportKind = "universities" | "colleges" | "programmes" | "courses" | "curricula";
type ReportRow = Record<string, string | number | null>;
const labels: Record<ReportKind, string> = {
  universities: "Universities",
  colleges: "Colleges",
  programmes: "Programmes",
  courses: "Course library",
  curricula: "Published curricula",
};
const csvCell = (value: string | number | null) => `"${String(value ?? "").replaceAll('"', '""')}"`;
const errorMessage = (reason: unknown) => axios.isAxiosError(reason)
  ? reason.response?.data?.detail ?? "The report data could not be loaded."
  : "The report data could not be loaded.";

export default function ReportsPage() {
  const [kind, setKind] = useState<ReportKind>("universities");
  const [universities, setUniversities] = useState<University[]>([]);
  const [colleges, setColleges] = useState<College[]>([]);
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [curricula, setCurricula] = useState<CurriculumLibraryItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<University[]>("/universities", { params: { limit: 100 } }),
      api.get<College[]>("/colleges", { params: { limit: 100 } }),
      api.get<Programme[]>("/programmes", { params: { limit: 100 } }),
      api.get<Course[]>("/courses", { params: { limit: 100 } }),
      api.get<CurriculumLibraryItem[]>("/curricula", { params: { limit: 100 } }),
    ]).then(([universityResponse, collegeResponse, programmeResponse, courseResponse, curriculumResponse]) => {
      setUniversities(universityResponse.data);
      setColleges(collegeResponse.data);
      setProgrammes(programmeResponse.data);
      setCourses(courseResponse.data);
      setCurricula(curriculumResponse.data);
    }).catch((reason: unknown) => setError(errorMessage(reason)))
      .finally(() => setLoading(false));
  }, []);

  const rows = useMemo<ReportRow[]>(() => {
    switch (kind) {
      case "universities":
        return universities.map(({ name, code, status, contact_person, contact_email, phone_number, created_at }) =>
          ({ name, code, status, contact_person, contact_email, phone_number, created_at }));
      case "colleges":
        return colleges.map(({ university_name, name, code, status, state, district, contact_email, reviewer_name, programme_count, assignment_count }) =>
          ({ university_name, name, code, status, state, district, contact_email, reviewer_name, programme_count, assignment_count }));
      case "programmes":
        return programmes.map(({ university_name, name, degree_type, specialization, level, duration_years, semester_count, academic_year, status }) =>
          ({ university_name, name, degree_type, specialization, level, duration_years, semester_count, academic_year, status }));
      case "courses":
        return courses.map(({ course_code, name, category, course_type, credits, status, programme_ids }) =>
          ({ course_code, name, category, course_type, credits, status, programme_count: programme_ids.length }));
      case "curricula":
        return curricula.map(({ title, programme_name, university_name, academic_year, status, current_version_number, created_at }) =>
          ({ title, programme_name, university_name, academic_year, status, current_version_number, created_at }));
    }
  }, [kind, universities, colleges, programmes, courses, curricula]);

  function downloadCsv() {
    if (rows.length === 0) return;
    const columns = Object.keys(rows[0]);
    const csv = [columns.map(csvCell).join(","), ...rows.map((row) => columns.map((column) => csvCell(row[column])).join(","))].join("\r\n");
    const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `curriculum-hub-${kind}-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return <PortalLayout role="admin">
    <div><p className="text-sm font-medium text-navy">ADMIN WORKSPACE</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Reports &amp; exports</h1><p className="mt-2 text-sm text-slate-500">Review current platform records and export operational summaries as CSV.</p></div>
    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    <section className="mt-7 max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
      <div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-navy"><FileSpreadsheet size={20} /></span><div><h2 className="font-bold text-ink">Operational data export</h2><p className="mt-1 text-sm text-slate-500">Exports up to 100 records of the selected type.</p></div></div>
      <label className="mt-6 block text-xs font-semibold text-slate-600">Report<select value={kind} onChange={(event) => setKind(event.target.value as ReportKind)} className="mt-1 w-full rounded-lg border bg-white px-3 py-2.5 text-sm">{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <div className="mt-4 flex items-center justify-between rounded-xl bg-slate-50 p-4"><span className="text-sm text-slate-600">{loading ? "Loading report data…" : `${rows.length} ${labels[kind].toLowerCase()} available`}</span><button disabled={loading || rows.length === 0} onClick={downloadCsv} className="inline-flex items-center gap-2 rounded-lg bg-navy px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><Download size={15} />Download CSV</button></div>
      <p className="mt-3 text-xs leading-relaxed text-slate-500">Exports exclude account passwords, authentication tokens, reviewer comments, and private attachments.</p>
    </section>
  </PortalLayout>;
}

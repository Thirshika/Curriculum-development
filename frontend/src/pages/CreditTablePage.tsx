import { FormEvent, useCallback, useEffect, useState } from "react";
import { RefreshCw, SlidersHorizontal, Trash2 } from "lucide-react";
import axios from "axios";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { CreditTableRow, CreditTableSource } from "../types";

type Level = "ug" | "pg";
type TableView = "limits" | "distribution";
const semesterLabels = ["I", "II", "III", "IV", "V", "VI"];
const semesterDistribution = [
  { category: "Core (CC)", creditsPerPaper: 4, papers: [2, 2, 2, 3, 3, 3] },
  { category: "Minor (MI)", creditsPerPaper: 4, papers: [0, 1, 1, 1, 1, 2] },
  { category: "Multidisciplinary (MDC)", creditsPerPaper: 3, papers: [1, 1, 1, 0, 0, 0] },
  { category: "AEC", creditsPerPaper: 3, papers: [2, 2, 0, 0, 0, 0] },
  { category: "SEC", creditsPerPaper: 3, papers: [0, 0, 1, 1, 1, 0] },
  { category: "VAC", creditsPerPaper: 3, papers: [1, 1, 0, 0, 0, 0] },
  { category: "Internship (INT)", creditsPerPaper: 4, papers: [0, 0, 0, 0, 0, 1] },
];
const broadCategoryLabels: Record<string, string> = {
  Major: "Major (Core)",
  Minor: "Minor Stream",
  "Ability Enhancement": "Ability Enhancement Courses (AEC)",
  "Skill-Based": "Skill Enhancement Courses (SEC)",
  "Value-Added": "Value Added Courses common for all UG",
  "Research Project": "Research Project / Dissertation",
};
const errorMessage = (reason: unknown) => {
  if (!axios.isAxiosError(reason)) return "The request could not be completed.";
  const detail: unknown = reason.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => typeof item === "object" && item !== null && "msg" in item ? String(item.msg) : String(item)).join("; ");
  return "The request could not be completed.";
};
const format = (value: string | null) => value === null ? "—" : `${value} cr`;

function Source({ source, onRemove }: { source: CreditTableSource | null; onRemove: (id: string) => void }) {
  if (!source?.manual) return null;
  const overrideId = source.override_id;
  return <span className="inline-flex items-center gap-1"><span className="rounded-full bg-violet-100 px-2 py-1 text-[10px] font-bold uppercase text-violet-800">Manual</span>{overrideId && <button aria-label="Remove manual override" title="Remove override" className="text-rose-600 hover:text-rose-800" onClick={() => onRemove(overrideId)}><Trash2 size={13} /></button>}</span>;
}

export default function CreditTablePage() {
  const [level, setLevel] = useState<Level>("ug");
  const [durationYears, setDurationYears] = useState<3 | 4>(3);
  const [tableView, setTableView] = useState<TableView>("limits");
  const [rows, setRows] = useState<CreditTableRow[]>([]);
  const [category, setCategory] = useState("");
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const supportsSemesterDistribution = level === "ug" && durationYears === 3;
  const semesterTotals = semesterLabels.map((_, semesterIndex) =>
    semesterDistribution.reduce((total, row) => total + row.papers[semesterIndex] * row.creditsPerPaper, 0),
  );
  const totalDistributionCredits = semesterTotals.reduce((total, credits) => total + credits, 0);

  const loadTable = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<{ rows: CreditTableRow[] }>("/credit-table", { params: { programme_level: level, duration_years: durationYears } });
      setRows(data.rows);
      setCategory((current) => data.rows.some((row) => row.category === current) ? current : data.rows[0]?.category ?? "");
      setError("");
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setLoading(false); }
  }, [durationYears, level]);

  useEffect(() => { void loadTable(); }, [loadTable]);
  useEffect(() => {
    const timer = window.setInterval(() => { void loadTable(); }, 10000);
    return () => window.clearInterval(timer);
  }, [loadTable]);
  async function saveOverride(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.put("/credit-table/overrides", {
        programme_level: level,
        scope_type: "category",
        category: category.trim(),
        limit_type: "maximum",
        value: Number(value),
      });
      setNotice("Manual override saved. It will take precedence over regulatory limits.");
      setValue("");
      await loadTable();
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  }

  async function deleteOverride(id: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.delete(`/credit-table/overrides/${id}`);
      setNotice("Manual maximum removed.");
      await loadTable();
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  }

  return <PortalLayout role="admin">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-medium text-navy">STEP 2 · DERIVED CREDIT LIMITS</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Credit Table</h1><p className="mt-2 max-w-3xl text-sm text-slate-500">Minimum credits are extracted from regulation tables. Enter maximum credits manually for each broad course category.</p></div><div className="flex items-center gap-2"><label className="text-xs font-semibold text-slate-500">Programme level<select value={level} onChange={(event) => { setLevel(event.target.value as Level); setTableView("limits"); }} className="form-input ml-2 min-w-24"><option value="ug">UG</option><option value="pg">PG</option></select></label><button aria-label="Refresh credit table" onClick={() => void loadTable()} className="rounded-lg border p-2 text-slate-600"><RefreshCw size={17} /></button></div></div>
    {notice && <div role="status" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div>}
    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    <section className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card">
      <div className="border-b border-slate-100 px-5 py-4"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-bold text-ink">{tableView === "distribution" && supportsSemesterDistribution ? "Semester-wise paper count and credit distribution · 3-year UG" : `${durationYears}-year full degree · ${level.toUpperCase()}`}</h2><div className="flex flex-wrap items-center gap-3"><div className="inline-flex rounded-lg bg-slate-100 p-1" role="group" aria-label="Degree duration"><button type="button" aria-pressed={durationYears === 3} onClick={() => { setDurationYears(3); setTableView("limits"); }} className={`rounded-md px-3 py-2 text-sm font-semibold ${durationYears === 3 ? "bg-white text-navy shadow-sm" : "text-slate-600"}`}>3-year full degree</button><button type="button" aria-pressed={durationYears === 4} onClick={() => { setDurationYears(4); setTableView("limits"); }} className={`rounded-md px-3 py-2 text-sm font-semibold ${durationYears === 4 ? "bg-white text-navy shadow-sm" : "text-slate-600"}`}>4-year full degree</button></div><div className="inline-flex rounded-lg bg-slate-100 p-1" role="group" aria-label="Credit table view"><button type="button" aria-pressed={tableView === "limits"} onClick={() => setTableView("limits")} className={`rounded-md px-3 py-2 text-sm font-semibold ${tableView === "limits" ? "bg-white text-navy shadow-sm" : "text-slate-600"}`}>Credit limits</button><button type="button" aria-pressed={tableView === "distribution"} disabled={!supportsSemesterDistribution} title={supportsSemesterDistribution ? undefined : "Semester-wise distribution is available for 3-year UG"} onClick={() => setTableView("distribution")} className={`rounded-md px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${tableView === "distribution" && supportsSemesterDistribution ? "bg-white text-navy shadow-sm" : "text-slate-600"}`}>Sem-wise distribution</button></div></div></div>{!supportsSemesterDistribution && <p className="mt-2 text-xs text-slate-500">Semester-wise distribution is available for 3-year UG.</p>}</div>
      {tableView === "distribution" && supportsSemesterDistribution ? <div className="overflow-x-auto"><table className="w-full min-w-[900px] border-collapse text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th scope="col" className="border border-slate-200 px-4 py-3">Course category</th>{semesterLabels.map((semester) => <th scope="col" key={semester} className="border border-slate-200 px-4 py-3">Sem {semester}</th>)}<th scope="col" className="border border-slate-200 px-4 py-3">Total credits</th></tr></thead><tbody>{semesterDistribution.map((row) => { const totalCredits = row.papers.reduce((total, papers) => total + papers, 0) * row.creditsPerPaper; return <tr key={row.category}><th scope="row" className="border border-slate-200 px-4 py-3 font-semibold text-slate-800">{row.category}</th>{row.papers.map((papers, index) => <td key={index} className="border border-slate-200 px-4 py-3">{papers * row.creditsPerPaper}</td>)}<td className="border border-slate-200 px-4 py-3">{totalCredits}</td></tr>; })}<tr className="bg-slate-50 font-bold text-ink"><th scope="row" className="border border-slate-200 px-4 py-3">Semester total</th>{semesterTotals.map((credits, index) => <td key={index} className="border border-slate-200 px-4 py-3">{credits}</td>)}<td className="border border-slate-200 px-4 py-3">{totalDistributionCredits}</td></tr></tbody></table></div> : <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Broad category of course</th><th className="px-4 py-3">Minimum credit</th><th className="px-4 py-3">Maximum credit</th></tr></thead><tbody className="divide-y divide-slate-100">{rows.map((row) => <tr key={row.scope_type === "total" ? "total" : row.category}><td className="px-5 py-4 font-semibold text-slate-800">{row.scope_type === "total" ? "Total" : row.category ? broadCategoryLabels[row.category] ?? row.category : ""}</td><td className="px-4 py-4">{row.credit_value === "—" ? "—" : row.credit_value ? `${row.credit_value} cr` : "—"}</td><td className="px-4 py-4">{row.scope_type === "total" ? "—" : <><div>{format(row.maximum)}</div><div className="mt-1"><Source source={row.maximum_source} onRemove={(id) => void deleteOverride(id)} /></div></>}</td></tr>)}
        {!rows.length && <tr><td colSpan={3} className="px-5 py-12 text-center text-sm text-slate-500">{loading ? "Loading credit limits…" : "No broad course-category credit table is available for this level."}</td></tr>}</tbody></table></div>}
    </section>
    <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
      <h2 className="flex items-center gap-2 font-bold text-ink"><SlidersHorizontal size={17} />Add or update a manual override</h2>
      <form onSubmit={(event) => void saveOverride(event)} className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-xs font-semibold text-slate-600">Broad category of course<select required value={category} onChange={(event) => setCategory(event.target.value)} className="form-input mt-1" disabled={!rows.length}>{rows.map((row) => <option key={row.category} value={row.category ?? ""}>{row.category ? broadCategoryLabels[row.category] ?? row.category : ""}</option>)}</select></label>
        <label className="text-xs font-semibold text-slate-600">Limit type<select value="maximum" className="form-input mt-1" disabled><option value="maximum">Maximum</option></select></label>
        <label className="text-xs font-semibold text-slate-600">Credits<input required type="number" min="0" max="100000" step="0.01" value={value} onChange={(event) => setValue(event.target.value)} className="form-input mt-1" /></label>
        <button disabled={busy || !rows.length || !category} className="self-end rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Saving…" : "Save override"}</button>
      </form>
    </section>
  </PortalLayout>;
}

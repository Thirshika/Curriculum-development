import { FormEvent, useCallback, useEffect, useState } from "react";
import { Search, Trash2, Upload } from "lucide-react";
import axios from "axios";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { RegulatoryDocument } from "../types";

const errorMessage = (reason: unknown) => {
  if (!axios.isAxiosError(reason)) return "The request could not be completed.";
  const detail: unknown = reason.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => typeof item === "object" && item !== null && "msg" in item ? String(item.msg) : String(item)).join("; ");
  return "The request could not be completed.";
};

export default function RegulationsPage() {
  const [documents, setDocuments] = useState<RegulatoryDocument[]>([]);
  const [search, setSearch] = useState("");
  const [issuer, setIssuer] = useState("");
  const [year, setYear] = useState("");
  const [level, setLevel] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [issuingAuthority, setIssuingAuthority] = useState("");
  const [version, setVersion] = useState("");
  const [documentYear, setDocumentYear] = useState(String(new Date().getFullYear()));
  const [programmeLevel, setProgrammeLevel] = useState<"ug" | "pg">("ug");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get<RegulatoryDocument[]>("/regulations", {
        params: {
          search: search || undefined,
          issuing_authority: issuer || undefined,
          year: year || undefined,
          programme_level: level || undefined,
          limit: 100,
        },
      });
      setDocuments(data);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setLoading(false); }
  }, [issuer, level, search, year]);

  useEffect(() => { void loadDocuments(); }, [loadDocuments]);

  async function uploadDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return setError("Choose a PDF to upload.");
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const formData = new FormData();
      formData.append("title", title);
      formData.append("issuing_authority", issuingAuthority);
      formData.append("year", documentYear);
      formData.append("version", version);
      formData.append("programme_level", programmeLevel);
      formData.append("file", file);
      const { data } = await api.post<RegulatoryDocument>("/regulations", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setNotice(data.courses_imported
        ? `Uploaded ${data.title}; ${data.courses_imported} course(s) imported from PDF and ${data.rule_count} credit rule(s) extracted.`
        : `Uploaded ${data.title}; no complete course rows were found, and ${data.rule_count} credit rule(s) were extracted. Course rows need a title, category, semester, L-T-P, and credits.`);
      setTitle("");
      setIssuingAuthority("");
      setVersion("");
      setFile(null);
      await loadDocuments();
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusy(false); }
  }

  async function deleteDocument(document: RegulatoryDocument) {
    if (!window.confirm(`Delete "${document.title}"? Its extracted credit limits and stored PDF will also be deleted.`)) return;
    const previousIndex = documents.findIndex((item) => item.id === document.id);
    setBusy(true);
    setError("");
    setNotice("");
    setDocuments((current) => current.filter((item) => item.id !== document.id));
    try {
      await api.delete(`/regulations/${document.id}`);
      setNotice(`${document.title} deleted.`);
    } catch (reason) {
      setDocuments((current) => {
        if (current.some((item) => item.id === document.id)) return current;
        const restored = [...current];
        restored.splice(Math.min(previousIndex, restored.length), 0, document);
        return restored;
      });
      setError(errorMessage(reason));
    }
    finally { setBusy(false); }
  }

  return <PortalLayout role="admin">
    <div><p className="text-sm font-medium text-navy">STEP 1 · REGULATORY KNOWLEDGE BASE</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Regulatory Knowledge Base</h1><p className="mt-2 max-w-3xl text-sm text-slate-500">Upload regulations and extract credit limits. Complete detected limits flow straight to the Credit Table and Course Library without approval.</p></div>
    {notice && <div role="status" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div>}
    {error && <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
      <h2 className="flex items-center gap-2 font-bold text-ink"><Upload size={17} />Upload regulation PDF</h2>
      <form onSubmit={(event) => void uploadDocument(event)} className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-xs font-semibold text-slate-600">Title<input required minLength={2} maxLength={240} value={title} onChange={(event) => setTitle(event.target.value)} className="form-input mt-1" /></label>
        <label className="text-xs font-semibold text-slate-600">Issuing body<input required minLength={2} maxLength={200} value={issuingAuthority} onChange={(event) => setIssuingAuthority(event.target.value)} className="form-input mt-1" /></label>
        <label className="text-xs font-semibold text-slate-600">Year<input required type="number" min="1900" max="2200" value={documentYear} onChange={(event) => setDocumentYear(event.target.value)} className="form-input mt-1" /></label>
        <label className="text-xs font-semibold text-slate-600">Version<input required maxLength={80} value={version} onChange={(event) => setVersion(event.target.value)} className="form-input mt-1" /></label>
        <label className="text-xs font-semibold text-slate-600">Programme level<select value={programmeLevel} onChange={(event) => setProgrammeLevel(event.target.value as "ug" | "pg")} className="form-input mt-1"><option value="ug">UG</option><option value="pg">PG</option></select></label>
        <label className="text-xs font-semibold text-slate-600">PDF file<input required type="file" accept="application/pdf,.pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="form-input mt-1" /></label>
        <button disabled={busy} className="rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50 sm:col-span-2 lg:col-span-3">{busy ? "Uploading…" : "Upload and apply extracted credit limits"}</button>
      </form>
    </section>
    <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
        <h2 className="font-bold text-ink">Regulation documents</h2>
        <form onSubmit={(event) => { event.preventDefault(); void loadDocuments(); }} className="mt-3 space-y-2">
          <label className="relative block"><Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Title or issuing body" className="search-input w-full rounded-lg border py-2 pr-3 text-sm" /></label>
          <div className="grid grid-cols-2 gap-2"><input aria-label="Filter by issuing body" value={issuer} onChange={(event) => setIssuer(event.target.value)} placeholder="Issuing body" className="min-w-0 rounded-lg border px-2 py-2 text-sm" /><input aria-label="Filter by year" value={year} onChange={(event) => setYear(event.target.value)} placeholder="Year" className="min-w-0 rounded-lg border px-2 py-2 text-sm" /><select aria-label="Filter by level" value={level} onChange={(event) => setLevel(event.target.value)} className="rounded-lg border px-2 py-2 text-sm"><option value="">UG/PG</option><option value="ug">UG</option><option value="pg">PG</option></select></div>
          <button className="w-full rounded-lg bg-slate-100 py-2 text-sm font-semibold text-slate-700">Search &amp; filter</button>
        </form>
        <div className="mt-3 space-y-2">{loading ? <p className="p-3 text-sm text-slate-500">Loading…</p> : documents.map((document) => <div key={document.id} className="flex items-start gap-2 rounded-xl border border-slate-100 p-3">
          <div className="min-w-0 flex-1 text-left">
            <span className="block text-sm font-semibold text-slate-800">{document.title}</span><span className="mt-1 block text-xs text-slate-500">{document.issuing_authority} · {document.year ?? "—"} · {document.applies_to_all_levels ? "ALL LEVELS" : document.programme_level?.toUpperCase() ?? "—"}</span><span className="mt-1 block text-xs text-slate-400">{document.rule_count} extracted items · v{document.version}</span>
          </div>
          <button aria-label={`Delete ${document.title}`} title="Delete regulation" disabled={busy} onClick={() => void deleteDocument(document)} className="rounded-lg border border-rose-100 p-2 text-rose-600 hover:bg-rose-50 disabled:opacity-50"><Trash2 size={15} /></button>
        </div>)}</div>
    </section>
  </PortalLayout>;
}

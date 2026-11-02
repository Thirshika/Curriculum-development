import { FormEvent, useCallback, useEffect, useState } from "react";
import { Archive, BookOpenText, Check, Download, FileText, Flag, Search, ShieldCheck, X } from "lucide-react";
import axios from "axios";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type { CreditConstraint, CreditConstraintKind, RegulatoryDocument, RegulatoryRule, University } from "../types";

type Category = "ugc" | "nep_2020" | "ncrf" | "nheqf" | "university" | "other";
type RuleStatus = "pending" | "verified" | "rejected";
type Tab = "documents" | "rules" | "verified" | "conflicts";

const categories: { value: Category; label: string }[] = [
  { value: "ugc", label: "UGC regulations and frameworks" },
  { value: "nep_2020", label: "NEP 2020" },
  { value: "ncrf", label: "National Credit Framework (NCrF)" },
  { value: "nheqf", label: "National Higher Education Qualifications Framework (NHEQF)" },
  { value: "university", label: "University regulations" },
  { value: "other", label: "Other approved guidelines" },
];

function errorText(error: unknown) {
  if (axios.isAxiosError(error)) return error.response?.data?.detail ?? "The request could not be completed.";
  return "The request could not be completed.";
}

function formatDate(value: string | null) {
  if (!value) return "Not specified";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

export default function RegulationsPage() {
  const [documents, setDocuments] = useState<RegulatoryDocument[]>([]);
  const [universities, setUniversities] = useState<University[]>([]);
  const [rules, setRules] = useState<RegulatoryRule[]>([]);
  const [constraints, setConstraints] = useState<CreditConstraint[]>([]);
  const [constraintKind, setConstraintKind] = useState<CreditConstraintKind>("min_total_credits");
  const [constraintValue, setConstraintValue] = useState("");
  const [tab, setTab] = useState<Tab>("documents");
  const [documentOffset, setDocumentOffset] = useState(0);
  const [ruleOffset, setRuleOffset] = useState(0);
  const [documentFilter, setDocumentFilter] = useState("");
  const [searchText, setSearchText] = useState("");
  const [category, setCategory] = useState<Category>("ugc");
  const [universityId, setUniversityId] = useState("");
  const [title, setTitle] = useState("");
  const [authority, setAuthority] = useState("");
  const [version, setVersion] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [applicability, setApplicability] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<RegulatoryDocument | null>(null);
  const [preview, setPreview] = useState("");
  const [previewTitle, setPreviewTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get<RegulatoryDocument[]>("/regulations", {
        params: {
          search: searchText.trim() || undefined,
          category: documentFilter || undefined,
          offset: documentOffset,
          limit: 25,
        },
      });
      setDocuments(data);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setLoading(false);
    }
  }, [documentFilter, documentOffset, searchText]);

  const loadRules = useCallback(async (statusFilter?: RuleStatus, conflictsOnly = false) => {
    setError("");
    try {
      const { data } = await api.get<RegulatoryRule[]>("/regulatory-rules", {
        params: {
          document_id: selectedDocument?.id,
          verification_status: statusFilter,
          conflicts_only: conflictsOnly || undefined,
          offset: ruleOffset,
          limit: 50,
        },
      });
      setRules(data);
    } catch (reason) {
      setError(errorText(reason));
    }
  }, [ruleOffset, selectedDocument?.id]);

  useEffect(() => { void loadDocuments(); }, [loadDocuments]);
  useEffect(() => {
    api.get<University[]>("/universities", { params: { limit: 100 } })
      .then(({ data }) => setUniversities(data.filter((university) => university.status === "active")))
      .catch((reason) => setError(errorText(reason)));
  }, []);
  useEffect(() => {
    if (tab !== "documents") void loadRules(tab === "rules" ? "pending" : tab === "verified" ? "verified" : undefined, tab === "conflicts");
  }, [loadRules, tab]);
  useEffect(() => {
    if (tab !== "verified") return;
    api.get<CreditConstraint[]>("/regulatory-rules/credit-constraints", {
      params: { document_id: selectedDocument?.id },
    }).then(({ data }) => setConstraints(data)).catch((reason) => setError(errorText(reason)));
  }, [selectedDocument?.id, tab]);

  async function uploadDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return setError("Choose a PDF or DOCX document to upload.");
    setSaving(true);
    setError("");
    setNotice("");
    const body = new FormData();
    body.append("file", file);
    body.append("category", category);
    body.append("issuing_authority", authority);
    body.append("version", version);
    body.append("applicability", applicability);
    if (category === "university") body.append("university_id", universityId);
    if (title.trim()) body.append("title", title.trim());
    if (effectiveDate) body.append("effective_date", effectiveDate);
    try {
      const { data } = await api.post<RegulatoryDocument>("/regulations", body, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setNotice(`Document uploaded. ${data.chunk_count} searchable sections prepared; ${data.pending_rules} extracted rule candidates need review.`);
      setFile(null);
      setTitle("");
      setAuthority("");
      setVersion("");
      setEffectiveDate("");
      setApplicability("");
      setUniversityId("");
      const input = document.getElementById("regulation-file") as HTMLInputElement | null;
      if (input) input.value = "";
      setDocumentOffset(0);
      setRuleOffset(0);
      await loadDocuments();
      setSelectedDocument(data);
      setTab("rules");
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setSaving(false);
    }
  }

  async function verifyRule(rule: RegulatoryRule, verificationStatus: "verified" | "rejected") {
    setError("");
    try {
      await api.patch(`/regulatory-rules/${rule.id}/verification`, { verification_status: verificationStatus });
      setNotice(verificationStatus === "verified" ? "Rule verified and available to regulatory retrieval." : "Rule rejected; it will not be used for retrieval.");
      await Promise.all([loadRules(tab === "rules" ? "pending" : tab === "verified" ? "verified" : undefined, tab === "conflicts"), loadDocuments()]);
    } catch (reason) {
      setError(errorText(reason));
    }
  }

  async function flagConflict(rule: RegulatoryRule) {
    const note = window.prompt("Describe the potential conflict for Admin review:", rule.conflict_note ?? "");
    if (note === null) return;
    if (!note.trim()) return setError("A conflict review note is required.");
    try {
      await api.patch(`/regulatory-rules/${rule.id}/conflict`, { has_conflict: true, conflict_note: note.trim() });
      setNotice("Potential conflict flagged for administrator review.");
      await loadRules(tab === "rules" ? "pending" : tab === "verified" ? "verified" : undefined, tab === "conflicts");
    } catch (reason) {
      setError(errorText(reason));
    }
  }

  async function clearConflict(rule: RegulatoryRule) {
    if (!window.confirm("Clear the conflict flag after completing the administrator review?")) return;
    try {
      await api.patch(`/regulatory-rules/${rule.id}/conflict`, { has_conflict: false });
      setNotice("Conflict flag cleared.");
      await loadRules(undefined, true);
    } catch (reason) {
      setError(errorText(reason));
    }
  }

  async function saveConstraint(event: FormEvent<HTMLFormElement>, rule: RegulatoryRule) {
    event.preventDefault();
    const value = Number(constraintValue);
    if (!Number.isFinite(value) || value <= 0) return setError("Enter a positive numeric threshold.");
    setError("");
    try {
      await api.put(`/regulatory-rules/${rule.id}/credit-constraint`, { kind: constraintKind, value });
      setNotice("Deterministic credit constraint saved with its verified regulatory source.");
      const { data } = await api.get<CreditConstraint[]>("/regulatory-rules/credit-constraints", {
        params: { document_id: selectedDocument?.id },
      });
      setConstraints(data);
    } catch (reason) {
      setError(errorText(reason));
    }
  }

  async function archiveDocument(documentItem: RegulatoryDocument) {
    if (!window.confirm(`Archive “${documentItem.title}” version ${documentItem.version}? Archived rules are excluded from retrieval.`)) return;
    try {
      await api.post(`/regulations/${documentItem.id}/archive`);
      setNotice(`${documentItem.title} version ${documentItem.version} archived.`);
      await loadDocuments();
      if (selectedDocument?.id === documentItem.id) setSelectedDocument({ ...documentItem, status: "archived" });
    } catch (reason) {
      setError(errorText(reason));
    }
  }

  async function showText(documentItem: RegulatoryDocument) {
    try {
      const { data } = await api.get<{ title: string; extracted_text: string }>(`/regulations/${documentItem.id}/text`);
      setPreviewTitle(data.title);
      setPreview(data.extracted_text);
    } catch (reason) {
      setError(errorText(reason));
    }
  }

  async function downloadSource(documentItem: RegulatoryDocument) {
    try {
      const { data } = await api.get<Blob>(`/regulations/${documentItem.id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(data);
      const anchor = window.document.createElement("a");
      anchor.href = url;
      anchor.download = documentItem.original_filename;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (reason) {
      setError(errorText(reason));
    }
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDocumentOffset(0);
    void loadDocuments();
  }

  const tabs: { value: Tab; label: string; count?: number }[] = [
    { value: "documents", label: "Documents" },
    { value: "rules", label: "Rule verification", count: documents.reduce((sum, item) => sum + item.pending_rules, 0) },
    { value: "verified", label: "Verified rules" },
    { value: "conflicts", label: "Conflict review" },
  ];

  return <PortalLayout role="admin">
    <div><p className="text-sm font-medium text-navy">ADMIN WORKSPACE</p><h1 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Regulatory knowledge base</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">Prepare and verify regulatory sources before they can inform curriculum generation. Uploading a document is not AI model training; only verified, active rules are returned by regulatory retrieval.</p></div>
    {notice && <div role="status" className="mt-6 flex items-start justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"><span className="flex items-start gap-2"><Check className="mt-0.5 shrink-0" size={16} />{notice}</span><button aria-label="Dismiss" onClick={() => setNotice("")}><X size={15} /></button></div>}
    {error && <div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

    <section className="mt-7 rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card sm:p-6">
      <div className="flex items-start gap-3"><div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-blue-50 text-navy"><FileText size={19} /></div><div><h2 className="text-base font-bold text-ink">Upload regulatory source</h2><p className="mt-1 text-sm text-slate-500">PDF and DOCX · 25 MB maximum · documents are stored privately and processed locally.</p></div></div>
      <form className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" onSubmit={uploadDocument}>
        <label className="text-sm font-medium text-slate-700">Regulatory category<select className="form-input mt-2" value={category} onChange={(event) => setCategory(event.target.value as Category)}>{categories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
        {category === "university" && <label className="text-sm font-medium text-slate-700">Applicable university<select className="form-input mt-2" required value={universityId} onChange={(event) => setUniversityId(event.target.value)}><option value="" disabled>Select the university for this regulation</option>{universities.map((university) => <option key={university.id} value={university.id}>{university.name} ({university.code})</option>)}</select></label>}
        <label className="text-sm font-medium text-slate-700">Document title<input className="form-input mt-2" maxLength={240} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. National Credit Framework" /></label>
        <label className="text-sm font-medium text-slate-700">Issuing authority<input className="form-input mt-2" required minLength={2} maxLength={200} value={authority} onChange={(event) => setAuthority(event.target.value)} placeholder="e.g. UGC" /></label>
        <label className="text-sm font-medium text-slate-700">Document version<input className="form-input mt-2" required maxLength={80} value={version} onChange={(event) => setVersion(event.target.value)} placeholder="e.g. 2023 / Version 1.0" /></label>
        <label className="text-sm font-medium text-slate-700">Effective date<input className="form-input mt-2" type="date" value={effectiveDate} onChange={(event) => setEffectiveDate(event.target.value)} /></label>
        <label className="text-sm font-medium text-slate-700">Applicability<input className="form-input mt-2" required minLength={2} maxLength={500} value={applicability} onChange={(event) => setApplicability(event.target.value)} placeholder="Programmes, levels, or universities covered" /></label>
        <label className="text-sm font-medium text-slate-700 sm:col-span-2 lg:col-span-3">PDF or Word document<input id="regulation-file" className="form-input mt-2 file:mr-3 file:rounded-md file:border-0 file:bg-blue-50 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-navy" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" required onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
        <div className="flex items-center justify-between gap-3 sm:col-span-2 lg:col-span-3"><p className="text-xs leading-5 text-slate-500">Text is extracted, split into searchable sections, and embedded locally. Candidate rules remain pending until an administrator verifies them.</p><button disabled={saving} className="shrink-0 rounded-xl bg-navy px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#102f5e] disabled:opacity-60">{saving ? "Processing…" : "Upload & process"}</button></div>
      </form>
    </section>

    <section className="mt-7 overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-card">
      <div className="flex flex-col justify-between gap-4 border-b border-slate-100 px-5 pt-5 sm:px-6">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><h2 className="text-base font-bold text-ink">Regulatory sources</h2><p className="mt-1 text-sm text-slate-500">Versioned source documents, extracted rules, and verification state.</p></div><form onSubmit={submitSearch} className="flex gap-2"><div className="relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} /><input className="form-input h-10 w-full pl-9 sm:w-56" value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Search sources" /></div><button className="rounded-xl border border-slate-200 px-3 text-sm font-semibold text-slate-600 hover:bg-slate-50">Search</button></form></div>
        <div className="flex gap-5 overflow-x-auto">{tabs.map((item) => <button key={item.value} onClick={() => { setRuleOffset(0); setTab(item.value); }} className={`flex shrink-0 items-center gap-2 border-b-2 px-1 pb-3 text-sm font-semibold ${tab === item.value ? "border-navy text-navy" : "border-transparent text-slate-500 hover:text-slate-800"}`}>{item.label}{item.count ? <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-800">{item.count}</span> : null}</button>)}</div>
      </div>
      {tab === "documents" && <>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3 sm:px-6"><label className="flex items-center gap-2 text-xs font-medium text-slate-500">Category<select className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700" value={documentFilter} onChange={(event) => { setDocumentOffset(0); setDocumentFilter(event.target.value); }}><option value="">All categories</option>{categories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label><span className="text-xs text-slate-500">Showing {documents.length ? documentOffset + 1 : 0}–{documentOffset + documents.length}</span></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[980px] text-left text-sm"><thead className="bg-slate-50/80 text-[11px] font-semibold uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3 sm:px-6">Source</th><th className="px-5 py-3">Category / version</th><th className="px-5 py-3">Effective date</th><th className="px-5 py-3">Rule status</th><th className="px-5 py-3">State</th><th className="px-5 py-3 text-right">Actions</th></tr></thead><tbody className="divide-y divide-slate-100">
          {loading && <tr><td colSpan={6} className="px-6 py-12 text-center text-sm text-slate-500">Loading regulatory sources…</td></tr>}
          {!loading && documents.length === 0 && <tr><td colSpan={6} className="px-6 py-14 text-center"><div className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-slate-50 text-slate-400"><BookOpenText size={20} /></div><p className="mt-3 text-sm font-semibold text-slate-700">No regulatory sources yet</p><p className="mt-1 text-xs text-slate-500">Upload an approved PDF or DOCX above to start the knowledge base.</p></td></tr>}
          {!loading && documents.map((item) => <tr key={item.id} className="hover:bg-slate-50/60"><td className="px-5 py-4 sm:px-6"><p className="font-semibold text-slate-800">{item.title}</p><p className="mt-1 text-xs text-slate-500">{item.issuing_authority} · {item.original_filename}</p><p className="mt-1 text-[11px] text-slate-400">{item.chunk_count} searchable sections{item.extraction_warnings.length ? " · extraction warning" : ""}</p></td><td className="px-5 py-4"><p className="font-medium text-slate-700">{categories.find((option) => option.value === item.category)?.label ?? item.category}</p><p className="mt-1 text-xs text-slate-500">Version {item.version}{item.university_name ? ` · ${item.university_name}` : ""}</p></td><td className="px-5 py-4 text-xs text-slate-600">{formatDate(item.effective_date)}</td><td className="px-5 py-4"><p className="text-xs font-medium text-amber-800">{item.pending_rules} pending</p><p className="mt-1 text-xs text-emerald-700">{item.verified_rules} verified · {item.rejected_rules} rejected</p></td><td className="px-5 py-4"><span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${item.status === "ready" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{item.status}</span></td><td className="px-5 py-4"><div className="flex justify-end gap-1"><button onClick={() => { setSelectedDocument(item); setTab("rules"); }} className="rounded-lg px-2.5 py-2 text-xs font-semibold text-navy hover:bg-blue-50">Review rules</button><button onClick={() => void showText(item)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" title="View extracted text" aria-label="View extracted text"><BookOpenText size={15} /></button><button onClick={() => void downloadSource(item)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" title="Download source" aria-label="Download source"><Download size={15} /></button>{item.status === "ready" && <button onClick={() => void archiveDocument(item)} className="rounded-lg p-2 text-slate-500 hover:bg-rose-50 hover:text-rose-600" title="Archive source" aria-label="Archive source"><Archive size={15} /></button>}</div></td></tr>)}
        </tbody></table></div>
        <div className="flex items-center justify-end gap-2 border-t border-slate-100 px-5 py-3 sm:px-6"><button disabled={documentOffset === 0 || loading} onClick={() => setDocumentOffset(Math.max(0, documentOffset - 25))} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 disabled:opacity-40">Previous</button><button disabled={documents.length < 25 || loading} onClick={() => setDocumentOffset(documentOffset + 25)} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 disabled:opacity-40">Next</button></div>
      </>}
      {tab !== "documents" && <div className="divide-y divide-slate-100">
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 sm:px-6">        <div className="flex items-center gap-2"><span className="text-xs font-medium text-slate-500">Source</span><select className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700" value={selectedDocument?.id ?? ""} onChange={(event) => { const selected = documents.find((item) => item.id === event.target.value) ?? null; setRuleOffset(0); setSelectedDocument(selected); }}><option value="">All sources</option>{documents.map((item) => <option key={item.id} value={item.id}>{item.title} · v{item.version}</option>)}</select></div><span className="text-xs text-slate-500">Showing {rules.length ? ruleOffset + 1 : 0}–{ruleOffset + rules.length}</span></div>
        {rules.length === 0 && <div className="px-6 py-14 text-center"><div className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-slate-50 text-slate-400">{tab === "conflicts" ? <Flag size={19} /> : <ShieldCheck size={19} />}</div><p className="mt-3 text-sm font-semibold text-slate-700">{tab === "conflicts" ? "No flagged conflicts" : tab === "verified" ? "No verified rules" : "No pending rules"}</p><p className="mt-1 text-xs text-slate-500">{tab === "conflicts" ? "Potential conflicts flagged for administrator review appear here." : tab === "verified" ? "Verified active rules that are eligible for regulatory retrieval appear here." : "Extracted rules await verification after a source document is uploaded."}</p></div>}
        {rules.map((rule) => {
          const ruleConstraints = constraints.filter((constraint) => constraint.rule_id === rule.id);
          return <article key={rule.id} className="px-5 py-5 sm:px-6">
            <div className="flex flex-col justify-between gap-3 sm:flex-row">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold capitalize ${rule.verification_status === "verified" ? "bg-emerald-50 text-emerald-700" : rule.verification_status === "rejected" ? "bg-rose-50 text-rose-700" : "bg-amber-50 text-amber-800"}`}>{rule.verification_status}</span>
                {rule.has_conflict && <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-2.5 py-1 text-[10px] font-semibold text-orange-800"><Flag size={12} />Conflict flagged</span>}
                <span className="text-xs font-medium text-slate-500">{rule.document_title} · v{rule.version}</span>
              </div>
              <span className="text-xs text-slate-500">{rule.clause ? `Clause ${rule.clause}` : "Section not identified"}{rule.page_number ? ` · Page ${rule.page_number}` : ""}</span>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-700">{rule.text}</p>
            <p className="mt-2 text-xs text-slate-500">{rule.issuing_authority} · {rule.applicability} · Effective {formatDate(rule.effective_date)}</p>
            {rule.conflict_note && <p className="mt-3 rounded-lg border border-orange-100 bg-orange-50 px-3 py-2 text-xs leading-5 text-orange-900"><strong>Conflict note:</strong> {rule.conflict_note}</p>}
            {ruleConstraints.length > 0 && <div className="mt-4 flex flex-wrap gap-2">{ruleConstraints.map((constraint) => <span key={constraint.id} className="rounded-lg border border-blue-100 bg-blue-50 px-2.5 py-1.5 text-xs font-semibold text-navy">{constraint.kind.replaceAll("_", " ")}: {constraint.value}</span>)}</div>}
            {tab === "verified" && !rule.has_conflict && <form onSubmit={(event) => void saveConstraint(event, rule)} className="mt-4 flex flex-wrap items-end gap-2 rounded-xl bg-slate-50 p-3">
              <label className="text-xs font-medium text-slate-600">Deterministic check<select className="form-input mt-1.5 h-9 py-1 text-xs" value={constraintKind} onChange={(event) => setConstraintKind(event.target.value as CreditConstraintKind)}><option value="min_total_credits">Minimum total credits</option><option value="max_total_credits">Maximum total credits</option><option value="min_semester_credits">Minimum credits each semester</option><option value="max_semester_credits">Maximum credits each semester</option><option value="min_duration_years">Minimum programme duration (years)</option><option value="max_duration_years">Maximum programme duration (years)</option><option value="min_semesters">Minimum semester count</option><option value="max_semesters">Maximum semester count</option></select></label>
              <label className="text-xs font-medium text-slate-600">Rule threshold<input className="form-input mt-1.5 h-9 w-36 py-1 text-xs" type="number" min="0.01" step="0.01" required value={constraintValue} onChange={(event) => setConstraintValue(event.target.value)} placeholder="e.g. 120" /></label>
              <button className="rounded-lg bg-navy px-3 py-2 text-xs font-semibold text-white hover:bg-[#102f5e]">Save configured rule</button>
              <p className="basis-full text-[11px] leading-5 text-slate-500">Enter only the numeric requirement explicitly stated by this verified source. This does not infer a rule from its text.</p>
            </form>}
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              {tab === "conflicts" && <button onClick={() => void clearConflict(rule)} className="rounded-lg border border-orange-200 px-3 py-2 text-xs font-semibold text-orange-800 hover:bg-orange-50">Clear conflict flag</button>}
              {tab === "rules" && rule.verification_status === "pending" && <><button onClick={() => void verifyRule(rule, "rejected")} className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-50">Reject candidate</button><button onClick={() => void flagConflict(rule)} className="inline-flex items-center gap-1.5 rounded-lg border border-orange-200 px-3 py-2 text-xs font-semibold text-orange-800 hover:bg-orange-50"><Flag size={13} />Flag conflict</button><button onClick={() => void verifyRule(rule, "verified")} className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-800"><Check size={14} />Verify rule</button></>}
            </div>
          </article>;
        })}
        <div className="flex items-center justify-end gap-2 border-t border-slate-100 px-5 py-3 sm:px-6"><button disabled={ruleOffset === 0} onClick={() => setRuleOffset(Math.max(0, ruleOffset - 50))} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 disabled:opacity-40">Previous</button><button disabled={rules.length < 50} onClick={() => setRuleOffset(ruleOffset + 50)} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 disabled:opacity-40">Next</button></div>
      </div>}
    </section>

    {preview && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 p-4" role="dialog" aria-modal="true" aria-labelledby="preview-title"><section className="flex max-h-[85vh] w-full max-w-3xl flex-col rounded-2xl bg-white shadow-2xl"><header className="flex items-center justify-between border-b border-slate-100 px-5 py-4"><div><h2 id="preview-title" className="font-bold text-ink">{previewTitle}</h2><p className="mt-1 text-xs text-slate-500">Extracted source text · private administrator preview</p></div><button onClick={() => setPreview("")} aria-label="Close preview" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={18} /></button></header><pre className="overflow-auto whitespace-pre-wrap p-5 text-sm leading-6 text-slate-700">{preview}</pre></section></div>}
  </PortalLayout>;
}

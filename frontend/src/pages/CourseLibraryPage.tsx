import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUpDown,
  BookOpen,
  Calendar,
  Check,
  ChevronDown,
  Eye,
  FileCheck2,
  FileText,
  GraduationCap,
  Layers,
  Pencil,
  Plus,
  RotateCcw,
  Save,
  Settings,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import axios from "axios";
import api from "../api/client";
import PortalLayout from "../components/PortalLayout";
import type {
  CourseCatalogueRow,
  CourseCreditDefault,
  CourseLibraryDetail,
  CourseLibraryPaper,
  Programme,
  University,
} from "../types";

export type PaperDraft = {
  id?: string;
  semester: number;
  paper_code: string;
  paper_title: string;
  paper_type: string;
  category: string;
  lecture_hours: string;
  tutorial_hours: string;
  practical_hours: string;
  internal_marks: string;
  external_marks: string;
  total_marks: string;
  credits: string;
};

export type CourseForm = {
  course_name: string;
  course_code: string;
  course_level: string;
  university_id: string;
  faculty_school: string;
  course_type: string;
  department: string;
  programme_id: string;
  programme_code: string;
  description: string;
  regulation_year: string;
  academic_year: string;
  effective_from: string;
  effective_until: string;
  status: "active" | "draft" | "archived";
  objectives: string[];
};

export interface SemesterDistributionRule {
  category: string;
  aliases: string[];
  creditsPerPaper: number;
  papers: number[]; // Index 0 = Sem 1, Index 1 = Sem 2, ..., Index 5 = Sem 6
}

export const SEMESTER_DISTRIBUTION_RULES: SemesterDistributionRule[] = [
  {
    category: "Core (CC)",
    aliases: ["core", "core (cc)", "major", "major (core)", "cc"],
    creditsPerPaper: 4,
    papers: [2, 2, 2, 3, 3, 3], // Sem 1 has 2 major papers = 8 points (4 points per paper)
  },
  {
    category: "Minor (MI)",
    aliases: ["minor", "minor (mi)", "minor stream", "mi"],
    creditsPerPaper: 4,
    papers: [0, 1, 1, 1, 1, 2],
  },
  {
    category: "Multidisciplinary (MDC)",
    aliases: ["multidisciplinary", "multidisciplinary (mdc)", "mdc"],
    creditsPerPaper: 3,
    papers: [1, 1, 1, 0, 0, 0],
  },
  {
    category: "AEC",
    aliases: ["aec", "ability enhancement", "ability enhancement courses (aec)"],
    creditsPerPaper: 3,
    papers: [2, 2, 0, 0, 0, 0],
  },
  {
    category: "SEC",
    aliases: ["sec", "skill enhancement", "skill enhancement courses (sec)", "skill-based"],
    creditsPerPaper: 3,
    papers: [0, 0, 1, 1, 1, 0],
  },
  {
    category: "VAC",
    aliases: ["vac", "value added", "value-added", "value added courses common for all ug"],
    creditsPerPaper: 3,
    papers: [1, 1, 0, 0, 0, 0],
  },
  {
    category: "Internship (INT)",
    aliases: ["internship", "internship (int)", "int", "project", "research project"],
    creditsPerPaper: 4,
    papers: [0, 0, 0, 0, 0, 1],
  },
];

function getSemesterCategoryAllocation(categoryName: string, semester: number) {
  const norm = categoryName.trim().toLowerCase();
  const rule = SEMESTER_DISTRIBUTION_RULES.find((r) =>
    r.aliases.some((alias) => norm === alias || norm.includes(alias))
  );

  if (rule) {
    const semIndex = Math.max(0, semester - 1);
    const paperCountInSem = rule.papers[semIndex] ?? 0;
    return {
      categoryDisplay: rule.category,
      paperCountInSem,
      hasRule: true,
    };
  }

  return {
    categoryDisplay: categoryName,
    paperCountInSem: 0,
    hasRule: false,
  };
}

const defaultSamplePapers: PaperDraft[] = [];

const initialBlankForm = (): CourseForm => ({
  course_name: "",
  course_code: "",
  course_level: "UG",
  university_id: "",
  faculty_school: "",
  course_type: "Regular",
  department: "",
  programme_id: "",
  programme_code: "",
  description: "",
  regulation_year: "",
  academic_year: "",
  effective_from: "",
  effective_until: "",
  status: "draft",
  objectives: [],
});

const blankPaper = (semester: number): PaperDraft => {
  return {
    semester,
    paper_code: "",
    paper_title: "",
    paper_type: "Core",
    category: "Core (CC)",
    lecture_hours: "",
    tutorial_hours: "",
    practical_hours: "",
    internal_marks: "25",
    external_marks: "75",
    total_marks: "100",
    credits: "",
  };
};

const errorMessage = (reason: unknown) => {
  if (!axios.isAxiosError(reason)) return "The request could not be completed.";
  const detail: unknown = reason.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) =>
        typeof item === "object" && item !== null && "msg" in item
          ? String(item.msg)
          : String(item)
      )
      .join("; ");
  }
  return "The request could not be completed.";
};

function toDraft(paper: CourseLibraryPaper): PaperDraft {
  return {
    ...paper,
    lecture_hours: String(paper.lecture_hours),
    tutorial_hours: String(paper.tutorial_hours),
    practical_hours: String(paper.practical_hours),
    internal_marks: String(paper.internal_marks),
    external_marks: String(paper.external_marks),
    total_marks: String(paper.total_marks),
    credits: String(paper.credits),
  };
}

function totalCredits(papers: PaperDraft[]): number {
  return papers.reduce((sum, paper) => sum + (Number(paper.credits) || 0), 0);
}

export default function CourseLibraryPage() {
  const [universities, setUniversities] = useState<University[]>([]);
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [catalogue, setCatalogue] = useState<CourseCatalogueRow[]>([]);
  const [activeTab, setActiveTab] = useState<"designer" | "catalogue">("designer");

  const [form, setForm] = useState<CourseForm>(initialBlankForm);
  const [papers, setPapers] = useState<PaperDraft[]>([]);
  const [semesterCount, setSemesterCount] = useState<number>(6);
  const [activeSemester, setActiveSemester] = useState<number>(1);

  // Paper Add/Edit Modal
  const [paperModalOpen, setPaperModalOpen] = useState(false);
  const [editingPaperIndex, setEditingPaperIndex] = useState<number | null>(null);
  const [paperForm, setPaperForm] = useState<PaperDraft>(blankPaper(1));
  const [creditDefault, setCreditDefault] = useState<CourseCreditDefault | null>(null);
  const [creditDefaultLoading, setCreditDefaultLoading] = useState(false);
  const [applyFetchedCreditDefault, setApplyFetchedCreditDefault] = useState(false);

  // Manage papers menu
  const [manageMenuOpen, setManageMenuOpen] = useState(false);
  const manageMenuRef = useRef<HTMLDivElement>(null);

  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState<CourseLibraryDetail | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const activeUniversities = useMemo(
    () => universities.filter((u) => u.status === "active"),
    [universities]
  );

  const selectedUniversity = useMemo(
    () => universities.find((u) => u.id === form.university_id),
    [universities, form.university_id]
  );

  const selectedProgramme = useMemo(
    () => programmes.find((p) => p.id === form.programme_id),
    [programmes, form.programme_id]
  );

  const availableProgrammes = useMemo(() => {
    if (!form.university_id) return programmes;
    return programmes.filter((p) => p.university_id === form.university_id);
  }, [programmes, form.university_id]);

  const activeModalCreditRule = useMemo(
    () => getSemesterCategoryAllocation(paperForm.category || "Core (CC)", activeSemester),
    [paperForm.category, activeSemester],
  );

  const activeSemesterPapers = useMemo(
    () => papers.filter((p) => p.semester === activeSemester),
    [papers, activeSemester]
  );

  const activeSemesterCredits = useMemo(
    () => totalCredits(activeSemesterPapers),
    [activeSemesterPapers]
  );

  useEffect(() => {
    if (!paperModalOpen || !form.programme_id || !paperForm.category) {
      setCreditDefault(null);
      return;
    }

    let active = true;
    setCreditDefault(null);
    setCreditDefaultLoading(true);
    async function loadCreditDefault() {
      try {
        const { data } = await api.get<CourseCreditDefault>("/courses/credits/default", {
          params: {
            programme_id: form.programme_id,
            category: paperForm.category,
            semester: activeSemester,
          },
        });
        if (!active) return;
        setCreditDefault(data);
        if (applyFetchedCreditDefault) {
          setPaperForm((current) => ({
            ...current,
            ...(data.default_credits !== null
              ? { credits: data.default_credits }
              : {}),
            ...(data.lecture_hours !== null
              ? { lecture_hours: data.lecture_hours }
              : {}),
            ...(data.tutorial_hours !== null
              ? { tutorial_hours: data.tutorial_hours }
              : {}),
            ...(data.practical_hours !== null
              ? { practical_hours: data.practical_hours }
              : {}),
          }));
        }
      } catch (reason) {
        if (active) {
          setCreditDefault(null);
          setError(errorMessage(reason));
        }
      } finally {
        if (active) {
          setCreditDefaultLoading(false);
          setApplyFetchedCreditDefault(false);
        }
      }
    }
    void loadCreditDefault();
    return () => {
      active = false;
    };
  }, [
    activeSemester,
    form.programme_id,
    paperForm.category,
    paperModalOpen,
  ]);

  // Close manage menu on outside click
  useEffect(() => {
    function handleClickOutside(evt: MouseEvent) {
      if (manageMenuRef.current && !manageMenuRef.current.contains(evt.target as Node)) {
        setManageMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const loadCatalogue = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<CourseCatalogueRow[]>("/courses/library", {
        params: {
          status: statusFilter || undefined,
          search: search.trim() || undefined,
        },
      });
      setCatalogue(data);
      setError("");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  // Initial load
  useEffect(() => {
    let active = true;
    async function loadOptions() {
      try {
        const [univRes, progRes] = await Promise.all([
          api.get<University[]>("/universities", { params: { limit: 100 } }),
          api.get<Programme[]>("/programmes", { params: { limit: 100 } }),
        ]);
        if (active) {
          setUniversities(univRes.data);
          setProgrammes(progRes.data);

          // Find ABC University or first active university
          const abc = univRes.data.find(
            (u) => u.name.toLowerCase().includes("abc") || u.status === "active"
          );
          if (abc) {
            const matchedProg = progRes.data.find(
              (p) =>
                p.university_id === abc.id &&
                p.name.toLowerCase().includes("b.sc")
            );
            setForm((prev) => {
              return {
                ...prev,
                university_id: abc.id,
                programme_id: matchedProg ? matchedProg.id : prev.programme_id,
                programme_code: matchedProg ? "BSC-CS" : prev.programme_code,
              };
            });
            if (matchedProg) setSemesterCount(matchedProg.semester_count);
          }
        }
      } catch (reason) {
        if (active) setError(errorMessage(reason));
      }
    }
    void loadOptions();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    void loadCatalogue();
  }, [loadCatalogue]);

  function setFormField<K extends keyof CourseForm>(key: K, value: CourseForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function handleUniversityChange(univId: string) {
    setFormField("university_id", univId);
    const firstProg = programmes.find((p) => p.university_id === univId);
    if (firstProg) {
      selectProgramme(firstProg.id);
    } else {
      setFormField("programme_id", "");
    }
  }

  async function selectProgramme(programmeId: string) {
    setFormField("programme_id", programmeId);
    if (!programmeId) return;
    const programme = programmes.find((item) => item.id === programmeId);
    if (programme) {
      setFormField("university_id", programme.university_id);
      setFormField("course_name", programme.name);
      setFormField("course_level", programme.level.toUpperCase());
      setSemesterCount(programme.semester_count || 6);
    }
    setError("");
    try {
      const { data } = await api.get<CourseLibraryDetail>(`/courses/library/${programmeId}`);
      if (data.configured) {
        setForm((prev) => ({
          ...prev,
          course_name: data.course_name || prev.course_name,
          course_code: data.course_code || prev.course_code,
          faculty_school: data.faculty_school || prev.faculty_school,
          department: data.department || prev.department,
          description: data.description || prev.description,
          regulation_year: data.regulation_year || prev.regulation_year,
          academic_year: data.academic_year || prev.academic_year,
          effective_from: data.effective_from ?? prev.effective_from,
          effective_until: data.effective_until ?? prev.effective_until,
          status: (data.status as "active" | "draft" | "archived") || prev.status,
        }));
        if (data.papers && data.papers.length > 0) {
          setPapers(data.papers.map(toDraft));
        }
      }
    } catch {
      // Keep defaults if not configured
    }
  }

  function startCreate() {
    setPreview(null);
    setForm(initialBlankForm());
    setPapers([]);
    setPaperForm(blankPaper(1));
    setEditingPaperIndex(null);
    setPaperModalOpen(false);
    setManageMenuOpen(false);
    setSemesterCount(6);
    setActiveSemester(1);
    setActiveTab("designer");
    setError("");
    setNotice("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function startEdit(row: CourseCatalogueRow) {
    setActiveTab("designer");
    setPreview(null);
    await selectProgramme(row.programme_id);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function addSemester() {
    if (!form.programme_id) {
      setError("Select a programme before adding a semester.");
      return;
    }
    if (semesterCount >= 24) {
      setError("A programme cannot have more than 24 semesters.");
      return;
    }

    const nextSemester = semesterCount + 1;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const { data } = await api.patch<Programme>(`/programmes/${form.programme_id}`, {
        semester_count: nextSemester,
      });
      setProgrammes((current) =>
        current.map((programme) => programme.id === data.id ? data : programme)
      );
      setSemesterCount(data.semester_count);
      setActiveSemester(data.semester_count);
      setNotice(`Semester ${data.semester_count} added.`);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setSaving(false);
    }
  }

  function handleDeleteSemester(sem: number) {
    // Must keep at least 1 semester
    if (semesterCount <= 1) return;
    const hasPapers = papers.some((p) => p.semester === sem);
    if (hasPapers) {
      setError(
        `Semester ${sem} has papers. Remove all papers from Semester ${sem} before deleting it.`
      );
      return;
    }
    // Renumber papers in higher semesters downward
    setPapers((current) =>
      current.map((p) =>
        p.semester > sem ? { ...p, semester: p.semester - 1 } : p
      )
    );
    const newCount = semesterCount - 1;
    setSemesterCount(newCount);
    // If we deleted the active semester, move to the one before it
    setActiveSemester((prev) => (prev >= sem ? Math.max(1, prev - 1) : prev));
    setNotice(`Semester ${sem} deleted. Remaining semesters renumbered.`);
  }

  // Paper Management
  function openAddPaper() {
    setEditingPaperIndex(null);
    setPaperForm(blankPaper(activeSemester));
    setApplyFetchedCreditDefault(true);
    setPaperModalOpen(true);
  }

  function openEditPaper(paper: PaperDraft) {
    const index = papers.indexOf(paper);
    setEditingPaperIndex(index);
    setPaperForm({ ...paper });
    setApplyFetchedCreditDefault(false);
    setPaperModalOpen(true);
  }

  function savePaperModal(event: FormEvent) {
    event.preventDefault();
    const validatedPaper: PaperDraft = {
      ...paperForm,
      semester: activeSemester,
      total_marks: String(
        (Number(paperForm.internal_marks) || 0) + (Number(paperForm.external_marks) || 0)
      ),
    };

    if (editingPaperIndex !== null && editingPaperIndex >= 0) {
      setPapers((current) =>
        current.map((item, idx) => (idx === editingPaperIndex ? validatedPaper : item))
      );
      setNotice(`Paper ${validatedPaper.paper_code} updated.`);
    } else {
      setPapers((current) => [...current, validatedPaper]);
      setNotice(`Paper ${validatedPaper.paper_code} added to Semester ${activeSemester}.`);
    }
    setPaperModalOpen(false);
  }

  function removePaper(paper: PaperDraft) {
    if (
      !window.confirm(
        `Are you sure you want to remove ${paper.paper_code || "this paper"} from Semester ${paper.semester}?`
      )
    )
      return;
    setPapers((current) => current.filter((p) => p !== paper));
    setNotice(`Paper removed.`);
  }

  function sortPapers() {
    setPapers((current) => {
      const otherSemesters = current.filter((p) => p.semester !== activeSemester);
      const sortedActive = [...activeSemesterPapers].sort((a, b) =>
        a.paper_code.localeCompare(b.paper_code)
      );
      return [...otherSemesters, ...sortedActive];
    });
    setNotice(`Semester ${activeSemester} papers sorted by paper code.`);
  }

  function populateSamplePapers() {
    setPapers((current) => {
      const otherSemesters = current.filter((p) => p.semester !== activeSemester);
      const generated = defaultSamplePapers.map((p, idx) => ({
        ...p,
        semester: activeSemester,
        paper_code: `BSC${activeSemester}0${idx + 1}`,
        id: undefined,
      }));
      return [...otherSemesters, ...generated];
    });
    setManageMenuOpen(false);
    setNotice(`Sample papers added to Semester ${activeSemester}.`);
  }

  function clearSemesterPapers() {
    if (
      !window.confirm(`Clear all papers in Semester ${activeSemester}?`)
    )
      return;
    setPapers((current) => current.filter((p) => p.semester !== activeSemester));
    setManageMenuOpen(false);
    setNotice(`All papers in Semester ${activeSemester} removed.`);
  }

  function handleModalCategoryChange(selectedCategory: string) {
    setPaperForm((prev) => ({
      ...prev,
      category: selectedCategory,
    }));
    setApplyFetchedCreditDefault(true);
  }

  async function autoFillCreditsFromTable() {
    setManageMenuOpen(false);
    if (!form.programme_id) {
      setError("Select a programme before fetching its Credit Table defaults.");
      return;
    }

    try {
      const activePapers = papers.filter((paper) => paper.semester === activeSemester);
      const categories = [...new Set(activePapers.map((paper) => paper.category))];
      const defaults = await Promise.all(
        categories.map(async (paperCategory) => {
          const { data } = await api.get<CourseCreditDefault>("/courses/credits/default", {
            params: {
              programme_id: form.programme_id,
              category: paperCategory,
              semester: activeSemester,
            },
          });
          return [paperCategory, data.default_credits] as const;
        }),
      );
      const creditsByCategory = new Map(defaults);
      let updatedCount = 0;
      const updated = papers.map((paper) => {
        const defaultCredits = creditsByCategory.get(paper.category);
        if (
          paper.semester !== activeSemester ||
          defaultCredits === null ||
          defaultCredits === undefined ||
          String(defaultCredits) === paper.credits
        ) {
          return paper;
        }
        updatedCount++;
        return { ...paper, credits: String(defaultCredits) };
      });
      setPapers(updated);
      setNotice(
        `Credits updated from the selected programme's Credit Table for Semester ${activeSemester} (${updatedCount} paper(s) updated).`,
      );
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  // Objectives handling
  function addObjective() {
    setForm((prev) => ({
      ...prev,
      objectives: [...prev.objectives, ""],
    }));
  }

  function updateObjective(index: number, val: string) {
    setForm((prev) => {
      const next = [...prev.objectives];
      next[index] = val;
      return { ...prev, objectives: next };
    });
  }

  function removeObjective(index: number) {
    setForm((prev) => ({
      ...prev,
      objectives: prev.objectives.filter((_, i) => i !== index),
    }));
  }

  function buildPreviewDetail(status: "draft" | "active" | "archived"): CourseLibraryDetail {
    const prog = selectedProgramme;
    const universityName = selectedUniversity?.name || "ABC University";
    const progName = prog ? prog.name : form.course_name;
    const durationYears = prog ? prog.duration_years : "3";

    const normalizedPapers = papers.map((paper, index) => ({
      ...paper,
      id: paper.id ?? `preview-${index}`,
      total_marks: String(
        (Number(paper.internal_marks) || 0) + (Number(paper.external_marks) || 0)
      ),
    }));

    return {
      programme_id: prog?.id || "preview-programme",
      course_name: form.course_name,
      course_code: form.course_code,
      university_id: form.university_id,
      university: universityName,
      programme: progName,
      course_level: form.course_level.toLowerCase(),
      duration_years: durationYears,
      total_semesters: semesterCount,
      total_papers: normalizedPapers.length,
      total_credits: String(totalCredits(papers)),
      status,
      configured: Boolean(form.course_code),
      faculty_school: form.faculty_school,
      department: form.department,
      description: form.description,
      regulation_year: form.regulation_year,
      academic_year: form.academic_year,
      effective_from: form.effective_from || null,
      effective_until: form.effective_until || null,
      semesters: Array.from({ length: semesterCount }, (_, index) => {
        const sem = index + 1;
        const semPapers = papers.filter((paper) => paper.semester === sem);
        return {
          semester: sem,
          total_papers: semPapers.length,
          total_credits: String(totalCredits(semPapers)),
        };
      }),
      papers: normalizedPapers,
    };
  }

  async function saveCourse(status: "draft" | "active") {
    // If no programme selected, attempt to find or prompt
    let progId = form.programme_id;
    if (!progId) {
      const match = programmes.find(
        (p) =>
          p.university_id === form.university_id ||
          p.name.toLowerCase() === form.course_name.toLowerCase()
      );
      if (match) {
        progId = match.id;
        setFormField("programme_id", match.id);
      } else if (programmes.length > 0) {
        progId = programmes[0].id;
        setFormField("programme_id", programmes[0].id);
      } else {
        setError("Please select or create a Programme before saving.");
        return;
      }
    }

    if (status === "active" && papers.length === 0) {
      setError("Add at least one paper before saving an active course.");
      return;
    }

    setSaving(true);
    setError("");
    setNotice("");

    try {
      const targetProg = programmes.find((p) => p.id === progId);
      const progAcademicYear = targetProg?.academic_year || form.academic_year;

      await api.put(`/courses/library/${progId}`, {
        course_name: form.course_name,
        course_code: form.course_code,
        faculty_school: form.faculty_school,
        department: form.department,
        description: form.description,
        regulation_year: form.regulation_year,
        academic_year: progAcademicYear,
        effective_from: form.effective_from || null,
        effective_until: form.effective_until || null,
        status,
        papers: papers.map((paper) => ({
          id: paper.id,
          semester: paper.semester,
          paper_code: paper.paper_code,
          paper_title: paper.paper_title,
          paper_type: paper.paper_type,
          category: paper.category,
          lecture_hours: Number(paper.lecture_hours) || 0,
          tutorial_hours: Number(paper.tutorial_hours) || 0,
          practical_hours: Number(paper.practical_hours) || 0,
          internal_marks: Number(paper.internal_marks) || 0,
          external_marks: Number(paper.external_marks) || 0,
          credits: Number(paper.credits) || 0,
        })),
      });

      setNotice(
        status === "draft"
          ? "Course saved as draft."
          : `Course "${form.course_name}" (${form.course_code}) saved successfully!`
      );
      await loadCatalogue();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setSaving(false);
    }
  }

  async function openPreview(row?: CourseCatalogueRow) {
    setError("");
    try {
      if (row) {
        const { data } = await api.get<CourseLibraryDetail>(`/courses/library/${row.programme_id}`);
        setPreview(data);
      } else {
        setPreview(buildPreviewDetail(form.status));
      }
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  async function deleteCourse(row: CourseCatalogueRow) {
    if (
      !window.confirm(
        `Archive ${row.course_code} — ${row.course_name}? Its papers and course data will be preserved.`
      )
    )
      return;
    setError("");
    setNotice("");
    try {
      await api.delete(`/courses/library/${row.programme_id}`);
      setNotice(`${row.course_code} archived.`);
      await loadCatalogue();
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  const inputClass =
    "w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-800 outline-none transition focus:border-[#164a9f] focus:ring-2 focus:ring-[#164a9f]/10";

  return (
    <PortalLayout role="admin">
      <div className="space-y-6">
        {/* Top Header */}
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-bold tracking-wider text-[#164a9f]">
              CURRICULUM MANAGEMENT
            </p>
            <h1 className="mt-0.5 text-2xl font-black text-[#102b5b]">Course Library</h1>
            <p className="mt-0.5 text-xs text-slate-500">
              Design, configure and structure university courses, semester papers, and credit schemes.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-xl bg-slate-100 p-1 text-xs font-semibold text-slate-600">
              <button
                type="button"
                onClick={() => setActiveTab("designer")}
                className={`rounded-lg px-3 py-1.5 transition ${
                  activeTab === "designer"
                    ? "bg-white text-[#164a9f] shadow-xs font-bold"
                    : "hover:text-slate-900"
                }`}
              >
                Course Designer
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("catalogue")}
                className={`rounded-lg px-3 py-1.5 transition ${
                  activeTab === "catalogue"
                    ? "bg-white text-[#164a9f] shadow-xs font-bold"
                    : "hover:text-slate-900"
                }`}
              >
                Catalogue ({catalogue.length})
              </button>
            </div>

            <button
              type="button"
              onClick={startCreate}
              className="inline-flex items-center gap-1.5 rounded-xl bg-[#164a9f] px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-[#103b83] transition"
            >
              <Plus size={15} />
              New Course
            </button>
          </div>
        </header>

        {/* Global Notices / Alerts */}
        {notice && (
          <div
            role="status"
            className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50/90 px-4 py-3 text-sm font-medium text-emerald-800"
          >
            <span>{notice}</span>
            <button
              type="button"
              onClick={() => setNotice("")}
              className="text-emerald-600 hover:text-emerald-900"
            >
              <X size={16} />
            </button>
          </div>
        )}
        {error && (
          <div
            role="alert"
            className="flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50/90 px-4 py-3 text-sm font-medium text-rose-800"
          >
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError("")}
              className="text-rose-600 hover:text-rose-900"
            >
              <X size={16} />
            </button>
          </div>
        )}

        {/* ===================== VIEW 1: COURSE DESIGNER (MATCHES USER IMAGE) ===================== */}
        {activeTab === "designer" && (
          <div className="space-y-6">
            {/* 5-Step Progress Stepper Bar */}
            <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs sm:p-5">
              <div className="flex items-center justify-between">
                {[
                  { num: 1, label: "Basic Information", target: "sec-basic", active: true },
                  { num: 2, label: "Academic Details", target: "sec-academic", active: false },
                  { num: 3, label: "Semester Structure", target: "sec-semester", active: false },
                  { num: 4, label: "Course Objectives", target: "sec-objectives", active: false },
                  { num: 5, label: "Review & Submit", target: "sec-actions", active: false },
                ].map((step, idx, arr) => (
                  <div key={step.num} className="flex flex-1 items-center">
                    <button
                      type="button"
                      onClick={() =>
                        document
                          .getElementById(step.target)
                          ?.scrollIntoView({ behavior: "smooth" })
                      }
                      className="group flex flex-col items-center gap-1.5 focus:outline-none"
                    >
                      <div
                        className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition ${
                          step.num === 1
                            ? "bg-[#103b83] text-white shadow-xs"
                            : "border-2 border-[#103b83] bg-white text-[#103b83] group-hover:bg-blue-50"
                        }`}
                      >
                        {step.num === 1 ? <Check size={14} className="stroke-[3]" /> : step.num}
                      </div>
                      <span className="text-[11px] font-semibold text-slate-700 group-hover:text-[#103b83]">
                        {step.num}. {step.label}
                      </span>
                    </button>
                    {idx < arr.length - 1 && (
                      <div className="mx-2 mb-4 h-0.5 flex-1 bg-slate-200" />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Upper Grid: Left 2 Cards + Right Course Summary Card */}
            <div className="grid gap-6 lg:grid-cols-12">
              {/* Left Column (8 cols): Section 1 and Section 2 */}
              <div className="space-y-6 lg:col-span-8 xl:col-span-8">
                {/* 1. Basic Information */}
                <section
                  id="sec-basic"
                  className="rounded-2xl border border-slate-200/90 bg-white p-5 shadow-xs"
                >
                  <div className="flex items-center gap-2">
                    <BookOpen size={18} className="text-[#103b83]" />
                    <h2 className="text-base font-bold text-[#102b5b]">1. Basic Information</h2>
                  </div>

                  <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {/* Course Name */}
                    <div>
                      <label className="text-xs font-semibold text-slate-700">
                        Course Name <span className="text-rose-500">*</span>
                      </label>
                      <input
                        required
                        type="text"
                        value={form.course_name}
                        onChange={(e) => setFormField("course_name", e.target.value)}
                        placeholder="e.g. B.Sc Computer Science"
                        className={`${inputClass} mt-1`}
                      />
                    </div>

                    {/* Course Code */}
                    <div>
                      <label className="text-xs font-semibold text-slate-700">
                        Course Code <span className="text-rose-500">*</span>
                      </label>
                      <input
                        required
                        type="text"
                        value={form.course_code}
                        onChange={(e) => setFormField("course_code", e.target.value.toUpperCase())}
                        placeholder="e.g. BSC-CS-001"
                        className={`${inputClass} mt-1 font-mono`}
                      />
                    </div>

                    {/* Course Level */}
                    <div>
                      <label className="text-xs font-semibold text-slate-700">
                        Course Level <span className="text-rose-500">*</span>
                      </label>
                      <div className="relative mt-1">
                        <select
                          value={form.course_level}
                          onChange={(e) => setFormField("course_level", e.target.value)}
                          className={`${inputClass} appearance-none pr-8 font-medium`}
                        >
                          <option value="UG">UG</option>
                          <option value="PG">PG</option>
                          <option value="Diploma">Diploma</option>
                          <option value="Certificate">Certificate</option>
                          <option value="Doctoral">Doctoral</option>
                          <option value="Other">Other</option>
                        </select>
                        <ChevronDown
                          size={15}
                          className="pointer-events-none absolute right-3 top-3.5 text-slate-400"
                        />
                      </div>
                    </div>

                    {/* University */}
                    <div>
                      <label className="text-xs font-semibold text-slate-700">
                        University <span className="text-rose-500">*</span>
                      </label>
                      <div className="relative mt-1">
                        <select
                          required
                          value={form.university_id}
                          onChange={(e) => handleUniversityChange(e.target.value)}
                          className={`${inputClass} appearance-none pr-8 font-medium`}
                        >
                          <option value="">Select University</option>
                          {activeUniversities.map((u) => (
                            <option key={u.id} value={u.id}>
                              {u.name}
                            </option>
                          ))}
                        </select>
                        <ChevronDown
                          size={15}
                          className="pointer-events-none absolute right-3 top-3.5 text-slate-400"
                        />
                      </div>
                    </div>

                    {/* Faculty / School */}
                    <div>
                      <label className="text-xs font-semibold text-slate-700">
                        Faculty / School <span className="text-rose-500">*</span>
                      </label>
                      <div className="relative mt-1">
                        <input
                          required
                          type="text"
                          list="faculty-options"
                          value={form.faculty_school}
                          onChange={(e) => setFormField("faculty_school", e.target.value)}
                          placeholder="e.g. School of Computing"
                          className={`${inputClass} pr-8`}
                        />
                        <ChevronDown
                          size={15}
                          className="pointer-events-none absolute right-3 top-3.5 text-slate-400"
                        />
                        <datalist id="faculty-options">
                          <option value="School of Computing" />
                          <option value="School of Engineering & Technology" />
                          <option value="School of Arts & Science" />
                          <option value="School of Management" />
                          <option value="Department of Information Technology" />
                        </datalist>
                      </div>
                    </div>

                    {/* Course Type */}
                    <div>
                      <label className="text-xs font-semibold text-slate-700">
                        Course Type <span className="text-rose-500">*</span>
                      </label>
                      <div className="relative mt-1">
                        <select
                          value={form.course_type}
                          onChange={(e) => setFormField("course_type", e.target.value)}
                          className={`${inputClass} appearance-none pr-8 font-medium`}
                        >
                          <option value="Regular">Regular</option>
                          <option value="Honors">Honors</option>
                          <option value="Self-Financed">Self-Financed</option>
                          <option value="Distance">Distance</option>
                          <option value="Online">Online</option>
                          <option value="Part-time">Part-time</option>
                        </select>
                        <ChevronDown
                          size={15}
                          className="pointer-events-none absolute right-3 top-3.5 text-slate-400"
                        />
                      </div>
                    </div>

                    {/* Department */}
                    <div>
                      <label className="text-xs font-semibold text-slate-700">
                        Department <span className="text-rose-500">*</span>
                      </label>
                      <input
                        required
                        type="text"
                        value={form.department}
                        onChange={(e) => setFormField("department", e.target.value)}
                        placeholder="e.g. Computer Science"
                        className={`${inputClass} mt-1`}
                      />
                    </div>

                    {/* Programme / Degree */}
                    <div>
                      <label className="text-xs font-semibold text-slate-700">
                        Programme / Degree <span className="text-rose-500">*</span>
                      </label>
                      <div className="relative mt-1">
                        <select
                          required
                          value={form.programme_id}
                          onChange={(e) => void selectProgramme(e.target.value)}
                          className={`${inputClass} appearance-none pr-8 font-medium`}
                        >
                          <option value="">Select Programme</option>
                          {availableProgrammes.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                        </select>
                        <ChevronDown
                          size={15}
                          className="pointer-events-none absolute right-3 top-3.5 text-slate-400"
                        />
                      </div>
                    </div>

                    {/* Programme Code */}
                    <div>
                      <label className="text-xs font-semibold text-slate-700">Programme Code</label>
                      <input
                        type="text"
                        value={form.programme_code}
                        onChange={(e) => setFormField("programme_code", e.target.value.toUpperCase())}
                        placeholder="e.g. BSC-CS"
                        className={`${inputClass} mt-1 font-mono`}
                      />
                    </div>
                  </div>
                </section>

                {/* 2. Academic Details */}
                <section
                  id="sec-academic"
                  className="rounded-2xl border border-slate-200/90 bg-white p-5 shadow-xs"
                >
                  <div className="flex items-center gap-2">
                    <Settings size={18} className="text-[#103b83]" />
                    <h2 className="text-base font-bold text-[#102b5b]">2. Academic Details</h2>
                  </div>

                  <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                    {/* Course Description */}
                    <div className="sm:col-span-2 lg:col-span-3 xl:col-span-2">
                      <label className="text-xs font-semibold text-slate-700">
                        Course Description <span className="text-rose-500">*</span>
                      </label>
                      <textarea
                        required
                        rows={2}
                        value={form.description}
                        onChange={(e) => setFormField("description", e.target.value)}
                        placeholder="Comprehensive course on computer science and programming."
                        className={`${inputClass} mt-1 resize-y`}
                      />
                    </div>

                    {/* Regulation / Syllabus Year */}
                    <div>
                      <label className="text-xs font-semibold text-slate-700">
                        Regulation / Syllabus Year <span className="text-rose-500">*</span>
                      </label>
                      <div className="relative mt-1">
                        <select
                          value={form.regulation_year}
                          onChange={(e) => setFormField("regulation_year", e.target.value)}
                          className={`${inputClass} appearance-none pr-8 font-medium`}
                        >
                          <option value="2026">2026</option>
                          <option value="2025">2025</option>
                          <option value="2024">2024</option>
                          <option value="2023">2023</option>
                          <option value="2022">2022</option>
                          <option value="2021">2021</option>
                        </select>
                        <ChevronDown
                          size={15}
                          className="pointer-events-none absolute right-3 top-3.5 text-slate-400"
                        />
                      </div>
                    </div>

                    {/* Academic Year */}
                    <div>
                      <label className="text-xs font-semibold text-slate-700">
                        Academic Year <span className="text-rose-500">*</span>
                      </label>
                      <div className="relative mt-1">
                        <input
                          type="text"
                          value={form.academic_year}
                          onChange={(e) => setFormField("academic_year", e.target.value)}
                          placeholder="2024-25"
                          className={`${inputClass} font-medium pr-8`}
                        />
                        <Calendar
                          size={15}
                          className="pointer-events-none absolute right-3 top-3.5 text-slate-400"
                        />
                      </div>
                    </div>

                    {/* Effective From */}
                    <div>
                      <label className="text-xs font-semibold text-slate-700">Effective From</label>
                      <div className="relative mt-1">
                        <input
                          type="date"
                          value={form.effective_from}
                          onChange={(e) => setFormField("effective_from", e.target.value)}
                          className={`${inputClass} font-medium pr-3`}
                        />
                      </div>
                    </div>

                    {/* Effective Until */}
                    <div>
                      <label className="text-xs font-semibold text-slate-700">Effective Until</label>
                      <div className="relative mt-1">
                        <input
                          type="date"
                          min={form.effective_from || undefined}
                          value={form.effective_until}
                          onChange={(e) => setFormField("effective_until", e.target.value)}
                          className={`${inputClass} font-medium pr-3`}
                        />
                      </div>
                    </div>

                    {/* Course Status */}
                    <div className="sm:col-span-2 lg:col-span-3 xl:col-span-1">
                      <label className="text-xs font-semibold text-slate-700">
                        Course Status <span className="text-rose-500">*</span>
                      </label>
                      <div className="relative mt-1">
                        <select
                          value={form.status}
                          onChange={(e) =>
                            setFormField(
                              "status",
                              e.target.value as "active" | "draft" | "archived"
                            )
                          }
                          className={`${inputClass} appearance-none pr-8 font-semibold ${
                            form.status === "active"
                              ? "text-emerald-700"
                              : form.status === "draft"
                              ? "text-amber-700"
                              : "text-slate-600"
                          }`}
                        >
                          <option value="active">● Active</option>
                          <option value="draft">○ Draft</option>
                          <option value="archived">✕ Archived</option>
                        </select>
                        <ChevronDown
                          size={15}
                          className="pointer-events-none absolute right-3 top-3.5 text-slate-400"
                        />
                      </div>
                    </div>
                  </div>
                </section>
              </div>

              {/* Right Column (4 cols): Course Summary Card */}
              <div className="lg:col-span-4 xl:col-span-4">
                <aside className="sticky top-6 rounded-2xl border border-blue-100 bg-[#f0f5ff] p-5 shadow-xs">
                  <div className="flex items-center gap-2 border-b border-blue-200/60 pb-3">
                    <GraduationCap size={20} className="text-[#103b83]" />
                    <h3 className="text-base font-bold text-[#102b5b]">Course Summary</h3>
                  </div>

                  <div className="mt-3 space-y-2.5 text-xs">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-semibold text-slate-600">Course Name</span>
                      <span className="max-w-[60%] text-right font-medium text-slate-900">
                        : {form.course_name || "—"}
                      </span>
                    </div>

                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-semibold text-slate-600">Course Code</span>
                      <span className="font-mono font-semibold text-slate-900">
                        : {form.course_code || "—"}
                      </span>
                    </div>

                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-semibold text-slate-600">University</span>
                      <span className="max-w-[60%] text-right font-medium text-slate-900">
                        : {selectedUniversity?.name || "ABC University"}
                      </span>
                    </div>

                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-semibold text-slate-600">Programme</span>
                      <span className="max-w-[60%] text-right font-medium text-slate-900">
                        : {selectedProgramme?.name || form.course_name || "—"}
                      </span>
                    </div>

                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-semibold text-slate-600">Duration</span>
                      <span className="font-medium text-slate-900">
                        : {selectedProgramme?.duration_years || Math.ceil(semesterCount / 2)} Years
                      </span>
                    </div>

                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-semibold text-slate-600">Total Semesters</span>
                      <span className="font-medium text-slate-900">: {semesterCount}</span>
                    </div>

                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-semibold text-slate-600">Total Papers</span>
                      <span className="font-medium text-slate-900">: {papers.length}</span>
                    </div>

                    <div className="flex items-baseline justify-between gap-2 border-t border-blue-200/80 pt-2.5">
                      <span className="text-sm font-bold text-slate-900">Total Credits</span>
                      <span className="text-base font-black text-[#103b83]">
                        : {totalCredits(papers)}
                      </span>
                    </div>
                  </div>
                </aside>
              </div>
            </div>

            {/* Section 3: 3. Semester Structure & Paper Details */}
            <section
              id="sec-semester"
              className="rounded-2xl border border-slate-200/90 bg-white p-5 shadow-xs"
            >
              {/* Header */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
                <div className="flex items-center gap-2">
                  <Layers size={18} className="text-[#103b83]" />
                  <h2 className="text-base font-bold text-[#102b5b]">
                    3. Semester Structure &amp; Paper Details
                  </h2>
                </div>

                <button
                  type="button"
                  onClick={() => void addSemester()}
                  disabled={saving || !form.programme_id || semesterCount >= 24}
                  title={semesterCount >= 24 ? "A programme cannot have more than 24 semesters." : undefined}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-[#103b83] px-3.5 py-2 text-xs font-bold text-white shadow-xs hover:bg-[#0c2f68] transition disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Plus size={15} />
                  Add Semester
                </button>
              </div>

              {/* Semester Body: Left vertical navigation tabs + Right table content */}
              <div className="mt-4 grid gap-5 lg:grid-cols-12">
                {/* Left Column: Vertical Semester Tabs */}
                <div className="lg:col-span-2">
                  <div className="space-y-1">
                    {Array.from({ length: semesterCount }, (_, index) => index + 1).map((sem) => {
                      const semPaperCount = papers.filter((p) => p.semester === sem).length;
                      const isActive = activeSemester === sem;
                      const canDelete = semesterCount > 1 && semPaperCount === 0;
                      return (
                        <div key={sem} className="group relative">
                          <button
                            type="button"
                            onClick={() => setActiveSemester(sem)}
                            className={`flex w-full items-center justify-between rounded-xl px-3.5 py-2.5 text-xs font-semibold transition pr-8 ${
                              isActive
                                ? "border-l-4 border-[#103b83] bg-[#eef4ff] text-[#103b83] font-bold shadow-xs"
                                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                            }`}
                          >
                            <span>Semester {sem}</span>
                            <span
                              className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                isActive
                                  ? "bg-[#103b83] text-white"
                                  : "bg-slate-100 text-slate-500"
                              }`}
                            >
                              {semPaperCount}
                            </span>
                          </button>
                          {/* Delete button — visible on hover */}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteSemester(sem);
                            }}
                            disabled={!canDelete}
                            title={
                              semesterCount <= 1
                                ? "Cannot delete the only semester"
                                : semPaperCount > 0
                                ? `Remove all ${semPaperCount} paper(s) first`
                                : `Delete Semester ${sem}`
                            }
                            className={`absolute right-1.5 top-1/2 -translate-y-1/2 rounded-lg p-1 opacity-0 transition-all group-hover:opacity-100 ${
                              canDelete
                                ? "text-rose-400 hover:bg-rose-50 hover:text-rose-600"
                                : "cursor-not-allowed text-slate-300"
                            }`}
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Right Column: Active Semester Banner, Table & Footer */}
                <div className="lg:col-span-10">
                  {/* Semester Sub-header Banner */}
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-t-xl bg-[#f5f8ff] px-4 py-3 border border-b-0 border-slate-200">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-[#102b5b]">
                        Semester {activeSemester} – {activeSemesterPapers.length} Papers
                      </span>
                      <span className="text-slate-300">|</span>
                      <span className="text-xs font-medium text-slate-600">Total Credits:</span>
                      <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-extrabold text-[#103b83]">
                        {activeSemesterCredits}
                      </span>
                    </div>

                    <div className="relative flex items-center gap-2">
                      <button
                        type="button"
                        onClick={sortPapers}
                        title="Sort papers in this semester by code"
                        className="rounded-lg p-1.5 text-slate-500 hover:bg-white hover:text-slate-800 transition"
                      >
                        <ArrowUpDown size={15} />
                      </button>

                      {/* Manage Papers Dropdown Menu */}
                      <div className="relative" ref={manageMenuRef}>
                        <button
                          type="button"
                          onClick={() => setManageMenuOpen(!manageMenuOpen)}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          <Settings size={13} className="text-[#103b83]" />
                          Manage Papers
                        </button>

                        {manageMenuOpen && (
                          <div className="absolute right-0 top-full z-20 mt-1.5 w-60 rounded-xl border border-slate-200 bg-white p-1.5 shadow-lg">
                            <button
                              type="button"
                              onClick={autoFillCreditsFromTable}
                              className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-slate-700 hover:bg-slate-100"
                            >
                              <Sparkles size={14} className="text-blue-600" />
                              Auto-fill from Credit Table
                            </button>
                            <button
                              type="button"
                              onClick={populateSamplePapers}
                              className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-slate-700 hover:bg-slate-100"
                            >
                              <Plus size={14} className="text-emerald-600" />
                              Add 5 Standard Papers
                            </button>
                            <button
                              type="button"
                              onClick={clearSemesterPapers}
                              className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-rose-600 hover:bg-rose-50"
                            >
                              <RotateCcw size={14} />
                              Clear Semester Papers
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Credit Table Sem-wise Distribution Reference Banner */}
                  <div className="flex flex-wrap items-center gap-1.5 border-x border-slate-200 bg-[#f8faff] px-4 py-2 text-[11px] text-slate-700">
                    <span className="flex items-center gap-1 font-bold text-[#103b83]">
                      <Sparkles size={12} className="text-[#103b83]" />
                      Credit Table Sem {activeSemester} Rules:
                    </span>
                    {SEMESTER_DISTRIBUTION_RULES.filter(
                      (r) => (r.papers[activeSemester - 1] ?? 0) > 0
                    ).map((r) => {
                      const pCount = r.papers[activeSemester - 1];
                      const totCred = pCount * r.creditsPerPaper;
                      return (
                        <span
                          key={r.category}
                          className="rounded-md border border-blue-100 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-800 shadow-2xs"
                        >
                          <strong>{r.category}:</strong> {pCount} paper{pCount > 1 ? "s" : ""} = {totCred} pts ({r.creditsPerPaper} cr/paper)
                        </span>
                      );
                    })}
                  </div>

                  {/* Papers Table */}
                  <div className="overflow-x-auto border border-slate-200">
                    <table className="w-full min-w-[760px] text-left text-xs">
                      <thead className="bg-[#fcfdfe] text-[11px] font-bold uppercase tracking-wider text-slate-500 border-b border-slate-200">
                        <tr>
                          <th className="px-3 py-2.5 w-10 text-center">#</th>
                          <th className="px-3 py-2.5 font-semibold">Paper Code</th>
                          <th className="px-3 py-2.5 font-semibold">Paper Title</th>
                          <th className="px-3 py-2.5 font-semibold">Type</th>
                          <th className="px-3 py-2.5 font-semibold">Category</th>
                          <th className="px-3 py-2.5 font-semibold">L-T-P</th>
                          <th className="px-3 py-2.5 font-semibold">Credits</th>
                          <th className="px-3 py-2.5 font-semibold">IA Marks</th>
                          <th className="px-3 py-2.5 font-semibold">Ext. Marks</th>
                          <th className="px-3 py-2.5 font-semibold text-center">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 bg-white">
                        {activeSemesterPapers.map((paper, idx) => (
                          <tr key={`${paper.paper_code}-${idx}`} className="hover:bg-slate-50/80 transition">
                            <td className="px-3 py-3 text-center text-slate-400 font-medium">
                              {idx + 1}
                            </td>
                            <td className="px-3 py-3 font-mono font-bold text-slate-900">
                              {paper.paper_code}
                            </td>
                            <td className="px-3 py-3 font-medium text-slate-800">
                              {paper.paper_title}
                            </td>
                            <td className="px-3 py-3 text-slate-600 font-medium">
                              {paper.paper_type}
                            </td>
                            <td className="px-3 py-3 text-slate-600 font-medium">
                              {paper.category}
                            </td>
                            <td className="px-3 py-3 font-mono text-slate-700">
                              {paper.lecture_hours || "0"}-{paper.tutorial_hours || "0"}-
                              {paper.practical_hours || "0"}
                            </td>
                            <td className="px-3 py-3 font-bold text-[#103b83]">
                              {paper.credits}
                            </td>
                            <td className="px-3 py-3 text-slate-700">{paper.internal_marks}</td>
                            <td className="px-3 py-3 text-slate-700">{paper.external_marks}</td>
                            <td className="px-3 py-3">
                              <div className="flex items-center justify-center gap-1.5">
                                <button
                                  type="button"
                                  title="Edit paper"
                                  onClick={() => openEditPaper(paper)}
                                  className="rounded-lg bg-blue-50/80 p-1.5 text-blue-600 hover:bg-blue-100 transition"
                                >
                                  <Pencil size={13} />
                                </button>
                                <button
                                  type="button"
                                  title="Delete paper"
                                  onClick={() => removePaper(paper)}
                                  className="rounded-lg bg-rose-50/80 p-1.5 text-rose-500 hover:bg-rose-100 transition"
                                >
                                  <Trash2 size={13} />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}

                        {activeSemesterPapers.length === 0 && (
                          <tr>
                            <td colSpan={10} className="px-4 py-8 text-center text-xs text-slate-400">
                              No papers added to Semester {activeSemester} yet. Click &ldquo;+ Add Paper&rdquo; to add your first paper.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>

                  {/* Table Footer: + Add Paper Button and Semester Total Credits Badge */}
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-b-xl border border-t-0 border-slate-200 bg-[#f9fbff] p-3">
                    <button
                      type="button"
                      onClick={openAddPaper}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-[#103b83] px-3.5 py-2 text-xs font-bold text-white shadow-xs hover:bg-[#0c2f68] transition"
                    >
                      <Plus size={15} />
                      Add Paper
                    </button>

                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
                      <span>Semester Total Credits:</span>
                      <span className="rounded-full bg-blue-100 px-3 py-1 font-black text-[#103b83]">
                        {activeSemesterCredits}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* Section 4: Course Objectives & Outcomes */}
            <section
              id="sec-objectives"
              className="rounded-2xl border border-slate-200/90 bg-white p-5 shadow-xs"
            >
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2">
                  <FileText size={18} className="text-[#103b83]" />
                  <h2 className="text-base font-bold text-[#102b5b]">4. Course Objectives</h2>
                </div>
                <button
                  type="button"
                  onClick={addObjective}
                  className="inline-flex items-center gap-1 rounded-lg border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-[#103b83] hover:bg-blue-100"
                >
                  <Plus size={13} /> Add Objective
                </button>
              </div>

              <div className="mt-3 space-y-2">
                {form.objectives.map((obj, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-blue-50 text-[10px] font-bold text-[#103b83]">
                      {i + 1}
                    </span>
                    <input
                      type="text"
                      value={obj}
                      onChange={(e) => updateObjective(i, e.target.value)}
                      placeholder={`Course objective ${i + 1}`}
                      className={`${inputClass} !py-1.5 text-xs`}
                    />
                    <button
                      type="button"
                      onClick={() => removeObjective(i)}
                      className="p-1 text-slate-400 hover:text-rose-500"
                    >
                      <X size={15} />
                    </button>
                  </div>
                ))}
              </div>
            </section>

            {/* Bottom Actions Bar */}
            <div
              id="sec-actions"
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs"
            >
              <button
                type="button"
                onClick={() => setActiveTab("catalogue")}
                className="text-xs font-semibold text-slate-600 hover:text-slate-900"
              >
                ← Back to Catalogue
              </button>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => void saveCourse("draft")}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 px-4 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition"
                >
                  <Save size={14} />
                  {saving ? "Saving…" : "Save as Draft"}
                </button>
                <button
                  type="button"
                  onClick={() => void openPreview()}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-blue-200 bg-blue-50/70 px-4 py-2.5 text-xs font-bold text-[#103b83] hover:bg-blue-100/70 transition"
                >
                  <Eye size={14} />
                  Preview Course
                </button>
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => void saveCourse("active")}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-[#103b83] px-5 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-[#0c2f68] disabled:opacity-50 transition"
                >
                  <FileCheck2 size={15} />
                  {saving ? "Saving Course…" : "Save Course"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ===================== VIEW 2: COURSE CATALOGUE ===================== */}
        {activeTab === "catalogue" && (
          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-5">
              <div>
                <h2 className="text-base font-bold text-[#102b5b]">Course Catalogue</h2>
                <p className="mt-0.5 text-xs text-slate-500">
                  All active and configured university courses with semester paper totals.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <input
                  aria-label="Search courses"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search course, code, university…"
                  className="w-60 rounded-xl border border-slate-300 px-3 py-1.5 text-xs outline-none focus:border-[#164a9f]"
                />
                <select
                  aria-label="Filter course status"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium"
                >
                  <option value="">Active &amp; drafts</option>
                  <option value="active">Active</option>
                  <option value="draft">Draft</option>
                  <option value="archived">Archived</option>
                </select>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-left text-xs">
                <thead className="bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500 border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-3">Course Name</th>
                    <th className="px-4 py-3">Code</th>
                    <th className="px-4 py-3">University</th>
                    <th className="px-4 py-3">Programme</th>
                    <th className="px-4 py-3">Duration</th>
                    <th className="px-4 py-3">Semesters</th>
                    <th className="px-4 py-3">Papers</th>
                    <th className="px-4 py-3">Credits</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {catalogue.map((row) => (
                    <tr key={row.programme_id} className="hover:bg-slate-50/80 transition">
                      <td className="px-4 py-3 font-bold text-slate-900">{row.course_name}</td>
                      <td className="px-4 py-3 font-mono font-semibold text-slate-700">
                        {row.course_code}
                      </td>
                      <td className="px-4 py-3 text-slate-600">{row.university}</td>
                      <td className="px-4 py-3 text-slate-600">{row.programme}</td>
                      <td className="px-4 py-3 text-slate-600">{row.duration_years} Years</td>
                      <td className="px-4 py-3 text-slate-600">{row.total_semesters}</td>
                      <td className="px-4 py-3 text-slate-600">{row.total_papers}</td>
                      <td className="px-4 py-3 font-bold text-[#103b83]">
                        {Number(row.total_credits).toFixed(2)}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                            row.status === "active"
                              ? "bg-emerald-100 text-emerald-800"
                              : row.status === "archived"
                              ? "bg-slate-100 text-slate-600"
                              : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {row.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-center gap-1">
                          <button
                            type="button"
                            onClick={() => void openPreview(row)}
                            title="Preview course"
                            className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-50"
                          >
                            <Eye size={13} />
                          </button>
                          <button
                            type="button"
                            onClick={() => void startEdit(row)}
                            title="Edit course in Designer"
                            className="rounded-lg border border-blue-200 bg-blue-50/50 p-1.5 text-[#103b83] hover:bg-blue-100/50"
                          >
                            <Pencil size={13} />
                          </button>
                          {row.status !== "archived" && (
                            <button
                              type="button"
                              onClick={() => void deleteCourse(row)}
                              title="Archive course"
                              className="rounded-lg border border-rose-100 bg-rose-50/50 p-1.5 text-rose-600 hover:bg-rose-100/50"
                            >
                              <Trash2 size={13} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}

                  {catalogue.length === 0 && (
                    <tr>
                      <td colSpan={10} className="px-5 py-12 text-center text-xs text-slate-400">
                        {loading
                          ? "Loading course catalogue…"
                          : "No courses found. Use 'Course Designer' to create your first course."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* ===================== MODAL: ADD / EDIT PAPER ===================== */}
        {paperModalOpen && (
          <div
            role="dialog"
            aria-modal="true"
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-xs"
          >
            <div className="w-full max-w-lg rounded-2xl bg-white p-5 shadow-2xl">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h3 className="text-base font-bold text-[#102b5b]">
                  {editingPaperIndex !== null
                    ? `Edit Paper: ${paperForm.paper_code}`
                    : `Add Paper to Semester ${activeSemester}`}
                </h3>
                <button
                  type="button"
                  onClick={() => setPaperModalOpen(false)}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
                >
                  <X size={16} />
                </button>
              </div>

              <form onSubmit={savePaperModal} className="mt-4 space-y-3.5 text-xs">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="font-semibold text-slate-700">
                      Paper Code <span className="text-rose-500">*</span>
                    </label>
                    <input
                      required
                      type="text"
                      value={paperForm.paper_code}
                      onChange={(e) =>
                        setPaperForm((p) => ({ ...p, paper_code: e.target.value.toUpperCase() }))
                      }
                      placeholder="e.g. BSC101"
                      className={`${inputClass} !py-2 font-mono`}
                    />
                  </div>

                  <div>
                    <label className="font-semibold text-slate-700">
                      Paper Title <span className="text-rose-500">*</span>
                    </label>
                    <input
                      required
                      type="text"
                      value={paperForm.paper_title}
                      onChange={(e) =>
                        setPaperForm((p) => ({ ...p, paper_title: e.target.value }))
                      }
                      placeholder="e.g. Programming in C"
                      className={`${inputClass} !py-2`}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="font-semibold text-slate-700">Paper Type</label>
                    <select
                      value={paperForm.paper_type}
                      onChange={(e) =>
                        setPaperForm((p) => ({ ...p, paper_type: e.target.value }))
                      }
                      className={`${inputClass} !py-2`}
                    >
                      <option value="Core">Core</option>
                      <option value="Elective">Elective</option>
                      <option value="Theory">Theory</option>
                      <option value="Practical">Practical</option>
                      <option value="Project">Project</option>
                      <option value="Seminar">Seminar</option>
                      <option value="Internship">Internship</option>
                    </select>
                  </div>

                  <div>
                    <label className="font-semibold text-slate-700">
                      Category <span className="text-rose-500">*</span>
                      <span className="ml-1 text-[10px] font-normal text-[#103b83]">
                        (From Credit Table)
                      </span>
                    </label>
                    <div className="relative mt-1">
                      <select
                        required
                        value={paperForm.category}
                        onChange={(e) => handleModalCategoryChange(e.target.value)}
                        className={`${inputClass} !py-2 font-medium appearance-none pr-8`}
                      >
                        <option value="">Select Category</option>
                        {SEMESTER_DISTRIBUTION_RULES.map((rule) => (
                          <option key={rule.category} value={rule.category}>
                            {rule.category}
                          </option>
                        ))}
                      </select>
                      <ChevronDown
                        size={14}
                        className="pointer-events-none absolute right-3 top-3 text-slate-400"
                      />
                    </div>
                  </div>
                </div>

                {/* Credit Table Rule Information Card */}
                <div className="rounded-xl border border-blue-200 bg-[#f0f5ff] p-3 text-xs text-[#102b5b]">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 font-bold">
                      <Sparkles size={14} className="text-[#103b83]" />
                      <span>Credit Table Rule (Semester {activeSemester}):</span>
                    </div>
                    <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-[10px] font-black text-[#103b83]">
                      {creditDefaultLoading
                        ? "Loading Credit Table…"
                        : creditDefault?.default_credits !== null && creditDefault?.default_credits !== undefined
                        ? `${creditDefault.default_credits} Credits / Paper`
                        : "No fixed credit value"}
                    </span>
                  </div>
                  <p className="mt-1.5 text-[11px] text-slate-600 leading-relaxed">
                    {activeModalCreditRule.paperCountInSem > 0 ? (
                      <>
                        In Semester {activeSemester}, <strong>{activeModalCreditRule.categoryDisplay}</strong> allocates{" "}
                        <strong>{activeModalCreditRule.paperCountInSem} paper{activeModalCreditRule.paperCountInSem > 1 ? "s" : ""}</strong> with{" "}
                        <strong>
                          {creditDefault?.default_credits !== null && creditDefault?.default_credits !== undefined
                            ? Number(creditDefault.default_credits) * activeModalCreditRule.paperCountInSem
                            : "—"} total credit points
                        </strong>{" "}
                        in the Credit Table.
                        <span className="block mt-0.5 font-semibold text-[#103b83]">
                          → Distributed as exactly{" "}
                          <strong>{creditDefault?.default_credits ?? "—"} credit points per paper</strong>.
                        </span>
                      </>
                    ) : (
                      <>
                        Category <strong>{activeModalCreditRule.categoryDisplay}</strong> has no papers allocated in Semester {activeSemester} in the Credit Table.{" "}
                        {creditDefault?.default_credits !== null && creditDefault?.default_credits !== undefined
                          ? <>Its matching value is <strong>{creditDefault.default_credits} credits</strong>.</>
                          : "No fixed credit value is configured; enter the approved value."}
                      </>
                    )}
                    {creditDefault?.source && (
                      <span className="mt-1 block text-slate-500">Source: {creditDefault.source}</span>
                    )}
                  </p>
                </div>

                {/* L-T-P Hours */}
                <div>
                  <label className="font-semibold text-slate-700">L - T - P Hours</label>
                  <div className="mt-1 grid grid-cols-3 gap-2">
                    <div>
                      <span className="text-[10px] text-slate-500">Lecture (L)</span>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={paperForm.lecture_hours}
                        onChange={(e) =>
                          setPaperForm((p) => ({ ...p, lecture_hours: e.target.value }))
                        }
                        className={`${inputClass} !py-1.5 font-mono text-center`}
                      />
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500">Tutorial (T)</span>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={paperForm.tutorial_hours}
                        onChange={(e) =>
                          setPaperForm((p) => ({ ...p, tutorial_hours: e.target.value }))
                        }
                        className={`${inputClass} !py-1.5 font-mono text-center`}
                      />
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500">Practical (P)</span>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={paperForm.practical_hours}
                        onChange={(e) =>
                          setPaperForm((p) => ({ ...p, practical_hours: e.target.value }))
                        }
                        className={`${inputClass} !py-1.5 font-mono text-center`}
                      />
                    </div>
                  </div>
                </div>

                {/* Credits & Marks */}
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="font-semibold text-slate-700">
                      Credits <span className="text-rose-500">*</span>
                      <span className="ml-1 text-[10px] font-normal text-emerald-700">
                        (Auto-set)
                      </span>
                    </label>
                    <input
                      required
                      type="number"
                      min="0"
                      max="100"
                      step="0.5"
                      value={paperForm.credits}
                      onChange={(e) =>
                        setPaperForm((p) => ({ ...p, credits: e.target.value }))
                      }
                      className={`${inputClass} !py-2 font-bold text-[#103b83] bg-blue-50/20`}
                    />
                  </div>

                  <div>
                    <label className="font-semibold text-slate-700">IA Marks</label>
                    <input
                      type="number"
                      min="0"
                      max="1000"
                      value={paperForm.internal_marks}
                      onChange={(e) =>
                        setPaperForm((p) => ({ ...p, internal_marks: e.target.value }))
                      }
                      className={`${inputClass} !py-2`}
                    />
                  </div>

                  <div>
                    <label className="font-semibold text-slate-700">Ext. Marks</label>
                    <input
                      type="number"
                      min="0"
                      max="1000"
                      value={paperForm.external_marks}
                      onChange={(e) =>
                        setPaperForm((p) => ({ ...p, external_marks: e.target.value }))
                      }
                      className={`${inputClass} !py-2`}
                    />
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => setPaperModalOpen(false)}
                    className="rounded-xl border border-slate-300 px-4 py-2 font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="rounded-xl bg-[#103b83] px-4 py-2 font-bold text-white hover:bg-[#0c2f68]"
                  >
                    {editingPaperIndex !== null ? "Update Paper" : "Save Paper"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ===================== MODAL: PREVIEW COURSE ===================== */}
        {preview && (
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Course preview"
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-xs"
          >
            <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
              <div className="sticky top-0 z-10 flex items-start justify-between border-b border-slate-100 bg-white px-6 py-4">
                <div>
                  <p className="text-xs font-bold tracking-wide text-[#164a9f]">COURSE PREVIEW</p>
                  <h2 className="mt-0.5 text-xl font-bold text-[#102b5b]">
                    {preview.course_name} ({preview.course_code})
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={() => setPreview(null)}
                  className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="space-y-5 p-6">
                <dl className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4 rounded-xl bg-slate-50 p-4">
                  <div>
                    <dt className="text-slate-500">University</dt>
                    <dd className="font-semibold text-slate-900">{preview.university}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Programme / Degree</dt>
                    <dd className="font-semibold text-slate-900">{preview.programme}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Level &amp; Duration</dt>
                    <dd className="font-semibold text-slate-900">
                      {preview.course_level.toUpperCase()} · {preview.duration_years} Years
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Academic Year / Regulation</dt>
                    <dd className="font-semibold text-slate-900">
                      {preview.academic_year} · {preview.regulation_year || "—"}
                    </dd>
                  </div>
                  <div className="sm:col-span-2 lg:col-span-4 border-t border-slate-200/60 pt-2">
                    <dt className="text-slate-500">Description</dt>
                    <dd className="font-medium text-slate-800">{preview.description || "—"}</dd>
                  </div>
                </dl>

                {/* Semesters list */}
                {preview.semesters.map((sem) => {
                  const semPapers = preview.papers.filter((p) => p.semester === sem.semester);
                  return (
                    <div
                      key={sem.semester}
                      className="overflow-hidden rounded-xl border border-slate-200"
                    >
                      <div className="flex justify-between bg-[#f5f8ff] px-4 py-2.5 text-xs font-bold text-[#102b5b]">
                        <span>
                          Semester {sem.semester} – {semPapers.length} papers
                        </span>
                        <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[#103b83]">
                          {Number(sem.total_credits).toFixed(2)} credits
                        </span>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-slate-50 text-[10px] uppercase text-slate-500 border-b border-slate-100">
                            <tr>
                              <th className="px-3 py-2">Code</th>
                              <th className="px-3 py-2">Title</th>
                              <th className="px-3 py-2">Type / Category</th>
                              <th className="px-3 py-2">L-T-P</th>
                              <th className="px-3 py-2">Marks</th>
                              <th className="px-3 py-2">Credits</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {semPapers.map((p) => (
                              <tr key={p.id ?? p.paper_code}>
                                <td className="px-3 py-2 font-mono font-bold">{p.paper_code}</td>
                                <td className="px-3 py-2 font-medium">{p.paper_title}</td>
                                <td className="px-3 py-2 text-slate-600">
                                  {p.paper_type} · {p.category}
                                </td>
                                <td className="px-3 py-2 font-mono">
                                  {p.lecture_hours}-{p.tutorial_hours}-{p.practical_hours}
                                </td>
                                <td className="px-3 py-2">
                                  {p.internal_marks} + {p.external_marks} = {p.total_marks}
                                </td>
                                <td className="px-3 py-2 font-bold text-[#103b83]">
                                  {p.credits}
                                </td>
                              </tr>
                            ))}
                            {semPapers.length === 0 && (
                              <tr>
                                <td colSpan={6} className="px-3 py-4 text-center text-slate-400">
                                  No papers in Semester {sem.semester}.
                                </td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </PortalLayout>
  );
}

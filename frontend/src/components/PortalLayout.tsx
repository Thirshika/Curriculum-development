import { useState } from "react";
import type { ReactNode } from "react";
import { BookOpenCheck, Building2, ChevronDown, CircleHelp, ClipboardCheck, FileStack, GraduationCap, Library, LogOut, Settings, ShieldCheck, Sparkles, UserRound, UsersRound, Workflow, ChartNoAxesCombined, History, Bell, MessageSquareText, UserCircle, WalletCards } from "lucide-react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import type { UserRole } from "../types";

export default function PortalLayout({ role, children }: { role: UserRole; children: ReactNode }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const isAdmin = role === "admin";
  const adminNavigation = [
    { to: "/admin", label: "Admin Dashboard", icon: ShieldCheck, end: true },
    { to: "/admin/universities", label: "University Management", icon: Building2, end: false },
    { to: "/admin/regulations", label: "Regulatory Knowledge Base", icon: FileStack, end: false },
    { to: "/admin/credit-table", label: "Credit Table", icon: WalletCards, end: false },
    { to: "/admin/courses", label: "Course Library", icon: Library, end: false },
    { to: "/admin/curricula/design", label: "Curriculum Designer", icon: GraduationCap, end: false },
    { to: "/admin/curricula/generate", label: "AI Syllabus Generator", icon: Sparkles, end: false },
    { to: "/admin/reviewers", label: "Reviewer Management", icon: UsersRound, end: false },
    { to: "/admin/reviews", label: "Approval Workflow", icon: Workflow, end: false },
    { to: "/admin/reports", label: "Reports & Exports", icon: ChartNoAxesCombined, end: false },
    { to: "/admin/curricula", label: "Version History", icon: History, end: false },
    { to: "/admin/settings", label: "System Settings", icon: Settings, end: false },
  ];
  const reviewerNavigation = [
    { to: "/reviewer", label: "Dashboard", icon: ShieldCheck, end: true },
    { to: "/reviewer/assigned", label: "Assigned Curricula", icon: Library, end: false },
    { to: "/reviewer/review", label: "Curriculum Review", icon: ClipboardCheck, end: false },
    { to: "/reviewer/comments", label: "Comments & Feedback", icon: MessageSquareText, end: false },
    { to: "/reviewer/history", label: "Review History", icon: History, end: false },
    { to: "/reviewer/notifications", label: "Notifications", icon: Bell, end: false },
    { to: "/reviewer/profile", label: "My Profile", icon: UserCircle, end: false },
  ];
  const navigation = isAdmin ? adminNavigation : reviewerNavigation;
  const currentLabel = navigation.find((item) => item.to === location.pathname)?.label
    ?? (!isAdmin && location.pathname.startsWith("/reviewer/assignments/") ? "Curriculum Review" : isAdmin ? "Admin" : "Reviewer Dashboard");
  const reviewerReviewRouteActive = !isAdmin && location.pathname.startsWith("/reviewer/assignments/");

  async function handleSignOut() {
    await signOut();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <aside className={`fixed inset-y-0 left-0 z-30 hidden w-[258px] flex-col border-r border-slate-200/80 bg-white lg:flex ${isAdmin ? "" : "border-t-4 border-t-teal-500"}`}>
        <div className="flex h-[76px] items-center gap-3 border-b border-slate-100 px-6">
          <div className={`grid h-10 w-10 place-items-center rounded-xl text-white ${isAdmin ? "bg-navy" : "bg-teal-700"}`}><BookOpenCheck size={21} /></div>
          <div>
            <p className="text-sm font-bold tracking-tight text-ink">Curriculum Hub</p>
            <p className="mt-0.5 text-[11px] font-medium uppercase tracking-[0.12em] text-slate-400">{isAdmin ? "Administration" : "University review"}</p>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pt-7">
          <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">Workspace</p>
          <nav className="space-y-1">{navigation.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold transition ${(isActive || (to === "/reviewer/review" && reviewerReviewRouteActive)) ? (isAdmin ? "bg-blue-50 text-navy" : "bg-teal-50 text-teal-800") : "text-slate-500 hover:bg-slate-50 hover:text-slate-800"}`}><Icon size={18} />{label}</NavLink>)}</nav>
        </div>
        <div className="mt-auto border-t border-slate-100 p-4">
          <div className="flex items-start gap-3 rounded-xl bg-slate-50 p-3">
            <CircleHelp className="mt-0.5 shrink-0 text-slate-400" size={17} />
            <div><p className="text-xs font-semibold text-slate-700">Need assistance?</p><p className="mt-1 text-[11px] leading-relaxed text-slate-500">Contact your platform administrator for account support.</p></div>
          </div>
        </div>
      </aside>
      <div className="lg:pl-[258px]">
        <header className="sticky top-0 z-20 flex h-[76px] items-center justify-between border-b border-slate-200/80 bg-white/95 px-5 backdrop-blur md:px-8">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 lg:hidden"><BookOpenCheck size={19} className={isAdmin ? "text-navy" : "text-teal-700"} /><span className="text-sm font-bold text-ink">Curriculum Hub</span></div>
            <div className="hidden text-sm text-slate-400 lg:block">Workspace <span className="mx-2">/</span><span className="font-semibold text-slate-700">{currentLabel}</span></div>
          </div>
          <div className="relative">
            <button onClick={() => setMenuOpen(!menuOpen)} className="flex items-center gap-3 rounded-xl py-1.5 pl-2 pr-1 text-left hover:bg-slate-50">
              <span className={`grid h-9 w-9 place-items-center rounded-full text-sm font-bold ${isAdmin ? "bg-blue-100 text-navy" : "bg-teal-100 text-teal-800"}`}>{user?.full_name.slice(0, 1).toUpperCase()}</span>
              <span className="hidden sm:block"><span className="block text-xs font-semibold text-slate-800">{user?.full_name}</span><span className="mt-0.5 block text-[11px] capitalize text-slate-500">{isAdmin ? "Platform administrator" : user?.university_name ?? "University reviewer"}</span></span>
              <ChevronDown size={15} className="ml-1 text-slate-400" />
            </button>
            {menuOpen && <div className="absolute right-0 top-12 w-48 rounded-xl border border-slate-200 bg-white p-1.5 shadow-card">
              <div className="flex items-center gap-2 px-3 py-2 text-xs text-slate-500"><UserRound size={15} />{user?.email}</div>
              <button onClick={handleSignOut} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-rose-600 hover:bg-rose-50"><LogOut size={15} />Sign out</button>
            </div>}
          </div>
        </header>
        <nav aria-label={isAdmin ? "Admin navigation" : "Reviewer navigation"} className="flex gap-2 overflow-x-auto border-b border-slate-200 bg-white px-5 py-2.5 lg:hidden">{navigation.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold ${(isActive || (to === "/reviewer/review" && reviewerReviewRouteActive)) ? (isAdmin ? "bg-blue-50 text-navy" : "bg-teal-50 text-teal-800") : "text-slate-500 hover:bg-slate-50"}`}><Icon size={15} />{label}</NavLink>)}</nav>
        {menuOpen && <button className="fixed inset-0 z-10 cursor-default lg:hidden" aria-label="Close menu" onClick={() => setMenuOpen(false)} />}
        <main className="mx-auto max-w-[1440px] px-5 py-8 md:px-8 md:py-10">{children}</main>
      </div>
    </div>
  );
}

import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import AdminDashboard from "./pages/AdminDashboard";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import LoginPage from "./pages/LoginPage";
import ReviewerDashboard from "./pages/ReviewerDashboard";
import UniversitiesPage from "./pages/UniversitiesPage";
import ReviewersPage from "./pages/ReviewersPage";
import RegulationsPage from "./pages/RegulationsPage";
import ProgrammesPage from "./pages/ProgrammesPage";
import CurriculumGenerationPage from "./pages/CurriculumGenerationPage";
import CurriculaLibraryPage from "./pages/CurriculaLibraryPage";
import ReviewerReviewPage from "./pages/ReviewerReviewPage";
import AdminFeedbackPage from "./pages/AdminFeedbackPage";
import CollegesPage from "./pages/CollegesPage";
import CourseLibraryPage from "./pages/CourseLibraryPage";
import CurriculumDesignerPage from "./pages/CurriculumDesignerPage";
import ReportsPage from "./pages/ReportsPage";
import SystemSettingsPage from "./pages/SystemSettingsPage";
import ReviewerWorkspacePage from "./pages/ReviewerWorkspacePage";
import ReviewerSignupPage from "./pages/ReviewerSignupPage";

function HomeRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <div className="grid min-h-screen place-items-center text-sm text-slate-500">Loading your workspace…</div>;
  if (!user) return <Navigate to="/login/admin" replace />;
  if (user.must_change_password) return <Navigate to="/change-password" replace />;
  return <Navigate to={user.role === "admin" ? "/admin" : "/reviewer"} replace />;
}

export default function App() {
  return <Routes>
    <Route path="/login" element={<Navigate to="/login/admin" replace />} />
    <Route path="/login/admin" element={<LoginPage role="admin" />} />
    <Route path="/login/reviewer" element={<LoginPage role="reviewer" />} />
    <Route path="/reviewer/signup" element={<ReviewerSignupPage />} />
    <Route element={<ProtectedRoute allowPasswordChange />}>
      <Route path="/change-password" element={<ChangePasswordPage />} />
    </Route>
    <Route element={<ProtectedRoute role="admin" />}>
      <Route path="/admin" element={<AdminDashboard />} />
      <Route path="/admin/universities" element={<UniversitiesPage />} />
      <Route path="/admin/colleges" element={<CollegesPage />} />
      <Route path="/admin/rules" element={<ProgrammesPage />} />
      <Route path="/admin/validation" element={<ProgrammesPage />} />
      <Route path="/admin/reviewers" element={<ReviewersPage />} />
      <Route path="/admin/regulations" element={<RegulationsPage />} />
      <Route path="/admin/programmes" element={<ProgrammesPage />} />
      <Route path="/admin/curricula/generate" element={<CurriculumGenerationPage />} />
      <Route path="/admin/curricula/design" element={<CurriculumDesignerPage />} />
      <Route path="/admin/courses" element={<CourseLibraryPage />} />
      <Route path="/admin/curricula" element={<CurriculaLibraryPage />} />
      <Route path="/admin/reviews" element={<AdminFeedbackPage />} />
      <Route path="/admin/reports" element={<ReportsPage />} />
      <Route path="/admin/settings" element={<SystemSettingsPage />} />
    </Route>
    <Route element={<ProtectedRoute role="reviewer" />}>
      <Route path="/reviewer" element={<ReviewerDashboard />} />
      <Route path="/reviewer/assigned" element={<ReviewerWorkspacePage section="assigned" />} />
      <Route path="/reviewer/review" element={<ReviewerWorkspacePage section="review" />} />
      <Route path="/reviewer/comments" element={<ReviewerWorkspacePage section="comments" />} />
      <Route path="/reviewer/compliance" element={<ReviewerWorkspacePage section="compliance" />} />
      <Route path="/reviewer/history" element={<ReviewerWorkspacePage section="history" />} />
      <Route path="/reviewer/notifications" element={<ReviewerWorkspacePage section="notifications" />} />
      <Route path="/reviewer/profile" element={<ReviewerWorkspacePage section="profile" />} />
      <Route path="/reviewer/assignments/:assignmentId" element={<ReviewerReviewPage />} />
    </Route>
    <Route path="*" element={<HomeRedirect />} />
  </Routes>;
}

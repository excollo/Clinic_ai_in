import { lazy, Suspense, type ReactElement } from "react";
import { useAuthStore } from "@/lib/authStore";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

const LoginPage = lazy(() => import("@/pages/LoginPage"));
const ForgotPasswordPage = lazy(() => import("@/pages/ForgotPasswordPage"));
const SignupPage = lazy(() => import("@/pages/SignupPage"));
const WelcomeTourPage = lazy(() => import("@/pages/WelcomeTourPage"));
const ProtectedApp = lazy(() => import("./ProtectedApp"));

function ProtectedRoute({ children }: { children: ReactElement }) {
  const hasSession = useAuthStore((s) => Boolean(s.apiKey && s.doctorId)) || Boolean(localStorage.getItem("clinic_api_key") && localStorage.getItem("clinic_doctor_id"));
  return hasSession ? children : <Navigate to="/login" replace />;
}

function App() {
  const location = useLocation();
  const title = location.pathname === "/login" ? "Sign in · Clinic-AI India" : location.pathname === "/dashboard" ? "Dashboard · Clinic-AI India" : location.pathname.startsWith("/visits/") ? "Visit · Clinic-AI India" : "Clinic-AI India";
  useDocumentTitle(title);
  return (
    <div className="transition-opacity duration-200">
      <Suspense fallback={<div className="grid min-h-screen place-items-center"><div className="h-10 w-64 animate-pulse rounded-xl bg-slate-200" /></div>}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/welcome-tour" element={<WelcomeTourPage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <ProtectedApp />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </Suspense>
    </div>
  );
}

export default App;

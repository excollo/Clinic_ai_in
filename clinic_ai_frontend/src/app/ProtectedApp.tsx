import { lazy, Suspense } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { Route, Routes } from "react-router-dom";
import { queryClient } from "@/lib/queryClient";
import { ProtectedShell } from "@/components/ProtectedShell";

const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const RegisterPatientPage = lazy(() => import("@/pages/RegisterPatientPage"));
const PatientsPage = lazy(() => import("@/pages/PatientsPage"));
const ConsentPage = lazy(() => import("@/pages/ConsentPage"));
const PatientDeclinedConsentPage = lazy(() => import("@/pages/PatientDeclinedConsentPage"));
const WalkInConfirmationPage = lazy(() => import("@/pages/WalkInConfirmationPage"));
const ScheduleConfirmationPage = lazy(() => import("@/pages/ScheduleConfirmationPage"));
const PatientDetailPage = lazy(() => import("@/pages/PatientDetailPage"));
const AbhaScanSharePage = lazy(() => import("@/pages/AbhaScanSharePage"));
const VisitWorkspacePage = lazy(() => import("@/pages/VisitWorkspacePage"));
const WhatsAppSentConfirmationPage = lazy(() => import("@/pages/WhatsAppSentConfirmationPage"));
const MedicationSchedulePage = lazy(() => import("@/pages/MedicationSchedulePage"));
const CarePrepListPage = lazy(() => import("@/pages/CarePrepListPage"));
const IntakeWorkspacePage = lazy(() => import("@/pages/IntakeWorkspacePage"));
const CalendarPage = lazy(() => import("@/pages/CalendarPage"));
const LabInboxPage = lazy(() => import("@/pages/LabInboxPage"));
const LabResultDetailPage = lazy(() => import("@/pages/LabResultDetailPage"));
const NotificationsPage = lazy(() => import("@/pages/NotificationsPage"));
const SettingsPage = lazy(() => import("@/pages/SettingsPage"));

export default function ProtectedApp() {
  return (
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<div className="h-10 w-64 animate-pulse rounded-xl bg-slate-200" />}>
        <Routes>
          <Route path="/" element={<ProtectedShell />}>
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="register-patient" element={<RegisterPatientPage />} />
            <Route path="patients" element={<PatientsPage />} />
            <Route path="patients/:id" element={<PatientDetailPage />} />
            <Route path="consent/:visitId" element={<ConsentPage />} />
            <Route path="consent-declined" element={<PatientDeclinedConsentPage />} />
            <Route path="walk-in-confirmation" element={<WalkInConfirmationPage />} />
            <Route path="schedule-confirmation" element={<ScheduleConfirmationPage />} />
            <Route path="scan-share" element={<AbhaScanSharePage />} />
            <Route path="careprep" element={<CarePrepListPage />} />
            <Route path="careprep/:visitId" element={<IntakeWorkspacePage />} />
            <Route path="calendar" element={<CalendarPage />} />
            <Route path="lab-inbox" element={<LabInboxPage />} />
            <Route path="lab-inbox/:labId" element={<LabResultDetailPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="visits/:visitId" element={<VisitWorkspacePage />} />
            <Route path="visits/:visitId/recap-sent" element={<WhatsAppSentConfirmationPage />} />
            <Route path="visits/:visitId/medication-schedule" element={<MedicationSchedulePage />} />
          </Route>
        </Routes>
      </Suspense>
    </QueryClientProvider>
  );
}

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useAuthStore } from "@/lib/authStore";
import { fetchConsentText } from "@/lib/mocks/consent";
import { queueClinicalRecord, runSyncNow } from "@/lib/offline/sync";

export default function ConsentPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { visitId = "" } = useParams();
  const location = useLocation();
  const doctorId = useAuthStore((s) => s.doctorId ?? "doctor-opaque-001");
  const doctorName = useAuthStore((s) => s.doctorName ?? t("common.doctor"));
  const state = location.state as { patient_id?: string; patientName?: string; patientLanguage?: string; visitType?: "walk_in" | "scheduled" } | undefined;
  const [confirmed, setConfirmed] = useState(false);
  const language = state?.patientLanguage ?? t("registration.hindi");
  const consentQuery = useQuery({
    queryKey: ["consent-text", language],
    queryFn: () => fetchConsentText(language),
  });
  const timestamp = useMemo(() => new Date().toLocaleTimeString(), []);

  const captureConsent = async () => {
    const id = crypto.randomUUID();
    await queueClinicalRecord("consent", {
      id,
      patient_id: state?.patient_id ?? "pat_unknown",
      visit_id: visitId,
      doctor_id: doctorId,
      language,
      patient_confirmed: true,
      consent_text_version: "v1.2",
      payload: {
        patient_id: state?.patient_id,
        visit_id: visitId,
        doctor_id: doctorId,
        language,
        consent_text_version: "v1.2",
        patient_confirmed: true,
        timestamp: new Date().toISOString(),
      },
    });
    void runSyncNow();
    if (state?.visitType === "scheduled") navigate("/schedule-confirmation", { state });
    else navigate("/walk-in-confirmation", { state: { ...state, token_number: state?.token_number } });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <span className="rounded-full bg-indigo-100 px-3 py-1 text-xs text-indigo-700">{t("consent.pill")}</span>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs">{language}</span>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs">v1.2</span>
      </div>
      <h2 className="text-h2">{t("consent.title")}</h2>
      <p className="text-sm text-clinic-muted">{t("consent.subtitle")}</p>
      <div className="max-h-72 overflow-y-auto rounded-2xl border border-clinic-border bg-white p-4 whitespace-pre-line">{consentQuery.data ?? t("common.loading")}</div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded-xl bg-white p-3 border border-clinic-border"><p className="text-xs text-clinic-muted">{t("consent.patientName")}</p><p>{state?.patientName ?? t("common.unknown")}</p></div>
        <div className="rounded-xl bg-white p-3 border border-clinic-border"><p className="text-xs text-clinic-muted">{t("consent.recordedBy")}</p><p>{doctorName}</p></div>
      </div>
      <label className="flex items-center gap-2 rounded-xl border border-green-300 bg-green-50 p-3"><input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /> {t("consent.confirmedVerbally")} · {timestamp}</label>
      <div className="flex flex-wrap justify-between gap-2">
        <button className="rounded-xl border border-red-300 px-4 py-2 text-red-600">{t("consent.declined")}</button>
        <div className="flex gap-2">
          <button onClick={() => navigate(-1)} className="rounded-xl border border-clinic-border px-4 py-2">{t("common.back")}</button>
          <button disabled={!confirmed} onClick={() => void captureConsent()} className="rounded-xl bg-clinic-primary px-4 py-2 text-white disabled:opacity-50">{t("consent.capture")}</button>
        </div>
      </div>
    </div>
  );
}

import { CheckCircle2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";

export default function WalkInConfirmationPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const state = useLocation().state as { patientName?: string; token_number?: string; patientLanguage?: string } | undefined;
  return (
    <div className="grid place-items-center">
      <div className="clinic-card w-full max-w-xl p-8 text-center">
        <CheckCircle2 className="mx-auto h-10 w-10 text-green-600" />
        <p className="mt-2 text-sm text-clinic-muted">{t("confirmation.queueAdded")}</p>
        <p className="text-6xl font-bold text-clinic-primary">{state?.token_number ?? "OPD-13"}</p>
        <p className="mt-2 text-sm">{state?.patientName} · {state?.patientLanguage}</p>
        <div className="mt-5 flex justify-center gap-2">
          <button onClick={() => navigate("/patients")} className="rounded-xl border border-clinic-border px-4 py-2">{t("confirmation.addAnotherWalkIn")}</button>
          <button onClick={() => navigate("/dashboard")} className="rounded-xl bg-clinic-primary px-4 py-2 text-white">{t("confirmation.goToQueue")}</button>
        </div>
      </div>
    </div>
  );
}

import { CheckCircle2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { useVisitStore } from "@/lib/visitStore";

export default function WhatsAppSentConfirmationPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { visitId } = useParams();
  const visit = useVisitStore();
  return (
    <div className="grid place-items-center">
      <div className="clinic-card w-full max-w-xl p-8 text-center">
        <CheckCircle2 className="mx-auto h-16 w-16 text-green-600" />
        <h2 className="mt-3 text-2xl font-semibold">{t("whatsappConfirmation.title")}</h2>
        <p className="mt-1 text-sm text-clinic-muted">{t("whatsappConfirmation.recipientLine")}</p>
        <p className="mt-2 text-xs text-clinic-muted">{t("whatsappConfirmation.statusLine")}</p>
        <div className="mt-4 grid grid-cols-1 gap-2">
          <button onClick={() => navigate(`/visits/${visitId}/medication-schedule`)} className="rounded-xl border border-clinic-border px-4 py-2 text-left">{t("whatsappConfirmation.actionMedicationSchedule")}</button>
          <button onClick={() => navigate("/patients")} className="rounded-xl border border-clinic-border px-4 py-2 text-left">{t("whatsappConfirmation.actionScheduleFollowup")}</button>
          <button onClick={() => { visit.setStatus("done"); navigate("/patients"); }} className="rounded-xl bg-clinic-primary px-4 py-2 text-white">{t("whatsappConfirmation.actionCompleteVisit")}</button>
        </div>
      </div>
    </div>
  );
}

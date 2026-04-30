import { CheckCircle2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import { formatClinicDate, formatClinicTime } from "@/lib/format";

export default function ScheduleConfirmationPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const state = useLocation().state as { patientName?: string } | undefined;
  const when = new Date();
  return (
    <div className="grid place-items-center">
      <div className="clinic-card w-full max-w-xl p-8 text-center">
        <CheckCircle2 className="mx-auto h-10 w-10 text-green-600" />
        <h2 className="mt-2 text-xl font-semibold">{t("confirmation.appointmentConfirmed")}</h2>
        <p className="mt-1 text-sm text-clinic-muted">{formatClinicDate(when)} · {formatClinicTime(when)} · {state?.patientName}</p>
        <p className="mt-2 text-sm text-green-700">{t("confirmation.whatsappSent")}</p>
        <div className="mt-5 flex justify-center gap-2">
          <button onClick={() => navigate("/patients")} className="rounded-xl border border-clinic-border px-4 py-2">{t("confirmation.addAnotherAppointment")}</button>
          <button onClick={() => navigate("/dashboard")} className="rounded-xl bg-clinic-primary px-4 py-2 text-white">{t("confirmation.viewCalendar")}</button>
        </div>
      </div>
    </div>
  );
}

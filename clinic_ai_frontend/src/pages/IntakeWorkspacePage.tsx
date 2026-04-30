import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import { getCareprepByVisitId } from "@/lib/mocks/careprep";

export default function IntakeWorkspacePage() {
  const { t } = useTranslation();
  const { visitId = "" } = useParams();
  const navigate = useNavigate();
  const item = useMemo(() => getCareprepByVisitId(visitId), [visitId]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-h2">{item.patientName}</h2>
          <p className="text-sm text-clinic-muted">{item.token} · {item.visitType === "walk_in" ? t("visitWorkspace.walkIn") : t("visitWorkspace.scheduled")} · {item.language} · {formatDistanceToNow(new Date(item.registeredAt), { addSuffix: true })}</p>
        </div>
        <button onClick={() => navigate(`/visits/${item.visitId}`)} className="rounded-xl bg-clinic-primary px-4 py-2 text-white">Start consult {"->"}</button>
      </div>
      {item.hasRedFlag && (
        <div className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          <p className="font-semibold">{t("intake.redFlags")}</p>
          <p>{item.redFlags.join(", ")}. Suggested questions: pain duration, radiation, associated breathlessness.</p>
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="clinic-card p-4">
          <p className="mb-1 text-xs text-clinic-muted">{t("previsit.chiefComplaint")}</p>
          <p className="text-lg font-semibold">{item.chiefComplaint}</p>
          <p className="mt-3 text-sm"><span className="text-clinic-muted">History:</span> Hypertension, no known allergies.</p>
          <p className="text-sm"><span className="text-clinic-muted">Other relevant info:</span> Previous similar episode 6 months ago.</p>
        </div>
        <div className="clinic-card p-4">
          <p className="mb-2 text-xs text-clinic-muted">Intake Q&A · {item.language}</p>
          <div className="max-h-64 space-y-2 overflow-y-auto">
            {[
              ["When did symptoms start?", "Since yesterday evening."],
              ["Any fever?", "No fever."],
              ["Any known allergy?", "No known allergy."],
            ].map(([q, a]) => (
              <div key={q}>
                <p className="text-xs text-clinic-muted">{q}</p>
                <p className="text-sm font-medium">{a}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="clinic-card p-4">
        <p className="mb-2 text-xs text-clinic-muted">{t("previsit.uploadedImages")}</p>
        <div className="flex gap-2">
          {Array.from({ length: Math.max(1, item.imageCount) }).map((_, idx) => (
            <button key={idx} className="h-16 w-16 rounded-lg bg-slate-100" />
          ))}
        </div>
      </div>
    </div>
  );
}

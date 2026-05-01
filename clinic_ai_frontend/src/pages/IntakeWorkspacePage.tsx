import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchCareprepSessionByVisitId } from "@/lib/services/careprepService";

export default function IntakeWorkspacePage() {
  const { t } = useTranslation();
  const { visitId = "" } = useParams();
  const intakeQuery = useQuery({
    queryKey: ["careprep-session", visitId],
    enabled: Boolean(visitId),
    queryFn: () => fetchCareprepSessionByVisitId(visitId),
  });

  if (!intakeQuery.data) {
    return (
      <div className="rounded-xl border border-dashed border-clinic-border bg-white p-6 text-sm text-clinic-muted">
        {!intakeQuery.isLoading ? t("careprep.empty") : t("common.loading")}
      </div>
    );
  }

  const item = intakeQuery.data;
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-h2">Intake Session</h2>
        <p className="text-sm text-clinic-muted">Visit: {item.visitId} · Status: {item.intakeStatus}</p>
      </div>
      {item.illness && (
        <div className="clinic-card p-4">
          <p className="mb-1 text-xs text-clinic-muted">Chief complaint</p>
          <p className="text-lg font-semibold">{item.illness}</p>
        </div>
      )}
      <div className="clinic-card p-4">
        <p className="mb-2 text-xs text-clinic-muted">Intake Q&A</p>
        <div className="max-h-[70vh] space-y-3 overflow-y-auto">
          {item.questionAnswers.map((qa, idx) => (
            <div key={`${qa.question}-${idx}`} className="rounded-lg border border-clinic-border p-3">
              <p className="text-xs text-clinic-muted">{qa.topic || "question"}</p>
              <p className="text-sm font-medium">{qa.question}</p>
              <p className="mt-1 text-sm">{qa.answer}</p>
            </div>
          ))}
          {item.questionAnswers.length === 0 && (
            <p className="text-sm text-clinic-muted">No intake responses found.</p>
          )}
        </div>
      </div>
    </div>
  );
}

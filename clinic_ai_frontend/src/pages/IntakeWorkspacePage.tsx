import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { careprepDetailHasIntake, fetchCareprepSessionByVisitId } from "@/lib/services/careprepService";

export default function IntakeWorkspacePage() {
  const { t } = useTranslation();
  const { visitId = "" } = useParams();
  const intakeQuery = useQuery({
    queryKey: ["careprep-session", visitId],
    enabled: Boolean(visitId),
    queryFn: () => fetchCareprepSessionByVisitId(visitId),
  });

  if (intakeQuery.isError) {
    return (
      <div className="rounded-xl border border-dashed border-clinic-border bg-white p-6 text-sm text-red-600">
        {t("common.error")}
      </div>
    );
  }

  if (intakeQuery.isLoading || !intakeQuery.data) {
    return (
      <div className="rounded-xl border border-dashed border-clinic-border bg-white p-6 text-sm text-clinic-muted">
        {intakeQuery.isLoading ? t("common.loading") : t("careprep.empty")}
      </div>
    );
  }

  const item = intakeQuery.data;
  if (!careprepDetailHasIntake(item)) {
    return (
      <div className="rounded-xl border border-dashed border-clinic-border bg-white p-8 text-center">
        <h2 className="text-h3">{t("intake.noIntakeTitle")}</h2>
        <p className="mt-2 text-sm text-clinic-muted">{t("intake.noIntakeBody")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-h2">{t("intake.sessionTitle")}</h2>
        <p className="text-sm text-clinic-muted">
          {t("intake.visitMeta", { visitId: item.visitId, status: item.intakeStatus })}
        </p>
      </div>
      {item.illness && (
        <div className="clinic-card p-4">
          <p className="mb-1 text-xs text-clinic-muted">{t("intake.chiefComplaint")}</p>
          <p className="text-lg font-semibold">{item.illness}</p>
        </div>
      )}
      <div className="clinic-card p-4">
        <p className="mb-2 text-xs text-clinic-muted">{t("intake.qaHeading")}</p>
        <div className="max-h-[70vh] space-y-3 overflow-y-auto">
          {item.questionAnswers.map((qa, idx) => (
            <div key={`${qa.question}-${idx}`} className="rounded-lg border border-clinic-border p-3">
              <p className="text-xs text-clinic-muted">{qa.topic || t("intake.questionTopicFallback")}</p>
              <p className="text-sm font-medium">{qa.question}</p>
              <p className="mt-1 text-sm">{qa.answer}</p>
            </div>
          ))}
          {item.questionAnswers.length === 0 && (
            <p className="text-sm text-clinic-muted">{t("intake.noResponsesYet")}</p>
          )}
        </div>
      </div>
    </div>
  );
}

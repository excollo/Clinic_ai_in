import { Activity } from "lucide-react";
import { useTranslation } from "react-i18next";

export function ClinicLogo({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-3">
      <div className="grid h-10 w-10 place-items-center rounded-xl bg-clinic-primary text-white">
        <Activity className="h-5 w-5" />
      </div>
      {!compact && (
        <div>
          <p className="text-sm font-semibold text-clinic-ink">{t("brand.name")}</p>
        </div>
      )}
    </div>
  );
}

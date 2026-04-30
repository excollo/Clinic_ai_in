import { useTranslation } from "react-i18next";

export default function ProfileTab() {
  const { t } = useTranslation();
  return (
    <div className="space-y-3">
      <input className="w-full rounded-xl border border-clinic-border px-3 py-2" placeholder={t("settings.profileDoctorName")} />
      <input className="w-full rounded-xl border border-clinic-border px-3 py-2" placeholder={t("settings.profileSpecialty")} />
      <input className="w-full rounded-xl border border-clinic-border px-3 py-2" placeholder={t("settings.profileMobile")} />
      <input className="w-full rounded-xl border border-clinic-border px-3 py-2" placeholder={t("settings.profileEmail")} />
    </div>
  );
}

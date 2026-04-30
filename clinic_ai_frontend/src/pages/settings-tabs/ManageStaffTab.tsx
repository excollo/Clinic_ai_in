import { useState } from "react";
import { useTranslation } from "react-i18next";

type Staff = { n: string; r: string };

export default function ManageStaffTab() {
  const { t } = useTranslation();
  const [staff, setStaff] = useState<Staff[]>([{ n: t("settings.staffFrontDesk"), r: t("settings.staffReception") }, { n: t("settings.staffNurse"), r: t("settings.staffNurseRole") }]);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [mobile, setMobile] = useState("");
  const [role, setRole] = useState(t("settings.staffReception"));

  return (
    <div className="space-y-2">
      {staff.map((s) => (
        <div key={s.n} className="flex items-center justify-between rounded-xl border border-clinic-border bg-white p-3">
          <div>
            <p>{s.n}</p>
            <p className="text-xs text-clinic-muted">{s.r}</p>
          </div>
          <button
            className="rounded-lg border px-3 py-1 text-red-600"
            onClick={() => {
              if (window.confirm(t("settings.removeStaffConfirm"))) {
                setStaff((prev) => prev.filter((x) => x.n !== s.n));
              }
            }}
          >
            Remove
          </button>
        </div>
      ))}
      <button className="rounded-xl bg-clinic-primary px-4 py-2 text-white" onClick={() => setOpen(true)}>{t("settings.addStaff")}</button>
      {open && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-4">
            <h3 className="mb-3 font-semibold">{t("settings.addStaff")}</h3>
            <div className="space-y-2">
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("settings.name")} className="w-full rounded-xl border border-clinic-border px-3 py-2" />
              <input value={mobile} onChange={(e) => setMobile(e.target.value)} placeholder={t("settings.profileMobile")} className="w-full rounded-xl border border-clinic-border px-3 py-2" />
              <select value={role} onChange={(e) => setRole(e.target.value)} className="w-full rounded-xl border border-clinic-border px-3 py-2"><option>{t("settings.staffReception")}</option><option>{t("settings.staffNurseRole")}</option><option>{t("settings.staffAdmin")}</option></select>
            </div>
            <div className="mt-3 flex justify-end gap-2">
              <button className="rounded-xl border border-clinic-border px-3 py-2" onClick={() => setOpen(false)}>{t("common.cancel")}</button>
              <button
                className="rounded-xl bg-clinic-primary px-3 py-2 text-white"
                onClick={() => {
                  if (!name.trim()) return;
                  setStaff((prev) => [{ n: name.trim(), r: role }, ...prev]);
                  setOpen(false);
                  setName("");
                  setMobile("");
                }}
              >
                {t("settings.add")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

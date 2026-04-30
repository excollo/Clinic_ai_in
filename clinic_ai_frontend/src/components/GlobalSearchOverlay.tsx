import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

export function GlobalSearchOverlay({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const { t } = useTranslation();
  const navigate = useNavigate();
  useEffect(() => {
    if (open) setQuery("");
  }, [open]);
  const patients = useMemo(() => (query.trim() ? [{ id: "pat_rs", name: "ravi patel", mobile: "9876543210" }, { id: "pat_mv", name: "meera verma", mobile: "9898989898" }, { id: "pat_sg", name: "suresh gupta", mobile: "9123456780" }] : []), [query]);
  const visits = useMemo(() => (query.trim() ? [{ id: "vis_chest_001", diagnosis: "chest pain review" }, { id: "vis_fever_001", diagnosis: "fever follow-up" }] : []), [query]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] bg-black/50 p-4" onClick={onClose}>
      <div className="mx-auto mt-20 w-full max-w-2xl rounded-2xl bg-white p-4" onClick={(e) => e.stopPropagation()}>
        <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("search.placeholder")} className="w-full rounded-xl border border-clinic-border px-3 py-2" />
        <div className="mt-3 space-y-3">
          <div>
            <p className="text-xs text-clinic-muted">{t("search.patients")}</p>
            {patients.map((p) => <button key={p.id} className="block w-full rounded-lg px-2 py-2 text-left hover:bg-slate-50" onClick={() => { navigate(`/patients/${p.id}`); onClose(); }}>{p.name} · {p.mobile}</button>)}
          </div>
          <div>
            <p className="text-xs text-clinic-muted">{t("search.visits")}</p>
            {visits.map((v) => <button key={v.id} className="block w-full rounded-lg px-2 py-2 text-left hover:bg-slate-50" onClick={() => { navigate(`/visits/${v.id}`); onClose(); }}>{v.diagnosis}</button>)}
          </div>
        </div>
      </div>
    </div>
  );
}

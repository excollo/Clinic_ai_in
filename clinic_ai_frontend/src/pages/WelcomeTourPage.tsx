import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { AuthCard } from "@/features/auth/components";

export default function WelcomeTourPage() {
  const { t } = useTranslation();
  useDocumentTitle(`Welcome · ${t("common.brand")}`);
  const navigate = useNavigate();
  const [index, setIndex] = useState(0);
  const slides = [
    { title: t("tour.slide1Title"), desc: t("tour.slide1Desc") },
    { title: t("tour.slide2Title"), desc: t("tour.slide2Desc") },
    { title: t("tour.slide3Title"), desc: t("tour.slide3Desc") },
  ];
  return (
    <AuthCard title={t("auth.welcomeTour")}>
      <div className="rounded-xl bg-slate-50 p-5">
        <h3 className="text-lg font-semibold">{slides[index].title}</h3>
        <p className="text-sm text-clinic-muted">{slides[index].desc}</p>
      </div>
      <div className="mt-4 flex items-center justify-between">
        <button className="text-sm text-clinic-primary" onClick={() => navigate("/dashboard")}>{t("common.skip")}</button>
        <div className="flex gap-2">{slides.map((_, idx) => <span key={idx} className={`h-2 w-2 rounded-full ${idx === index ? "bg-clinic-primary" : "bg-slate-300"}`} />)}</div>
        {index < 2 ? (
          <button className="rounded-xl bg-clinic-primary px-4 py-2 text-white" onClick={() => setIndex(index + 1)}>{t("common.continue")}</button>
        ) : (
          <button className="rounded-xl bg-clinic-primary px-4 py-2 text-white" onClick={() => navigate("/dashboard")}>{t("auth.goToDashboard")}</button>
        )}
      </div>
    </AuthCard>
  );
}

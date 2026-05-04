import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Calendar, FileHeart, FlaskConical, LayoutDashboard, LogOut, QrCode, Settings, ShieldCheck, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/lib/authStore";
import { GlobalSearchOverlay } from "./GlobalSearchOverlay";
import { ShortcutHelpModal } from "./ShortcutHelpModal";
import { ClinicLogo } from "./ClinicLogo";

async function fetchUnsyncedCount() {
  const mod = await import("@/lib/offline/sync");
  return mod.getUnsyncedCount();
}

export function ProtectedShell() {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const location = useLocation();
  const navGroups = [
    {
      title: t("shell.practice"),
      items: [
        { label: t("shell.dashboard"), icon: LayoutDashboard, to: "/dashboard" },
        { label: t("shell.calendar"), icon: Calendar, to: "/calendar" },
        { label: t("shell.patients"), icon: Users, to: "/patients" },
        { label: t("shell.careprep"), icon: FileHeart, to: "/careprep" },
        { label: t("shell.labInbox"), icon: FlaskConical, to: "/lab-inbox" },
        { label: t("shell.scanShare"), icon: QrCode, to: "/scan-share" },
      ],
    },
    {
      title: t("shell.admin"),
      items: [
        { label: t("shell.settings"), icon: Settings, to: "/settings" },
        { label: t("shell.auditLog"), icon: ShieldCheck, to: "/settings?tab=audit-log" },
      ],
    },
  ];
  const navigate = useNavigate();
  const clear = useAuthStore((s) => s.clearSession);
  const doctorName = useAuthStore((s) => s.doctorName ?? t("common.doctor"));
  const [searchOpen, setSearchOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const unsynced = useQuery({ queryKey: ["unsynced"], queryFn: fetchUnsyncedCount, refetchInterval: 10_000 });
  const showGlobalTopbar = location.pathname === "/dashboard";

  useEffect(() => {
    let cleanup: undefined | (() => void);
    void import("@/lib/offline/sync").then((mod) => {
      mod.startOfflineSyncWorker();
      cleanup = mod.stopOfflineSyncWorker;
    });
    return () => cleanup?.();
  }, []);

  useEffect(() => {
    const handler = () => {
      console.info('[TOPBAR] invalidating ["unsynced"] query');
      void queryClient.invalidateQueries({ queryKey: ["unsynced"] });
    };
    window.addEventListener("offline-sync-updated", handler);
    return () => window.removeEventListener("offline-sync-updated", handler);
  }, [queryClient]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const cmd = e.metaKey || e.ctrlKey;
      if (cmd && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (cmd && e.key.toLowerCase() === "n") {
        e.preventDefault();
        navigate("/register-patient");
      }
      if (cmd && e.key === "/") {
        e.preventDefault();
        setShortcutsOpen(true);
      }
      if (e.key === "escape") {
        setSearchOpen(false);
        setShortcutsOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate]);

  useEffect(() => {
    console.info("[TOPBAR] unsynced count updated:", unsynced.data ?? 0);
  }, [unsynced.data]);

  return (
    <div className="flex min-h-screen bg-clinic-surface">
      <aside className="hidden w-60 bg-clinic-sidebar p-4 text-white lg:block">
        <ClinicLogo compact />
        <div className="mt-6">
          {navGroups.map((g) => (
            <div key={g.title} className="mb-6">
              <p className="mb-2 text-xs text-clinic-sidebarText">{g.title}</p>
              <div className="space-y-1">
                {g.items.map(({ label, icon: Icon, to }) => (
                  <NavLink key={label} to={to} className={({ isActive }) => `block w-full rounded-xl px-3 py-2 text-left text-sm ${isActive ? "bg-clinic-sidebarMuted text-white" : "text-clinic-sidebarText"}`}>
                    <Icon className="mr-2 inline h-4 w-4" /> {label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="absolute bottom-6 w-52 rounded-xl bg-clinic-sidebarMuted p-3 text-sm">
          <p>{doctorName}</p>
          <button onClick={() => { clear(); navigate("/login"); }} className="mt-2 text-xs text-clinic-sidebarText"><LogOut className="mr-1 inline h-3 w-3" /> {t("common.logout")}</button>
        </div>
      </aside>
      <main className="flex-1 p-4 md:p-6">
        {showGlobalTopbar && (
          <div className="mb-5 flex items-center justify-between">
            <h1 className="text-h2">{t("common.dashboard")}</h1>
            <div className="flex items-center gap-3">
              {(unsynced.data ?? 0) > 0 && <span className="rounded-lg bg-amber-100 px-2 py-1 text-xs text-amber-700">{t("topbar.unsyncedCount", { count: unsynced.data })}</span>}
              <button onClick={() => navigate("/notifications")} aria-label={t("common.notifications")} className="rounded-lg border border-clinic-border bg-white p-2"><Bell className="h-4 w-4" /></button>
            </div>
          </div>
        )}
        <Outlet />
      </main>
      <GlobalSearchOverlay open={searchOpen} onClose={() => setSearchOpen(false)} />
      <ShortcutHelpModal open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </div>
  );
}

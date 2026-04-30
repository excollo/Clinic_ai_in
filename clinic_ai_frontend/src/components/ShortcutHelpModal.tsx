import { useTranslation } from "react-i18next";

export function ShortcutHelpModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-black/50 p-4" onClick={onClose}>
      <div className="w-full max-w-lg rounded-2xl bg-white p-4" onClick={(e) => e.stopPropagation()}>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="font-semibold">{t("search.shortcutsTitle")}</h3>
          <button onClick={onClose} aria-label={t("search.closeShortcuts")}>X</button>
        </div>
        <table className="w-full text-sm">
          <tbody>
            <tr><td>{t("search.shortcutGlobalSearch")}</td><td>Ctrl/Cmd + K</td></tr>
            <tr><td>{t("search.shortcutRegister")}</td><td>Ctrl/Cmd + N</td></tr>
            <tr><td>{t("search.shortcutHelp")}</td><td>Ctrl/Cmd + /</td></tr>
            <tr><td>{t("search.shortcutClose")}</td><td>Esc</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

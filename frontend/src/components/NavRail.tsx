import { t } from "../i18n";
import { useStore, type Tab } from "../state/store";

const tabs = (): { key: Tab; label: string; ico: string }[] => [
  { key: "office", label: t("Office"), ico: "⌂" },
  { key: "dashboard", label: t("Money"), ico: "€" },
  { key: "staff", label: t("Staff"), ico: "☺" },
  { key: "lab", label: t("LAB"), ico: "⚗" },
  { key: "history", label: t("History"), ico: "≡" },
  { key: "ceo", label: t("CEO"), ico: "♛" },
  { key: "paper", label: t("Paper"), ico: "▤" },
  { key: "ai", label: t("AI log"), ico: "⌘" },
  { key: "saves", label: t("Saves"), ico: "▣" },
];

export function NavRail() {
  const tab = useStore((s) => s.tab);
  const setTab = useStore((s) => s.setTab);
  return (
    <nav className="rail" aria-label={t("Views")}>
      {tabs().map((item) => (
        <button key={item.key} className={tab === item.key ? "active" : ""} onClick={() => setTab(item.key)}>
          <span className="ico" aria-hidden>
            {item.ico}
          </span>
          {item.label}
        </button>
      ))}
    </nav>
  );
}

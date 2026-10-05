import { useStore, type Tab } from "../state/store";

const TABS: { key: Tab; label: string; ico: string }[] = [
  { key: "office", label: "Office", ico: "⌂" },
  { key: "dashboard", label: "Money", ico: "€" },
  { key: "staff", label: "Staff", ico: "☺" },
  { key: "lab", label: "LAB", ico: "⚗" },
  { key: "history", label: "History", ico: "≡" },
  { key: "ceo", label: "CEO", ico: "♛" },
  { key: "paper", label: "Paper", ico: "▤" },
  { key: "ai", label: "AI log", ico: "⌘" },
  { key: "saves", label: "Saves", ico: "▣" },
];

export function NavRail() {
  const tab = useStore((s) => s.tab);
  const setTab = useStore((s) => s.setTab);
  return (
    <nav className="rail" aria-label="Views">
      {TABS.map((t) => (
        <button key={t.key} className={tab === t.key ? "active" : ""} onClick={() => setTab(t.key)}>
          <span className="ico" aria-hidden>
            {t.ico}
          </span>
          {t.label}
        </button>
      ))}
    </nav>
  );
}

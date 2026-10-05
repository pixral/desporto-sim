import { create } from "zustand";
import { ES } from "./es";

/**
 * Translations. The English text is the key; `t("Run")` returns it in the current language and falls back to
 * English when a translation is missing. Placeholders look like {name}. When one English word needs two
 * translations, give it a context after "|": t("Close|price") shows "Close" in English and has its own entry.
 * Changing the language remounts the app (see App.tsx), so plain `t()` calls in helpers and canvases pick it up
 * without subscribing.
 */
export type Lang = "en" | "es";
export const LANGS: { key: Lang; label: string }[] = [
  { key: "en", label: "English" },
  { key: "es", label: "Español" },
];

const STORAGE_KEY = "desporto-lang";

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "es") return saved;
  } catch {
    /* private mode */
  }
  return typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("es") ? "es" : "en";
}

export const useLang = create<{ lang: Lang; setLang: (l: Lang) => void }>((set) => ({
  lang: initialLang(),
  setLang: (lang) => {
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      /* private mode */
    }
    document.documentElement.lang = lang;
    set({ lang });
  },
}));

export type Params = Record<string, string | number>;

export function translate(lang: Lang, text: string, params?: Params): string {
  const bar = text.indexOf("|");
  const english = bar >= 0 ? text.slice(0, bar) : text;
  let out = lang === "es" ? (ES[text] ?? english) : english;
  if (params) out = out.replace(/\{(\w+)\}/g, (m, k: string) => (k in params ? String(params[k]) : m));
  return out;
}

/** Translate into the current language. */
export function t(text: string, params?: Params): string {
  return translate(useLang.getState().lang, text, params);
}

export function currentLang(): Lang {
  return useLang.getState().lang;
}

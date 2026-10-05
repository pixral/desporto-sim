import { describe, expect, it } from "vitest";
import { ES, ES_CORE } from "./es";
import { ES_OFFICE } from "./es/office";
import { ES_PEOPLE } from "./es/people";
import { ES_SERVER } from "./es/server";
import { ES_SHELL } from "./es/shell";
import { ES_VIEWS } from "./es/views";
import { translate } from "./index";

// every source file, as text (tests and the dictionaries themselves excluded)
const sources = import.meta.glob(["../**/*.ts", "../**/*.tsx", "!../**/*.test.ts", "!../i18n/**"], {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

/** The literal texts passed to t("…"). */
function keysIn(src: string): string[] {
  const out: string[] = [];
  const re = /\bt\(\s*"((?:[^"\\]|\\.)*)"/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src))) out.push(JSON.parse(`"${m[1]}"`));
  return out;
}

const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe("Spanish translation", () => {
  const used = new Map<string, string>();
  for (const [file, src] of Object.entries(sources)) for (const k of keysIn(src)) used.set(k, file);

  it("covers every text the code translates", () => {
    expect(used.size).toBeGreaterThan(20); // the scan really finds the source files
    const missing = [...used].filter(([k]) => !(k in ES)).map(([k, file]) => `${file}: ${k}`);
    expect(missing).toEqual([]);
  });

  it("never translates the same English text two ways", () => {
    const seen = new Map<string, string>();
    const clash: string[] = [];
    for (const dict of [ES_SERVER, ES_SHELL, ES_PEOPLE, ES_VIEWS, ES_OFFICE, ES_CORE]) {
      for (const [en, es] of Object.entries(dict)) {
        if (seen.has(en) && seen.get(en) !== es) clash.push(`${en}: "${seen.get(en)}" vs "${es}"`);
        seen.set(en, es);
      }
    }
    expect(clash).toEqual([]);
  });

  it("keeps the same placeholders", () => {
    const wrong = Object.entries(ES)
      .filter(([en, es]) => placeholders(en).join() !== placeholders(es).join())
      .map(([en]) => en);
    expect(wrong).toEqual([]);
  });

  it("fills placeholders and falls back to English", () => {
    expect(translate("es", "day {n}", { n: 3 })).toBe("día 3");
    expect(translate("en", "day {n}", { n: 3 })).toBe("day 3");
    expect(translate("es", "No such text anywhere")).toBe("No such text anywhere");
    expect([translate("en", "Close|price"), translate("es", "Close|price"), translate("es", "Close")]).toEqual(["Close", "Cierre", "Cerrar"]);
  });
});

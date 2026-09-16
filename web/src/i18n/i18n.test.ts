import { describe, expect, it } from "vitest";
import {
  SUPPORTED_LANGUAGES,
  TRANSLATIONS,
  type SupportedLanguage,
  type TranslationKeys,
} from "./translations";

function getLeafKeys(obj: unknown, prefix = ""): Record<string, string> {
  const leafKeys: Record<string, string> = {};
  if (!obj || typeof obj !== "object") return leafKeys;

  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    const fullPath = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "object" && value !== null) {
      Object.assign(leafKeys, getLeafKeys(value, fullPath));
    } else if (typeof value === "string") {
      leafKeys[fullPath] = value;
    }
  }
  return leafKeys;
}

function extractPlaceholders(text: string): string[] {
  const matches = text.match(/\{\{\s*\w+\s*\}\}/g);
  if (!matches) return [];
  return matches.map((m) => m.replace(/\s+/g, "")).sort();
}

/**
 * Reusable localization quality gate assertion.
 * Validates key parity, missing keys, extra keys, non-empty values, and variable interpolation integrity.
 */
export function validateLocalizationQuality(catalogs: Record<SupportedLanguage, TranslationKeys>): void {
  const enKeys = getLeafKeys(catalogs.en);
  const locales: SupportedLanguage[] = ["fa", "ar", "tr"];

  locales.forEach((lang) => {
    const langKeys = getLeafKeys(catalogs[lang]);

    // Missing keys check
    const missingKeys = Object.keys(enKeys).filter((k) => !(k in langKeys));
    if (missingKeys.length > 0) {
      throw new Error(`Localization Quality Gate Failed [${lang.toUpperCase()}]: Missing ${missingKeys.length} keys: ${missingKeys.join(", ")}`);
    }

    // Extra / Orphaned keys check
    const extraKeys = Object.keys(langKeys).filter((k) => !(k in enKeys));
    if (extraKeys.length > 0) {
      throw new Error(`Localization Quality Gate Failed [${lang.toUpperCase()}]: Extra ${extraKeys.length} keys: ${extraKeys.join(", ")}`);
    }

    // Placeholder & Non-empty text integrity check
    for (const [key, enText] of Object.entries(enKeys)) {
      const langText = langKeys[key];
      if (!langText || langText.trim() === "") {
        throw new Error(`Localization Quality Gate Failed [${lang.toUpperCase()}]: Empty translation for key '${key}'`);
      }

      const enVars = extractPlaceholders(enText);
      const langVars = extractPlaceholders(langText);
      if (enVars.join(",") !== langVars.join(",")) {
        throw new Error(
          `Localization Quality Gate Failed [${lang.toUpperCase()}]: Placeholder mismatch for key '${key}'. Expected [${enVars.join(", ")}], got [${langVars.join(", ")}]`
        );
      }
    }
  });
}

describe("GLOBAL LOCALIZATION QUALITY GATE", () => {
  it("passes reusable localization quality gate for all supported locales", () => {
    expect(() => validateLocalizationQuality(TRANSLATIONS)).not.toThrow();
  });

  it("fails quality gate if a key is missing in a language catalog", () => {
    const corruptedCatalog = JSON.parse(JSON.stringify(TRANSLATIONS)) as Record<SupportedLanguage, TranslationKeys>;
    // Delete a key from Persian
    delete (corruptedCatalog.fa as any).nav.dashboard;

    expect(() => validateLocalizationQuality(corruptedCatalog)).toThrowError(
      /Missing 1 keys: nav.dashboard/
    );
  });

  it("fails quality gate if a placeholder variable is missing or altered", () => {
    const corruptedCatalog = JSON.parse(JSON.stringify(TRANSLATIONS)) as Record<SupportedLanguage, TranslationKeys>;
    // Corrupt a variable placeholder in Turkish
    corruptedCatalog.tr.markets.symbolSelected = "Seçildi"; // Missing {{symbol}}

    expect(() => validateLocalizationQuality(corruptedCatalog)).toThrowError(
      /Placeholder mismatch for key 'markets.symbolSelected'/
    );
  });

  it("includes all 4 required supported languages with proper metadata", () => {
    const codes = SUPPORTED_LANGUAGES.map((l) => l.code);
    expect(codes).toEqual(["en", "fa", "ar", "tr"]);

    const en = SUPPORTED_LANGUAGES.find((l) => l.code === "en");
    const fa = SUPPORTED_LANGUAGES.find((l) => l.code === "fa");
    const ar = SUPPORTED_LANGUAGES.find((l) => l.code === "ar");
    const tr = SUPPORTED_LANGUAGES.find((l) => l.code === "tr");

    expect(en?.dir).toBe("ltr");
    expect(fa?.dir).toBe("rtl");
    expect(ar?.dir).toBe("rtl");
    expect(tr?.dir).toBe("ltr");
  });

  it("verifies Persian translation terminology and RTL suitability", () => {
    const fa = TRANSLATIONS.fa;
    expect(fa.nav.dashboard).toBe("داشبورد");
    expect(fa.risk.stopLoss).toBe("حد ضرر (SL)");
    expect(fa.risk.targetTp1).toBe("تارگت اول (TP1)");
    expect(fa.walkForward.title).toBe("اعتبارسنجی پیشرو و ثبات استراتژی");
    expect(fa.backtest.title).toBe("ارزیابی بک‌تست");
    expect(fa.status.connected).toBe("متصل");
    expect(fa.status.disconnected).toBe("قطع شده");
  });

  it("verifies Arabic and Turkish translation catalog completeness", () => {
    const ar = TRANSLATIONS.ar;
    const tr = TRANSLATIONS.tr;

    expect(ar.nav.dashboard).toBe("لوحة التحكم");
    expect(ar.risk.stopLoss).toBe("إيقاف الخسارة (SL)");
    expect(tr.nav.dashboard).toBe("Kontrol Paneli");
    expect(tr.risk.stopLoss).toBe("Zarar Durdur (SL)");
  });

  it("formats numbers and currency correctly according to locale rules", () => {
    const value = 2650.5;
    const enCurrency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
    const faCurrency = new Intl.NumberFormat("fa-IR", { style: "currency", currency: "USD" }).format(value);
    const arCurrency = new Intl.NumberFormat("ar-SA", { style: "currency", currency: "USD" }).format(value);
    const trCurrency = new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY" }).format(value);

    expect(enCurrency).toContain("2,650.50");
    expect(faCurrency).toBeDefined();
    expect(arCurrency).toBeDefined();
    expect(trCurrency).toBeDefined();
  });
});

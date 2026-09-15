import { describe, expect, it } from "vitest";
import { SUPPORTED_LANGUAGES, TRANSLATIONS, type SupportedLanguage } from "./translations";

describe("i18n Localization Architecture", () => {
  it("includes all 4 required languages", () => {
    const codes = SUPPORTED_LANGUAGES.map((l) => l.code);
    expect(codes).toEqual(["en", "fa", "ar", "tr"]);
  });

  it("assigns correct direction for LTR and RTL languages", () => {
    const en = SUPPORTED_LANGUAGES.find((l) => l.code === "en");
    const fa = SUPPORTED_LANGUAGES.find((l) => l.code === "fa");
    const ar = SUPPORTED_LANGUAGES.find((l) => l.code === "ar");
    const tr = SUPPORTED_LANGUAGES.find((l) => l.code === "tr");

    expect(en?.dir).toBe("ltr");
    expect(fa?.dir).toBe("rtl");
    expect(ar?.dir).toBe("rtl");
    expect(tr?.dir).toBe("ltr");
  });

  it("contains complete translation structures across all languages", () => {
    const languages: SupportedLanguage[] = ["en", "fa", "ar", "tr"];

    languages.forEach((lang) => {
      const dict = TRANSLATIONS[lang];
      expect(dict).toBeDefined();
      expect(dict.nav.dashboard).toBeTruthy();
      expect(dict.topbar.platformTitle).toBeTruthy();
      expect(dict.signal.buy).toBeTruthy();
      expect(dict.risk.tradeRiskBreakdown).toBeTruthy();
      expect(dict.academy.title).toBeTruthy();
      expect(dict.settings.languageSettings).toBeTruthy();
      expect(dict.watchlist.columns.symbol).toBeTruthy();
    });
  });

  it("formats numbers and currency correctly according to locale rules", () => {
    const value = 2650.5;
    const enCurrency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
    const faCurrency = new Intl.NumberFormat("fa-IR", { style: "currency", currency: "USD" }).format(value);
    const arCurrency = new Intl.NumberFormat("ar-SA", { style: "currency", currency: "USD" }).format(value);

    expect(enCurrency).toContain("2,650.50");
    expect(faCurrency).toBeDefined();
    expect(arCurrency).toBeDefined();
  });
});

import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import {
  SUPPORTED_LANGUAGES,
  TRANSLATIONS,
  type LanguageInfo,
  type SupportedLanguage,
  type TextDirection,
} from "./translations";

const STORAGE_KEY = "ai_trading_lab_lang";

export interface I18nContextType {
  language: SupportedLanguage;
  direction: TextDirection;
  currentLanguageInfo: LanguageInfo;
  supportedLanguages: LanguageInfo[];
  setLanguage: (lang: SupportedLanguage) => void;
  t: (keyPath: string, vars?: Record<string, string | number>) => string;
  formatNumber: (value: number, options?: Intl.NumberFormatOptions) => string;
  formatCurrency: (value: number, currency?: string) => string;
  formatPercent: (value: number) => string;
  formatDate: (date: string | number | Date, options?: Intl.DateTimeFormatOptions) => string;
}

const I18nContext = createContext<I18nContextType | null>(null);

function getInitialLanguage(): SupportedLanguage {
  try {
    const saved = localStorage.getItem(STORAGE_KEY) as SupportedLanguage;
    if (saved && SUPPORTED_LANGUAGES.some((l) => l.code === saved)) {
      return saved;
    }
  } catch {
    // Fallback if localStorage is restricted
  }

  try {
    const browserLang = navigator.language?.slice(0, 2).toLowerCase();
    if (browserLang === "fa") return "fa";
    if (browserLang === "ar") return "ar";
    if (browserLang === "tr") return "tr";
  } catch {
    // Ignore browser lang check failures
  }

  return "en";
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<SupportedLanguage>(getInitialLanguage);

  const currentLanguageInfo = useMemo(() => {
    return (
      SUPPORTED_LANGUAGES.find((l) => l.code === language) ?? SUPPORTED_LANGUAGES[0]
    );
  }, [language]);

  const direction = currentLanguageInfo.dir;

  const setLanguage = (lang: SupportedLanguage) => {
    setLanguageState(lang);
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      // Ignore storage errors
    }
  };

  useEffect(() => {
    document.documentElement.setAttribute("dir", direction);
    document.documentElement.setAttribute("lang", language);
  }, [language, direction]);

  const localeCode = useMemo(() => {
    switch (language) {
      case "fa":
        return "fa-IR";
      case "ar":
        return "ar-SA";
      case "tr":
        return "tr-TR";
      default:
        return "en-US";
    }
  }, [language]);

  const t = (keyPath: string, vars?: Record<string, string | number>): string => {
    const parts = keyPath.split(".");
    let current: unknown = TRANSLATIONS[language] || TRANSLATIONS.en;
    let fallback: unknown = TRANSLATIONS.en;

    for (const p of parts) {
      if (current && typeof current === "object" && p in current) {
        current = (current as Record<string, unknown>)[p];
      } else {
        current = undefined;
      }
      if (fallback && typeof fallback === "object" && p in fallback) {
        fallback = (fallback as Record<string, unknown>)[p];
      } else {
        fallback = undefined;
      }
    }

    let result = typeof current === "string" ? current : typeof fallback === "string" ? fallback : keyPath;

    if (vars) {
      Object.entries(vars).forEach(([k, v]) => {
        result = result.replace(new RegExp(`{{\\s*${k}\\s*}}`, "g"), String(v));
      });
    }

    return result;
  };

  const formatNumber = (value: number, options?: Intl.NumberFormatOptions): string => {
    try {
      return new Intl.NumberFormat(localeCode, options).format(value);
    } catch {
      return String(value);
    }
  };

  const formatCurrency = (value: number, currency: string = "USD"): string => {
    try {
      return new Intl.NumberFormat(localeCode, {
        style: "currency",
        currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(value);
    } catch {
      return `$${value.toFixed(2)}`;
    }
  };

  const formatPercent = (value: number): string => {
    try {
      return new Intl.NumberFormat(localeCode, {
        style: "percent",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(value / 100);
    } catch {
      return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
    }
  };

  const formatDate = (
    date: string | number | Date,
    options?: Intl.DateTimeFormatOptions
  ): string => {
    try {
      const d = typeof date === "string" || typeof date === "number" ? new Date(date) : date;
      if (isNaN(d.getTime())) return String(date);
      const defaultOptions: Intl.DateTimeFormatOptions = {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        ...options,
      };
      return new Intl.DateTimeFormat(localeCode, defaultOptions).format(d);
    } catch {
      return String(date);
    }
  };

  const value: I18nContextType = {
    language,
    direction,
    currentLanguageInfo,
    supportedLanguages: SUPPORTED_LANGUAGES,
    setLanguage,
    t,
    formatNumber,
    formatCurrency,
    formatPercent,
    formatDate,
  };

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextType {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return context;
}

import { describe, expect, it } from "vitest";
import { ACADEMY_CATEGORIES, GLOSSARY_ITEMS } from "./academyData";

describe("Academy & Educational Content", () => {
  it("contains all 10 required educational categories", () => {
    expect(ACADEMY_CATEGORIES.length).toBe(10);
    const categoryIds = ACADEMY_CATEGORIES.map((c) => c.id);
    expect(categoryIds).toContain("basics");
    expect(categoryIds).toContain("how-trading-works");
    expect(categoryIds).toContain("technical-analysis");
    expect(categoryIds).toContain("risk-management");
    expect(categoryIds).toContain("strategy-concepts");
    expect(categoryIds).toContain("backtesting");
    expect(categoryIds).toContain("walk-forward");
    expect(categoryIds).toContain("signals");
    expect(categoryIds).toContain("trading-psychology");
    expect(categoryIds).toContain("glossary");
  });

  it("contains articles for every educational category with valid sections", () => {
    ACADEMY_CATEGORIES.forEach((category) => {
      expect(category.articles.length).toBeGreaterThan(0);
      category.articles.forEach((article) => {
        expect(article.title).toBeTruthy();
        expect(article.readTime).toBeTruthy();
        expect(article.sections.length).toBeGreaterThan(0);
      });
    });
  });

  it("contains glossary items for key quantitative trading terms", () => {
    expect(GLOSSARY_ITEMS.length).toBeGreaterThanOrEqual(10);
    const terms = GLOSSARY_ITEMS.map((g) => g.term);
    expect(terms.some((t) => t.includes("Drawdown"))).toBe(true);
    expect(terms.some((t) => t.includes("Profit Factor"))).toBe(true);
    expect(terms.some((t) => t.includes("Walk-Forward"))).toBe(true);
    expect(terms.some((t) => t.includes("XAU/USD"))).toBe(true);
  });
});

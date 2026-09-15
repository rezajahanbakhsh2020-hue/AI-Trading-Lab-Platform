import { useState } from "react";
import {
  ACADEMY_CATEGORIES,
  GLOSSARY_ITEMS,
  type AcademyArticle,
} from "../../architecture/academyData";
import { useI18n } from "../../i18n";

export function AcademyViewer() {
  const { t } = useI18n();
  const [selectedCategoryId, setSelectedCategoryId] = useState<string>("basics");
  const [selectedArticle, setSelectedArticle] = useState<AcademyArticle | null>(
    ACADEMY_CATEGORIES[0]?.articles[0] ?? null
  );
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [glossaryCategory, setGlossaryCategory] = useState<string>("All");

  const currentCategory = ACADEMY_CATEGORIES.find(
    (cat) => cat.id === selectedCategoryId
  );

  const filteredGlossary = GLOSSARY_ITEMS.filter((item) => {
    const matchesCat =
      glossaryCategory === "All" || item.category === glossaryCategory;
    const matchesQuery =
      item.term.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.definition.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesQuery;
  });

  return (
    <div className="academy-shell">
      {/* Search Header */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-body">
          <div className="academy-search-bar">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              className="input-search"
              placeholder={t("academy.searchPlaceholder")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Category Tabs Bar */}
      <div className="academy-category-scroll">
        {ACADEMY_CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            className={
              selectedCategoryId === cat.id
                ? "cat-tab-btn active"
                : "cat-tab-btn"
            }
            onClick={() => {
              setSelectedCategoryId(cat.id);
              if (cat.articles[0]) {
                setSelectedArticle(cat.articles[0]);
              }
            }}
          >
            <span>{cat.title}</span>
          </button>
        ))}
      </div>

      {selectedCategoryId !== "glossary" ? (
        <div className="grid cols-2" style={{ marginTop: 20 }}>
          {/* Article List / Index */}
          <div className="card">
            <div className="card-head">
              <h3>{currentCategory?.title} Modules</h3>
              <span className="chip">
                {t("academy.modulesCount", { count: currentCategory?.articles.length ?? 0 })}
              </span>
            </div>
            <div className="card-body">
              <p className="hint">{currentCategory?.shortDescription}</p>
              <div className="article-list" style={{ marginTop: 14 }}>
                {currentCategory?.articles.map((art) => (
                  <div
                    key={art.id}
                    className={
                      selectedArticle?.id === art.id
                        ? "article-card-item active"
                        : "article-card-item"
                    }
                    onClick={() => setSelectedArticle(art)}
                  >
                    <div className="article-item-head">
                      <strong>{art.title}</strong>
                      <span className="badge-level">{art.level}</span>
                    </div>
                    <p className="hint">{art.summary}</p>
                    <div className="article-meta">
                      <span>⏱ {t("academy.readTime", { time: art.readTime })}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Reader Pane */}
          <div className="card">
            {selectedArticle ? (
              <div className="card-body">
                <div className="article-reader">
                  <span className="kicker">{selectedArticle.level} Module</span>
                  <h2>{selectedArticle.title}</h2>
                  <div className="article-meta-bar">
                    <span>⏱ {t("academy.readTime", { time: selectedArticle.readTime })}</span>
                    <span className="chip ready-chip">{t("academy.originalContent")}</span>
                  </div>

                  <hr className="divider" />

                  {selectedArticle.sections.map((sec, i) => (
                    <div key={i} className="article-section">
                      <h4>{sec.heading}</h4>
                      <p>{sec.body}</p>
                      {sec.bulletPoints && (
                        <ul className="article-bullets">
                          {sec.bulletPoints.map((bp, idx) => (
                            <li key={idx}>{bp}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="card-body">
                <p className="hint">{t("academy.selectArticleHint")}</p>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Glossary Section */
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-head">
            <div>
              <h3>{t("academy.glossaryTitle")}</h3>
              <p className="hint">{t("academy.glossarySub")}</p>
            </div>
            <span className="chip">
              {t("academy.termsCount", { count: filteredGlossary.length })}
            </span>
          </div>

          <div className="card-body">
            <div className="category-pills" style={{ marginBottom: 16 }}>
              {["All", "Risk", "Performance", "Execution", "Backtest", "Strategy", "Markets"].map(
                (cat) => (
                  <button
                    key={cat}
                    className={
                      glossaryCategory === cat ? "pill-btn active" : "pill-btn"
                    }
                    onClick={() => setGlossaryCategory(cat)}
                  >
                    {cat}
                  </button>
                )
              )}
            </div>

            <div className="glossary-grid">
              {filteredGlossary.map((g, i) => (
                <div key={i} className="glossary-card">
                  <div className="glossary-head">
                    <strong>{g.term}</strong>
                    <span className="badge-soft">{g.category}</span>
                  </div>
                  <p className="hint">{g.definition}</p>
                  {g.formulaOrExample && (
                    <code className="formula-box">{g.formulaOrExample}</code>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

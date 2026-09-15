import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useI18n } from "../../i18n";
import {
  queryCommandCenter,
  loadRecentSearches,
  saveRecentSearch,
  clearRecentSearches,
  type CommandItem,
} from "../../architecture/commandCenter";
import type { HostSnapshot } from "../../architecture/hostView";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  snapshot: HostSnapshot;
  onSelectSymbol?: (symbol: string) => void;
}

export function CommandPalette({
  isOpen,
  onClose,
  snapshot,
  onSelectSymbol,
}: CommandPaletteProps) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);

  useEffect(() => {
    if (isOpen) {
      setRecentSearches(loadRecentSearches());
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery("");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const groups = queryCommandCenter(query, snapshot);
  const flattenedItems: CommandItem[] = groups.flatMap((g) => g.items);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (flattenedItems.length > 0) {
        setSelectedIndex((prev) => (prev + 1) % flattenedItems.length);
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (flattenedItems.length > 0) {
        setSelectedIndex((prev) => (prev - 1 + flattenedItems.length) % flattenedItems.length);
      }
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (flattenedItems.length > 0 && flattenedItems[selectedIndex]) {
        handleSelectItem(flattenedItems[selectedIndex]);
      }
    }
  };

  const handleSelectItem = (item: CommandItem) => {
    if (query.trim()) {
      saveRecentSearch(query);
    }
    onClose();

    if (item.actionSymbol && onSelectSymbol) {
      onSelectSymbol(item.actionSymbol);
    }

    if (item.route) {
      navigate(item.route);
    }
  };

  const handleClearRecent = () => {
    clearRecentSearches();
    setRecentSearches([]);
  };

  const handleRecentClick = (recentQuery: string) => {
    setQuery(recentQuery);
    inputRef.current?.focus();
  };

  let globalItemCounter = 0;

  return (
    <div
      className="command-palette-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={t("commandCenter.title")}
    >
      <div
        className="command-palette-modal"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <div className="command-palette-header">
          <span className="search-icon">🔍</span>
          <input
            ref={inputRef}
            type="text"
            className="command-palette-input"
            placeholder={t("commandCenter.placeholder")}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
          />
          <button
            className="command-palette-close-btn"
            onClick={onClose}
            title={t("commandCenter.close")}
          >
            ✕
          </button>
        </div>

        {!query && recentSearches.length > 0 && (
          <div className="command-palette-recent">
            <div className="recent-head">
              <span>{t("commandCenter.recentSearches")}</span>
              <button className="btn-link" onClick={handleClearRecent}>
                {t("commandCenter.clearRecent")}
              </button>
            </div>
            <div className="recent-chips">
              {recentSearches.map((item) => (
                <button
                  key={item}
                  className="recent-chip"
                  onClick={() => handleRecentClick(item)}
                >
                  🕒 {item}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="command-palette-body">
          {flattenedItems.length === 0 ? (
            <div className="command-palette-empty">
              <h4>{t("commandCenter.noResultsTitle")}</h4>
              <p>{t("commandCenter.noResultsSub")}</p>
            </div>
          ) : (
            groups.map((group) => {
              const categoryLabel = t(group.categoryLabelKey as any) !== group.categoryLabelKey
                ? t(group.categoryLabelKey as any)
                : t(`commandCenter.categories.${group.category}` as any) || group.category;

              return (
                <div key={group.category} className="command-group">
                  <div className="command-group-header">{categoryLabel}</div>
                  <div className="command-group-items">
                    {group.items.map((item) => {
                      const currentIndex = globalItemCounter++;
                      const isSelected = currentIndex === selectedIndex;

                      return (
                        <div
                          key={item.id}
                          className={`command-item ${isSelected ? "selected" : ""}`}
                          onClick={() => handleSelectItem(item)}
                          onMouseEnter={() => setSelectedIndex(currentIndex)}
                        >
                          <div className="command-item-main">
                            <span className="command-item-title">{item.title}</span>
                            {item.description && (
                              <span className="command-item-desc">{item.description}</span>
                            )}
                          </div>
                          <div className="command-item-meta">
                            {item.badge && (
                              <span className={`chip ${item.requiresAdmin ? "ready-chip" : ""}`}>
                                {item.badge}
                              </span>
                            )}
                            <span className="command-item-route">{item.route}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div className="command-palette-footer">
          <span>{t("commandCenter.keyboardHint")}</span>
          <span className="platform-tag">AI Trading Lab Platform</span>
        </div>
      </div>
    </div>
  );
}

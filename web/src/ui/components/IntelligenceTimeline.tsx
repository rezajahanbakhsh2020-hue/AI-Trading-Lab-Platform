import { useState } from "react";
import type { HostSnapshot } from "../../architecture/hostView";
import type { NotificationItem } from "../../architecture/notification";
import {
  extractTimelineFromHostSnapshot,
  generateExplainabilityPayload,
  type TimelineCategory,
  type TimelineItem,
  type ExplainabilityPayload,
} from "../../architecture/timeline";

interface IntelligenceTimelineProps {
  snapshot: HostSnapshot;
  notifications?: readonly NotificationItem[];
  compact?: boolean;
}

export function IntelligenceTimeline({
  snapshot,
  notifications = [],
  compact = false,
}: IntelligenceTimelineProps) {
  const [activeCategory, setActiveCategory] = useState<TimelineCategory | "all">("all");
  const [selectedItem, setSelectedItem] = useState<TimelineItem | null>(null);
  const [explainPayload, setExplainPayload] = useState<ExplainabilityPayload | null>(null);

  const allItems = extractTimelineFromHostSnapshot(snapshot, notifications);

  const filteredItems = activeCategory === "all"
    ? allItems
    : allItems.filter((it) => it.category === activeCategory);

  const handleInspectExplainability = (item: TimelineItem) => {
    setSelectedItem(item);
    const exp = generateExplainabilityPayload(item, snapshot);
    setExplainPayload(exp);
  };

  const handleCloseExplainability = () => {
    setSelectedItem(null);
    setExplainPayload(null);
  };

  const categories: { id: TimelineCategory | "all"; label: string }[] = [
    { id: "all", label: "All Events" },
    { id: "market", label: "Market" },
    { id: "signal", label: "Signals" },
    { id: "notification", label: "Notifications" },
    { id: "health", label: "Health & System" },
  ];

  return (
    <div className={`timeline-container ${compact ? "timeline-compact" : ""}`}>
      <div className="timeline-header flex justify-between items-center mb-4">
        <div>
          <h2 className="text-xl font-bold text-gray-100 flex items-center gap-2">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            Unified Intelligence Timeline
          </h2>
          <p className="text-xs text-gray-400 mt-1">
            Real chronological platform activity & explainability layer
          </p>
        </div>

        {!compact && (
          <div className="timeline-filters flex gap-1 bg-gray-900/80 p-1 rounded-lg border border-gray-800">
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id)}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                  activeCategory === cat.id
                    ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                    : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {filteredItems.length === 0 ? (
        <div className="empty-timeline p-8 text-center bg-gray-900/40 rounded-xl border border-gray-800/60">
          <p className="text-sm text-gray-400">No events recorded in this category.</p>
        </div>
      ) : (
        <div className="timeline-feed space-y-3">
          {filteredItems.map((item) => (
            <div
              key={item.itemId}
              className={`timeline-card p-3.5 rounded-xl bg-gray-900/60 border transition-all ${
                item.severity === "success"
                  ? "border-emerald-500/30 hover:border-emerald-500/50"
                  : item.severity === "warning"
                  ? "border-amber-500/30 hover:border-amber-500/50"
                  : item.severity === "error"
                  ? "border-rose-500/30 hover:border-rose-500/50"
                  : "border-gray-800 hover:border-gray-700"
              }`}
            >
              <div className="flex justify-between items-start gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2 py-0.5 text-[10px] font-semibold tracking-wider rounded uppercase ${
                      item.category === "signal"
                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                        : item.category === "market"
                        ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                        : item.category === "health"
                        ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                        : "bg-gray-800 text-gray-300"
                    }`}>
                      {item.category}
                    </span>
                    <span className="text-xs font-semibold text-gray-200">
                      {item.title}
                    </span>
                  </div>

                  <p className="text-xs text-gray-300 mt-1 leading-relaxed">
                    {item.summary}
                  </p>

                  <div className="flex items-center gap-3 mt-2 text-[11px] text-gray-400">
                    <span>Source: <strong className="text-gray-300">{item.source}</strong></span>
                    <span>•</span>
                    <time>{item.formattedTime}</time>
                  </div>
                </div>

                {item.explainable && (
                  <button
                    onClick={() => handleInspectExplainability(item)}
                    className="px-2.5 py-1 text-xs font-medium text-amber-400 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 rounded-lg transition-colors whitespace-nowrap"
                  >
                    Explain Context →
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Explainability Modal Drawer */}
      {selectedItem && explainPayload && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="explain-modal w-full max-w-2xl bg-gray-900 border border-amber-500/40 rounded-2xl p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start mb-4 border-b border-gray-800 pb-3">
              <div>
                <span className="px-2.5 py-0.5 text-[10px] font-bold uppercase rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">
                  Explainability Layer
                </span>
                <h3 className="text-lg font-bold text-gray-100 mt-1">
                  {selectedItem.title}
                </h3>
              </div>
              <button
                onClick={handleCloseExplainability}
                className="text-gray-400 hover:text-white text-lg font-bold p-1"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                <h4 className="font-semibold text-amber-400 mb-1">Source & Freshness</h4>
                <div className="grid grid-cols-2 gap-2 text-gray-300">
                  <div>Source: <strong>{explainPayload.source}</strong></div>
                  <div>Freshness: <strong className="text-emerald-400">{explainPayload.freshnessStatus}</strong></div>
                  <div>Received At: {explainPayload.receivedAt}</div>
                </div>
              </div>

              <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                <h4 className="font-semibold text-amber-400 mb-1">Permitted Market Context</h4>
                <pre className="text-emerald-300 font-mono text-[11px] overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(explainPayload.permittedMarketContext, null, 2)}
                </pre>
              </div>

              <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                <h4 className="font-semibold text-amber-400 mb-1">Permitted Risk & Setup Context</h4>
                <pre className="text-blue-300 font-mono text-[11px] overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(explainPayload.permittedRiskContext, null, 2)}
                </pre>
              </div>

              <div className="bg-gray-950 p-3 rounded-lg border border-gray-800">
                <h4 className="font-semibold text-amber-400 mb-1">Explainability Boundary Notes</h4>
                <ul className="list-disc list-inside space-y-1 text-gray-300">
                  {explainPayload.explainabilityNotes.map((note, idx) => (
                    <li key={idx}>{note}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="mt-5 flex justify-end">
              <button
                onClick={handleCloseExplainability}
                className="px-4 py-2 text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg transition-colors"
              >
                Close Explanation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

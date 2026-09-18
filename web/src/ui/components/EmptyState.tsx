type EmptyStateProps = {
  title: string;
  message: string;
  icon?: string;
  actionText?: string;
  onAction?: () => void;
  helpRoute?: string;
  helpText?: string;
};

export function EmptyState({
  title,
  message,
  actionText,
  onAction,
  helpRoute = "/help",
  helpText = "Need Help? Visit Help Center →",
}: EmptyStateProps) {
  return (
    <div className="empty-state">
      <div className="empty-icon-ring">
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h4>{title}</h4>
      <p className="hint">{message}</p>
      <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center", alignItems: "center", marginTop: 12 }}>
        {actionText && onAction && (
          <button className="btn btn-secondary" onClick={onAction}>
            {actionText}
          </button>
        )}
        {helpRoute && (
          <a href={helpRoute} className="btn btn-ghost" style={{ fontSize: "0.8125rem", color: "#60a5fa" }}>
            {helpText}
          </a>
        )}
      </div>
    </div>
  );
}

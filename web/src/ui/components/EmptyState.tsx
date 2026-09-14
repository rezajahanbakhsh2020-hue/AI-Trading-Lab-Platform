type EmptyStateProps = {
  title: string;
  message: string;
  icon?: string;
  actionText?: string;
  onAction?: () => void;
};

export function EmptyState({
  title,
  message,
  actionText,
  onAction,
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
      {actionText && onAction && (
        <button className="btn btn-secondary" onClick={onAction} style={{ marginTop: 12 }}>
          {actionText}
        </button>
      )}
    </div>
  );
}

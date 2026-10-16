import { STATUS_LABELS } from "../lib/format";

export function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{STATUS_LABELS[status] || status}</span>;
}

// Loading / error placeholder used by every view.
export function LoadState({ loading, error, onRetry }) {
  if (loading) return <div className="state" role="status">Loading...</div>;
  if (error)
    return (
      <div className="state state-error" role="alert">
        <span>{error.message}</span>
        {onRetry && (
          <button type="button" className="btn btn-ghost" onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
    );
  return null;
}

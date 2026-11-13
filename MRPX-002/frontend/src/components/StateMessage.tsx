import { AlertTriangle } from "lucide-react";

const SKELETON_ROWS = 10;

/** Loading skeleton, empty block and error block for the content area. */
export function StateMessage(props: {
  kind: "loading" | "empty" | "error";
  message?: string;
  onAction?: () => void;
  actionLabel?: string;
}) {
  const { kind, message, onAction, actionLabel } = props;

  if (kind === "loading") {
    return (
      <div className="card px-4 py-3" role="status" aria-busy="true">
        <span className="sr-only">Loading transfer candidates</span>
        {Array.from({ length: SKELETON_ROWS }, (_, i) => (
          <div
            key={i}
            aria-hidden="true"
            className="my-4 h-3 animate-pulse rounded bg-asm-mist"
            style={{ width: `${90 + (i % 3) * 3}%` }}
          />
        ))}
      </div>
    );
  }

  const isError = kind === "error";
  return (
    <div className="card p-6 text-left" role={isError ? "alert" : "status"}>
      <h2 className="flex items-center gap-2 text-base font-semibold text-asm-ink">
        {isError && (
          <AlertTriangle aria-hidden="true" className="h-5 w-5 shrink-0 text-asm-err lg:h-4 lg:w-4" />
        )}
        {message}
      </h2>
      {onAction && actionLabel && (
        <button
          type="button"
          className={`mt-4 ${isError ? "btn-primary" : "btn-outline"}`}
          onClick={onAction}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

import { AlertTriangle } from "lucide-react";

import { daysOld, formatDate, formatMonth } from "../format";
import { STALE_AFTER_DAYS } from "../pages/TransferCandidatesPage";

/** "MRP result 30 Aug 2026 · Inventory month Aug 2026", with a warning when the MRP result is stale. */
export function FreshnessLine(props: {
  mrpSnapshotDate: string | null;
  inventoryMonth: string | null;
  today: Date;
}) {
  const { mrpSnapshotDate: d, inventoryMonth: m, today } = props;
  if (d === null) {
    return <p className="mb-4 text-sm text-asm-muted">No MRP result loaded yet</p>;
  }
  const age = daysOld(d, today);
  const stale = age > STALE_AFTER_DAYS;
  const text = `MRP result ${formatDate(d)}` + (m ? ` · Inventory month ${formatMonth(m)}` : "");
  return (
    <div className="mb-4">
      <div className="flex flex-wrap items-center gap-3 text-sm text-asm-muted">
        <span>{text}</span>
        {stale && (
          <span className="chip-warn">
            <AlertTriangle aria-hidden="true" size={16} />
            {`${age} days old`}
          </span>
        )}
      </div>
      {stale && (
        <p className="mt-2 text-sm text-asm-ink">
          {`The daily refresh has not run since ${formatDate(d)}.`}
        </p>
      )}
    </div>
  );
}

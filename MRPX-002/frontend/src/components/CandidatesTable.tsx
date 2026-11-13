import { ChevronDown, ChevronUp } from "lucide-react";
import type { KeyboardEvent, ReactNode } from "react";

import type { CandidateQuery } from "../api";
import { coveragePct, formatQty } from "../format";
import type { CandidateRow } from "../types";

type SortColumn = NonNullable<CandidateQuery["sortBy"]>;

const CRIT_CHIP: Record<string, string> = { A: "chip-crit-a", B: "chip-crit-b", C: "chip-crit-c" };
// Columns that only show from the 1024 px breakpoint (tablet keeps 5 key columns).
const WIDE = "hidden lg:table-cell";
const TH = "sticky top-0 z-10 bg-asm-paper px-3 py-2 text-left text-xs font-medium text-asm-muted border-b border-asm-line";
const TD = "px-3 py-3 align-top text-sm";
const ICON = "h-5 w-5 lg:h-4 lg:w-4";

function CriticalityChip({ value }: { value: string | null }) {
  const chip = value ? CRIT_CHIP[value] : undefined;
  if (!chip) return <span className="chip-mute">Not set</span>;
  return (
    <span className={chip}>
      <span className="max-lg:sr-only">Criticality </span>
      {value}
    </span>
  );
}

function PlantCell({ code, name }: { code: string; name: string }) {
  return (
    <>
      <span className="block font-mono">{code}</span>
      <span className="block text-xs text-asm-muted">{name}</span>
    </>
  );
}

function SortHeader(props: {
  column: SortColumn;
  label: string;
  sortBy: string;
  sortDir: string;
  onSort: (col: SortColumn) => void;
  className?: string;
}) {
  const { column, label, sortBy, sortDir, onSort, className = "" } = props;
  const active = sortBy === column;
  const ariaSort = active ? (sortDir === "asc" ? "ascending" : "descending") : "none";
  let arrow: ReactNode = null;
  if (active) {
    arrow =
      sortDir === "asc" ? (
        <ChevronUp aria-hidden="true" className={ICON} />
      ) : (
        <ChevronDown aria-hidden="true" className={ICON} />
      );
  }
  return (
    <th scope="col" aria-sort={ariaSort} className={`${TH} text-right ${className}`}>
      <button
        type="button"
        onClick={() => onSort(column)}
        className={`focus-ring ml-auto inline-flex min-h-[48px] items-center gap-1 rounded lg:min-h-[44px] ${
          active ? "text-asm-ink" : ""
        }`}
      >
        {label}
        {arrow}
      </button>
    </th>
  );
}

/** Sortable candidate table: 10 columns from 1024 px, 5 key columns below. Rows open SCR-02. */
export function CandidatesTable(props: {
  rows: CandidateRow[];
  sortBy: string;
  sortDir: string;
  onSort: (col: SortColumn) => void;
  onOpen: (row: CandidateRow) => void;
}) {
  const { rows, sortBy, sortDir, onSort, onOpen } = props;
  const sortProps = { sortBy, sortDir, onSort };
  const onKey = (e: KeyboardEvent<HTMLTableRowElement>, row: CandidateRow) => {
    if (e.key === "Enter") {
      e.preventDefault();
      onOpen(row);
    }
  };

  return (
    <div className="card">
      <table className="w-full border-separate border-spacing-0">
        <thead>
          <tr>
            <th scope="col" className={TH}>Material</th>
            <th scope="col" className={TH}>Criticality</th>
            <th scope="col" className={`${TH} ${WIDE}`}>Family</th>
            <th scope="col" className={`${TH} ${WIDE}`}>Type</th>
            <th scope="col" className={`${TH} ${WIDE}`}>Short plant</th>
            <SortHeader column="shortage_qty" label="Shortage" className={WIDE} {...sortProps} />
            <SortHeader column="weeks_late" label="Weeks late" {...sortProps} />
            <th scope="col" className={TH}>Plant holding stock</th>
            <SortHeader column="stock_qty" label="Stock" className={WIDE} {...sortProps} />
            <SortHeader column="movable_qty" label="Movable" {...sortProps} />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const pct = coveragePct(row.movable_qty, row.shortage_qty);
            const unit = row.unit_of_measure ? ` ${row.unit_of_measure}` : "";
            return (
              <tr
                key={`${row.material}|${row.short_plant}|${row.stock_plant}`}
                tabIndex={0}
                role="link"
                onClick={() => onOpen(row)}
                onKeyDown={(e) => onKey(e, row)}
                className="focus-ring cursor-pointer hover:bg-asm-mist [&>td]:border-b [&>td]:border-asm-line last:[&>td]:border-b-0"
              >
                <td className={`${TD} lg:max-w-[18rem]`}>
                  <span className="block font-mono">{row.material}</span>
                  {row.material_description && (
                    <span
                      className="block text-xs text-asm-muted lg:truncate"
                      title={row.material_description}
                    >
                      {row.material_description}
                    </span>
                  )}
                </td>
                <td className={TD}>
                  <CriticalityChip value={row.criticality === "NONE" ? null : row.criticality} />
                </td>
                <td className={`${TD} ${WIDE}`}>{row.product_family ?? ""}</td>
                <td className={`${TD} ${WIDE}`}>{row.material_type ?? ""}</td>
                <td className={`${TD} ${WIDE}`}>
                  <PlantCell code={row.short_plant} name={row.short_plant_name} />
                </td>
                <td className={`${TD} ${WIDE} tnum text-right`}>{formatQty(row.shortage_qty)}</td>
                <td className={`${TD} tnum text-right`}>{`${row.weeks_late} wk`}</td>
                <td className={TD}>
                  <PlantCell code={row.stock_plant} name={row.stock_plant_name} />
                </td>
                <td className={`${TD} ${WIDE} tnum text-right`}>{formatQty(row.stock_qty)}</td>
                <td className={`${TD} tnum text-right`}>
                  <span className="block font-semibold">{`${formatQty(row.movable_qty)}${unit}`}</span>
                  <span className="ml-auto mt-1 block h-1 w-24 overflow-hidden rounded-full bg-asm-mist">
                    <span className="block h-1 rounded-full bg-asm-cyan" style={{ width: `${pct}%` }} />
                  </span>
                  <span className="mt-1 block text-xs text-asm-muted">
                    <span className="lg:hidden">{`of ${formatQty(row.shortage_qty)} · `}</span>
                    {`${pct}%`}
                    <span className="hidden lg:inline"> of shortage</span>
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

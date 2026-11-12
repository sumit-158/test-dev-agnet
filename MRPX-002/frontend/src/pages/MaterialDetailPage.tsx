import { ArrowLeft } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { ApiError, ERROR_UNAVAILABLE, fetchMaterialDetail } from "../api";
import { HoldingPlantsTable } from "../components/HoldingPlantsTable";
import { StateMessage } from "../components/StateMessage";
import { formatDate, formatMonth, formatQty } from "../format";
import type { MaterialDetail } from "../types";
import { COPY_RETRY } from "./TransferCandidatesPage";

export const COPY_NOT_FOUND_TITLE = "Not in the current MRP result";
export const COPY_BACK = "Back to transfer candidates";
export const COPY_NO_DESCRIPTION = "No description in the material master";

const CRIT_CHIP: Record<string, string> = { A: "chip-crit-a", B: "chip-crit-b", C: "chip-crit-c" };
const ICON = "h-5 w-5 lg:h-4 lg:w-4";

type Failure = { notFound: boolean; message: string };

function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

function CriticalityChip({ value }: { value: string | null }) {
  const chip = value ? CRIT_CHIP[value] : undefined;
  if (!value || !chip) return <span className="chip-mute">Not set</span>;
  return <span className={chip}>{`Criticality ${value}`}</span>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-asm-muted">{label}</dt>
      <dd className="mt-1 text-sm text-asm-ink">{children}</dd>
    </div>
  );
}

// Freshness fields read as one phrase ("MRP result 30 Aug 2026"); the term stays for assistive tech.
function InlineField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="sr-only">{label}</dt>
      <dd className="text-sm text-asm-ink">{`${label} ${value}`}</dd>
    </div>
  );
}

function Header({ detail }: { detail: MaterialDetail }) {
  const crit = detail.criticality === "NONE" ? null : detail.criticality;
  return (
    <div className="mb-4">
      <h1 className="font-mono text-2xl font-semibold text-asm-ink">{detail.material}</h1>
      {detail.material_description ? (
        <p className="mt-1 text-base text-asm-ink">{detail.material_description}</p>
      ) : (
        <p className="mt-1 text-base text-asm-muted">{COPY_NO_DESCRIPTION}</p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <CriticalityChip value={crit} />
        <span className="chip-mute">
          {detail.product_family ? `Family ${detail.product_family}` : "Family not set"}
        </span>
        <span className="chip-mute">
          {detail.material_type ? `Type ${detail.material_type}` : "Type not set"}
        </span>
      </div>
    </div>
  );
}

function KeyFields({ detail }: { detail: MaterialDetail }) {
  const unit = detail.unit_of_measure ? ` ${detail.unit_of_measure}` : "";
  const country = detail.short_plant_country ? ` · ${detail.short_plant_country}` : "";
  return (
    <section aria-label="Shortage details" className="card mb-6 p-4">
      <dl className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Field label="Short plant">
          <span className="font-mono">{detail.short_plant}</span>
          {` · ${detail.short_plant_name}${country}`}
        </Field>
        <Field label="Shortage">
          <span className="tnum text-base font-semibold">{`${formatQty(detail.shortage_qty)}${unit}`}</span>
        </Field>
        <Field label="Expected">
          <span className="tnum">{`${detail.weeks_late} weeks late`}</span>
        </Field>
        <InlineField label="MRP result" value={formatDate(detail.mrp_snapshot_date)} />
        <InlineField label="Inventory month" value={formatMonth(detail.inventory_month)} />
      </dl>
    </section>
  );
}

/** SCR-02: one shortage (material x short plant) and every plant holding stock for it. Read-only. */
export default function MaterialDetailPage(): JSX.Element {
  const { material = "", shortPlant = "" } = useParams();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "";
  const backTo = "/" + from;

  const [detail, setDetail] = useState<MaterialDetail | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  // API-02 once on mount and on "Try again".
  useEffect(() => {
    const ctrl = new AbortController();
    setDetail(null);
    setFailure(null);
    fetchMaterialDetail(material, shortPlant, ctrl.signal)
      .then(setDetail)
      .catch((err: unknown) => {
        if (isAbort(err)) return;
        if (err instanceof ApiError) {
          setFailure({ notFound: err.status === 404, message: err.detail });
        } else {
          setFailure({ notFound: false, message: ERROR_UNAVAILABLE });
        }
      });
    return () => ctrl.abort();
  }, [material, shortPlant, reloadKey]);

  let content;
  if (failure?.notFound) {
    content = (
      <div className="card p-6" role="status">
        <h2 className="text-base font-semibold text-asm-ink">{COPY_NOT_FOUND_TITLE}</h2>
        <p className="mt-2 text-sm text-asm-ink">{failure.message}</p>
        <Link to={backTo} className="btn-outline mt-4">
          {COPY_BACK}
        </Link>
      </div>
    );
  } else if (failure) {
    content = (
      <StateMessage
        kind="error"
        message={failure.message}
        actionLabel={COPY_RETRY}
        onAction={() => setReloadKey((k) => k + 1)}
      />
    );
  } else if (!detail) {
    content = <StateMessage kind="loading" />;
  } else {
    content = (
      <>
        <Header detail={detail} />
        <KeyFields detail={detail} />
        <h2 className="mb-3 text-base font-semibold text-asm-ink">
          {`Plants holding stock (${detail.holding_plants.length})`}
        </h2>
        <HoldingPlantsTable
          plants={detail.holding_plants}
          shortageQty={detail.shortage_qty}
          unit={detail.unit_of_measure}
        />
      </>
    );
  }

  return (
    <>
      <Link to={backTo} className="btn-ghost -ml-4 mb-4">
        <ArrowLeft aria-hidden="true" className={ICON} />
        {COPY_BACK}
      </Link>
      {content}
      <div className="sticky bottom-0 -mx-6 -mb-6 mt-6 border-t border-asm-line bg-asm-paper px-6 py-3 lg:hidden">
        <Link to={backTo} className="btn-outline w-full">
          {COPY_BACK}
        </Link>
      </div>
    </>
  );
}

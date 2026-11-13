import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError, ERROR_UNAVAILABLE, fetchCandidates, fetchFilters, type CandidateQuery } from "../api";
import { CandidatesTable } from "../components/CandidatesTable";
import { FilterBar } from "../components/FilterBar";
import { FreshnessLine } from "../components/FreshnessLine";
import { StateMessage } from "../components/StateMessage";
import { formatQty } from "../format";
import type { CandidatePage, CandidateRow, FilterOptions } from "../types";

export const PAGE_SIZE = 50;
export const STALE_AFTER_DAYS = 1;
export const COPY_EMPTY = "No transfer candidates match these filters.";
export const COPY_CLEAR = "Clear filters";
export const COPY_RETRY = "Try again";

type SortBy = NonNullable<CandidateQuery["sortBy"]>;
const SORT_COLUMNS: SortBy[] = ["movable_qty", "shortage_qty", "stock_qty", "weeks_late"];

export interface ListParams {
  plant: string | "";
  country: string | "";
  crit: string[];
  family: string | "";
  sortBy: CandidateQuery["sortBy"];
  sortDir: "asc" | "desc";
  page: number;
}

/** URL keys: plant, country, crit (comma list), family, sort, dir, page; missing keys get defaults. */
export function readParams(search: URLSearchParams): ListParams {
  const sort = search.get("sort");
  const page = Number.parseInt(search.get("page") ?? "", 10);
  return {
    plant: search.get("plant") ?? "",
    country: search.get("country") ?? "",
    crit: (search.get("crit") ?? "").split(",").filter((c) => c !== ""),
    family: search.get("family") ?? "",
    sortBy: SORT_COLUMNS.find((c) => c === sort) ?? "movable_qty",
    sortDir: search.get("dir") === "asc" ? "asc" : "desc",
    page: Number.isFinite(page) && page >= 1 ? page : 1,
  };
}

/** Writes filters only when set, then always sort, dir and page. */
export function writeParams(p: ListParams): URLSearchParams {
  const search = new URLSearchParams();
  if (p.plant) search.set("plant", p.plant);
  if (p.country) search.set("country", p.country);
  if (p.crit.length > 0) search.set("crit", p.crit.join(","));
  if (p.family) search.set("family", p.family);
  search.set("sort", p.sortBy ?? "movable_qty");
  search.set("dir", p.sortDir);
  search.set("page", String(p.page));
  return search;
}

function errorText(err: unknown): string {
  return err instanceof ApiError ? err.detail : ERROR_UNAVAILABLE;
}

function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

export default function TransferCandidatesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const params = readParams(searchParams);
  const query = writeParams(params).toString();

  const [options, setOptions] = useState<FilterOptions | null>(null);
  const [filtersError, setFiltersError] = useState<string | null>(null);
  const [data, setData] = useState<CandidatePage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const optionsRef = useRef<FilterOptions | null>(null);

  // API-03 once on mount; again only on "Try again" while the options are still missing.
  useEffect(() => {
    if (optionsRef.current) return;
    const ctrl = new AbortController();
    setFiltersError(null);
    fetchFilters(ctrl.signal)
      .then((o) => {
        optionsRef.current = o;
        setOptions(o);
      })
      .catch((err: unknown) => {
        if (!isAbort(err)) setFiltersError(errorText(err));
      });
    return () => ctrl.abort();
  }, [reloadKey]);

  // API-01 on every change of filters, sort or page.
  useEffect(() => {
    const p = readParams(new URLSearchParams(query));
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    fetchCandidates(
      {
        shortPlant: p.plant ? [p.plant] : [],
        country: p.country ? [p.country] : [],
        criticality: p.crit,
        productFamily: p.family ? [p.family] : [],
        sortBy: p.sortBy,
        sortDir: p.sortDir,
        limit: PAGE_SIZE,
        offset: (p.page - 1) * PAGE_SIZE,
      },
      ctrl.signal,
    )
      .then((page) => {
        setData(page);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (isAbort(err)) return;
        setError(errorText(err));
        setLoading(false);
      });
    return () => ctrl.abort();
  }, [query, reloadKey]);

  const update = (p: ListParams) => setSearchParams(writeParams(p));
  const clearFilters = () => update({ ...params, plant: "", country: "", crit: [], family: "", page: 1 });
  const onSort = (col: SortBy) =>
    update({
      ...params,
      sortBy: col,
      sortDir: params.sortBy === col && params.sortDir === "desc" ? "asc" : "desc",
      page: 1,
    });
  const onOpen = (row: CandidateRow) =>
    navigate(`/materials/${encodeURIComponent(row.material)}/plants/${row.short_plant}`, {
      state: { from: location.search },
    });

  const shownError = error ?? filtersError;
  const total = data?.total ?? 0;
  const rows = (data?.items ?? []).slice(0, PAGE_SIZE);
  const plantName = options?.short_plants.find((p) => p.code === params.plant)?.name;
  const plantSuffix = params.plant
    ? plantName
      ? ` for ${plantName} (${params.plant})`
      : ` for plant ${params.plant}`
    : "";
  const from = data ? data.offset + 1 : 0;
  const to = data ? data.offset + rows.length : 0;

  let content;
  if (shownError) {
    content = (
      <StateMessage
        kind="error"
        message={shownError}
        actionLabel={COPY_RETRY}
        onAction={() => setReloadKey((k) => k + 1)}
      />
    );
  } else if (loading || !data) {
    content = <StateMessage kind="loading" />;
  } else if (rows.length === 0) {
    content = (
      <StateMessage kind="empty" message={COPY_EMPTY} actionLabel={COPY_CLEAR} onAction={clearFilters} />
    );
  } else {
    content = (
      <>
        <CandidatesTable
          rows={rows}
          sortBy={params.sortBy ?? "movable_qty"}
          sortDir={params.sortDir}
          onSort={onSort}
          onOpen={onOpen}
        />
        <nav aria-label="Pages" className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-asm-muted">
          <span className="tnum">{`Showing ${formatQty(from)}–${formatQty(to)} of ${formatQty(total)}`}</span>
          <span className="flex gap-2">
            <button
              type="button"
              className="btn-outline disabled:cursor-not-allowed disabled:opacity-50"
              disabled={params.page <= 1}
              onClick={() => update({ ...params, page: params.page - 1 })}
            >
              Previous
            </button>
            <button
              type="button"
              className="btn-outline disabled:cursor-not-allowed disabled:opacity-50"
              disabled={to >= total}
              onClick={() => update({ ...params, page: params.page + 1 })}
            >
              Next
            </button>
          </span>
        </nav>
      </>
    );
  }

  return (
    <>
      <h1 className="mb-2 text-2xl font-semibold text-asm-ink">Transfer candidates</h1>
      <FreshnessLine
        mrpSnapshotDate={data?.mrp_snapshot_date ?? options?.mrp_snapshot_date ?? null}
        inventoryMonth={data?.inventory_month ?? options?.inventory_month ?? null}
        today={new Date()}
      />
      <FilterBar options={options} params={params} onChange={update} />
      {!shownError && !loading && data && (
        <p className="mb-3 text-sm text-asm-muted">
          {`${formatQty(total)} transfer candidates${plantSuffix}`}
        </p>
      )}
      {content}
    </>
  );
}

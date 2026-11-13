import type { CandidatePage, FilterOptions, MaterialDetail } from "./types";

export const DEFAULT_LIMIT = 50;
export const DEFAULT_SORT_BY = "movable_qty";
export const DEFAULT_SORT_DIR = "desc";
export const ERROR_UNAVAILABLE = "The transfer candidates could not be loaded. Try again.";

/** An API response with a non-2xx status; `detail` is the user-facing message. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

export interface CandidateQuery {
  shortPlant?: string[];
  country?: string[];
  criticality?: string[];
  productFamily?: string[];
  sortBy?: "movable_qty" | "shortage_qty" | "stock_qty" | "weeks_late";
  sortDir?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

function buildQuery(q: CandidateQuery): string {
  const params = new URLSearchParams();
  for (const value of q.shortPlant ?? []) params.append("short_plant", value);
  for (const value of q.country ?? []) params.append("country", value);
  for (const value of q.criticality ?? []) params.append("criticality", value);
  for (const value of q.productFamily ?? []) params.append("product_family", value);
  params.append("sort_by", q.sortBy ?? DEFAULT_SORT_BY);
  params.append("sort_dir", q.sortDir ?? DEFAULT_SORT_DIR);
  params.append("limit", String(q.limit ?? DEFAULT_LIMIT));
  params.append("offset", String(q.offset ?? 0));
  return params.toString();
}

async function request<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal, headers: { Accept: "application/json" } });
  if (!res.ok) {
    let detail = ERROR_UNAVAILABLE;
    try {
      const body: unknown = await res.json();
      if (
        typeof body === "object" &&
        body !== null &&
        typeof (body as { detail?: unknown }).detail === "string"
      ) {
        detail = (body as { detail: string }).detail;
      }
    } catch {
      // Non-JSON body (e.g. an HTML 503 from a proxy): keep the generic message.
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export async function fetchCandidates(
  q: CandidateQuery,
  signal?: AbortSignal,
): Promise<CandidatePage> {
  return request<CandidatePage>(`/api/transfer-candidates?${buildQuery(q)}`, signal);
}

export async function fetchFilters(signal?: AbortSignal): Promise<FilterOptions> {
  return request<FilterOptions>("/api/filters", signal);
}

export async function fetchMaterialDetail(
  material: string,
  shortPlant: string,
  signal?: AbortSignal,
): Promise<MaterialDetail> {
  const path = `${encodeURIComponent(material)}/${encodeURIComponent(shortPlant)}`;
  return request<MaterialDetail>(`/api/transfer-candidates/${path}`, signal);
}

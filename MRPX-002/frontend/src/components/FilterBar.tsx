import { useState } from "react";

import { COPY_CLEAR, type ListParams } from "../pages/TransferCandidatesPage";
import type { FilterOptions } from "../types";

const CRITICALITY_TOGGLES = [
  { value: "A", label: "A" },
  { value: "B", label: "B" },
  { value: "C", label: "C" },
  { value: "NONE", label: "Not set" },
];

const SELECT_CLASS =
  "focus-ring min-h-[48px] w-full rounded-lg border border-asm-line px-3 text-sm text-asm-ink lg:min-h-[44px] lg:w-56";
const LABEL_CLASS = "mb-1 block text-xs font-medium text-asm-muted";

/** Plant, country, criticality and family filters; collapses behind a button under 1024 px. */
export function FilterBar(props: {
  options: FilterOptions | null;
  params: ListParams;
  onChange: (p: ListParams) => void;
}) {
  const { options, params, onChange } = props;
  const [open, setOpen] = useState(false);

  const count =
    (params.plant ? 1 : 0) +
    (params.country ? 1 : 0) +
    (params.crit.length > 0 ? 1 : 0) +
    (params.family ? 1 : 0);
  const set = (patch: Partial<ListParams>) => onChange({ ...params, ...patch, page: 1 });
  const toggleCrit = (value: string) =>
    set({
      crit: params.crit.includes(value)
        ? params.crit.filter((c) => c !== value)
        : [...params.crit, value],
    });

  const plants = options?.short_plants ?? [];
  const countries = options?.countries ?? [];
  const families = options?.product_families ?? [];
  const crits = CRITICALITY_TOGGLES.filter((t) => options?.criticalities.includes(t.value));

  return (
    <div className="mb-4">
      <button
        type="button"
        className="btn-outline lg:hidden"
        aria-expanded={open}
        aria-controls="candidate-filters"
        onClick={() => setOpen(!open)}
      >
        {`Filters (${count})`}
      </button>
      <div
        id="candidate-filters"
        className={`card mt-3 flex-col gap-4 p-4 lg:mt-0 lg:flex lg:flex-row lg:flex-wrap lg:items-end ${
          open ? "flex" : "hidden"
        }`}
      >
        <div>
          <label htmlFor="filter-plant" className={LABEL_CLASS}>
            Short plant
          </label>
          <select
            id="filter-plant"
            className={SELECT_CLASS}
            value={params.plant}
            onChange={(e) => set({ plant: e.target.value })}
          >
            <option value="">All plants</option>
            {params.plant && !plants.some((p) => p.code === params.plant) && (
              <option value={params.plant}>{params.plant}</option>
            )}
            {plants.map((p) => (
              <option key={p.code} value={p.code}>{`${p.code} · ${p.name}`}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="filter-country" className={LABEL_CLASS}>
            Country
          </label>
          <select
            id="filter-country"
            className={SELECT_CLASS}
            value={params.country}
            onChange={(e) => set({ country: e.target.value })}
          >
            <option value="">All countries</option>
            {params.country && !countries.includes(params.country) && (
              <option value={params.country}>{params.country}</option>
            )}
            {countries.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <fieldset>
          <legend className={LABEL_CLASS}>Criticality</legend>
          <div className="flex gap-2">
            {crits.map((t) => {
              const pressed = params.crit.includes(t.value);
              return (
                <button
                  key={t.value}
                  type="button"
                  aria-pressed={pressed}
                  onClick={() => toggleCrit(t.value)}
                  className={`focus-ring min-w-[48px] lg:min-w-[44px] ${
                    pressed ? "btn-primary" : "btn-outline"
                  }`}
                >
                  {t.label}
                </button>
              );
            })}
          </div>
        </fieldset>
        <div>
          <label htmlFor="filter-family" className={LABEL_CLASS}>
            Product family
          </label>
          <select
            id="filter-family"
            className={SELECT_CLASS}
            value={params.family}
            onChange={(e) => set({ family: e.target.value })}
          >
            <option value="">All families</option>
            {params.family && !families.includes(params.family) && (
              <option value={params.family}>{params.family}</option>
            )}
            {families.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>
        {count > 0 && (
          <button
            type="button"
            className="btn-ghost self-start lg:self-end"
            onClick={() => set({ plant: "", country: "", crit: [], family: "" })}
          >
            {COPY_CLEAR}
          </button>
        )}
      </div>
    </div>
  );
}

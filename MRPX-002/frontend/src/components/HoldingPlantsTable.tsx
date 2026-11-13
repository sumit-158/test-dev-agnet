import { coveragePct, formatQty } from "../format";
import type { HoldingPlant } from "../types";

// Columns that only show from the 1024 px breakpoint (tablet shows the name under the code).
const WIDE = "hidden lg:table-cell";
const TH = "px-3 py-2 text-left text-xs font-medium text-asm-muted border-b border-asm-line";
const TD = "px-3 py-3 align-top text-sm";
const NO_COUNTRY = "—";

/** Plants holding normal stock for one shortage, in API order (movable_qty desc). Read-only. */
export function HoldingPlantsTable(props: { plants: HoldingPlant[]; shortageQty: number; unit: string | null }): JSX.Element {
  const { plants, shortageQty, unit } = props;
  const suffix = unit ? ` ${unit}` : "";

  return (
    <div className="card overflow-x-auto">
      <table className="w-full border-separate border-spacing-0">
        <thead>
          <tr>
            <th scope="col" className={TH}>Plant</th>
            <th scope="col" className={`${TH} ${WIDE}`}>Name</th>
            <th scope="col" className={`${TH} ${WIDE}`}>Country</th>
            <th scope="col" className={`${TH} text-right`}>Stock</th>
            <th scope="col" className={`${TH} text-right`}>Movable</th>
            <th scope="col" className={`${TH} text-right`}>Covers</th>
          </tr>
        </thead>
        <tbody>
          {plants.map((plant) => {
            const pct = coveragePct(plant.movable_qty, shortageQty);
            const country = plant.stock_plant_country ?? NO_COUNTRY;
            return (
              <tr
                key={plant.stock_plant}
                className="[&>td]:border-b [&>td]:border-asm-line last:[&>td]:border-b-0"
              >
                <td className={TD}>
                  <span className="block font-mono">{plant.stock_plant}</span>
                  <span className="block text-xs text-asm-muted lg:hidden">
                    {`${plant.stock_plant_name} · ${country}`}
                  </span>
                </td>
                <td className={`${TD} ${WIDE}`}>{plant.stock_plant_name}</td>
                <td className={`${TD} ${WIDE}`}>{country}</td>
                <td className={`${TD} tnum text-right`}>{formatQty(plant.stock_qty)}</td>
                <td className={`${TD} tnum text-right font-semibold`}>
                  {`${formatQty(plant.movable_qty)}${suffix}`}
                </td>
                <td className={`${TD} tnum text-right`}>
                  <span className="block">{`Covers ${pct}%`}</span>
                  <span className="ml-auto mt-1 block h-1 w-20 overflow-hidden rounded-full bg-asm-mist lg:w-24">
                    <span className="block h-1 rounded-full bg-asm-cyan" style={{ width: `${pct}%` }} />
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

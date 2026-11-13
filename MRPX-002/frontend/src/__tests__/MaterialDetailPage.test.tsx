import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import * as api from "../api";
import MaterialDetailPage from "../pages/MaterialDetailPage";
import type { MaterialDetail } from "../types";
import { goldenRow } from "./fixtures";

const URL = "/materials/1236-561-01/plants/3300";
const NOT_FOUND = "Material 0000-000-00 is not short in plant 3300 in the current MRP result.";

const goldenDetail: MaterialDetail = {
  material: goldenRow.material,
  material_description: goldenRow.material_description,
  material_type: goldenRow.material_type,
  product_family: goldenRow.product_family,
  criticality: goldenRow.criticality,
  short_plant: goldenRow.short_plant,
  short_plant_name: goldenRow.short_plant_name,
  short_plant_country: goldenRow.short_plant_country,
  shortage_qty: goldenRow.shortage_qty,
  weeks_late: goldenRow.weeks_late,
  unit_of_measure: goldenRow.unit_of_measure,
  mrp_snapshot_date: goldenRow.mrp_snapshot_date,
  inventory_month: goldenRow.inventory_month,
  holding_plants: [
    {
      stock_plant: goldenRow.stock_plant,
      stock_plant_name: goldenRow.stock_plant_name,
      stock_plant_country: goldenRow.stock_plant_country,
      stock_qty: goldenRow.stock_qty,
      movable_qty: goldenRow.movable_qty,
    },
  ],
};

function renderAt(entry: string | { pathname: string; state: unknown }) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/materials/:material/plants/:shortPlant" element={<MaterialDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

test("f07 ac1 renders golden detail", async () => {
  const fetchMaterialDetail = vi.spyOn(api, "fetchMaterialDetail").mockResolvedValue(goldenDetail);
  renderAt(URL);

  expect(await screen.findByRole("heading", { level: 1, name: "1236-561-01" })).toBeInTheDocument();
  expect(fetchMaterialDetail).toHaveBeenCalledWith("1236-561-01", "3300", expect.any(AbortSignal));
  expect(screen.getByText("EMI GASKET / SPIRAL / SSN-053W")).toBeInTheDocument();
  expect(screen.getByText("Criticality A")).toBeInTheDocument();
  expect(screen.getByText("Family PE")).toBeInTheDocument();
  expect(screen.getByText("Type HALB")).toBeInTheDocument();

  const fields = screen.getByRole("region", { name: "Shortage details" });
  expect(within(fields).getByText("Shortage")).toBeInTheDocument();
  expect(within(fields).getByText("336,233 MM")).toBeInTheDocument();
  expect(within(fields).getByText("9 weeks late")).toBeInTheDocument();
  expect(within(fields).getByText("MRP result 30 Aug 2026")).toBeInTheDocument();
  expect(within(fields).getByText("Inventory month Aug 2026")).toBeInTheDocument();

  expect(screen.getByRole("heading", { level: 2, name: "Plants holding stock (1)" })).toBeInTheDocument();
  const table = screen.getByRole("table");
  expect(within(table).getByText("UNKNOWN PLANT")).toBeInTheDocument();
  expect(within(table).getByText("356,500")).toBeInTheDocument();
  expect(within(table).getByText("Covers 100%")).toBeInTheDocument();
});

test("f07 ac2 not found", async () => {
  vi.spyOn(api, "fetchMaterialDetail").mockRejectedValue(new api.ApiError(404, NOT_FOUND));
  renderAt("/materials/0000-000-00/plants/3300");

  expect(await screen.findByText("Not in the current MRP result")).toBeInTheDocument();
  expect(screen.getByText(NOT_FOUND)).toBeInTheDocument();
  const links = screen.getAllByRole("link", { name: "Back to transfer candidates" });
  expect(links.length).toBeGreaterThan(0);
  for (const link of links) expect(link).toHaveAttribute("href", "/");
});

test("f07 ac3 back link keeps filters", async () => {
  vi.spyOn(api, "fetchMaterialDetail").mockResolvedValue(goldenDetail);
  renderAt({ pathname: URL, state: { from: "?plant=3300&crit=A" } });

  expect(await screen.findByRole("heading", { level: 1, name: "1236-561-01" })).toBeInTheDocument();
  const links = screen.getAllByRole("link", { name: "Back to transfer candidates" });
  expect(links.length).toBeGreaterThan(0);
  for (const link of links) expect(link).toHaveAttribute("href", "/?plant=3300&crit=A");
});

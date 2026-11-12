import type { CandidatePage, CandidateRow, FilterOptions } from "../types";

// JSON mirrors of the TSD §12 fixture rows (numbers as numbers, ISO dates as strings).

export const goldenRow: CandidateRow = {
  material: "1236-561-01",
  material_description: "EMI GASKET / SPIRAL / SSN-053W",
  material_type: "HALB",
  product_family: "PE",
  criticality: "A",
  short_plant: "3300",
  short_plant_name: "ASM Korea Ltd.",
  short_plant_country: "KR",
  stock_plant: "1000",
  stock_plant_name: "UNKNOWN PLANT",
  stock_plant_country: null,
  shortage_qty: 336233,
  stock_qty: 356500,
  movable_qty: 336233,
  weeks_late: 9,
  unit_of_measure: "MM",
  mrp_snapshot_date: "2026-08-30",
  inventory_month: "202608",
};

const rowB: CandidateRow = {
  material: "1226-807-01",
  material_description: "EMI GASKET / SPIRAL / SSN-036W",
  material_type: "HALB",
  product_family: "CP",
  criticality: "C",
  short_plant: "3300",
  short_plant_name: "ASM Korea Ltd.",
  short_plant_country: "KR",
  stock_plant: "3320",
  stock_plant_name: "ASM Korea Ltd.",
  stock_plant_country: "KR",
  shortage_qty: 2035876,
  stock_qty: 60000,
  movable_qty: 60000,
  weeks_late: 13,
  unit_of_measure: "MM",
  mrp_snapshot_date: "2026-08-30",
  inventory_month: "202608",
};

const rowC: CandidateRow = {
  material: "1232-405-01",
  material_description: "EMI GASKET / SPIRAL / SSN-028W",
  material_type: "HALB",
  product_family: "CP",
  criticality: "A",
  short_plant: "3300",
  short_plant_name: "ASM Korea Ltd.",
  short_plant_country: "KR",
  stock_plant: "3320",
  stock_plant_name: "ASM Korea Ltd.",
  stock_plant_country: "KR",
  shortage_qty: 55730,
  stock_qty: 60000,
  movable_qty: 55730,
  weeks_late: 12,
  unit_of_measure: "MM",
  mrp_snapshot_date: "2026-08-30",
  inventory_month: "202608",
};

export const sampleRows: CandidateRow[] = [goldenRow, rowB, rowC];

export const samplePage: CandidatePage = {
  items: sampleRows,
  total: 3,
  mrp_snapshot_date: "2026-08-30",
  inventory_month: "202608",
  limit: 50,
  offset: 0,
};

export const sampleFilters: FilterOptions = {
  short_plants: [{ code: "3300", name: "ASM Korea Ltd.", country: "KR" }],
  countries: ["KR"],
  criticalities: ["A", "C", "NONE"],
  product_families: ["CP", "PE"],
  mrp_snapshot_date: "2026-08-30",
  inventory_month: "202608",
};

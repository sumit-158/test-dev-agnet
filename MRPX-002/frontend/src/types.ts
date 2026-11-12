// Mirrors of the v2/F-02 response models. Keys keep the API's snake_case; dates are ISO
// "YYYY-MM-DD" strings, inventory months "YYYYMM" strings, quantities numbers.
// Criticality "NONE" means not set.

export interface CandidateRow {
  material: string;
  material_description: string | null;
  material_type: string | null;
  product_family: string | null;
  criticality: string | null;
  short_plant: string;
  short_plant_name: string;
  short_plant_country: string | null;
  stock_plant: string;
  stock_plant_name: string;
  stock_plant_country: string | null;
  shortage_qty: number;
  stock_qty: number;
  movable_qty: number;
  weeks_late: number;
  unit_of_measure: string | null;
  mrp_snapshot_date: string;
  inventory_month: string;
}

export interface CandidatePage {
  items: CandidateRow[];
  total: number;
  mrp_snapshot_date: string | null;
  inventory_month: string | null;
  limit: number;
  offset: number;
}

export interface HoldingPlant {
  stock_plant: string;
  stock_plant_name: string;
  stock_plant_country: string | null;
  stock_qty: number;
  movable_qty: number;
}

export interface MaterialDetail {
  material: string;
  material_description: string | null;
  material_type: string | null;
  product_family: string | null;
  criticality: string | null;
  short_plant: string;
  short_plant_name: string;
  short_plant_country: string | null;
  shortage_qty: number;
  weeks_late: number;
  unit_of_measure: string | null;
  mrp_snapshot_date: string;
  inventory_month: string;
  holding_plants: HoldingPlant[];
}

export interface PlantOption {
  code: string;
  name: string;
  country: string | null;
}

export interface FilterOptions {
  short_plants: PlantOption[];
  countries: string[];
  criticalities: string[];
  product_families: string[];
  mrp_snapshot_date: string | null;
  inventory_month: string | null;
}

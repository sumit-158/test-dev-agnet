-- MRPX-002 | feature v1/F-03: Validation extract per short plant (VAL-01)
-- Purpose: all transfer candidates of one short plant, for planner confirmation (PRD §3).
--          Reads only the gold view T-01 (delivery-specs §1); nothing is written.
-- Run in the Databricks SQL editor; set parameter `short_plant` to the 4-character plant code; export the result as CSV and share it with the plant's planners for confirmation (PRD §3).
-- Plant code: use the code as shown in SAP (upper case, e.g. 35B0); a lower-case code
--             such as 35b0 returns 0 rows.

-- MRPX-002 v1/F-03 VAL-01: all transfer candidates of one short plant, for planner confirmation (PRD §3).
SELECT material,
       material_description,
       material_type,
       product_family,
       criticality,
       short_plant,
       short_plant_name,
       short_plant_country,
       stock_plant,
       stock_plant_name,
       stock_plant_country,
       shortage_qty,
       stock_qty,
       movable_qty,
       weeks_late,
       unit_of_measure,
       mrp_snapshot_date,
       inventory_month
FROM sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair
WHERE short_plant = :short_plant
ORDER BY movable_qty DESC, material ASC, stock_plant ASC

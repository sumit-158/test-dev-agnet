-- MRPX-002 | feature v1/F-01: Create the gold materialized view of transfer candidates (T-01)
-- Purpose: scheduled materialized view sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair,
--          one row per (material, short plant, stock plant), plus the SELECT grant for the app.
-- Run in the Databricks SQL editor on a serverless SQL warehouse: statement 1, wait for the
-- initial refresh, then statement 2.

-- Statement 1: T-01 (TSD §5.2). Rules: BR-01, BR-02, BR-05, BR-06 (shortage side); library stock notes
-- (stock side); BR-03, BR-04 (plants); D-11 (material master duplicates); BR-07 (schedule); skill §6 (audit columns).
CREATE OR REPLACE MATERIALIZED VIEW sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair (
  material               STRING  COMMENT 'Material (part) number; f_mrp.MATERIAL = dim_material.MATERIAL_KEY',
  material_description   STRING  COMMENT 'Material description from the latest material master batch (column MATERIAL); NULL when blank',
  material_type          STRING  COMMENT 'SAP material type (MATERIAL_TYPE), for example HALB',
  product_family         STRING  COMMENT 'Product family = PRODUCT_HIER_LEVEL_1 of the material master; NULL when blank',
  criticality            STRING  COMMENT 'Material criticality A, B or C from the material master; NULL when blank',
  short_plant            STRING  COMMENT 'Plant code with the MRP shortage (f_mrp.PLANT)',
  short_plant_name       STRING  COMMENT 'Plant name from dim_plant.PLANT; UNKNOWN PLANT when the code is not in dim_plant (BR-03)',
  short_plant_country    STRING  COMMENT 'ISO country of the short plant (dim_plant.COUNTRY_KEY, BR-04); NULL when unmatched',
  stock_plant            STRING  COMMENT 'Plant code holding normal stock of the material (f_monthly_inventory_stock.PLANT)',
  stock_plant_name       STRING  COMMENT 'Plant name from dim_plant.PLANT; UNKNOWN PLANT when the code is not in dim_plant (BR-03)',
  stock_plant_country    STRING  COMMENT 'ISO country of the stock plant (dim_plant.COUNTRY_KEY); NULL when unmatched',
  shortage_qty           DECIMAL(27,3) COMMENT 'SUM(MRP_SHORTAGE_QUANTITY) over shortage rows (> 0) of the material in the short plant, one snapshot (BR-02, BR-05)',
  stock_qty              DECIMAL(27,3) COMMENT 'SUM(TOTAL_QUANTITY) of normal stock (blank SPECIAL_STOCK_INDICATOR) of the material in the stock plant, latest inventory month',
  movable_qty            DECIMAL(27,3) COMMENT 'LEAST(shortage_qty, stock_qty): the part of the shortage this stock could cover',
  weeks_late             INT     COMMENT 'MAX(CAST(ESTIMATED_WEEKS_LATE AS INT)) over the shortage rows (BR-06)',
  unit_of_measure        STRING  COMMENT 'Base unit of measure of the MRP rows (BASE_UNIT_OF_MEASURE); MRP and stock units agree',
  mrp_snapshot_date      DATE    COMMENT 'MRP result date: the one SNAPSHOT_DATE used (latest)',
  inventory_month        STRING  COMMENT 'Inventory month used (CALENDAR_YEAR_MONTH, yyyyMM, latest)',
  ETL_LOADDATE           DATE    COMMENT 'Day this row was computed by the refresh',
  SOURCE_SNAPSHOT_DATE   DATE    COMMENT 'Snapshot date of the MRP source (same as mrp_snapshot_date)',
  CONSTRAINT material_not_null     EXPECT (material IS NOT NULL)            ON VIOLATION FAIL UPDATE,
  CONSTRAINT short_plant_not_null  EXPECT (short_plant IS NOT NULL)         ON VIOLATION FAIL UPDATE,
  CONSTRAINT stock_plant_not_null  EXPECT (stock_plant IS NOT NULL)         ON VIOLATION FAIL UPDATE,
  CONSTRAINT plants_differ         EXPECT (short_plant <> stock_plant)      ON VIOLATION FAIL UPDATE,
  CONSTRAINT movable_positive      EXPECT (movable_qty > 0)                 ON VIOLATION FAIL UPDATE,
  CONSTRAINT criticality_valid     EXPECT (criticality IS NULL OR criticality IN ('A', 'B', 'C'))
)
CLUSTER BY (short_plant, material)
COMMENT 'MRPX-002 transfer candidates: one row per material short in one plant and held as normal stock in another plant, latest MRP snapshot and latest inventory month. Read by the Shortage Rebalancing app.'
SCHEDULE CRON '0 45 6 * * ?' AT TIME ZONE 'Asia/Singapore'
AS
WITH snap AS (
  SELECT MAX(SNAPSHOT_DATE) AS snapshot_date
  FROM sandbox_others.sap_test.f_mrp
),
short AS (
  SELECT m.PLANT                                   AS plant,
         m.MATERIAL                                AS material,
         SUM(m.MRP_SHORTAGE_QUANTITY)              AS shortage_qty,
         MAX(CAST(m.ESTIMATED_WEEKS_LATE AS INT))  AS weeks_late,
         MIN(m.BASE_UNIT_OF_MEASURE)               AS unit_of_measure,
         MAX(m.SNAPSHOT_DATE)                      AS snapshot_date
  FROM sandbox_others.sap_test.f_mrp m
  JOIN snap s ON m.SNAPSHOT_DATE = s.snapshot_date
  WHERE m.MRP_SHORTAGE_QUANTITY > 0
  GROUP BY m.PLANT, m.MATERIAL
),
mon AS (
  SELECT MAX(CALENDAR_YEAR_MONTH) AS inventory_month
  FROM sandbox_others.sap_test.f_monthly_inventory_stock
),
stock AS (
  SELECT s.PLANT                     AS plant,
         s.MATERIAL                  AS material,
         SUM(s.TOTAL_QUANTITY)       AS stock_qty,
         MAX(s.CALENDAR_YEAR_MONTH)  AS inventory_month
  FROM sandbox_others.sap_test.f_monthly_inventory_stock s
  JOIN mon ON s.CALENDAR_YEAR_MONTH = mon.inventory_month
  WHERE s.SPECIAL_STOCK_INDICATOR IS NULL OR s.SPECIAL_STOCK_INDICATOR = ''
  GROUP BY s.PLANT, s.MATERIAL
  HAVING SUM(s.TOTAL_QUANTITY) > 0
),
mat AS (
  SELECT MATERIAL_KEY,
         NULLIF(TRIM(MATERIAL), '')             AS material_description,
         NULLIF(TRIM(MATERIAL_TYPE), '')        AS material_type,
         NULLIF(TRIM(PRODUCT_HIER_LEVEL_1), '') AS product_family,
         NULLIF(TRIM(CRITICALITY), '')          AS criticality
  FROM gops_dev.test.sap_extract_dim_material
  WHERE BATCHRUN_DATE = (SELECT MAX(BATCHRUN_DATE) FROM gops_dev.test.sap_extract_dim_material)
  QUALIFY ROW_NUMBER() OVER (PARTITION BY MATERIAL_KEY ORDER BY CHANGED_ON DESC NULLS LAST, MATERIAL ASC) = 1
)
SELECT sh.material                                        AS material,
       mat.material_description                           AS material_description,
       mat.material_type                                  AS material_type,
       mat.product_family                                 AS product_family,
       mat.criticality                                    AS criticality,
       sh.plant                                           AS short_plant,
       COALESCE(ps.PLANT, 'UNKNOWN PLANT')                AS short_plant_name,
       ps.COUNTRY_KEY                                     AS short_plant_country,
       st.plant                                           AS stock_plant,
       COALESCE(ph.PLANT, 'UNKNOWN PLANT')                AS stock_plant_name,
       ph.COUNTRY_KEY                                     AS stock_plant_country,
       CAST(sh.shortage_qty AS DECIMAL(27,3))             AS shortage_qty,
       CAST(st.stock_qty AS DECIMAL(27,3))                AS stock_qty,
       CAST(LEAST(sh.shortage_qty, st.stock_qty) AS DECIMAL(27,3)) AS movable_qty,
       sh.weeks_late                                      AS weeks_late,
       sh.unit_of_measure                                 AS unit_of_measure,
       CAST(sh.snapshot_date AS DATE)                     AS mrp_snapshot_date,
       st.inventory_month                                 AS inventory_month,
       current_date()                                     AS ETL_LOADDATE,
       CAST(sh.snapshot_date AS DATE)                     AS SOURCE_SNAPSHOT_DATE
FROM short sh
JOIN stock st
  ON sh.material = st.material
 AND sh.plant <> st.plant
LEFT JOIN mat
  ON sh.material = mat.MATERIAL_KEY
LEFT JOIN sandbox_others.sap_test.dim_plant ps
  ON sh.plant = ps.PLANT_KEY
LEFT JOIN sandbox_others.sap_test.dim_plant ph
  ON st.plant = ph.PLANT_KEY;

-- Statement 2: access (D-08)
GRANT SELECT ON TABLE sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair TO `account users`;

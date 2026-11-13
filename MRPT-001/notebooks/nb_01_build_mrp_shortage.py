# Databricks notebook source
# MAGIC %md
# MAGIC # nb_01_build_mrp_shortage
# MAGIC
# MAGIC **Purpose.** Build silver table `f_mrp_shortage` (T-01): for the latest MRP snapshot, the total
# MAGIC shortage and the worst weeks late per material and plant (the short side of the view).
# MAGIC
# MAGIC **Source.** `{CATALOG}.{SRC_SAP_SCHEMA}.f_mrp` (SRC-01, 409M rows over 86 snapshots; filtered to
# MAGIC the latest `SNAPSHOT_DATE` only, never summed across snapshots).
# MAGIC
# MAGIC **Target.** `{CATALOG}.{SCHEMA}.f_mrp_shortage` (`CREATE OR REPLACE TABLE`, rerunnable).
# MAGIC
# MAGIC **Grain.** One row per (`material`, `plant`) with `MRP_SHORTAGE_QUANTITY > 0` in the latest snapshot.
# MAGIC
# MAGIC **Columns.**
# MAGIC | column | type | meaning |
# MAGIC |---|---|---|
# MAGIC | material | STRING | SAP material |
# MAGIC | plant | STRING | SAP plant |
# MAGIC | shortage_qty | DECIMAL | `SUM(MRP_SHORTAGE_QUANTITY)` |
# MAGIC | weeks_late | INT | `MAX(TRY_CAST(ESTIMATED_WEEKS_LATE AS INT))`; non-castable values become NULL, row kept |
# MAGIC | mrp_result_date | DATE | latest `SNAPSHOT_DATE` |
# MAGIC | _etl_loaded_at | TIMESTAMP | load time |
# MAGIC | _etl_run_id | STRING | run id (widget `run_id`, default `manual`) |
# MAGIC
# MAGIC **How to run.** Run all cells (optionally set widget `run_id`). The same SQL can be run through
# MAGIC dbsql on the dev warehouse. Fails with `ValueError("f_mrp is empty")` before writing if the source is empty.

# COMMAND ----------

# Parameters
import re

CATALOG = "sandbox_others"
SCHEMA = "mrpt_001_poc"
SRC_SAP_SCHEMA = "sap_test"

SRC_TABLE = f"{CATALOG}.{SRC_SAP_SCHEMA}.f_mrp"
TARGET_TABLE = f"{CATALOG}.{SCHEMA}.f_mrp_shortage"
GRAIN_KEYS = ["material", "plant"]

try:
    dbutils.widgets.text("run_id", "manual")  # noqa: F821 (Databricks global)
    run_id = dbutils.widgets.get("run_id")  # noqa: F821
except NameError:
    run_id = "manual"
run_id = str(run_id).strip() if run_id is not None else "manual"
if not run_id:
    run_id = "manual"
if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id):
    raise ValueError(f"invalid run_id: {run_id!r} (allowed: [A-Za-z0-9_.-])")

# COMMAND ----------

# Functions


def fx_check_not_empty(df, name):
    """Raise ValueError("<name> is empty") when df has 0 rows (cheap: reads at most 1 row)."""
    if len(df.limit(1).collect()) == 0:
        raise ValueError(f"{name} is empty")


def fx_check_unique_grain(df, keys, name):
    """Raise ValueError when df is not unique on keys."""
    dup = df.groupBy(*keys).count().filter("count > 1").limit(1).collect()
    if dup:
        raise ValueError(f"{name} is not unique on {keys}: e.g. {dup[0].asDict()}")


def fx_check_no_null_keys(df, keys, name):
    """Raise ValueError when any key column is NULL."""
    cond = " OR ".join(f"{k} IS NULL" for k in keys)
    if df.filter(cond).limit(1).collect():
        raise ValueError(f"{name} has null keys in {keys}")


def sql_create_schema():
    return f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}"


def sql_build_mrp_shortage(run_id):
    # TRY_CAST: the warehouse runs in ANSI mode, where CAST of a malformed string fails;
    # the contract requires non-castable weeks late -> NULL with the row kept.
    return f"""
CREATE OR REPLACE TABLE {TARGET_TABLE} AS
WITH snap AS (SELECT MAX(SNAPSHOT_DATE) AS snapshot_date FROM {SRC_TABLE})
SELECT m.MATERIAL AS material, m.PLANT AS plant,
       SUM(m.MRP_SHORTAGE_QUANTITY) AS shortage_qty,
       MAX(TRY_CAST(m.ESTIMATED_WEEKS_LATE AS INT)) AS weeks_late,
       CAST(s.snapshot_date AS DATE) AS mrp_result_date,
       current_timestamp() AS _etl_loaded_at,
       '{run_id}' AS _etl_run_id
FROM {SRC_TABLE} m
JOIN snap s ON m.SNAPSHOT_DATE = s.snapshot_date
WHERE m.MRP_SHORTAGE_QUANTITY > 0
GROUP BY m.MATERIAL, m.PLANT, s.snapshot_date
"""


# COMMAND ----------

# Input checks


def step_input_checks():
    src = spark.table(SRC_TABLE).select("MATERIAL", "PLANT", "SNAPSHOT_DATE")  # noqa: F821
    fx_check_not_empty(src, "f_mrp")


# COMMAND ----------

# Business logic


def step_build():
    spark.sql(sql_create_schema())  # noqa: F821
    spark.sql(sql_build_mrp_shortage(run_id))  # noqa: F821


def step_output_checks():
    out = spark.table(TARGET_TABLE).select(*GRAIN_KEYS)  # noqa: F821
    fx_check_not_empty(out, "f_mrp_shortage")
    fx_check_unique_grain(out, GRAIN_KEYS, "f_mrp_shortage")
    fx_check_no_null_keys(out, GRAIN_KEYS, "f_mrp_shortage")


# COMMAND ----------

# Main


def main():
    step_input_checks()  # fails before anything is written
    step_build()
    step_output_checks()
    print(f"{TARGET_TABLE} built (run_id={run_id})")


main()

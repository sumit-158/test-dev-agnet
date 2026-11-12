-- MRPX-002 v2/F-08: run after the first deploy; replace ${app_sp} with the application id shown by
-- `databricks apps get mrpx-002-transfer-candidates` (field service_principal_client_id).
GRANT USE CATALOG ON CATALOG sandbox_others TO `${app_sp}`;
GRANT USE SCHEMA ON SCHEMA sandbox_others.gold TO `${app_sp}`;
GRANT SELECT ON TABLE sandbox_others.gold.agg_mrpx_transfer_candidate_plant_pair TO `${app_sp}`;

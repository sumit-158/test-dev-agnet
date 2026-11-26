CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.eval_pir_sl_extraction_chat (
  case_id STRING NOT NULL COMMENT 'GE-001 golden, DEMO-nnn, SYN-nnn, INJ-nnn, NOT-nnn, COR-nnn',
  version INT NOT NULL COMMENT 'Evaluation set version',
  title STRING COMMENT 'Request title without personal data',
  messages_json STRING COMMENT 'JSON array of {"text": ...} in send order',
  attachment_paths ARRAY<STRING> COMMENT 'SRC-01 volume paths',
  expected_request_type STRING COMMENT 'create_pir | update_pir | create_sl | update_sl | create_pir_and_sl | not_pir_sl',
  expected_line_items_json STRING COMMENT 'JSON array of line items with doc_type, action, fields',
  expected_source_segments_json STRING COMMENT 'JSON object line_no.field -> [M|A]',
  tags ARRAY<STRING> COMMENT 'golden, demo, synthetic, injection, not_pir_sl, multilingual, conflict, computed, both_pir_and_sl, scanned, correction',
  is_synthetic BOOLEAN COMMENT 'True when written to fill a gap',
  notes STRING COMMENT 'Why the case exists',
  ETL_LOADDATE DATE COMMENT 'Day the row was loaded'
)
COMMENT 'SCO-001 evaluation set: one row per case and version (TSD-SCO-001 T-01)'
CLUSTER BY (version, case_id);

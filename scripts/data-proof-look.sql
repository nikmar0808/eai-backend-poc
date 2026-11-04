-- POC 3, Stage 8: the table's definition, its indexes, what is stored, and the plan of the readings query.
SET timezone = 'UTC';
ANALYZE smart_meter_intervals;
\d smart_meter_intervals
SELECT count(*) AS all_rows, count(*) - count(DISTINCT (meter_id, "timestamp")) AS duplicates FROM smart_meter_intervals;
SELECT "timestamp", kwh_value FROM smart_meter_intervals WHERE meter_id = 'PROOF-0001' ORDER BY "timestamp", id LIMIT 2;
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY OFF)
SELECT * FROM smart_meter_intervals WHERE meter_id = 'PROOF-0100' ORDER BY "timestamp" DESC LIMIT 20;
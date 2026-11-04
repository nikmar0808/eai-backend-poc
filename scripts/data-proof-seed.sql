-- POC 3, Stage 8: made-up old rows on a database of its own, at Alembic revision 0001 (the old table).
-- 200 meters x 1,000 readings, one reading an hour, as India wall-clock time, and every reading of meter PROOF-0001
-- sent twice: what the old service stored when a client retried.
INSERT INTO smart_meter_intervals (meter_id, grid_zone, "timestamp", kwh_value, voltage, created_at)
SELECT 'PROOF-' || lpad(m::text, 4, '0'), 'ZONE-A', timestamp '2026-09-01 00:00:00' + h * interval '1 hour', 1.5, 230.0, timestamp '2026-10-09 00:00:00'
FROM generate_series(1, 200) AS m, generate_series(0, 999) AS h;
INSERT INTO smart_meter_intervals (meter_id, grid_zone, "timestamp", kwh_value, voltage, created_at)
SELECT meter_id, grid_zone, "timestamp", 9.9, voltage, created_at FROM smart_meter_intervals WHERE meter_id = 'PROOF-0001';
ANALYZE smart_meter_intervals;
SELECT count(*) AS all_rows, count(*) - count(DISTINCT (meter_id, "timestamp")) AS duplicates FROM smart_meter_intervals;
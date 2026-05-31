-- Drop legacy tables that have been replaced by portfolio_composition.
-- alerts depends on portfolio_snapshots (FK snapshot_from_id, snapshot_to_id)
-- portfolio_positions depends on portfolio_snapshots
-- Drop in dependency order.

DROP TABLE IF EXISTS alerts CASCADE;
DROP TABLE IF EXISTS portfolio_positions CASCADE;
DROP TABLE IF EXISTS portfolio_snapshots CASCADE;

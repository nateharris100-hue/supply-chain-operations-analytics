#!/usr/bin/env python3
"""
export_master.py — build the single Tableau fact table.

WHY THIS EXISTS
---------------
The first version of this project exported eight separate CSVs, each already
aggregated to a different grain (one row per supplier, per product, per
shipping mode). In Tableau each file is a separate data source, and a filter
only applies within one data source — so a supplier filter could not reach the
shipping file, which had no supplier column left in it.

This script instead exports ONE flat table at the lowest grain (one row = one
order) and lets Tableau do the aggregating. Every KPI on every dashboard is
then a calculation over the same source, so one filter drives the whole story.

Deliberately NOT included: suppliers.on_time_rate. That is the supplier's
nominal contract rate, and keeping it alongside the on-time rate we compute
from actual dates would give the workbook two competing answers to the same
question. Actual delivery dates are the single source of truth.

Usage:  python3 python/export_master.py [db_path]
Output: outputs/supply_chain_master.csv
"""

import os
import sys
import sqlite3
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# Optional override: some network/FUSE-mounted folders don't support SQLite's
# file locking, so the DB can be read from a local copy instead.
DB_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "supply_chain.db")
OUT_DIR = os.path.join(ROOT, "outputs")
OUT_PATH = os.path.join(OUT_DIR, "supply_chain_master.csv")

# One row per order. LEFT JOINs on shipments/inventory so an order without a
# shipment record is still counted in spend. Inventory is collapsed to one row
# per product (MIN inventory_id) — joining it raw would fan out any product
# stocked in two warehouses and silently double that order's spend.
QUERY = """
SELECT
    o.order_id,
    o.order_date,
    o.expected_delivery_date,
    o.actual_delivery_date,
    o.quantity_ordered,
    o.order_cost,
    o.order_status,
    o.po_number,

    s.supplier_id,
    s.supplier_name,
    s.country                AS supplier_country,
    s.city                   AS supplier_city,
    s.lead_time_days         AS contract_lead_time_days,
    s.quality_score,
    s.contract_end_date,

    p.product_id,
    p.product_name,
    p.category,
    p.sku,
    p.unit_cost              AS standard_unit_cost,
    p.reorder_point,
    CASE WHEN p.description LIKE '%single-source%' THEN 1 ELSE 0 END
                             AS is_single_source,

    sh.shipping_mode,
    sh.carrier,
    sh.shipping_cost,
    sh.shipment_date,
    sh.actual_arrival_date,
    sh.shipment_status,

    i.warehouse_location,
    i.quantity_on_hand,
    i.quantity_reserved
FROM orders o
JOIN      suppliers  s  ON s.supplier_id = o.supplier_id
JOIN      products   p  ON p.product_id  = o.product_id
LEFT JOIN shipments  sh ON sh.order_id   = o.order_id
LEFT JOIN inventory  i  ON i.inventory_id = (
            SELECT MIN(inventory_id) FROM inventory
            WHERE product_id = o.product_id)
"""


def main():
    conn = sqlite3.connect(DB_PATH)
    order_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    df = pd.read_sql_query(QUERY, conn)
    conn.close()

    # --- fan-out guard ------------------------------------------------------
    # A silent many-to-many join would duplicate order rows and inflate every
    # spend figure on every dashboard. Fail loudly instead of shipping it.
    assert len(df) == order_count, (
        f"FAN-OUT: {len(df)} rows from {order_count} orders — a join is "
        f"duplicating orders and would inflate all spend metrics."
    )
    assert df["order_id"].is_unique, "FAN-OUT: duplicate order_id in output"

    # --- dates --------------------------------------------------------------
    for col in ["order_date", "expected_delivery_date", "actual_delivery_date",
                "shipment_date", "actual_arrival_date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # --- derived: timing ----------------------------------------------------
    df["days_late"] = (df["actual_delivery_date"]
                       - df["expected_delivery_date"]).dt.days
    df["is_on_time"] = (df["days_late"] <= 0).astype("Int64")
    df["is_on_time"] = df["is_on_time"].where(df["actual_delivery_date"].notna())
    df["is_late"] = 1 - df["is_on_time"]
    # Explicit denominator for on-time rate in Tableau. Dividing by COUNT of
    # orders would wrongly count not-yet-delivered orders as failures.
    df["is_delivered"] = df["actual_delivery_date"].notna().astype(int)
    df["total_cycle_time"] = (df["actual_delivery_date"]
                              - df["order_date"]).dt.days
    df["days_in_transit"] = (df["actual_arrival_date"]
                             - df["shipment_date"]).dt.days
    df["promised_lead_time_days"] = (df["expected_delivery_date"]
                                     - df["order_date"]).dt.days

    # --- derived: cost ------------------------------------------------------
    # Planned cost uses the PRODUCT's standard unit cost (the catalogue price we
    # expected to pay), not the supplier's blended average — otherwise variance
    # just measures product mix rather than price performance.
    df["planned_cost"] = df["quantity_ordered"] * df["standard_unit_cost"]
    df["cost_variance"] = df["order_cost"] - df["planned_cost"]
    df["cost_variance_pct"] = df["cost_variance"] / df["planned_cost"]
    df["landed_cost"] = df["order_cost"] + df["shipping_cost"].fillna(0)
    df["actual_unit_cost"] = df["order_cost"] / df["quantity_ordered"]

    # --- derived: inventory -------------------------------------------------
    df["available_qty"] = df["quantity_on_hand"] - df["quantity_reserved"]
    df["below_reorder_point"] = (
        df["available_qty"] < df["reorder_point"]).astype(int)
    df["coverage_ratio"] = df["available_qty"] / df["reorder_point"]
    df["inventory_value_at_hand"] = (df["quantity_on_hand"]
                                     * df["standard_unit_cost"])

    # --- derived: date parts for trend charts -------------------------------
    df["order_month"] = df["order_date"].values.astype("datetime64[M]")
    df["order_quarter"] = (df["order_date"].dt.year.astype(str) + "-Q"
                           + df["order_date"].dt.quarter.astype(str))
    df["order_year"] = df["order_date"].dt.year

    # --- sanity checks ------------------------------------------------------
    problems = []
    neg = (df["days_in_transit"] < 0).sum()
    if neg:
        problems.append(f"{neg} rows with negative transit time")
    if df["planned_cost"].le(0).any():
        problems.append("non-positive planned_cost present")
    if df["order_cost"].isna().any():
        problems.append("null order_cost present")
    if problems:
        raise SystemExit("DATA QUALITY FAILURES:\n  - " + "\n  - ".join(problems))

    os.makedirs(OUT_DIR, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    # --- report -------------------------------------------------------------
    delivered = df[df["actual_delivery_date"].notna()]
    print(f"Wrote {OUT_PATH}")
    print(f"  rows        : {len(df):,}  (orders: {order_count:,}) — 1:1, no fan-out")
    print(f"  columns     : {len(df.columns)}")
    print(f"  date range  : {df['order_date'].min().date()} to {df['order_date'].max().date()}")
    print(f"  total spend : ${df['order_cost'].sum():,.0f}")
    print(f"  freight     : ${df['shipping_cost'].sum():,.0f}")
    print(f"  on-time     : {100 * delivered['is_on_time'].mean():.1f}%")
    print(f"  cost var    : {100 * df['cost_variance'].sum() / df['planned_cost'].sum():+.2f}%")
    print(f"  suppliers   : {df['supplier_name'].nunique()}   products: {df['product_name'].nunique()}")


if __name__ == "__main__":
    main()

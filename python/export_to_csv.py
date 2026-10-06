"""
Export Supply Chain Database to CSV files for Tableau Public
Creates CSV files from all production queries
"""

import sqlite3
import csv
import os
from pathlib import Path

# Connect to database
db_path = Path(__file__).parent.parent / 'supply_chain.db'
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Create outputs folder
output_folder = Path(__file__).parent.parent / 'outputs'
output_folder.mkdir(exist_ok=True)

print("📊 Exporting Supply Chain Data to CSV...\n")

# ============================================================================
# QUERY 1: SUPPLIER PERFORMANCE SCORECARD
# ============================================================================
query1 = """
SELECT
    s.supplier_id,
    s.supplier_name,
    COUNT(DISTINCT o.order_id) as total_orders,
    COUNT(sh.actual_arrival_date) as delivered_shipments,
    -- On-time = arrived on or before the date promised on the ORDER, measured
    -- only over shipments that have actually arrived. Undelivered shipments are
    -- excluded rather than counted as late.
    ROUND(SUM(CASE WHEN sh.actual_arrival_date IS NOT NULL AND sh.actual_arrival_date <= o.expected_delivery_date THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(sh.actual_arrival_date), 0), 2) as on_time_rate_pct,
    ROUND(AVG(o.order_cost), 2) as avg_order_cost,
    ROUND(SUM(o.order_cost), 2) as total_spend,
    s.quality_score,
    s.lead_time_days,
    ROUND(AVG(JULIANDAY(sh.actual_arrival_date) - JULIANDAY(o.expected_delivery_date)), 1) as avg_days_late
FROM suppliers s
LEFT JOIN orders o ON s.supplier_id = o.supplier_id
LEFT JOIN shipments sh ON o.order_id = sh.order_id
GROUP BY s.supplier_id, s.supplier_name, s.quality_score, s.lead_time_days
ORDER BY on_time_rate_pct DESC, total_spend DESC
"""

print("📈 Exporting: Supplier Performance...")
cursor.execute(query1)
rows = cursor.fetchall()
with open(output_folder / 'supplier_performance.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([desc[0] for desc in cursor.description])
    writer.writerows(rows)
print("✅ supplier_performance.csv")

# ============================================================================
# QUERY 2: INVENTORY OPTIMIZATION
# ============================================================================
query2 = """
SELECT
    p.product_id,
    p.product_name,
    p.category,
    i.quantity_on_hand,
    i.quantity_reserved,
    (i.quantity_on_hand - i.quantity_reserved) as available_quantity,
    p.reorder_point,
    ROUND((i.quantity_on_hand - i.quantity_reserved) / p.reorder_point, 2) as coverage_ratio,
    CASE
        WHEN (i.quantity_on_hand - i.quantity_reserved) < p.reorder_point THEN 'REORDER URGENT'
        WHEN (i.quantity_on_hand - i.quantity_reserved) < p.reorder_point * 1.5 THEN 'REORDER SOON'
        ELSE 'OK'
    END as reorder_status,
    s.supplier_name,
    s.lead_time_days
FROM products p
JOIN inventory i ON p.product_id = i.product_id
JOIN suppliers s ON p.supplier_id = s.supplier_id
ORDER BY
    CASE
        WHEN (i.quantity_on_hand - i.quantity_reserved) < p.reorder_point THEN 1
        WHEN (i.quantity_on_hand - i.quantity_reserved) < p.reorder_point * 1.5 THEN 2
        ELSE 3
    END,
    coverage_ratio ASC
"""

print("📦 Exporting: Inventory Status...")
cursor.execute(query2)
rows = cursor.fetchall()
with open(output_folder / 'inventory_status.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([desc[0] for desc in cursor.description])
    writer.writerows(rows)
print("✅ inventory_status.csv")

# ============================================================================
# QUERY 3: SHIPPING PERFORMANCE
# ============================================================================
query3 = """
SELECT
    sh.shipping_mode,
    COUNT(sh.shipment_id) as total_shipments,
    ROUND(AVG(JULIANDAY(sh.actual_arrival_date) - JULIANDAY(sh.shipment_date)), 1) as avg_days_in_transit,
    ROUND(MIN(JULIANDAY(sh.actual_arrival_date) - JULIANDAY(sh.shipment_date)), 1) as min_days,
    ROUND(MAX(JULIANDAY(sh.actual_arrival_date) - JULIANDAY(sh.shipment_date)), 1) as max_days,
    ROUND(AVG(sh.shipping_cost), 2) as avg_shipping_cost,
    ROUND(SUM(sh.shipping_cost), 2) as total_shipping_spend,
    SUM(CASE WHEN sh.actual_arrival_date <= o.expected_delivery_date THEN 1 ELSE 0 END) as on_time_count,
    -- Measured against the ORDER promise date, not the carrier's own ETA. The
    -- carrier ETA flatters economy shipping, whose quoted window is padded.
    ROUND(SUM(CASE WHEN sh.actual_arrival_date <= o.expected_delivery_date THEN 1 ELSE 0 END) * 100.0 / COUNT(sh.shipment_id), 2) as on_time_pct
FROM shipments sh
JOIN orders o ON sh.order_id = o.order_id
WHERE sh.actual_arrival_date IS NOT NULL
GROUP BY sh.shipping_mode
ORDER BY on_time_pct DESC
"""

print("🚚 Exporting: Shipping Performance...")
cursor.execute(query3)
rows = cursor.fetchall()
with open(output_folder / 'shipping_performance.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([desc[0] for desc in cursor.description])
    writer.writerows(rows)
print("✅ shipping_performance.csv")

# ============================================================================
# QUERY 4: COST VARIANCE ANALYSIS
# ============================================================================
query4 = """
SELECT
    s.supplier_name,
    COUNT(DISTINCT o.order_id) as order_count,
    SUM(o.order_cost) as actual_total_spend,
    SUM(o.quantity_ordered * p.unit_cost) as planned_total_cost,
    ROUND(SUM(o.order_cost) - SUM(o.quantity_ordered * p.unit_cost), 2) as cost_variance,
    ROUND((SUM(o.order_cost) - SUM(o.quantity_ordered * p.unit_cost)) / SUM(o.quantity_ordered * p.unit_cost) * 100, 2) as variance_pct,
    ROUND(AVG(o.order_cost), 2) as avg_order_cost
FROM orders o
JOIN suppliers s ON o.supplier_id = s.supplier_id
JOIN products p ON o.product_id = p.product_id
GROUP BY s.supplier_id, s.supplier_name
HAVING COUNT(DISTINCT o.order_id) > 0
ORDER BY variance_pct DESC
"""

print("💰 Exporting: Cost Variance Analysis...")
cursor.execute(query4)
rows = cursor.fetchall()
with open(output_folder / 'cost_variance.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([desc[0] for desc in cursor.description])
    writer.writerows(rows)
print("✅ cost_variance.csv")

# ============================================================================
# QUERY 5: ORDER FULFILLMENT CYCLE TIME
# ============================================================================
query5 = """
SELECT
    o.order_id,
    s.supplier_name,
    p.product_name,
    o.order_date,
    o.expected_delivery_date,
    sh.actual_arrival_date,
    ROUND(JULIANDAY(sh.shipment_date) - JULIANDAY(o.order_date), 1) as days_to_ship,
    ROUND(JULIANDAY(sh.actual_arrival_date) - JULIANDAY(sh.shipment_date), 1) as days_in_transit,
    ROUND(JULIANDAY(sh.actual_arrival_date) - JULIANDAY(o.order_date), 1) as total_cycle_time,
    CASE
        WHEN sh.actual_arrival_date <= o.expected_delivery_date THEN 'ON TIME'
        ELSE 'LATE'
    END as fulfillment_status,
    o.order_cost
FROM orders o
JOIN suppliers s ON o.supplier_id = s.supplier_id
JOIN products p ON o.product_id = p.product_id
JOIN shipments sh ON o.order_id = sh.order_id
WHERE sh.actual_arrival_date IS NOT NULL
ORDER BY o.order_date DESC
"""

print("⏱️  Exporting: Order Fulfillment Cycle Time...")
cursor.execute(query5)
rows = cursor.fetchall()
with open(output_folder / 'order_fulfillment_cycle.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([desc[0] for desc in cursor.description])
    writer.writerows(rows)
print("✅ order_fulfillment_cycle.csv")

# ============================================================================
# QUERY 6: LATE DELIVERY RISK ANALYSIS
# ============================================================================
query6 = """
SELECT
    s.supplier_name,
    sh.shipping_mode,
    COUNT(sh.shipment_id) as total_shipments,
    SUM(CASE WHEN sh.actual_arrival_date > o.expected_delivery_date THEN 1 ELSE 0 END) as late_shipments,
    ROUND(SUM(CASE WHEN sh.actual_arrival_date > o.expected_delivery_date THEN 1 ELSE 0 END) * 100.0 / COUNT(sh.shipment_id), 2) as late_delivery_risk_pct,
    ROUND(AVG(CASE WHEN sh.actual_arrival_date > o.expected_delivery_date THEN JULIANDAY(sh.actual_arrival_date) - JULIANDAY(o.expected_delivery_date) ELSE 0 END), 1) as avg_days_late
FROM shipments sh
JOIN orders o ON sh.order_id = o.order_id
JOIN suppliers s ON o.supplier_id = s.supplier_id
WHERE sh.actual_arrival_date IS NOT NULL
GROUP BY s.supplier_name, sh.shipping_mode
ORDER BY late_delivery_risk_pct DESC
"""

print("⚠️  Exporting: Late Delivery Risk...")
cursor.execute(query6)
rows = cursor.fetchall()
with open(output_folder / 'late_delivery_risk.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([desc[0] for desc in cursor.description])
    writer.writerows(rows)
print("✅ late_delivery_risk.csv")

# ============================================================================
# QUERY 7: INVENTORY TURNOVER & HOLDING COSTS
# ============================================================================
query7 = """
SELECT
    p.product_name,
    p.category,
    i.quantity_on_hand,
    COUNT(DISTINCT o.order_id) as orders_count_6m,
    ROUND(COUNT(DISTINCT o.order_id) / 6.0, 2) as avg_orders_per_month,
    CASE
        WHEN COUNT(DISTINCT o.order_id) > 0 THEN ROUND(i.quantity_on_hand / (COUNT(DISTINCT o.order_id) / 6.0), 1)
        ELSE NULL
    END as months_of_inventory,
    ROUND(i.quantity_on_hand * p.unit_cost * 0.05, 2) as estimated_holding_cost_monthly
FROM products p
JOIN inventory i ON p.product_id = i.product_id
LEFT JOIN orders o ON p.product_id = o.product_id
GROUP BY p.product_id, p.product_name, p.category, i.quantity_on_hand, p.unit_cost
ORDER BY avg_orders_per_month DESC
"""

print("📊 Exporting: Inventory Turnover & Holding Costs...")
cursor.execute(query7)
rows = cursor.fetchall()
with open(output_folder / 'inventory_turnover.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([desc[0] for desc in cursor.description])
    writer.writerows(rows)
print("✅ inventory_turnover.csv")

# ============================================================================
# QUERY 8: SUPPLIER CONCENTRATION RISK
# ============================================================================
query8 = """
SELECT
    s.supplier_name,
    COUNT(DISTINCT o.order_id) as total_orders,
    ROUND(SUM(o.order_cost), 2) as total_spend,
    ROUND(SUM(o.order_cost) / (SELECT SUM(order_cost) FROM orders) * 100, 2) as spend_concentration_pct,
    ROUND(COUNT(DISTINCT o.order_id) / (SELECT COUNT(DISTINCT order_id) FROM orders) * 100, 2) as order_concentration_pct,
    CASE
        WHEN ROUND(SUM(o.order_cost) / (SELECT SUM(order_cost) FROM orders) * 100, 2) > 20 THEN 'HIGH RISK'
        WHEN ROUND(SUM(o.order_cost) / (SELECT SUM(order_cost) FROM orders) * 100, 2) > 10 THEN 'MEDIUM RISK'
        ELSE 'LOW RISK'
    END as concentration_risk_level
FROM suppliers s
LEFT JOIN orders o ON s.supplier_id = o.supplier_id
GROUP BY s.supplier_id, s.supplier_name
ORDER BY total_spend DESC
"""

print("🎯 Exporting: Supplier Concentration Risk...")
cursor.execute(query8)
rows = cursor.fetchall()
with open(output_folder / 'supplier_concentration_risk.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([desc[0] for desc in cursor.description])
    writer.writerows(rows)
print("✅ supplier_concentration_risk.csv")

print("\n" + "="*70)
print("✅ ALL CSV FILES EXPORTED SUCCESSFULLY!")
print("="*70)
print(f"\n📁 CSV Files Location: {output_folder}")
print("\n📊 Files created:")
print("   1. supplier_performance.csv")
print("   2. inventory_status.csv")
print("   3. shipping_performance.csv")
print("   4. cost_variance.csv")
print("   5. order_fulfillment_cycle.csv")
print("   6. late_delivery_risk.csv")
print("   7. inventory_turnover.csv")
print("   8. supplier_concentration_risk.csv")
print("\n🎯 Next Steps for Tableau Public:")
print("   1. Open Tableau Public")
print("   2. Click 'Create' → 'Visualizations'")
print("   3. For each CSV file:")
print("      - Click 'Connect to Data'")
print("      - Select 'Text File' (CSV)")
print("      - Browse to the CSV file")
print("      - Create sheets and dashboards")
print("\n" + "="*70 + "\n")

conn.close()

-- ============================================================================
-- SUPPLY CHAIN ANALYSIS QUERIES
-- 8 production queries + 3 supporting queries against supply_chain.db
-- ============================================================================
--
-- METRIC DEFINITIONS (applied consistently across every query below and in
-- the Tableau workbook, so the same question always returns the same answer):
--
--   on-time   An order arrived on or before orders.expected_delivery_date --
--             the date promised to whoever raised the requisition. Measured
--             ONLY over shipments that have actually arrived. Shipments still
--             in transit are excluded from the denominator, not counted late.
--
--             Deliberately NOT shipments.expected_arrival_date. That is the
--             carrier's own ETA after pickup, which is padded differently by
--             mode -- scoring against it rates economy shipping highest
--             (77%) and overnight lowest (47%), inverting the real ranking.
--             Against the order promise date the ranking is overnight 90.4%,
--             express 88.3%, standard 84.8%, economy 75.8%.
--
--   spend     orders.order_cost, actual not planned.
--
--   on-time rate at portfolio level is shipment-weighted (84.3%), not an
--   unweighted mean of per-supplier rates (81.4%) -- the unweighted figure
--   lets a supplier with 20 orders move the number as much as one with 300.
-- ============================================================================

-- ============================================================================
-- QUERY 1: SUPPLIER PERFORMANCE SCORECARD
-- Purpose: Evaluate supplier reliability, cost, quality
-- Used by: L3Harris (Program Management), Target, Hopkins
-- ============================================================================
SELECT
    s.supplier_id,
    s.supplier_name,
    COUNT(DISTINCT o.order_id) as total_orders,
    COUNT(sh.actual_arrival_date) as delivered_shipments,
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
ORDER BY on_time_rate_pct DESC, total_spend DESC;

-- ============================================================================
-- QUERY 2: INVENTORY OPTIMIZATION ANALYSIS
-- Purpose: Identify reorder needs and inventory health
-- Used by: Target (Inventory Management), Hopkins
-- ============================================================================
SELECT
    p.product_id,
    p.product_name,
    p.category,
    i.quantity_on_hand,
    i.quantity_reserved,
    (i.quantity_on_hand - i.quantity_reserved) as available_quantity,
    p.reorder_point,
    ROUND((i.quantity_on_hand - i.quantity_reserved) * 1.0 / NULLIF(p.reorder_point, 0), 2) as coverage_ratio,
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
    coverage_ratio ASC;

-- ============================================================================
-- QUERY 3: DELIVERY PERFORMANCE BY SHIPPING MODE
-- Purpose: Compare speed, cost, reliability by shipping method
-- Used by: Target (Operations), L3Harris
-- ============================================================================
SELECT
    sh.shipping_mode,
    COUNT(sh.shipment_id) as total_shipments,
    ROUND(AVG(JULIANDAY(sh.actual_arrival_date) - JULIANDAY(sh.shipment_date)), 1) as avg_days_in_transit,
    ROUND(MIN(JULIANDAY(sh.actual_arrival_date) - JULIANDAY(sh.shipment_date)), 1) as min_days,
    ROUND(MAX(JULIANDAY(sh.actual_arrival_date) - JULIANDAY(sh.shipment_date)), 1) as max_days,
    ROUND(AVG(sh.shipping_cost), 2) as avg_shipping_cost,
    ROUND(SUM(sh.shipping_cost), 2) as total_shipping_spend,
    SUM(CASE WHEN sh.actual_arrival_date <= o.expected_delivery_date THEN 1 ELSE 0 END) as on_time_count,
    ROUND(SUM(CASE WHEN sh.actual_arrival_date <= o.expected_delivery_date THEN 1 ELSE 0 END) * 100.0 / COUNT(sh.shipment_id), 2) as on_time_pct
FROM shipments sh
JOIN orders o ON sh.order_id = o.order_id
WHERE sh.actual_arrival_date IS NOT NULL
GROUP BY sh.shipping_mode
ORDER BY on_time_pct DESC;

-- ============================================================================
-- QUERY 4: COST VARIANCE ANALYSIS
-- Purpose: Track actual vs. planned spend by supplier
-- Used by: L3Harris (Program Management), Target
-- ============================================================================
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
ORDER BY variance_pct DESC;

-- ============================================================================
-- QUERY 5: ORDER FULFILLMENT CYCLE TIME
-- Purpose: Measure order-to-delivery timeline
-- Used by: Target (Operations), L3Harris
-- ============================================================================
SELECT
    o.order_id,
    o.order_date,
    sh.shipment_date,
    sh.actual_arrival_date,
    ROUND(JULIANDAY(sh.actual_arrival_date) - JULIANDAY(o.order_date), 0) as total_cycle_days,
    ROUND(JULIANDAY(sh.shipment_date) - JULIANDAY(o.order_date), 0) as days_to_ship,
    ROUND(JULIANDAY(sh.actual_arrival_date) - JULIANDAY(sh.shipment_date), 0) as days_in_transit,
    s.supplier_name,
    sh.shipping_mode,
    CASE
        WHEN JULIANDAY(sh.actual_arrival_date) - JULIANDAY(o.order_date) <= 14 THEN 'Fast (<=14 days)'
        WHEN JULIANDAY(sh.actual_arrival_date) - JULIANDAY(o.order_date) <= 30 THEN 'Normal (15-30 days)'
        ELSE 'Slow (>30 days)'
    END as speed_category
FROM orders o
JOIN shipments sh ON o.order_id = sh.order_id
JOIN suppliers s ON o.supplier_id = s.supplier_id
WHERE sh.actual_arrival_date IS NOT NULL
ORDER BY total_cycle_days DESC;

-- ============================================================================
-- QUERY 6: LATE DELIVERY RISK ANALYSIS
-- Purpose: Calculate late delivery percentage by supplier and shipping mode
-- Used by: All companies (risk management)
-- ============================================================================
SELECT
    s.supplier_name,
    sh.shipping_mode,
    COUNT(sh.shipment_id) as total_shipments,
    SUM(CASE WHEN sh.actual_arrival_date > o.expected_delivery_date THEN 1 ELSE 0 END) as late_shipments,
    ROUND(SUM(CASE WHEN sh.actual_arrival_date > o.expected_delivery_date THEN 1 ELSE 0 END) * 100.0 / COUNT(sh.shipment_id), 2) as late_delivery_risk_pct,
    ROUND(AVG(CASE WHEN sh.actual_arrival_date > o.expected_delivery_date THEN JULIANDAY(sh.actual_arrival_date) - JULIANDAY(o.expected_delivery_date) ELSE 0 END), 1) as avg_days_late,
    ROUND(MAX(JULIANDAY(sh.actual_arrival_date) - JULIANDAY(o.expected_delivery_date)), 0) as max_days_late
FROM shipments sh
JOIN orders o ON sh.order_id = o.order_id
JOIN suppliers s ON o.supplier_id = s.supplier_id
WHERE sh.actual_arrival_date IS NOT NULL
GROUP BY s.supplier_id, s.supplier_name, sh.shipping_mode
ORDER BY late_delivery_risk_pct DESC;

-- ============================================================================
-- QUERY 7: INVENTORY TURNOVER & HOLDING COSTS
-- Purpose: Measure inventory efficiency and carrying costs
-- Used by: Target (Supply Chain), Hopkins
-- ============================================================================
SELECT
    p.product_id,
    p.product_name,
    p.category,
    COUNT(o.order_id) as units_ordered,
    i.quantity_on_hand,
    ROUND(i.quantity_on_hand / (COUNT(o.order_id) / 6.0 + 0.1), 1) as estimated_months_on_hand,
    ROUND((COUNT(o.order_id) / 6.0) / (i.quantity_on_hand + 0.1), 2) as turnover_ratio_6mo,
    ROUND(i.quantity_on_hand * p.unit_cost, 2) as inventory_value,
    ROUND(i.quantity_on_hand * p.unit_cost * 0.25 / 12, 2) as estimated_monthly_holding_cost
FROM products p
JOIN inventory i ON p.product_id = i.product_id
LEFT JOIN orders o ON p.product_id = o.product_id
GROUP BY p.product_id, p.product_name, p.category, p.unit_cost, i.quantity_on_hand
ORDER BY estimated_monthly_holding_cost DESC;

-- ============================================================================
-- QUERY 8: SUPPLIER CONCENTRATION RISK
-- Purpose: Identify over-reliance on single suppliers
-- Used by: Target (Risk Mitigation), L3Harris
-- ============================================================================
SELECT
    s.supplier_id,
    s.supplier_name,
    COUNT(DISTINCT p.product_id) as products_supplied,
    COUNT(DISTINCT o.order_id) as total_orders,
    ROUND(SUM(o.order_cost), 2) as supplier_spend,
    ROUND(SUM(o.order_cost) * 100.0 / (SELECT SUM(order_cost) FROM orders WHERE actual_delivery_date IS NOT NULL), 2) as pct_of_total_spend,
    CASE
        WHEN ROUND(SUM(o.order_cost) * 100.0 / (SELECT SUM(order_cost) FROM orders WHERE actual_delivery_date IS NOT NULL), 2) > 30 THEN 'HIGH RISK - DIVERSIFY'
        WHEN ROUND(SUM(o.order_cost) * 100.0 / (SELECT SUM(order_cost) FROM orders WHERE actual_delivery_date IS NOT NULL), 2) > 15 THEN 'MEDIUM RISK'
        ELSE 'LOW RISK'
    END as concentration_risk
FROM suppliers s
LEFT JOIN orders o ON s.supplier_id = o.supplier_id
LEFT JOIN products p ON s.supplier_id = p.supplier_id
GROUP BY s.supplier_id, s.supplier_name
HAVING COUNT(DISTINCT o.order_id) > 0
ORDER BY pct_of_total_spend DESC;

-- ============================================================================
-- BONUS QUERIES - Additional analysis
-- ============================================================================

-- BONUS QUERY A: YTD PERFORMANCE SUMMARY
-- Quick snapshot of current year-to-date performance
SELECT
    'YTD Performance Snapshot' as metric,
    (SELECT COUNT(*) FROM orders) as total_orders,
    (SELECT COUNT(*) FROM orders WHERE actual_delivery_date IS NOT NULL) as completed_orders,
    ROUND((SELECT SUM(order_cost) FROM orders), 2) as total_spend,
    ROUND((SELECT AVG(order_cost) FROM orders), 2) as avg_order_value,
    (SELECT COUNT(*) FROM suppliers) as active_suppliers,
    (SELECT COUNT(*)
       FROM inventory i
       JOIN products p ON p.product_id = i.product_id
      WHERE (i.quantity_on_hand - i.quantity_reserved) < p.reorder_point
    ) as products_needing_reorder;

-- BONUS QUERY B: TOP 5 MOST EXPENSIVE ORDERS
SELECT
    o.order_id,
    o.order_date,
    s.supplier_name,
    p.product_name,
    o.quantity_ordered,
    ROUND(o.order_cost, 2) as order_cost,
    o.order_status
FROM orders o
JOIN suppliers s ON o.supplier_id = s.supplier_id
JOIN products p ON o.product_id = p.product_id
ORDER BY o.order_cost DESC
LIMIT 5;

-- BONUS QUERY C: OVERDUE ORDERS (still pending)
SELECT
    o.order_id,
    o.order_date,
    o.expected_delivery_date,
    s.supplier_name,
    p.product_name,
    o.quantity_ordered,
    ROUND(o.order_cost, 2) as order_cost,
    ROUND(JULIANDAY('2026-09-22') - JULIANDAY(o.expected_delivery_date), 0) as days_overdue
FROM orders o
JOIN suppliers s ON o.supplier_id = s.supplier_id
JOIN products p ON o.product_id = p.product_id
WHERE o.actual_delivery_date IS NULL
  AND DATE(o.expected_delivery_date) < DATE('2026-09-22')
ORDER BY days_overdue DESC;

-- ============================================================================
-- END OF QUERIES
-- ============================================================================

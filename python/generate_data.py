#!/usr/bin/env python3
"""
generate_data.py — Supply chain dataset generator.

Builds 24 months of synthetic but internally consistent supply chain history
into supply_chain.db, using the existing schema in database/schema.sql.

The data is deliberately NOT uniform random. Several patterns are planted so
that the Tableau dashboards have real findings to surface. See PLANTED
PATTERNS below.

Deterministic: SEED is fixed, so regenerating reproduces the exact same
database. Screenshots, README figures and interview talking points stay valid.

Usage:  python3 python/generate_data.py
"""

import sqlite3
import random
import os
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# PLANTED PATTERNS (what the dashboards should be able to discover)
# ---------------------------------------------------------------------------
# 1. DEGRADING SUPPLIER  - Shenzhen Precision Mfg: on-time slides ~0.94 -> ~0.58
#                          across 24 months while lead time grows 28 -> 45 days.
#                          It is also a top-3 spend supplier and sole source for
#                          several SKUs. This is the "which suppliers could
#                          break us" headline.
# 2. SEASONALITY         - Q4 (Oct-Dec) order volume ~1.5x baseline, January dips.
# 3. CHEAP-BUT-UNRELIABLE- 'economy' shipping is the cheapest per order and has
#    SHIPPING MODE         the worst on-time rate and longest transit. Drives the
#                          cost-vs-speed scatter on the Logistics page.
# 4. SPEND CONCENTRATION - Top 5 suppliers carry ~60% of spend (Pareto).
# 5. SKU CONCENTRATION   - ~20% of SKUs carry ~80% of inventory value.
# 6. COST VARIANCE       - Meridian Components drifts progressively over planned
#                          cost; most other suppliers hold near zero variance.
# 7. QUADRANT STRUCTURE  - Suppliers deliberately populate all four quadrants of
#                          (lead time variability x on-time rate).
# 8. SLOW-MOVING STOCK   - A handful of high-unit-cost SKUs are heavily
#                          overstocked (capital tied up), while ~15% of SKUs sit
#                          below their reorder point.
# 9. TAIL-SUPPLIER TRAP  - Some tiny suppliers have terrible metrics but
#                          negligible spend. Risk must be weighted by spend, or
#                          they wrongly dominate the risk view.
# ---------------------------------------------------------------------------

SEED = 42
random.seed(SEED)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# Optional override: some network/FUSE-mounted folders don't support SQLite's
# file locking, so the DB can be built elsewhere and copied into place.
#   python3 python/generate_data.py [output_db_path]
import sys
DB_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "supply_chain.db")
SCHEMA_PATH = os.path.join(ROOT, "database", "schema.sql")

START_DATE = date(2024, 10, 1)
END_DATE = date(2026, 9, 30)
TARGET_ORDERS = 3200

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

LOCATIONS = [
    ("China", "Shenzhen"), ("China", "Suzhou"), ("Vietnam", "Hanoi"),
    ("Taiwan", "Taipei"), ("South Korea", "Busan"), ("Japan", "Osaka"),
    ("Germany", "Stuttgart"), ("Sweden", "Gothenburg"), ("Poland", "Wroclaw"),
    ("Mexico", "Monterrey"), ("USA", "Austin"), ("USA", "Columbus"),
    ("USA", "Reno"), ("India", "Pune"), ("Malaysia", "Penang"),
]

CATEGORIES = [
    "Electronics", "Storage", "Components", "Cables", "Accessories",
    "Peripherals", "Hardware", "Stationery", "Furniture",
]

WAREHOUSES = [
    "Baltimore DC", "Atlanta DC", "Dallas DC", "Reno DC", "Columbus DC",
]

# shipping_mode -> (min_transit, max_transit, base_cost, per_unit_cost,
#                   reliability, [carriers], selection_weight, value_rate)
#
# value_rate is freight charged as a share of the goods' value. Real freight
# runs roughly 3-8% of procurement spend; a flat per-unit charge alone leaves
# freight at well under 1%, which reads as fake on a logistics dashboard.
SHIP_MODES = {
    "overnight": (1, 2, 180.0, 2.20, 0.97, ["FirstClass Delivery", "AeroLink"], 0.10, 0.052),
    "express":   (3, 7, 85.0, 1.10, 0.91, ["Express Logistics Co", "SwiftFreight"], 0.28, 0.034),
    "standard":  (8, 16, 35.0, 0.45, 0.86, ["Continental Freight", "RailBridge Logistics"], 0.37, 0.021),
    "economy":   (18, 35, 12.0, 0.18, 0.68, ["OceanWay Shipping", "GlobalSea Freight"], 0.25, 0.011),
}

# ---------------------------------------------------------------------------
# Suppliers — hand-built "story" suppliers first, then generated filler
# ---------------------------------------------------------------------------
# fields: name, country, city, base_on_time, lead_time, lead_var, quality,
#         spend_weight, tags
STORY_SUPPLIERS = [
    # The headline risk: big spend, sole-source, and visibly degrading.
    dict(name="Shenzhen Precision Mfg", country="China", city="Shenzhen",
         on_time=0.94, lead=28, lead_var=9, quality=4, weight=14.0,
         tags={"degrading"}),
    # The anchor: biggest spend, dependable, unremarkable.
    dict(name="Global Tech Supply", country="Taiwan", city="Taipei",
         on_time=0.91, lead=21, lead_var=4, quality=4, weight=16.0, tags=set()),
    # Reliable but slow and expensive — top-left quadrant.
    dict(name="Nordic Quality AB", country="Sweden", city="Gothenburg",
         on_time=0.96, lead=35, lead_var=3, quality=5, weight=9.0,
         tags={"premium"}),
    # Fast but sloppy — bottom-left quadrant.
    dict(name="Rapid Parts Express", country="USA", city="Reno",
         on_time=0.82, lead=7, lead_var=2, quality=2, weight=8.0, tags=set()),
    # The cost-variance offender.
    dict(name="Meridian Components", country="Mexico", city="Monterrey",
         on_time=0.88, lead=18, lead_var=5, quality=3, weight=10.0,
         tags={"cost_drift"}),
    # Solid mid-tier spread
    dict(name="Pacific Rim Industrial", country="Vietnam", city="Hanoi",
         on_time=0.87, lead=32, lead_var=11, quality=3, weight=5.5, tags=set()),
    dict(name="Stuttgart Werke GmbH", country="Germany", city="Stuttgart",
         on_time=0.93, lead=26, lead_var=4, quality=5, weight=5.0,
         tags={"premium"}),
    dict(name="Osaka Micro Systems", country="Japan", city="Osaka",
         on_time=0.95, lead=24, lead_var=3, quality=5, weight=4.5, tags=set()),
    # Erratic: high lead-time variability, poor on-time — top-right danger zone.
    dict(name="Penang Assembly Partners", country="Malaysia", city="Penang",
         on_time=0.74, lead=38, lead_var=16, quality=2, weight=4.0, tags=set()),
    dict(name="Wroclaw Fabrication", country="Poland", city="Wroclaw",
         on_time=0.90, lead=20, lead_var=5, quality=4, weight=3.5, tags=set()),
]

# Tail suppliers: bad metrics, negligible spend. The "risk must be weighted by
# spend" trap.
TAIL_SUPPLIERS = [
    dict(name="Budget Source Imports", country="China", city="Suzhou",
         on_time=0.61, lead=46, lead_var=18, quality=1, weight=0.5, tags=set()),
    dict(name="Lowcost Direct Ltd", country="India", city="Pune",
         on_time=0.66, lead=42, lead_var=15, quality=2, weight=0.4, tags=set()),
    dict(name="Quickship Surplus", country="USA", city="Columbus",
         on_time=0.70, lead=9, lead_var=6, quality=1, weight=0.6, tags=set()),
]

FILLER_NAMES = [
    "Apex Industrial Group", "Brightline Manufacturing", "Cascade Supply Partners",
    "Delta Point Components", "Eastgate Trading Co", "Fairmount Industrial",
    "Granite Peak Supply", "Harborview Components", "Ironwood Manufacturing",
    "Junction Supply Group", "Keystone Fabrication", "Lakeside Industrial",
    "Northbridge Components", "Oakfield Supply Co", "Pinnacle Parts Group",
    "Riverstone Industrial", "Summit Line Supply",
]


def build_suppliers():
    suppliers = []
    for s in STORY_SUPPLIERS + TAIL_SUPPLIERS:
        suppliers.append(dict(s))
    for name in FILLER_NAMES:
        country, city = random.choice(LOCATIONS)
        suppliers.append(dict(
            name=name, country=country, city=city,
            on_time=round(random.uniform(0.78, 0.95), 3),
            lead=random.randint(8, 42),
            lead_var=random.randint(2, 12),
            quality=random.choice([2, 3, 3, 4, 4, 5]),
            weight=round(random.uniform(0.6, 1.8), 2),
            tags=set(),
        ))
    return suppliers


PRODUCT_WORDS = {
    "Electronics": ["CPU Processor", "GPU Module", "Power Supply Unit", "Logic Board",
                    "Sensor Array", "Controller Chip", "Display Panel", "Audio Module"],
    "Storage": ["SSD 1TB", "SSD 4TB", "HDD 8TB", "NVMe Drive 2TB", "Memory Card 512GB",
                "RAM Memory 32GB", "RAM Memory 64GB"],
    "Components": ["Cooling Fan", "Heat Sink", "Capacitor Pack", "Voltage Regulator",
                   "Circuit Breaker", "Relay Switch", "Bearing Assembly"],
    "Cables": ["HDMI Cable 2m", "USB-C Cable", "Ethernet Cable Cat6", "Power Cord",
               "Fiber Optic Patch", "Ribbon Connector"],
    "Accessories": ["Mouse Wireless", "Keyboard Mechanical", "Webcam HD", "Headset Stereo",
                    "Docking Station", "Carry Case"],
    "Peripherals": ["Laser Printer", "Barcode Scanner", "Label Printer", "Monitor 27in",
                    "Monitor 32in", "Scanner Flatbed"],
    "Hardware": ["Mounting Bracket", "Rack Rail Kit", "Fastener Set", "Enclosure Panel",
                 "Cable Tray", "Server Chassis"],
    "Stationery": ["Shipping Label Roll", "Packing Tape", "Document Sleeve",
                   "Inventory Tag Pack", "Marker Set"],
    "Furniture": ["Workbench Steel", "Shelving Unit", "Storage Cabinet", "Rolling Cart",
                  "Office Chair", "Standing Desk"],
}

COST_BANDS = {
    "Electronics": (120, 2400), "Storage": (60, 900), "Components": (8, 320),
    "Cables": (3, 45), "Accessories": (15, 180), "Peripherals": (140, 1800),
    "Hardware": (10, 420), "Stationery": (2, 28), "Furniture": (90, 1200),
}


def build_products(suppliers):
    products = []
    pid = 0
    for cat, names in PRODUCT_WORDS.items():
        lo, hi = COST_BANDS[cat]
        for nm in names:
            pid += 1
            unit_cost = round(random.uniform(lo, hi), 2)
            products.append(dict(
                product_id=pid,
                name=nm,
                category=cat,
                unit_cost=unit_cost,
                reorder_point=random.choice([25, 40, 50, 60, 75, 100, 120]),
                sku=f"SKU-{cat[:3].upper()}-{pid:04d}",
                # Pareto popularity: a few SKUs dominate order volume
                popularity=None,  # assigned below
                single_source=False,
                primary_supplier=None,
            ))
    # PLANTED: Zipf popularity curve. Smooth and bounded, so ~20% of SKUs carry
    # most of the volume without any single SKU dominating the whole dataset.
    ranks = list(range(len(products)))
    random.shuffle(ranks)
    for rank, idx in enumerate(ranks, start=1):
        products[idx]["popularity"] = 1.0 / (rank ** 0.75)

    # Assign primary suppliers weighted by spend weight
    weights = [s["weight"] for s in suppliers]
    for p in products:
        p["primary_supplier"] = random.choices(range(len(suppliers)), weights=weights)[0]

    # PLANTED: sole-source a set of SKUs, several of them on the degrading
    # supplier, so single-source risk and supplier degradation overlap.
    degrading_idx = next(i for i, s in enumerate(suppliers) if "degrading" in s["tags"])
    # Sole-source the degrading supplier's HIGHEST-VOLUME SKUs, not random ones.
    # That is what makes the exposure material: the supplier we most need to
    # replace is the one we cannot replace without re-sourcing real volume.
    degrading_products = sorted(
        [p for p in products if p["primary_supplier"] == degrading_idx],
        key=lambda x: -x["popularity"])
    for p in degrading_products[:6]:
        p["single_source"] = True
    others = [p for p in products if p["primary_supplier"] != degrading_idx]
    for p in random.sample(others, 7):
        p["single_source"] = True
    return products


def month_index(d):
    return (d.year - START_DATE.year) * 12 + (d.month - START_DATE.month)


TOTAL_MONTHS = month_index(END_DATE) + 1


def seasonal_multiplier(d):
    """PLANTED: Q4 peak, January trough, mild year-over-year growth."""
    m = d.month
    if m in (10, 11, 12):
        season = 1.5
    elif m == 1:
        season = 0.78
    elif m in (6, 7):
        season = 0.92
    else:
        season = 1.0
    growth = 1.0 + 0.15 * (month_index(d) / TOTAL_MONTHS)
    return season * growth


def supplier_on_time_at(sup, d):
    """PLANTED: the degrading supplier's reliability decays over the window."""
    base = sup["on_time"]
    if "degrading" in sup["tags"]:
        progress = month_index(d) / max(TOTAL_MONTHS - 1, 1)
        base = 0.94 - 0.36 * progress          # 0.94 -> 0.58
    return max(0.30, min(0.99, base))


def supplier_lead_at(sup, d):
    """The degrading supplier's lead time also stretches."""
    lead = sup["lead"]
    if "degrading" in sup["tags"]:
        progress = month_index(d) / max(TOTAL_MONTHS - 1, 1)
        lead = 28 + 17 * progress              # 28 -> 45 days
    jitter = random.gauss(0, sup["lead_var"] / 3.0)
    return max(2, int(round(lead + jitter)))


def pick_shipping_mode(order_value):
    """Higher-value orders skew toward faster modes; economy carries the tail."""
    modes = list(SHIP_MODES.keys())
    weights = []
    for m in modes:
        w = SHIP_MODES[m][6]
        if order_value > 20000:
            w *= {"overnight": 2.4, "express": 1.7, "standard": 0.9, "economy": 0.35}[m]
        elif order_value < 2000:
            w *= {"overnight": 0.3, "express": 0.7, "standard": 1.1, "economy": 1.8}[m]
        weights.append(w)
    return random.choices(modes, weights=weights)[0]


def main():
    # schema.sql begins with DROP TABLE IF EXISTS for every table, so we
    # rebuild in place rather than deleting the file.
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())

    suppliers = build_suppliers()
    products = build_products(suppliers)

    # -- suppliers -----------------------------------------------------------
    for i, s in enumerate(suppliers, start=1):
        s["id"] = i
        sup_products = [p["unit_cost"] for p in products
                        if p["primary_supplier"] == i - 1]
        cost_per_unit = round(sum(sup_products) / len(sup_products), 2) if sup_products \
            else round(random.uniform(20, 400), 2)
        slug = s["name"].lower().replace(" ", "").replace(",", "")[:18]
        conn.execute(
            """INSERT INTO suppliers (supplier_id, supplier_name, country, city,
               on_time_rate, lead_time_days, cost_per_unit, contract_end_date,
               quality_score, phone, email)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (i, s["name"], s["country"], s["city"], s["on_time"], s["lead"],
             cost_per_unit,
             (END_DATE + timedelta(days=random.randint(30, 900))).isoformat(),
             s["quality"],
             f"+1-555-{random.randint(1000, 9999)}",
             f"orders@{slug}.com"),
        )

    # -- products ------------------------------------------------------------
    for p in products:
        conn.execute(
            """INSERT INTO products (product_id, product_name, category, unit_cost,
               reorder_point, supplier_id, sku, description)
               VALUES (?,?,?,?,?,?,?,?)""",
            (p["product_id"], p["name"], p["category"], p["unit_cost"],
             p["reorder_point"], p["primary_supplier"] + 1, p["sku"],
             f"{p['category']} item"
             + (" (single-source)" if p["single_source"] else "")),
        )

    # -- orders + shipments --------------------------------------------------
    # Build a per-day order schedule honouring seasonality.
    days = (END_DATE - START_DATE).days + 1
    day_weights = []
    for n in range(days):
        d = START_DATE + timedelta(days=n)
        w = 0.0 if d.weekday() >= 5 else seasonal_multiplier(d)
        day_weights.append(w)
    total_w = sum(day_weights)
    order_days = []
    for n, w in enumerate(day_weights):
        count = int(round(TARGET_ORDERS * w / total_w))
        order_days.extend([START_DATE + timedelta(days=n)] * count)

    # Precompute, per supplier, the products it may fulfil: anything that is not
    # single-sourced elsewhere, plus its own single-source SKUs.
    sup_weights = [s["weight"] for s in suppliers]
    allowed_products, allowed_weights = [], []
    for si in range(len(suppliers)):
        allowed = [p for p in products
                   if not p["single_source"] or p["primary_supplier"] == si]
        allowed_products.append(allowed)
        allowed_weights.append([p["popularity"] for p in allowed])
    order_id = 0
    shipment_id = 0

    for od in order_days:
        order_id += 1
        # Supplier first (weighted by intended spend share), then a product that
        # supplier is allowed to fulfil. Choosing in this order keeps each
        # supplier's spend close to its intended weight; choosing the product
        # first lets one popular SKU drag its supplier to the top of the Pareto.
        sup_idx = random.choices(range(len(suppliers)), weights=sup_weights)[0]
        sup = suppliers[sup_idx]
        p = random.choices(allowed_products[sup_idx],
                           weights=allowed_weights[sup_idx])[0]

        qty = max(1, int(random.lognormvariate(3.1, 0.85)))
        planned_unit = p["unit_cost"]

        # PLANTED: cost drift for the offender; small noise for everyone else.
        drift = 1.0
        if "cost_drift" in sup["tags"]:
            drift = 1.0 + 0.12 * (month_index(od) / max(TOTAL_MONTHS - 1, 1)) \
                + random.gauss(0, 0.03)
        elif "premium" in sup["tags"]:
            drift = 1.0 + random.gauss(0.01, 0.015)
        else:
            drift = 1.0 + random.gauss(0.0, 0.025)
        actual_unit = max(0.01, planned_unit * drift)
        order_cost = round(qty * actual_unit, 2)

        lead = supplier_lead_at(sup, od)
        expected_delivery = od + timedelta(days=lead)

        mode = pick_shipping_mode(order_cost)
        (t_min, t_max, base_c, per_unit_c, mode_rel,
         carriers, _, value_rate) = SHIP_MODES[mode]

        # Combined reliability: supplier and shipping mode each contribute.
        sup_rel = supplier_on_time_at(sup, od)
        p_on_time = 1.0 - (1.0 - sup_rel) * 0.75 - (1.0 - mode_rel) * 0.55
        p_on_time = max(0.25, min(0.985, p_on_time))
        on_time = random.random() < p_on_time

        if on_time:
            actual_delivery = expected_delivery - timedelta(days=random.randint(0, 4))
        else:
            actual_delivery = expected_delivery + timedelta(
                days=int(max(1, random.lognormvariate(1.5, 0.8))))

        # Shipment dates are derived so they stay consistent with delivery:
        # arrival == delivery, and transit respects the mode's range.
        transit = random.randint(t_min, t_max)
        if not on_time:
            transit += random.randint(0, 6)
        shipment_date = actual_delivery - timedelta(days=transit)
        if shipment_date <= od:
            shipment_date = od + timedelta(days=1)
            transit = max(1, (actual_delivery - shipment_date).days)
        expected_arrival = shipment_date + timedelta(days=(t_min + t_max) // 2)

        shipping_cost = round(base_c + per_unit_c * qty
                              + value_rate * order_cost
                              + random.gauss(0, base_c * 0.08), 2)
        shipping_cost = max(5.0, shipping_cost)

        if actual_delivery <= END_DATE:
            status = "delivered"
            ship_status = "delivered"
            actual_delivery_val = actual_delivery.isoformat()
            actual_arrival_val = actual_delivery.isoformat()
        else:
            status = "in_transit"
            ship_status = "in_transit"
            actual_delivery_val = None
            actual_arrival_val = None

        conn.execute(
            """INSERT INTO orders (order_id, order_date, product_id, supplier_id,
               quantity_ordered, order_status, expected_delivery_date,
               actual_delivery_date, order_cost, po_number)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (order_id, od.isoformat(), p["product_id"], sup["id"], qty, status,
             expected_delivery.isoformat(), actual_delivery_val, order_cost,
             f"PO-{od.year}-{order_id:05d}"),
        )

        # A small share of orders have no shipment record yet (just placed).
        if shipment_date <= END_DATE:
            shipment_id += 1
            conn.execute(
                """INSERT INTO shipments (shipment_id, order_id, shipment_date,
                   expected_arrival_date, actual_arrival_date, shipping_mode,
                   shipping_cost, carrier, tracking_number, shipment_status)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (shipment_id, order_id, shipment_date.isoformat(),
                 expected_arrival.isoformat(), actual_arrival_val, mode,
                 shipping_cost, random.choice(carriers),
                 f"TRK{shipment_id:09d}", ship_status),
            )

    # -- inventory -----------------------------------------------------------
    # PLANTED: ~15% below reorder point; a handful of expensive SKUs heavily
    # overstocked (capital tied up).
    inv_id = 0
    slow_movers = set(random.sample(
        [p["product_id"] for p in sorted(products, key=lambda x: -x["unit_cost"])[:25]], 8))
    short_stock = set(random.sample([p["product_id"] for p in products], 11))

    for p in products:
        warehouses = random.sample(WAREHOUSES, random.choice([1, 1, 1, 2]))
        for wh in warehouses:
            inv_id += 1
            rp = p["reorder_point"]
            if p["product_id"] in short_stock:
                on_hand = random.randint(int(rp * 0.15), int(rp * 0.75))
            elif p["product_id"] in slow_movers:
                on_hand = random.randint(rp * 8, rp * 20)
            else:
                on_hand = random.randint(int(rp * 1.1), int(rp * 4.5))
            reserved = random.randint(0, max(1, int(on_hand * 0.2)))
            conn.execute(
                """INSERT INTO inventory (inventory_id, product_id, warehouse_location,
                   quantity_on_hand, quantity_reserved, last_received_date,
                   expiration_date)
                   VALUES (?,?,?,?,?,?,?)""",
                (inv_id, p["product_id"], wh, on_hand, reserved,
                 (END_DATE - timedelta(days=random.randint(1, 120))).isoformat(),
                 None),
            )

    conn.commit()

    # -- summary -------------------------------------------------------------
    def one(q):
        return conn.execute(q).fetchone()[0]

    print("Database rebuilt:", DB_PATH)
    print(f"  suppliers : {one('SELECT COUNT(*) FROM suppliers')}")
    print(f"  products  : {one('SELECT COUNT(*) FROM products')}")
    print(f"  inventory : {one('SELECT COUNT(*) FROM inventory')}")
    print(f"  orders    : {one('SELECT COUNT(*) FROM orders')}")
    print(f"  shipments : {one('SELECT COUNT(*) FROM shipments')}")
    print("  date range:", conn.execute(
        "SELECT MIN(order_date), MAX(order_date) FROM orders").fetchone())
    print(f"  total spend: ${one('SELECT SUM(order_cost) FROM orders'):,.0f}")
    conn.close()


if __name__ == "__main__":
    main()

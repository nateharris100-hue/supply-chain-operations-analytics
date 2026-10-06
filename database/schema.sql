-- ============================================================================
-- SUPPLY CHAIN DATABASE SCHEMA
-- Purpose: Relational database for supply chain operations analysis
-- Tables: Suppliers, Products, Inventory, Orders, Shipments
-- ============================================================================

-- Drop existing tables (if rebuilding)
DROP TABLE IF EXISTS shipments;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS suppliers;

-- ============================================================================
-- TABLE 1: SUPPLIERS
-- ============================================================================
CREATE TABLE suppliers (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name TEXT NOT NULL UNIQUE,
    country TEXT NOT NULL,
    city TEXT,
    on_time_rate REAL DEFAULT 0.90,
    lead_time_days INTEGER DEFAULT 30,
    cost_per_unit REAL DEFAULT 100.00,
    contract_end_date DATE,
    quality_score INTEGER DEFAULT 3,
    phone TEXT,
    email TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TABLE 2: PRODUCTS
-- ============================================================================
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    unit_cost REAL NOT NULL,
    reorder_point INTEGER DEFAULT 50,
    supplier_id INTEGER NOT NULL,
    sku TEXT UNIQUE,
    description TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);

-- ============================================================================
-- TABLE 3: INVENTORY
-- ============================================================================
CREATE TABLE inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    warehouse_location TEXT NOT NULL,
    quantity_on_hand INTEGER DEFAULT 0,
    quantity_reserved INTEGER DEFAULT 0,
    last_received_date DATE,
    expiration_date DATE,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- ============================================================================
-- TABLE 4: ORDERS
-- ============================================================================
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_date DATE NOT NULL,
    product_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    quantity_ordered INTEGER NOT NULL,
    order_status TEXT DEFAULT 'pending',
    expected_delivery_date DATE,
    actual_delivery_date DATE,
    order_cost REAL NOT NULL,
    po_number TEXT UNIQUE,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);

-- ============================================================================
-- TABLE 5: SHIPMENTS
-- ============================================================================
CREATE TABLE shipments (
    shipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    shipment_date DATE NOT NULL,
    expected_arrival_date DATE,
    actual_arrival_date DATE,
    shipping_mode TEXT DEFAULT 'standard',
    shipping_cost REAL,
    carrier TEXT,
    tracking_number TEXT UNIQUE,
    shipment_status TEXT DEFAULT 'in_transit',
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- ============================================================================
-- CREATE INDEXES (for query performance)
-- ============================================================================
CREATE INDEX idx_orders_supplier ON orders(supplier_id);
CREATE INDEX idx_orders_product ON orders(product_id);
CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_shipments_order ON shipments(order_id);
CREATE INDEX idx_shipments_date ON shipments(shipment_date);
CREATE INDEX idx_inventory_product ON inventory(product_id);
CREATE INDEX idx_products_supplier ON products(supplier_id);

-- ============================================================================
-- DATABASE SETUP COMPLETE
-- Run sample_data.sql next to populate with test data
-- ============================================================================

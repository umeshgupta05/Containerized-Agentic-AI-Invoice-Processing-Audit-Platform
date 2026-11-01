CREATE SCHEMA IF NOT EXISTS erp;
CREATE SCHEMA IF NOT EXISTS langgraph;

CREATE TABLE IF NOT EXISTS erp.vendors (
    vendor_id VARCHAR(64) PRIMARY KEY,
    vendor_name VARCHAR(255) NOT NULL,
    country VARCHAR(64),
    currency CHAR(3)
);

CREATE TABLE IF NOT EXISTS erp.sku_master (
    item_code VARCHAR(64) PRIMARY KEY,
    category VARCHAR(128),
    uom VARCHAR(32),
    gst_rate NUMERIC(6, 2)
);

CREATE TABLE IF NOT EXISTS erp.purchase_orders (
    po_number VARCHAR(64) PRIMARY KEY,
    vendor_id VARCHAR(64) NOT NULL REFERENCES erp.vendors(vendor_id)
);

CREATE TABLE IF NOT EXISTS erp.po_line_items (
    id VARCHAR(128) PRIMARY KEY,
    po_number VARCHAR(64) NOT NULL REFERENCES erp.purchase_orders(po_number),
    item_code VARCHAR(64) REFERENCES erp.sku_master(item_code),
    description VARCHAR(512),
    qty NUMERIC(12, 3),
    unit_price NUMERIC(14, 4),
    currency CHAR(3)
);

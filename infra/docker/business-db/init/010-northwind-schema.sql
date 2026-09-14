\set ON_ERROR_STOP on

BEGIN;

CREATE SCHEMA IF NOT EXISTS northwind;
COMMENT ON SCHEMA northwind IS 'Fixed Northwind-compatible dataset used by Enterprise Data Copilot.';

CREATE TABLE IF NOT EXISTS northwind.dataset_manifest (
    dataset_name text PRIMARY KEY,
    dataset_version text NOT NULL,
    source_note text NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS northwind.categories (
    category_id integer PRIMARY KEY,
    category_name varchar(50) NOT NULL UNIQUE,
    description text
);
COMMENT ON TABLE northwind.categories IS 'Product category lookup.';
COMMENT ON COLUMN northwind.categories.category_name IS 'Business-facing product category name.';

CREATE TABLE IF NOT EXISTS northwind.suppliers (
    supplier_id integer PRIMARY KEY,
    company_name varchar(100) NOT NULL,
    country varchar(50) NOT NULL
);
COMMENT ON TABLE northwind.suppliers IS 'Companies that supply products.';

CREATE TABLE IF NOT EXISTS northwind.products (
    product_id integer PRIMARY KEY,
    product_name varchar(100) NOT NULL,
    supplier_id integer NOT NULL REFERENCES northwind.suppliers(supplier_id),
    category_id integer NOT NULL REFERENCES northwind.categories(category_id),
    unit_price numeric(10, 2) NOT NULL CHECK (unit_price >= 0),
    units_in_stock integer NOT NULL CHECK (units_in_stock >= 0),
    discontinued boolean NOT NULL DEFAULT false
);
COMMENT ON TABLE northwind.products IS 'Products available for sale and their current catalogue attributes.';
COMMENT ON COLUMN northwind.products.unit_price IS 'Current catalogue unit price; historical sales use order_details.unit_price.';

CREATE TABLE IF NOT EXISTS northwind.customers (
    customer_id varchar(5) PRIMARY KEY,
    company_name varchar(100) NOT NULL,
    contact_name varchar(100),
    city varchar(50),
    country varchar(50) NOT NULL
);
COMMENT ON TABLE northwind.customers IS 'Customer companies that place orders.';

CREATE TABLE IF NOT EXISTS northwind.employees (
    employee_id integer PRIMARY KEY,
    first_name varchar(50) NOT NULL,
    last_name varchar(50) NOT NULL,
    title varchar(100) NOT NULL,
    reports_to integer REFERENCES northwind.employees(employee_id),
    hire_date date NOT NULL
);
COMMENT ON TABLE northwind.employees IS 'Sales employees and their reporting line.';

CREATE TABLE IF NOT EXISTS northwind.shippers (
    shipper_id integer PRIMARY KEY,
    company_name varchar(100) NOT NULL
);
COMMENT ON TABLE northwind.shippers IS 'Shipping providers used to fulfil orders.';

CREATE TABLE IF NOT EXISTS northwind.orders (
    order_id integer PRIMARY KEY,
    customer_id varchar(5) NOT NULL REFERENCES northwind.customers(customer_id),
    employee_id integer NOT NULL REFERENCES northwind.employees(employee_id),
    order_date date NOT NULL,
    required_date date NOT NULL,
    shipped_date date,
    shipper_id integer REFERENCES northwind.shippers(shipper_id),
    freight numeric(10, 2) NOT NULL DEFAULT 0 CHECK (freight >= 0),
    ship_country varchar(50) NOT NULL,
    CHECK (required_date >= order_date),
    CHECK (shipped_date IS NULL OR shipped_date >= order_date)
);
COMMENT ON TABLE northwind.orders IS 'Order headers. Revenue is derived from order_details, excluding freight.';
COMMENT ON COLUMN northwind.orders.order_date IS 'Date on which the customer placed the order.';

CREATE TABLE IF NOT EXISTS northwind.order_details (
    order_id integer NOT NULL REFERENCES northwind.orders(order_id),
    product_id integer NOT NULL REFERENCES northwind.products(product_id),
    unit_price numeric(10, 2) NOT NULL CHECK (unit_price >= 0),
    quantity smallint NOT NULL CHECK (quantity > 0),
    discount numeric(4, 3) NOT NULL DEFAULT 0 CHECK (discount >= 0 AND discount <= 1),
    PRIMARY KEY (order_id, product_id)
);
COMMENT ON TABLE northwind.order_details IS 'Order line items used to calculate gross and net sales.';
COMMENT ON COLUMN northwind.order_details.unit_price IS 'Unit price captured at order time.';
COMMENT ON COLUMN northwind.order_details.discount IS 'Fractional line discount from 0.000 to 1.000.';

CREATE INDEX IF NOT EXISTS idx_orders_order_date ON northwind.orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON northwind.orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_order_details_product_id ON northwind.order_details(product_id);

CREATE SCHEMA IF NOT EXISTS restricted;
CREATE TABLE IF NOT EXISTS restricted.private_notes (
    note_id integer PRIMARY KEY,
    note text NOT NULL
);
COMMENT ON SCHEMA restricted IS 'Deliberately inaccessible schema used by permission regression tests.';

COMMIT;

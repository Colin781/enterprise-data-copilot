\set ON_ERROR_STOP on

BEGIN;

INSERT INTO northwind.dataset_manifest (dataset_name, dataset_version, source_note, loaded_at)
VALUES (
    'northwind',
    'northwind-compact-v1',
    'Deterministic Northwind-compatible fixture maintained in this repository.',
    '2026-09-14T00:00:00Z'
)
ON CONFLICT (dataset_name) DO UPDATE SET
    dataset_version = EXCLUDED.dataset_version,
    source_note = EXCLUDED.source_note,
    loaded_at = EXCLUDED.loaded_at;

INSERT INTO northwind.categories (category_id, category_name, description) VALUES
    (1, 'Beverages', 'Soft drinks, coffees, teas and beers'),
    (2, 'Condiments', 'Sweet and savoury sauces'),
    (3, 'Confections', 'Desserts, candies and sweet breads'),
    (4, 'Dairy Products', 'Cheeses and other dairy products'),
    (5, 'Grains/Cereals', 'Breads, crackers, pasta and cereal'),
    (6, 'Meat/Poultry', 'Prepared meats'),
    (7, 'Produce', 'Dried fruit and bean curd'),
    (8, 'Seafood', 'Seaweed and fish')
ON CONFLICT (category_id) DO UPDATE SET
    category_name = EXCLUDED.category_name,
    description = EXCLUDED.description;

INSERT INTO northwind.suppliers (supplier_id, company_name, country) VALUES
    (1, 'Exotic Liquids', 'United Kingdom'),
    (2, 'New Orleans Cajun Delights', 'USA'),
    (3, 'Grandma Kelly''s Homestead', 'USA'),
    (4, 'Tokyo Traders', 'Japan'),
    (5, 'Cooperativa de Quesos', 'Spain'),
    (6, 'Nord-Ost-Fisch', 'Germany')
ON CONFLICT (supplier_id) DO UPDATE SET
    company_name = EXCLUDED.company_name,
    country = EXCLUDED.country;

INSERT INTO northwind.products (
    product_id, product_name, supplier_id, category_id, unit_price, units_in_stock, discontinued
) VALUES
    (1, 'Chai', 1, 1, 18.00, 39, false),
    (2, 'Chang', 1, 1, 19.00, 17, false),
    (3, 'Aniseed Syrup', 1, 2, 10.00, 13, false),
    (4, 'Chef Anton''s Cajun Seasoning', 2, 2, 22.00, 53, false),
    (5, 'Grandma''s Boysenberry Spread', 3, 2, 25.00, 120, false),
    (6, 'Ikura', 4, 8, 31.00, 31, false),
    (7, 'Queso Cabrales', 5, 4, 21.00, 22, false),
    (8, 'Queso Manchego La Pastora', 5, 4, 38.00, 86, false),
    (9, 'Konbu', 4, 8, 6.00, 24, false),
    (10, 'Pavlova', 3, 3, 17.45, 29, false),
    (11, 'Tunnbrod', 6, 5, 9.00, 61, false),
    (12, 'Thuringer Rostbratwurst', 6, 6, 123.79, 0, true)
ON CONFLICT (product_id) DO UPDATE SET
    product_name = EXCLUDED.product_name,
    supplier_id = EXCLUDED.supplier_id,
    category_id = EXCLUDED.category_id,
    unit_price = EXCLUDED.unit_price,
    units_in_stock = EXCLUDED.units_in_stock,
    discontinued = EXCLUDED.discontinued;

INSERT INTO northwind.customers (customer_id, company_name, contact_name, city, country) VALUES
    ('ALFKI', 'Alfreds Futterkiste', 'Maria Anders', 'Berlin', 'Germany'),
    ('ANATR', 'Ana Trujillo Emparedados', 'Ana Trujillo', 'Mexico City', 'Mexico'),
    ('AROUT', 'Around the Horn', 'Thomas Hardy', 'London', 'United Kingdom'),
    ('BERGS', 'Berglunds snabbkop', 'Christina Berglund', 'Lulea', 'Sweden'),
    ('BONAP', 'Bon app', 'Laurence Lebihan', 'Marseille', 'France'),
    ('ERNSH', 'Ernst Handel', 'Roland Mendel', 'Graz', 'Austria'),
    ('FRANK', 'Frankenversand', 'Peter Franken', 'Munich', 'Germany'),
    ('HUNGO', 'Hungry Owl All-Night Grocers', 'Patricia McKenna', 'Cork', 'Ireland'),
    ('QUICK', 'QUICK-Stop', 'Horst Kloss', 'Cunewalde', 'Germany'),
    ('SAVEA', 'Save-a-lot Markets', 'Jose Pavarotti', 'Boise', 'USA')
ON CONFLICT (customer_id) DO UPDATE SET
    company_name = EXCLUDED.company_name,
    contact_name = EXCLUDED.contact_name,
    city = EXCLUDED.city,
    country = EXCLUDED.country;

INSERT INTO northwind.employees (
    employee_id, first_name, last_name, title, reports_to, hire_date
) VALUES
    (1, 'Nancy', 'Davolio', 'Sales Representative', NULL, '2020-05-01'),
    (2, 'Andrew', 'Fuller', 'Vice President, Sales', NULL, '2019-08-14'),
    (3, 'Janet', 'Leverling', 'Sales Representative', NULL, '2021-04-01'),
    (4, 'Margaret', 'Peacock', 'Sales Representative', NULL, '2020-05-03'),
    (5, 'Steven', 'Buchanan', 'Sales Manager', NULL, '2021-10-17')
ON CONFLICT (employee_id) DO UPDATE SET
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    title = EXCLUDED.title,
    reports_to = EXCLUDED.reports_to,
    hire_date = EXCLUDED.hire_date;

UPDATE northwind.employees SET reports_to = 2 WHERE employee_id IN (1, 3, 4);
UPDATE northwind.employees SET reports_to = 2 WHERE employee_id = 5;

INSERT INTO northwind.shippers (shipper_id, company_name) VALUES
    (1, 'Speedy Express'),
    (2, 'United Package'),
    (3, 'Federal Shipping')
ON CONFLICT (shipper_id) DO UPDATE SET company_name = EXCLUDED.company_name;

INSERT INTO northwind.orders (
    order_id, customer_id, employee_id, order_date, required_date, shipped_date,
    shipper_id, freight, ship_country
) VALUES
    (11001, 'ALFKI', 1, '2024-01-08', '2024-02-05', '2024-01-11', 1, 32.50, 'Germany'),
    (11002, 'ANATR', 3, '2024-01-19', '2024-02-16', '2024-01-24', 2, 18.30, 'Mexico'),
    (11003, 'AROUT', 4, '2024-02-03', '2024-03-02', '2024-02-08', 3, 44.10, 'United Kingdom'),
    (11004, 'BERGS', 1, '2024-02-21', '2024-03-20', '2024-02-26', 2, 62.00, 'Sweden'),
    (11005, 'BONAP', 3, '2024-03-04', '2024-04-01', '2024-03-08', 1, 25.40, 'France'),
    (11006, 'ERNSH', 4, '2024-03-18', '2024-04-15', '2024-03-25', 3, 88.90, 'Austria'),
    (11007, 'FRANK', 1, '2024-04-02', '2024-04-30', '2024-04-05', 2, 29.60, 'Germany'),
    (11008, 'HUNGO', 3, '2024-04-17', '2024-05-15', '2024-04-23', 1, 51.25, 'Ireland'),
    (11009, 'QUICK', 4, '2024-05-06', '2024-06-03', '2024-05-09', 3, 105.00, 'Germany'),
    (11010, 'SAVEA', 1, '2024-05-22', '2024-06-19', '2024-05-28', 2, 70.40, 'USA'),
    (11011, 'ALFKI', 3, '2025-01-07', '2025-02-04', '2025-01-10', 1, 38.20, 'Germany'),
    (11012, 'ANATR', 4, '2025-01-23', '2025-02-20', '2025-01-29', 2, 20.10, 'Mexico'),
    (11013, 'AROUT', 1, '2025-02-05', '2025-03-05', '2025-02-12', 3, 47.80, 'United Kingdom'),
    (11014, 'BERGS', 3, '2025-02-20', '2025-03-20', '2025-02-25', 2, 65.90, 'Sweden'),
    (11015, 'BONAP', 4, '2025-03-06', '2025-04-03', '2025-03-11', 1, 28.70, 'France'),
    (11016, 'ERNSH', 1, '2025-03-19', '2025-04-16', '2025-03-27', 3, 95.60, 'Austria'),
    (11017, 'FRANK', 3, '2025-04-03', '2025-05-01', '2025-04-08', 2, 31.50, 'Germany'),
    (11018, 'HUNGO', 4, '2025-04-22', '2025-05-20', NULL, 1, 58.30, 'Ireland'),
    (11019, 'QUICK', 1, '2025-05-08', '2025-06-05', '2025-05-13', 3, 112.40, 'Germany'),
    (11020, 'SAVEA', 3, '2025-05-26', '2025-06-23', NULL, 2, 75.80, 'USA')
ON CONFLICT (order_id) DO UPDATE SET
    customer_id = EXCLUDED.customer_id,
    employee_id = EXCLUDED.employee_id,
    order_date = EXCLUDED.order_date,
    required_date = EXCLUDED.required_date,
    shipped_date = EXCLUDED.shipped_date,
    shipper_id = EXCLUDED.shipper_id,
    freight = EXCLUDED.freight,
    ship_country = EXCLUDED.ship_country;

INSERT INTO northwind.order_details (order_id, product_id, unit_price, quantity, discount) VALUES
    (11001, 1, 18.00, 12, 0.000), (11001, 7, 21.00, 5, 0.050),
    (11002, 3, 10.00, 20, 0.000), (11002, 10, 17.45, 8, 0.100),
    (11003, 2, 19.00, 15, 0.000), (11003, 6, 31.00, 6, 0.000),
    (11004, 8, 38.00, 10, 0.050), (11004, 11, 9.00, 30, 0.000),
    (11005, 4, 22.00, 14, 0.000), (11005, 5, 25.00, 7, 0.100),
    (11006, 6, 31.00, 18, 0.050), (11006, 12, 123.79, 3, 0.000),
    (11007, 1, 18.00, 25, 0.100), (11007, 9, 6.00, 20, 0.000),
    (11008, 7, 21.00, 16, 0.000), (11008, 10, 17.45, 12, 0.050),
    (11009, 8, 38.00, 22, 0.100), (11009, 12, 123.79, 5, 0.050),
    (11010, 2, 19.00, 30, 0.000), (11010, 5, 25.00, 18, 0.100),
    (11011, 1, 18.00, 18, 0.000), (11011, 6, 31.00, 8, 0.050),
    (11012, 3, 10.00, 25, 0.000), (11012, 11, 9.00, 16, 0.000),
    (11013, 2, 19.00, 20, 0.050), (11013, 7, 21.00, 11, 0.000),
    (11014, 8, 38.00, 14, 0.000), (11014, 10, 17.45, 20, 0.100),
    (11015, 4, 22.00, 17, 0.050), (11015, 9, 6.00, 40, 0.000),
    (11016, 6, 31.00, 24, 0.100), (11016, 12, 123.79, 4, 0.000),
    (11017, 1, 18.00, 28, 0.050), (11017, 5, 25.00, 12, 0.000),
    (11018, 7, 21.00, 21, 0.100), (11018, 11, 9.00, 35, 0.000),
    (11019, 8, 38.00, 26, 0.050), (11019, 12, 123.79, 6, 0.100),
    (11020, 2, 19.00, 32, 0.000), (11020, 10, 17.45, 24, 0.050)
ON CONFLICT (order_id, product_id) DO UPDATE SET
    unit_price = EXCLUDED.unit_price,
    quantity = EXCLUDED.quantity,
    discount = EXCLUDED.discount;

INSERT INTO restricted.private_notes (note_id, note)
VALUES (1, 'This row proves that the reader cannot cross the schema boundary.')
ON CONFLICT (note_id) DO UPDATE SET note = EXCLUDED.note;

COMMIT;

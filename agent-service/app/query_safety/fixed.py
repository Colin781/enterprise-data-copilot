FIXED_TOP_CUSTOMERS_SQL = """
SELECT
    c.company_name AS customer,
    ROUND(SUM(od.unit_price * od.quantity * (1 - od.discount)), 2) AS revenue
FROM northwind.customers AS c
JOIN northwind.orders AS o ON o.customer_id = c.customer_id
JOIN northwind.order_details AS od ON od.order_id = o.order_id
GROUP BY c.customer_id, c.company_name
ORDER BY revenue DESC, customer
LIMIT 5
""".strip()

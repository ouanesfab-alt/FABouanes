from __future__ import annotations

import pytest
from app.services.alert_service import (
    check_stock_alerts,
    check_overdue_clients,
    broadcast_overdue_alerts,
)
from app.core.db_access import execute_db, query_db


def test_stock_alerts_behavior():
    # Clean existing stock_alerts
    execute_db("DELETE FROM stock_alerts")
    execute_db("DELETE FROM raw_materials WHERE name = %s", ("Alert Test RM",))
    execute_db("DELETE FROM finished_products WHERE name = %s", ("Alert Test FP",))
    
    # 1. Insert raw material with qty <= threshold and threshold > 0 (should alert)
    execute_db(
        "INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold) VALUES (%s, %s, %s, %s, %s, %s)",
        ("Alert Test RM", "kg", 5.0000, 50.0000, 60.0000, 10.0000)
    )
    
    # 2. Insert raw material with qty <= threshold but threshold is 0 (should NOT alert)
    execute_db(
        "INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold) VALUES (%s, %s, %s, %s, %s, %s)",
        ("No Alert Test RM", "kg", 0.0000, 50.0000, 60.0000, 0.0000)
    )
    
    # 3. Insert finished product with qty <= threshold and threshold > 0 (should alert)
    execute_db(
        "INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost, alert_threshold) VALUES (%s, %s, %s, %s, %s, %s)",
        ("Alert Test FP", "kg", 3.0000, 120.0000, 90.0000, 5.0000)
    )
    
    # Run alert checking service
    check_stock_alerts()
    
    # Query generated alerts
    alerts = query_db("SELECT * FROM stock_alerts ORDER BY triggered_at DESC")
    assert len(alerts) == 2
    
    rm_alert = [a for a in alerts if a["product_type"] == "raw_material"][0]
    fp_alert = [a for a in alerts if a["product_type"] == "finished_product"][0]
    
    assert rm_alert["product_name"] == "Alert Test RM"
    assert float(rm_alert["current_qty"]) == 5.0
    assert float(rm_alert["threshold_qty"]) == 10.0
    
    assert fp_alert["product_name"] == "Alert Test FP"
    assert float(fp_alert["current_qty"]) == 3.0
    assert float(fp_alert["threshold_qty"]) == 5.0
    
    # 4. Check duplicate prevention: running it again within 24h should NOT add new unacknowledged alert for the same product
    check_stock_alerts()
    alerts_after = query_db("SELECT * FROM stock_alerts")
    assert len(alerts_after) == 2
    
    # Clean up
    execute_db("DELETE FROM stock_alerts")
    execute_db("DELETE FROM raw_materials WHERE name IN (%s, %s)", ("Alert Test RM", "No Alert Test RM"))
    execute_db("DELETE FROM finished_products WHERE name = %s", ("Alert Test FP",))


def test_overdue_clients_behavior():
    execute_db("DELETE FROM clients WHERE name = %s", ("Overdue Client Test",))
    
    # Insert client with positive balance
    execute_db(
        "INSERT INTO clients (name, phone, address, notes, opening_credit) VALUES (%s, %s, %s, %s, %s)",
        ("Overdue Client Test", "0550000000", "", "", 100.0)
    )
    
    overdue = check_overdue_clients(overdue_days=-1)
    assert len(overdue) >= 1
    
    # broadcast
    count = broadcast_overdue_alerts()
    assert count >= 0
    
    # Clean up
    execute_db("DELETE FROM clients WHERE name = %s", ("Overdue Client Test",))

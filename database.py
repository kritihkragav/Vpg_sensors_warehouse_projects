import os
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, "database")
DATABASE_PATH = os.path.join(DATABASE_DIR, "warehouse.db")


def get_db_path():
    return DATABASE_PATH


@contextmanager
def get_connection():
    os.makedirs(DATABASE_DIR, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database tables."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS racks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rack_id TEXT UNIQUE NOT NULL,
                product_name TEXT NOT NULL,
                unit_weight REAL NOT NULL,
                initial_quantity INTEGER NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rack_id TEXT NOT NULL,
                weight REAL NOT NULL,
                current_quantity INTEGER NOT NULL,
                dispatched_quantity INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (rack_id) REFERENCES racks(rack_id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_rack_id
            ON inventory(rack_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_timestamp
            ON inventory(timestamp)
        """)


def insert_sample_data():
    """Insert sample rack and inventory data for demonstration."""
    from models import RackModel, InventoryModel
    import random
    from datetime import datetime, timedelta

    sample_racks = [
        ("R001", "Steel Brackets", 2.5, 100),
        ("R002", "Aluminum Panels", 3.0, 80),
        ("R003", "Copper Fittings", 1.8, 120),
        ("R004", "Plastic Housings", 0.5, 200),
        ("R005", "Rubber Gaskets", 0.2, 150),
    ]

    for rack_id, product_name, unit_weight, initial_qty in sample_racks:
        if not RackModel.get_by_rack_id(rack_id):
            RackModel.create(rack_id, product_name, unit_weight, initial_qty)

    racks = RackModel.get_all()
    base_time = datetime.now() - timedelta(hours=24)

    for rack in racks:
        existing = InventoryModel.get_latest_by_rack(rack["rack_id"])
        if existing:
            continue

        current_qty = random.randint(5, rack["initial_quantity"])
        weight = round(current_qty * rack["unit_weight"], 2)
        dispatched = rack["initial_quantity"] - current_qty

        for i in range(5):
            ts = (base_time + timedelta(hours=i * 4)).strftime("%Y-%m-%d %H:%M:%S")
            qty = max(1, current_qty + random.randint(-10, 5))
            qty = min(qty, rack["initial_quantity"])
            w = round(qty * rack["unit_weight"], 2)
            disp = rack["initial_quantity"] - qty
            InventoryModel.create(rack["rack_id"], w, qty, disp, timestamp=ts)

        InventoryModel.create(
            rack["rack_id"], weight, current_qty, dispatched
        )

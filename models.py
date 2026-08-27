from datetime import datetime
from database import get_connection


class RackModel:
    @staticmethod
    def get_all():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM racks ORDER BY rack_id"
            ).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_by_rack_id(rack_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM racks WHERE rack_id = ?", (rack_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create(rack_id, product_name, unit_weight, initial_quantity):
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO racks (rack_id, product_name, unit_weight, initial_quantity)
                   VALUES (?, ?, ?, ?)""",
                (rack_id, product_name, unit_weight, initial_quantity),
            )

    @staticmethod
    def update(rack_id, product_name, unit_weight, initial_quantity):
        with get_connection() as conn:
            conn.execute(
                """UPDATE racks SET product_name = ?, unit_weight = ?,
                   initial_quantity = ? WHERE rack_id = ?""",
                (product_name, unit_weight, initial_quantity, rack_id),
            )

    @staticmethod
    def delete(rack_id):
        with get_connection() as conn:
            conn.execute("DELETE FROM inventory WHERE rack_id = ?", (rack_id,))
            conn.execute("DELETE FROM racks WHERE rack_id = ?", (rack_id,))

    @staticmethod
    def count():
        with get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM racks").fetchone()
            return row["cnt"]


class InventoryModel:
    @staticmethod
    def create(rack_id, weight, current_quantity, dispatched_quantity, timestamp=None):
        with get_connection() as conn:
            if timestamp:
                conn.execute(
                    """INSERT INTO inventory
                       (rack_id, weight, current_quantity, dispatched_quantity, timestamp)
                       VALUES (?, ?, ?, ?, ?)""",
                    (rack_id, weight, current_quantity, dispatched_quantity, timestamp),
                )
            else:
                conn.execute(
                    """INSERT INTO inventory
                       (rack_id, weight, current_quantity, dispatched_quantity)
                       VALUES (?, ?, ?, ?)""",
                    (rack_id, weight, current_quantity, dispatched_quantity),
                )

    @staticmethod
    def get_latest_by_rack(rack_id):
        with get_connection() as conn:
            row = conn.execute(
                """SELECT * FROM inventory WHERE rack_id = ?
                   ORDER BY timestamp DESC LIMIT 1""",
                (rack_id,),
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_all_latest():
        """Get latest inventory record for each rack."""
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT i.* FROM inventory i
                INNER JOIN (
                    SELECT rack_id, MAX(timestamp) as max_ts
                    FROM inventory GROUP BY rack_id
                ) latest ON i.rack_id = latest.rack_id AND i.timestamp = latest.max_ts
                ORDER BY i.rack_id
            """).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_history(rack_id=None, date_from=None, date_to=None, search=None):
        query = "SELECT * FROM inventory WHERE 1=1"
        params = []

        if rack_id:
            query += " AND rack_id = ?"
            params.append(rack_id)

        if date_from:
            query += " AND date(timestamp) >= date(?)"
            params.append(date_from)

        if date_to:
            query += " AND date(timestamp) <= date(?)"
            params.append(date_to)

        if search:
            query += " AND rack_id LIKE ?"
            params.append(f"%{search}%")

        query += " ORDER BY timestamp DESC LIMIT 500"

        with get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_dashboard_data():
        """Combine rack info with latest inventory for dashboard."""
        racks = RackModel.get_all()
        result = []
        total_inventory = 0
        total_dispatched = 0
        low_stock = 0
        critical_stock = 0

        for rack in racks:
            inv = InventoryModel.get_latest_by_rack(rack["rack_id"])
            current_qty = inv["current_quantity"] if inv else rack["initial_quantity"]
            dispatched = inv["dispatched_quantity"] if inv else 0
            weight = inv["weight"] if inv else round(
                current_qty * rack["unit_weight"], 2
            )

            status = "normal"
            if current_qty < 10:
                status = "critical"
                critical_stock += 1
                low_stock += 1
            elif current_qty < 20:
                status = "low"
                low_stock += 1

            total_inventory += current_qty
            total_dispatched += dispatched

            result.append({
                "rack_id": rack["rack_id"],
                "product_name": rack["product_name"],
                "initial_quantity": rack["initial_quantity"],
                "current_quantity": current_qty,
                "dispatched_quantity": dispatched,
                "current_weight": weight,
                "unit_weight": rack["unit_weight"],
                "status": status,
            })

        return {
            "racks": result,
            "kpis": {
                "total_racks": len(racks),
                "total_inventory": total_inventory,
                "total_dispatched": total_dispatched,
                "low_stock_alerts": low_stock,
                "critical_alerts": critical_stock,
            },
        }

    @staticmethod
    def get_trend_data():
        """Get data for analytics charts."""
        with get_connection() as conn:
            inventory_trend = conn.execute("""
                SELECT date(timestamp) as date,
                       SUM(current_quantity) as total_qty
                FROM inventory
                GROUP BY date(timestamp)
                ORDER BY date(timestamp)
            """).fetchall()

            dispatch_trend = conn.execute("""
                SELECT date(timestamp) as date,
                       SUM(dispatched_quantity) as total_dispatched
                FROM inventory
                GROUP BY date(timestamp)
                ORDER BY date(timestamp)
            """).fetchall()

            utilization = conn.execute("""
                SELECT i.rack_id, r.initial_quantity,
                       i.current_quantity,
                       ROUND(i.current_quantity * 100.0 / r.initial_quantity, 1) as utilization
                FROM inventory i
                INNER JOIN racks r ON i.rack_id = r.rack_id
                INNER JOIN (
                    SELECT rack_id, MAX(timestamp) as max_ts
                    FROM inventory GROUP BY rack_id
                ) latest ON i.rack_id = latest.rack_id AND i.timestamp = latest.max_ts
                ORDER BY i.rack_id
            """).fetchall()

            return {
                "inventory_trend": [dict(r) for r in inventory_trend],
                "dispatch_trend": [dict(r) for r in dispatch_trend],
                "utilization": [dict(r) for r in utilization],
            }

    @staticmethod
    def update_from_weight(rack_id, weight):
        """Process weight update from Raspberry Pi."""
        rack = RackModel.get_by_rack_id(rack_id)
        if not rack:
            return None, "Rack not found"

        if rack["unit_weight"] <= 0:
            return None, "Invalid unit weight"

        current_quantity = int(weight / rack["unit_weight"])
        dispatched_quantity = rack["initial_quantity"] - current_quantity

        InventoryModel.create(
            rack_id, weight, current_quantity, dispatched_quantity
        )

        return {
            "rack_id": rack_id,
            "weight": weight,
            "current_quantity": current_quantity,
            "dispatched_quantity": dispatched_quantity,
        }, None

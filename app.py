import csv
import io
import os
import random
import webbrowser
from functools import wraps
from threading import Timer

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
    Response,
)

from database import init_db, insert_sample_data
from models import RackModel, InventoryModel

app = Flask(__name__)
app.secret_key = "smart-fg-warehouse-secret-key-2024"
app.config.update(
    SESSION_COOKIE_SAME_SITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
    TEMPLATES_AUTO_RELOAD=True,
)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
APP_HOST = "127.0.0.1"
APP_PORT = int(os.environ.get("PORT", 5000))
APP_URL = f"http://{APP_HOST}:{APP_PORT}"


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.after_request
def prevent_stale_cache(response):
    """Stop embedded browsers from showing cached 'connection lost' pages."""
    if response.content_type and "text/html" in response.content_type:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "SMART FG Warehouse Monitor"})


@app.route("/favicon.ico")
def favicon():
    return Response(status=204)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("dashboard"))
        error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    data = InventoryModel.get_dashboard_data()
    return render_template("dashboard.html", data=data)


@app.route("/racks", methods=["GET", "POST"])
@login_required
def racks():
    message = None
    error = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            rack_id = request.form.get("rack_id", "").strip().upper()
            product_name = request.form.get("product_name", "").strip()
            try:
                unit_weight = float(request.form.get("unit_weight", 0))
                initial_quantity = int(request.form.get("initial_quantity", 0))
            except ValueError:
                error = "Invalid numeric values."
            else:
                if not rack_id or not product_name:
                    error = "Rack ID and Product Name are required."
                elif unit_weight <= 0 or initial_quantity <= 0:
                    error = "Unit weight and initial quantity must be positive."
                elif RackModel.get_by_rack_id(rack_id):
                    error = f"Rack {rack_id} already exists."
                else:
                    RackModel.create(rack_id, product_name, unit_weight, initial_quantity)
                    weight = round(initial_quantity * unit_weight, 2)
                    InventoryModel.create(rack_id, weight, initial_quantity, 0)
                    message = f"Rack {rack_id} added successfully."

        elif action == "edit":
            rack_id = request.form.get("rack_id", "").strip()
            product_name = request.form.get("product_name", "").strip()
            try:
                unit_weight = float(request.form.get("unit_weight", 0))
                initial_quantity = int(request.form.get("initial_quantity", 0))
            except ValueError:
                error = "Invalid numeric values."
            else:
                if unit_weight <= 0 or initial_quantity <= 0:
                    error = "Unit weight and initial quantity must be positive."
                else:
                    RackModel.update(rack_id, product_name, unit_weight, initial_quantity)
                    message = f"Rack {rack_id} updated successfully."

        elif action == "delete":
            rack_id = request.form.get("rack_id", "").strip()
            RackModel.delete(rack_id)
            message = f"Rack {rack_id} deleted successfully."

    all_racks = RackModel.get_all()
    rack_inventory = []
    for rack in all_racks:
        inv = InventoryModel.get_latest_by_rack(rack["rack_id"])
        rack_inventory.append({
            **rack,
            "current_quantity": inv["current_quantity"] if inv else rack["initial_quantity"],
            "current_weight": inv["weight"] if inv else round(
                rack["initial_quantity"] * rack["unit_weight"], 2
            ),
        })

    return render_template(
        "racks.html",
        racks=rack_inventory,
        message=message,
        error=error,
    )


@app.route("/history")
@login_required
def history():
    rack_id = request.args.get("rack_id", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    search = request.args.get("search", "")

    records = InventoryModel.get_history(
        rack_id=rack_id or None,
        date_from=date_from or None,
        date_to=date_to or None,
        search=search or None,
    )
    all_racks = RackModel.get_all()

    return render_template(
        "history.html",
        records=records,
        all_racks=all_racks,
        filters={
            "rack_id": rack_id,
            "date_from": date_from,
            "date_to": date_to,
            "search": search,
        },
    )


@app.route("/analytics")
@login_required
def analytics():
    trend_data = InventoryModel.get_trend_data()
    return render_template("analytics.html", trend_data=trend_data)


@app.route("/api/dashboard")
@login_required
def api_dashboard():
    data = InventoryModel.get_dashboard_data()
    return jsonify(data)


@app.route("/api/analytics")
@login_required
def api_analytics():
    return jsonify(InventoryModel.get_trend_data())


@app.route("/update", methods=["POST"])
def update_inventory():
    """Live inventory update API for Raspberry Pi integration."""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    rack_id = data.get("rack_id")
    weight = data.get("weight")

    if not rack_id or weight is None:
        return jsonify({"status": "error", "message": "rack_id and weight are required"}), 400

    try:
        weight = float(weight)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "weight must be a number"}), 400

    result, error = InventoryModel.update_from_weight(rack_id, weight)
    if error:
        return jsonify({"status": "error", "message": error}), 404

    return jsonify({"status": "success", "data": result})


@app.route("/generate-demo-data", methods=["POST"])
@login_required
def generate_demo_data():
    demo_racks = [
        ("R001", "Steel Brackets", 2.5, 100),
        ("R002", "Aluminum Panels", 3.0, 80),
        ("R003", "Copper Fittings", 1.8, 120),
        ("R004", "Plastic Housings", 0.5, 200),
        ("R005", "Rubber Gaskets", 0.2, 150),
    ]

    for rack_id, product_name, unit_weight, initial_qty in demo_racks:
        existing = RackModel.get_by_rack_id(rack_id)
        if not existing:
            RackModel.create(rack_id, product_name, unit_weight, initial_qty)

        rack = RackModel.get_by_rack_id(rack_id)
        current_qty = random.randint(5, rack["initial_quantity"])
        weight = round(current_qty * rack["unit_weight"], 2)
        dispatched = rack["initial_quantity"] - current_qty
        InventoryModel.create(rack_id, weight, current_qty, dispatched)

    return redirect(url_for("dashboard"))


@app.route("/export/inventory")
@login_required
def export_inventory():
    data = InventoryModel.get_dashboard_data()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Rack ID", "Product Name", "Initial Quantity",
        "Current Quantity", "Dispatched Quantity", "Current Weight (kg)", "Status",
    ])
    for rack in data["racks"]:
        writer.writerow([
            rack["rack_id"],
            rack["product_name"],
            rack["initial_quantity"],
            rack["current_quantity"],
            rack["dispatched_quantity"],
            rack["current_weight"],
            rack["status"].upper(),
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_report.csv"},
    )


@app.route("/export/dispatch")
@login_required
def export_dispatch():
    records = InventoryModel.get_history()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Timestamp", "Rack ID", "Weight (kg)",
        "Current Quantity", "Dispatched Quantity",
    ])
    for rec in records:
        writer.writerow([
            rec["timestamp"],
            rec["rack_id"],
            rec["weight"],
            rec["current_quantity"],
            rec["dispatched_quantity"],
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=dispatch_report.csv"},
    )


def open_browser():
    """Open the app in the system browser (more reliable than IDE preview)."""
    webbrowser.open_new_tab(f"{APP_URL}/login")


if __name__ == "__main__":
    init_db()
    insert_sample_data()

    print("=" * 56)
    print("  SMART FG WAREHOUSE MONITORING SYSTEM")
    print("=" * 56)
    print(f"  Open in Chrome/Edge: {APP_URL}/login")
    print("  Login: admin / admin123")
    print("  Press Ctrl+C to stop the server")
    print("=" * 56)

    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        Timer(1.5, open_browser).start()

    app.run(
        debug=True,
        host=APP_HOST,
        port=APP_PORT,
        use_reloader=False,
        threaded=True,
    )

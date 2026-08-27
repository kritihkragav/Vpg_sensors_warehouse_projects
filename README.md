# VPG Sensors Warehouse Monitoring System

IoT-based Smart Warehouse Monitoring System integrating Load Cell and HX711 for real-time weight measurement, microcontroller-based data acquisition, IoT communication, and a web-based dashboard for inventory monitoring, data visualization, and intelligent warehouse management.

Monitor Finished Goods inventory racks using VPG Load Cells and Raspberry Pi.

## Tech Stack

- Python Flask
- SQLite Database
- Bootstrap 5
- Chart.js
- HTML5 / CSS3 / JavaScript

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000** in your browser.

### Login Credentials

| Field    | Value     |
|----------|-----------|
| Username | `admin`   |
| Password | `admin123`|

## Project Structure

```
warehouse_monitor/
├── app.py              # Flask application & routes
├── models.py           # Database models & business logic
├── database.py         # SQLite initialization & sample data
├── requirements.txt    # Python dependencies
├── static/
│   ├── css/style.css   # Industrial theme styles
│   └── js/dashboard.js # Live dashboard refresh (5s)
├── templates/          # HTML templates
└── database/
    └── warehouse.db    # Auto-created on first run
```

## Features

### Dashboard
- KPI cards: Total Racks, Total Inventory, Total Dispatched, Low Stock Alerts
- Live inventory table with status indicators (Normal / Low / Critical)
- Auto-refresh every 5 seconds
- Generate Demo Data button
- Export Inventory & Dispatch reports as CSV

### Rack Management
- Add, edit, and delete racks
- Fields: Rack ID, Product Name, Unit Weight, Initial Quantity

### Inventory History
- Search by Rack ID
- Filter by rack and date range
- Full timestamp history

### Analytics
- Inventory Trend chart (Chart.js)
- Dispatch Trend chart
- Rack Utilization bar chart

### Low Stock Alerts
- **Yellow (Low Stock):** current quantity &lt; 20
- **Red (Critical):** current quantity &lt; 10

## API — Raspberry Pi Integration

### POST /update

Accepts JSON from VPG Load Cell via Raspberry Pi:

```python
import requests

requests.post(
    "http://server-ip:5000/update",
    json={
        "rack_id": "R001",
        "weight": 72.5
    }
)
```

**Processing logic:**
```
current_quantity = int(weight / unit_weight)
dispatched_quantity = initial_quantity - current_quantity
```

**Success response:**
```json
{
    "status": "success",
    "data": {
        "rack_id": "R001",
        "weight": 72.5,
        "current_quantity": 29,
        "dispatched_quantity": 71
    }
}
```

The dashboard reflects changes automatically within 5 seconds.

### GET /api/dashboard (authenticated)

Returns live KPI and inventory data as JSON for the dashboard refresh.

## Database Schema

### racks
| Column           | Type    |
|------------------|---------|
| id               | INTEGER |
| rack_id          | TEXT    |
| product_name     | TEXT    |
| unit_weight      | REAL    |
| initial_quantity | INTEGER |

### inventory
| Column              | Type     |
|---------------------|----------|
| id                  | INTEGER  |
| rack_id             | TEXT     |
| weight              | REAL     |
| current_quantity    | INTEGER  |
| dispatched_quantity | INTEGER  |
| timestamp           | DATETIME |

## Demo Data

On first run, sample racks (R001–R005) and historical inventory records are created automatically. Use the **Generate Demo Data** button on the dashboard to simulate new random weight readings.

## Export Reports

- **Export Inventory CSV** — current snapshot of all racks
- **Export Dispatch CSV** — full dispatch history

## Production Notes

For production deployment:
1. Change `app.secret_key` in `app.py`
2. Set `debug=False`
3. Use a production WSGI server (e.g. Gunicorn)
4. Place behind a reverse proxy (Nginx) with HTTPS

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## License

Internal use — VPG Load Cell Warehouse Monitoring System.

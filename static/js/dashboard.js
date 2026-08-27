/**
 * SMART FG Warehouse - Dashboard Live Refresh
 * Auto-refreshes dashboard data every 5 seconds
 */

(function () {
    'use strict';

    const REFRESH_INTERVAL = 5000;

    function getStatusBadge(status) {
        const labels = {
            normal: 'Normal',
            low: 'Low Stock',
            critical: 'Critical',
        };
        const classes = {
            normal: 'status-normal',
            low: 'status-low',
            critical: 'status-critical',
        };
        return `<span class="status-badge ${classes[status] || 'status-normal'}">${labels[status] || status}</span>`;
    }

    function updateKPIs(kpis) {
        const fields = {
            'kpi-total-racks': kpis.total_racks,
            'kpi-total-inventory': kpis.total_inventory,
            'kpi-total-dispatched': kpis.total_dispatched,
            'kpi-low-stock': kpis.low_stock_alerts,
        };

        for (const [id, value] of Object.entries(fields)) {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        }
    }

    function updateAlerts(racks) {
        const container = document.getElementById('alertContainer');
        if (!container) return;

        let html = '';
        racks.forEach(function (rack) {
            if (rack.status === 'critical') {
                html += `
                    <div class="alert alert-danger alert-card d-flex align-items-center" role="alert">
                        <i class="bi bi-exclamation-octagon-fill fs-4 me-3"></i>
                        <div>
                            <strong>CRITICAL ALERT:</strong> Rack ${rack.rack_id} (${rack.product_name})
                            — Only ${rack.current_quantity} units remaining!
                        </div>
                    </div>`;
            } else if (rack.status === 'low') {
                html += `
                    <div class="alert alert-warning alert-card d-flex align-items-center" role="alert">
                        <i class="bi bi-exclamation-triangle-fill fs-4 me-3"></i>
                        <div>
                            <strong>LOW STOCK:</strong> Rack ${rack.rack_id} (${rack.product_name})
                            — ${rack.current_quantity} units remaining
                        </div>
                    </div>`;
            }
        });
        container.innerHTML = html;
    }

    function updateTable(racks) {
        const tbody = document.getElementById('inventoryTableBody');
        if (!tbody) return;

        if (racks.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center text-muted py-4">
                        No racks configured. Add racks or generate demo data.
                    </td>
                </tr>`;
            return;
        }

        let html = '';
        racks.forEach(function (rack) {
            html += `
                <tr>
                    <td><strong>${rack.rack_id}</strong></td>
                    <td>${rack.product_name}</td>
                    <td>${rack.initial_quantity}</td>
                    <td>${rack.current_quantity}</td>
                    <td>${rack.dispatched_quantity}</td>
                    <td>${rack.current_weight}</td>
                    <td>${getStatusBadge(rack.status)}</td>
                </tr>`;
        });
        tbody.innerHTML = html;
    }

    function flashLiveIndicator() {
        const indicator = document.getElementById('liveIndicator');
        if (indicator) {
            indicator.style.opacity = '0.4';
            setTimeout(function () {
                indicator.style.opacity = '1';
            }, 300);
        }
    }

    function refreshDashboard() {
        fetch('/api/dashboard', {
            method: 'GET',
            credentials: 'same-origin',
            cache: 'no-store',
            headers: { 'Accept': 'application/json' },
        })
            .then(function (response) {
                if (response.redirected || response.status === 401) {
                    window.location.href = '/login';
                    return null;
                }
                if (!response.ok) throw new Error('Network error');
                return response.json();
            })
            .then(function (data) {
                if (!data) return;
                updateKPIs(data.kpis);
                updateAlerts(data.racks);
                updateTable(data.racks);
                flashLiveIndicator();
            })
            .catch(function () {
                /* Server restarting — retry on next interval instead of crashing */
            });
    }

    if (document.getElementById('inventoryTable')) {
        setInterval(refreshDashboard, REFRESH_INTERVAL);
    }
})();

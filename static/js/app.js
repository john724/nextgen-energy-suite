// API Base URL
const API_BASE = '/api';

// Shared Chart Options for dark glassmorphism theme
const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    color: '#94A3B8',
    plugins: {
        legend: {
            labels: { color: '#FFFFFF', font: { family: 'Outfit', size: 13 } }
        },
        tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            titleColor: '#FFFFFF',
            bodyColor: '#94A3B8',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            padding: 12,
            cornerRadius: 8
        }
    },
    scales: {
        x: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#94A3B8', font: { family: 'Outfit' } }
        },
        y: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#94A3B8', font: { family: 'Outfit' } }
        }
    }
};

// State to track if charts are initialized
let charts = {
    b2b: null,
    p2p: null,
    ev: null
};

// ── Tab Management ───────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(button => {
    button.addEventListener('click', () => {
        // Remove active class from all buttons and contents
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        
        // Add active class to clicked button and target content
        button.classList.add('active');
        const targetId = button.getAttribute('data-target');
        document.getElementById(targetId).classList.add('active');
        
        // Load data if not already loaded
        if (targetId === 'b2b-tab' && !charts.b2b) loadB2BData();
        if (targetId === 'p2p-tab' && !charts.p2p) loadP2PData();
        if (targetId === 'ev-tab' && !charts.ev) loadEVData();
    });
});

// Helper to format currency
const formatEur = (value) => new Intl.NumberFormat('en-EU', { style: 'currency', currency: 'EUR' }).format(value);

// Helper to create Stat Box HTML
const createStatBox = (label, value, isHighlight = false) => `
    <div class="stat-box">
        <div class="stat-label">${label}</div>
        <div class="stat-value ${isHighlight ? 'highlight' : ''}">${value}</div>
    </div>
`;

// ── Data Fetching & Rendering ────────────────────────────────────────────────

async function loadB2BData() {
    try {
        const response = await fetch(`${API_BASE}/b2b`);
        const data = await response.json();
        
        // Update Stats
        const statsHtml = `
            ${createStatBox('Optimized Cost / Day', formatEur(data.metrics.optimised_cost_eur), true)}
            ${createStatBox('Total Daily Savings', formatEur(data.metrics.total_cost_saving_eur))}
            ${createStatBox('Carbon Reduction', data.metrics.carbon_reduction_pct.toFixed(1) + '%')}
            ${createStatBox('BESS Arbitrage', formatEur(data.metrics.bess_arbitrage_eur))}
        `;
        document.getElementById('b2b-stats').innerHTML = statsHtml;

        // Render Chart (Dual Axis)
        const ctx = document.getElementById('b2bChart').getContext('2d');
        charts.b2b = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.chart_data.hours.map(h => `${h}:00`),
                datasets: [
                    {
                        label: 'Net Load (kW)',
                        data: data.chart_data.net_load_kw,
                        backgroundColor: 'rgba(6, 182, 212, 0.5)',
                        borderColor: '#06B6D4',
                        borderWidth: 1,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Spot Price (€/kWh)',
                        data: data.chart_data.spot_prices,
                        type: 'line',
                        borderColor: '#10B981',
                        backgroundColor: '#10B981',
                        tension: 0.4,
                        borderWidth: 3,
                        pointRadius: 4,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                ...chartOptions,
                scales: {
                    ...chartOptions.scales,
                    y: { ...chartOptions.scales.y, type: 'linear', display: true, position: 'left', title: {display: true, text: 'kW', color: '#94A3B8'} },
                    y1: { type: 'linear', display: true, position: 'right', grid: {drawOnChartArea: false}, title: {display: true, text: '€', color: '#94A3B8'} }
                }
            }
        });
    } catch (err) {
        document.getElementById('b2b-stats').innerHTML = '<div class="stat-box">Error loading data. Is the FastAPI server running?</div>';
        console.error(err);
    }
}

async function loadP2PData() {
    try {
        const response = await fetch(`${API_BASE}/p2p`);
        const data = await response.json();
        
        // Update Stats
        const welfareGain = data.metrics.consumer_surplus_eur + data.metrics.producer_surplus_eur;
        const statsHtml = `
            ${createStatBox('Total Welfare Gain', formatEur(welfareGain), true)}
            ${createStatBox('Volume Traded', data.metrics.total_p2p_energy_kwh.toFixed(1) + ' kWh')}
            ${createStatBox('Avg Clearing Price', formatEur(data.metrics.avg_price_eur) + '/kWh')}
            ${createStatBox('Local Coverage', data.metrics.local_coverage_pct.toFixed(1) + '%')}
        `;
        document.getElementById('p2p-stats').innerHTML = statsHtml;

        // Render Chart
        const ctx = document.getElementById('p2pChart').getContext('2d');
        const labels = data.participants.map(p => p.name.split(' ')[0]);
        const benefits = data.participants.map(p => p.net_benefit);
        
        charts.p2p = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Net Benefit vs Grid-Only (€)',
                    data: benefits,
                    backgroundColor: benefits.map(b => b >= 0 ? 'rgba(16, 185, 129, 0.6)' : 'rgba(239, 68, 68, 0.6)'),
                    borderColor: benefits.map(b => b >= 0 ? '#10B981' : '#EF4444'),
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: chartOptions
        });
    } catch (err) {
        console.error(err);
    }
}

async function loadEVData() {
    try {
        const response = await fetch(`${API_BASE}/ev`);
        const data = await response.json();
        
        // Update Stats
        const statsHtml = `
            ${createStatBox('Annual Fleet Savings', formatEur(data.metrics.annual_benefit_eur), true)}
            ${createStatBox('V2G Grid Revenue', formatEur(data.metrics.v2g_revenue_eur))}
            ${createStatBox('Smart Charge Savings', formatEur(data.metrics.smart_charge_saving_eur))}
            ${createStatBox('Vehicles Ready', `${data.metrics.vehicles_ready} / ${data.metrics.fleet_size}`)}
        `;
        document.getElementById('ev-stats').innerHTML = statsHtml;

        // Render Chart
        const ctx = document.getElementById('evChart').getContext('2d');
        const labels = data.vehicles.map(v => v.id);
        const naiveCosts = data.vehicles.map(v => v.cost + (v.cost * 1.5)); // Mocked naive cost offset for visual display
        const smartCosts = data.vehicles.map(v => v.cost);
        
        charts.ev = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Smart TCO Cost (€)',
                        data: smartCosts,
                        backgroundColor: 'rgba(6, 182, 212, 0.8)',
                    },
                    {
                        label: 'V2G Revenue Earned (€)',
                        data: data.vehicles.map(v => v.v2g_revenue),
                        backgroundColor: 'rgba(16, 185, 129, 0.8)',
                    }
                ]
            },
            options: {
                ...chartOptions,
                scales: {
                    x: { stacked: true, ...chartOptions.scales.x },
                    y: { stacked: true, ...chartOptions.scales.y, title: {display: true, text: '€', color: '#94A3B8'} }
                }
            }
        });
    } catch (err) {
        console.error(err);
    }
}

// Initial Load for B2B Tab
loadB2BData();

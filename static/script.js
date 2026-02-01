// Update this URL to your deployed Render URL for production if needed, or use relative /api
const API_BASE = "/api";
let currentChart = null;

const emojiMap = {
    "Aggressive Buyer": "🐂",
    "Aggressive Seller": "🐻",
    "Near POI": "🔵",
    "Point of Release": "🚀",
    "Sellers Absorption": "🟣",
    "Buyers Absorption": "🟣",
    "Absorption (L-Shadow)": "🟣",
    "Absorption (U-Shadow)": "🟣"
};

async function fetchLatestSignals() {
    try {
        const response = await fetch(`${API_BASE}/signals`);
        const data = await response.json();
        
        if (data.error) {
            console.error("API Error:", data.error);
            return;
        }

        renderTable(data);
        updateStats(data);
        
        // Auto-load first symbol's chart if none selected
        if (!currentChart && data.length > 0) {
            loadHistoricalData(data[0].Symbol);
        }
    } catch (err) {
        console.error("Fetch Error:", err);
    }
}

async function loadHistoricalData(symbol) {
    document.getElementById('selected-symbol-display').textContent = `Loading ${symbol}...`;
    try {
        const response = await fetch(`${API_BASE}/historical/${symbol}`);
        const data = await response.json();
        
        if (data.error) {
            console.error("Historical API Error:", data.error);
            return;
        }

        document.getElementById('selected-symbol-display').textContent = symbol;
        renderChart(symbol, data);
    } catch (err) {
        console.error("Historical Fetch Error:", err);
    }
}

function renderTable(signals) {
    const tbody = document.getElementById('signal-body');
    tbody.innerHTML = '';

    if (signals.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 50px; color: var(--text-secondary);">No active signals detected.</td></tr>';
        return;
    }

    signals.forEach(sig => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.onclick = () => loadHistoricalData(sig.Symbol);
        
        const signalBadges = sig.Signals.split(', ').map(s => {
            let className = 'signal-badge';
            const lowerS = s.toLowerCase();
            if (lowerS.includes('buyer')) className += ' signal-buyer';
            else if (lowerS.includes('seller')) className += ' signal-seller';
            else if (lowerS.includes('poi') || lowerS.includes('release')) className += ' signal-poi';
            else if (lowerS.includes('absorption')) className += ' signal-absorption';
            
            return `<span class="${className}">${s}</span>`;
        }).join(' ');

        tr.innerHTML = `
            <td style="font-weight: 700; color: var(--accent-color);">${sig.Symbol}</td>
            <td>${sig.Date}</td>
            <td>${sig.Close.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
            <td>${sig.Volume.toLocaleString()}</td>
            <td>${signalBadges}</td>
        `;
        tbody.appendChild(tr);
    });
}

function getEmojiForSignals(signalsStr) {
    if (!signalsStr) return null;
    const sigs = signalsStr.split(', ');
    for (const s of sigs) {
        if (emojiMap[s]) return emojiMap[s];
    }
    return "💡";
}

function renderChart(symbol, history) {
    const ctx = document.getElementById('signalChart').getContext('2d');
    
    if (currentChart) {
        currentChart.destroy();
    }

    const labels = history.map(h => h.Date);
    const prices = history.map(h => h.Close);
    const pointLabels = history.map(h => getEmojiForSignals(h.Signals));

    currentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Price',
                data: prices,
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88, 166, 255, 0.1)',
                borderWidth: 2,
                pointRadius: (ctx) => pointLabels[ctx.dataIndex] ? 12 : 0,
                pointHoverRadius: 15,
                pointStyle: (ctx) => {
                    const emoji = pointLabels[ctx.dataIndex];
                    if (!emoji) return 'circle';
                    
                    // Create emoji point style
                    const canvas = document.createElement('canvas');
                    canvas.width = 24;
                    canvas.height = 24;
                    const cctx = canvas.getContext('2d');
                    cctx.font = '18px serif';
                    cctx.textAlign = 'center';
                    cctx.textBaseline = 'middle';
                    cctx.fillText(emoji, 12, 12);
                    return canvas;
                },
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#8b949e', maxTicksLimit: 10 }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#8b949e' }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        afterBody: (context) => {
                            const index = context[0].dataIndex;
                            const signals = history[index].Signals;
                            return signals ? `Signals: ${signals}` : '';
                        }
                    }
                }
            }
        }
    });
}

function updateStats(signals) {
    document.getElementById('total-signals').textContent = signals.length;
    if (signals.length > 0) {
        const counts = {};
        signals.forEach(s => counts[s.Symbol] = (counts[s.Symbol] || 0) + 1);
        const top = Object.keys(counts).reduce((a, b) => counts[a] > counts[b] ? a : b);
        document.getElementById('top-symbol').textContent = top;
    }
    document.getElementById('last-refresh').textContent = new Date().toLocaleTimeString();
}

// Initial fetch
fetchLatestSignals();
setInterval(fetchLatestSignals, 5 * 60 * 1000);

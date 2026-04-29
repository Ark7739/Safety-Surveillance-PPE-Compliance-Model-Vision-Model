/**
 * SafetyVision AI — Frontend Application
 * ========================================
 * Handles SocketIO real-time updates, video feed management,
 * compliance gauge animation, Chart.js trend chart, and UI interactions.
 */

// ─── State ──────────────────────────────────────────────

const state = {
    isMonitoring: false,
    sessionId: null,
    source: null,
    alertCount: 0,
    complianceHistory: [],
    maxHistoryPoints: 60,
};

// ─── SocketIO Connection ────────────────────────────────

const socket = io({ transports: ['websocket', 'polling'] });

socket.on('connect', () => {
    console.log('🔌 Connected to server');
});

socket.on('disconnect', () => {
    console.log('🔌 Disconnected');
    updateStatus('idle', 'Disconnected');
});

socket.on('status', (data) => {
    if (data.is_monitoring) {
        setMonitoringState(true);
        state.sessionId = data.session_id;
        state.source = data.source;
    }
});

socket.on('stats_update', (data) => {
    updateStatsUI(data);
});

socket.on('violation_alert', (data) => {
    addViolationAlert(data);
});

socket.on('monitoring_stopped', () => {
    setMonitoringState(false);
});

// ─── Video Source Management ────────────────────────────

const sourceSelect = document.getElementById('source-select');
const fileUploadVideo = document.getElementById('file-upload-video');
const fileUploadImage = document.getElementById('file-upload-image');
const fileUploadManual = document.getElementById('file-upload-manual');
const rtspInput = document.getElementById('rtsp-input');
const videoFeed = document.getElementById('video-feed');
const manualImageResult = document.getElementById('manual-image-result');
const placeholder = document.getElementById('video-placeholder');

// ─── Mode Switching ────────────────────────────────────

function switchMode(mode) {
    // Stop live stream if switching to manual
    if (mode === 'manual' && state.isMonitoring) {
        stopMonitoring();
    }

    // Toggle UI buttons
    document.getElementById('btn-mode-live').classList.toggle('active', mode === 'live');
    document.getElementById('btn-mode-manual').classList.toggle('active', mode === 'manual');

    // Toggle Controls
    document.getElementById('live-controls').classList.toggle('hidden', mode !== 'live');
    document.getElementById('manual-controls').classList.toggle('hidden', mode !== 'manual');

    // Toggle Video Area
    if (mode === 'manual') {
        videoFeed.classList.add('hidden');
        document.getElementById('recording-badge').classList.add('hidden');
        if (!manualImageResult.src || manualImageResult.src.endsWith(window.location.host + '/')) {
            placeholder.classList.remove('hidden');
            document.getElementById('placeholder-text').innerHTML = "Select an image to detect PPE";
        } else {
            placeholder.classList.add('hidden');
            manualImageResult.classList.remove('hidden');
        }
    } else {
        manualImageResult.classList.add('hidden');
        if (state.isMonitoring) {
            placeholder.classList.add('hidden');
            videoFeed.classList.remove('hidden');
        } else {
            placeholder.classList.remove('hidden');
            document.getElementById('placeholder-text').innerHTML = "Select a video source and click <strong>Start Monitoring</strong>";
            videoFeed.classList.add('hidden');
        }
    }
}

sourceSelect.addEventListener('change', () => {
    const value = sourceSelect.value;
    rtspInput.classList.toggle('hidden', value !== 'rtsp');
    if (value === 'upload_video') {
        fileUploadVideo.click();
    } else if (value === 'upload_image') {
        fileUploadImage.click();
    }
});

async function handleFileUpload(file, typeIcon, inputElement) {
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.status === 'uploaded') {
            // Add as option and select it
            const option = document.createElement('option');
            option.value = data.filepath;
            option.textContent = `${typeIcon} ${data.filename}`;
            sourceSelect.appendChild(option);
            sourceSelect.value = data.filepath;
            
            // Auto-start if it is an image
            if (typeIcon === '🖼️') {
                startMonitoring();
            }
        }
    } catch (err) {
        console.error('Upload failed:', err);
    } finally {
        if (inputElement) inputElement.value = '';
    }
}

fileUploadVideo.addEventListener('change', (e) => {
    handleFileUpload(e.target.files[0], '📁', e.target);
});

fileUploadImage.addEventListener('change', (e) => {
    handleFileUpload(e.target.files[0], '🖼️', e.target);
});

fileUploadManual.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Show loading state
    manualImageResult.classList.add('hidden');
    placeholder.classList.remove('hidden');
    document.getElementById('placeholder-text').innerHTML = "⚙️ Processing Image... Please wait.";

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/detect_image', { method: 'POST', body: formData });
        const data = await res.json();
        
        if (data.status === 'success') {
            // Display Image
            manualImageResult.src = data.image_b64;
            manualImageResult.classList.remove('hidden');
            placeholder.classList.add('hidden');
            
            // Update Stats
            updateStatsUI(data.stats);
            
            // Clear old alerts and add new ones
            document.getElementById('alerts-list').innerHTML = '';
            state.alertCount = 0;
            document.getElementById('alert-count-badge').textContent = '0';
            document.getElementById('alert-count-badge').classList.remove('has-alerts');
            
            if (data.violations && data.violations.length > 0) {
                data.violations.forEach(v => addViolationAlert(v));
            } else {
                document.getElementById('alerts-list').innerHTML = '<div class="alert-empty">No violations detected</div>';
            }
        } else {
            alert(data.error || 'Failed to detect image');
            document.getElementById('placeholder-text').innerHTML = "Select an image to detect PPE";
        }
    } catch (err) {
        console.error('Detection failed:', err);
        alert('Failed to connect to server');
        document.getElementById('placeholder-text').innerHTML = "Select an image to detect PPE";
    } finally {
        e.target.value = '';
    }
});

// ─── Confidence Slider ─────────────────────────────────

const confidenceSlider = document.getElementById('confidence-slider');
const confidenceValue = document.getElementById('confidence-value');

confidenceSlider.addEventListener('input', () => {
    confidenceValue.textContent = parseFloat(confidenceSlider.value).toFixed(2);
});

confidenceSlider.addEventListener('change', () => {
    updateSettings();
});

// ─── PPE Toggles ───────────────────────────────────────

document.querySelectorAll('.ppe-toggle').forEach(toggle => {
    toggle.addEventListener('change', () => {
        updateSettings();
    });
});

function getRequiredPPE() {
    const required = [];
    document.querySelectorAll('.ppe-toggle:checked').forEach(toggle => {
        required.push(toggle.dataset.ppe);
    });
    return required;
}

async function updateSettings() {
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                confidence: parseFloat(confidenceSlider.value),
                required_ppe: getRequiredPPE(),
            }),
        });
    } catch (err) {
        console.error('Settings update failed:', err);
    }
}

// ─── Monitoring Controls ────────────────────────────────

async function startMonitoring() {
    let source = sourceSelect.value;
    if (source === 'rtsp') {
        source = rtspInput.value;
        if (!source) { alert('Enter RTSP URL'); return; }
    }
    if (source === 'upload_video') {
        fileUploadVideo.click();
        return;
    }
    if (source === 'upload_image') {
        fileUploadImage.click();
        return;
    }

    try {
        const res = await fetch('/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source }),
        });
        const data = await res.json();
        if (data.status === 'started') {
            state.sessionId = data.session_id;
            setMonitoringState(true);
        } else {
            alert(data.error || 'Failed to start');
        }
    } catch (err) {
        console.error('Start failed:', err);
        alert('Failed to connect to server');
    }
}

async function stopMonitoring() {
    try {
        await fetch('/api/stop', { method: 'POST' });
        setMonitoringState(false);
    } catch (err) {
        console.error('Stop failed:', err);
    }
}

function setMonitoringState(active) {
    state.isMonitoring = active;
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');
    const recBadge = document.getElementById('recording-badge');

    if (active) {
        btnStart.classList.add('hidden');
        btnStop.classList.remove('hidden');
        placeholder.classList.add('hidden');
        videoFeed.classList.remove('hidden');
        manualImageResult.classList.add('hidden');
        videoFeed.src = '/video_feed?' + Date.now();
        recBadge.classList.remove('hidden');
        updateStatus('active', 'Monitoring');
    } else {
        btnStart.classList.remove('hidden');
        btnStop.classList.add('hidden');
        recBadge.classList.add('hidden');
        updateStatus('idle', 'Idle');
        // Keep last frame visible
    }
}

function updateStatus(type, text) {
    const indicator = document.getElementById('status-indicator');
    const dot = indicator.querySelector('.status-dot');
    const textEl = indicator.querySelector('.status-text');
    dot.className = 'status-dot ' + type;
    textEl.textContent = text;
}

// ─── Stats UI Update ────────────────────────────────────

function updateStatsUI(data) {
    // FPS
    document.querySelector('#fps-badge .fps-value').textContent = data.fps || 0;
    document.querySelector('#frame-badge .frame-value').textContent = data.frame_number || 0;

    // Gauge
    updateGauge(data.compliance_rate || 0);

    // Counts
    document.getElementById('compliant-count').textContent = data.compliant || 0;
    document.getElementById('total-count').textContent = data.total_persons || 0;
    document.getElementById('violation-count').textContent = data.non_compliant || 0;

    // Detection counts
    const counts = data.detection_counts || {};
    const ppeTypes = ['helmet', 'vest', 'gloves', 'goggles', 'boots', 'harness'];
    ppeTypes.forEach(ppe => {
        const el = document.getElementById(`det-${ppe}`);
        if (el) el.textContent = counts[ppe] || 0;
    });

    // Update compliance chart
    addChartDataPoint(data.compliance_rate || 0, data.timestamp || '');
}

// ─── Compliance Gauge ──────────────────────────────────

function updateGauge(rate) {
    const gaugeValue = document.getElementById('gauge-value');
    const gaugeFill = document.getElementById('gauge-fill');

    gaugeValue.textContent = Math.round(rate);

    // Arc length: 251 is the full arc path length
    const offset = 251 - (251 * rate / 100);
    gaugeFill.style.strokeDashoffset = offset;

    // Change color based on compliance rate
    let color;
    if (rate >= 80) color = '#10b981';
    else if (rate >= 50) color = '#f59e0b';
    else color = '#ef4444';

    gaugeFill.style.stroke = color;
}

// ─── Violation Alerts ──────────────────────────────────

function addViolationAlert(data) {
    state.alertCount++;
    const badge = document.getElementById('alert-count-badge');
    badge.textContent = state.alertCount;
    badge.classList.add('has-alerts');

    const alertsList = document.getElementById('alerts-list');

    // Remove "no violations" placeholder
    const empty = alertsList.querySelector('.alert-empty');
    if (empty) empty.remove();

    // Create alert item
    const alertItem = document.createElement('div');
    alertItem.className = 'alert-item';
    alertItem.innerHTML = `
        <div class="alert-icon">⚠️</div>
        <div class="alert-content">
            <div class="alert-title">Worker #${data.person_id + 1} — Non-Compliant</div>
            <div class="alert-detail">Missing: ${data.missing_ppe.join(', ')}</div>
        </div>
        <div class="alert-time">${data.timestamp}</div>
    `;

    // Prepend (newest first)
    alertsList.insertBefore(alertItem, alertsList.firstChild);

    // Limit to 50 alerts in DOM
    while (alertsList.children.length > 50) {
        alertsList.removeChild(alertsList.lastChild);
    }

    // Play alert sound (subtle)
    playAlertSound();
}

function playAlertSound() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = 800;
        gain.gain.value = 0.05;
        osc.start();
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
        osc.stop(ctx.currentTime + 0.15);
    } catch (e) { /* ignore audio errors */ }
}

// ─── Compliance Trend Chart ─────────────────────────────

let complianceChart = null;

function initChart() {
    const ctx = document.getElementById('compliance-chart').getContext('2d');

    const gradient = ctx.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, 'rgba(0, 212, 255, 0.2)');
    gradient.addColorStop(1, 'rgba(0, 212, 255, 0.0)');

    complianceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Compliance %',
                data: [],
                borderColor: '#00d4ff',
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointHoverBackgroundColor: '#00d4ff',
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(17, 24, 39, 0.9)',
                    titleColor: '#94a3b8',
                    bodyColor: '#f1f5f9',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    padding: 10,
                    cornerRadius: 8,
                    callbacks: {
                        label: (ctx) => `Compliance: ${ctx.parsed.y.toFixed(1)}%`
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: { color: 'rgba(255,255,255,0.03)' },
                    ticks: { color: '#475569', font: { size: 10 }, maxTicksLimit: 10 },
                },
                y: {
                    display: true,
                    min: 0, max: 100,
                    grid: { color: 'rgba(255,255,255,0.03)' },
                    ticks: {
                        color: '#475569',
                        font: { size: 10 },
                        callback: (v) => v + '%',
                        stepSize: 25,
                    }
                }
            },
            animation: { duration: 300 }
        }
    });
}

function addChartDataPoint(rate, timestamp) {
    if (!complianceChart) return;

    const data = complianceChart.data;
    data.labels.push(timestamp);
    data.datasets[0].data.push(rate);

    // Keep only last N points
    if (data.labels.length > state.maxHistoryPoints) {
        data.labels.shift();
        data.datasets[0].data.shift();
    }

    complianceChart.update('none'); // No animation for performance
}

// ─── Report Download ────────────────────────────────────

async function downloadReport() {
    const sessionId = state.sessionId;
    if (!sessionId) {
        alert('No active session. Start monitoring first.');
        return;
    }

    try {
        const res = await fetch(`/api/report?session_id=${sessionId}`);
        const report = await res.json();

        // Download as JSON
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `ppe_compliance_report_${sessionId}_${new Date().toISOString().slice(0,10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
    } catch (err) {
        console.error('Report download failed:', err);
        alert('Failed to generate report');
    }
}

// ─── Initialize ─────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initChart();

    // Add SVG gradient for gauge (needs to be in SVG)
    const gaugeSvg = document.querySelector('.gauge-svg');
    if (gaugeSvg) {
        const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        defs.innerHTML = `
            <linearGradient id="gauge-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#ef4444"/>
                <stop offset="50%" stop-color="#f59e0b"/>
                <stop offset="100%" stop-color="#10b981"/>
            </linearGradient>
        `;
        gaugeSvg.insertBefore(defs, gaugeSvg.firstChild);
    }

    // Check initial status
    fetch('/api/status')
        .then(r => r.json())
        .then(data => {
            if (data.is_monitoring) {
                setMonitoringState(true);
                state.sessionId = data.session_id;
            }
        })
        .catch(() => {});

    console.log('✅ SafetyVision AI Dashboard initialized');
});

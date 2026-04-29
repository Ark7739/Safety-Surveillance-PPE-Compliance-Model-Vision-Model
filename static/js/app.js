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
    // Browser webcam state
    browserCamActive: false,
    browserCamStream: null,
    browserCamLoop: null,
    browserCamProcessing: false,
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
    // Stop any active streams
    if (mode !== 'live' && state.isMonitoring) {
        stopMonitoring();
    }
    if (mode !== 'browser-cam' && state.browserCamActive) {
        stopBrowserCam();
    }

    // Toggle UI buttons
    document.getElementById('btn-mode-live').classList.toggle('active', mode === 'live');
    document.getElementById('btn-mode-browser-cam').classList.toggle('active', mode === 'browser-cam');
    document.getElementById('btn-mode-manual').classList.toggle('active', mode === 'manual');

    // Toggle Controls
    document.getElementById('live-controls').classList.toggle('hidden', mode !== 'live');
    document.getElementById('browser-cam-controls').classList.toggle('hidden', mode !== 'browser-cam');
    document.getElementById('manual-controls').classList.toggle('hidden', mode !== 'manual');

    // Hide all video elements first
    videoFeed.classList.add('hidden');
    manualImageResult.classList.add('hidden');
    document.getElementById('browser-cam-preview').classList.add('hidden');
    document.getElementById('browser-cam-result').classList.add('hidden');
    document.getElementById('recording-badge').classList.add('hidden');

    // Show correct video area
    if (mode === 'manual') {
        if (!manualImageResult.src || manualImageResult.src.endsWith(window.location.host + '/')) {
            placeholder.classList.remove('hidden');
            document.getElementById('placeholder-text').innerHTML = "Select an image to detect PPE";
        } else {
            placeholder.classList.add('hidden');
            manualImageResult.classList.remove('hidden');
        }
    } else if (mode === 'browser-cam') {
        placeholder.classList.remove('hidden');
        document.getElementById('placeholder-text').innerHTML = `
            <div style="display:flex;flex-direction:column;align-items:center;gap:8px;">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M23 7l-7 5 7 5V7z"></path><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>
                <span>Click <strong>Start Camera</strong> to use your browser webcam</span>
                <span style="font-size:0.8rem;opacity:0.6;">Works on cloud deployments — camera runs in your browser</span>
            </div>`;
    } else {
        if (state.isMonitoring) {
            placeholder.classList.add('hidden');
            videoFeed.classList.remove('hidden');
        } else {
            placeholder.classList.remove('hidden');
            document.getElementById('placeholder-text').innerHTML = "Select a video source and click <strong>Start Monitoring</strong>";
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

// ─── Browser Webcam Mode ───────────────────────────────────────

async function startBrowserCam() {
    const preview = document.getElementById('browser-cam-preview');
    const resultImg = document.getElementById('browser-cam-result');
    const canvas = document.getElementById('browser-cam-canvas');
    const fpsLabel = document.getElementById('browser-cam-fps');

    try {
        // Request camera access
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'environment' },
            audio: false
        });

        state.browserCamStream = stream;
        state.browserCamActive = true;

        // Show preview briefly then switch to result display
        preview.srcObject = stream;
        preview.classList.remove('hidden');
        placeholder.classList.add('hidden');

        // Toggle buttons
        document.getElementById('btn-cam-start').classList.add('hidden');
        document.getElementById('btn-cam-stop').classList.remove('hidden');
        updateStatus('active', 'Browser Cam');
        document.getElementById('recording-badge').classList.remove('hidden');

        // Wait for video to be ready
        await new Promise(resolve => {
            preview.onloadedmetadata = resolve;
        });

        // Set canvas size to match video
        canvas.width = preview.videoWidth;
        canvas.height = preview.videoHeight;
        const ctx = canvas.getContext('2d');

        // Start frame capture loop
        let frameCount = 0;
        let lastFpsTime = Date.now();

        async function captureAndDetect() {
            if (!state.browserCamActive) return;
            if (state.browserCamProcessing) {
                // Skip frame if previous one is still processing
                state.browserCamLoop = requestAnimationFrame(captureAndDetect);
                return;
            }

            state.browserCamProcessing = true;

            try {
                // Draw current video frame to canvas
                ctx.drawImage(preview, 0, 0);

                // Convert to blob
                const blob = await new Promise(resolve => {
                    canvas.toBlob(resolve, 'image/jpeg', 0.7);
                });

                // Send to server for detection
                const formData = new FormData();
                formData.append('file', blob, 'frame.jpg');

                const res = await fetch('/api/detect_image', { method: 'POST', body: formData });
                const data = await res.json();

                if (data.status === 'success' && state.browserCamActive) {
                    // Show annotated result (hide preview, show result)
                    resultImg.src = data.image_b64;
                    resultImg.classList.remove('hidden');
                    preview.classList.add('hidden');

                    // Update stats
                    updateStatsUI(data.stats);

                    // Handle violations
                    if (data.violations && data.violations.length > 0) {
                        data.violations.forEach(v => addViolationAlert(v));
                    }

                    // FPS counter
                    frameCount++;
                    const now = Date.now();
                    if (now - lastFpsTime >= 1000) {
                        const fps = frameCount / ((now - lastFpsTime) / 1000);
                        fpsLabel.textContent = `${fps.toFixed(1)} FPS`;
                        document.querySelector('#fps-badge .fps-value').textContent = fps.toFixed(1);
                        frameCount = 0;
                        lastFpsTime = now;
                    }
                }
            } catch (err) {
                console.error('Browser cam frame error:', err);
            } finally {
                state.browserCamProcessing = false;
            }

            // Schedule next frame capture
            if (state.browserCamActive) {
                // Small delay to avoid overwhelming the server
                setTimeout(() => {
                    state.browserCamLoop = requestAnimationFrame(captureAndDetect);
                }, 100); // ~10 FPS max request rate
            }
        }

        // Start the loop
        state.browserCamLoop = requestAnimationFrame(captureAndDetect);

    } catch (err) {
        console.error('Camera access failed:', err);
        if (err.name === 'NotAllowedError') {
            alert('Camera access denied. Please allow camera permission and try again.');
        } else if (err.name === 'NotFoundError') {
            alert('No camera found on this device.');
        } else {
            alert('Failed to access camera: ' + err.message);
        }
    }
}

function stopBrowserCam() {
    state.browserCamActive = false;

    // Cancel animation frame
    if (state.browserCamLoop) {
        cancelAnimationFrame(state.browserCamLoop);
        state.browserCamLoop = null;
    }

    // Stop camera stream
    if (state.browserCamStream) {
        state.browserCamStream.getTracks().forEach(track => track.stop());
        state.browserCamStream = null;
    }

    // Reset UI
    const preview = document.getElementById('browser-cam-preview');
    const resultImg = document.getElementById('browser-cam-result');
    preview.srcObject = null;
    preview.classList.add('hidden');
    resultImg.classList.add('hidden');
    document.getElementById('btn-cam-start').classList.remove('hidden');
    document.getElementById('btn-cam-stop').classList.add('hidden');
    document.getElementById('recording-badge').classList.add('hidden');
    document.getElementById('browser-cam-fps').textContent = '';
    placeholder.classList.remove('hidden');
    document.getElementById('placeholder-text').innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px;">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M23 7l-7 5 7 5V7z"></path><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>
            <span>Click <strong>Start Camera</strong> to use your browser webcam</span>
            <span style="font-size:0.8rem;opacity:0.6;">Works on cloud deployments — camera runs in your browser</span>
        </div>`;
    updateStatus('idle', 'Idle');
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

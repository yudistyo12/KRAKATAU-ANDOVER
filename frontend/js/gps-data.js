// ============================================================
// GPS TELEMETRY CLIENT
// ============================================================
const GPSData = {
    data: {
        lat: null,
        lon: null,
        speed: null,
        course: null,
        heading: null,
        fix: false
    },
    pathHistory: [],
    MAX_PATH_LENGTH: 200,
    fetchInProgress: false,
    visualPosition: null,
    visualHistory: [],
    lastMotionTime: null,
    animationFrame: null,

    updateVisualMotion(data) {
        const now = performance.now();
        const elapsed = this.lastMotionTime === null
            ? 0
            : Math.min((now - this.lastMotionTime) / 1000, 1);
        const heading = Number(data.heading ?? data.course);
        const speed = Math.max(Number(data.speed) || 0, 0);

        if (!this.visualPosition) {
            const lane = new URLSearchParams(window.location.search).get('lane');
            this.visualPosition = { x: lane === 'B' ? 0.12 : 0.88, y: 0.82 };
        } else if (Number.isFinite(heading) && speed > 0 && elapsed > 0) {
            const headingRadians = heading * Math.PI / 180;
            const movement = Math.min(speed * elapsed * 0.012, 0.025);
            this.visualPosition.x += Math.sin(headingRadians) * movement;
            this.visualPosition.y -= Math.cos(headingRadians) * movement;
            this.visualPosition.x = Math.max(0.04, Math.min(0.96, this.visualPosition.x));
            this.visualPosition.y = Math.max(0.08, Math.min(0.92, this.visualPosition.y));
        }

        this.lastMotionTime = now;
        const lastVisualPoint = this.visualHistory[this.visualHistory.length - 1];
        if (!lastVisualPoint || lastVisualPoint.x !== this.visualPosition.x || lastVisualPoint.y !== this.visualPosition.y) {
            this.visualHistory.push({ ...this.visualPosition });
            if (this.visualHistory.length > this.MAX_PATH_LENGTH) this.visualHistory.shift();
        }
    },

    async fetch() {
        if (this.fetchInProgress) return;
        this.fetchInProgress = true;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 4500);

        try {
            const response = await fetch(CONFIG.TELEMETRY, {
                method: 'GET',
                cache: 'no-cache',
                signal: controller.signal
            });
            if (!response.ok) throw new Error('GPS telemetry request failed');

            const data = await response.json();
            this.data = data;
            this.updateVisualMotion(data);

            if (data.fix && Number.isFinite(Number(data.lat)) && Number.isFinite(Number(data.lon))) {
                const point = {
                    lat: Number(data.lat),
                    lon: Number(data.lon)
                };
                const lastPoint = this.pathHistory[this.pathHistory.length - 1];

                if (!lastPoint || lastPoint.lat !== point.lat || lastPoint.lon !== point.lon) {
                    this.pathHistory.push(point);
                    if (this.pathHistory.length > this.MAX_PATH_LENGTH) this.pathHistory.shift();
                }
            }
        } catch (error) {
            console.error('[GCS] Error fetching GPS telemetry:', error);
        } finally {
            clearTimeout(timeoutId);
            this.fetchInProgress = false;
        }

        if (window.VehicleState) window.VehicleState.render(this.data);
        if (window.VehicleState) window.VehicleState.pathHistory = this.pathHistory;
        if (window.GPSRenderer) window.GPSRenderer.draw();
    },

    clearPath() {
        this.pathHistory = [];
        this.visualHistory = this.visualPosition ? [{ ...this.visualPosition }] : [];
        if (window.VehicleState) window.VehicleState.pathHistory = this.pathHistory;
        if (window.GPSRenderer) window.GPSRenderer.draw();
    }
};

window.GPSData = GPSData;
setInterval(() => GPSData.fetch(), CONFIG.POLL_INTERVALS.TELEMETRY);
GPSData.fetch();

const clearPathBtn = document.getElementById('btn-clear-path');
if (clearPathBtn) clearPathBtn.addEventListener('click', () => GPSData.clearPath());

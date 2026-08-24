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
    position: null,
    targetPosition: null,
    animationFrame: null,

    animateToPosition(position) {
        const startPosition = this.position || position;
        const startTime = performance.now();
        const duration = Math.min(CONFIG.POLL_INTERVALS.TELEMETRY * 0.9, 900);

        this.targetPosition = position;

        const animate = currentTime => {
            const progress = Math.min((currentTime - startTime) / duration, 1);
            const easedProgress = 1 - Math.pow(1 - progress, 3);

            this.position = {
                lat: startPosition.lat + (position.lat - startPosition.lat) * easedProgress,
                lon: startPosition.lon + (position.lon - startPosition.lon) * easedProgress
            };

            if (window.GPSRenderer) window.GPSRenderer.draw();

            if (progress < 1) this.animationFrame = requestAnimationFrame(animate);
            else this.animationFrame = null;
        };

        if (this.animationFrame) cancelAnimationFrame(this.animationFrame);
        this.animationFrame = requestAnimationFrame(animate);
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

            if (data.fix && Number.isFinite(Number(data.lat)) && Number.isFinite(Number(data.lon))) {
                const point = {
                    lat: Number(data.lat),
                    lon: Number(data.lon)
                };
                this.animateToPosition(point);
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
        if (window.VehicleState) window.VehicleState.pathHistory = this.pathHistory;
        if (window.GPSRenderer) window.GPSRenderer.draw();
    }
};

window.GPSData = GPSData;
setInterval(() => GPSData.fetch(), CONFIG.POLL_INTERVALS.TELEMETRY);
GPSData.fetch();

const clearPathBtn = document.getElementById('btn-clear-path');
if (clearPathBtn) clearPathBtn.addEventListener('click', () => GPSData.clearPath());

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

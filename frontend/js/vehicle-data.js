// ============================================================
// REALTIME VEHICLE DATA & GPS PATH
// ============================================================
const VehicleState = {
    data: {
        lat: 0,
        lon: 0,
        speed: 0,
        course: 0,
        fix: false
    },
    pathHistory: [],
    MAX_PATH_LENGTH: 200,
    fetchInProgress: false,

    dom: {
        speed: document.getElementById('data-speed'),
        course: document.getElementById('data-course'),
        lat: document.getElementById('data-lat'),
        lon: document.getElementById('data-lon')
    },

    async fetch() {
        if (this.fetchInProgress) return;
        this.fetchInProgress = true;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 4500);

        try {
            const res = await fetch(CONFIG.TELEMETRY, {
                method: 'GET',
                cache: 'no-cache',
                signal: controller.signal
            });
            if (!res.ok) throw new Error('Vehicle data request failed');

            const data = await res.json();
            this.data = data;

            if (this.dom.speed) this.dom.speed.textContent = `${Number(data.speed || 0).toFixed(1)} m/s`;
            if (this.dom.course) this.dom.course.textContent = `${Number(data.course || 0).toFixed(1)} °`;
            if (this.dom.lat) this.dom.lat.textContent = Number(data.lat || 0).toFixed(6);
            if (this.dom.lon) this.dom.lon.textContent = Number(data.lon || 0).toFixed(6);

            if (data.fix && Number(data.lat || 0) !== 0 && Number(data.lon || 0) !== 0) {
                const currentLat = Number(data.lat);
                const currentLon = Number(data.lon);
                const lastPoint = this.pathHistory[this.pathHistory.length - 1];

                if (!lastPoint || lastPoint.lat !== currentLat || lastPoint.lon !== currentLon) {
                    this.pathHistory.push({ lat: currentLat, lon: currentLon });
                    if (this.pathHistory.length > this.MAX_PATH_LENGTH) this.pathHistory.shift();
                }
            }
        } catch (err) {
            console.error('[GCS] Error fetching vehicle data:', err);
        } finally {
            clearTimeout(timeoutId);
            this.fetchInProgress = false;
        }

        if (window.GPSRenderer) window.GPSRenderer.draw();
    },

    clearPath() {
        this.pathHistory = [];
        if (window.GPSRenderer) window.GPSRenderer.draw();
    }
};

window.VehicleState = VehicleState;

const clearPathBtn = document.getElementById('btn-clear-path');
if (clearPathBtn) clearPathBtn.addEventListener('click', () => VehicleState.clearPath());
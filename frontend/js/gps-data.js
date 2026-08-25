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
    lastSuccessfulFetch: null,
    visualPosition: null,
    visualHistory: [],
    lastMotionTime: null,
    sessionId: null,

    normalizeTelemetry(data) {
        const telemetry = data || {};
        const speed = telemetry.speed ?? telemetry.speed_knots ?? null;

        return {
            ...telemetry,
            lat: telemetry.lat ?? telemetry.latitude ?? null,
            lon: telemetry.lon ?? telemetry.longitude ?? null,
            speed,
            course: telemetry.course ?? telemetry.course_over_ground ?? null,
            fix: Boolean(telemetry.fix ?? telemetry.gps_valid)
        };
    },

    updateVisualMotion(data) {
        const now = performance.now();
        const elapsed = this.lastMotionTime === null ? 0 : Math.min((now - this.lastMotionTime) / 1000, 1);
        const heading = Number(data.heading ?? data.course);
        const speed = Number(data.motor_speed_mps ?? data.gps_speed_mps
            ?? data.speed) || 0;

        if (!this.visualPosition) {
            const lane = new URLSearchParams(window.location.search).get('lane');
            this.visualPosition = { x: lane === 'B' ? 0.12 : 0.88, y: 0.82 };
        } else if (Number.isFinite(heading) && elapsed > 0 && speed !== 0) {
            const radians = heading * Math.PI / 180;
            const movement = Math.max(-0.025, Math.min(0.025, speed * elapsed * 0.012));
            this.visualPosition.x += Math.sin(radians) * movement;
            this.visualPosition.y -= Math.cos(radians) * movement;
            this.visualPosition.x = Math.max(0.04, Math.min(0.96, this.visualPosition.x));
            this.visualPosition.y = Math.max(0.08, Math.min(0.92, this.visualPosition.y));
        }

        this.lastMotionTime = now;
        const lastPoint = this.visualHistory[this.visualHistory.length - 1];
        if (!lastPoint || lastPoint.x !== this.visualPosition.x || lastPoint.y !== this.visualPosition.y) {
            this.visualHistory.push({ ...this.visualPosition });
            if (this.visualHistory.length > this.MAX_PATH_LENGTH) this.visualHistory.shift();
        }
    },

    resetForNewSession() {
        this.pathHistory = [];
        this.visualHistory = [];
        this.visualPosition = null;
        this.lastMotionTime = null;
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

            const data = this.normalizeTelemetry(await response.json());
            if (data.session_id && this.sessionId && data.session_id !== this.sessionId) {
                this.resetForNewSession();
            }
            if (data.session_id) this.sessionId = data.session_id;
            this.data = data;
            this.lastSuccessfulFetch = Date.now();
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
            this.data = {
                ...this.data,
                gps_valid: false
            };
        } finally {
            clearTimeout(timeoutId);
            this.fetchInProgress = false;
        }

        if (window.VehicleState) window.VehicleState.render(this.data);
        if (window.VehicleState) window.VehicleState.pathHistory = this.pathHistory;
        if (window.GPSRenderer) window.GPSRenderer.draw();
    },

};

window.GPSData = GPSData;
setInterval(() => GPSData.fetch(), CONFIG.POLL_INTERVALS.TELEMETRY);
GPSData.fetch();

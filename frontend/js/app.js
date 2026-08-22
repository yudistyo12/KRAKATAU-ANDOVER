// ============================================================
// MAIN APP INITIALIZER & ROUTER
// ============================================================
const GCSApp = {
    getCurrentLane() {
        const urlParams = new URLSearchParams(window.location.search);
        const lane = urlParams.get('lane');
        return (lane === 'A' || lane === 'B') ? lane : 'A';
    },

    updateLaneDisplay() {
        const lane = this.getCurrentLane();
        const laneBadge = document.getElementById('lane-badge');

        if (laneBadge) laneBadge.textContent = `LANE ${lane}`;
    },

    updateClock() {
        const clock = document.getElementById('header-clock');
        if (!clock) return;

        const now = new Date();
        clock.dateTime = now.toISOString();
        clock.textContent = new Intl.DateTimeFormat('id-ID', {
            dateStyle: 'medium',
            timeStyle: 'medium'
        }).format(now);
    },

    init() {
        const urlParams = new URLSearchParams(window.location.search);
        const selectedLane = urlParams.get('lane');
        const laneChosen = selectedLane === 'A' || selectedLane === 'B';

        const landingView = document.getElementById('landing-view');

        if (!laneChosen) {
            if (landingView) landingView.style.display = 'flex';
            return;
        }

        if (landingView) landingView.style.display = 'none';

        this.updateLaneDisplay();
        this.updateClock();
        setInterval(() => this.updateClock(), 1000);
        CameraManager.init();
        GPSRenderer.init();

        VehicleState.fetch();
        setInterval(() => VehicleState.fetch(), CONFIG.POLL_INTERVALS.TELEMETRY);

        CameraManager.refreshLatestSnapshots();
        setInterval(() => CameraManager.refreshLatestSnapshots(), CONFIG.POLL_INTERVALS.SNAPSHOTS);
    }
};

window.GCSApp = GCSApp;
document.addEventListener('DOMContentLoaded', () => GCSApp.init());
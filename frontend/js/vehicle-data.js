// ============================================================
// VEHICLE DATA DISPLAYY
// ============================================================
const VehicleState = {
    data: {
        lat: null,
        lon: null,
        speed: null,
        course: null,
        heading: null,
        fix: false
    },
    pathHistory: [],

    dom: {
        speed: document.getElementById('data-speed'),
        course: document.getElementById('data-course'),
        lat: document.getElementById('data-lat'),
        lon: document.getElementById('data-lon')
    },

    formatValue(value, decimals, suffix = '') {
        const number = Number(value);
        return Number.isFinite(number)
            ? `${number.toFixed(decimals)}${suffix}`
            : '--';
    },

    render(data) {
        this.data = data || {};
        const courseOrHeading = this.data.course ?? this.data.heading;
        const hasCoordinates = Number.isFinite(Number(this.data.lat))
            && Number.isFinite(Number(this.data.lon));

        if (this.dom.speed) {
            this.dom.speed.textContent = this.formatValue(this.data.speed, 1, ' m/s');
        }
        if (this.dom.course) {
            this.dom.course.textContent = this.formatValue(courseOrHeading, 1, ' °');
        }
        if (this.dom.lat) {
            this.dom.lat.textContent = hasCoordinates ? this.formatValue(this.data.lat, 6) : '--';
        }
        if (this.dom.lon) {
            this.dom.lon.textContent = hasCoordinates ? this.formatValue(this.data.lon, 6) : '--';
        }
    },

    clearPath() {
        GPSData.clearPath();
    }
};

window.VehicleState = VehicleState;

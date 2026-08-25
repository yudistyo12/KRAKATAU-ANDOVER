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
        this.data = data;
        const courseOrHeading = data.heading ?? data.course;
        if (this.dom.speed) this.dom.speed.textContent = this.formatValue(data.speed, 1, ' m/s');
        if (this.dom.course) this.dom.course.textContent = this.formatValue(courseOrHeading, 1, ' °');
        if (this.dom.lat) this.dom.lat.textContent = this.formatValue(data.lat, 6);
        if (this.dom.lon) this.dom.lon.textContent = this.formatValue(data.lon, 6);
    },

    clearPath() {
        GPSData.clearPath();
    }
};

window.VehicleState = VehicleState;

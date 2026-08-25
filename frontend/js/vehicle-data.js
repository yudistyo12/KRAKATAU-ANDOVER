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
        lon: document.getElementById('data-lon'),
        coordinates: document.getElementById('header-coordinates')
    },

    formatValue(value, decimals, suffix = '') {
        const number = Number(value);
        return Number.isFinite(number)
            ? `${number.toFixed(decimals)}${suffix}`
            : '--';
    },

    formatCoordinate(value, isLatitude) {
        const number = Number(value);
        if (!Number.isFinite(number)) return null;

        const hemisphere = isLatitude
            ? (number < 0 ? 'S' : 'N')
            : (number < 0 ? 'W' : 'E');
        const absolute = Math.abs(number);
        const degrees = Math.floor(absolute);
        const minutes = (absolute - degrees) * 60;

        return `${hemisphere} ${degrees}° ${minutes.toFixed(4).replace('.', ',')}'`;
    },

    render(data) {
        this.data = data || {};
        const courseOrHeading = this.data.course ?? this.data.heading;
        const gpsIsValid = Boolean(this.data.fix ?? this.data.gps_valid);
        const hasCoordinates = gpsIsValid
            && Number.isFinite(Number(this.data.lat))
            && Number.isFinite(Number(this.data.lon));
        const hasSpeed = gpsIsValid && Number.isFinite(Number(this.data.speed));
        const hasCourse = gpsIsValid && Number.isFinite(Number(courseOrHeading));

        if (this.dom.speed) {
            this.dom.speed.textContent = hasSpeed
                ? this.formatValue(this.data.speed, 1, ' knots')
                : '--';
        }
        if (this.dom.course) {
            this.dom.course.textContent = hasCourse
                ? this.formatValue(courseOrHeading, 1, ' °')
                : '--';
        }
        if (this.dom.lat) {
            this.dom.lat.textContent = hasCoordinates ? this.formatValue(this.data.lat, 6) : '--';
        }
        if (this.dom.lon) {
            this.dom.lon.textContent = hasCoordinates ? this.formatValue(this.data.lon, 6) : '--';
        }
        if (this.dom.coordinates) {
            const latitude = this.formatCoordinate(this.data.lat, true);
            const longitude = this.formatCoordinate(this.data.lon, false);
            this.dom.coordinates.textContent = latitude && longitude
                ? `[${latitude} ${longitude}]`
                : '--';
        }
    }
};

window.VehicleState = VehicleState;

// ============================================================
// KRAKATAU ANDOVER GCS — SERVER CONFIGURATION
// ============================================================
const API_BASE_URL = "http://192.168.0.110:5001";

const CONFIG = {
    HEARTBEAT: `${API_BASE_URL}/ping_gcs`,
    TELEMETRY: `${API_BASE_URL}/telemetry`,
    CAMERA: {
        SURFACE: `${API_BASE_URL}/surface_feed`,
        UNDERWATER: `${API_BASE_URL}/underwater_feed`,
        STATUS_SURFACE: `${API_BASE_URL}/camera_status/surface`,
        STATUS_UNDERWATER: `${API_BASE_URL}/camera_status/underwater`
    },
    
    PHOTOS: {
        SURFACE: `${API_BASE_URL}/api/photos/surface`,
        UNDERWATER: `${API_BASE_URL}/api/photos/underwater`,
        LATEST_SURFACE: `${API_BASE_URL}/api/latest-photo/surface`,
        LATEST_UNDERWATER: `${API_BASE_URL}/api/latest-photo/underwater`
    },
    POLL_INTERVALS: {
        TELEMETRY: 1000,
        HEARTBEAT: 1000,
        SNAPSHOTS: 1000,
        CAMERA_REFRESH: 5000
    }
};
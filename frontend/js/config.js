// ============================================================
// KRAKATAU ANDOVER GCS — SERVER CONFIGURATION
// ============================================================
const API_BASE_URL = "http://192.168.1.102:5001";

const CONFIG = {
    //TELEMETRY: `${API_BASE_URL}/telemetry`,
    CAMERA: {
        SURFACE: `${API_BASE_URL}/surface_feed`,
        UNDERWATER: `${API_BASE_URL}/underwater_feed`
    },
    
    PHOTOS: {
        SURFACE: `${API_BASE_URL}/api/photos/surface`,
        UNDERWATER: `${API_BASE_URL}/api/photos/underwater`
    },
    POLL_INTERVALS: {
        TELEMETRY: 1000,
        SNAPSHOTS: 5000
    }
};
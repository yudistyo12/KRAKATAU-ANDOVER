// ============================================================
// CAMERA STREAM & LATEST SNAPSHOT HANDLER
// ============================================================
const CameraManager = {
    snapshotRefreshInProgress: false,
    streamRetryTimers: {},

    init() {
        this.setupStream('surface-camera', 'surface-error', 'surface-camera-status', CONFIG.CAMERA.SURFACE);
        this.setupStream('underwater-camera', 'underwater-error', 'underwater-camera-status', CONFIG.CAMERA.UNDERWATER);
        this.checkStatus();
        setInterval(() => this.checkStatus(), CONFIG.POLL_INTERVALS.CAMERA_REFRESH);
        setInterval(() => this.refreshStreams(), CONFIG.POLL_INTERVALS.CAMERA_REFRESH);
    },

    async checkStatus() {
        await Promise.all([
            this.checkCameraStatus('surface', CONFIG.CAMERA.STATUS_SURFACE),
            this.checkCameraStatus('underwater', CONFIG.CAMERA.STATUS_UNDERWATER)
        ]);
    },

    async checkCameraStatus(camera, statusUrl) {
        const status = document.getElementById(`${camera}-camera-status`);
        if (!status) return;

        try {
            const response = await fetch(`${statusUrl}?t=${Date.now()}`, {
                cache: 'no-store'
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            const image = document.getElementById(`${camera}-camera`);
            const online = Boolean(data.running && data.has_frame);
            status.className = `camera-status ${online ? 'online' : 'offline'}`;
            status.innerHTML = `<span class="dot"></span> ${online ? 'ONLINE' : 'OFFLINE'}`;

            if (!online && image) {
                this.scheduleStreamReconnect(
                    `${camera}-camera`,
                    image,
                    camera === 'surface' ? CONFIG.CAMERA.SURFACE : CONFIG.CAMERA.UNDERWATER
                );
            }
        } catch (error) {
            const image = document.getElementById(`${camera}-camera`);
            status.className = 'camera-status offline';
            status.innerHTML = '<span class="dot"></span> OFFLINE';
            if (image) {
                this.scheduleStreamReconnect(
                    `${camera}-camera`,
                    image,
                    camera === 'surface' ? CONFIG.CAMERA.SURFACE : CONFIG.CAMERA.UNDERWATER
                );
            }
        }
    },

    setupStream(imgId, errorId, statusId, streamUrl) {
        const img = document.getElementById(imgId);
        const err = document.getElementById(errorId);
        const status = document.getElementById(statusId);

        if (!img) return;

        img.removeAttribute('crossorigin');
        img.src = `${streamUrl}?t=${Date.now()}`;
        img.style.display = 'block';

        img.onerror = () => {
            img.style.display = 'block';
            if (err) err.style.display = 'flex';
            if (status) {
                status.textContent = 'OFFLINE';
                status.className = 'camera-status offline';
            }
            this.scheduleStreamReconnect(imgId, img, streamUrl);
        };

        img.onload = () => {
            clearTimeout(this.streamRetryTimers[imgId]);
            delete this.streamRetryTimers[imgId];
            if (err) err.style.display = 'none';
            if (status) {
                status.textContent = 'ONLINE';
                status.className = 'camera-status online';
            }
        };
    },

    scheduleStreamReconnect(imgId, img, streamUrl) {
        if (this.streamRetryTimers[imgId]) return;

        this.streamRetryTimers[imgId] = setTimeout(() => {
            delete this.streamRetryTimers[imgId];
            img.src = `${streamUrl}${streamUrl.includes('?') ? '&' : '?'}t=${Date.now()}`;
            img.style.display = 'block';
        }, 3000);
    },

    refreshStreams() {
        [
            ['surface-camera', CONFIG.CAMERA.SURFACE],
            ['underwater-camera', CONFIG.CAMERA.UNDERWATER]
        ].forEach(([imgId, streamUrl]) => {
            const image = document.getElementById(imgId);
            if (!image) return;

            image.src = `${streamUrl}${streamUrl.includes('?') ? '&' : '?'}t=${Date.now()}`;
            image.style.display = 'block';
        });
    },

    getPhotoPath(photo) {
        if (typeof photo === 'string') return photo;
        if (!photo || typeof photo !== 'object') return null;
        return photo.path || photo.url || photo.filename || photo.file || null;
    },

    getPhotoTime(photo) {
        if (!photo || typeof photo !== 'object') return 0;
        const value = photo.mtime || photo.modified || photo.created_at || photo.timestamp || photo.date;
        const time = value ? Date.parse(value) : 0;
        return Number.isNaN(time) ? 0 : time;
    },

    getLatestPhoto(data) {
        const explicitLatest = data.latest || data.latest_photo || data.latestPhoto;
        const explicitPath = this.getPhotoPath(explicitLatest || data.photo);
        if (explicitPath) return explicitPath;

        const photos = Array.isArray(data.photos)
            ? data.photos
            : (Array.isArray(data.files) ? data.files : data.images);
        if (!Array.isArray(photos)) return null;
        if (!photos.length) return null;

        const hasTimestamps = photos.some(photo => this.getPhotoTime(photo) > 0);
        if (hasTimestamps) {
            return this.getPhotoPath([...photos].sort((left, right) => {
                return this.getPhotoTime(right) - this.getPhotoTime(left);
            })[0]);
        }

        // The Mini PC photo API returns newest files first when no metadata is provided.
        return this.getPhotoPath(photos[0]);
    },

    async refreshLatestSnapshot(camera) {
        const container = document.getElementById(`${camera}-snapshot-container`);
        if (!container) return;
        const latestUrl = camera === 'surface'
            ? CONFIG.PHOTOS.LATEST_SURFACE
            : CONFIG.PHOTOS.LATEST_UNDERWATER;
        container.classList.add('is-loading');
        container.classList.remove('is-error');
        const imageUrl = `${latestUrl}?t=${Date.now()}`;
        let image = container.querySelector('img');

        if (!image) {
            image = document.createElement('img');
            image.alt = `${camera} snapshot terakhir`;
            image.loading = 'lazy';
            container.replaceChildren(image);
        }

        image.onload = () => {
            container.classList.remove('is-loading', 'is-error');
        };
        image.onerror = () => {
            this.setSnapshotMessage(container, `Belum ada foto ${camera}.`, false);
        };
        image.src = imageUrl;
    },

    setSnapshotMessage(container, message, isError) {
        container.replaceChildren();
        const state = document.createElement('span');
        state.className = 'snapshot-state';
        state.textContent = message;
        container.appendChild(state);
        container.classList.toggle('is-loading', !isError);
        container.classList.toggle('is-error', isError);
    },

    refreshLatestSnapshots() {
        if (this.snapshotRefreshInProgress) return;
        this.snapshotRefreshInProgress = true;

        Promise.all([
            this.refreshLatestSnapshot('surface'),
            this.refreshLatestSnapshot('underwater')
        ]).finally(() => {
            this.snapshotRefreshInProgress = false;
        });
    }
};
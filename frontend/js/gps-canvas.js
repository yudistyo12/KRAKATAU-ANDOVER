// ============================================================
// GPS CANVAS & ARENA RENDERER
// ============================================================
const GPSRenderer = {
    canvas: document.getElementById('gps-canvas'),
    ctx: null,
    minLat: -5.397340,
    maxLat: -5.396940,
    minLon: 105.266589,
    maxLon: 105.266989,
    plotLeft: 38,
    plotRight: 38,
    plotTop: 28,
    plotBottom: 42,

    init() {
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.resize();
        window.addEventListener('resize', () => this.resize());
    },

    resize() {
        if (!this.canvas || !this.ctx) return;
        const rect = this.canvas.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
            const dpr = window.devicePixelRatio || 1;
            this.canvas.width = Math.round(rect.width * dpr);
            this.canvas.height = Math.round(rect.height * dpr);
            this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
        this.draw();
    },

    mapLonToX(lon, W) {
        return this.plotLeft + ((lon - this.minLon) / (this.maxLon - this.minLon)) * (W - this.plotLeft - this.plotRight);
    },

    mapLatToY(lat, H) {
        return this.plotTop + ((this.maxLat - lat) / (this.maxLat - this.minLat)) * (H - this.plotTop - this.plotBottom);
    },

    fitToVehiclePath() {
        const pathHistory = window.VehicleState ? window.VehicleState.pathHistory : [];
        const telemetry = window.VehicleState ? window.VehicleState.data : null;
        const points = pathHistory.filter(point => Number.isFinite(point.lat) && Number.isFinite(point.lon));

        if (telemetry && telemetry.fix && Number.isFinite(Number(telemetry.lat)) && Number.isFinite(Number(telemetry.lon))) {
            points.push({ lat: Number(telemetry.lat), lon: Number(telemetry.lon) });
        }

        if (!points.length) return;

        const latitudes = points.map(point => point.lat);
        const longitudes = points.map(point => point.lon);
        const latRange = Math.max(Math.max(...latitudes) - Math.min(...latitudes), 0.00001);
        const lonRange = Math.max(Math.max(...longitudes) - Math.min(...longitudes), 0.00001);
        const latPadding = latRange * 0.2;
        const lonPadding = lonRange * 0.2;

        this.minLat = Math.min(...latitudes) - latPadding;
        this.maxLat = Math.max(...latitudes) + latPadding;
        this.minLon = Math.min(...longitudes) - lonPadding;
        this.maxLon = Math.max(...longitudes) + lonPadding;
    },

    draw() {
        if (!this.canvas || !this.ctx) return;
        const ctx = this.ctx;
        const rect = this.canvas.getBoundingClientRect();
        const W = rect.width || 400;
        const H = rect.height || 300;
        const lane = window.GCSApp ? window.GCSApp.getCurrentLane() : 'A';

        ctx.clearRect(0, 0, W, H);
        ctx.fillStyle = 'rgba(246, 245, 250, 0.9)';
        ctx.fillRect(0, 0, W, H);

        const COL_W = Math.min(100, (W - 80) / 4);
        const ROW_H = Math.min(68, (H - 80) / 4);
        const MARGIN_L = (W - COL_W * 4) / 2;
        const MARGIN_T = (H - ROW_H * 4) / 2;

        this.plotLeft = MARGIN_L - 20;
        this.plotRight = MARGIN_L - 20;
        this.plotTop = MARGIN_T;
        this.plotBottom = H - (MARGIN_T + ROW_H * 4);
        this.fitToVehiclePath();

        const cx = col => MARGIN_L + col * COL_W;
        const ry = row => MARGIN_T + (5 - row) * ROW_H;

        // Grid Lines & Labels
        ctx.save();
        ctx.strokeStyle = 'rgba(0, 0, 0, 0.07)';
        ctx.lineWidth = 0.5;
        const colLabels = ['A', 'B', 'C', 'D', 'E'];
        const rowLabels = ['5', '4', '3', '2', '1'];

        for (let i = 0; i < 5; i++) {
            ctx.beginPath();
            ctx.moveTo(cx(i), ry(5) - 8);
            ctx.lineTo(cx(i), ry(1) + 30);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(cx(0) - 15, ry(5 - i));
            ctx.lineTo(cx(4) + 15, ry(5 - i));
            ctx.stroke();
        }

        ctx.fillStyle = '#130f0f';
        ctx.font = '11px Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        colLabels.forEach((label, i) => ctx.fillText(label, cx(i), ry(5) - 12));

        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        rowLabels.forEach((label, i) => ctx.fillText(label, cx(0) - 22, ry(5 - i)));
        ctx.restore();

        // Marker Helpers
        const drawBuoy = (x, y, color, radius = 5) => {
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();
        };

        const drawBlock = (x, y, w, h, color) => {
            ctx.fillStyle = color;
            ctx.fillRect(x - w / 2, y - h / 2, w, h);
        };

        const drawLabel = (x, y, text, bgColor) => {
            ctx.fillStyle = bgColor;
            ctx.beginPath();
            if (ctx.roundRect) ctx.roundRect(x - 36, y - 11, 72, 22, 4);
            else ctx.rect(x - 36, y - 11, 72, 22);
            ctx.fill();
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 10px Arial, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(text, x, y);
        };

        const drawStartFinish = (x, y) => {
            ctx.beginPath();
            ctx.ellipse(x, y, 34, 17, 0, 0, Math.PI * 2);
            ctx.fillStyle = '#0284c7';
            ctx.fill();
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 9px Arial, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('Start /', x, y - 5);
            ctx.fillText('Finish', x, y + 6);
        };

        const drawNavDots = (x, y) => {
            for (let i = 0; i < 3; i++) drawBuoy(x, y - i * 8, '#555', 2.5);
        };

        const RED = '#ef4444', GREEN = '#22c55e', DARK_BLUE = '#1a56db';
        const greenTopY = ry(5) + 5, redTopY = ry(5) + 20;

        [cx(1) + 20, cx(2) - 18, cx(2) + 18, cx(3) - 20].forEach(x => {
            drawBuoy(x, greenTopY, GREEN, 4.5);
            drawBuoy(x, redTopY, RED, 4.5);
        });

        const yLeftMid = (ry(4) + ry(3)) / 2;
        [
            { rX: cx(0) + 12, gX: cx(0) - 12, y: ry(4) - 5 },
            { rX: cx(0) + 4,  gX: cx(0) - 30, y: yLeftMid },
            { rX: cx(0) + 12, gX: cx(0) - 12, y: ry(3) + 5 }
        ].forEach(p => {
            drawBuoy(p.rX, p.y, RED, 4.5);
            drawBuoy(p.gX, p.y, GREEN, 4.5);
        });

        [
            { rX: cx(4) - 12, gX: cx(4) + 12, y: ry(4) - 5 },
            { rX: cx(4) - 25, gX: cx(4) + 4,  y: yLeftMid },
            { rX: cx(4) - 12, gX: cx(4) + 12, y: ry(3) + 5 }
        ].forEach(p => {
            drawBuoy(p.rX, p.y, RED, 4.5);
            drawBuoy(p.gX, p.y, GREEN, 4.5);
        });

        // Route Curves
        ctx.save();
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(71, 85, 105, 0.45)';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 3]);

        if (lane === 'A') {
            drawBlock(cx(0) + 5, ry(2), 28, 16, DARK_BLUE);
            drawBlock(cx(1) + 5, ry(1) + 5, 26, 14, GREEN);
            drawLabel(cx(2) + 10, ry(1) + 5, 'Lintasan A', RED);
            drawStartFinish(cx(4), ry(1) + 10);
            drawNavDots(cx(4), ry(1) - 8);

            ctx.moveTo(cx(4), ry(1) + 10);
            ctx.lineTo(cx(4), ry(1) - 15);
            ctx.bezierCurveTo(cx(4) - 5, ry(3) + 10, cx(4) - 5, ry(4) - 10, cx(4) - 10, ry(4) - 25);
            ctx.bezierCurveTo(cx(3) + 20, greenTopY + 7, cx(3) - 20, greenTopY + 7, cx(2), greenTopY + 7);
            ctx.bezierCurveTo(cx(1) + 20, greenTopY + 7, cx(1) - 10, ry(5) + 10, cx(0) - 2, ry(4) - 20);
            ctx.bezierCurveTo(cx(0) - 2, ry(3), cx(0) - 18, ry(2) - 10, cx(0) - 15, ry(2) + 5);
            ctx.bezierCurveTo(cx(0) - 10, ry(1) - 10, cx(1) - 10, ry(1) - 10, cx(1) + 30, ry(1) - 10);
            ctx.lineTo(cx(3) + 20, ry(1) - 10);
            ctx.bezierCurveTo(cx(4) - 20, ry(1) - 10, cx(4), ry(1) - 5, cx(4), ry(1) + 10);
        } else {
            drawStartFinish(cx(0), ry(1) + 10);
            drawNavDots(cx(0), ry(1) - 8);
            drawBlock(cx(4) - 5, ry(2), 28, 16, DARK_BLUE);
            drawBlock(cx(3) - 5, ry(1) + 5, 26, 14, GREEN);
            drawLabel(cx(2) - 10, ry(1) + 5, 'Lintasan B', '#16a34a');

            ctx.moveTo(cx(0), ry(1) + 10);
            ctx.lineTo(cx(0), ry(1) - 15);
            ctx.bezierCurveTo(cx(0) - 2, ry(3), cx(0) - 2, ry(4) - 20, cx(0) + 10, ry(4) - 25);
            ctx.bezierCurveTo(cx(1) + 20, greenTopY + 7, cx(2), greenTopY + 7, cx(3) - 20, greenTopY + 7);
            ctx.bezierCurveTo(cx(3) + 20, greenTopY + 7, cx(4) + 10, ry(5) + 10, cx(4) - 2, ry(4) - 20);
            ctx.bezierCurveTo(cx(4) - 2, ry(3), cx(4) + 18, ry(2) - 10, cx(4) + 15, ry(2) + 5);
            ctx.bezierCurveTo(cx(4) + 10, ry(1) - 10, cx(3) + 10, ry(1) - 10, cx(3) - 30, ry(1) - 10);
            ctx.lineTo(cx(1) - 20, ry(1) - 10);
            ctx.bezierCurveTo(cx(0) + 20, ry(1) - 10, cx(0), ry(1) - 5, cx(0), ry(1) + 10);
        }
        ctx.stroke();
        ctx.restore();

        // Actual Trajectory
        const pathHistory = window.VehicleState ? window.VehicleState.pathHistory : [];
        if (pathHistory && pathHistory.length > 0) {
            ctx.beginPath();
            ctx.strokeStyle = 'rgba(30, 64, 175, 0.6)';
            ctx.lineWidth = 2;
            ctx.setLineDash([6, 4]);

            pathHistory.forEach((pt, idx) => {
                const x = this.mapLonToX(pt.lon, W);
                const y = this.mapLatToY(pt.lat, H);
                if (idx === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            if (pathHistory.length > 1) ctx.stroke();
            ctx.setLineDash([]);

            pathHistory.forEach(pt => {
                const x = this.mapLonToX(pt.lon, W);
                const y = this.mapLatToY(pt.lat, H);
                ctx.beginPath();
                ctx.arc(x, y, 3, 0, Math.PI * 2);
                ctx.fillStyle = '#1e40af';
                ctx.fill();
            });
        }

        // Ship Icon & Heading
        const tel = window.VehicleState ? window.VehicleState.data : null;
        let shipX, shipY;

        if (tel && tel.fix && Number.isFinite(Number(tel.lat)) && Number.isFinite(Number(tel.lon))) {
            shipX = this.mapLonToX(Number(tel.lon || 0), W);
            shipY = this.mapLatToY(Number(tel.lat || 0), H);
        } else {
            shipX = lane === 'A' ? cx(4) : cx(0);
            shipY = ry(1) + 10;
        }

        ctx.font = '24px Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('🚢', shipX, shipY);

        const heading = tel ? (tel.heading ?? tel.course) : null;
        if (tel && Number.isFinite(Number(heading)) && tel.fix && Number.isFinite(Number(tel.lat)) && Number.isFinite(Number(tel.lon))) {
            const courseRad = (Number(heading) - 90) * (Math.PI / 180);
            const len = 25;
            ctx.beginPath();
            ctx.moveTo(shipX, shipY);
            ctx.lineTo(shipX + Math.cos(courseRad) * len, shipY + Math.sin(courseRad) * len);
            ctx.strokeStyle = '#79c0ff';
            ctx.lineWidth = 3;
            ctx.stroke();
        }

        ctx.fillStyle = '#6B5C52';
        ctx.font = 'bold 12px Tahoma, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(`LINTASAN ${lane}`, W / 2, 8);
    }
};

window.GPSRenderer = GPSRenderer;
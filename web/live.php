<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Feed</title>
    <link rel="stylesheet" href="style.css">
</head>

<body>

<div class="sidebar">
    <h2>Helmet AI</h2>

    <a href="index.php">Dashboard</a>
    <a class="active" href="live.php">Live Feed</a>
    <a href="history.php">ประวัติ</a>
</div>

<div class="main">

    <div class="topbar">
        <div>
            <h1>Live Feed</h1>
            <p>ติดตามภาพจากกล้องและผลการตรวจจับแบบเรียลไทม์</p>
        </div>

        <button type="button" class="btn-refresh" onclick="reconnectCamera()">
            รีเฟรชการเชื่อมต่อ
        </button>
    </div>

    <div class="live-layout">

        <div class="live-box">

            <div class="live-header">
                <span class="live-indicator" id="live-indicator">● OFFLINE</span>
                <span id="live-time">--:--:--</span>
            </div>

            <div id="camera-error" class="camera-error">
                <div class="camera-error-icon">📷</div>
                <h3>ยังไม่สามารถเชื่อมต่อกล้องได้</h3>
                <p>กรุณาเปิดโปรแกรม Flask ตรวจจับหมวกกันน็อคก่อน</p>
                <button type="button" class="btn-reconnect" onclick="reconnectCamera()">
                    ลองเชื่อมต่อใหม่
                </button>
            </div>

            <img
                id="live-feed"
                src="http://127.0.0.1:5000/video_feed"
                alt="Live Camera Feed"
                onload="cameraConnected()"
                onerror="cameraDisconnected()"
            >

        </div>

        <div class="status-box">

            <div class="info-card system-card">
                <h3>สถานะระบบ</h3>

                <span id="system-status" class="offline">
                    ● OFFLINE
                </span>

                <div class="system-detail">
                    <span>กล้อง</span>
                    <b id="camera-status">ไม่เชื่อมต่อ</b>
                </div>

                <div class="system-detail">
                    <span>ชื่อกล้อง</span>
                    <b id="camera-name">Web Camera</b>
                </div>

                <div class="system-detail">
                    <span>อัปเดตล่าสุด</span>
                    <b id="last-update">-</b>
                </div>
            </div>

            <div class="info-card latest-card">
                <div class="card-title-row">
                    <h3>ตรวจพบล่าสุด</h3>
                    <span class="count-pill" id="latest-count">0 รายการ</span>
                </div>

                <div id="latest-detections" class="latest-list">
                    <p class="empty-text">กำลังโหลดข้อมูล...</p>
                </div>
            </div>

            <div class="info-card live-summary-card">
                <h3>สรุปการตรวจพบล่าสุด</h3>

                <div class="live-summary-row">
                    <span>สวมหมวก</span>
                    <b class="text-green" id="live-helmet-count">0</b>
                </div>

                <div class="live-summary-row">
                    <span>ไม่สวมหมวก</span>
                    <b class="text-red" id="live-no-helmet-count">0</b>
                </div>
            </div>

        </div>

    </div>

</div>

<script>
const API_URL = "http://127.0.0.1:5000";
const liveFeed = document.getElementById("live-feed");
const cameraError = document.getElementById("camera-error");

function escapeHTML(text) {
    if (text === null || text === undefined || text === "") {
        return "-";
    }

    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateText) {
    if (!dateText) return "-";

    const date = new Date(dateText);

    if (isNaN(date.getTime())) {
        return dateText;
    }

    return new Intl.DateTimeFormat("th-TH", {
        dateStyle: "short",
        timeStyle: "medium"
    }).format(date);
}

function updateClock() {
    const now = new Date();

    document.getElementById("live-time").textContent =
        now.toLocaleTimeString("th-TH");
}

function setSystemOnline(isOnline, cameraName = "Web Camera") {
    const statusElement = document.getElementById("system-status");
    const indicator = document.getElementById("live-indicator");
    const cameraStatus = document.getElementById("camera-status");

    document.getElementById("camera-name").textContent = cameraName;
    document.getElementById("last-update").textContent =
        new Date().toLocaleTimeString("th-TH");

    if (isOnline) {
        statusElement.textContent = "● ONLINE";
        statusElement.className = "online";

        indicator.textContent = "● LIVE";
        indicator.className = "live-indicator online-live";

        cameraStatus.textContent = "เชื่อมต่อแล้ว";
        cameraStatus.className = "text-green";
    } else {
        statusElement.textContent = "● OFFLINE";
        statusElement.className = "offline";

        indicator.textContent = "● OFFLINE";
        indicator.className = "live-indicator offline-live";

        cameraStatus.textContent = "ไม่เชื่อมต่อ";
        cameraStatus.className = "text-red";
    }
}

function cameraConnected() {
    liveFeed.style.display = "block";
    cameraError.style.display = "none";
}

function cameraDisconnected() {
    liveFeed.style.display = "none";
    cameraError.style.display = "flex";
    setSystemOnline(false);
}

function reconnectCamera() {
    liveFeed.style.display = "none";
    cameraError.style.display = "flex";

    liveFeed.src = `${API_URL}/video_feed?t=${Date.now()}`;

    refreshLiveData();
}

async function updateSystemStatus() {
    try {
        const response = await fetch(
            `${API_URL}/api/status?t=${Date.now()}`,
            { cache: "no-store" }
        );

        if (!response.ok) {
            throw new Error("Status API error");
        }

        const data = await response.json();

        setSystemOnline(
            Boolean(data.online),
            data.camera_name || "Web Camera"
        );

    } catch (error) {
        setSystemOnline(false);
    }
}

async function updateLatestDetections() {
    const container = document.getElementById("latest-detections");
    const countElement = document.getElementById("latest-count");
    const helmetCountElement = document.getElementById("live-helmet-count");
    const noHelmetCountElement = document.getElementById("live-no-helmet-count");

    try {
        const response = await fetch(
            `${API_URL}/api/latest-detections?t=${Date.now()}`,
            { cache: "no-store" }
        );

        if (!response.ok) {
            throw new Error("Latest detection API error");
        }

        const data = await response.json();
        const items = data.items || [];

        countElement.textContent = `${items.length} รายการ`;

        const helmetCount = items.filter(
            item => item.helmet_status === "สวมหมวก"
        ).length;

        const noHelmetCount = items.filter(
            item => item.helmet_status === "ไม่สวมหมวก"
        ).length;

        helmetCountElement.textContent = helmetCount;
        noHelmetCountElement.textContent = noHelmetCount;

        if (items.length === 0) {
            container.innerHTML = `
                <p class="empty-text">
                    ยังไม่มีข้อมูลการตรวจจับล่าสุด
                </p>
            `;
            return;
        }

        container.innerHTML = items.map(item => {
            const isNoHelmet = item.helmet_status === "ไม่สวมหมวก";

            return `
                <div class="latest-item">
                    <div class="latest-top">
                        <span class="${isNoHelmet ? "badge-danger" : "badge-safe"}">
                            ${escapeHTML(item.helmet_status)}
                        </span>
                    </div>

                    <div class="latest-detail">
                        ทะเบียน: <b>${escapeHTML(item.plate_number)}</b>
                    </div>

                    <div class="latest-detail">
                        จังหวัด: <b>${escapeHTML(item.province)}</b>
                    </div>

                    <div class="latest-time">
                        ${formatDate(item.detected_at)}
                    </div>
                </div>
            `;
        }).join("");

    } catch (error) {
        countElement.textContent = "0 รายการ";
        helmetCountElement.textContent = "0";
        noHelmetCountElement.textContent = "0";

        container.innerHTML = `
            <p class="empty-text">
                ไม่สามารถโหลดข้อมูลล่าสุดได้
            </p>
        `;
    }
}

function refreshLiveData() {
    updateSystemStatus();
    updateLatestDetections();
    updateClock();
}

refreshLiveData();

setInterval(refreshLiveData, 2000);
setInterval(updateClock, 1000);
</script>

</body>
</html>
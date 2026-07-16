<?php
include "db.php";

date_default_timezone_set("Asia/Bangkok");
mysqli_set_charset($conn, "utf8mb4");


/* =========================
   ฟังก์ชันช่วยดึงจำนวนข้อมูล
========================= */
function getCount($conn, $sql) {
    $result = mysqli_query($conn, $sql);

    if (!$result) {
        return 0;
    }

    $row = mysqli_fetch_assoc($result);

    return $row ? (int)$row["total"] : 0;
}

function e($text) {
    return htmlspecialchars((string)$text, ENT_QUOTES, "UTF-8");
}


/* =========================
   สรุปเฉพาะข้อมูลวันนี้
========================= */
$todayTotalSql = "
    SELECT COUNT(*) AS total
    FROM detections
    WHERE DATE(detected_at) = CURDATE()
";
$todayTotal = getCount($conn, $todayTotalSql);

$todayHelmetSql = "
    SELECT COUNT(*) AS total
    FROM detections
    WHERE DATE(detected_at) = CURDATE()
    AND helmet_status = 'สวมหมวก'
";
$todayHelmet = getCount($conn, $todayHelmetSql);

$todayNoHelmetSql = "
    SELECT COUNT(*) AS total
    FROM detections
    WHERE DATE(detected_at) = CURDATE()
    AND helmet_status = 'ไม่สวมหมวก'
";
$todayNoHelmet = getCount($conn, $todayNoHelmetSql);


/* =========================
   ช่วงเวลาที่พบมากที่สุดวันนี้
========================= */
$peakHourSql = "
    SELECT
        HOUR(detected_at) AS peak_hour,
        COUNT(*) AS total
    FROM detections
    WHERE DATE(detected_at) = CURDATE()
    GROUP BY HOUR(detected_at)
    ORDER BY total DESC, peak_hour ASC
    LIMIT 1
";

$peakHourResult = mysqli_query($conn, $peakHourSql);
$peakHourRow = $peakHourResult ? mysqli_fetch_assoc($peakHourResult) : null;

if ($peakHourRow) {
    $peakHour = sprintf(
        "%02d:00 - %02d:59",
        $peakHourRow["peak_hour"],
        $peakHourRow["peak_hour"]
    );
    $peakTotal = (int)$peakHourRow["total"];
} else {
    $peakHour = "-";
    $peakTotal = 0;
}


/* =========================
   ข้อมูลสำหรับกราฟ 7 วันย้อนหลัง
========================= */
$dailySql = "
    SELECT
        DATE(detected_at) AS day,
        COUNT(*) AS total
    FROM detections
    WHERE DATE(detected_at) >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
    GROUP BY DATE(detected_at)
    ORDER BY day ASC
";

$dailyResult = mysqli_query($conn, $dailySql);

$dailyMap = [];

if ($dailyResult) {
    while ($row = mysqli_fetch_assoc($dailyResult)) {
        $dailyMap[$row["day"]] = (int)$row["total"];
    }
}

$dailyLabels = [];
$dailyValues = [];

for ($i = 6; $i >= 0; $i--) {
    $date = date("Y-m-d", strtotime("-$i days"));

    $dailyLabels[] = date("d/m", strtotime($date));
    $dailyValues[] = isset($dailyMap[$date]) ? $dailyMap[$date] : 0;
}


/* =========================
   รายการล่าสุดเฉพาะวันนี้
========================= */
$latestTodaySql = "
    SELECT *
    FROM detections
    WHERE DATE(detected_at) = CURDATE()
    ORDER BY detected_at DESC
    LIMIT 10
";

$latestTodayResult = mysqli_query($conn, $latestTodaySql);
?>

<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Helmet Detection Dashboard</title>

    <link rel="stylesheet" href="style.css?v=2">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>

<body>

<div class="sidebar">
    <h2>Helmet AI</h2>

    <a class="active" href="index.php">Dashboard</a>
    <a href="live.php">Live Feed</a>
    <a href="history.php">ประวัติ</a>
</div>

<div class="main">

    <div class="topbar">
        <div>
            <h1>Dashboard</h1>
            <p>สรุปภาพรวมระบบตรวจจับหมวกกันน็อคและป้ายทะเบียน</p>
        </div>

        <div class="topbar-buttons">
            <a class="btn-history" href="history.php">ดูประวัติทั้งหมด</a>
            <a class="btn-live" href="live.php">เปิด Live Feed</a>
        </div>
    </div>

    <!-- การ์ดสรุปของวันนี้ 4 ช่อง -->
    <div class="summary-title">
        <h3>สรุปข้อมูลวันนี้</h3>
        <span><?php echo date("d/m/Y"); ?></span>
    </div>

    <div class="cards">

    <div class="card">
        <p>ตรวจพบรถมอเตอร์ไซค์วันนี้</p>

        <div class="card-number">
            <h2><?php echo $todayTotal; ?></h2>
            <span>คัน</span>
        </div>
    </div>

    <div class="card green">
        <p>พบผู้สวมหมวก</p>

        <div class="card-number">
            <h2><?php echo $todayHelmet; ?></h2>
            <span>คน</span>
        </div>
    </div>

    <div class="card red">
        <p>พบผู้ไม่สวมหมวก</p>

        <div class="card-number">
            <h2><?php echo $todayNoHelmet; ?></h2>
            <span>คน</span>
        </div>
    </div>

    <div class="card blue">
        <p>ช่วงเวลาที่พบมากที่สุด</p>

        <h2 class="peak-hour">
            <?php echo $peakHour; ?>
        </h2>

        <small>
            <?php echo $peakTotal; ?> รายการ
        </small>
    </div>

</div>

    <!-- กราฟ -->
    <div class="chart-grid">

        <div class="chart-box">
            <div class="chart-header">
                <h3>จำนวนการตรวจจับย้อนหลัง 7 วัน</h3>
            </div>

            <canvas id="dailyChart"></canvas>
        </div>

        <div class="chart-box">
            <div class="chart-header">
                <h3>สถานะการสวมหมวกวันนี้</h3>
            </div>

            <canvas id="helmetChart"></canvas>
        </div>

    </div>

    <!-- ตารางรายการวันนี้ -->
    <div class="table-box">

        <div class="table-header">
            <div>
                <h3>รายการตรวจจับล่าสุดของวันนี้</h3>
                <p>
                    แสดงเฉพาะ 10 รายการล่าสุดของวันที่
                    <?php echo date("d/m/Y"); ?>
                </p>
            </div>

            <a href="history.php" class="btn-view-all">ดูทั้งหมด</a>
        </div>

        <div class="table-responsive">
            <table>
                <thead>
                    <tr>
                        <th>เวลา</th>
                        <th>ภาพหลักฐาน</th>
                        <th>สถานะ</th>
                        <th>ทะเบียน</th>
                        <th>ความมั่นใจ</th>
                    </tr>
                </thead>

                <tbody>
                    <?php if ($latestTodayResult && mysqli_num_rows($latestTodayResult) > 0) { ?>

                        <?php while ($row = mysqli_fetch_assoc($latestTodayResult)) { ?>

                            <?php
                            $confidence = "-";

                            if ($row["confidence"] !== null && $row["confidence"] !== "") {
                                $confidenceValue = (float)$row["confidence"];

                                if ($confidenceValue <= 1) {
                                    $confidenceValue = $confidenceValue * 100;
                                }

                                $confidence = round($confidenceValue) . "%";
                            }

                            $statusClass = $row["helmet_status"] === "ไม่สวมหมวก"
                                ? "badge-red"
                                : "badge-green";
                            ?>

                            <tr>
                                <td>
                                    <?php echo date("H:i:s", strtotime($row["detected_at"])); ?>
                                </td>

                                <td>
                                    <?php if (!empty($row["image_path"])) { ?>
                                        <img
                                            src="<?php echo e($row["image_path"]); ?>"
                                            class="evidence-img"
                                            alt="ภาพหลักฐาน"
                                        >
                                    <?php } else { ?>
                                        -
                                    <?php } ?>
                                </td>

                                <td>
                                    <span class="<?php echo $statusClass; ?>">
                                        <?php echo e($row["helmet_status"]); ?>
                                    </span>
                                </td>

                                <td>
                                    <?php
                                    echo !empty($row["plate_number"])
                                        ? e($row["plate_number"])
                                        : "-";
                                    ?>
                                </td>

                                <td><?php echo $confidence; ?></td>
                            </tr>

                        <?php } ?>

                    <?php } else { ?>

                        <tr>
                            <td colspan="5" class="no-data">
                                ยังไม่มีข้อมูลการตรวจจับของวันนี้
                            </td>
                        </tr>

                    <?php } ?>
                </tbody>
            </table>
        </div>

    </div>

</div>

<script>
const dailyLabels = <?php echo json_encode($dailyLabels, JSON_UNESCAPED_UNICODE); ?>;
const dailyValues = <?php echo json_encode($dailyValues, JSON_UNESCAPED_UNICODE); ?>;

const todayHelmet = <?php echo $todayHelmet; ?>;
const todayNoHelmet = <?php echo $todayNoHelmet; ?>;


/* กราฟจำนวนการตรวจจับย้อนหลัง 7 วัน */
new Chart(document.getElementById("dailyChart"), {
    type: "bar",
    data: {
        labels: dailyLabels,
        datasets: [{
            label: "จำนวนการตรวจจับ",
            data: dailyValues,
            backgroundColor: "#1976f3",
            borderRadius: 8
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                ticks: {
                    stepSize: 5
                }
            }
        }
    }
});


/* กราฟเปรียบเทียบสวมหมวก / ไม่สวมหมวก */
new Chart(document.getElementById("helmetChart"), {
    type: "doughnut",
    data: {
        labels: ["สวมหมวก", "ไม่สวมหมวก"],
        datasets: [{
            data: [todayHelmet, todayNoHelmet],
            backgroundColor: ["#22c55e", "#ef4444"],
            borderWidth: 0
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "68%",
        plugins: {
            legend: {
                position: "bottom"
            }
        }
    }
});
</script>

</body>
</html>

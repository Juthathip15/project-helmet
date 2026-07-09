<?php
include "db.php";

date_default_timezone_set("Asia/Bangkok");
mysqli_set_charset($conn, "utf8mb4");

/* =========================
   รับค่าจากฟอร์มค้นหา
========================= */
$keyword = isset($_GET["keyword"]) ? trim($_GET["keyword"]) : "";
$status = isset($_GET["status"]) ? trim($_GET["status"]) : "";
$dateFrom = isset($_GET["date_from"]) ? trim($_GET["date_from"]) : "";
$dateTo = isset($_GET["date_to"]) ? trim($_GET["date_to"]) : "";

/* =========================
   ตั้งค่าการแบ่งหน้า
========================= */
$perPage = 10;

$page = isset($_GET["page"]) ? (int)$_GET["page"] : 1;

if ($page < 1) {
    $page = 1;
}

$offset = ($page - 1) * $perPage;

/* =========================
   สร้างเงื่อนไข SQL
========================= */
$where = [];

if ($keyword !== "") {
    $safeKeyword = mysqli_real_escape_string($conn, $keyword);

    $where[] = "(
        plate_number LIKE '%$safeKeyword%'
        OR province LIKE '%$safeKeyword%'
    )";
}

if ($status === "สวมหมวก" || $status === "ไม่สวมหมวก") {
    $safeStatus = mysqli_real_escape_string($conn, $status);
    $where[] = "helmet_status = '$safeStatus'";
}

if ($dateFrom !== "") {
    $safeDateFrom = mysqli_real_escape_string($conn, $dateFrom);
    $where[] = "DATE(detected_at) >= '$safeDateFrom'";
}

if ($dateTo !== "") {
    $safeDateTo = mysqli_real_escape_string($conn, $dateTo);
    $where[] = "DATE(detected_at) <= '$safeDateTo'";
}

$whereSql = "";

if (!empty($where)) {
    $whereSql = "WHERE " . implode(" AND ", $where);
}

/* =========================
   นับจำนวนข้อมูลทั้งหมด
========================= */
$countSql = "
    SELECT COUNT(*) AS total
    FROM detections
    $whereSql
";

$countResult = mysqli_query($conn, $countSql);
$countRow = $countResult ? mysqli_fetch_assoc($countResult) : null;

$totalRows = $countRow ? (int)$countRow["total"] : 0;
$totalPages = max(1, (int)ceil($totalRows / $perPage));

if ($page > $totalPages) {
    $page = $totalPages;
    $offset = ($page - 1) * $perPage;
}

/* =========================
   ดึงข้อมูลในหน้าปัจจุบัน
========================= */
$sql = "
    SELECT *
    FROM detections
    $whereSql
    ORDER BY detected_at DESC
    LIMIT $offset, $perPage
";

$result = mysqli_query($conn, $sql);

/* ป้องกัน XSS ตอนแสดงผล */
function e($text) {
    return htmlspecialchars((string)$text, ENT_QUOTES, "UTF-8");
}

/* สร้างลิงก์ Pagination โดยคงค่า Filter เดิม */
function pageUrl($pageNumber) {
    $params = $_GET;
    $params["page"] = $pageNumber;

    return "history.php?" . http_build_query($params);
}

/* สร้างลิงก์ Export โดยส่ง Filter เดิมไปด้วย */
$exportParams = [];

if ($keyword !== "") {
    $exportParams["keyword"] = $keyword;
}

if ($status !== "") {
    $exportParams["status"] = $status;
}

if ($dateFrom !== "") {
    $exportParams["date_from"] = $dateFrom;
}

if ($dateTo !== "") {
    $exportParams["date_to"] = $dateTo;
}

$exportUrl = "export_history.php";

if (!empty($exportParams)) {
    $exportUrl .= "?" . http_build_query($exportParams);
}
?>

<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ประวัติการตรวจจับ</title>
    <link rel="stylesheet" href="style.css">
</head>

<body>

<div class="sidebar">
    <h2>Helmet AI</h2>

    <a href="index.php">Dashboard</a>
    <a href="live.php">Live Feed</a>
    <a class="active" href="history.php">ประวัติ</a>
</div>

<div class="main">

    <div class="topbar">
        <div>
            <h1>ประวัติการตรวจจับ</h1>
            <p>ค้นหา ตรวจสอบ และดูข้อมูลการตรวจจับย้อนหลังทั้งหมด</p>
        </div>

        <div class="topbar-buttons">
            <a class="btn-live" href="live.php">เปิด Live Feed</a>
        </div>
    </div>

    <!-- ส่วนค้นหาและกรองข้อมูล -->
    <div class="filter-box">

        <div class="filter-header">
            <h3>ค้นหาและกรองข้อมูล</h3>
            <span>พบทั้งหมด <?php echo number_format($totalRows); ?> รายการ</span>
        </div>

        <form method="GET" action="history.php" class="filter-form">

            <div class="filter-group keyword-group">
                <label for="keyword">ค้นหาทะเบียน / จังหวัด</label>
                <input
                    type="text"
                    id="keyword"
                    name="keyword"
                    value="<?php echo e($keyword); ?>"
                    placeholder="เช่น กข 1234 หรือ กรุงเทพมหานคร"
                >
            </div>

            <div class="filter-group">
                <label for="status">สถานะ</label>
                <select id="status" name="status">
                    <option value="">ทั้งหมด</option>
                    <option value="สวมหมวก"
                        <?php echo $status === "สวมหมวก" ? "selected" : ""; ?>>
                        สวมหมวก
                    </option>
                    <option value="ไม่สวมหมวก"
                        <?php echo $status === "ไม่สวมหมวก" ? "selected" : ""; ?>>
                        ไม่สวมหมวก
                    </option>
                </select>
            </div>

            <div class="filter-group">
                <label for="date_from">ตั้งแต่วันที่</label>
                <input
                    type="date"
                    id="date_from"
                    name="date_from"
                    value="<?php echo e($dateFrom); ?>"
                >
            </div>

            <div class="filter-group">
                <label for="date_to">ถึงวันที่</label>
                <input
                    type="date"
                    id="date_to"
                    name="date_to"
                    value="<?php echo e($dateTo); ?>"
                >
            </div>

            <div class="filter-actions">
                <button type="submit" class="btn-search">ค้นหา</button>
                <a href="history.php" class="btn-reset">ล้างตัวกรอง</a>
            </div>

        </form>

    </div>

    <!-- ตารางประวัติ -->
    <div class="table-box">

        <div class="table-header">
            <div>
                <h3>รายการตรวจจับย้อนหลัง</h3>
                <p>
                    แสดงรายการที่
                    <?php echo $totalRows > 0 ? ($offset + 1) : 0; ?>
                    -
                    <?php echo min($offset + $perPage, $totalRows); ?>
                    จากทั้งหมด <?php echo number_format($totalRows); ?> รายการ
                </p>
            </div>

            <a class="btn-view-all" href="<?php echo e($exportUrl); ?>">
                Export CSV
            </a>
        </div>

        <div class="table-responsive">
            <table>
                <thead>
                    <tr>
                        <th>ลำดับ</th>
                        <th>วันที่</th>
                        <th>เวลา</th>
                        <th>ทะเบียน</th>
                        <th>จังหวัด</th>
                        <th>ความมั่นใจ</th>
                        <th>สถานะ</th>
                        <th>ภาพหลักฐาน</th>
                    </tr>
                </thead>

                <tbody>

                <?php if ($result && mysqli_num_rows($result) > 0) { ?>

                    <?php $no = $offset + 1; ?>

                    <?php while ($row = mysqli_fetch_assoc($result)) { ?>

                        <?php
                            $confidence = "-";

                            if ($row["confidence"] !== null && $row["confidence"] !== "") {
                                $confidenceValue = (float)$row["confidence"];

                                if ($confidenceValue <= 1) {
                                    $confidenceValue = $confidenceValue * 100;
                                }

                                $confidence = number_format($confidenceValue, 0) . "%";
                            }

                            $isNoHelmet = $row["helmet_status"] === "ไม่สวมหมวก";
                        ?>

                        <tr>
                            <td><?php echo $no++; ?></td>

                            <td>
                                <?php
                                echo !empty($row["detected_at"])
                                    ? date("d/m/Y", strtotime($row["detected_at"]))
                                    : "-";
                                ?>
                            </td>

                            <td>
                                <?php
                                echo !empty($row["detected_at"])
                                    ? date("H:i:s", strtotime($row["detected_at"]))
                                    : "-";
                                ?>
                            </td>

                            <td>
                                <?php
                                echo !empty($row["plate_number"])
                                    ? e($row["plate_number"])
                                    : "-";
                                ?>
                            </td>

                            <td>
                                <?php
                                echo !empty($row["province"])
                                    ? e($row["province"])
                                    : "-";
                                ?>
                            </td>

                            <td><?php echo $confidence; ?></td>

                            <td>
                                <span class="<?php echo $isNoHelmet ? "badge-red" : "badge-green"; ?>">
                                    <?php echo e($row["helmet_status"]); ?>
                                </span>
                            </td>

                            <td>
                                <?php if (!empty($row["image_path"])) { ?>

                                    <img
                                        src="<?php echo e($row["image_path"]); ?>"
                                        class="history-img"
                                        alt="ภาพหลักฐาน"
                                        onclick="showImage('<?php echo e($row["image_path"]); ?>')"
                                    >

                                <?php } else { ?>
                                    -
                                <?php } ?>
                            </td>
                        </tr>

                    <?php } ?>

                <?php } else { ?>

                    <tr>
                        <td colspan="8" class="no-data">
                            ไม่พบข้อมูลตามเงื่อนไขที่ค้นหา
                        </td>
                    </tr>

                <?php } ?>

                </tbody>
            </table>
        </div>

        <!-- Pagination -->
        <?php if ($totalPages > 1) { ?>

            <div class="pagination">

                <?php if ($page > 1) { ?>
                    <a href="<?php echo pageUrl($page - 1); ?>">‹ ก่อนหน้า</a>
                <?php } ?>

                <?php
                $startPage = max(1, $page - 2);
                $endPage = min($totalPages, $page + 2);

                for ($i = $startPage; $i <= $endPage; $i++) {
                ?>
                    <a
                        href="<?php echo pageUrl($i); ?>"
                        class="<?php echo $i === $page ? "active-page" : ""; ?>"
                    >
                        <?php echo $i; ?>
                    </a>
                <?php } ?>

                <?php if ($page < $totalPages) { ?>
                    <a href="<?php echo pageUrl($page + 1); ?>">ถัดไป ›</a>
                <?php } ?>

            </div>

        <?php } ?>

    </div>

</div>

<!-- Modal สำหรับดูภาพหลักฐานขนาดใหญ่ -->
<div id="imageModal" class="image-modal" onclick="closeImage()">
    <span class="close-image">&times;</span>
    <img id="modalImage" src="" alt="ภาพหลักฐานขนาดใหญ่">
</div>

<script>
function showImage(imagePath) {
    document.getElementById("modalImage").src = imagePath;
    document.getElementById("imageModal").style.display = "flex";
}

function closeImage() {
    document.getElementById("imageModal").style.display = "none";
}
</script>

</body>
</html>

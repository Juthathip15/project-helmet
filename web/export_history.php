<?php
include "db.php";

date_default_timezone_set("Asia/Bangkok");
mysqli_set_charset($conn, "utf8mb4");

/* =========================
   รับค่า Filter เดียวกับ history.php
========================= */
$keyword = isset($_GET["keyword"]) ? trim($_GET["keyword"]) : "";
$status = isset($_GET["status"]) ? trim($_GET["status"]) : "";
$dateFrom = isset($_GET["date_from"]) ? trim($_GET["date_from"]) : "";
$dateTo = isset($_GET["date_to"]) ? trim($_GET["date_to"]) : "";

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
   ดึงข้อมูลทั้งหมดตาม Filter
   (ไม่จำกัด 10 รายการเหมือนหน้าตาราง)
========================= */
$sql = "
    SELECT
        id,
        detected_at,
        helmet_status,
        plate_number,
        province,
        confidence,
        image_path
    FROM detections
    $whereSql
    ORDER BY detected_at DESC
";

$result = mysqli_query($conn, $sql);

/* =========================
   สร้างไฟล์ CSV
========================= */
$filename = "helmet_detection_history_" . date("Ymd_His") . ".csv";

header("Content-Type: text/csv; charset=utf-8");
header("Content-Disposition: attachment; filename=\"$filename\"");
header("Pragma: no-cache");
header("Expires: 0");

$output = fopen("php://output", "w");

/* BOM สำหรับให้ Excel แสดงภาษาไทยถูกต้อง */
fwrite($output, "\xEF\xBB\xBF");

/* หัวตาราง */
fputcsv($output, [
    "ลำดับ",
    "วันที่",
    "เวลา",
    "สถานะ",
    "ป้ายทะเบียน",
    "จังหวัด",
    "ความมั่นใจ (%)",
    "พาธภาพหลักฐาน"
]);

$no = 1;

if ($result) {
    while ($row = mysqli_fetch_assoc($result)) {
        $date = !empty($row["detected_at"])
            ? date("d/m/Y", strtotime($row["detected_at"]))
            : "-";

        $time = !empty($row["detected_at"])
            ? date("H:i:s", strtotime($row["detected_at"]))
            : "-";

        $confidence = "";

        if ($row["confidence"] !== null && $row["confidence"] !== "") {
            $confidenceValue = (float)$row["confidence"];

            if ($confidenceValue <= 1) {
                $confidenceValue = $confidenceValue * 100;
            }

            $confidence = round($confidenceValue);
        }

        fputcsv($output, [
            $no++,
            $date,
            $time,
            $row["helmet_status"] ?? "",
            $row["plate_number"] ?? "",
            $row["province"] ?? "",
            $confidence,
            $row["image_path"] ?? ""
        ]);
    }
}

fclose($output);
exit;
?>

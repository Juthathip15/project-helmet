<?php
$host = "localhost";
$user = "root";
$password = "";
$dbname = "helmet_license_db";

$conn = new mysqli($host, $user, $password, $dbname);

if ($conn->connect_error) {
    die("เชื่อมต่อฐานข้อมูลล้มเหลว: " . $conn->connect_error);
}

$conn->set_charset("utf8mb4");
?>
import mysql.connector
from mysql.connector import Error


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="helmet_license_db"
    )


def save_detection(
    helmet_status,
    plate_number,
    province,
    image_path,
    confidence=0.0
):
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
        INSERT INTO detections
        (
            image_path,
            helmet_status,
            plate_number,
            province,
            confidence
        )
        VALUES (%s, %s, %s, %s, %s)
        """

        values = (
            image_path,
            helmet_status,
            plate_number,
            province,
            confidence
        )

        cursor.execute(sql, values)
        conn.commit()

        print("บันทึกข้อมูลลงฐานข้อมูลสำเร็จ")

    except Error as e:
        print("เกิดข้อผิดพลาดในการบันทึกฐานข้อมูล:", e)

    finally:
        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()


def get_latest_detections(limit=10):
    conn = None
    cursor = None

    try:
        # จำกัดจำนวนรายการที่ส่งไปหน้าเว็บ ไม่เกิน 10
        limit = max(1, min(int(limit), 10))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        sql = """
        SELECT
            id,
            helmet_status,
            COALESCE(plate_number, '') AS plate_number,
            COALESCE(province, '') AS province,
            COALESCE(confidence, 0) AS confidence,
            detected_at,
            image_path
        FROM detections
        ORDER BY detected_at DESC
        LIMIT %s
        """

        cursor.execute(sql, (limit,))
        results = cursor.fetchall()

        # เปลี่ยนวันที่ให้อยู่ในรูปแบบที่ JavaScript อ่านได้
        for row in results:
            if row.get("detected_at"):
                row["detected_at"] = row["detected_at"].strftime(
                    "%Y-%m-%dT%H:%M:%S"
                )

        return results

    except Error as e:
        print("เกิดข้อผิดพลาดในการดึงข้อมูลล่าสุด:", e)
        return []

    finally:
        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()
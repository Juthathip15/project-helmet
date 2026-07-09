from ultralytics import YOLO
import cv2
import easyocr
import mysql.connector
from pathlib import Path

plate_model = YOLO("runs/detect/runs/plate_model-3/weights/best.pt")
reader = easyocr.Reader(['th', 'en'])

evidence_folder = Path("web/evidence")

def update_plate(id, plate_number, province):
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="helmet_license_db"
    )

    cursor = conn.cursor()

    sql = """
    UPDATE detections
    SET plate_number=%s, province=%s
    WHERE id=%s
    """

    cursor.execute(sql, (plate_number, province, id))
    conn.commit()

    cursor.close()
    conn.close()

def read_plate_from_image(image_path):
    image = cv2.imread(str(image_path))

    if image is None:
        return "", ""

    plate_text = ""
    province_text = ""

    results = plate_model(image)

    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            class_name = plate_model.names[cls_id]

            if class_name == "license-plate":
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                crop = image[y1:y2, x1:x2]

                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                gray = cv2.resize(gray, None, fx=4, fy=4)
                gray = cv2.GaussianBlur(gray, (3, 3), 0)

                ocr_result = reader.readtext(
                    gray,
                    detail=1,
                    paragraph=False
                )

                text = ""
                for item in ocr_result:
                    text += item[1] + " "

                text = text.strip()

                if text != "":
                    plate_text = text

    return plate_text, province_text

def get_unprocessed_records():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="helmet_license_db"
    )

    cursor = conn.cursor(dictionary=True)

    sql = """
    SELECT id, image_path
    FROM detections
    WHERE helmet_status='ไม่สวมหมวก'
    AND image_path IS NOT NULL
    AND image_path != ''
    AND (plate_number IS NULL OR plate_number = '')
    ORDER BY detected_at DESC
    """

    cursor.execute(sql)
    records = cursor.fetchall()

    cursor.close()
    conn.close()

    return records

records = get_unprocessed_records()

print("พบรูปที่ยังไม่ได้อ่านป้าย:", len(records), "รายการ")

for row in records:
    id = row["id"]
    db_image_path = row["image_path"]

    image_path = Path("web") / db_image_path

    print("\nกำลังประมวลผล ID:", id)
    print("รูป:", image_path)

    plate_number, province = read_plate_from_image(image_path)

    print("ทะเบียนที่อ่านได้:", plate_number)

    if plate_number != "":
        update_plate(id, plate_number, province)
        print("อัปเดตฐานข้อมูลแล้ว")
    else:
        print("ยังอ่านป้ายไม่ได้")

print("\nประมวลผลเสร็จแล้ว")
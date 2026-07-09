from ultralytics import YOLO
import cv2
import easyocr
from database import save_detection
import os
from datetime import datetime
from pathlib import Path
import torch

print("CUDA:", torch.cuda.is_available())
print("GPU:", torch.cuda.get_device_name(0))

helmet_model = YOLO("runs/detect/runs/helmet_model-5/weights/best.pt")
plate_model = YOLO("runs/detect/runs/plate_model-5/weights/best.pt")

helmet_model.to("cuda")
plate_model.to("cuda")

reader = easyocr.Reader(['th', 'en'], gpu=True)

test_folder = Path("D:/dataset/test")

image_files = list(test_folder.rglob("*.*"))

print("พบไฟล์ทั้งหมด:", len(image_files))

for f in image_files:
    print(f)
for image_file in image_files:

    print("\n==============================")
    print("กำลังตรวจ:", image_file.name)

    image_path = str(image_file)
    image = cv2.imread(image_path)

    if image is None:
        print("อ่านรูปไม่ได้:", image_path)
        continue

    helmet_status = "ไม่ทราบ"
    plate_text = ""
    province_text = ""
    confidence = 0.0
    db_image_path = ""

    # ตรวจหมวก
    helmet_results = helmet_model(image)

    for result in helmet_results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            class_name = helmet_model.names[cls_id]

            if class_name == "With Helmet":
                helmet_status = "สวมหมวก"
            elif class_name == "Without Helmet":
                helmet_status = "ไม่สวมหมวก"

    # ถ้าตรวจหมวกไม่เจอ ไม่บันทึก
    if helmet_status == "ไม่ทราบ":
        print("ไม่พบการตรวจจับหมวก ไม่บันทึกลงฐานข้อมูล")
        continue

    # ตรวจป้าย + OCR
    plate_results = plate_model(image)

    for result in plate_results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            class_name = plate_model.names[cls_id]
            conf = float(box.conf[0])

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
                    confidence = conf

    # บันทึกภาพเฉพาะไม่สวมหมวก
    if helmet_status == "ไม่สวมหมวก":
        os.makedirs("web/evidence", exist_ok=True)

        filename = datetime.now().strftime("no_helmet_%Y%m%d_%H%M%S_") + image_file.name
        save_image_path = "web/evidence/" + filename

        cv2.imwrite(save_image_path, image)

        db_image_path = "evidence/" + filename

    # บันทึกลง Database
    save_detection(
        image_path=db_image_path,
        helmet_status=helmet_status,
        plate_number=plate_text,
        province=province_text,
        confidence=confidence
    )

    print("บันทึกข้อมูลลงฐานข้อมูลสำเร็จ")
    print("สถานะหมวก:", helmet_status)
    print("ทะเบียน:", plate_text)
    print("จังหวัด:", province_text)
    print("ภาพหลักฐาน:", db_image_path)

print("\nทดสอบครบทุกภาพแล้ว")
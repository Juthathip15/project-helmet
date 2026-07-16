from flask import Flask, Response, jsonify
import cv2
import os
import time
import easyocr

from datetime import datetime
from queue import Queue, Full
from threading import Thread, Lock
from ultralytics import YOLO
from database import save_detection, get_latest_detections


app = Flask(__name__)


# ==========================
# ตั้งค่า Path โมเดล
# ==========================
HELMET_MODEL_PATH = "runs/detect/runs/helmet_model_gpu/weights/best.pt"
PLATE_MODEL_PATH = "runs/detect/runs/plate_model_gpu/weights/best.pt"
MOTORCYCLE_MODEL_PATH = ("runs/detect/runs/motorcycle_model_gpu/weights/best.pt")

# ==========================
# ตั้งค่ากล้อง / ประสิทธิภาพ
# ==========================
CAMERA_INDEX = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30

# ==========================
# ตั้งค่าระบบตรวจจับมอเตอร์ไซค์
# ==========================
MOTORCYCLE_CONF = 0.50
MOTORCYCLE_IMGSZ = 640

# ขยายกรอบมอเตอร์ไซค์ขึ้นด้านบนเพื่อให้ครอบคลุมศีรษะคนขี่
RIDER_PADDING_TOP = 0.80
RIDER_PADDING_SIDE = 0.20
RIDER_PADDING_BOTTOM = 0.15

# YOLO หมวกทำงานที่ 640 แม้กล้องเป็น 720p
HELMET_IMGSZ = 640

# จำกัด FPS ที่ส่งภาพไปหน้าเว็บ
STREAM_FPS = 20
STREAM_MAX_WIDTH = 960
STREAM_JPEG_QUALITY = 70

# แสดงภาพเฟรมเดียวกับที่ YOLO ตรวจเสร็จ
# เพื่อให้กรอบตรงกับศีรษะเสมอ แม้รถเคลื่อนที่เร็ว
# หมายเหตุ: FPS หน้า Live จะขึ้นกับความเร็ว YOLO บน CPU
DETECTION_INTERVAL = 0.00


# ==========================
# ตั้งค่าระบบตรวจจับ / OCR
# ==========================
SAVE_INTERVAL = 5
DETECT_CONF = 0.55
SAVE_CONF = 0.70

PLATE_CONF = 0.35
PLATE_IMGSZ = 640
PLATE_PADDING = 10

# ป้ายที่เล็กมากจะยังบันทึก crop ไว้ แต่ไม่เรียก OCR
# ช่วยลดอาการหน่วงและลดข้อความ OCR มั่ว
OCR_MIN_PLATE_CONF = 0.40
OCR_MIN_PLATE_WIDTH = 30
OCR_MIN_PLATE_HEIGHT = 10


# ==========================
# Path โฟลเดอร์ภาพ
# ==========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# อยู่ใต้ web เพื่อให้ Dashboard / History แสดงได้
EVIDENCE_ROOT = os.path.join(BASE_DIR, "web", "evidence")

# ข้อมูลดิบสำหรับเทรนและ OCR ย้ายไป D:
DATASET_ROOT = r"D:\helmet_data"
PLATE_TRAINING_ROOT = os.path.join(DATASET_ROOT, "plate_candidates")
PLATE_CROP_ROOT = os.path.join(DATASET_ROOT, "plate_crops")


# ==========================
# CORS สำหรับ PHP
# ==========================
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


# ==========================
# โหลดโมเดล / OCR
# ==========================
# ==========================
# โหลดโมเดล / OCR
# ==========================
motorcycle_model = YOLO(
    MOTORCYCLE_MODEL_PATH
).to("cuda")

helmet_model = YOLO(
    HELMET_MODEL_PATH
).to("cuda")

plate_model = YOLO(
    PLATE_MODEL_PATH
).to("cuda")

reader = easyocr.Reader(
    ["th", "en"],
    gpu=True
)

print(
    "Motorcycle model classes =",
    motorcycle_model.names
)

print(
    "Helmet model classes =",
    helmet_model.names
)

print(
    "Plate model classes =",
    plate_model.names
)
# ==========================
# เปิดกล้อง
# ==========================
camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
camera.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

print("Camera opened =", camera.isOpened())
print(
    "Camera actual size =",
    int(camera.get(cv2.CAP_PROP_FRAME_WIDTH)),
    "x",
    int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
)


# ==========================
# Shared state / background queue
# ==========================
frame_lock = Lock()
detection_lock = Lock()

latest_raw_frame = None
latest_boxes = []
latest_boxes_updated_at = 0.0

# ภาพที่มาจากเฟรมเดียวกับผล YOLO
# ใช้แสดง Live Feed เพื่อไม่ให้ bounding box เหลื่อมกับรถ
latest_detection_frame = None
latest_detection_frame_updated_at = 0.0

last_save_times = {
    "With Helmet": 0.0,
    "Without Helmet": 0.0
}

# OCR และการบันทึกเหตุการณ์ทำทีละงาน เพื่อไม่ให้ CPU และ RAM สะสม
# หาก OCR ยังทำงานอยู่ เหตุการณ์ใหม่จะไม่ถูกต่อคิวซ้อนกัน
# Live Feed จะไม่ค้างรอ OCR
event_queue = Queue(maxsize=1)


# ==========================
# ฟังก์ชันโฟลเดอร์ / บันทึกภาพ
# ==========================
def get_date_folder(root_path, now):
    year = now.strftime("%Y")
    month = now.strftime("%m")
    day = now.strftime("%d")

    save_dir = os.path.join(root_path, year, month, day)
    os.makedirs(save_dir, exist_ok=True)

    return save_dir, year, month, day


def save_evidence_image(display_frame, confidence, now, helmet_status):
    save_dir, year, month, day = get_date_folder(EVIDENCE_ROOT, now)

    time_text = now.strftime("%Y%m%d_%H%M%S_%f")
    conf_text = int(confidence * 100)

    if helmet_status == "Without Helmet":
        status_text = "no_helmet"
    else:
        status_text = "with_helmet"

    filename = f"live_{status_text}_{time_text}_{conf_text}.jpg"
    save_path = os.path.join(save_dir, filename)

    cv2.imwrite(
        save_path,
        display_frame,
        [cv2.IMWRITE_JPEG_QUALITY, 80]
    )

    return f"evidence/{year}/{month}/{day}/{filename}"


def save_raw_plate_training_image(raw_frame, confidence, now):
    save_dir, _, _, _ = get_date_folder(PLATE_TRAINING_ROOT, now)

    time_text = now.strftime("%Y%m%d_%H%M%S")
    conf_text = int(confidence * 100)
    filename = f"raw_no_helmet_{time_text}_{conf_text}.jpg"
    save_path = os.path.join(save_dir, filename)

    cv2.imwrite(
        save_path,
        raw_frame,
        [cv2.IMWRITE_JPEG_QUALITY, 90]
    )

    return save_path


def save_plate_crop_image(plate_crop, helmet_confidence, plate_confidence, now):
    save_dir, _, _, _ = get_date_folder(PLATE_CROP_ROOT, now)

    time_text = now.strftime("%Y%m%d_%H%M%S")
    helmet_conf_text = int(helmet_confidence * 100)
    plate_conf_text = int(plate_confidence * 100)

    filename = (
        f"plate_crop_{time_text}"
        f"_helmet{helmet_conf_text}"
        f"_plate{plate_conf_text}.jpg"
    )

    save_path = os.path.join(save_dir, filename)

    cv2.imwrite(
        save_path,
        plate_crop,
        [cv2.IMWRITE_JPEG_QUALITY, 95]
    )

    return save_path


# ==========================
# ฟังก์ชันช่วยกล้อง / detection
# ==========================
def get_latest_raw_frame():
    with frame_lock:
        if latest_raw_frame is None:
            return None
        return latest_raw_frame.copy()


def get_latest_boxes():
    with detection_lock:
        boxes_copy = [item.copy() for item in latest_boxes]
        updated_at = latest_boxes_updated_at
    return boxes_copy, updated_at


def get_latest_detection_frame():
    with detection_lock:
        if latest_detection_frame is None:
            return None
        return latest_detection_frame.copy()


def normalize_class_name(class_name):
    name = str(class_name).strip().lower()
    name = name.replace("_", " ")
    name = name.replace("-", " ")
    return " ".join(name.split())

def get_rider_roi(frame, motorcycle_box):
    frame_height, frame_width = frame.shape[:2]

    x1 = int(motorcycle_box["x1"])
    y1 = int(motorcycle_box["y1"])
    x2 = int(motorcycle_box["x2"])
    y2 = int(motorcycle_box["y2"])

    width = x2 - x1
    height = y2 - y1

    roi_x1 = max(
        0,
        int(x1 - width * RIDER_PADDING_SIDE)
    )
    roi_y1 = max(
        0,
        int(y1 - height * RIDER_PADDING_TOP)
    )
    roi_x2 = min(
        frame_width,
        int(x2 + width * RIDER_PADDING_SIDE)
    )
    roi_y2 = min(
        frame_height,
        int(y2 + height * RIDER_PADDING_BOTTOM)
    )

    if roi_x2 <= roi_x1 or roi_y2 <= roi_y1:
        return None, None

    rider_roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]

    if rider_roi.size == 0:
        return None, None

    roi_coords = {
        "x1": roi_x1,
        "y1": roi_y1,
        "x2": roi_x2,
        "y2": roi_y2
    }

    return rider_roi, roi_coords

def is_valid_helmet_box_coords(x1, y1, x2, y2, frame_width, frame_height):
    width = x2 - x1
    height = y2 - y1

    if width <= 0 or height <= 0:
        return False

    area = width * height
    frame_area = frame_width * frame_height
    center_y = (y1 + y2) / 2
    ratio = width / height

    if area < frame_area * 0.002:
        return False

    if area > frame_area * 0.20:
        return False

    if center_y > frame_height * 0.75:
        return False

    if ratio > 2.0 or ratio < 0.25:
        return False

    return True


def draw_detection_box(frame, detection):
    x1 = int(detection["x1"])
    y1 = int(detection["y1"])
    x2 = int(detection["x2"])
    y2 = int(detection["y2"])

    class_name = detection["class_name"]
    confidence = detection["confidence"]

    if class_name == "With Helmet":
        color = (0, 180, 0)
    else:
        color = (0, 0, 255)

    label = f"{class_name} {confidence:.2f}"

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    text_size, _ = cv2.getTextSize(
        label,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        2
    )

    text_width, text_height = text_size
    label_top = max(0, y1 - text_height - 8)

    cv2.rectangle(
        frame,
        (x1, label_top),
        (x1 + text_width + 6, y1),
        color,
        -1
    )

    cv2.putText(
        frame,
        label,
        (x1 + 3, max(18, y1 - 5)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2
    )


# ==========================
# ครอปและอ่านป้ายทะเบียน
# ทำใน Event Worker เท่านั้น
# ==========================
def crop_plate_from_box(frame, x1, y1, x2, y2):
    frame_height, frame_width = frame.shape[:2]

    x1 = max(0, x1 - PLATE_PADDING)
    y1 = max(0, y1 - PLATE_PADDING)
    x2 = min(frame_width, x2 + PLATE_PADDING)
    y2 = min(frame_height, y2 + PLATE_PADDING)

    if x2 <= x1 or y2 <= y1:
        return None

    crop = frame[y1:y2, x1:x2]

    if crop.size == 0:
        return None

    return crop


def read_plate_from_frame(raw_frame, helmet_confidence, now):
    plate_text = ""
    province_text = ""
    plate_crop_path = ""
    best_plate_confidence = 0.0

    results = plate_model(
        raw_frame,
        conf=PLATE_CONF,
        imgsz=PLATE_IMGSZ,
        verbose=False
    )

    best_box = None

    for result in results:
        if result.boxes is None:
            continue

        for box in result.boxes:
            cls_id = int(box.cls[0])
            class_name = normalize_class_name(plate_model.names[cls_id])

            if class_name not in ("license plate", "licenseplate"):
                continue

            plate_confidence = float(box.conf[0])

            if plate_confidence > best_plate_confidence:
                best_plate_confidence = plate_confidence
                best_box = box

    if best_box is None:
        return plate_text, province_text, plate_crop_path, best_plate_confidence

    x1, y1, x2, y2 = map(int, best_box.xyxy[0])
    plate_crop = crop_plate_from_box(raw_frame, x1, y1, x2, y2)

    if plate_crop is None:
        return plate_text, province_text, plate_crop_path, best_plate_confidence

    plate_crop_path = save_plate_crop_image(
        plate_crop,
        helmet_confidence,
        best_plate_confidence,
        now
    )

    crop_height, crop_width = plate_crop.shape[:2]

    # crop เล็กมาก: เก็บรูปไว้เทรนได้ แต่ข้าม OCR เพื่อลดหน่วง
    if (
        best_plate_confidence < OCR_MIN_PLATE_CONF
        or crop_width < OCR_MIN_PLATE_WIDTH
        or crop_height < OCR_MIN_PLATE_HEIGHT
    ):
        print(
            "ข้าม OCR: ป้ายเล็กหรือ confidence ต่ำ",
            f"({crop_width}x{crop_height}, {best_plate_confidence:.2%})"
        )
        return plate_text, province_text, plate_crop_path, best_plate_confidence

    gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(
        gray,
        None,
        fx=4,
        fy=4,
        interpolation=cv2.INTER_CUBIC
    )
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    try:
        ocr_result = reader.readtext(
            gray,
            detail=1,
            paragraph=False
        )
    except Exception as error:
        print("OCR error:", error)
        return plate_text, province_text, plate_crop_path, best_plate_confidence

    print("OCR Result =", ocr_result)

    text_parts = []
    for item in ocr_result:
        text = str(item[1]).strip()
        if text:
            text_parts.append(text)

    plate_text = " ".join(text_parts).strip()

    return plate_text, province_text, plate_crop_path, best_plate_confidence


# ==========================
# Capture Worker
# อ่านกล้องตลอดเวลา เพื่อให้ได้ frame ใหม่สุด
# ==========================
def capture_worker():
    global latest_raw_frame

    while True:
        success, frame = camera.read()

        if not success:
            print("อ่านภาพจากกล้องไม่ได้")
            time.sleep(0.10)
            continue

        # ห้าม cv2.flip(frame, 1)
        # เพราะป้ายทะเบียนจะกลับด้านและ OCR อ่านยาก
        with frame_lock:
            latest_raw_frame = frame


# ==========================
# Event Worker
# OCR + ตรวจป้าย + บันทึกไฟล์ / DB ทำเบื้องหลัง
# ==========================
def process_event_worker():
    while True:
        (
            raw_frame,
            evidence_frame,
            helmet_status,
            helmet_confidence,
            now
        ) = event_queue.get()

        try:
            # เก็บภาพก่อน เพื่อไม่ให้สูญเหตุการณ์แม้ OCR อ่านไม่สำเร็จ
            db_image_path = save_evidence_image(
                evidence_frame,
                helmet_confidence,
                now,
                helmet_status
            )

            plate_number = ""
            province = ""
            plate_crop_path = ""
            plate_confidence = 0.0
            raw_training_path = ""

            if helmet_status == "Without Helmet":
                # ตรวจป้ายและ OCR เฉพาะกรณีไม่สวมหมวก
                raw_training_path = save_raw_plate_training_image(
                    raw_frame,
                    helmet_confidence,
                    now
                )

                (
                    plate_number,
                    province,
                    plate_crop_path,
                    plate_confidence
                ) = read_plate_from_frame(
                    raw_frame,
                    helmet_confidence,
                    now
                )

                db_helmet_status = "ไม่สวมหมวก"
            else:
                db_helmet_status = "สวมหมวก"

            save_detection(
                image_path=db_image_path,
                helmet_status=db_helmet_status,
                plate_number=plate_number,
                province=province,
                confidence=helmet_confidence
            )

            print("====================================")
            print("สถานะ:", db_helmet_status)
            print("บันทึก Evidence:", db_image_path)

            if helmet_status == "Without Helmet":
                print("ภาพเต็มดิบ:", raw_training_path)
                print("Crop ป้ายทะเบียน:", plate_crop_path)
                print("Plate confidence:", f"{plate_confidence:.2%}")
                print("ทะเบียน:", plate_number)
                print("จังหวัด:", province)
            else:
                print("สวมหมวก: ไม่ตรวจป้ายทะเบียน")

            print("Helmet confidence:", f"{helmet_confidence:.2%}")
            print("====================================")

        except Exception as error:
            print("Event worker error:", error)

        finally:
            event_queue.task_done()
def draw_motorcycle_box(frame, detection):
    x1 = int(detection["x1"])
    y1 = int(detection["y1"])
    x2 = int(detection["x2"])
    y2 = int(detection["y2"])

    confidence = detection["confidence"]
    label = f"Motorcycle {confidence:.2f}"
    color = (255, 120, 0)

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        color,
        2
    )

    cv2.putText(
        frame,
        label,
        (x1, max(20, y1 - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        color,
        2
    )

# ==========================
# Helmet Detection Worker
# ตรวจหมวกอิสระจากการส่งภาพ Live Feed
# ==========================
def helmet_detection_worker():
    global latest_boxes, latest_boxes_updated_at
    global latest_detection_frame, latest_detection_frame_updated_at
    global last_save_times

    while True:
        loop_started_at = time.time()
        raw_frame = get_latest_raw_frame()

        if raw_frame is None:
            time.sleep(0.05)
            continue

        frame_height, frame_width = raw_frame.shape[:2]

        detections = []
        motorcycle_detections = []
        events_to_save = []

        try:
            # ==========================
            # 1. ตรวจจับมอเตอร์ไซค์
            # ==========================
            motorcycle_results = motorcycle_model(
                raw_frame,
                conf=MOTORCYCLE_CONF,
                imgsz=MOTORCYCLE_IMGSZ,
                verbose=False
            )

            for result in motorcycle_results:
                if result.boxes is None:
                    continue

                for box in result.boxes:
                    cls_id = int(box.cls[0])

                    motorcycle_class = normalize_class_name(
                        motorcycle_model.names[cls_id]
                    )

                    motorcycle_confidence = float(box.conf[0])

                    # รองรับชื่อ Class หลายแบบ
                    if motorcycle_class not in (
                        "motorcycle",
                        "motorbike",
                        "motor cycle"
                    ):
                        continue

                    mx1, my1, mx2, my2 = map(
                        int,
                        box.xyxy[0]
                    )

                    if mx2 <= mx1 or my2 <= my1:
                        continue

                    motorcycle_detection = {
                        "x1": mx1,
                        "y1": my1,
                        "x2": mx2,
                        "y2": my2,
                        "class_name": "Motorcycle",
                        "confidence": motorcycle_confidence
                    }

                    motorcycle_detections.append(
                        motorcycle_detection
                    )

                    # ==========================
                    # 2. ขยายพื้นที่รถและคนขี่
                    # ==========================
                    rider_roi, roi_coords = get_rider_roi(
                        raw_frame,
                        motorcycle_detection
                    )

                    if rider_roi is None:
                        continue

                    roi_height, roi_width = rider_roi.shape[:2]

                    # ==========================
                    # 3. ตรวจหมวกเฉพาะ Rider ROI
                    # ==========================
                    helmet_results = helmet_model(
                        rider_roi,
                        conf=DETECT_CONF,
                        imgsz=HELMET_IMGSZ,
                        verbose=False
                    )

                    best_helmet_detection = None

                    for helmet_result in helmet_results:
                        if helmet_result.boxes is None:
                            continue

                        for helmet_box in helmet_result.boxes:
                            hx1, hy1, hx2, hy2 = map(
                                int,
                                helmet_box.xyxy[0]
                            )

                            if not is_valid_helmet_box_coords(
                                hx1,
                                hy1,
                                hx2,
                                hy2,
                                roi_width,
                                roi_height
                            ):
                                continue

                            helmet_cls_id = int(
                                helmet_box.cls[0]
                            )

                            helmet_class_name = (
                                helmet_model.names[
                                    helmet_cls_id
                                ]
                            )

                            helmet_confidence = float(
                                helmet_box.conf[0]
                            )

                            if helmet_class_name not in (
                                "With Helmet",
                                "Without Helmet"
                            ):
                                continue

                            # แปลงพิกัดจาก ROI กลับเป็นภาพเต็ม
                            full_x1 = roi_coords["x1"] + hx1
                            full_y1 = roi_coords["y1"] + hy1
                            full_x2 = roi_coords["x1"] + hx2
                            full_y2 = roi_coords["y1"] + hy2

                            helmet_detection = {
                                "x1": full_x1,
                                "y1": full_y1,
                                "x2": full_x2,
                                "y2": full_y2,
                                "class_name": helmet_class_name,
                                "confidence": helmet_confidence,
                                "motorcycle_box": motorcycle_detection
                            }

                            detections.append(
                                helmet_detection
                            )

                            # เลือกผลหมวกที่ Confidence สูงที่สุด
                            # ของมอเตอร์ไซค์คันนี้
                            if (
                                best_helmet_detection is None
                                or helmet_confidence
                                > best_helmet_detection[
                                    "confidence"
                                ]
                            ):
                                best_helmet_detection = (
                                    helmet_detection
                                )

                    # ==========================
                    # 4. สร้าง Event แยกตามรถแต่ละคัน
                    # ==========================
                    if (
                        best_helmet_detection is not None
                        and best_helmet_detection[
                            "confidence"
                        ] >= SAVE_CONF
                    ):
                        events_to_save.append(
                            best_helmet_detection
                        )

        except Exception as error:
            print(
                "Motorcycle/Helmet detection error:",
                error
            )
            time.sleep(0.10)
            continue

        now_time = time.time()

        # ==========================
        # 5. วาดกรอบ Live Feed
        # ==========================
        detected_display_frame = raw_frame.copy()

        # วาดกรอบมอเตอร์ไซค์
        for motorcycle in motorcycle_detections:
            draw_motorcycle_box(
                detected_display_frame,
                motorcycle
            )

        # วาดกรอบหมวก
        for detection in detections:
            draw_detection_box(
                detected_display_frame,
                detection
            )

        with detection_lock:
            latest_boxes = detections
            latest_boxes_updated_at = now_time
            latest_detection_frame = (
                detected_display_frame
            )
            latest_detection_frame_updated_at = (
                now_time
            )

        # ==========================
        # 6. ให้ Without Helmet สำคัญก่อน
        # ==========================
        events_to_save.sort(
            key=lambda item:
            item["class_name"] != "Without Helmet"
        )

        # ==========================
        # 7. ส่ง Event ไป Worker
        # ==========================
        for event in events_to_save:
            helmet_status = event["class_name"]
            helmet_confidence = event["confidence"]
            motorcycle_box = event["motorcycle_box"]

            if (
                now_time - last_save_times[
                    helmet_status
                ] < SAVE_INTERVAL
            ):
                continue

            evidence_frame = raw_frame.copy()

            # วาดกรอบรถคันที่เป็น Event
            draw_motorcycle_box(
                evidence_frame,
                motorcycle_box
            )

            # วาดกรอบหมวกเฉพาะ Event นี้
            draw_detection_box(
                evidence_frame,
                event
            )

            try:
                event_queue.put_nowait(
                    (
                        raw_frame.copy(),
                        evidence_frame,
                        helmet_status,
                        helmet_confidence,
                        datetime.now()
                    )
                )

                last_save_times[
                    helmet_status
                ] = now_time

                print(
                    "ส่งเหตุการณ์:",
                    helmet_status,
                    f"{helmet_confidence:.2%}",
                    "Motorcycle:",
                    f"{motorcycle_box['confidence']:.2%}"
                )

            except Full:
                print(
                    "Event Worker ยังทำงานอยู่:",
                    "ข้ามเหตุการณ์นี้ชั่วคราว"
                )

            # Queue มีขนาด 1
            break

        elapsed = time.time() - loop_started_at
        sleep_time = DETECTION_INTERVAL - elapsed

        if sleep_time > 0:
            time.sleep(sleep_time)
            
# ==========================
# เริ่ม Background Workers เพียงครั้งเดียว
# ==========================
camera_thread = Thread(target=capture_worker, daemon=True)
detector_thread = Thread(target=helmet_detection_worker, daemon=True)
event_thread = Thread(target=process_event_worker, daemon=True)

camera_thread.start()
detector_thread.start()
event_thread.start()


# ==========================
# MJPEG Stream
# แสดงเฟรมเดียวกับที่ YOLO ตรวจแล้ว
# จึงทำให้ bounding box ตรงตำแหน่งจริง ไม่เหลื่อมกับรถ
# ==========================
def generate_frames():
    frame_delay = 1 / STREAM_FPS

    while True:
        # ใช้ภาพที่ detector worker ตรวจเสร็จแล้วพร้อมกรอบ
        # ภาพนี้และ box เป็นเฟรมเดียวกัน 100%
        display_frame = get_latest_detection_frame()

        # ตอนเริ่มโปรแกรม detector ยังไม่สร้างภาพ ให้แสดงกล้องดิบชั่วคราว
        if display_frame is None:
            display_frame = get_latest_raw_frame()

        if display_frame is None:
            time.sleep(0.05)
            continue

        stream_frame = display_frame
        frame_height, frame_width = stream_frame.shape[:2]

        if frame_width > STREAM_MAX_WIDTH:
            scale = STREAM_MAX_WIDTH / frame_width
            new_width = int(frame_width * scale)
            new_height = int(frame_height * scale)

            stream_frame = cv2.resize(
                stream_frame,
                (new_width, new_height),
                interpolation=cv2.INTER_AREA
            )

        ret, buffer = cv2.imencode(
            ".jpg",
            stream_frame,
            [cv2.IMWRITE_JPEG_QUALITY, STREAM_JPEG_QUALITY]
        )

        if not ret:
            time.sleep(0.01)
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + buffer.tobytes()
            + b"\r\n"
        )

        time.sleep(frame_delay)


# ==========================
# Flask Routes
# ==========================
@app.route("/")
def index():
    return "Live Feed Server Running"


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
    )


@app.route("/api/status")
def api_status():
    camera_online = camera is not None and camera.isOpened()

    return jsonify({
        "online": camera_online,
        "camera_name": "Web Camera"
    })


@app.route("/api/latest-detections")
def api_latest_detections():
    try:
        items = get_latest_detections(5)
        return jsonify({"items": items})

    except Exception as error:
        print("Latest detections API error:", error)
        return jsonify({"items": [], "error": str(error)}), 500


# ==========================
# เริ่ม Flask Server
# ==========================
if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        threaded=True,
        use_reloader=False
    )

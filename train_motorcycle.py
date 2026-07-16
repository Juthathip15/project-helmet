from ultralytics import YOLO

def main():
    model = YOLO("yolov8n.pt")

    model.train(
        data="D:/dataset/motorcycle/data.yaml",
        epochs=100,
        imgsz=640,
        batch=8,
        device=0,          # ใช้ GPU
        workers=0,         # ป้องกันปัญหา multiprocessing บน Windows
        project="runs",
        name="motorcycle_model_gpu"
    )

if __name__ == "__main__":
    main()
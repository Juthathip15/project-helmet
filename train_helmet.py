from ultralytics import YOLO

def main():
    model = YOLO("yolov8n.pt")

    model.train(
        data="D:/dataset/helmet/data.yaml",
        epochs=100,
        imgsz=640,
        batch=8,
        device=0,
        workers=0,
        project="runs",
        name="helmet_model_gpu"
    )

if __name__ == "__main__":
    main()
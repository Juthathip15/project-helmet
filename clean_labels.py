from pathlib import Path

label_dirs = [
    Path("D:/dataset/helmet/train/labels"),
    Path("D:/dataset/helmet/valid/labels"),
    Path("D:/dataset/helmet/test/labels"),
]

for label_dir in label_dirs:
    for txt_file in label_dir.glob("*.txt"):
        lines = txt_file.read_text().splitlines()
        kept = []

        for line in lines:
            parts = line.strip().split()
            if not parts:
                continue

            class_id = int(parts[0])

            if class_id in [0, 1]:
                kept.append(line)

        txt_file.write_text("\n".join(kept) + ("\n" if kept else ""))

print("Clean labels done")
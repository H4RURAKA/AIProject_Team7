import torch
import cv2
import json
from pathlib import Path

# YOLOv11 모델 로드
model = torch.hub.load('ultralytics/yolov11', 'yolov11s', pretrained=True)

# 학습 데이터 준비
train_images = ['1.jpg', '2.jpg', '3.jpg']
train_jsons = ['1.json', '2.json', '3.json']

# JSON에서 레이블 추출
def load_labels(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
    labels = []
    for node in data['nodes']:
        labels.append({
            'name': node['type'],
            'x_center': node['x'],
            'y_center': node['y']
        })
    return labels

# 이미지와 레이블 매핑
for img_path, json_path in zip(train_images, train_jsons):
    img = cv2.imread(img_path)
    labels = load_labels(json_path)
    # train/images, train/labels
    # YOLO 형식(.txt 파일)으로 변환 필요

# 터미널에서 실행 예시: python train.py --img 640 --batch 16 --epochs 10 --data custom_data.yaml --weights yolov11s.pt

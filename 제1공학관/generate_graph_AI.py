import cv2
import pytesseract
import json
import os

def extract_nodes_from_image(image_path, floor_name):
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binarized = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)

    contours, _ = cv2.findContours(binarized, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    nodes = []
    node_id = 1

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w * h < 300:  # 너무 작은 것은 무시
            continue

        roi = image[y:y+h, x:x+w]
        text = pytesseract.image_to_string(roi, config='--psm 7').strip()

        if not text:
            continue

        node_type = "Room"
        lowered = text.lower()

        # 유형 자동 분류
        if "elevator" in lowered:
            node_type = "Elevator"
        elif "stair" in lowered:
            node_type = "Stair"
        elif "door" in lowered:
            node_type = "Door"
        elif "node" in lowered or text.isdigit():
            node_type = "Corridor"
        elif "toilet" in lowered:
            node_type = "Restroom"

        nodes.append({
            "id": node_id,
            "name": text,
            "type": node_type,
            "x": float(x + w // 2),
            "y": float(y + h // 2)
        })
        node_id += 1

    return nodes

def save_graph_json(output_path, background, nodes, scale=1.0):
    data = {
        "background": background,
        "scale": scale,
        "nodes": nodes,
        "edges": []  # 아직 간선 없음
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    for floor in [4, 5]:
        img_name = f"{floor}.jpg"
        json_name = f"{floor}f_auto.json"

        nodes = extract_nodes_from_image(img_name, f"{floor}f")
        save_graph_json(json_name, img_name, nodes)
        print(f"{json_name} 생성 완료 - 노드 수: {len(nodes)}")

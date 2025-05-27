# 학습된 모델 로드
model = torch.hub.load('ultralytics/yolov11', 'custom', path='path/to/trained_model.pt')

# 객체 감지 및 JSON 생성 함수
def create_json_from_image(image_path):
    img = cv2.imread(image_path)
    results = model(img)
    detections = results.pandas().xyxy[0]  # 감지된 객체 데이터프레임

    nodes = []
    edges = []
    node_id = 1

    # 노드 생성
    for _, row in detections.iterrows():
        node = {
            "id": node_id,
            "name": f"{row['name']}{node_id}",
            "type": row['name'],
            "x": (row['xmin'] + row['xmax']) / 2,
            "y": (row['ymin'] + row['ymax']) / 2
        }
        nodes.append(node)
        node_id += 1

    # 엣지 생성
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            edge = {
                "source": nodes[i]['id'],
                "target": nodes[j]['id'],
                "weight": ((nodes[i]['x'] - nodes[j]['x'])**2 + (nodes[i]['y'] - nodes[j]['y'])**2)**0.5
            }
            edges.append(edge)

    json_data = {
        "background": Path(image_path).name,
        "scale": 1.0,
        "nodes": nodes,
        "edges": edges
    }

    output_path = f"{Path(image_path).stem}.json"
    with open(output_path, 'w') as f:
        json.dump(json_data, f, indent=4)
    return output_path

# 새로운 이미지 처리
new_image = '4.jpg'
output_json = create_json_from_image(new_image)
print(f"JSON 파일이 생성되었습니다: {output_json}")

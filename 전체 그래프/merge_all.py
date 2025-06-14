import json
import glob
import os

def merge_buildings_json(input_pattern="*.json", output_file="merged_buildings_graph.json"):
    """
    여러 건물(graph) JSON 파일을 하나의 그래프로 병합합니다.

    - 각 노드의 id에 건물명(파일명) 접두사를 추가하여 충돌 방지
    - edges는 양방향으로 추가
    - Outside 타입의 road1~road4 노드를 찾아서 매핑
    - road3↔road4: weight=1.0
    - road2↔road1: weight=85.0
    """
    nodes = []
    edges = []
    road_map = {}  # road 이름 -> 새로운 id

    # 입력 파일 찾기 (출력 파일 제외)
    files = sorted(glob.glob(input_pattern))
    files = [f for f in files if os.path.basename(f) != output_file]

    for filepath in files:
        building = os.path.splitext(os.path.basename(filepath))[0]  # ex: '산학협력관'
        data = json.load(open(filepath, 'r', encoding='utf-8'))

        # 노드 처리
        for node in data.get("nodes", []):
            old_id = node["id"]
            new_id = f"{building}_{old_id}"
            node["id"] = new_id

            # road 노드 매핑 (Outside 타입, 이름이 'roadX'인 경우)
            if node.get("type") == "Outside" and node.get("name", "").startswith("road"):
                road_map[node["name"]] = new_id

            nodes.append(node)

        # 엣지 처리 (양방향)
        for edge in data.get("edges", []):
            src = f"{building}_{edge['source']}"
            tgt = f"{building}_{edge['target']}"
            weight = edge.get("weight", 1.0)
            edges.append({"source": src, "target": tgt, "weight": weight})
            edges.append({"source": tgt, "target": src, "weight": weight})

    # 건물 간 도로 연결 추가
    # road3 <-> road4, weight = 1m
    if "road3" in road_map and "road4" in road_map:
        a, b = road_map["road3"], road_map["road4"]
        edges.append({"source": a, "target": b, "weight": 1.0})
        edges.append({"source": b, "target": a, "weight": 1.0})

    # road2 <-> road1, weight = 85m
    if "road2" in road_map and "road1" in road_map:
        a, b = road_map["road2"], road_map["road1"]
        edges.append({"source": a, "target": b, "weight": 25.0})
        edges.append({"source": b, "target": a, "weight": 25.0})

    # 결과 저장
    merged = {"nodes": nodes, "edges": edges}
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    merge_buildings_json()

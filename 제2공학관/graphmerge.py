import json
import glob
import os
import re

def merge_graph_json(input_pattern="*f.json", output_file="merged_graph.json"):
    """
    Merge multiple floor graph JSON files into a single graph.

    - Discards `background` and `scale`.
    - Prefixes each node id with its floor (e.g., "1f_123").
    - Merges nodes and edges across floors.
    - Adds elevator connections between adjacent floors (weight 2.0).
    - Adds stair connections between adjacent floors (weight 6.0).
    """
    nodes = []
    edges = []
    elevator_map = {}  # floor -> {index: new_id}
    stair_map = {}     # floor -> {index: new_id}

    # find and sort input files by floor number
    files = sorted(
        glob.glob(input_pattern),
        key=lambda x: int(re.search(r"(\d+)f", os.path.basename(x)).group(1))
    )

    for filepath in files:
        floor = os.path.basename(filepath).split('.')[0]  # e.g. '1f'
        data = json.load(open(filepath, 'r', encoding='utf-8'))
        elevator_map[floor] = {}
        stair_map[floor] = {}

        # process nodes
        for node in data.get("nodes", []):
            old_id = node["id"]
            new_id = f"{floor}_{old_id}"
            node["id"] = new_id

            # record elevator and stair nodes by their index extracted from name
            if node["type"] == "Elevator":
                m = re.search(r"elevator(\d+)", node["name"])
                if m:
                    elevator_map[floor][m.group(1)] = new_id
            elif node["type"] == "Stair":
                m = re.search(r"stair(\d+)", node["name"])
                if m:
                    stair_map[floor][m.group(1)] = new_id

            nodes.append(node)

        # process edges
        for edge in data.get("edges", []):
            src = f"{floor}_{edge['source']}"
            tgt = f"{floor}_{edge['target']}"
            edges.append({"source": src, "target": tgt, "weight": edge["weight"]})
            edges.append({"source": tgt, "target": src, "weight": edge["weight"]})

    # add inter-floor connections for elevators and stairs
    floors = sorted(
        elevator_map.keys(),
        key=lambda f: int(re.search(r"(\d+)", f).group(1))
    )
    for i in range(len(floors) - 1):
        f1, f2 = floors[i], floors[i + 1]
        # elevators (weight 2.0)
        for idx, id1 in elevator_map[f1].items():
            id2 = elevator_map[f2].get(idx)
            if id2:
                edges.append({"source": id1, "target": id2, "weight": 1.0})
                edges.append({"source": id2, "target": id1, "weight": 1.0})
        # stairs (weight 6.0)
        for idx, id1 in stair_map[f1].items():
            id2 = stair_map[f2].get(idx)
            if id2:
                edges.append({"source": id1, "target": id2, "weight": 6.0})
                edges.append({"source": id2, "target": id1, "weight": 6.0})

    # write merged graph to output
    merged = {"nodes": nodes, "edges": edges}
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    merge_graph_json()

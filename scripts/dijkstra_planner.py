#!/usr/bin/env python3
"""
Dijkstra Path Planner Script for X30 GS Simulator
Calculates the shortest movement path from a start node (e.g., current node 'nofr')
to a destination node (e.g., 'ChargeIn-final' / 'ChargeIn').
"""

import os
import sys
import csv
import json
import math
import heapq
import argparse
from typing import Dict, List, Tuple, Optional, Any


class DijkstraPlanner:
    def __init__(self):
        # Node mapping: node_id -> { 'name': str, 'x': float, 'y': float, 'z': float, 'yaw': float, 'raw': Any }
        self.nodes: Dict[str, dict] = {}
        # Graph adjacency list: node_id -> list of (neighbor_id, edge_cost, path_id)
        self.graph: Dict[str, List[Tuple[str, float, str]]] = {}
        # Name lookup for quick matching: normalized_name -> node_id
        self.name_to_id: Dict[str, str] = {}

    def parse_pose(self, pose_str: str) -> Tuple[float, float, float, float]:
        """Parse pose string formatted like '{x,y,z,yaw}' or list/dict."""
        try:
            if isinstance(pose_str, str):
                cleaned = pose_str.strip('{}()[] ')
                parts = [float(p.strip()) for p in cleaned.split(',') if p.strip()]
                x = parts[0] if len(parts) > 0 else 0.0
                y = parts[1] if len(parts) > 1 else 0.0
                z = parts[2] if len(parts) > 2 else 0.0
                yaw = parts[3] if len(parts) > 3 else 0.0
                return x, y, z, yaw
            elif isinstance(pose_str, (list, tuple)):
                x = float(pose_str[0]) if len(pose_str) > 0 else 0.0
                y = float(pose_str[1]) if len(pose_str) > 1 else 0.0
                z = float(pose_str[2]) if len(pose_str) > 2 else 0.0
                yaw = float(pose_str[3]) if len(pose_str) > 3 else 0.0
                return x, y, z, yaw
        except Exception:
            pass
        return 0.0, 0.0, 0.0, 0.0

    def add_node(self, node_id: str, name: str = "", x: float = 0.0, y: float = 0.0, z: float = 0.0, yaw: float = 0.0, raw: Any = None):
        """Add a node to the planner graph."""
        nid = str(node_id).strip()
        self.nodes[nid] = {
            'id': nid,
            'name': name or nid,
            'x': float(x),
            'y': float(y),
            'z': float(z),
            'yaw': float(yaw),
            'raw': raw
        }
        if nid not in self.graph:
            self.graph[nid] = []
            
        # Add to name lookup
        norm_name = (name or nid).strip().lower()
        self.name_to_id[norm_name] = nid
        self.name_to_id[nid.lower()] = nid

    def add_edge(self, node1: str, node2: str, cost: Optional[float] = None, path_id: str = "", bidirectional: bool = True):
        """Add an edge between node1 and node2."""
        n1 = str(node1).strip()
        n2 = str(node2).strip()
        if n1 not in self.nodes or n2 not in self.nodes:
            return

        if cost is None:
            # Compute 3D Euclidean distance
            p1 = self.nodes[n1]
            p2 = self.nodes[n2]
            cost = math.sqrt((p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2 + (p1['z'] - p2['z'])**2)

        self.graph[n1].append((n2, cost, path_id))
        if bidirectional:
            self.graph[n2].append((n1, cost, path_id))

    def load_from_csv(self, nodes_csv_path: str, paths_csv_path: Optional[str] = None):
        """Load graph topology from nodes.csv and optional paths.csv."""
        if not os.path.exists(nodes_csv_path):
            print(f"[Error] Nodes CSV file not found: {nodes_csv_path}")
            return False

        print(f"[DijkstraPlanner] Loading nodes from {nodes_csv_path}...")
        with open(nodes_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) < 4:
                    continue
                nid = row[0].strip()
                name = row[1].strip() if len(row) > 1 else nid
                x, y, z, yaw = self.parse_pose(row[3]) if len(row) > 3 else (0.0, 0.0, 0.0, 0.0)
                self.add_node(nid, name=name, x=x, y=y, z=z, yaw=yaw, raw=row)

        if paths_csv_path and os.path.exists(paths_csv_path):
            print(f"[DijkstraPlanner] Loading paths from {paths_csv_path}...")
            with open(paths_csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                first_row = next(reader, None)
                if first_row:
                    # Check if the first row is a header
                    if len(first_row) > 0 and (first_row[0].lower() in ['id', 'path_id'] or not first_row[0].isdigit() and not first_row[0].startswith('path_')):
                        pass # It's a header, skip it
                    else:
                        # It's data, process it
                        if len(first_row) >= 3:
                            self.add_edge(first_row[1].strip(), first_row[2].strip(), path_id=first_row[0].strip(), bidirectional=False)
                for row in reader:
                    if len(row) < 3:
                        continue
                    pid = row[0].strip()
                    n1 = row[1].strip()
                    n2 = row[2].strip()
                    self.add_edge(n1, n2, path_id=pid, bidirectional=False)
        else:
            # If no paths CSV is provided, connect nearest neighbor nodes automatically (mesh graph)
            print("[DijkstraPlanner] No paths.csv provided. Auto-generating sequential/proximity graph...")
            node_ids = list(self.nodes.keys())
            for i in range(len(node_ids) - 1):
                self.add_edge(node_ids[i], node_ids[i+1], bidirectional=True)

        return True

    def load_from_json(self, json_path: str):
        """Load graph topology from a waypoints JSON file."""
        if not os.path.exists(json_path):
            print(f"[Error] JSON file not found: {json_path}")
            return False

        print(f"[DijkstraPlanner] Loading waypoints from {json_path}...")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        waypoints = data if isinstance(data, list) else data.get('waypoints', data.get('nodes', []))
        prev_id = None
        for i, wp in enumerate(waypoints):
            nid = wp.get('Node_info') or wp.get('ID') or wp.get('id') or f"wp_{i}"
            name = wp.get('Node_info') or wp.get('Name') or nid
            x = float(wp.get('PosX', wp.get('x', 0.0)))
            y = float(wp.get('PosY', wp.get('y', 0.0)))
            z = float(wp.get('PosZ', wp.get('z', 0.0)))
            yaw = float(wp.get('AngleYaw', wp.get('yaw', 0.0)))

            self.add_node(nid, name=name, x=x, y=y, z=z, yaw=yaw, raw=wp)

            if prev_id is not None:
                self.add_edge(prev_id, nid, bidirectional=True)
            prev_id = nid

        return True

    def resolve_node_id(self, search_query: str) -> Optional[str]:
        """Resolve a user search query (ID or Name) to a node ID in the graph."""
        if not search_query:
            return None
        query = search_query.strip()
        
        # 1. Exact match by ID
        if query in self.nodes:
            return query
            
        # 2. Exact match by normalized name / ID lower
        query_lower = query.lower()
        if query_lower in self.name_to_id:
            return self.name_to_id[query_lower]
            
        # 3. Substring match
        for nid, info in self.nodes.items():
            if query_lower in nid.lower() or query_lower in info['name'].lower():
                return nid

        return None

    def find_shortest_path(self, start_query: str, end_query: str, is_go_home: bool = False) -> Optional[Dict[str, Any]]:
        """
        Run Dijkstra's algorithm to find the shortest path from start_query to end_query.
        Returns a dict containing path nodes, total distance, and trajectory steps.
        """
        start_node = self.resolve_node_id(start_query)
        end_node = self.resolve_node_id(end_query)

        if not start_node:
            print(f"[Error] Could not find start node matching query: '{start_query}'")
            return None
        if not end_node:
            print(f"[Error] Could not find end node matching query: '{end_query}'")
            return None

        print(f"[DijkstraPlanner] Calculating route from '{start_node}' ({self.nodes[start_node]['name']}) -> '{end_node}' ({self.nodes[end_node]['name']})...")

        # Priority queue stores tuples of (accumulated_distance, current_node_id)
        pq: List[Tuple[float, str]] = []
        heapq.heappush(pq, (0.0, start_node))

        distances: Dict[str, float] = {nid: float('inf') for nid in self.nodes}
        distances[start_node] = 0.0

        previous_nodes: Dict[str, Optional[str]] = {nid: None for nid in self.nodes}
        edge_used: Dict[str, str] = {nid: "" for nid in self.nodes}

        while pq:
            current_dist, u = heapq.heappop(pq)

            if current_dist > distances[u]:
                continue

            if u == end_node:
                break  # Reached target

            for v, weight, path_id in self.graph.get(u, []):
                new_dist = current_dist + weight
                if new_dist < distances[v]:
                    distances[v] = new_dist
                    previous_nodes[v] = u
                    edge_used[v] = path_id
                    heapq.heappush(pq, (new_dist, v))

        if distances[end_node] == float('inf'):
            print(f"[DijkstraPlanner] No path found between '{start_node}' and '{end_node}'.")
            return None

        # Reconstruct path
        path_ids: List[str] = []
        curr = end_node
        while curr is not None:
            path_ids.append(curr)
            curr = previous_nodes[curr]
        path_ids.reverse()

        # Build trajectory step details
        steps = []
        accumulated = 0.0
        for i in range(len(path_ids)):
            nid = path_ids[i]
            node_info = self.nodes[nid]
            step_dist = 0.0
            step_yaw = node_info['yaw']
            
            if i > 0:
                prev_info = self.nodes[path_ids[i-1]]
                dx = node_info['x'] - prev_info['x']
                dy = node_info['y'] - prev_info['y']
                dz = node_info['z'] - prev_info['z']
                step_dist = math.sqrt(dx**2 + dy**2 + dz**2)
                accumulated += step_dist

            # Calculate directional yaw pointing to the NEXT node
            if i < len(path_ids) - 1:
                next_info = self.nodes[path_ids[i+1]]
                dx_next = next_info['x'] - node_info['x']
                dy_next = next_info['y'] - node_info['y']
                step_yaw = math.atan2(dy_next, dx_next)
            else:
                # For the final node, inherit the arrival angle
                if i > 0:
                    prev_info = self.nodes[path_ids[i-1]]
                    dx_prev = node_info['x'] - prev_info['x']
                    dy_prev = node_info['y'] - prev_info['y']
                    step_yaw = math.atan2(dy_prev, dx_prev)
                else:
                    step_yaw = node_info['yaw']

            raw = node_info.get('raw', [])
            point_info = 0
            if isinstance(raw, list) and len(raw) > 11:
                val = str(raw[11]).strip()
                point_info = int(val) if val.isdigit() else 0
            elif isinstance(raw, dict):
                point_info = int(raw.get('PointInfo', 0))

            # Fix Yaw logic based on '0', '1', '2'
            fix_yaw_val = "1"
            if isinstance(raw, list) and len(raw) > 7:
                fix_yaw_val = str(raw[7]).strip()
            elif isinstance(raw, dict):
                fix_yaw_val = str(raw.get('fix_yaw', '1')).strip()
            
            preserve_yaw = False
            if fix_yaw_val == '0':
                preserve_yaw = True
            elif fix_yaw_val == '1':
                preserve_yaw = not is_go_home

            if preserve_yaw:
                step_yaw = node_info['yaw']

            steps.append({
                'step': i,
                'node_id': nid,
                'name': node_info['name'],
                'x': node_info['x'],
                'y': node_info['y'],
                'z': node_info['z'],
                'yaw': round(step_yaw, 4),
                'step_distance': round(step_dist, 4),
                'accumulated_distance': round(accumulated, 4),
                'point_info': point_info,
                'via_path_id': edge_used.get(nid, "")
            })

        result = {
            'start_node': start_node,
            'end_node': end_node,
            'total_distance_m': round(distances[end_node], 4),
            'node_count': len(path_ids),
            'path_nodes': path_ids,
            'steps': steps
        }

        return result

    def plan_multi_segment_path(self, query_nodes: List[str], is_go_home: bool = False) -> Optional[Dict[str, Any]]:
        """
        Calculate a continuous path through a sequence of query nodes.
        Stitches individual Dijkstra paths together, avoiding duplicate boundary nodes.
        """
        if len(query_nodes) < 2:
            print("[Error] Multi-segment path requires at least 2 nodes.")
            return None

        stitched_steps = []
        total_dist = 0.0
        path_nodes = []
        step_counter = 0

        # Run Dijkstra between each consecutive pair
        for i in range(len(query_nodes) - 1):
            start_q = query_nodes[i]
            end_q = query_nodes[i+1]
            segment = self.find_shortest_path(start_q, end_q, is_go_home=is_go_home)
            if not segment:
                print(f"[Error] Failed to calculate segment from '{start_q}' to '{end_q}'")
                return None

            segment_steps = segment['steps']
            if not segment_steps:
                continue

            # Accumulate distance
            total_dist += segment['total_distance_m']

            # Stitch path nodes
            segment_nodes = segment['path_nodes']
            if i == 0:
                path_nodes.extend(segment_nodes)
            else:
                path_nodes.extend(segment_nodes[1:])

            # Stitch steps
            start_idx = 0 if i == 0 else 1
            for step in segment_steps[start_idx:]:
                cloned_step = dict(step)
                cloned_step['step'] = step_counter
                cloned_step['accumulated_distance'] = round((stitched_steps[-1]['accumulated_distance'] if stitched_steps else 0.0) + step['step_distance'], 4)
                stitched_steps.append(cloned_step)
                step_counter += 1

        if not stitched_steps:
            return None

        return {
            'start_node': stitched_steps[0]['node_id'],
            'end_node': stitched_steps[-1]['node_id'],
            'total_distance_m': round(total_dist, 4),
            'node_count': len(path_nodes),
            'path_nodes': path_nodes,
            'steps': stitched_steps
        }



def main():
    parser = argparse.ArgumentParser(description="Dijkstra Shortest Path Planner for X30 GS Simulator")
    parser.add_argument('--start', type=str, default='nofr', help="Start node ID or Name (default: 'nofr')")
    parser.add_argument('--end', type=str, default='ChargeIn-final', help="Destination node ID or Name (default: 'ChargeIn-final')")
    parser.add_argument('--nodes', type=str, default='resource/nodes.csv', help="Path to nodes CSV file")
    parser.add_argument('--paths', type=str, default='resource/paths.csv', help="Path to paths CSV file")
    parser.add_argument('--json', type=str, default='', help="Path to waypoints JSON file (optional alternative)")
    parser.add_argument('--export', type=str, default='', help="Export path result to JSON file (optional)")
    args = parser.parse_args()

    planner = DijkstraPlanner()

    # Priority 1: Load from JSON if specified and existing
    if args.json and os.path.exists(args.json):
        success = planner.load_from_json(args.json)
    # Priority 2: Load from CSV files
    else:
        nodes_path = args.nodes if os.path.exists(args.nodes) else os.path.join(os.path.dirname(__file__), "..", "resource", "nodes.csv")
        paths_path = args.paths if os.path.exists(args.paths) else os.path.join(os.path.dirname(__file__), "..", "resource", "paths.csv")
        
        # If resource/nodes.csv doesn't exist, search for any available JSON or CSV file in resource/
        if not os.path.exists(nodes_path):
            json_fallback = os.path.join(os.path.dirname(__file__), "..", "resource", "path", "final_packing_1month.json")
            if os.path.exists(json_fallback):
                success = planner.load_from_json(json_fallback)
            else:
                print(f"[Error] Neither nodes CSV nor sample JSON could be located.")
                sys.exit(1)
        else:
            success = planner.load_from_csv(nodes_path, paths_path if os.path.exists(paths_path) else None)

    if not success or not planner.nodes:
        print("[Error] Failed to build planner graph.")
        sys.exit(1)

    print(f"\n=======================================================")
    print(f"   DIJKSTRA PATH PLANNING RESULT")
    print(f"=======================================================")
    
    result = planner.find_shortest_path(args.start, args.end)

    if result:
        print(f"\n✅ Path found successfully!")
        print(f"• Start Node : {result['start_node']}")
        print(f"• Target Node: {result['end_node']}")
        print(f"• Total Dist : {result['total_distance_m']} meters")
        print(f"• Total Nodes: {result['node_count']}")
        print(f"\nRoute trajectory:")
        for idx, step in enumerate(result['steps']):
            print(f"  [{idx+1:02d}] {step['node_id']} ({step['name']}) -> Pose: ({step['x']:.2f}, {step['y']:.2f}, {step['z']:.2f}) | Leg: {step['step_distance']}m | Total: {step['accumulated_distance']}m")

        if args.export:
            with open(args.export, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=4)
            print(f"\n💾 Saved path result to: {args.export}")

    else:
        print(f"\n❌ Could not find path from '{args.start}' to '{args.end}'.")


if __name__ == '__main__':
    main()

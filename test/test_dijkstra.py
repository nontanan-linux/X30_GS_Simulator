import unittest
import sys
import os
import math
import tempfile

# Add scripts directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))

from dijkstra_planner import DijkstraPlanner

class TestDijkstraPlannerComprehensive(unittest.TestCase):
    def setUp(self):
        self.planner = DijkstraPlanner()
        self.nodes_csv = os.path.abspath(os.path.join(os.path.dirname(__file__), '../resource/nodes.csv'))
        self.paths_csv = os.path.abspath(os.path.join(os.path.dirname(__file__), '../resource/paths.csv'))
        
        # Load the graph
        self.planner.load_from_csv(self.nodes_csv, self.paths_csv if os.path.exists(self.paths_csv) else None)

    def test_tc01_graph_initialization(self):
        """TC-01: Graph Initialization"""
        self.assertGreater(len(self.planner.nodes), 0, "Nodes should be loaded into memory.")
        if os.path.exists(self.paths_csv):
            self.assertGreater(len(self.planner.graph), 0, "Graph edges should be loaded.")

    def test_tc02_shortest_path_calculation(self):
        """TC-02: Shortest Path Calculation"""
        node_ids = list(self.planner.nodes.keys())
        if len(node_ids) >= 2:
            start = node_ids[0]
            end = node_ids[-1]
            res = self.planner.find_shortest_path(start, end)
            if res:
                self.assertEqual(res['start_node'], start)
                self.assertEqual(res['end_node'], end)
                self.assertGreater(len(res['steps']), 0)

    def test_tc03_yaw_resolution_standard(self):
        """TC-03: Heading / Yaw Resolution - Basic math verification"""
        # Add two dummy nodes and connect them
        self.planner.add_node("dummy1", name="Dummy Node 1", x=0.0, y=0.0, z=0.0, yaw=0.0, raw=["dummy1", "Dummy Node 1", "station", "{0.0,0.0,0.0,0.0}", "", "0", "1st_floor", "2"])
        self.planner.add_node("dummy2", name="Dummy Node 2", x=10.0, y=10.0, z=0.0, yaw=0.0, raw=["dummy2", "Dummy Node 2", "station", "{10.0,10.0,0.0,0.0}", "", "0", "1st_floor", "2"])
        self.planner.add_edge("dummy1", "dummy2", path_id="edge-1", bidirectional=False)
        
        res = self.planner.find_shortest_path("dummy1", "dummy2")
        self.assertIsNotNone(res)
        # Expected yaw from (0,0) to (10,10) is atan2(10, 10) = pi / 4 = 0.7854
        steps = res['steps']
        self.assertAlmostEqual(steps[0]['yaw'], 0.7854, places=4)

    def test_tc04_invalid_node_input(self):
        """TC-04: Invalid Node Input"""
        res = self.planner.find_shortest_path('invalid-node-1234', 'invalid-node-5678')
        self.assertIsNone(res)

    def test_tc05_disconnected_topology(self):
        """TC-05: Disconnected Topology"""
        self.planner.add_node("isolated1", name="Isolated 1", x=0.0, y=0.0, z=0.0, yaw=0.0)
        self.planner.add_node("isolated2", name="Isolated 2", x=1.0, y=1.0, z=0.0, yaw=0.0)
        # No edge added between them
        res = self.planner.find_shortest_path("isolated1", "isolated2")
        self.assertIsNone(res)

    def test_tc06_performance_stress(self):
        """TC-06: Performance benchmark (1,000+ Nodes)"""
        benchmark_planner = DijkstraPlanner()
        # Create a large grid graph of 1000 nodes
        for i in range(1000):
            benchmark_planner.add_node(f"node_{i}", name=f"Node {i}", x=float(i), y=0.0, z=0.0, yaw=0.0)
            if i > 0:
                benchmark_planner.add_edge(f"node_{i-1}", f"node_{i}", path_id=f"edge_{i}", bidirectional=True)
        
        import time
        start_time = time.time()
        res = benchmark_planner.find_shortest_path("node_0", "node_999")
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000.0
        
        self.assertIsNotNone(res)
        self.assertLess(duration_ms, 500.0, f"Stress test path calculation took {duration_ms} ms, which is slower than 500 ms limit.")

    def test_tc07_multi_segment_planning(self):
        """TC-07: Multi-Segment Path Planning (Stitching)"""
        node_ids = list(self.planner.nodes.keys())
        if len(node_ids) >= 3:
            query = [node_ids[0], node_ids[1], node_ids[2]]
            res = self.planner.plan_multi_segment_path(query)
            if res:
                self.assertEqual(res['start_node'], query[0])
                self.assertEqual(res['end_node'], query[-1])
                self.assertGreaterEqual(res['node_count'], 2)

    def test_tc09_bidirectional_paths(self):
        """TC-09: Bidirectional Path Settings Check"""
        planner = DijkstraPlanner()
        planner.add_node("A", x=0.0, y=0.0)
        planner.add_node("B", x=1.0, y=0.0)
        
        # Test unidirectional
        planner.add_edge("A", "B", path_id="edgeAB", bidirectional=False)
        self.assertIsNotNone(planner.find_shortest_path("A", "B"))
        self.assertIsNone(planner.find_shortest_path("B", "A"))
        
        # Test bidirectional
        planner2 = DijkstraPlanner()
        planner2.add_node("A", x=0.0, y=0.0)
        planner2.add_node("B", x=1.0, y=0.0)
        planner2.add_edge("A", "B", path_id="edgeAB", bidirectional=True)
        self.assertIsNotNone(planner2.find_shortest_path("A", "B"))
        self.assertIsNotNone(planner2.find_shortest_path("B", "A"))

    def test_tc10_fix_yaw_0_rule(self):
        """TC-10: Fix Yaw 0 rule (Locked Yaw)"""
        self.planner.add_node("A", x=0.0, y=0.0, yaw=1.57, raw=["A", "Node A", "station", "{0,0,0,1.57}", "", "0", "1st_floor", "0"]) # FY=0
        self.planner.add_node("B", x=10.0, y=0.0, yaw=0.0, raw=["B", "Node B", "station", "{10,0,0,0}", "", "0", "1st_floor", "2"]) # FY=2
        self.planner.add_edge("A", "B", path_id="eAB", bidirectional=True)
        
        # Heading from A to B is mathematically 0.0 rad, but FY=0 for A should lock its yaw to 1.57 rad
        res = self.planner.find_shortest_path("A", "B")
        self.assertIsNotNone(res)
        self.assertAlmostEqual(res['steps'][0]['yaw'], 1.57, places=4)

    def test_tc11_fix_yaw_1_rule(self):
        """TC-11: Fix Yaw 1 rule (Locked in normal, free in Go Home)"""
        self.planner.add_node("A", x=0.0, y=0.0, yaw=0.5, raw=["A", "Node A", "station", "{0,0,0,0.5}", "", "0", "1st_floor", "1"]) # FY=1
        self.planner.add_node("B", x=10.0, y=10.0, yaw=0.0, raw=["B", "Node B", "station", "{10,10,0,0}", "", "0", "1st_floor", "2"]) # FY=2
        self.planner.add_edge("A", "B", path_id="eAB", bidirectional=True)
        
        # Normal mission (is_go_home = False) -> Locked to 0.5 rad
        res_normal = self.planner.find_shortest_path("A", "B", is_go_home=False)
        self.assertIsNotNone(res_normal)
        self.assertAlmostEqual(res_normal['steps'][0]['yaw'], 0.5, places=4)
        
        # Go Home mission (is_go_home = True) -> Free, recalculates heading to face B (pi/4 = 0.7854 rad)
        res_gohome = self.planner.find_shortest_path("A", "B", is_go_home=True)
        self.assertIsNotNone(res_gohome)
        self.assertAlmostEqual(res_gohome['steps'][0]['yaw'], 0.7854, places=4)

    def test_tc12_fix_yaw_2_rule(self):
        """TC-12: Fix Yaw 2 rule (Always Free)"""
        self.planner.add_node("A", x=0.0, y=0.0, yaw=1.0, raw=["A", "Node A", "station", "{0,0,0,1.0}", "", "0", "1st_floor", "2"]) # FY=2
        self.planner.add_node("B", x=0.0, y=10.0, yaw=0.0, raw=["B", "Node B", "station", "{0,10,0,0}", "", "0", "1st_floor", "2"]) # FY=2
        self.planner.add_edge("A", "B", path_id="eAB", bidirectional=True)
        
        # Normal mission (is_go_home = False) -> Recalculates heading to face B (atan2(10, 0) = pi/2 = 1.5708)
        res = self.planner.find_shortest_path("A", "B", is_go_home=False)
        self.assertIsNotNone(res)
        self.assertAlmostEqual(res['steps'][0]['yaw'], 1.5708, places=4)

    def test_tc13_parse_pose_formats(self):
        """TC-13: Parse Pose string coordinate formatting"""
        x, y, z, yaw = self.planner.parse_pose("{12.5, -45.67, 1.2, 3.1415}")
        self.assertEqual(x, 12.5)
        self.assertEqual(y, -45.67)
        self.assertEqual(z, 1.2)
        self.assertEqual(yaw, 3.1415)
        
        x2, y2, z2, yaw2 = self.planner.parse_pose("invalid_format")
        self.assertEqual(x2, 0.0)
        self.assertEqual(y2, 0.0)
        self.assertEqual(z2, 0.0)
        self.assertEqual(yaw2, 0.0)

    def test_tc14_resolve_node_id_or_name(self):
        """TC-14: Resolve Node ID or Name matching"""
        self.planner.add_node("via-12", name="First Waypoint", x=0.0, y=0.0)
        self.assertEqual(self.planner.resolve_node_id("via-12"), "via-12")
        self.assertEqual(self.planner.resolve_node_id("First Waypoint"), "via-12")
        self.assertEqual(self.planner.resolve_node_id("  first waypoint  "), "via-12")
        self.assertIsNone(self.planner.resolve_node_id("Unknown Node"))

    def test_tc15_consecutive_identical_nodes(self):
        """TC-15: Consecutive identical query nodes in multi-segment path"""
        self.planner.add_node("A", x=0.0, y=0.0)
        self.planner.add_node("B", x=1.0, y=0.0)
        self.planner.add_edge("A", "B", path_id="eAB", bidirectional=True)
        
        query = ["A", "A", "B"]
        res = self.planner.plan_multi_segment_path(query)
        self.assertIsNotNone(res)
        self.assertEqual(res['start_node'], "A")
        self.assertEqual(res['end_node'], "B")
        self.assertEqual(res['node_count'], 2)

    def test_tc16_load_from_json(self):
        """TC-16: Load graph definitions from JSON format alternative"""
        import json
        temp_data = [
            {
                "Node_info": "nodeA",
                "Name": "Point A",
                "Pose": "{10.0, 20.0, 0.0, 0.5}",
                "fix_yaw": "1"
            },
            {
                "Node_info": "nodeB",
                "Name": "Point B",
                "Pose": "{20.0, 30.0, 0.0, 1.0}",
                "fix_yaw": "2"
            }
        ]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(temp_data, f)
            temp_path = f.name
            
        try:
            planner = DijkstraPlanner()
            planner.load_from_json(temp_path)
            self.assertIn("nodeA", planner.nodes)
            self.assertIn("nodeB", planner.nodes)
            self.assertEqual(planner.nodes["nodeA"]["x"], 10.0)
            self.assertEqual(planner.nodes["nodeB"]["yaw"], 1.0)
        finally:
            os.remove(temp_path)

    def test_tc17_empty_or_single_node_query(self):
        """TC-17: Empty or single node query in Multi-segment Calculation"""
        res_empty = self.planner.plan_multi_segment_path([])
        self.assertIsNone(res_empty)
        
        res_single = self.planner.plan_multi_segment_path(["via-84"])
        self.assertIsNone(res_single)

if __name__ == '__main__':
    unittest.main()

import open3d as o3d
import numpy as np
import os
import argparse
import matplotlib.pyplot as plt

class PCDToMeshConverter:
    """
    Expert tool for converting PCD to Mesh optimized for CARLA and ROS.
    Includes simplification and multi-format export.
    """

    def __init__(self, input_path):
        self.input_path = input_path
        self.pcd = None
        self.mesh = None
        self.densities = None

    def load_pcd(self):
        """Loads the .pcd file."""
        print(f"[1/6] Loading PCD: {self.input_path}")
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"Input file not found: {self.input_path}")
        self.pcd = o3d.io.read_point_cloud(self.input_path)
        print(f"      Loaded {len(self.pcd.points)} points.")
        return self.pcd

    def pre_process(self, nb_neighbors=20, std_ratio=2.0):
        """Statistical outlier removal and normal estimation."""
        print("[2/6] Pre-processing...")
        cl, ind = self.pcd.remove_statistical_outlier(nb_neighbors=nb_neighbors, std_ratio=std_ratio)
        self.pcd = self.pcd.select_by_index(ind)
        self.pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
        self.pcd.orient_normals_towards_camera_location(camera_location=np.array([0., 0., 0.]))
        return self.pcd

    def poisson_reconstruction(self, depth=9):
        """Surface reconstruction using Poisson algorithm."""
        print(f"[3/6] Surface Reconstruction (Poisson depth={depth})...")
        self.mesh, self.densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            self.pcd, depth=depth
        )
        return self.mesh

    def clean_and_color(self, percentile=0.1):
        """Removes low-density artifacts and colors by height."""
        print("[4/6] Cleaning and Coloring...")
        
        # Remove low-density noise
        vertices_to_remove = self.densities < np.quantile(self.densities, percentile)
        self.mesh.remove_vertices_by_mask(vertices_to_remove)
        
        # Standard cleaning
        self.mesh.remove_unreferenced_vertices()
        self.mesh.remove_degenerate_triangles()
        
        # Coloring
        vertices = np.asarray(self.mesh.vertices)
        if len(vertices) > 0:
            z_values = vertices[:, 2]
            z_norm = (z_values - np.min(z_values)) / (np.max(z_values) - np.min(z_values) + 1e-7)
            cmap = plt.get_cmap("jet")
            self.mesh.vertex_colors = o3d.utility.Vector3dVector(cmap(z_norm)[:, :3])
        
        self.mesh.compute_vertex_normals()
        print(f"      Base mesh has {len(self.mesh.vertices)} vertices.")
        return self.mesh

    def simplify_mesh(self, target_triangles=50000):
        """Simplifies the mesh for simulation performance (CARLA/ROS)."""
        if len(self.mesh.triangles) > target_triangles:
            print(f"      Simplifying mesh to {target_triangles} triangles for performance...")
            self.mesh = self.mesh.simplify_quadric_decimation(target_number_of_triangles=target_triangles)
            self.mesh.compute_vertex_normals()
            print(f"      Simplified to {len(self.mesh.vertices)} vertices.")
        return self.mesh

    def export_for_sim(self, base_name):
        """Exports in .ply (ROS) and .obj (CARLA) formats."""
        print(f"[5/6] Exporting for Sim...")
        # .ply is best for ROS/RViz (native vertex colors)
        o3d.io.write_triangle_mesh(f"{base_name}.ply", self.mesh)
        # .obj is standard for CARLA/Unreal
        o3d.io.write_triangle_mesh(f"{base_name}.obj", self.mesh)
        print(f"      Exported {base_name}.ply and {base_name}.obj")

    def visualize(self):
        """Comparison visualization."""
        print("[6/6] Visualizing...")
        mesh_copy = o3d.geometry.TriangleMesh(self.mesh)
        bbox = self.pcd.get_axis_aligned_bounding_box()
        mesh_copy.translate([(bbox.get_max_extent() * 1.2), 0, 0])
        o3d.visualization.draw_geometries([self.pcd, mesh_copy], window_name="Sim-Ready Mesh")

def main():
    parser = argparse.ArgumentParser(description="PCD to Sim-Ready Mesh (CARLA/ROS)")
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, default="sim_mesh")
    parser.add_argument("--depth", type=int, default=9)
    parser.add_argument("--target_tri", type=int, default=50000, help="Target triangle count for sim")
    parser.add_argument("--no-viz", action="store_true")
    
    args = parser.parse_args()

    converter = PCDToMeshConverter(args.input)
    try:
        converter.load_pcd()
        converter.pre_process()
        converter.poisson_reconstruction(depth=args.depth)
        converter.clean_and_color()
        converter.simplify_mesh(target_triangles=args.target_tri)
        converter.export_for_sim(args.output)
        if not args.no_viz:
            converter.visualize()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

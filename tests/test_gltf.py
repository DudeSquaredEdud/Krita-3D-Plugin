#!/usr/bin/env python3


import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pose_engine.gltf.loader import GLBLoader
from pose_engine.gltf.builder import build_skeleton_from_gltf, build_mesh_from_gltf


def test_glb_loader():
    
    print("\n=== Testing GLB Loader ===")
    
    test_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "krita_3d_pose", "RIGLADY.glb")
    
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        print("Skipping GLB loader test")
        return
    
    loader = GLBLoader()
    data = loader.load(test_file)
    
    print(f"Loaded GLB file: {test_file}")
    print(f"Number of nodes: {len(data.nodes)}")
    print(f"Number of skins: {len(data.skins)}")
    print(f"Number of meshes: {len(data.meshes)}")
    print(f"Number of accessors: {len(data.accessors)}")
    print(f"Number of buffer views: {len(data.buffer_views)}")
    
    assert len(data.nodes) > 0, "No nodes found"
    assert len(data.skins) > 0, "No skins found"
    assert len(data.meshes) > 0, "No meshes found"
    
    print(" GLB loader test passed!")


def test_build_skeleton():
    
    print("\n=== Testing Skeleton Building ===")
    
    test_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "krita_3d_pose", "RIGLADY.glb")
    
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        print("Skipping skeleton building test")
        return
    
    loader = GLBLoader()
    data = loader.load(test_file)
    
    skeleton, bone_mapping = build_skeleton_from_gltf(data, loader=loader)
    
    print(f"Skeleton built with {len(skeleton)} bones")
    
    print("\nBone hierarchy:")
    skeleton.print_hierarchy()
    
    for bone in skeleton:
        pos = bone.get_world_position()
        assert isinstance(pos.x, float), f"Bone {bone.name} has invalid position"
    
    print(" Skeleton building test passed!")


def test_build_mesh():
    
    print("\n=== Testing Mesh Building ===")
    
    test_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "krita_3d_pose", "RIGLADY.glb")
    
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        print("Skipping mesh building test")
        return
    
    loader = GLBLoader()
    data = loader.load(test_file)
    
    skeleton, bone_mapping = build_skeleton_from_gltf(data, loader=loader)

    mesh_data = build_mesh_from_gltf(data, bone_mapping=bone_mapping, loader=loader)
    
    print(f"Mesh built with {len(mesh_data.positions)} vertices")
    print(f"Mesh has {len(mesh_data.indices)} indices")
    print(f"Mesh has {len(mesh_data.normals)} normals")
    
    if mesh_data.skinning_data:
        print(f"Mesh has skinning data for {mesh_data.skinning_data.get_vertex_count()} vertices")
    
    assert len(mesh_data.positions) > 0, "No positions found"
    assert len(mesh_data.indices) > 0, "No indices found"
    
    print(" Mesh building test passed!")


def test_node_parsing():
    
    print("\n=== Testing Node Parsing ===")
    
    test_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                             "krita_3d_pose", "RIGLADY.glb")
    
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        print("Skipping node parsing test")
        return
    
    loader = GLBLoader()
    data = loader.load(test_file)
    
    for i, node in enumerate(data.nodes[:5]):
        print(f"Node {i}: {node.name}")
        print(f"  Translation: {node.translation}")
        print(f"  Rotation: {node.rotation}")
        print(f"  Scale: {node.scale}")
        print(f"  Children: {node.children}")
    
    print(" Node parsing test passed!")


def run_all_tests():
    
    print("=" * 60)
    print("GLTF LOADER TESTS")
    print("=" * 60)
    
    test_glb_loader()
    test_node_parsing()
    test_build_skeleton()
    test_build_mesh()
    
    print("\n" + "=" * 60)
    print("ALL GLTF TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()

#!/usr/bin/env python3


import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pose_engine.vec3 import Vec3
from pose_engine.quat import Quat
from pose_engine.mat4 import Mat4
from pose_engine.transform import Transform
from pose_engine.bone import Bone
from pose_engine.skeleton import Skeleton
from pose_engine.skinning import VertexSkinning, SkinningData, apply_skinning, compute_bone_matrices_from_skeleton


def test_bone_creation():
    
    print("\n=== Testing Bone Creation ===")
    
    bone = Bone("test_bone", 0)
    assert bone.name == "test_bone"
    assert bone.index == 0
    assert bone.parent is None
    assert len(bone.children) == 0
    
    print(f"Created bone: {bone}")
    print(" Bone creation test passed!")


def test_bone_hierarchy():
    
    print("\n=== Testing Bone Hierarchy ===")
    
    root = Bone("root", 0)
    child1 = Bone("child1", 1)
    child2 = Bone("child2", 2)
    grandchild = Bone("grandchild", 3)
    
    root.add_child(child1)
    root.add_child(child2)
    child1.add_child(grandchild)
    
    assert child1.parent is root
    assert child2.parent is root
    assert grandchild.parent is child1
    assert grandchild in child1.children
    assert child1 in root.children
    assert child2 in root.children
    
    assert root.get_depth() == 0
    assert child1.get_depth() == 1
    assert grandchild.get_depth() == 2
    
    assert root.is_ancestor_of(grandchild)
    assert child1.is_ancestor_of(grandchild)
    assert not child2.is_ancestor_of(grandchild)
    
    print(" Bone hierarchy test passed!")


def test_bone_transforms():
    
    print("\n=== Testing Bone Transforms ===")
    
    root = Bone("root", 0)
    root.bind_transform.position = Vec3(0, 0, 0)
    
    child = Bone("child", 1)
    child.bind_transform.position = Vec3(0, 2, 0)  
    
    root.add_child(child)
    
    root_pos = root.get_world_position()
    child_pos = child.get_world_position()
    
    print(f"Root world position: {root_pos}")
    print(f"Child world position: {child_pos}")
    
    assert abs(root_pos.y - 0) < 0.001
    assert abs(child_pos.y - 2) < 0.001
    
    root.set_pose_rotation(Quat.from_axis_angle_degrees(Vec3(0, 0, 1), 90))

    child_pos_rotated = child.get_world_position()
    print(f"Child position after root 90° Z rotation: {child_pos_rotated}")
    
    
    assert abs(child_pos_rotated.x - (-2)) < 0.01
    assert abs(child_pos_rotated.y - 0) < 0.01
    
    print(" Bone transform test passed!")


def test_skeleton():
    
    print("\n=== Testing Skeleton ===")
    
    skeleton = Skeleton()
    
    root = skeleton.add_bone("root")
    hip = skeleton.add_bone("hip", parent_index=0)
    spine = skeleton.add_bone("spine", parent_index=1)
    
    assert len(skeleton) == 3
    assert skeleton.get_bone("root") is root
    assert skeleton.get_bone_index("spine") == 2
    
    roots = skeleton.get_root_bones()
    assert len(roots) == 1
    assert roots[0] is root
    
    leaves = skeleton.get_leaf_bones()
    assert len(leaves) == 1
    assert leaves[0] is spine
    
    chain = skeleton.get_bone_chain("spine", "root")
    assert len(chain) == 3
    assert chain[0] is spine
    assert chain[2] is root
    
    print(f"Skeleton: {skeleton}")
    print(" Skeleton test passed!")


def test_skeleton_pose():
    
    print("\n=== Testing Skeleton Pose ===")
    
    skeleton = Skeleton()
    
    shoulder = skeleton.add_bone("shoulder")
    shoulder.bind_transform.position = Vec3(0, 0, 0)
    
    upper_arm = skeleton.add_bone("upper_arm", parent_index=0)
    upper_arm.bind_transform.position = Vec3(1, 0, 0)  
    
    forearm = skeleton.add_bone("forearm", parent_index=1)
    forearm.bind_transform.position = Vec3(1, 0, 0)  
    
    hand = skeleton.add_bone("hand", parent_index=2)
    hand.bind_transform.position = Vec3(0.5, 0, 0)  
    
    skeleton.update_all_transforms()
    hand_pos = hand.get_world_position()
    print(f"Hand initial position: {hand_pos}")
    
    upper_arm.set_pose_rotation(Quat.from_axis_angle_degrees(Vec3(0, 0, 1), 90))
    skeleton.update_all_transforms()
    
    hand_pos_rotated = hand.get_world_position()
    print(f"Hand position after upper arm rotation: {hand_pos_rotated}")
    
    skeleton.reset_pose()
    skeleton.update_all_transforms()
    hand_pos_reset = hand.get_world_position()
    print(f"Hand position after reset: {hand_pos_reset}")
    
    assert abs(hand_pos.x - hand_pos_reset.x) < 0.001
    assert abs(hand_pos.y - hand_pos_reset.y) < 0.001
    assert abs(hand_pos.z - hand_pos_reset.z) < 0.001
    
    print(" Skeleton pose test passed!")


def test_vertex_skinning():
    
    print("\n=== Testing Vertex Skinning ===")
    
    skinning = VertexSkinning(max_influences=4)
    skinning.add_influence(0, 0.7)
    skinning.add_influence(1, 0.3)
    skinning.normalize_weights()
    
    influences = skinning.get_influences()
    print(f"Vertex influences: {influences}")
    
    total_weight = sum(w for _, w in influences)
    assert abs(total_weight - 1.0) < 0.001
    
    print(" Vertex skinning test passed!")


def test_skinning_data():
    
    print("\n=== Testing Skinning Data ===")
    
    skeleton = Skeleton()

    bone0 = skeleton.add_bone("bone0")
    bone0.bind_transform.position = Vec3(0, 0, 0)
    bone0.inverse_bind_matrix = Mat4.identity()
    
    bone1 = skeleton.add_bone("bone1", parent_index=0)
    bone1.bind_transform.position = Vec3(0, 0, 0)  
    bone1.inverse_bind_matrix = Mat4.identity()
    
    skinning_data = SkinningData(vertex_count=2)

    v0_skinning = skinning_data.get_vertex_skinning(0)
    v0_skinning.add_influence(0, 1.0)
    v0_skinning.normalize_weights()
    
    v1_skinning = skinning_data.get_vertex_skinning(1)
    v1_skinning.add_influence(0, 0.5)
    v1_skinning.add_influence(1, 0.5)
    v1_skinning.normalize_weights()
    
    compute_bone_matrices_from_skeleton(skeleton, skinning_data)

    positions = [Vec3(0, 0, 0), Vec3(0.5, 0, 0)]
    normals = [Vec3(0, 1, 0), Vec3(0, 1, 0)]
    
    skinned_positions, skinned_normals = apply_skinning(positions, normals, skinning_data)
    
    print(f"Original positions: {[str(p) for p in positions]}")
    print(f"Skinned positions: {[str(p) for p in skinned_positions]}")
    
    for i, (orig, skinned) in enumerate(zip(positions, skinned_positions)):
        assert abs(orig.x - skinned.x) < 0.001, f"Vertex {i} X mismatch"
        assert abs(orig.y - skinned.y) < 0.001, f"Vertex {i} Y mismatch"
        assert abs(orig.z - skinned.z) < 0.001, f"Vertex {i} Z mismatch"
    
    print(" Skinning data test passed!")


def run_all_tests():
    
    print("=" * 60)
    print("SKELETON SYSTEM TESTS")
    print("=" * 60)
    
    test_bone_creation()
    test_bone_hierarchy()
    test_bone_transforms()
    test_skeleton()
    test_skeleton_pose()
    test_vertex_skinning()
    test_skinning_data()
    
    print("\n" + "=" * 60)
    print("ALL SKELETON TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()

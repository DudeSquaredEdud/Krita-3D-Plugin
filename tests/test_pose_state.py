#!/usr/bin/env python3


import pytest
import json
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pose_engine.pose_state import BonePose, PoseSnapshot, UndoRedoStack, PoseSerializer
from pose_engine.quat import Quat
from pose_engine.vec3 import Vec3
from pose_engine.skeleton import Skeleton


class TestBonePose:
    

    def test_bone_pose_creation(self):
        
        pose = BonePose(
            rotation=Quat(1, 0, 0, 0),
            position=Vec3(0, 0, 0),
            scale=Vec3(1, 1, 1)
        )
        
        assert pose.rotation.w == 1
        assert pose.position.x == 0
        assert pose.scale.x == 1

    def test_bone_pose_defaults(self):
        
        pose = BonePose()
        
        assert pose.rotation.w == 1
        assert pose.rotation.x == 0
        assert pose.rotation.y == 0
        assert pose.rotation.z == 0
        
        assert pose.position.x == 0
        assert pose.position.y == 0
        assert pose.position.z == 0
        
        assert pose.scale.x == 1
        assert pose.scale.y == 1
        assert pose.scale.z == 1

    def test_bone_pose_to_dict(self):
        
        pose = BonePose(
            rotation=Quat(0.707, 0, 0.707, 0),
            position=Vec3(1, 2, 3),
            scale=Vec3(2, 2, 2)
        )
        
        data = pose.to_dict()
        
        assert 'rotation' in data
        assert 'position' in data
        assert 'scale' in data
        assert len(data['rotation']) == 4
        assert len(data['position']) == 3
        assert len(data['scale']) == 3

    def test_bone_pose_from_dict(self):
        
        data = {
            'rotation': [0.707, 0, 0.707, 0],
            'position': [1, 2, 3],
            'scale': [2, 2, 2]
        }
        
        pose = BonePose.from_dict(data)
        
        assert pose.rotation.w == 0.707
        assert pose.rotation.x == 0
        assert pose.rotation.y == 0.707
        assert pose.rotation.z == 0
        assert pose.position.x == 1
        assert pose.position.y == 2
        assert pose.position.z == 3
        assert pose.scale.x == 2

    def test_bone_pose_from_dict_defaults(self):
        
        data = {}
        
        pose = BonePose.from_dict(data)
        
        assert pose.rotation.w == 1
        assert pose.position.x == 0
        assert pose.scale.x == 1

    def test_bone_pose_roundtrip(self):
        
        original = BonePose(
            rotation=Quat(0.5, 0.5, 0.5, 0.5),
            position=Vec3(5, 10, 15),
            scale=Vec3(1, 2, 3)
        )
        
        data = original.to_dict()
        restored = BonePose.from_dict(data)
        
        assert abs(restored.rotation.w - original.rotation.w) < 0.001
        assert abs(restored.rotation.x - original.rotation.x) < 0.001
        assert restored.position.x == original.position.x
        assert restored.scale.x == original.scale.x


class TestPoseSnapshot:
    

    def test_pose_snapshot_creation(self):
        
        bones = {
            'root': BonePose(),
            'spine': BonePose(rotation=Quat.from_axis_angle(Vec3.UP, 0.5))
        }
        
        snapshot = PoseSnapshot(bones=bones, name="Test Pose")
        
        assert snapshot.name == "Test Pose"
        assert len(snapshot.bones) == 2
        assert 'root' in snapshot.bones
        assert 'spine' in snapshot.bones

    def test_pose_snapshot_defaults(self):
        
        snapshot = PoseSnapshot()
        
        assert snapshot.bones == {}
        assert snapshot.name == ""
        assert snapshot.timestamp == 0.0

    def test_pose_snapshot_to_dict(self):
        
        bones = {
            'root': BonePose(rotation=Quat.identity(), position=Vec3(0, 0, 0)),
            'head': BonePose(rotation=Quat(0.707, 0, 0, 0.707), position=Vec3(0, 1, 0))
        }
        
        snapshot = PoseSnapshot(bones=bones, name="Serialize Test", timestamp=12345.0)
        data = snapshot.to_dict()
        
        assert data['name'] == "Serialize Test"
        assert data['timestamp'] == 12345.0
        assert 'bones' in data
        assert 'root' in data['bones']
        assert 'head' in data['bones']

    def test_pose_snapshot_from_dict(self):
        
        data = {
            'name': 'Deserialize Test',
            'timestamp': 67890.0,
            'bones': {
                'root': {
                    'rotation': [1, 0, 0, 0],
                    'position': [0, 0, 0],
                    'scale': [1, 1, 1]
                },
                'spine': {
                    'rotation': [0.707, 0, 0.707, 0],
                    'position': [0, 1, 0],
                    'scale': [1, 1, 1]
                }
            }
        }
        
        snapshot = PoseSnapshot.from_dict(data)
        
        assert snapshot.name == 'Deserialize Test'
        assert snapshot.timestamp == 67890.0
        assert len(snapshot.bones) == 2
        assert 'root' in snapshot.bones
        assert 'spine' in snapshot.bones

    def test_pose_snapshot_get_bone_pose(self):
        
        bones = {
            'root': BonePose(rotation=Quat.identity()),
            'head': BonePose(rotation=Quat(0.707, 0, 0, 0.707))
        }
        
        snapshot = PoseSnapshot(bones=bones)
        
        root_pose = snapshot.get_bone_pose('root')
        assert root_pose is not None
        assert root_pose.rotation.w == 1
        
        missing = snapshot.get_bone_pose('nonexistent')
        assert missing is None

    def test_pose_snapshot_roundtrip(self):
        
        bones = {
            'root': BonePose(rotation=Quat(0.5, 0.5, 0.5, 0.5)),
            'spine': BonePose(position=Vec3(1, 2, 3)),
            'head': BonePose(scale=Vec3(2, 1, 1))
        }
        
        original = PoseSnapshot(bones=bones, name="Roundtrip Test", timestamp=999.0)
        data = original.to_dict()
        restored = PoseSnapshot.from_dict(data)
        
        assert restored.name == original.name
        assert restored.timestamp == original.timestamp
        assert len(restored.bones) == len(original.bones)
        
        for bone_name in original.bones:
            orig_pose = original.bones[bone_name]
            rest_pose = restored.bones[bone_name]
            
            assert abs(orig_pose.rotation.w - rest_pose.rotation.w) < 0.001


class TestPoseSnapshotCaptureApply:
    

    def test_capture_from_skeleton(self, sample_skeleton):
        
        snapshot = PoseSnapshot.capture_from_skeleton(sample_skeleton, "Captured Pose")
        
        assert snapshot.name == "Captured Pose"
        assert len(snapshot.bones) == len(sample_skeleton)
        assert 'root' in snapshot.bones
        assert 'spine' in snapshot.bones

    def test_apply_to_skeleton(self, sample_skeleton):
        
        original = PoseSnapshot.capture_from_skeleton(sample_skeleton)
        
        root_bone = sample_skeleton.get_bone('root')
        root_bone.set_pose_rotation(Quat.from_axis_angle(Vec3.UP, 0.5))
        sample_skeleton.update_all_transforms()
        
        original.apply_to_skeleton(sample_skeleton)
        
        root_bone = sample_skeleton.get_bone('root')
        assert abs(root_bone.pose_transform.rotation.w - 1) < 0.1

    def test_capture_apply_roundtrip(self, sample_skeleton):
        
        spine = sample_skeleton.get_bone('spine')
        spine.set_pose_rotation(Quat.from_axis_angle(Vec3(1, 0, 0), 0.3))
        spine.set_pose_position(Vec3(0.5, 1.5, 0.2))
        sample_skeleton.update_all_transforms()
        
        modified_snapshot = PoseSnapshot.capture_from_skeleton(sample_skeleton, "Modified")
        
        for bone in sample_skeleton:
            bone.set_pose_rotation(Quat.identity())
            bone.set_pose_position(Vec3(0, 0, 0))
        sample_skeleton.update_all_transforms()
        
        modified_snapshot.apply_to_skeleton(sample_skeleton)
        
        spine = sample_skeleton.get_bone('spine')
        assert abs(spine.pose_transform.rotation.x - 0.147) < 0.01  


class TestUndoRedoStack:
    

    def test_undo_redo_stack_creation(self):
        
        stack = UndoRedoStack(max_history=50)
        
        assert stack.can_undo == False
        assert stack.can_redo == False
        assert stack.undo_count == 0
        assert stack.redo_count == 0

    def test_push_state(self, sample_skeleton):
        
        stack = UndoRedoStack()
        
        stack.push_state(sample_skeleton, "Initial State")
        
        assert stack.undo_count == 0
        assert stack._current_snapshot is not None

    def test_undo(self, sample_skeleton):
        
        stack = UndoRedoStack()
        
        stack.push_state(sample_skeleton, "State 1")
        
        root = sample_skeleton.get_bone('root')
        root.set_pose_rotation(Quat.from_axis_angle(Vec3.UP, 0.5))
        sample_skeleton.update_all_transforms()
        
        stack.push_state(sample_skeleton, "State 2")
        
        assert stack.can_undo == True
        
        result = stack.undo(sample_skeleton)
        
        assert result is not None
        assert stack.can_redo == True

    def test_redo(self, sample_skeleton):
        
        stack = UndoRedoStack()
        
        stack.push_state(sample_skeleton, "State 1")
        
        root = sample_skeleton.get_bone('root')
        root.set_pose_rotation(Quat.from_axis_angle(Vec3.UP, 0.5))
        sample_skeleton.update_all_transforms()
        
        stack.push_state(sample_skeleton, "State 2")
        
        stack.undo(sample_skeleton)
        
        assert stack.can_redo == True
        result = stack.redo(sample_skeleton)
        
        assert result is not None
        assert stack.can_redo == False

    def test_undo_redo_multiple(self, sample_skeleton):
        
        stack = UndoRedoStack(max_history=10)
        
        for i in range(5):
            root = sample_skeleton.get_bone('root')
            root.set_pose_rotation(Quat.from_axis_angle(Vec3.UP, i * 0.1))
            sample_skeleton.update_all_transforms()
            stack.push_state(sample_skeleton, f"State {i}")
        
        for i in range(3):
            assert stack.can_undo
            stack.undo(sample_skeleton)
        
        assert stack.undo_count == 1
        assert stack.redo_count == 3
        
        for i in range(2):
            assert stack.can_redo
            stack.redo(sample_skeleton)
        
        assert stack.redo_count == 1

    def test_push_clears_redo(self, sample_skeleton):
        
        stack = UndoRedoStack()
        
        stack.push_state(sample_skeleton, "State 1")
        stack.push_state(sample_skeleton, "State 2")
        
        stack.undo(sample_skeleton)
        assert stack.can_redo == True
        
        stack.push_state(sample_skeleton, "State 3")
        
        assert stack.can_redo == False

    def test_max_history(self, sample_skeleton):
        
        stack = UndoRedoStack(max_history=3)
        
        for i in range(5):
            root = sample_skeleton.get_bone('root')
            root.set_pose_rotation(Quat.from_axis_angle(Vec3.UP, i * 0.1))
            sample_skeleton.update_all_transforms()
            stack.push_state(sample_skeleton, f"State {i}")
        
        assert stack.undo_count <= 3

    def test_clear(self, sample_skeleton):
        
        stack = UndoRedoStack()
        
        stack.push_state(sample_skeleton, "State 1")
        stack.push_state(sample_skeleton, "State 2")
        stack.undo(sample_skeleton)
        
        stack.clear()
        
        assert stack.can_undo == False
        assert stack.can_redo == False
        assert stack.undo_count == 0
        assert stack.redo_count == 0

    def test_initialize(self, sample_skeleton):
        
        stack = UndoRedoStack()
        
        stack.initialize(sample_skeleton)
        
        assert stack._current_snapshot is not None
        assert stack.can_undo == False
        assert stack.can_redo == False


class TestPoseSerializer:
    

    def test_save_pose(self, sample_skeleton, tmp_path):
        
        filepath = str(tmp_path / "test_pose.json")
        
        result = PoseSerializer.save_pose(filepath, sample_skeleton, "Test Pose")
        
        assert result == True
        assert os.path.exists(filepath)
        
        with open(filepath) as f:
            data = json.load(f)
        
        assert data['name'] == "Test Pose"
        assert 'bones' in data

    def test_load_pose(self, sample_skeleton, tmp_path):
        
        filepath = str(tmp_path / "test_pose.json")
        
        PoseSerializer.save_pose(filepath, sample_skeleton, "Original")
        
        root = sample_skeleton.get_bone('root')
        original_rotation = root.pose_transform.rotation
        root.set_pose_rotation(Quat.from_axis_angle(Vec3.UP, 1.0))
        sample_skeleton.update_all_transforms()
        
        result = PoseSerializer.load_pose(filepath, sample_skeleton)
        
        assert result is not None
        assert isinstance(result, PoseSnapshot)
        
        root = sample_skeleton.get_bone('root')
        assert abs(root.pose_transform.rotation.w - original_rotation.w) < 0.01

    def test_load_pose_data(self, sample_skeleton, tmp_path):
        
        filepath = str(tmp_path / "test_pose.json")
        
        PoseSerializer.save_pose(filepath, sample_skeleton, "Data Test")
        
        snapshot = PoseSerializer.load_pose_data(filepath)
        
        assert snapshot is not None
        assert snapshot.name == "Data Test"

    def test_get_pose_info(self, sample_skeleton, tmp_path):
        
        filepath = str(tmp_path / "test_pose.json")
        
        PoseSerializer.save_pose(filepath, sample_skeleton, "Info Test")
        
        info = PoseSerializer.get_pose_info(filepath)
        
        assert info is not None
        assert info['name'] == "Info Test"
        assert 'timestamp' in info
        assert 'bone_count' in info
        assert info['bone_count'] == len(sample_skeleton)

    def test_load_nonexistent_file(self, tmp_path):
        
        result = PoseSerializer.load_pose_data(str(tmp_path / "nonexistent.json"))

        assert result is None

    def test_load_pose_nonexistent_file_returns_none(self, sample_skeleton, tmp_path):
        
        result = PoseSerializer.load_pose(str(tmp_path / "nonexistent.json"), sample_skeleton)

        assert result is None
        assert result is not False

    def test_get_info_nonexistent_file(self, tmp_path):
        
        result = PoseSerializer.get_pose_info(str(tmp_path / "nonexistent.json"))
        
        assert result is None

    def test_save_load_roundtrip(self, sample_skeleton, tmp_path):
        
        filepath = str(tmp_path / "roundtrip.json")
        
        spine = sample_skeleton.get_bone('spine')
        spine.set_pose_rotation(Quat.from_axis_angle(Vec3(1, 0, 0), 0.5))
        spine.set_pose_position(Vec3(1, 2, 3))
        sample_skeleton.update_all_transforms()
        
        PoseSerializer.save_pose(filepath, sample_skeleton, "Roundtrip")
        
        for bone in sample_skeleton:
            bone.set_pose_rotation(Quat.identity())
            bone.set_pose_position(Vec3(0, 0, 0))
        sample_skeleton.update_all_transforms()
        
        PoseSerializer.load_pose(filepath, sample_skeleton)
        
        spine = sample_skeleton.get_bone('spine')
        assert abs(spine.pose_transform.position.x - 1) < 0.01


class TestPoseStateIntegration:
    

    def test_full_undo_redo_workflow(self, sample_skeleton):
        
        stack = UndoRedoStack(max_history=20)
        
        stack.initialize(sample_skeleton)
        
        for i in range(5):
            root = sample_skeleton.get_bone('root')
            root.set_pose_rotation(Quat.from_axis_angle(Vec3.UP, i * 0.2))
            sample_skeleton.update_all_transforms()
            stack.push_state(sample_skeleton, f"Change {i}")
        
        while stack.can_undo:
            stack.undo(sample_skeleton)
        
        root = sample_skeleton.get_bone('root')
        assert abs(root.pose_transform.rotation.w - 1) < 0.1
        
        while stack.can_redo:
            stack.redo(sample_skeleton)
        
        
        root = sample_skeleton.get_bone('root')
        
        assert root.pose_transform.rotation.w < 1.0

    def test_pose_file_workflow(self, sample_skeleton, tmp_path):
        
        spine = sample_skeleton.get_bone('spine')
        spine.set_pose_rotation(Quat.from_axis_angle(Vec3(1, 0, 0), 0.3))
        sample_skeleton.update_all_transforms()
        
        filepath = str(tmp_path / "workflow_pose.json")
        PoseSerializer.save_pose(filepath, sample_skeleton, "Workflow Test")
        
        info = PoseSerializer.get_pose_info(filepath)
        assert info['name'] == "Workflow Test"
        
        for bone in sample_skeleton:
            bone.set_pose_rotation(Quat.identity())
        sample_skeleton.update_all_transforms()
        
        snapshot = PoseSerializer.load_pose(filepath, sample_skeleton)
        assert snapshot is not None
        
        spine = sample_skeleton.get_bone('spine')
        assert abs(spine.pose_transform.rotation.x - 0.147) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

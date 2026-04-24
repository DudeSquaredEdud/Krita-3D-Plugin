

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_vec3():

    from pose_engine.vec3 import Vec3
    return Vec3(1.0, 2.0, 3.0)


@pytest.fixture
def sample_quat():

    from pose_engine.quat import Quat
    return Quat(1, 0, 0, 0)


@pytest.fixture
def sample_mat4():

    from pose_engine.mat4 import Mat4
    return Mat4()


@pytest.fixture
def sample_transform():

    from pose_engine.transform import Transform
    return Transform()


@pytest.fixture
def sample_bone():

    from pose_engine.bone import Bone
    bone = Bone("test_bone", 0)
    bone.bind_position = bone.bind_transform.position
    return bone


@pytest.fixture
def sample_skeleton():

    from pose_engine.skeleton import Skeleton
    from pose_engine.vec3 import Vec3
    
    skeleton = Skeleton()
    
    root = skeleton.add_bone("root", parent_index=-1)
    root.bind_transform.set_position(0, 0, 0)
    
    spine = skeleton.add_bone("spine", parent_index=0)
    spine.bind_transform.set_position(0, 1, 0)
    
    head = skeleton.add_bone("head", parent_index=1)
    head.bind_transform.set_position(0, 2, 0)
    
    left_arm = skeleton.add_bone("left_arm", parent_index=0)
    left_arm.bind_transform.set_position(-1, 1, 0)
    
    left_hand = skeleton.add_bone("left_hand", parent_index=3)
    left_hand.bind_transform.set_position(-1, 2, 0)
    
    skeleton.update_all_transforms()
    
    return skeleton


@pytest.fixture
def simple_skeleton():

    from pose_engine.skeleton import Skeleton
    
    skeleton = Skeleton()
    
    root = skeleton.add_bone("root", parent_index=-1)
    root.bind_transform.set_position(0, 0, 0)
    
    child = skeleton.add_bone("child", parent_index=0)
    child.bind_transform.set_position(0, 1, 0)
    
    skeleton.update_all_transforms()
    
    return skeleton


@pytest.fixture
def sample_camera():

    from pose_engine.camera import Camera
    return Camera()


@pytest.fixture
def head_look_camera():

    from pose_engine.camera import Camera
    camera = Camera()
    camera.head_look_mode = True
    return camera


@pytest.fixture
def sample_settings():

    from pose_engine.settings import PluginSettings
    return PluginSettings()


@pytest.fixture
def temp_settings_file(tmp_path):

    import json
    
    settings_file = tmp_path / "test_settings.json"
    default_settings = {
        "camera": {
            "fov": 60.0,
            "default_distance": 5.0
        },
        "ui": {
            "show_mesh": True,
            "show_skeleton": True
        }
    }
    
    with open(settings_file, 'w') as f:
        json.dump(default_settings, f)
    
    return str(settings_file)


@pytest.fixture
def sample_glb_data():

    return {
        "nodes": [
            {"name": "root", "translation": [0, 0, 0]},
            {"name": "child", "translation": [0, 1, 0]}
        ],
        "skins": [
            {"joints": [0, 1]}
        ]
    }


@pytest.fixture
def assert_vec3_equal():

    from pose_engine.vec3 import Vec3
    
    def _compare(v1: Vec3, v2: Vec3, tolerance: float = 0.0001):
        assert abs(v1.x - v2.x) < tolerance, f"x: {v1.x} != {v2.x}"
        assert abs(v1.y - v2.y) < tolerance, f"y: {v1.y} != {v2.y}"
        assert abs(v1.z - v2.z) < tolerance, f"z: {v1.z} != {v2.z}"
    
    return _compare


@pytest.fixture
def assert_quat_equal():

    from pose_engine.quat import Quat
    
    def _compare(q1: Quat, q2: Quat, tolerance: float = 0.0001):
        dot = q1.w * q2.w + q1.x * q2.x + q1.y * q2.y + q1.z * q2.z
        if dot < 0:
            q2 = Quat(-q2.w, -q2.x, -q2.y, -q2.z)
        
        assert abs(q1.w - q2.w) < tolerance, f"w: {q1.w} != {q2.w}"
        assert abs(q1.x - q2.x) < tolerance, f"x: {q1.x} != {q2.x}"
        assert abs(q1.y - q2.y) < tolerance, f"y: {q1.y} != {q2.y}"
        assert abs(q1.z - q2.z) < tolerance, f"z: {q1.z} != {q2.z}"
    
    return _compare


def pytest_configure(config):
    
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


def pytest_collection_modifyitems(config, items):
    
    for item in items:
        if "test_skeleton" in item.fspath.basename:
            item.add_marker(pytest.mark.unit)

        if "test_math" in item.fspath.basename:
            item.add_marker(pytest.mark.unit)

        if "test_gltf" in item.fspath.basename:
            item.add_marker(pytest.mark.integration)

        if "test_camera" in item.fspath.basename:
            item.add_marker(pytest.mark.unit)

        if "test_settings" in item.fspath.basename:
            item.add_marker(pytest.mark.unit)

        if "test_camera_bookmarks" in item.fspath.basename:
            item.add_marker(pytest.mark.unit)

        if "test_pose_state" in item.fspath.basename:
            item.add_marker(pytest.mark.unit)

        if "test_scene" in item.fspath.basename:
            item.add_marker(pytest.mark.integration)

        if "test_model_instance" in item.fspath.basename:
            item.add_marker(pytest.mark.integration)
    
    
    @pytest.fixture
    def sample_scene():

        from pose_engine.scene import Scene
        return Scene()
    
    
    @pytest.fixture
    def sample_model_instance():

        from pose_engine.model_instance import ModelInstance
        return ModelInstance(name="TestModel")
    
    
    @pytest.fixture
    def sample_bookmark_data():

        return {
            "name": "Test Bookmark",
            "slot": 1,
            "target": (0, 1, 0),
            "distance": 5.0,
            "yaw": 0.0,
            "pitch": 0.0,
            "fov": 60.0,
            "near": 0.1,
            "far": 100.0
        }
    
    
    @pytest.fixture
    def temp_bookmarks_file(tmp_path):

        import json
        bookmarks_file = tmp_path / "test_bookmarks.json"
        bookmarks_file.write_text("{}")
        return str(bookmarks_file)
    
    
    @pytest.fixture
    def sample_bookmark():

        from pose_engine.camera.bookmarks import CameraBookmark
        from datetime import datetime
        return CameraBookmark(
            name="Test Bookmark",
            slot=1,
            target=(0, 1, 0),
            distance=5.0,
            yaw=0.0,
            pitch=0.0,
            fov=60.0
        )
    
    
    @pytest.fixture
    def sample_bone_pose():

        from pose_engine.pose_state import BonePose
        from pose_engine.quat import Quat
        from pose_engine.vec3 import Vec3
        return BonePose(
            rotation=Quat(1, 0, 0, 0),
            position=Vec3(0, 0, 0),
            scale=Vec3(1, 1, 1)
        )
    
    
    @pytest.fixture
    def sample_pose_snapshot():

        from pose_engine.pose_state import PoseSnapshot, BonePose
        from pose_engine.quat import Quat
        from pose_engine.vec3 import Vec3
        bones = {
            "root": BonePose(rotation=Quat.identity(), position=Vec3(0, 0, 0)),
            "spine": BonePose(rotation=Quat.identity(), position=Vec3(0, 1, 0))
        }
        return PoseSnapshot(bones=bones, name="Test Pose")
    
    
    @pytest.fixture
    def sample_undo_redo_stack():

        from pose_engine.pose_state import UndoRedoStack
        return UndoRedoStack(max_history=10)
    
    
    @pytest.fixture
    def sample_key_binding():

        from pose_engine.settings.key_bindings import KeyBinding
        from PyQt5.QtCore import Qt
        return KeyBinding(key=Qt.Key_F, modifiers=Qt.ControlModifier, action="test_action")
    
    
    @pytest.fixture
    def sample_mouse_binding():

        from pose_engine.settings.key_bindings import MouseBinding
        from PyQt5.QtCore import Qt
        return MouseBinding(button=Qt.LeftButton, modifiers=Qt.ShiftModifier, action="test_action")

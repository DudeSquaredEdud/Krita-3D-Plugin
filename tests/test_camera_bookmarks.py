#!/usr/bin/env python3


import pytest
import json
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pose_engine.camera.bookmarks import CameraBookmark, CameraBookmarkManager
from pose_engine.vec3 import Vec3


class TestCameraBookmark:
    

    def test_bookmark_creation(self):
        
        bookmark = CameraBookmark(
            name="Test Bookmark",
            slot=1,
            target=(0, 1, 0),
            distance=5.0,
            yaw=0.0,
            pitch=0.0,
            fov=60.0
        )
        
        assert bookmark.name == "Test Bookmark"
        assert bookmark.slot == 1
        assert bookmark.target == (0, 1, 0)
        assert bookmark.distance == 5.0
        assert bookmark.yaw == 0.0
        assert bookmark.pitch == 0.0
        assert bookmark.fov == 60.0

    def test_bookmark_default_values(self):
        
        bookmark = CameraBookmark(
            name="Default Bookmark",
            slot=2,
            target=(1, 2, 3),
            distance=3.0,
            yaw=0.5,
            pitch=0.25,
            fov=45.0
        )
        
        assert bookmark.near == 0.1
        assert bookmark.far == 100.0
        assert bookmark.created_at is not None
        assert bookmark.modified_at is not None

    def test_bookmark_to_dict(self):
        
        bookmark = CameraBookmark(
            name="Serialize Test",
            slot=3,
            target=(1.5, 2.5, 3.5),
            distance=7.0,
            yaw=1.0,
            pitch=0.5,
            fov=75.0,
            near=0.5,
            far=200.0
        )
        
        data = bookmark.to_dict()
        
        assert data['name'] == "Serialize Test"
        assert data['slot'] == 3
        assert data['target']['x'] == 1.5
        assert data['target']['y'] == 2.5
        assert data['target']['z'] == 3.5
        assert data['distance'] == 7.0
        assert data['yaw'] == 1.0
        assert data['pitch'] == 0.5
        assert data['fov'] == 75.0
        assert data['near'] == 0.5
        assert data['far'] == 200.0
        assert 'created_at' in data
        assert 'modified_at' in data

    def test_bookmark_from_dict(self):
        
        data = {
            'name': "Deserialize Test",
            'slot': 4,
            'target': {'x': 2.0, 'y': 3.0, 'z': 4.0},
            'distance': 10.0,
            'yaw': 1.5,
            'pitch': 0.75,
            'fov': 90.0,
            'near': 0.2,
            'far': 150.0,
            'created_at': '2024-01-15T10:30:00',
            'modified_at': '2024-01-15T11:00:00'
        }
        
        bookmark = CameraBookmark.from_dict(data)
        
        assert bookmark.name == "Deserialize Test"
        assert bookmark.slot == 4
        assert bookmark.target == (2.0, 3.0, 4.0)
        assert bookmark.distance == 10.0
        assert bookmark.yaw == 1.5
        assert bookmark.pitch == 0.75
        assert bookmark.fov == 90.0
        assert bookmark.near == 0.2
        assert bookmark.far == 150.0

    def test_bookmark_from_dict_tuple_target(self):
        
        data = {
            'name': "Tuple Target",
            'slot': 5,
            'target': [5.0, 6.0, 7.0],
            'distance': 8.0,
            'yaw': 0.0,
            'pitch': 0.0,
            'fov': 60.0,
            'created_at': '2024-01-15T10:30:00',
            'modified_at': '2024-01-15T11:00:00'
        }
        
        bookmark = CameraBookmark.from_dict(data)
        
        assert bookmark.target == (5.0, 6.0, 7.0)

    def test_bookmark_get_summary(self):
        
        bookmark = CameraBookmark(
            name="Summary Test",
            slot=1,
            target=(1.234, 5.678, 9.012),
            distance=7.5,
            yaw=0.0,
            pitch=0.0,
            fov=60.0
        )
        
        summary = bookmark.get_summary()
        
        assert "FOV:60" in summary
        assert "Dist:7.5" in summary
        assert "1.2" in summary

    def test_bookmark_roundtrip_serialization(self):
        
        original = CameraBookmark(
            name="Roundtrip Test",
            slot=6,
            target=(3.0, 4.0, 5.0),
            distance=12.0,
            yaw=2.0,
            pitch=1.0,
            fov=80.0,
            near=0.3,
            far=180.0
        )
        
        data = original.to_dict()
        restored = CameraBookmark.from_dict(data)
        
        assert restored.name == original.name
        assert restored.slot == original.slot
        assert restored.target == original.target
        assert restored.distance == original.distance
        assert restored.yaw == original.yaw
        assert restored.pitch == original.pitch
        assert restored.fov == original.fov
        assert restored.near == original.near
        assert restored.far == original.far


class TestCameraBookmarkManager:
    

    def test_manager_creation(self):
        
        manager = CameraBookmarkManager()
        
        assert manager._bookmarks == {}
        assert manager.MAX_BOOKMARKS == 9

    def test_manager_with_settings_dir(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        assert manager._settings_dir == tmp_path

    def test_save_bookmark(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        class MockCamera:
            target = Vec3(0, 1, 0)
            distance = 5.0
            yaw = 0.0
            pitch = 0.0
            fov = 60.0
            near = 0.1
            far = 100.0
        
        camera = MockCamera()
        bookmark = manager.save_bookmark(1, camera, "Test Bookmark")
        
        assert bookmark is not None
        assert bookmark.name == "Test Bookmark"
        assert bookmark.slot == 1
        assert manager.has_bookmark(1)

    def test_save_bookmark_invalid_slot(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        class MockCamera:
            target = Vec3(0, 1, 0)
            distance = 5.0
            yaw = 0.0
            pitch = 0.0
            fov = 60.0
        
        camera = MockCamera()
        
        with pytest.raises(ValueError):
            manager.save_bookmark(0, camera)

        with pytest.raises(ValueError):
            manager.save_bookmark(10, camera)

    def test_load_bookmark(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        class MockCamera:
            target = Vec3(0, 1, 0)
            distance = 5.0
            yaw = 0.5
            pitch = 0.25
            fov = 60.0
            near = 0.1
            far = 100.0
        
        camera1 = MockCamera()
        manager.save_bookmark(1, camera1, "Test")
        
        camera2 = MockCamera()
        camera2.target = Vec3(10, 10, 10)
        camera2.distance = 20.0
        camera2.yaw = 2.0
        camera2.pitch = 1.0
        camera2.fov = 90.0
        
        result = manager.load_bookmark(1, camera2)
        
        assert result == True
        assert camera2.target.x == 0
        assert camera2.target.y == 1
        assert camera2.target.z == 0
        assert camera2.distance == 5.0
        assert camera2.yaw == 0.5
        assert camera2.pitch == 0.25
        assert camera2.fov == 60.0

    def test_load_bookmark_nonexistent(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        class MockCamera:
            target = Vec3(0, 0, 0)
            distance = 1.0
            yaw = 0.0
            pitch = 0.0
            fov = 45.0
        
        camera = MockCamera()
        result = manager.load_bookmark(99, camera)
        
        assert result == False

    def test_delete_bookmark(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        class MockCamera:
            target = Vec3(0, 1, 0)
            distance = 5.0
            yaw = 0.0
            pitch = 0.0
            fov = 60.0
        
        camera = MockCamera()
        manager.save_bookmark(1, camera, "To Delete")
        
        assert manager.has_bookmark(1)
        
        result = manager.delete_bookmark(1)
        
        assert result == True
        assert not manager.has_bookmark(1)

    def test_delete_bookmark_nonexistent(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        result = manager.delete_bookmark(99)
        
        assert result == False

    def test_get_bookmark(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        class MockCamera:
            target = Vec3(1, 2, 3)
            distance = 7.0
            yaw = 1.0
            pitch = 0.5
            fov = 75.0
        
        camera = MockCamera()
        manager.save_bookmark(2, camera, "Get Test")
        
        bookmark = manager.get_bookmark(2)
        
        assert bookmark is not None
        assert bookmark.name == "Get Test"
        assert bookmark.target == (1, 2, 3)

    def test_get_bookmark_nonexistent(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        bookmark = manager.get_bookmark(99)
        
        assert bookmark is None

    def test_get_all_bookmarks(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        class MockCamera:
            target = Vec3(0, 0, 0)
            distance = 5.0
            yaw = 0.0
            pitch = 0.0
            fov = 60.0
        
        camera = MockCamera()
        manager.save_bookmark(1, camera, "Bookmark 1")
        manager.save_bookmark(2, camera, "Bookmark 2")
        manager.save_bookmark(3, camera, "Bookmark 3")
        
        all_bookmarks = manager.get_all_bookmarks()
        
        assert len(all_bookmarks) == 3
        assert 1 in all_bookmarks
        assert 2 in all_bookmarks
        assert 3 in all_bookmarks

    def test_has_bookmark(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        class MockCamera:
            target = Vec3(0, 0, 0)
            distance = 5.0
            yaw = 0.0
            pitch = 0.0
            fov = 60.0
        
        camera = MockCamera()
        
        assert not manager.has_bookmark(1)
        
        manager.save_bookmark(1, camera, "Test")
        
        assert manager.has_bookmark(1)

    def test_rename_bookmark(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        class MockCamera:
            target = Vec3(0, 0, 0)
            distance = 5.0
            yaw = 0.0
            pitch = 0.0
            fov = 60.0
        
        camera = MockCamera()
        manager.save_bookmark(1, camera, "Original Name")
        
        result = manager.rename_bookmark(1, "New Name")
        
        assert result == True
        assert manager.get_bookmark(1).name == "New Name"

    def test_rename_bookmark_nonexistent(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        result = manager.rename_bookmark(99, "New Name")
        
        assert result == False

    def test_bookmark_persistence(self, tmp_path):
        
        manager1 = CameraBookmarkManager(settings_dir=tmp_path)
        
        class MockCamera:
            target = Vec3(5, 10, 15)
            distance = 12.0
            yaw = 1.5
            pitch = 0.75
            fov = 85.0
        
        camera = MockCamera()
        manager1.save_bookmark(5, camera, "Persistence Test")
        
        manager2 = CameraBookmarkManager(settings_dir=tmp_path)
        
        assert manager2.has_bookmark(5)
        bookmark = manager2.get_bookmark(5)
        assert bookmark.name == "Persistence Test"
        assert bookmark.target == (5, 10, 15)

    def test_bookmark_slots(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        class MockCamera:
            target = Vec3(0, 0, 0)
            distance = 5.0
            yaw = 0.0
            pitch = 0.0
            fov = 60.0
        
        camera = MockCamera()
        
        for slot in range(1, 10):
            manager.save_bookmark(slot, camera, f"Slot {slot}")
            assert manager.has_bookmark(slot)
        
        all_bookmarks = manager.get_all_bookmarks()
        assert len(all_bookmarks) == 9

    def test_export_to_file(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        class MockCamera:
            target = Vec3(0, 0, 0)
            distance = 5.0
            yaw = 0.0
            pitch = 0.0
            fov = 60.0
        
        camera = MockCamera()
        manager.save_bookmark(1, camera, "Export Test 1")
        manager.save_bookmark(2, camera, "Export Test 2")
        
        export_path = tmp_path / "exported_bookmarks.json"
        result = manager.export_to_file(export_path)
        
        assert result == True
        assert export_path.exists()
        
        with open(export_path) as f:
            data = json.load(f)
        
        assert '1' in data
        assert '2' in data

    def test_import_from_file(self, tmp_path):
        
        export_path = tmp_path / "import_test.json"
        data = {
            '1': {
                'name': 'Imported 1',
                'slot': 1,
                'target': {'x': 1, 'y': 2, 'z': 3},
                'distance': 10.0,
                'yaw': 0.5,
                'pitch': 0.25,
                'fov': 70.0,
                'near': 0.1,
                'far': 100.0,
                'created_at': '2024-01-15T10:00:00',
                'modified_at': '2024-01-15T10:00:00'
            },
            '2': {
                'name': 'Imported 2',
                'slot': 2,
                'target': {'x': 4, 'y': 5, 'z': 6},
                'distance': 15.0,
                'yaw': 1.0,
                'pitch': 0.5,
                'fov': 80.0,
                'near': 0.1,
                'far': 100.0,
                'created_at': '2024-01-15T10:00:00',
                'modified_at': '2024-01-15T10:00:00'
            }
        }
        
        with open(export_path, 'w') as f:
            json.dump(data, f)
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        count = manager.import_from_file(export_path)
        
        assert count == 2
        assert manager.has_bookmark(1)
        assert manager.has_bookmark(2)
        assert manager.get_bookmark(1).name == 'Imported 1'

    def test_import_merge(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        class MockCamera:
            target = Vec3(0, 0, 0)
            distance = 5.0
            yaw = 0.0
            pitch = 0.0
            fov = 60.0
        
        camera = MockCamera()
        manager.save_bookmark(1, camera, "Existing")
        
        import_path = tmp_path / "merge_test.json"
        data = {
            '2': {
                'name': 'Merged',
                'slot': 2,
                'target': {'x': 0, 'y': 0, 'z': 0},
                'distance': 5.0,
                'yaw': 0.0,
                'pitch': 0.0,
                'fov': 60.0,
                'near': 0.1,
                'far': 100.0,
                'created_at': '2024-01-15T10:00:00',
                'modified_at': '2024-01-15T10:00:00'
            }
        }
        
        with open(import_path, 'w') as f:
            json.dump(data, f)
        
        count = manager.import_from_file(import_path, merge=True)
        
        assert count == 1
        assert manager.has_bookmark(1)
        assert manager.has_bookmark(2)

    def test_import_replace(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        class MockCamera:
            target = Vec3(0, 0, 0)
            distance = 5.0
            yaw = 0.0
            pitch = 0.0
            fov = 60.0
        
        camera = MockCamera()
        manager.save_bookmark(1, camera, "Existing")
        
        import_path = tmp_path / "replace_test.json"
        data = {
            '2': {
                'name': 'Replaced',
                'slot': 2,
                'target': {'x': 0, 'y': 0, 'z': 0},
                'distance': 5.0,
                'yaw': 0.0,
                'pitch': 0.0,
                'fov': 60.0,
                'near': 0.1,
                'far': 100.0,
                'created_at': '2024-01-15T10:00:00',
                'modified_at': '2024-01-15T10:00:00'
            }
        }
        
        with open(import_path, 'w') as f:
            json.dump(data, f)
        
        count = manager.import_from_file(import_path, merge=False)
        
        assert count == 1
        assert not manager.has_bookmark(1)
        assert manager.has_bookmark(2)

    def test_import_invalid_file(self, tmp_path):
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        
        result = manager.import_from_file(tmp_path / "nonexistent.json")
        assert result == -1
        
        invalid_path = tmp_path / "invalid.json"
        invalid_path.write_text("{ invalid json }")
        result = manager.import_from_file(invalid_path)
        assert result == -1

    def test_manager_without_settings_dir(self):
        
        manager = CameraBookmarkManager(settings_dir=None)
        
        class MockCamera:
            target = Vec3(0, 0, 0)
            distance = 5.0
            yaw = 0.0
            pitch = 0.0
            fov = 60.0
        
        camera = MockCamera()
        bookmark = manager.save_bookmark(1, camera, "Memory Only")
        
        assert bookmark is not None
        assert manager.has_bookmark(1)
        


class TestCameraBookmarkIntegration:
    

    def test_bookmark_with_real_camera(self, tmp_path):
        
        from pose_engine.camera import Camera
        
        manager = CameraBookmarkManager(settings_dir=tmp_path)
        camera = Camera()
        
        camera.target = Vec3(1, 2, 3)
        camera.distance = 7.5
        camera.yaw = 0.5
        camera.pitch = 0.25
        camera.fov = 75
        
        manager.save_bookmark(1, camera, "Real Camera Test")
        
        camera.target = Vec3(10, 20, 30)
        camera.distance = 20.0
        camera.yaw = 2.0
        camera.pitch = 1.0
        camera.fov = 90
        
        result = manager.load_bookmark(1, camera)
        
        assert result == True
        assert camera.target.x == 1
        assert camera.target.y == 2
        assert camera.target.z == 3
        assert camera.distance == 7.5
        assert camera.yaw == 0.5
        assert camera.pitch == 0.25
        assert camera.fov == 75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

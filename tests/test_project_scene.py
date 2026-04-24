

import os
import json
import tempfile
import shutil
import pytest
from datetime import datetime
from pathlib import Path

from pose_engine.project_scene import (
    ProjectScene, SceneSettings, SceneMetadata
)
from pose_engine.scene import Scene
from pose_engine.model_instance import ModelInstance


class TestSceneSettings:
    
    
    def test_default_settings(self):
        
        settings = SceneSettings()
        assert settings.idle_save_delay == 5.0
        assert settings.continuous_save_interval == 60.0
        assert settings.max_backup_files == 5
        assert settings.compress_output == False
        assert settings.enable_diff_save == True
    
    def test_custom_settings(self):
        
        settings = SceneSettings(
            idle_save_delay=10.0,
            continuous_save_interval=30.0,
            max_backup_files=10
        )
        assert settings.idle_save_delay == 10.0
        assert settings.continuous_save_interval == 30.0
        assert settings.max_backup_files == 10


class TestSceneMetadata:
    
    
    def test_default_metadata(self):
        
        meta = SceneMetadata()
        assert meta.name == "Untitled Scene"
        assert meta.version == "1.0"
        assert meta.krita_project is None
    
    def test_custom_metadata(self):
        
        meta = SceneMetadata(
            name="Test Scene",
            krita_project="/path/to/project.kra"
        )
        assert meta.name == "Test Scene"
        assert meta.krita_project == "/path/to/project.kra"


class TestProjectScene:
    
    
    @pytest.fixture
    def temp_dir(self):
        
        dir_path = tempfile.mkdtemp()
        yield dir_path
        shutil.rmtree(dir_path, ignore_errors=True)
    
    @pytest.fixture
    def scene(self):
        
        return Scene()
    
    @pytest.fixture
    def project_scene(self, scene):
        
        return ProjectScene(scene)
    
    def test_initialization(self, project_scene):
        
        assert project_scene.scene is not None
        assert project_scene.has_unsaved_changes == False
        assert project_scene.scene_file_path is None
    
    def test_mark_changed(self, project_scene):
        
        project_scene.mark_changed()
        assert project_scene.has_unsaved_changes == True
    
    def test_save_and_load(self, project_scene, temp_dir):
        
        file_path = os.path.join(temp_dir, "test_scene.k3dscene")
        
        result = project_scene.save(file_path)
        assert result == True
        assert project_scene.has_unsaved_changes == False
        assert os.path.exists(file_path)
        
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        assert 'metadata' in data
        assert 'scene' in data
        assert data['metadata']['name'] == "Untitled Scene"
        
        new_project_scene = ProjectScene(Scene())
        result = new_project_scene.load(file_path)
        assert result == True
        assert new_project_scene.scene_file_path == file_path
    
    def test_save_for_krita_project(self, project_scene, temp_dir):
        
        krita_path = os.path.join(temp_dir, "test_project.kra")
        
        result = project_scene.save_for_krita_project(krita_path)
        assert result == True
        
        expected_scene_path = os.path.join(temp_dir, "test_project.k3dscene")
        assert os.path.exists(expected_scene_path)
        assert project_scene.krita_project_path == krita_path
    
    def test_load_for_krita_project(self, project_scene, temp_dir):
        
        krita_path = os.path.join(temp_dir, "test_project.kra")
        
        project_scene.save_for_krita_project(krita_path)
        
        new_project_scene = ProjectScene(Scene())
        result = new_project_scene.load_for_krita_project(krita_path)
        assert result == True
        assert new_project_scene.krita_project_path == krita_path
    
    def test_load_nonexistent_scene(self, project_scene, temp_dir):
        
        krita_path = os.path.join(temp_dir, "nonexistent.kra")
        
        result = project_scene.load_for_krita_project(krita_path)
        assert result == False
        assert project_scene.krita_project_path == krita_path
        assert project_scene.scene_file_path is not None
    
    def test_backup_creation(self, project_scene, temp_dir):
        
        file_path = os.path.join(temp_dir, "test_scene.k3dscene")
        
        project_scene.save(file_path)
        
        project_scene.mark_changed()
        project_scene.save(file_path, create_backup=True)
        
        backup_dir = os.path.join(temp_dir, 'backups')
        assert os.path.exists(backup_dir)
        
        backups = os.listdir(backup_dir)
        assert len(backups) >= 1
    
    def test_backup_cleanup(self, project_scene, temp_dir):
        
        import time
        file_path = os.path.join(temp_dir, "test_scene.k3dscene")
        
        project_scene.settings.max_backup_files = 2
        
        for i in range(5):
            project_scene.mark_changed()
            project_scene.save(file_path, create_backup=True)
            time.sleep(0.01)
        
        backup_dir = os.path.join(temp_dir, 'backups')
        backups = os.listdir(backup_dir)
        
        assert len(backups) <= 2
    
    def test_new_scene(self, project_scene, temp_dir):
        
        file_path = os.path.join(temp_dir, "test_scene.k3dscene")
        project_scene.save(file_path)
        
        project_scene.new_scene()
        
        assert project_scene.has_unsaved_changes == False
        assert project_scene.scene_file_path is None
        assert project_scene.scene.get_model_count() == 0
    
    def test_state_hash_computation(self, project_scene):
        
        state1 = {'version': 1, 'models': {}}
        state2 = {'version': 1, 'models': {}}
        state3 = {'version': 2, 'models': {}}
        
        hash1 = project_scene._compute_state_hash(state1)
        hash2 = project_scene._compute_state_hash(state2)
        hash3 = project_scene._compute_state_hash(state3)
        
        assert hash1 == hash2
        assert hash1 != hash3
    
    def test_diff_computation(self, project_scene):
        
        previous = {
            'version': 1,
            'models': {
                'model1': {'name': 'Model1', 'visible': True}
            }
        }
        
        current = {
            'version': 1,
            'models': {
                'model1': {'name': 'Model1', 'visible': False},
                'model2': {'name': 'Model2', 'visible': True}
            }
        }
        
        diff = project_scene._compute_diff(current, previous)
        
        assert diff is not None
        assert 'changes' in diff
        assert 'model2' in diff['changes']
        assert diff['changes']['model2']['action'] == 'added'
        assert 'model1' in diff['changes']
        assert diff['changes']['model1']['action'] == 'modified'
    
    def test_diff_no_changes(self, project_scene):
        
        state = {
            'version': 1,
            'models': {
                'model1': {'name': 'Model1'}
            }
        }
        
        diff = project_scene._compute_diff(state, state)
        assert diff is None


class TestProjectSceneCallbacks:
    

    @pytest.fixture
    def temp_dir(self):
        
        dir_path = tempfile.mkdtemp()
        yield dir_path
        shutil.rmtree(dir_path, ignore_errors=True)

    def test_scene_saved_callback(self, temp_dir):
        
        scene = Scene()
        project_scene = ProjectScene(scene)
        file_path = os.path.join(temp_dir, "test.k3dscene")

        saved_path = None
        def on_saved(path):
            nonlocal saved_path
            saved_path = path

        project_scene.add_callback('scene_saved', on_saved)
        project_scene.save(file_path)

        assert saved_path == file_path

    def test_scene_loaded_callback(self, temp_dir):
        
        scene = Scene()
        project_scene = ProjectScene(scene)
        file_path = os.path.join(temp_dir, "test.k3dscene")

        project_scene.save(file_path)

        loaded_path = None
        def on_loaded(path):
            nonlocal loaded_path
            loaded_path = path

        new_project_scene = ProjectScene(Scene())
        new_project_scene.add_callback('scene_loaded', on_loaded)
        new_project_scene.load(file_path)

        assert loaded_path == file_path

    def test_remove_callback(self, temp_dir):
        
        scene = Scene()
        project_scene = ProjectScene(scene)
        file_path = os.path.join(temp_dir, "test.k3dscene")

        call_count = 0
        def on_saved(path):
            nonlocal call_count
            call_count += 1

        project_scene.add_callback('scene_saved', on_saved)
        project_scene.remove_callback('scene_saved', on_saved)
        project_scene.save(file_path)

        assert call_count == 0


class TestExportImport:
    
    
    @pytest.fixture
    def temp_dir(self):
        
        dir_path = tempfile.mkdtemp()
        yield dir_path
        shutil.rmtree(dir_path, ignore_errors=True)
    
    def test_export_full(self, temp_dir):
        
        scene = Scene()
        project_scene = ProjectScene(scene)
        
        export_path = os.path.join(temp_dir, "export.zip")
        result = project_scene.export_full(export_path, include_models=False)
        
        assert result == True
        assert os.path.exists(export_path.replace('.zip', '') + '.zip') or \
               os.path.exists(export_path) or \
               os.path.exists(export_path.replace('.zip', '') + '_export')
    
    def test_import_full(self, temp_dir):
        
        scene = Scene()
        project_scene = ProjectScene(scene)
        
        export_path = os.path.join(temp_dir, "export.zip")
        project_scene.export_full(export_path, include_models=False)
        
        new_project_scene = ProjectScene(Scene())
        # TODO: IMPLEMENT - full import test requires actual model files


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

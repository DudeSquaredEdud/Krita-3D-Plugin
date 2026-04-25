#!/usr/bin/env python3


import pytest
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pose_engine.settings.settings import (
    PluginSettings, KeyboardSettings, MouseSettings, 
    GizmoSettings, CameraSettings, UISettings,
    SettingsChangeNotifier
)
from pose_engine.settings.key_bindings import (
    KeyBinding, MouseBinding, find_binding_conflicts
)
from pose_engine.settings.defaults import (
    DEFAULT_KEYBOARD_SHORTCUTS, DEFAULT_MOUSE_SETTINGS,
    DEFAULT_GIZMO_SETTINGS, DEFAULT_CAMERA_SETTINGS, DEFAULT_UI_SETTINGS,
    KEYBOARD_ACTION_NAMES
)
from PyQt5.QtCore import Qt


class TestKeyBinding:
    

    def test_key_binding_creation(self):
        
        binding = KeyBinding(key=Qt.Key_F, modifiers=Qt.ControlModifier, action="test")
        
        assert binding.key == Qt.Key_F
        assert binding.modifiers == Qt.ControlModifier
        assert binding.action == "test"

    def test_key_binding_default_modifiers(self):
        
        binding = KeyBinding(key=Qt.Key_A)
        
        assert binding.key == Qt.Key_A
        assert binding.modifiers == Qt.NoModifier

    def test_key_binding_matches(self):
        
        binding = KeyBinding(key=Qt.Key_S, modifiers=Qt.ControlModifier)
        
        assert binding.matches(Qt.Key_S, Qt.ControlModifier) == True
        assert binding.matches(Qt.Key_S, Qt.NoModifier) == False
        assert binding.matches(Qt.Key_A, Qt.ControlModifier) == False

    def test_key_binding_to_dict(self):
        
        binding = KeyBinding(key=Qt.Key_Z, modifiers=Qt.ControlModifier | Qt.ShiftModifier, action="redo")
        data = binding.to_dict()
        
        assert data['key'] == Qt.Key_Z
        assert data['modifiers'] == int(Qt.ControlModifier | Qt.ShiftModifier)
        assert data['action'] == "redo"

    def test_key_binding_from_dict(self):
        
        data = {'key': Qt.Key_Y, 'modifiers': int(Qt.ControlModifier), 'action': 'redo_alt'}
        binding = KeyBinding.from_dict(data)
        
        assert binding.key == Qt.Key_Y
        assert binding.modifiers == Qt.ControlModifier
        assert binding.action == "redo_alt"

    def test_key_binding_get_key_name(self):
        
        binding = KeyBinding(key=Qt.Key_F)
        assert binding.get_key_name() == 'F'
        
        binding = KeyBinding(key=Qt.Key_Return)
        assert binding.get_key_name() == 'Return'

    def test_key_binding_get_modifier_names(self):
        
        binding = KeyBinding(key=Qt.Key_S, modifiers=Qt.ControlModifier | Qt.ShiftModifier)
        modifiers = binding.get_modifier_names()
        
        assert 'Ctrl' in modifiers
        assert 'Shift' in modifiers

    def test_key_binding_get_display_string(self):
        
        binding = KeyBinding(key=Qt.Key_S, modifiers=Qt.ControlModifier)
        display = binding.get_display_string()
        
        assert 'Ctrl' in display
        assert 'S' in display

    def test_key_binding_equality(self):
        
        b1 = KeyBinding(key=Qt.Key_A, modifiers=Qt.ControlModifier)
        b2 = KeyBinding(key=Qt.Key_A, modifiers=Qt.ControlModifier)
        b3 = KeyBinding(key=Qt.Key_A, modifiers=Qt.NoModifier)
        
        assert b1 == b2
        assert b1 != b3

    def test_key_binding_hash(self):
        
        b1 = KeyBinding(key=Qt.Key_A, modifiers=Qt.ControlModifier)
        b2 = KeyBinding(key=Qt.Key_A, modifiers=Qt.ControlModifier)
        
        assert hash(b1) == hash(b2)
        
        bindings_set = {b1, b2}
        assert len(bindings_set) == 1


class TestMouseBinding:
    

    def test_mouse_binding_creation(self):
        
        binding = MouseBinding(button=Qt.LeftButton, modifiers=Qt.ShiftModifier, action="pan")
        
        assert binding.button == Qt.LeftButton
        assert binding.modifiers == Qt.ShiftModifier
        assert binding.action == "pan"

    def test_mouse_binding_matches(self):
        
        binding = MouseBinding(button=Qt.RightButton, modifiers=Qt.NoModifier)
        
        assert binding.matches(Qt.RightButton, Qt.NoModifier) == True
        assert binding.matches(Qt.RightButton, Qt.ShiftModifier) == False
        assert binding.matches(Qt.LeftButton, Qt.NoModifier) == False

    def test_mouse_binding_to_dict(self):
        
        binding = MouseBinding(button=Qt.MiddleButton, modifiers=Qt.ControlModifier)
        data = binding.to_dict()
        
        assert data['button'] == int(Qt.MiddleButton)
        assert data['modifiers'] == int(Qt.ControlModifier)

    def test_mouse_binding_from_dict(self):
        
        data = {'button': int(Qt.RightButton), 'modifiers': int(Qt.NoModifier), 'action': 'rotate'}
        binding = MouseBinding.from_dict(data)
        
        assert binding.button == Qt.RightButton
        assert binding.modifiers == Qt.NoModifier
        assert binding.action == "rotate"

    def test_mouse_binding_get_button_name(self):
        
        binding = MouseBinding(button=Qt.LeftButton)
        assert binding.get_button_name() == 'Left'
        
        binding = MouseBinding(button=Qt.RightButton)
        assert binding.get_button_name() == 'Right'


class TestFindBindingConflicts:
    

    def test_no_conflicts(self):
        
        bindings = {
            'undo': KeyBinding(key=Qt.Key_Z, modifiers=Qt.ControlModifier),
            'redo': KeyBinding(key=Qt.Key_Y, modifiers=Qt.ControlModifier),
        }
        
        conflicts = find_binding_conflicts(bindings)
        assert len(conflicts) == 0

    def test_with_conflicts(self):
        
        bindings = {
            'undo': KeyBinding(key=Qt.Key_Z, modifiers=Qt.ControlModifier),
            'redo': KeyBinding(key=Qt.Key_Z, modifiers=Qt.ControlModifier),  
        }
        
        conflicts = find_binding_conflicts(bindings)
        assert len(conflicts) == 1
        assert conflicts[0][0] == 'undo'
        assert conflicts[0][1] == 'redo'

    def test_multiple_conflicts(self):
        
        bindings = {
            'action1': KeyBinding(key=Qt.Key_A, modifiers=Qt.NoModifier),
            'action2': KeyBinding(key=Qt.Key_A, modifiers=Qt.NoModifier),
            'action3': KeyBinding(key=Qt.Key_A, modifiers=Qt.NoModifier),
        }
        
        conflicts = find_binding_conflicts(bindings)
        assert len(conflicts) == 2


class TestKeyboardSettings:
    

    def test_keyboard_settings_creation(self):
        
        settings = KeyboardSettings()
        
        assert len(settings._shortcuts) > 0

    def test_keyboard_settings_defaults(self):
        
        settings = KeyboardSettings()
        
        assert settings.get_binding('undo') is not None
        assert settings.get_binding('redo') is not None

    def test_keyboard_get_binding(self):
        
        settings = KeyboardSettings()
        
        binding = settings.get_binding('undo')
        assert binding is not None
        assert binding.key == Qt.Key_Z
        assert binding.modifiers == Qt.ControlModifier

    def test_keyboard_get_binding_nonexistent(self):
        
        settings = KeyboardSettings()
        
        binding = settings.get_binding('nonexistent_action')
        assert binding is None

    def test_keyboard_set_binding(self):
        
        settings = KeyboardSettings()
        
        settings.set_binding('test_action', Qt.Key_T, Qt.AltModifier)
        binding = settings.get_binding('test_action')
        
        assert binding is not None
        assert binding.key == Qt.Key_T
        assert binding.modifiers == Qt.AltModifier

    def test_keyboard_get_key(self):
        
        settings = KeyboardSettings()
        
        key = settings.get_key('undo')
        assert key == Qt.Key_Z

    def test_keyboard_get_modifiers(self):
        
        settings = KeyboardSettings()
        
        modifiers = settings.get_modifiers('undo')
        assert modifiers == Qt.ControlModifier

    def test_keyboard_matches(self):
        
        settings = KeyboardSettings()
        
        assert settings.matches('undo', Qt.Key_Z, Qt.ControlModifier) == True
        assert settings.matches('undo', Qt.Key_Z, Qt.NoModifier) == False

    def test_keyboard_get_all_bindings(self):
        
        settings = KeyboardSettings()
        
        bindings = settings.get_all_bindings()
        assert isinstance(bindings, dict)
        assert len(bindings) > 0

    def test_keyboard_get_action_name(self):
        
        settings = KeyboardSettings()
        
        name = settings.get_action_name('undo')
        assert name == 'Undo'

    def test_keyboard_find_conflicts(self):
        
        settings = KeyboardSettings()
        
        conflicts = settings.find_conflicts()
        assert isinstance(conflicts, list)

    def test_keyboard_reset_to_defaults(self):
        
        settings = KeyboardSettings()
        
        settings.set_binding('undo', Qt.Key_X, Qt.ControlModifier)
        assert settings.get_key('undo') == Qt.Key_X
        
        settings.reset_to_defaults()
        assert settings.get_key('undo') == Qt.Key_Z

    def test_keyboard_to_dict(self):
        
        settings = KeyboardSettings()
        
        data = settings.to_dict()
        assert isinstance(data, dict)
        assert 'undo' in data

    def test_keyboard_load_from_dict(self):
        
        settings = KeyboardSettings()
        
        data = {
            'undo': {'key': Qt.Key_X, 'modifiers': int(Qt.ControlModifier), 'action': 'undo'}
        }
        
        settings.load_from_dict(data)
        assert settings.get_key('undo') == Qt.Key_X


class TestMouseSettings:
    

    def test_mouse_settings_creation(self):
        
        settings = MouseSettings()
        
        assert settings._settings is not None

    def test_mouse_get_sensitivity(self):
        
        settings = MouseSettings()
        
        sensitivity = settings.get_sensitivity('rotate')
        assert isinstance(sensitivity, float)

    def test_mouse_set_sensitivity(self):
        
        settings = MouseSettings()
        
        settings.set_sensitivity('rotate', 2.0)
        assert (settings.get_sensitivity('rotate') - 2.0)  < 0.01

    def test_mouse_get_binding(self):
        
        settings = MouseSettings()
        
        binding = settings.get_binding('rotate_binding')
        assert binding is not None

    def test_mouse_matches_binding(self):
        
        settings = MouseSettings()
        
        assert settings.matches_binding('rotate_binding', Qt.RightButton, Qt.NoModifier) == True

    def test_mouse_reset_to_defaults(self):
        
        settings = MouseSettings()
        
        settings.set_sensitivity('rotate', 5.0)
        settings.reset_to_defaults()
        
        assert (settings.get_sensitivity('rotate') - 1.0)  < 0.01

    def test_mouse_to_dict(self):
        
        settings = MouseSettings()
        
        data = settings.to_dict()
        assert isinstance(data, dict)

    def test_mouse_load_from_dict(self):
        
        settings = MouseSettings()
        
        data = {'rotate_sensitivity': 2.5}
        settings.load_from_dict(data)
        
        assert (settings.get_sensitivity('rotate') - 2.5) < 0.01


class TestGizmoSettings:
    

    def test_gizmo_settings_creation(self):
        
        settings = GizmoSettings()
        
        assert settings._settings is not None

    def test_gizmo_get(self):
        
        settings = GizmoSettings()
        
        scale = settings.get('base_scale')
        assert scale is not None

    def test_gizmo_set(self):
        
        settings = GizmoSettings()
        
        settings.set('base_scale', 0.5)
        assert (settings.get('base_scale') - 0.5) < 0.01

    def test_gizmo_get_scale_params(self):
        
        settings = GizmoSettings()
        
        base, min_scale, max_scale = settings.get_scale_params()
        assert base > 0
        assert min_scale > 0
        assert max_scale > min_scale

    def test_gizmo_get_sensitivity(self):
        
        settings = GizmoSettings()
        
        sens = settings.get_sensitivity('rotation')
        assert isinstance(sens, float)

    def test_gizmo_get_colors(self):
        
        settings = GizmoSettings()

        colors = settings.get_colors()
        assert isinstance(colors, dict)
        assert 'x_axis' in colors or 'x' in colors or 'red' in colors

    def test_gizmo_reset_to_defaults(self):
        
        settings = GizmoSettings()
        
        settings.set('base_scale', 10.0)
        settings.reset_to_defaults()
        
        assert abs(settings.get('base_scale') - 10.0) > 0.01

    def test_gizmo_to_dict(self):
        
        settings = GizmoSettings()
        
        data = settings.to_dict()
        assert isinstance(data, dict)

    def test_gizmo_load_from_dict(self):
        
        settings = GizmoSettings()

        data = {'base_scale': 0.3}
        settings.load_from_dict(data)

        assert (settings.get('base_scale') - 0.3) < 0.01

    def test_gizmo_get_display_scale_default(self):
        
        settings = GizmoSettings()

        assert abs(settings.get_display_scale() - 0.05) < 0.001

    def test_gizmo_get_joint_display_scale_default(self):
        
        settings = GizmoSettings()

        assert abs(settings.get_joint_display_scale() - 0.15) < 0.001

    def test_gizmo_set_display_scale(self):
        
        settings = GizmoSettings()

        settings.set('display_scale', 0.3)
        assert abs(settings.get_display_scale() - 0.3) < 0.001

    def test_gizmo_set_joint_display_scale(self):
        
        settings = GizmoSettings()

        settings.set('joint_display_scale', 0.5)
        assert abs(settings.get_joint_display_scale() - 0.5) < 0.001

    def test_gizmo_display_scale_in_to_dict(self):
        
        settings = GizmoSettings()

        data = settings.to_dict()
        assert 'display_scale' in data
        assert 'joint_display_scale' in data

    def test_gizmo_display_scale_load_from_dict(self):
        
        settings = GizmoSettings()

        data = {'display_scale': 0.4, 'joint_display_scale': 0.25}
        settings.load_from_dict(data)

        assert abs(settings.get_display_scale() - 0.4) < 0.001
        assert abs(settings.get_joint_display_scale() - 0.25) < 0.001

    def test_gizmo_set_with_notifier(self):
        
        from pose_engine.settings.settings import SettingsChangeNotifier
        notifier = SettingsChangeNotifier()
        settings = GizmoSettings(notifier)

        received = []
        notifier.setting_changed.connect(lambda cat, key, val: received.append((cat, key, val)))

        settings.set('display_scale', 0.5)

        assert len(received) == 1
        assert received[0] == ('gizmo', 'display_scale', 0.5)


class TestCameraSettings:
    

    def test_camera_settings_creation(self):
        
        settings = CameraSettings()
        
        assert settings._settings is not None

    def test_camera_get(self):
        
        settings = CameraSettings()
        
        fov = settings.get('default_fov')
        assert fov is not None

    def test_camera_set(self):
        
        settings = CameraSettings()
        
        settings.set('default_fov', 60.0)
        assert (settings.get('default_fov') - 60.0) < 0.01

    def test_camera_get_fov_params(self):
        
        settings = CameraSettings()
        
        default_fov, min_fov, max_fov = settings.get_fov_params()
        assert default_fov > 0
        assert min_fov > 0
        assert max_fov > min_fov

    def test_camera_get_distance_params(self):
        
        settings = CameraSettings()
        
        default_dist, min_dist, max_dist = settings.get_distance_params()
        assert default_dist > 0
        assert min_dist > 0
        assert max_dist > min_dist

    def test_camera_get_speed(self):
        
        settings = CameraSettings()
        
        speed = settings.get_speed('rotate')
        assert isinstance(speed, float)

    def test_camera_reset_to_defaults(self):
        
        settings = CameraSettings()
        
        settings.set('default_fov', 120.0)
        settings.reset_to_defaults()
        
        assert abs(settings.get('default_fov') - 120.0) > 0.01

    def test_camera_to_dict(self):
        
        settings = CameraSettings()
        
        data = settings.to_dict()
        assert isinstance(data, dict)

    def test_camera_load_from_dict(self):
        
        settings = CameraSettings()
        
        data = {'default_fov': 75.0}
        settings.load_from_dict(data)
        
        assert (settings.get('default_fov') - 75.0) < 0.01


class TestUISettings:
    

    def test_ui_settings_creation(self):
        
        settings = UISettings()
        
        assert settings._settings is not None

    def test_ui_get(self):
        
        settings = UISettings()
        
        show_mesh = settings.get('show_mesh_default')
        assert show_mesh is not None

    def test_ui_set(self):
        
        settings = UISettings()
        
        settings.set('show_mesh_default', False)
        assert settings.get('show_mesh_default') == False

    def test_ui_get_default_visibility(self):
        
        settings = UISettings()
        
        visibility = settings.get_default_visibility()
        assert isinstance(visibility, dict)
        assert 'mesh' in visibility
        assert 'skeleton' in visibility

    def test_ui_get_theme_colors(self):
        
        settings = UISettings()
        
        colors = settings.get_theme_colors()
        assert isinstance(colors, dict)

    def test_ui_reset_to_defaults(self):
        
        settings = UISettings()
        
        settings.set('show_mesh_default', False)
        settings.reset_to_defaults()
        
        assert settings.get('show_mesh_default') == True

    def test_ui_to_dict(self):
        
        settings = UISettings()
        
        data = settings.to_dict()
        assert isinstance(data, dict)

    def test_ui_load_from_dict(self):
        
        settings = UISettings()
        
        data = {'show_mesh_default': False}
        settings.load_from_dict(data)
        
        assert settings.get('show_mesh_default') == False


class TestPluginSettings:
    

    def test_plugin_settings_creation(self):
        
        settings = PluginSettings()
        
        assert settings.keyboard is not None
        assert settings.mouse is not None
        assert settings.gizmo is not None
        assert settings.camera is not None
        assert settings.ui is not None

    def test_plugin_settings_with_custom_dir(self, tmp_path):
        
        settings = PluginSettings(settings_dir=str(tmp_path))
        
        settings_path = settings.get_settings_path()
        assert tmp_path.name in settings_path or str(tmp_path) in settings_path

    def test_plugin_settings_save(self, tmp_path):
        
        settings = PluginSettings(settings_dir=str(tmp_path))
        
        settings.camera.set('default_fov', 75.0)
        
        result = settings.save()
        assert result == True
        
        settings_path = settings.get_settings_path()
        assert os.path.exists(settings_path)

    def test_plugin_settings_load(self, tmp_path):
        
        settings_file = tmp_path / '3d_pose_settings.json'
        settings_data = {
            'version': '1.0',
            'camera': {'default_fov': 80.0},
            'keyboard': {},
            'mouse': {},
            'gizmo': {},
            'ui': {}
        }
        
        with open(settings_file, 'w') as f:
            json.dump(settings_data, f)
        
        settings = PluginSettings(settings_dir=str(tmp_path))
        result = settings.load()
        
        assert result == True
        assert (settings.camera.get('default_fov') - 80.0) < 0.01

    def test_plugin_settings_load_file_not_found(self, tmp_path):
        
        settings = PluginSettings(settings_dir=str(tmp_path))
        
        result = settings.load()
        
        assert result == False

    def test_plugin_settings_load_invalid_json(self, tmp_path):
        
        settings_file = tmp_path / '3d_pose_settings.json'
        
        with open(settings_file, 'w') as f:
            f.write("{ invalid json }")
        
        settings = PluginSettings(settings_dir=str(tmp_path))
        result = settings.load()
        
        assert result == False

    def test_plugin_settings_reset_all(self, tmp_path):
        
        settings = PluginSettings(settings_dir=str(tmp_path))
        
        settings.camera.set('default_fov', 120.0)
        settings.gizmo.set('base_scale', 5.0)
        
        settings.reset_all_to_defaults()
        
        assert abs(settings.camera.get('default_fov') - 120.0) > 0.01
        assert abs(settings.gizmo.get('base_scale') - 5.0) > 0.01

    def test_plugin_settings_export_import(self, tmp_path):
        
        settings = PluginSettings(settings_dir=str(tmp_path))
        
        settings.camera.set('default_fov', 70.0)
        
        export_file = tmp_path / 'exported_settings.json'
        result = settings.export_to_file(str(export_file))
        assert result == True
        
        new_settings = PluginSettings(settings_dir=str(tmp_path))
        result = new_settings.import_from_file(str(export_file))
        assert result == True
        
        assert (new_settings.camera.get('default_fov') - 70.0)  < 0.01

    def test_plugin_settings_notifier(self):
        
        settings = PluginSettings()
        
        notifier = settings.notifier
        assert notifier is not None
        assert hasattr(notifier, 'settings_changed')

    def test_plugin_settings_is_modified(self, tmp_path):
        
        settings = PluginSettings(settings_dir=str(tmp_path))
        
        settings.reset_all_to_defaults()
        assert settings.is_modified() == True
        
        settings.save()
        assert settings.is_modified() == False


class TestSettingsChangeNotifier:
    

    def test_notifier_creation(self):
        
        notifier = SettingsChangeNotifier()
        
        assert notifier is not None

    def test_notifier_has_signals(self):
        
        notifier = SettingsChangeNotifier()
        
        assert hasattr(notifier, 'settings_changed')
        assert hasattr(notifier, 'key_binding_changed')
        assert hasattr(notifier, 'setting_changed')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

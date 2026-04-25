

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Any, List, Callable
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal, QObject

from .defaults import (
    DEFAULT_KEYBOARD_SHORTCUTS,
    DEFAULT_MOUSE_SETTINGS,
    DEFAULT_GIZMO_SETTINGS,
    DEFAULT_CAMERA_SETTINGS,
    DEFAULT_UI_SETTINGS,
    SETTINGS_VERSION,
    KEYBOARD_ACTION_NAMES,
    GIZMO_COLOR_SCHEMES,
    UI_THEMES,
)
from .key_bindings import KeyBinding, MouseBinding, find_binding_conflicts


class SettingsChangeNotifier(QObject):

    settings_changed = pyqtSignal(str, object)  # category, settings_dict
    key_binding_changed = pyqtSignal(str, KeyBinding)  # action, binding
    setting_changed = pyqtSignal(str, str, object)  # category, key, value


class KeyboardSettings:

    
    def __init__(self):
        
        self._shortcuts: Dict[str, KeyBinding] = {}
        self._load_defaults()
    
    def _load_defaults(self) -> None:
        
        for action, (key, modifiers) in DEFAULT_KEYBOARD_SHORTCUTS.items():
            self._shortcuts[action] = KeyBinding(
                key=key,
                modifiers=modifiers,
                action=action
            )
    
    def get_binding(self, action: str) -> Optional[KeyBinding]:

        return self._shortcuts.get(action)
    
    def get_key(self, action: str) -> int:
        
        binding = self._shortcuts.get(action)
        return binding.key if binding else Qt.Key_unknown
    
    def get_modifiers(self, action: str) -> int:
        
        binding = self._shortcuts.get(action)
        return binding.modifiers if binding else Qt.NoModifier
    
    def set_binding(self, action: str, key: int, modifiers: int) -> None:

        self._shortcuts[action] = KeyBinding(
            key=key,
            modifiers=modifiers,
            action=action
        )
    
    def set_binding_from_keybinding(self, action: str, binding: KeyBinding) -> None:
        
        binding.action = action
        self._shortcuts[action] = binding
    
    def matches(self, action: str, key: int, modifiers: int) -> bool:

        binding = self._shortcuts.get(action)
        if binding is None:
            return False
        return binding.matches(key, modifiers)
    
    def get_all_bindings(self) -> Dict[str, KeyBinding]:
        
        return dict(self._shortcuts)
    
    def get_action_name(self, action: str) -> str:
        
        return KEYBOARD_ACTION_NAMES.get(action, action)
    
    def find_conflicts(self) -> List[tuple]:
        
        return find_binding_conflicts(self._shortcuts)
    
    def reset_to_defaults(self) -> None:
        
        self._shortcuts.clear()
        self._load_defaults()
    
    def to_dict(self) -> Dict[str, Any]:
        
        return {
            action: binding.to_dict()
            for action, binding in self._shortcuts.items()
        }
    
    def load_from_dict(self, data: Dict[str, Any]) -> None:
        
        for action, binding_data in data.items():
            if action in DEFAULT_KEYBOARD_SHORTCUTS:
                self._shortcuts[action] = KeyBinding.from_dict(binding_data)


class MouseSettings:

    
    def __init__(self):
        
        self._settings: Dict[str, Any] = dict(DEFAULT_MOUSE_SETTINGS)
        self._bindings: Dict[str, MouseBinding] = {}
        self._load_bindings()
    
    def _load_bindings(self) -> None:
        
        binding_keys = [
            'rotate_binding', 'rotate_binding_alt',
            'pan_binding', 'pan_binding_alt',
            'zoom_binding'
        ]
        for key in binding_keys:
            if key in self._settings:
                data = self._settings[key]
                self._bindings[key] = MouseBinding(
                    button=data.get('button', Qt.NoButton),
                    modifiers=data.get('modifiers', Qt.NoModifier),
                    action=key
                )
    
    def get_sensitivity(self, sensitivity_type: str) -> float:
        
        return self._settings.get(f'{sensitivity_type}_sensitivity', 1.0)
    
    def set_sensitivity(self, sensitivity_type: str, value: float) -> None:
        
        self._settings[f'{sensitivity_type}_sensitivity'] = value
    
    def get_binding(self, binding_name: str) -> Optional[MouseBinding]:
        
        return self._bindings.get(binding_name)
    
    def matches_binding(self, binding_name: str, button: int, modifiers: int) -> bool:
        
        binding = self._bindings.get(binding_name)
        if binding is None:
            return False
        return binding.matches(button, modifiers)
    
    def get_scroll_zoom_speed(self) -> float:

        return self._settings.get('scroll_zoom_speed', 0.1)

    def set_scroll_zoom_speed(self, value: float) -> None:

        self._settings['scroll_zoom_speed'] = value

    def get_scroll_dolly_speed(self) -> float:

        return self._settings.get('scroll_dolly_speed', 0.2)

    def set_scroll_dolly_speed(self, value: float) -> None:

        self._settings['scroll_dolly_speed'] = value
    
    def reset_to_defaults(self) -> None:
        
        self._settings = dict(DEFAULT_MOUSE_SETTINGS)
        self._bindings.clear()
        self._load_bindings()
    
    def to_dict(self) -> Dict[str, Any]:
        
        result = dict(self._settings)
        for name, binding in self._bindings.items():
            result[name] = binding.to_dict()
        return result
    
    def load_from_dict(self, data: Dict[str, Any]) -> None:
        
        self._settings = dict(DEFAULT_MOUSE_SETTINGS)
        self._settings.update(data)
        self._bindings.clear()
        self._load_bindings()


class GizmoSettings:


    def __init__(self, notifier: Optional[SettingsChangeNotifier] = None):
        
        self._settings: Dict[str, Any] = dict(DEFAULT_GIZMO_SETTINGS)
        self._notifier = notifier

    def _set_notifier(self, notifier: SettingsChangeNotifier) -> None:
        
        self._notifier = notifier

    def get(self, key: str, default: Any = None) -> Any:
        
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        
        self._settings[key] = value
        if self._notifier:
            self._notifier.setting_changed.emit('gizmo', key, value)

    def get_scale_params(self) -> tuple:
        return (
            self._settings.get('base_scale', 1.0),
            self._settings.get('min_scale', 0.05),
            self._settings.get('max_scale', 2.0)
        )

    def get_display_scale(self) -> float:
        return self._settings.get('display_scale', 0.15)

    def get_joint_display_scale(self) -> float:
        return self._settings.get('joint_display_scale', 0.15)

    def get_sensitivity(self, mode: str) -> float:
        return self._settings.get(f'{mode}_sensitivity', 1.0)

    def get_colors(self) -> Dict[str, str]:
        scheme_name = self._settings.get('color_scheme', 'blender')
        return GIZMO_COLOR_SCHEMES.get(scheme_name, GIZMO_COLOR_SCHEMES['blender'])

    def get_color_schemes(self) -> Dict[str, Dict[str, str]]:
        return dict(GIZMO_COLOR_SCHEMES)

    def reset_to_defaults(self) -> None:
        self._settings = dict(DEFAULT_GIZMO_SETTINGS)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._settings)

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        self._settings = dict(DEFAULT_GIZMO_SETTINGS)
        self._settings.update(data)


class CameraSettings:
    def __init__(self, notifier: Optional[SettingsChangeNotifier] = None):
        self._settings: Dict[str, Any] = dict(DEFAULT_CAMERA_SETTINGS)
        self._notifier = notifier

    def _set_notifier(self, notifier: SettingsChangeNotifier) -> None:
        self._notifier = notifier

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
        if self._notifier:
            self._notifier.setting_changed.emit('camera', key, value)
    
    def get_fov_params(self) -> tuple:
        return (
            self._settings.get('default_fov', 45.0),
            self._settings.get('min_fov', 30.0),
            self._settings.get('max_fov', 120.0)
        )
    
    def get_distance_params(self) -> tuple:
        return (
            self._settings.get('default_distance', 3.0),
            self._settings.get('min_distance', 0.5),
            self._settings.get('max_distance', 20.0)
        )
    
    def get_speed(self, speed_type: str) -> float:
        return self._settings.get(f'{speed_type}_speed', 0.01)
    
    def reset_to_defaults(self) -> None:
        self._settings = dict(DEFAULT_CAMERA_SETTINGS)
    
    def to_dict(self) -> Dict[str, Any]:
        return dict(self._settings)
    
    def load_from_dict(self, data: Dict[str, Any]) -> None:
        self._settings = dict(DEFAULT_CAMERA_SETTINGS)
        self._settings.update(data)


class UISettings:

    def __init__(self, notifier: Optional[SettingsChangeNotifier] = None):
        self._settings: Dict[str, Any] = dict(DEFAULT_UI_SETTINGS)
        self._notifier = notifier

    def _set_notifier(self, notifier: SettingsChangeNotifier) -> None:
        self._notifier = notifier

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
        if self._notifier:
            self._notifier.setting_changed.emit('ui', key, value)

    def get_default_visibility(self) -> Dict[str, bool]:
        return {
            'mesh': self._settings.get('show_mesh_default', True),
            'skeleton': self._settings.get('show_skeleton_default', True),
            'joints': self._settings.get('show_joints_default', True),
            'gizmo': self._settings.get('show_gizmo_default', True),
        }

    def get_theme_colors(self) -> Dict[str, str]:
        theme_name = self._settings.get('theme', 'dark')
        return UI_THEMES.get(theme_name, UI_THEMES['dark'])

    def get_themes(self) -> Dict[str, Dict[str, str]]:
        return dict(UI_THEMES)

    def get_silhouette_mode(self) -> bool:
        return self._settings.get('silhouette_mode', False)

    def set_silhouette_mode(self, enabled: bool) -> None:
        self.set('silhouette_mode', enabled)

    def get_silhouette_color(self) -> str:
        return self._settings.get('silhouette_color', '#595959')

    def set_silhouette_color(self, color: str) -> None:
        self.set('silhouette_color', color)

    def get_outline_width(self) -> float:
        return self._settings.get('outline_width', 0.005)

    def set_outline_width(self, width: float) -> None:
        self.set('outline_width', width)

    def reset_to_defaults(self) -> None:
        self._settings = dict(DEFAULT_UI_SETTINGS)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._settings)

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        self._settings = dict(DEFAULT_UI_SETTINGS)
        self._settings.update(data)


class PluginSettings:
    
    def __init__(self, settings_dir: Optional[str] = None):
        self._settings_dir = settings_dir
        self._notifier = SettingsChangeNotifier()

        self.keyboard = KeyboardSettings()
        self.mouse = MouseSettings()
        self.gizmo = GizmoSettings(self._notifier)
        self.camera = CameraSettings(self._notifier)
        self.ui = UISettings(self._notifier)

        self._modified = False

        self._settings_path: Optional[str] = None
    
    @property
    def notifier(self) -> SettingsChangeNotifier:
        return self._notifier
    
    def get_settings_path(self) -> str:
        if self._settings_path is not None:
            return self._settings_path

        if self._settings_dir:
            settings_dir = Path(self._settings_dir)
        else:
            # Use a simple fallback that doesn't require Krita.instance()
            # This avoids interfering with Krita's window initialization
            settings_dir = Path.home() / '.local' / 'share' / 'krita_3d_pose'

        settings_dir.mkdir(parents=True, exist_ok=True)

        self._settings_path = str(settings_dir / '3d_pose_settings.json')
        return self._settings_path
    
    def load(self) -> bool:
        settings_path = self.get_settings_path()
        
        if not os.path.exists(settings_path):
            return False
        
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'keyboard' in data:
                self.keyboard.load_from_dict(data['keyboard'])
            if 'mouse' in data:
                self.mouse.load_from_dict(data['mouse'])
            if 'gizmo' in data:
                self.gizmo.load_from_dict(data['gizmo'])
            if 'camera' in data:
                self.camera.load_from_dict(data['camera'])
            if 'ui' in data:
                self.ui.load_from_dict(data['ui'])
            
            self._modified = False
            return True
            
        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Error loading settings: {e}")
            return False
    
    def save(self) -> bool:
        settings_path = self.get_settings_path()
        
        try:
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            
            data = {
                'version': SETTINGS_VERSION,
                'keyboard': self.keyboard.to_dict(),
                'mouse': self.mouse.to_dict(),
                'gizmo': self.gizmo.to_dict(),
                'camera': self.camera.to_dict(),
                'ui': self.ui.to_dict(),
            }
            
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            self._modified = False
            return True
            
        except (IOError, OSError) as e:
            print(f"Error saving settings: {e}")
            return False
    
    def reset_all_to_defaults(self) -> None:
        self.keyboard.reset_to_defaults()
        self.mouse.reset_to_defaults()
        self.gizmo.reset_to_defaults()
        self.camera.reset_to_defaults()
        self.ui.reset_to_defaults()
        self._modified = True
    
    def is_modified(self) -> bool:
        return self._modified
    
    def export_to_file(self, filepath: str) -> bool:
        try:
            data = {
                'version': SETTINGS_VERSION,
                'keyboard': self.keyboard.to_dict(),
                'mouse': self.mouse.to_dict(),
                'gizmo': self.gizmo.to_dict(),
                'camera': self.camera.to_dict(),
                'ui': self.ui.to_dict(),
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except (IOError, OSError) as e:
            print(f"Error exporting settings: {e}")
            return False
    
    def import_from_file(self, filepath: str) -> bool:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'keyboard' in data:
                self.keyboard.load_from_dict(data['keyboard'])
            if 'mouse' in data:
                self.mouse.load_from_dict(data['mouse'])
            if 'gizmo' in data:
                self.gizmo.load_from_dict(data['gizmo'])
            if 'camera' in data:
                self.camera.load_from_dict(data['camera'])
            if 'ui' in data:
                self.ui.load_from_dict(data['ui'])
            
            self._modified = True
            return True
            
        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Error importing settings: {e}")
            return False

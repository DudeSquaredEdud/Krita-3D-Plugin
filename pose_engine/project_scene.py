

import os
import json
import hashlib
import copy
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field

from .scene import Scene


@dataclass
class SceneSettings:
    idle_save_delay: float = 5.0
    continuous_save_interval: float = 60.0
    max_backup_files: int = 5
    compress_output: bool = False
    enable_diff_save: bool = True


@dataclass
class SceneMetadata:
    name: str = "Untitled Scene"
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0"
    krita_project: Optional[str] = None
    checksum: str = ""


class ProjectScene:


    SCENE_EXTENSION = ".k3dscene"

    def __init__(self, scene: Optional[Scene] = None):
        self._scene = scene or Scene()
        self._settings = SceneSettings()
        self._metadata = SceneMetadata()
        self._camera_bookmarks: Dict[str, dict] = {}

        self._last_saved_state: Optional[Dict[str, Any]] = None
        self._last_save_time: Optional[datetime] = None
        self._has_unsaved_changes = False
        self._change_count = 0

        self._scene_file_path: Optional[str] = None
        self._krita_project_path: Optional[str] = None

        self._current_state_hash: str = ""

        self._callbacks: Dict[str, List[Callable]] = {
            'scene_saved': [],
            'scene_loaded': [],
            'save_error': [],
            'load_error': [],
            'scene_changed': [],
            'auto_save_triggered': [],
            'bookmarks_loaded': [],
            'pre_save': [],
        }

        self._idle_timer: Optional[threading.Timer] = None
        self._continuous_timer: Optional[threading.Timer] = None
        self._stop_event = threading.Event()

    def add_callback(self, event: str, callback: Callable) -> None:

        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def remove_callback(self, event: str, callback: Callable) -> None:

        if event in self._callbacks:
            try:
                self._callbacks[event].remove(callback)
            except ValueError:
                pass

    def _emit(self, event: str, *args) -> None:

        for callback in self._callbacks.get(event, []):
            try:
                callback(*args)
            except Exception:
                pass

    @property
    def scene(self) -> Scene:
        return self._scene

    @property
    def has_unsaved_changes(self) -> bool:
        return self._has_unsaved_changes

    @property
    def scene_file_path(self) -> Optional[str]:
        return self._scene_file_path

    @property
    def krita_project_path(self) -> Optional[str]:
        return self._krita_project_path

    @property
    def settings(self) -> SceneSettings:
        return self._settings

    @settings.setter
    def settings(self, value: SceneSettings):
        self._settings = value

    def mark_changed(self):
        print("DEBUG: UNSAVED CHANGES")
        
        self._has_unsaved_changes = True
        self._change_count += 1
        self._metadata.modified_at = datetime.now()

        self._restart_idle_timer()

        if self._continuous_timer is None or not self._continuous_timer.is_alive():
            self._restart_continuous_timer()

        self._emit('scene_changed')

    def _restart_idle_timer(self) -> None:
        
        if self._idle_timer is not None:
            self._idle_timer.cancel()

        self._idle_timer = threading.Timer(
            self._settings.idle_save_delay,
            self._on_idle_save
        )
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _restart_continuous_timer(self) -> None:
        
        if self._continuous_timer is not None:
            self._continuous_timer.cancel()

        self._continuous_timer = threading.Timer(
            self._settings.continuous_save_interval,
            self._on_continuous_save
        )
        self._continuous_timer.daemon = True
        self._continuous_timer.start()

    def _stop_timers(self) -> None:
        
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None

        if self._continuous_timer is not None:
            self._continuous_timer.cancel()
            self._continuous_timer = None

    def _on_idle_save(self):
        if self._has_unsaved_changes and self._scene_file_path:
            self._do_auto_save("idle")

    def _on_continuous_save(self):
        if self._has_unsaved_changes and self._scene_file_path:
            self._do_auto_save("continuous")

    def _do_auto_save(self, trigger: str):
        if not self._scene_file_path:
            return

        try:
            self.save(self._scene_file_path, create_backup=True)
            self._change_count = 0
            self._emit('auto_save_triggered')
            print(f"[ProjectScene] Auto-saved ({trigger} trigger)")
        except Exception as e:
            self._emit('save_error', f"Auto-save failed: {e}")
            print(f"[ProjectScene] Auto-save failed: {e}")

    def _compute_state_hash(self, state: Dict[str, Any]) -> str:
        state_str = json.dumps(state, sort_keys=True)
        return hashlib.md5(state_str.encode()).hexdigest()

    def _get_current_state(self) -> Dict[str, Any]:
        return self._scene.to_dict()

    def _compute_diff(self, current: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Any]:
        diff = {
            'version': current.get('version'),
            'timestamp': datetime.now().isoformat(),
            'changes': {}
        }

        current_models = current.get('models', {})
        previous_models = previous.get('models', {})

        for model_id in current_models:
            if model_id not in previous_models:
                diff['changes'][model_id] = {'action': 'added', 'data': current_models[model_id]}

        for model_id in previous_models:
            if model_id not in current_models:
                diff['changes'][model_id] = {'action': 'removed'}

        for model_id in current_models:
            if model_id in previous_models:
                current_model = current_models[model_id]
                previous_model = previous_models[model_id]

                model_diff = self._diff_model(current_model, previous_model)
                if model_diff:
                    diff['changes'][model_id] = {'action': 'modified', 'data': model_diff}

        if current.get('selected_model_id') != previous.get('selected_model_id'):
            diff['selected_model_id'] = current.get('selected_model_id')
        if current.get('selected_bone_name') != previous.get('selected_bone_name'):
            diff['selected_bone_name'] = current.get('selected_bone_name')

        return diff if diff['changes'] or 'selected_model_id' in diff or 'selected_bone_name' in diff else None

    def _diff_model(self, current: Dict[str, Any], previous: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        diff = {}

        current_transform = current.get('transform', {})
        previous_transform = previous.get('transform', {})

        if current_transform != previous_transform:
            diff['transform'] = current_transform

        if current.get('visible') != previous.get('visible'):
            diff['visible'] = current.get('visible')

        current_bones = current.get('bones', {})
        previous_bones = previous.get('bones', {})

        bone_changes = {}
        for bone_name in set(current_bones.keys()) | set(previous_bones.keys()):
            if bone_name not in current_bones:
                bone_changes[bone_name] = {'action': 'removed'}
            elif bone_name not in previous_bones:
                bone_changes[bone_name] = {'action': 'added', 'data': current_bones[bone_name]}
            elif current_bones[bone_name] != previous_bones[bone_name]:
                bone_changes[bone_name] = {'action': 'modified', 'data': current_bones[bone_name]}

        if bone_changes:
            diff['bones'] = bone_changes

        if current.get('parent_id') != previous.get('parent_id'):
            diff['parent_id'] = current.get('parent_id')
        if current.get('parent_bone') != previous.get('parent_bone'):
            diff['parent_bone'] = current.get('parent_bone')

        return diff if diff else None


    def pre_save_bookmarks_update(self, bookmarks: Dict[str, dict]) -> None:
        self._camera_bookmarks = bookmarks

    def save(self, file_path: Optional[str] = None, create_backup: bool = False) -> bool:
        if file_path is None:
            file_path = self._scene_file_path

        if not file_path:
            self._emit('save_error', "No file path specified")
            return False

        if not file_path.endswith(self.SCENE_EXTENSION):
            file_path = file_path + self.SCENE_EXTENSION

        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            if create_backup and os.path.exists(file_path):
                self._create_backup(file_path)

            self._emit('pre_save', file_path)

            current_state = self._get_current_state()

            save_data = {
                'metadata': {
                    'name': self._metadata.name,
                    'created_at': self._metadata.created_at.isoformat(),
                    'modified_at': datetime.now().isoformat(),
                    'version': self._metadata.version,
                    'krita_project': self._krita_project_path,
                },
                'scene': current_state,
                'camera_bookmarks': self._camera_bookmarks
            }

            with open(file_path, 'w') as f:
                json.dump(save_data, f, indent=2)

            self._last_saved_state = copy.deepcopy(current_state)
            self._last_save_time = datetime.now()
            self._has_unsaved_changes = False
            self._current_state_hash = self._compute_state_hash(current_state)
            self._scene_file_path = file_path

            self._stop_timers()

            self._emit('scene_saved', file_path)
            return True

        except Exception as e:
            self._emit('save_error', str(e))
            return False

    def save_for_krita_project(self, krita_project_path: str) -> bool:
        base_name = os.path.splitext(os.path.basename(krita_project_path))[0]
        scene_dir = os.path.dirname(krita_project_path)
        scene_path = os.path.join(scene_dir, base_name + self.SCENE_EXTENSION)

        self._krita_project_path = krita_project_path
        self._metadata.krita_project = krita_project_path
        self._metadata.name = base_name

        return self.save(scene_path, create_backup=True)

    def _create_backup(self, file_path: str):
        if not os.path.exists(file_path):
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(os.path.dirname(file_path), 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        base_name = os.path.basename(file_path)
        backup_name = f"{os.path.splitext(base_name)[0]}_{timestamp}{self.SCENE_EXTENSION}"
        backup_path = os.path.join(backup_dir, backup_name)

        import shutil
        shutil.copy2(file_path, backup_path)

        self._cleanup_backups(backup_dir)

    def _cleanup_backups(self, backup_dir: str):
        if not os.path.exists(backup_dir):
            return

        backups = []
        for f in os.listdir(backup_dir):
            if f.endswith(self.SCENE_EXTENSION):
                full_path = os.path.join(backup_dir, f)
                backups.append((full_path, os.path.getmtime(full_path)))

        backups.sort(key=lambda x: x[1], reverse=True)

        for backup_path, _ in backups[self._settings.max_backup_files:]:
            try:
                os.remove(backup_path)
            except Exception as e:
                print(f"[ProjectScene] Failed to remove old backup {backup_path}: {e}")


    def load(self, file_path: str) -> bool:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            if 'metadata' in data:
                meta = data['metadata']
                self._metadata.name = meta.get('name', 'Untitled Scene')
                if 'created_at' in meta:
                    self._metadata.created_at = datetime.fromisoformat(meta['created_at'])
                if 'modified_at' in meta:
                    self._metadata.modified_at = datetime.fromisoformat(meta['modified_at'])
                self._metadata.version = meta.get('version', '1.0')
                self._krita_project_path = meta.get('krita_project')

            if 'scene' in data:
                scene_data = data['scene']
            else:
                scene_data = data

            base_path = os.path.dirname(file_path)
            self._scene.from_dict(scene_data, base_path)

            if 'camera_bookmarks' in data:
                self._camera_bookmarks = data['camera_bookmarks']
                self._emit('bookmarks_loaded', self._camera_bookmarks)

            self._last_saved_state = copy.deepcopy(scene_data)
            self._last_save_time = datetime.now()
            self._has_unsaved_changes = False
            self._current_state_hash = self._compute_state_hash(scene_data)
            self._scene_file_path = file_path

            self._emit('scene_loaded', file_path)
            return True

        except Exception as e:
            self._emit('load_error', str(e))
            return False

    def load_for_krita_project(self, krita_project_path: str) -> bool:
        base_name = os.path.splitext(os.path.basename(krita_project_path))[0]
        scene_dir = os.path.dirname(krita_project_path)
        scene_path = os.path.join(scene_dir, base_name + self.SCENE_EXTENSION)

        if os.path.exists(scene_path):
            return self.load(scene_path)
        else:
            self._krita_project_path = krita_project_path
            self._metadata.krita_project = krita_project_path
            self._metadata.name = base_name
            self._scene_file_path = scene_path
            return False


    def export_full(self, export_path: str, include_models: bool = True) -> bool:
        try:
            export_dir = os.path.splitext(export_path)[0] + '_export'
            os.makedirs(export_dir, exist_ok=True)

            model_mapping = {}
            if include_models:
                models_dir = os.path.join(export_dir, 'models')
                os.makedirs(models_dir, exist_ok=True)

                for model in self._scene.get_all_models():
                    if model.source_file and os.path.exists(model.source_file):
                        model_name = os.path.basename(model.source_file)
                        export_model_path = os.path.join(models_dir, model_name)

                        import shutil
                        shutil.copy2(model.source_file, export_model_path)

                        model_mapping[model.source_file] = f"models/{model_name}"

            manifest = {
                'version': '1.0',
                'exported_at': datetime.now().isoformat(),
                'metadata': {
                    'name': self._metadata.name,
                    'krita_project': self._metadata.krita_project,
                },
                'scene': self._scene.to_dict(),
                'model_files': model_mapping,
            }

            for _, model_data in manifest['scene'].get('models', {}).items():
                original_path = model_data.get('source_file')
                if original_path in model_mapping:
                    model_data['source_file'] = model_mapping[original_path]

            manifest_path = os.path.join(export_dir, 'manifest.json')
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)

            import shutil
            archive_path = shutil.make_archive(
                export_path.replace('.zip', ''),
                'zip',
                export_dir
            )

            print(f"[ProjectScene] Exported to {archive_path}")
            return True

        except Exception as e:
            self._emit('save_error', f"Export failed: {e}")
            return False

    def import_full(self, import_path: str) -> bool:
        try:
            import tempfile
            import shutil

            extract_dir = tempfile.mkdtemp()
            shutil.unpack_archive(import_path, extract_dir)

            manifest_path = os.path.join(extract_dir, 'manifest.json')
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            for _, model_data in manifest['scene'].get('models', {}).items():
                source_file = model_data.get('source_file')
                if source_file and source_file.startswith('models/'):
                    model_data['source_file'] = os.path.join(extract_dir, source_file)

            self._scene.from_dict(manifest['scene'], extract_dir)

            if 'metadata' in manifest:
                self._metadata.name = manifest['metadata'].get('name', 'Imported Scene')
                self._krita_project_path = manifest['metadata'].get('krita_project')

            self._has_unsaved_changes = True
            self.mark_changed()

            shutil.rmtree(extract_dir, ignore_errors=True)

            return True

        except Exception as e:
            self._emit('load_error', f"Import failed: {e}")
            return False


    def new_scene(self):
        
        self._scene._models.clear()
        self._scene._model_order.clear()
        self._scene._selected_model_id = None
        self._scene._selected_bone_name = None

        self._metadata = SceneMetadata()
        self._last_saved_state = None
        self._last_save_time = None
        self._has_unsaved_changes = False
        self._scene_file_path = None
        self._krita_project_path = None
        self._camera_bookmarks = {}

        self._stop_timers()

        self._emit('scene_changed')


    def set_camera_bookmarks(self, bookmarks: Dict[str, dict], mark_dirty: bool = True) -> None:
        self._camera_bookmarks = bookmarks
        if mark_dirty:
            self.mark_changed()

    def get_camera_bookmarks(self) -> Dict[str, dict]:
        return self._camera_bookmarks.copy()

    def update_camera_bookmark(self, slot: int, bookmark_data: dict) -> None:
        self._camera_bookmarks[str(slot)] = bookmark_data
        self.mark_changed()

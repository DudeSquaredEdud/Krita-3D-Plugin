

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pose_engine.ui.multi_viewport import Camera


@dataclass
class CameraBookmark:
    name: str
    slot: int # 1-9 for quick keys

    target: tuple
    distance: float
    yaw: float
    pitch: float

    fov: float
    near: float = 0.1
    far: float = 100.0

    mode: str = 'orbit'
    head_position: tuple = (0, 1.5, 3)
    head_yaw: float = 0.0
    head_pitch: float = 0.0

    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'slot': self.slot,
            'target': {'x': self.target[0], 'y': self.target[1], 'z': self.target[2]},
            'distance': self.distance,
            'yaw': self.yaw,
            'pitch': self.pitch,
            'fov': self.fov,
            'near': self.near,
            'far': self.far,
            'mode': self.mode,
            'head_position': {'x': self.head_position[0], 'y': self.head_position[1], 'z': self.head_position[2]},
            'head_yaw': self.head_yaw,
            'head_pitch': self.head_pitch,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CameraBookmark':
        target_data = data['target']
        if isinstance(target_data, dict):
            target = (target_data['x'], target_data['y'], target_data['z'])
        else:
            target = tuple(target_data)

        head_pos_data = data.get('head_position', (0, 1.5, 3))
        if isinstance(head_pos_data, dict):
            head_position = (head_pos_data['x'], head_pos_data['y'], head_pos_data['z'])
        else:
            head_position = tuple(head_pos_data) if head_pos_data else (0, 1.5, 3)

        return cls(
            name=data['name'],
            slot=data['slot'],
            target=target,
            distance=data['distance'],
            yaw=data['yaw'],
            pitch=data['pitch'],
            fov=data['fov'],
            near=data.get('near', 0.1),
            far=data.get('far', 100.0),
            mode=data.get('mode', 'orbit'),
            head_position=head_position,
            head_yaw=data.get('head_yaw', 0.0),
            head_pitch=data.get('head_pitch', 0.0),
            created_at=datetime.fromisoformat(data['created_at']),
            modified_at=datetime.fromisoformat(data['modified_at']),
        )

    def get_summary(self) -> str:
        if self.mode == 'head_look':
            return f"FOV:{self.fov:.0f}deg Head:({self.head_position[0]:.1f}, {self.head_position[1]:.1f}, {self.head_position[2]:.1f})"
        return f"FOV:{self.fov:.0f}deg Dist:{self.distance:.1f} Target:({self.target[0]:.1f}, {self.target[1]:.1f}, {self.target[2]:.1f})"


class CameraBookmarkManager:

    
    MAX_BOOKMARKS = 9  # Slots 1-9 for quick keys
    BOOKMARKS_FILE = 'camera_bookmarks.json'
    
    def __init__(self, settings_dir: Optional[Path] = None):
        self._bookmarks: Dict[int, CameraBookmark] = {}
        self._settings_dir = Path(settings_dir) if settings_dir else None
        self._load_bookmarks()
    
    def _get_bookmarks_path(self) -> Optional[Path]:
        if self._settings_dir is None:
            return None
        return self._settings_dir / self.BOOKMARKS_FILE
    
    def _load_bookmarks(self) -> None:
        bookmarks_path = self._get_bookmarks_path()
        if bookmarks_path is None or not bookmarks_path.exists():
            return
        
        try:
            with open(bookmarks_path, 'r') as f:
                data = json.load(f)
            
            for slot_str, bookmark_data in data.items():
                slot = int(slot_str)
                if 1 <= slot <= self.MAX_BOOKMARKS:
                    self._bookmarks[slot] = CameraBookmark.from_dict(bookmark_data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"[CameraBookmarkManager] Error loading bookmarks: {e}")
    
    def _save_bookmarks(self) -> None:
        bookmarks_path = self._get_bookmarks_path()
        if bookmarks_path is None:
            return
        
        bookmarks_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            str(slot): bookmark.to_dict()
            for slot, bookmark in self._bookmarks.items()
        }
        
        try:
            with open(bookmarks_path, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"[CameraBookmarkManager] Error saving bookmarks: {e}")
    
    def save_bookmark(self, slot: int, camera: Any, name: Optional[str] = None) -> CameraBookmark:
        if slot < 1 or slot > self.MAX_BOOKMARKS:
            raise ValueError(f"Slot must be 1-{self.MAX_BOOKMARKS}")

        target = camera.target
        if hasattr(target, 'x'):
            target_tuple = (target.x, target.y, target.z)
        else:
            target_tuple = tuple(target)

        # Determine camera mode and capture head-look state if applicable
        is_head_look = getattr(camera, '_head_look_mode', False)
        mode = 'head_look' if is_head_look else 'orbit'

        head_pos = getattr(camera, '_head_position', None)
        if head_pos is not None and hasattr(head_pos, 'x'):
            head_position = (head_pos.x, head_pos.y, head_pos.z)
        else:
            head_position = (0, 1.5, 3)

        head_yaw = getattr(camera, '_head_yaw', 0.0)
        head_pitch = getattr(camera, '_head_pitch', 0.0)

        existing = self._bookmarks.get(slot)
        if existing:
            created_at = existing.created_at
        else:
            created_at = datetime.now()

        bookmark = CameraBookmark(
            name=name or f"Bookmark {slot}",
            slot=slot,
            target=target_tuple,
            distance=camera.distance,
            yaw=camera.yaw,
            pitch=camera.pitch,
            fov=camera.fov,
            near=getattr(camera, 'near', 0.1),
            far=getattr(camera, 'far', 100.0),
            mode=mode,
            head_position=head_position,
            head_yaw=head_yaw,
            head_pitch=head_pitch,
            created_at=created_at,
            modified_at=datetime.now(),
        )

        self._bookmarks[slot] = bookmark
        self._save_bookmarks()

        return bookmark
    
    def load_bookmark(self, slot: int, camera: Any) -> bool:
        bookmark = self._bookmarks.get(slot)
        if bookmark is None:
            return False

        target = bookmark.target
        if hasattr(camera.target, 'x'):
            from pose_engine.vec3 import Vec3
            camera.target = Vec3(target[0], target[1], target[2])
        else:
            camera.target = target

        camera.distance = bookmark.distance
        camera.yaw = bookmark.yaw
        camera.pitch = bookmark.pitch
        camera.fov = bookmark.fov

        if hasattr(camera, 'near'):
            camera.near = bookmark.near
        if hasattr(camera, 'far'):
            camera.far = bookmark.far

        if bookmark.mode == 'head_look' and hasattr(camera, '_head_position'):
            from pose_engine.vec3 import Vec3
            hp = bookmark.head_position
            camera._head_position = Vec3(hp[0], hp[1], hp[2])
            camera._head_yaw = bookmark.head_yaw
            camera._head_pitch = bookmark.head_pitch
            if hasattr(camera, '_head_look_mode'):
                camera._head_look_mode = True
        elif hasattr(camera, '_head_look_mode'):
            # Explicitly restore orbit mode if bookmark was saved in orbit mode
            camera._head_look_mode = False
    
        return True
    
    def get_bookmark(self, slot: int) -> Optional[CameraBookmark]:
        return self._bookmarks.get(slot)
    
    def get_all_bookmarks(self) -> Dict[int, CameraBookmark]:
        return dict(self._bookmarks)
    
    def delete_bookmark(self, slot: int) -> bool:
        if slot in self._bookmarks:
            del self._bookmarks[slot]
            self._save_bookmarks()
            return True
        return False
    
    def rename_bookmark(self, slot: int, new_name: str) -> bool:
        bookmark = self._bookmarks.get(slot)
        if bookmark is None:
            return False
        
        bookmark.name = new_name
        bookmark.modified_at = datetime.now()
        self._save_bookmarks()
        return True
    
    def has_bookmark(self, slot: int) -> bool:
        return slot in self._bookmarks
    
    def export_to_file(self, filepath: Path) -> bool:
        data = {
            str(slot): bookmark.to_dict()
            for slot, bookmark in self._bookmarks.items()
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except IOError as e:
            print(f"[CameraBookmarkManager] Error exporting bookmarks: {e}")
            return False
    
    def import_from_file(self, filepath: Path, merge: bool = True) -> int:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"[CameraBookmarkManager] Error importing bookmarks: {e}")
            return -1
        
        if not merge:
            self._bookmarks.clear()
        
        count = 0
        for slot_str, bookmark_data in data.items():
            slot = int(slot_str)
            if 1 <= slot <= self.MAX_BOOKMARKS:
                self._bookmarks[slot] = CameraBookmark.from_dict(bookmark_data)
                count += 1
        
        self._save_bookmarks()
        return count

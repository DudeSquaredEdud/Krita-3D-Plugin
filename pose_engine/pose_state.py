import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .quat import Quat
from .vec3 import Vec3
from .skeleton import Skeleton
from .bone import Bone


@dataclass
class BonePose:
    rotation: Quat = field(default_factory=Quat.identity)
    position: Vec3 = field(default_factory=lambda: Vec3(0, 0, 0))
    scale: Vec3 = field(default_factory=lambda: Vec3(1, 1, 1))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'rotation': list(self.rotation.to_tuple()),
            'position': list(self.position.to_tuple()),
            'scale': list(self.scale.to_tuple())
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BonePose':
        rot_data = data.get('rotation', [1, 0, 0, 0])
        pos_data = data.get('position', [0, 0, 0])
        scale_data = data.get('scale', [1, 1, 1])
        
        return cls(
            rotation=Quat(rot_data[0], rot_data[1], rot_data[2], rot_data[3]),
            position=Vec3(pos_data[0], pos_data[1], pos_data[2]),
            scale=Vec3(scale_data[0], scale_data[1], scale_data[2])
        )
    
    @classmethod
    def from_bone(cls, bone: Bone) -> 'BonePose':
        return cls(
            rotation=bone.pose_transform.rotation,
            position=bone.pose_transform.position,
            scale=bone.pose_transform.scale
        )
    
    def apply_to_bone(self, bone: Bone) -> None:
        bone.set_pose_rotation(self.rotation)
        bone.set_pose_position(self.position)
        bone.set_pose_scale(self.scale)


@dataclass
class PoseSnapshot:
    bones: Dict[str, BonePose] = field(default_factory=dict)
    name: str = ""
    timestamp: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'timestamp': self.timestamp,
            'bones': {name: pose.to_dict() for name, pose in self.bones.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PoseSnapshot':
        bones = {}
        for name, pose_data in data.get('bones', {}).items():
            bones[name] = BonePose.from_dict(pose_data)
        
        return cls(
            bones=bones,
            name=data.get('name', ''),
            timestamp=data.get('timestamp', 0.0)
        )
    
    @classmethod
    def capture_from_skeleton(cls, skeleton: Skeleton, name: str = "") -> 'PoseSnapshot':
        import time
        bones = {}
        for bone in skeleton:
            bones[bone.name] = BonePose.from_bone(bone)
        
        return cls(bones=bones, name=name, timestamp=time.time())
    
    def apply_to_skeleton(self, skeleton: Skeleton) -> None:
        for bone in skeleton:
            if bone.name in self.bones:
                self.bones[bone.name].apply_to_bone(bone)
        
        skeleton.update_all_transforms()
    
    def get_bone_pose(self, bone_name: str) -> Optional[BonePose]:
        return self.bones.get(bone_name)


class UndoRedoStack:    
    def __init__(self, max_history: int = 50):
        self._undo_stack: List[PoseSnapshot] = []
        self._redo_stack: List[PoseSnapshot] = []
        self._max_history = max_history
        self._current_snapshot: Optional[PoseSnapshot] = None
    
    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0
    
    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0
    
    @property
    def undo_count(self) -> int:
        return len(self._undo_stack)
    
    @property
    def redo_count(self) -> int:
        return len(self._redo_stack)
    
    def push_state(self, skeleton: Skeleton, name: str = "") -> None:
        snapshot = PoseSnapshot.capture_from_skeleton(skeleton, name)
        
        if self._current_snapshot is not None:
            self._undo_stack.append(self._current_snapshot)
            
            if len(self._undo_stack) > self._max_history:
                self._undo_stack.pop(0)
        
        self._current_snapshot = snapshot
        
        self._redo_stack.clear()
    
    def undo(self, skeleton: Skeleton) -> Optional[PoseSnapshot]:
        if not self.can_undo:
            return None
        
        if self._current_snapshot is not None:
            self._redo_stack.append(self._current_snapshot)
        
        self._current_snapshot = self._undo_stack.pop()
        
        self._current_snapshot.apply_to_skeleton(skeleton)
        
        return self._current_snapshot
    
    def redo(self, skeleton: Skeleton) -> Optional[PoseSnapshot]:
        if not self.can_redo:
            return None
        
        if self._current_snapshot is not None:
            self._undo_stack.append(self._current_snapshot)
        
        self._current_snapshot = self._redo_stack.pop()
        
        self._current_snapshot.apply_to_skeleton(skeleton)
        
        return self._current_snapshot
    
    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._current_snapshot = None
    
    def initialize(self, skeleton: Skeleton) -> None:
        self.clear()
        self._current_snapshot = PoseSnapshot.capture_from_skeleton(skeleton, "initial")


class PoseSerializer:
    
    @staticmethod
    def save_pose(filepath: str, skeleton: Skeleton, name: str = "") -> bool:
        try:
            snapshot = PoseSnapshot.capture_from_skeleton(skeleton, name)
            data = snapshot.to_dict()
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving pose: {e}")
            return False
    
    @staticmethod
    def load_pose(filepath: str, skeleton: Skeleton) -> Optional[PoseSnapshot]:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            snapshot = PoseSnapshot.from_dict(data)
            snapshot.apply_to_skeleton(skeleton)
            
            return snapshot
        except Exception as e:
            print(f"Error loading pose: {e}")
            return None
    
    @staticmethod
    def load_pose_data(filepath: str) -> Optional[PoseSnapshot]:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            return PoseSnapshot.from_dict(data)
        except Exception as e:
            print(f"Error loading pose data: {e}")
            return None
    
    @staticmethod
    def get_pose_info(filepath: str) -> Optional[Dict[str, Any]]:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            return {
                'name': data.get('name', ''),
                'timestamp': data.get('timestamp', 0.0),
                'bone_count': len(data.get('bones', {}))
            }
        except Exception as e:
            print(f"Error reading pose info: {e}")
            return None

from typing import List, Dict, Optional, Iterator
from .bone import Bone
from .vec3 import Vec3
from .quat import Quat


class Skeleton:
    
    def __init__(self):
        self._bones: List[Bone] = []
        self._bone_names: Dict[str, int] = {}
        self._root_bones: List[Bone] = []
    
    def __len__(self) -> int:
        return len(self._bones)
    
    def __iter__(self) -> Iterator[Bone]:
        return iter(self._bones)
    
    def __getitem__(self, index: int) -> Bone:
        return self._bones[index]
    
    # Bone Management
    
    def add_bone(self, name: str, parent_index: int = -1) -> Bone:
        index = len(self._bones)
        bone = Bone(name, index)
        
        self._bones.append(bone)
        self._bone_names[name] = index
        
        if parent_index >= 0 and parent_index < len(self._bones):
            parent = self._bones[parent_index]
            parent.add_child(bone)
        else:
            self._root_bones.append(bone)
        
        return bone
    
    def get_bone(self, name: str) -> Optional[Bone]:
        index = self._bone_names.get(name)
        if index is not None:
            return self._bones[index]
        return None
    
    def get_bone_by_index(self, index: int) -> Optional[Bone]:
        if 0 <= index < len(self._bones):
            return self._bones[index]
        return None
    
    def get_bone_index(self, name: str) -> int:
        return self._bone_names.get(name, -1)
    
    def get_root_bones(self) -> List[Bone]:
        return self._root_bones.copy()
    
    def get_all_bones(self) -> List[Bone]:
        return self._bones.copy()
    
    # Transform Updates
    
    def update_all_transforms(self) -> None:
        for root in self._root_bones:
            self._update_bone_recursive(root)
    
    def _update_bone_recursive(self, bone: Bone) -> None:
        
        bone.get_world_transform()
        
        for child in bone.children:
            self._update_bone_recursive(child)
    
    def mark_all_dirty(self) -> None:
        for bone in self._bones:
            bone._mark_dirty()
    
    # Pose Operations
    
    def reset_pose(self) -> None:
        
        for bone in self._bones:
            bone.reset_pose()
    
    def set_bone_rotation(self, bone_name: str, rotation: Quat) -> bool:
        bone = self.get_bone(bone_name)
        if bone is not None:
            bone.set_pose_rotation(rotation)
            return True
        return False
    
    def set_bone_position(self, bone_name: str, position: Vec3) -> bool:
        bone = self.get_bone(bone_name)
        if bone is not None:
            bone.set_pose_position(position)
            return True
        return False
    
    def set_root_bone_position(self, position: Vec3) -> bool:
        root_bones = self._root_bones
        if root_bones[0] is not None:
            for root_bone in root_bones:
                if root_bone is not None:
                    root_bone.set_pose_position(position)
                    return True
        else:
            self._bones[0].set_pose_position(position)
        return False
    
    
    # Utility Methods
    
    def get_bone_chain(self, from_bone: str, to_ancestor: str) -> List[Bone]:
        start = self.get_bone(from_bone)
        end = self.get_bone(to_ancestor)
        
        if start is None or end is None:
            return []
        
        
        chain: List[Bone] = []
        current: Optional[Bone] = start
        
        while current is not None:
            chain.append(current)
            if current is end:
                return chain
            current = current.parent
        
        return []  
    
    def get_bone_children(self, bone_name: str) -> List[Bone]:
        bone = self.get_bone(bone_name)
        if bone is not None:
            return bone.children.copy()
        return []
    
    def get_bone_descendants(self, bone_name: str) -> List[Bone]:
        bone = self.get_bone(bone_name)
        if bone is not None:
            return bone.get_all_descendants()
        return []
    
    def get_leaf_bones(self) -> List[Bone]:
        return [b for b in self._bones if len(b.children) == 0]

    def get_visible_bones(self) -> List[Bone]:
        return [b for b in self._bones if b.visible]

    def set_bone_visible(self, bone_name: str, visible: bool, cascade: bool = False) -> bool:
        bone = self.get_bone(bone_name)
        if bone is None:
            return False
        bone.visible = visible
        if cascade:
            for descendant in bone.get_all_descendants():
                descendant.visible = visible
        return True

    def set_all_visible(self, visible: bool) -> None:
        for bone in self._bones:
            bone.visible = visible

    def get_bone_groups(self) -> Dict[str, List[str]]:
        groups: Dict[str, List[str]] = {}
        for bone in self._bones:
            name_lower = bone.name.lower()
            prefix = None
            for candidate in ('l_', 'r_', 'left', 'right'):
                if name_lower.startswith(candidate):
                    prefix = candidate
                    break
            if prefix is not None:
                group_key = name_lower[:len(prefix)].rstrip('_').upper() + ' Side'
                group_key = group_key.strip()
                if group_key not in groups:
                    groups[group_key] = []
                groups[group_key].append(bone.name)
        return groups

    def get_bone_count(self) -> int:
        return len(self._bones)
    
    def get_max_depth(self) -> int:
        max_depth = 0
        for bone in self._bones:
            depth = bone.get_depth()
            if depth > max_depth:
                max_depth = depth
        return max_depth
    
    def validate_hierarchy(self) -> List[str]:
        issues: List[str] = []
        
        for bone in self._bones:
            if bone.is_ancestor_of(bone):
                issues.append(f"Cycle detected: {bone.name} is its own ancestor")
        
        for bone in self._bones:
            if bone not in self._root_bones:
                current = bone
                found_root = False
                while current is not None:
                    if current in self._root_bones:
                        found_root = True
                        break
                    current = current.parent
                if not found_root:
                    issues.append(f"Bone {bone.name} has no path to root")
        
        seen_names: Dict[str, int] = {}
        for bone in self._bones:
            if bone.name in seen_names:
                issues.append(f"Duplicate bone name: {bone.name}")
            seen_names[bone.name] = bone.index
        
        return issues
    
    # Debug / Info
    
    def print_hierarchy(self) -> None:
        for root in self._root_bones:
            self._print_bone(root, 0)
    
    def _print_bone(self, bone: Bone, indent: int) -> None:
        prefix = "  " * indent
        pos = bone.get_world_position()
        print(f"{prefix}{bone.name} (index={bone.index}, pos=({pos.x:.2f}, {pos.y:.2f}, {pos.z:.2f}))")
        for child in bone.children:
            self._print_bone(child, indent + 1)
    
    def __repr__(self) -> str:
        return f"Skeleton(bones={len(self._bones)}, roots={len(self._root_bones)})"

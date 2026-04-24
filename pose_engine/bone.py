from typing import Optional, List
from .transform import Transform
from .vec3 import Vec3
from .quat import Quat
from .mat4 import Mat4


class Bone:
    __slots__ = (
        'name', 'index',
        'bind_transform', 'inverse_bind_matrix',
        'pose_transform',
        'parent', 'children',
        '_world_transform', '_world_dirty',
        '_final_matrix', '_final_dirty',
        'visible'
    )

    def __init__(self, name: str, index: int):
        self.name = name
        self.index = index

        self.bind_transform = Transform()
        self.inverse_bind_matrix: Optional[Mat4] = None

        self.pose_transform = Transform()

        self.parent: Optional['Bone'] = None
        self.children: List['Bone'] = []

        self._world_transform: Optional[Transform] = None
        self._world_dirty: bool = True

        self._final_matrix: Optional[Mat4] = None
        self._final_dirty: bool = True

        self.visible: bool = True
    
    def __repr__(self) -> str:
        return f"Bone('{self.name}', index={self.index})"
    
    # Hierarchy Management
    
    def add_child(self, child: 'Bone') -> None:
        if child.parent is not None:
            child.parent.remove_child(child)
        child.parent = self
        if child not in self.children:
            self.children.append(child)
        child._mark_dirty()
    
    def remove_child(self, child: 'Bone') -> None:
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            child._mark_dirty()
    
    def _mark_dirty(self) -> None:
        self._world_dirty = True
        self._final_dirty = True
        for child in self.children:
            child._mark_dirty()
    
    # Transform Computation
    
    def get_world_transform(self) -> Transform:
        if not self._world_dirty and self._world_transform is not None:
            return self._world_transform


        local = Transform()
        local._position = self.bind_transform.position + self.bind_transform.rotation.rotate_vector(self.pose_transform.position)

        local._rotation = self.pose_transform.rotation * self.bind_transform.rotation
        local._scale = Vec3(
            self.bind_transform.scale.x * self.pose_transform.scale.x,
            self.bind_transform.scale.y * self.pose_transform.scale.y,
            self.bind_transform.scale.z * self.pose_transform.scale.z
        )
        local._matrix_dirty = True

        if self.parent is not None:
            parent_world = self.parent.get_world_transform()
            self._world_transform = Transform.multiply(parent_world, local)
        else:
            self._world_transform = local

        self._world_dirty = False
        return self._world_transform
    
    def get_final_matrix(self) -> Mat4:
        if not self._final_dirty and self._final_matrix is not None:
            return self._final_matrix
        
        world = self.get_world_transform().to_matrix()
        
        if self.inverse_bind_matrix is not None:
            self._final_matrix = world * self.inverse_bind_matrix
        else:
            self._final_matrix = world
        
        self._final_dirty = False
        return self._final_matrix
    
    def get_world_position(self) -> Vec3:
        return self.get_world_transform().position
    
    def get_world_rotation(self) -> Quat:
        return self.get_world_transform().rotation
    
    # Pose Modification
    
    def set_pose_position(self, position: Vec3) -> None:
        self.pose_transform.position = position
        self._mark_dirty()
    
    def set_pose_rotation(self, rotation: Quat) -> None:
        self.pose_transform.rotation = rotation
        self._mark_dirty()
    
    def set_pose_scale(self, scale: Vec3) -> None:
        self.pose_transform.scale = scale
        self._mark_dirty()
    
    def reset_pose(self) -> None:
        self.pose_transform = Transform()
        self._mark_dirty()
    
    # Utility Methods
    
    def get_tail_position(self, length: float) -> Vec3:
        world = self.get_world_transform()
        # Bone points along local Y axis
        local_tail = Vec3(0, length, 0)
        return world.transform_point(local_tail)
    
    def get_depth(self) -> int:
        depth = 0
        current = self.parent
        while current is not None:
            depth += 1
            current = current.parent
        return depth
    
    def is_ancestor_of(self, other: 'Bone') -> bool:
        current = other.parent
        while current is not None:
            if current is self:
                return True
            current = current.parent
        return False
    
    def get_all_descendants(self) -> List['Bone']:
        descendants: List['Bone'] = []
        self._collect_descendants(descendants)
        return descendants
    
    def _collect_descendants(self, out_list: List['Bone']) -> None:
        for child in self.children:
            out_list.append(child)
            child._collect_descendants(out_list)

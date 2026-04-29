import uuid
from typing import Optional, List, Tuple, TYPE_CHECKING
from .skeleton import Skeleton
from .transform import Transform
from .vec3 import Vec3
from .quat import Quat
from .mat4 import Mat4
from .bone import Bone
from .gltf.builder import MeshData
from .gltf.loader import GLBLoader, GLBData
from .gltf.builder import build_skeleton_from_gltf, build_mesh_from_gltf
from .bone_extent import BoneExtentTracker

from .logger import get_logger
logger = get_logger(__name__)


class ModelInstance:
    
    def __init__(self, id: Optional[str] = None, name: str = "Model"):
        self.id: str = id or str(uuid.uuid4())[:8]
        self.name: str = name
        
        self.skeleton: Optional[Skeleton] = None
        self.mesh_data: Optional[MeshData] = None
        self._source_file: Optional[str] = None
        
        self.transform = Transform()
        
        self.visible: bool = True
        
        self._parent: Optional['ModelInstance'] = None
        self._children: List['ModelInstance'] = []
        self._parent_bone: Optional[str] = None
        
        self._renderer = None
        self._skeleton_viz = None
        self._gl_initialized: bool = False
        
        self._cached_bbox: Optional[Tuple[Vec3, Vec3]] = None

        self._bone_extent_tracker: Optional['BoneExtentTracker'] = None
        self._bbox_dirty: bool = True
    
    
    def load_from_file(self, file_path: str) -> None:
        loader = GLBLoader()
        glb_data = loader.load(file_path)

        self.skeleton, bone_mapping = build_skeleton_from_gltf(glb_data, loader=loader)

        self.mesh_data = build_mesh_from_gltf(glb_data, bone_mapping=bone_mapping, loader=loader, load_all_meshes=True)
        self._source_file = file_path

        self._apply_gltf_node_transform(glb_data)

        if self.skeleton:
            self.skeleton.update_all_transforms()

        self._calculate_bone_extents()

    def _apply_gltf_node_transform(self, glb_data: GLBData) -> None:
        if not glb_data.nodes:
            logger.debug("[DEBUG_TRANSFORM] No nodes in glb_data, skipping")
            return

        if glb_data.skins:
            logger.debug(f"[DEBUG_TRANSFORM] Model has {len(glb_data.skins)} skins, skipping node transform")
            return

        scenes = glb_data.json_data.get('scenes', [])
        scene_index = glb_data.json_data.get('scene', 0)
        root_indices: List[int] = []

        if scenes and scene_index < len(scenes):
            root_indices = scenes[scene_index].get('nodes', [])

        if not root_indices:
            root_indices = list(range(len(glb_data.nodes)))

        logger.debug(f"[DEBUG_TRANSFORM] scenes={len(scenes)} scene_index={scene_index} root_indices={root_indices}")

        mesh_nodes: List[Tuple[int, Mat4]] = []
        for idx in root_indices:
            self._collect_mesh_nodes(glb_data, idx, Mat4.identity(), mesh_nodes)

        logger.debug(f"[DEBUG_TRANSFORM] Found {len(mesh_nodes)} mesh nodes")
        if not mesh_nodes:
            return

        _, node_transform = mesh_nodes[0]
        self.transform.position = node_transform.get_translation()
        self.transform.rotation = node_transform.get_rotation()
        self.transform.scale = node_transform.get_scale()
        logger.debug(f"[DEBUG_TRANSFORM] Applied: pos={self.transform.position} rot={self.transform.rotation} scale={self.transform.scale}")

    def _collect_mesh_nodes(self, glb_data: GLBData, node_index: int,
                            parent_transform: Mat4, result: List[Tuple[int, Mat4]]) -> None:
        node = glb_data.nodes[node_index]

        if node.matrix:
            local = Mat4(node.matrix)
        else:
            t = Vec3(node.translation[0], node.translation[1], node.translation[2])
            r = Quat(node.rotation[3], node.rotation[0], node.rotation[1], node.rotation[2])
            s = Vec3(node.scale[0], node.scale[1], node.scale[2])
            local = Mat4.from_trs(t, r, s)

        world = parent_transform * local

        if node.mesh is not None:
            result.append((node_index, world))

        for child_index in node.children:
            self._collect_mesh_nodes(glb_data, child_index, world, result)

    def load_from_glb(self, file_path: str) -> None:
            self.load_from_file(file_path)
    
    @property
    def source_file(self) -> Optional[str]:
        return self._source_file
    
    
    def set_parent(self, parent: Optional['ModelInstance'], 
                   bone_name: Optional[str] = None) -> None:
        if self._parent is not None:
            self._parent._children.remove(self)
        
        self._parent = parent
        self._parent_bone = bone_name
        
        if parent is not None:
            parent._children.append(self)
    
    def get_parent(self) -> Optional['ModelInstance']:
        return self._parent
    
    def get_children(self) -> List['ModelInstance']:
        return self._children.copy()
    
    def get_parent_bone(self) -> Optional[str]:
        return self._parent_bone
    
    def _calculate_bone_extents(self) -> None:
        if not self.mesh_data or not self.skeleton:
            return
        
        self._bone_extent_tracker = BoneExtentTracker()
        
        bone_mapping = self.mesh_data.bone_mapping if self.mesh_data else {}
        
        self._bone_extent_tracker.calculate_from_mesh(
            self.mesh_data,
            self.skeleton,
            bone_mapping
        )
        
        self._bbox_dirty = True
        logger.debug(f"[ModelInstance] Calculated bone extents for {self.name}")

    def get_bounding_box(self) -> Tuple[Vec3, Vec3]:
        if self._bone_extent_tracker and self._bone_extent_tracker.has_data:
            return self._bone_extent_tracker.get_bounding_box(
                self.skeleton,
                self.transform
            )
        
        return Vec3(-0.5, -0.5, -0.5), Vec3(0.5, 0.5, 0.5)
    
    def invalidate_bounding_box(self) -> None:
        self._bbox_dirty = True
    
    def get_local_bounding_box(self) -> Tuple[Vec3, Vec3]:
        if self._bone_extent_tracker and self._bone_extent_tracker.has_data:
            return self._bone_extent_tracker.get_bounding_box(self.skeleton)
        return Vec3(-0.5, -0.5, -0.5), Vec3(0.5, 0.5, 0.5)
    
    def get_world_transform(self) -> Transform:
        if self._parent is None:
            return self.transform
        
        parent_world = self._parent.get_world_transform()
        
        if self._parent_bone is not None and self._parent.skeleton is not None:
            bone = self._parent.skeleton.get_bone(self._parent_bone)
            if bone is not None:
                bone_transform = bone.get_world_transform()
                # Combine: parent_world * bone_world * local_transform
                combined = Transform.multiply(parent_world, bone_transform)
                return Transform.multiply(combined, self.transform)
        
        return Transform.multiply(parent_world, self.transform)
    
    def get_world_position(self) -> Vec3:
        world_transform = self.get_world_transform()
        return world_transform.position
    
    
    def set_position(self, x: float, y: float, z: float) -> None:
        self.transform.set_position(x, y, z)
    
    def translate(self, offset: Vec3) -> None:
        self.transform.translate_by(offset)
    
    def rotate_y(self, angle_degrees: float) -> None:
        self.transform.rotate_by(Vec3(0, 1, 0), angle_degrees)
    
    # Skeleton Access
    
    def get_bone_count(self) -> int:
        return len(self.skeleton) if self.skeleton else 0
    
    def get_bone(self, name: str) -> Optional[Bone]:
        if self.skeleton:
            return self.skeleton.get_bone(name)
        return None
    
    def get_root_bones(self) -> List[Bone]:
        if self.skeleton:
            return self.skeleton.get_root_bones()
        return []
    
    def update_transforms(self) -> None:
        if self.skeleton:
            self.skeleton.update_all_transforms()
        self._bbox_dirty = True
    
    # Copying
    
    def copy(self, name: Optional[str] = None) -> 'ModelInstance':

        new_model = ModelInstance(
            id=None,
            name=name or f"{self.name} (copy)"
        )
        
        if self.skeleton:
            new_model.skeleton = self._deep_copy_skeleton_with_pose(self.skeleton)
        
        new_model.mesh_data = self.mesh_data
        new_model._source_file = self._source_file
        
        # Copy the transform
        new_model.transform = Transform()
        new_model.transform.position = Vec3(
            self.transform.position.x,
            self.transform.position.y,
            self.transform.position.z
        )
        new_model.transform.rotation = self.transform.rotation
        new_model.transform.scale = self.transform.scale
        
        return new_model
    
    def _deep_copy_skeleton_with_pose(self, skeleton: Skeleton) -> Skeleton:
        new_skeleton = Skeleton()
        
        
        for bone in skeleton:
            new_bone = new_skeleton.add_bone(bone.name)
            
            # Copy bind transform
            new_bone.bind_transform.position = Vec3(
                bone.bind_transform.position.x,
                bone.bind_transform.position.y,
                bone.bind_transform.position.z
            )
            new_bone.bind_transform.rotation = bone.bind_transform.rotation
            new_bone.bind_transform.scale = Vec3(
                bone.bind_transform.scale.x,
                bone.bind_transform.scale.y,
                bone.bind_transform.scale.z
            )
            
            # Copy inverse bind matrix
            if bone.inverse_bind_matrix:
                new_bone.inverse_bind_matrix = bone.inverse_bind_matrix
            
            # Copy pose transform
            new_bone.pose_transform.position = Vec3(
                bone.pose_transform.position.x,
                bone.pose_transform.position.y,
                bone.pose_transform.position.z
            )
            new_bone.pose_transform.rotation = bone.pose_transform.rotation
            new_bone.pose_transform.scale = Vec3(
                bone.pose_transform.scale.x,
                bone.pose_transform.scale.y,
                bone.pose_transform.scale.z
            )
    
            new_bone.visible = bone.visible
    
            # Build hierarchy
        for old_bone in skeleton:
            if old_bone.parent:
                new_bone = new_skeleton.get_bone(old_bone.name)
                new_parent = new_skeleton.get_bone(old_bone.parent.name)
                if new_bone and new_parent:
                    new_parent.add_child(new_bone)
    
        # Clear and rebuild based on actual parent state, fixes root bones
        new_skeleton._root_bones.clear()
        for bone in new_skeleton:
            if bone.parent is None:
                new_skeleton._root_bones.append(bone)
    
        
        new_skeleton.update_all_transforms()
        
        return new_skeleton
    
    # GPU Resources
    
    def initialize_gl(self) -> bool:
        if self._gl_initialized:
            return True
        
        # Actual GLRenderer and SkeletonVisualizer creation is done by
        # Viewport3D to ensure proper OpenGL context
        # TODO: refactor - initialize_gl() should not exist if it delegates entirely to Viewport3D
        self._gl_initialized = True
        return True
    
    def cleanup_gl(self) -> None:
        if self._renderer:
            self._renderer.cleanup()
            self._renderer = None
        if self._skeleton_viz:
            self._skeleton_viz.cleanup()
            self._skeleton_viz = None
        self._gl_initialized = False
        
    def _calculate_bone_extents(self) -> None:
        """Calculate bone extents from loaded mesh data."""
        if not self.mesh_data or not self.skeleton:
            return
        
        try:
            self._bone_extent_tracker = BoneExtentTracker()
            bone_mapping = self.mesh_data.bone_mapping if self.mesh_data else {}
            
            self._bone_extent_tracker.calculate_from_mesh(
                self.mesh_data,
                self.skeleton,
                bone_mapping
            )
            self._bbox_dirty = True
            logger.debug(f"[ModelInstance] Calculated bone extents for {self.name}")
        except Exception as e:
            logger.error(f"[ModelInstance] Failed to calculate bone extents: {e}")

    def get_bounding_box(self) -> Tuple[Vec3, Vec3]:
        """Get the current bounding box of this model."""
        if self._bone_extent_tracker and self._bone_extent_tracker.has_data:
            return self._bone_extent_tracker.get_bounding_box(
                self.skeleton,
                self.transform
            )
        return Vec3(-0.5, -0.5, -0.5), Vec3(0.5, 0.5, 0.5)

    def get_local_bounding_box(self) -> Tuple[Vec3, Vec3]:
        """Get bounding box in local space (without model transform)."""
        if self._bone_extent_tracker and self._bone_extent_tracker.has_data:
            return self._bone_extent_tracker.get_bounding_box(self.skeleton)
        return Vec3(-0.5, -0.5, -0.5), Vec3(0.5, 0.5, 0.5)

    def invalidate_bounding_box(self) -> None:
        """Mark bounding box as needing recalculation."""
        self._bbox_dirty = True
    
    # Representation
    
    def __repr__(self) -> str:
        return f"ModelInstance('{self.name}', id={self.id}, bones={self.get_bone_count()})"

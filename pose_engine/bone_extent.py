"""
Bone extent tracking for approximate bounding box calculation.
"""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from .vec3 import Vec3
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class BoneExtent:
    """Tracks the spatial extent of vertices influenced by a bone."""
    bone_name: str
    bone_index: int
    min_local: Vec3
    max_local: Vec3
    vertex_count: int = 0
    total_weight: float = 0.0


class BoneExtentTracker:
    """
    Tracks and calculates bone extents from mesh skinning data.
    """
    
    def __init__(self):
        self._extents: Dict[str, BoneExtent] = {}
        self._bone_index_map: Dict[int, str] = {}  # bone_index -> bone_name
        self._global_min: Vec3 = Vec3(float('inf'), float('inf'), float('inf'))
        self._global_max: Vec3 = Vec3(float('-inf'), float('-inf'), float('-inf'))
        self._has_data: bool = False
    
    def calculate_from_mesh(self, mesh_data, skeleton, bone_mapping: Dict[int, int]) -> None:
        """
        Calculate bone extents from mesh data.
        """
        if not mesh_data or not skeleton:
            logger.warning("[BoneExtent] No mesh_data or skeleton provided")
            return
        
        try:
            # Initialize extents for all bones
            for i, bone in enumerate(skeleton):
                self._extents[bone.name] = BoneExtent(
                    bone_name=bone.name,
                    bone_index=i,
                    min_local=Vec3(0, 0, 0),
                    max_local=Vec3(0, 0, 0),
                    vertex_count=0,
                    total_weight=0.0
                )
                self._bone_index_map[i] = bone.name
            
            # Process all sub-meshes
            for sub_mesh in mesh_data.sub_meshes:
                positions = sub_mesh.positions
                skinning_data = sub_mesh.skinning_data
                
                if not positions:
                    continue
                
                for vertex_idx, pos in enumerate(positions):
                    # Track global bounds
                    self._global_min = Vec3(
                        min(self._global_min.x, pos.x),
                        min(self._global_min.y, pos.y),
                        min(self._global_min.z, pos.z)
                    )
                    self._global_max = Vec3(
                        max(self._global_max.x, pos.x),
                        max(self._global_max.y, pos.y),
                        max(self._global_max.z, pos.z)
                    )
                    
                    # If no skinning, assign to root bones
                    if not skinning_data or vertex_idx >= skinning_data.get_vertex_count():
                        for root_bone in skeleton.get_root_bones():
                            extent = self._extents.get(root_bone.name)
                            if extent and root_bone.bind_transform:
                                self._update_extent(extent, pos, root_bone.bind_transform, 1.0)
                        continue
                    
                    # Process skinning influences
                    skinning = skinning_data.get_vertex_skinning(vertex_idx)
                    
                    for joint_idx, weight in skinning.get_influences():
                        # joint_idx IS the skeleton bone index directly
                        bone_name = self._bone_index_map.get(joint_idx)
                        if not bone_name:
                            continue
                        
                        extent = self._extents.get(bone_name)
                        if not extent:
                            continue
                        
                        bone = skeleton.get_bone(bone_name)
                        if not bone:
                            continue
                        
                        self._update_extent(extent, pos, bone.bind_transform, weight)
            
            self._has_data = True
            logger.debug(f"[BoneExtent] Calculated extents for {len(self._extents)} bones")
            
        except Exception as e:
            logger.error(f"[BoneExtent] Error calculating extents: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_extent(self, extent: BoneExtent, world_pos: Vec3, 
                       bone_transform, weight: float) -> None:
        """Update extent with a vertex position in bone-local space."""
        try:
            bone_matrix = bone_transform.to_matrix()
            inv_bone_matrix = bone_matrix.inverse()
            local_pos = inv_bone_matrix.transform_point(world_pos)
            
            if extent.vertex_count == 0:
                extent.min_local = Vec3(local_pos.x, local_pos.y, local_pos.z)
                extent.max_local = Vec3(local_pos.x, local_pos.y, local_pos.z)
            else:
                extent.min_local = Vec3(
                    min(extent.min_local.x, local_pos.x),
                    min(extent.min_local.y, local_pos.y),
                    min(extent.min_local.z, local_pos.z)
                )
                extent.max_local = Vec3(
                    max(extent.max_local.x, local_pos.x),
                    max(extent.max_local.y, local_pos.y),
                    max(extent.max_local.z, local_pos.z)
                )
            
            extent.vertex_count += 1
            extent.total_weight += weight
        except Exception as e:
            logger.warning(f"[BoneExtent] Error updating extent: {e}")
    
    def get_bounding_box(self, skeleton, model_transform=None) -> Tuple[Vec3, Vec3]:
        """Calculate current bounding box from bone positions + extents."""
        if not self._has_data or not skeleton:
            return Vec3(-0.5, -0.5, -0.5), Vec3(0.5, 0.5, 0.5)
        
        min_pt = Vec3(float('inf'), float('inf'), float('inf'))
        max_pt = Vec3(float('-inf'), float('-inf'), float('-inf'))
        
        has_any_extent = False
        
        for bone in skeleton:
            extent = self._extents.get(bone.name)
            if not extent or extent.vertex_count == 0:
                continue
            
            has_any_extent = True
            
            # Get bone's current world transform
            try:
                bone_world = bone.get_world_transform()
                bone_matrix = bone_world.to_matrix()
            except Exception:
                continue
            
            # Transform extent corners to world space
            corners = self._get_extent_corners(extent)
            
            for corner in corners:
                try:
                    world_corner = bone_matrix.transform_point(corner)
                    
                    if model_transform:
                        model_matrix = model_transform.to_matrix()
                        world_corner = model_matrix.transform_point(world_corner)
                    
                    min_pt = Vec3(
                        min(min_pt.x, world_corner.x),
                        min(min_pt.y, world_corner.y),
                        min(min_pt.z, world_corner.z)
                    )
                    max_pt = Vec3(
                        max(max_pt.x, world_corner.x),
                        max(max_pt.y, world_corner.y),
                        max(max_pt.z, world_corner.z)
                    )
                except Exception:
                    continue
        
        if not has_any_extent or min_pt.x == float('inf'):
            return self._global_min, self._global_max
        
        return min_pt, max_pt
    
    def _get_extent_corners(self, extent: BoneExtent) -> list:
        """Get the 8 corners of an extent box."""
        x0, y0, z0 = extent.min_local.x, extent.min_local.y, extent.min_local.z
        x1, y1, z1 = extent.max_local.x, extent.max_local.y, extent.max_local.z
        
        return [
            Vec3(x0, y0, z0), Vec3(x1, y0, z0),
            Vec3(x1, y1, z0), Vec3(x0, y1, z0),
            Vec3(x0, y0, z1), Vec3(x1, y0, z1),
            Vec3(x1, y1, z1), Vec3(x0, y1, z1),
        ]
    
    def get_extent(self, bone_name: str) -> Optional[BoneExtent]:
        return self._extents.get(bone_name)
    
    @property
    def has_data(self) -> bool:
        return self._has_data



from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from ..vec3 import Vec3
from ..quat import Quat
from ..mat4 import Mat4
from ..transform import Transform
from ..bone import Bone
from ..skeleton import Skeleton
from ..skinning import SkinningData, VertexSkinning
from .loader import GLBData, GLBLoader, MaterialData, TextureData, ImageData


@dataclass
class SubMeshData:
    positions: List[Vec3] = field(default_factory=list)
    normals: List[Vec3] = field(default_factory=list)
    texcoords: List[Tuple[float, float]] = field(default_factory=list)
    indices: List[int] = field(default_factory=list)
    skinning_data: Optional[SkinningData] = None
    material_index: Optional[int] = None


@dataclass
class MeshData:
    
    def __init__(self):
        self.sub_meshes: List[SubMeshData] = []
        self.materials: List[MaterialData] = []
        self.textures: List[TextureData] = []
        self.images: List[ImageData] = []
        self.bone_mapping: Dict[int, int] = {}
    
    @property
    def positions(self) -> List[Vec3]:
        return self.sub_meshes[0].positions if self.sub_meshes else []
    
    @property
    def normals(self) -> List[Vec3]:
        return self.sub_meshes[0].normals if self.sub_meshes else []
    
    @property
    def indices(self) -> List[int]:
        return self.sub_meshes[0].indices if self.sub_meshes else []
    
    @property
    def skinning_data(self) -> Optional[SkinningData]:
        return self.sub_meshes[0].skinning_data if self.sub_meshes else None


def build_skeleton_from_gltf(
    glb_data: GLBData,
    skin_index: int = 0,
    loader: Optional[GLBLoader] = None
) -> Tuple[Skeleton, Dict[int, int]]:
    if len(glb_data.skins) == 0:
        skeleton = Skeleton()
        root_bone = skeleton.add_bone("root")
        root_bone.bind_transform.position = Vec3(0, 0, 0)
        root_bone.bind_transform.rotation = Quat(1, 0, 0, 0)
        root_bone.bind_transform.scale = Vec3(1, 1, 1)
        root_bone.inverse_bind_matrix = root_bone.bind_transform.to_matrix().inverse()
        skeleton.update_all_transforms()
        return skeleton, {}

    if skin_index >= len(glb_data.skins):
        raise ValueError(f"Skin index {skin_index} out of range (model has {len(glb_data.skins)} skins)")

    skin = glb_data.skins[skin_index]
    skeleton = Skeleton()

    inverse_bind_matrices: List[List[float]] = []
    if skin.inverse_bind_matrices is not None:
        if loader is None:
            loader = GLBLoader()
            loader._data = glb_data
        inverse_bind_matrices = loader.get_inverse_bind_matrices(skin.inverse_bind_matrices)

    node_to_bone: Dict[int, int] = {}

    for i, joint_node_index in enumerate(skin.joints):
        node = glb_data.nodes[joint_node_index]

        bone = skeleton.add_bone(node.name)
        node_to_bone[joint_node_index] = i

        if node.matrix:
            mat = Mat4(node.matrix)
            bone.bind_transform.position = mat.get_translation()
            bone.bind_transform.rotation = mat.get_rotation()
            bone.bind_transform.scale = mat.get_scale()
        else:
            bone.bind_transform.position = Vec3(
                node.translation[0],
                node.translation[1],
                node.translation[2]
            )
            bone.bind_transform.rotation = Quat(
                node.rotation[3],  # w
                node.rotation[0],  # x
                node.rotation[1],  # y
                node.rotation[2]   # z
            )
            bone.bind_transform.scale = Vec3(
                node.scale[0],
                node.scale[1],
                node.scale[2]
            )

        if i < len(inverse_bind_matrices):
            bone.inverse_bind_matrix = Mat4(inverse_bind_matrices[i])
        else:
            bone.inverse_bind_matrix = bone.bind_transform.to_matrix().inverse()

    for joint_node_index in skin.joints:
        node = glb_data.nodes[joint_node_index]
        bone_index = node_to_bone[joint_node_index]
        bone = skeleton.get_bone_by_index(bone_index)

        for child_node_index in node.children:
            if child_node_index in node_to_bone:
                child_bone_index = node_to_bone[child_node_index]
                child_bone = skeleton.get_bone_by_index(child_bone_index)
                bone.add_child(child_bone)

    skeleton._root_bones = []
    for joint_node_index in skin.joints:
        bone_index = node_to_bone[joint_node_index]
        bone = skeleton.get_bone_by_index(bone_index)
        if bone.parent is None:
            skeleton._root_bones.append(bone)

    skeleton.update_all_transforms()

    return skeleton, node_to_bone


def build_mesh_from_gltf(
    glb_data: GLBData,
    mesh_index: int = 0,
    primitive_index: Optional[int] = None,
    bone_mapping: Optional[Dict[int, int]] = None,
    loader: Optional[GLBLoader] = None,
    load_all_meshes: bool = False
) -> MeshData:
    if loader is None:
        loader = GLBLoader()
        loader._data = glb_data

    mesh_data = MeshData()

    mesh_data.materials = glb_data.materials
    mesh_data.textures = glb_data.textures
    mesh_data.images = glb_data.images

    if bone_mapping:
        mesh_data.bone_mapping = bone_mapping

    if load_all_meshes:
        mesh_indices = list(range(len(glb_data.meshes)))
    else:
        if mesh_index >= len(glb_data.meshes):
            raise ValueError(f"Mesh index {mesh_index} out of range")
        mesh_indices = [mesh_index]

    for current_mesh_index in mesh_indices:
        mesh = glb_data.meshes[current_mesh_index]

        if primitive_index is not None and not load_all_meshes:
            if primitive_index >= len(mesh.primitives):
                raise ValueError(f"Primitive index {primitive_index} out of range")
            primitive_indices = [primitive_index]
        else:
            primitive_indices = list(range(len(mesh.primitives)))

        for prim_idx in primitive_indices:
            primitive = mesh.primitives[prim_idx]
            attributes = primitive.get('attributes', {})

            sub_mesh = SubMeshData()

            sub_mesh.material_index = primitive.get('material', None)

            if 'POSITION' in attributes:
                positions = loader.get_positions(attributes['POSITION'])
                sub_mesh.positions = [Vec3(p[0], p[1], p[2]) for p in positions]

            if 'NORMAL' in attributes:
                normals = loader.get_normals(attributes['NORMAL'])
                sub_mesh.normals = [Vec3(n[0], n[1], n[2]) for n in normals]

            if 'TEXCOORD_0' in attributes:
                texcoords = loader.get_texcoords(attributes['TEXCOORD_0'])
                sub_mesh.texcoords = texcoords

            if 'indices' in primitive:
                sub_mesh.indices = loader.get_indices(primitive['indices'])

            if 'JOINTS_0' in attributes and 'WEIGHTS_0' in attributes:
                joints = loader.get_joints(attributes['JOINTS_0'])
                weights = loader.get_weights(attributes['WEIGHTS_0'])

                sub_mesh.skinning_data = SkinningData(vertex_count=len(sub_mesh.positions))

                for i, (joint, weight) in enumerate(zip(joints, weights)):
                    skinning = sub_mesh.skinning_data.get_vertex_skinning(i)

                    for j in range(4):
                        bone_idx = joint[j]
                        weight_val = weight[j]

                        if weight_val > 0.0001:
                            skinning.add_influence(bone_idx, weight_val)

                skinning.normalize_weights()

            mesh_data.sub_meshes.append(sub_mesh)

    return mesh_data



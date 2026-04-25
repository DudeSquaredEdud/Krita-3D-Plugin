import struct
import json
import base64
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Accessor:
    buffer_view: int
    byte_offset: int
    component_type: int
    count: int
    type: str
    min_vals: List[float]
    max_vals: List[float]
    
    def get_component_size(self) -> int:
        sizes = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
        return sizes.get(self.component_type, 4)
    
    def get_num_components(self) -> int:
        counts = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
        return counts.get(self.type, 1)


@dataclass
class BufferView:
    buffer: int
    byte_offset: int
    byte_length: int
    byte_stride: Optional[int]
    target: Optional[int]


@dataclass
class SkinData:
    name: str
    joints: List[int]
    inverse_bind_matrices: Optional[int]
    skeleton: Optional[int]


@dataclass
class TextureData:
    name: str
    source_image: Optional[int]
    sampler: Optional[int]


@dataclass
class MaterialData:
    name: str
    base_color_factor: Tuple[float, float, float, float]
    base_color_texture: Optional[int]
    metallic_factor: float
    roughness_factor: float
    metallic_roughness_texture: Optional[int]
    normal_texture: Optional[int]
    emissive_factor: Tuple[float, float, float]
    alpha_mode: str  # "OPAQUE", "MASK", "BLEND"
    alpha_cutoff: float


@dataclass
class ImageData:
    name: str
    mime_type: str
    data: bytes


@dataclass
class RawMeshData:

    name: str
    primitives: List[Dict[str, Any]]


@dataclass
class NodeData:
    name: str
    children: List[int]
    mesh: Optional[int]
    skin: Optional[int]
    translation: List[float]
    rotation: List[float]
    scale: List[float]
    matrix: Optional[List[float]]


@dataclass
class GLBData:
    json_data: Dict[str, Any]
    binary_buffer: bytes
    buffers: Optional[List[bytes]] = None

    accessors: Optional[List[Accessor]] = None
    buffer_views: Optional[List[BufferView]] = None
    nodes: Optional[List[NodeData]] = None
    skins: Optional[List[SkinData]] = None
    meshes: Optional[List[RawMeshData]] = None
    materials: Optional[List[MaterialData]] = None
    textures: Optional[List[TextureData]] = None
    images: Optional[List[ImageData]] = None

    def __post_init__(self):
        if self.buffers is None:
            self.buffers = [self.binary_buffer] if self.binary_buffer else []

    def get_accessor_data(self, accessor_index: int) -> bytes:
        accessor = self.accessors[accessor_index]
        buffer_view = self.buffer_views[accessor.buffer_view]

        buf_index = getattr(buffer_view, 'buffer', 0) or 0
        buf = self.buffers[buf_index] if buf_index < len(self.buffers) else self.binary_buffer

        start = buffer_view.byte_offset + accessor.byte_offset
        end = start + accessor.count * accessor.get_num_components() * accessor.get_component_size()

        return buf[start:end]


class GLBLoader:

    GLB_MAGIC = 0x46546C67 # "glTF" in little-endian
    GLB_VERSION = 2
    CHUNK_JSON = 0x4E4F534A # "JSON"
    CHUNK_BIN = 0x004E4942 # "BIN\0"

    def __init__(self):
        self._data: Optional[GLBData] = None

    def load(self, filepath: str) -> GLBData:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.gltf':
            return self.load_gltf(filepath)
        with open(filepath, 'rb') as f:
            data = f.read()
        return self.load_from_bytes(data)

    def load_gltf(self, filepath: str) -> GLBData:
        gltf_dir = os.path.dirname(os.path.abspath(filepath))

        with open(filepath, 'r', encoding='utf-8') as f:
            json_data = json.load(f)

        buffers = []
        if 'buffers' in json_data and len(json_data['buffers']) > 0:
            for buf_info in json_data['buffers']:
                uri = buf_info.get('uri', '')
                if uri.startswith('data:'):
                    comma_idx = uri.index(',')
                    base64_data = uri[comma_idx + 1:]
                    buffers.append(base64.b64decode(base64_data))
                elif uri:
                    buf_path = os.path.join(gltf_dir, uri)
                    with open(buf_path, 'rb') as bf:
                        buffers.append(bf.read())
                else:
                    buffers.append(b'')
            if 'uri' not in json_data['buffers'][0]:
                json_data['buffers'][0]['_embedded'] = True

        binary_buffer = buffers[0] if buffers else b''
        return self._build_glb_data(json_data, binary_buffer, buffers=buffers)

    def load_from_bytes(self, data: bytes) -> GLBData:
        if len(data) < 12:
            raise ValueError("File too small to be a valid GLB")
        
        magic, version, _ = struct.unpack('<III', data[:12])
        
        if magic != self.GLB_MAGIC:
            raise ValueError(f"Invalid GLB magic: {magic:#x}, expected {self.GLB_MAGIC:#x}")
        
        if version != self.GLB_VERSION:
            raise ValueError(f"Unsupported GLB version: {version}, expected {self.GLB_VERSION}")
        
        offset = 12
        json_data = None
        binary_buffer = b''
        
        while offset < len(data):
            chunk_length, chunk_type = struct.unpack('<II', data[offset:offset+8])
            chunk_data = data[offset+8:offset+8+chunk_length]
            
            if chunk_type == self.CHUNK_JSON:
                json_data = json.loads(chunk_data.decode('utf-8'))
            elif chunk_type == self.CHUNK_BIN:
                binary_buffer = chunk_data
            
            offset += 8 + chunk_length
        
        if json_data is None:
            raise ValueError("GLB missing JSON chunk")
        
        if 'buffers' in json_data and len(json_data['buffers']) > 0:
            buffer_info = json_data['buffers'][0]
            if 'uri' not in buffer_info:
                json_data['buffers'][0]['_embedded'] = True
        
        return self._build_glb_data(json_data, binary_buffer)

    def _build_glb_data(self, json_data: Dict[str, Any], binary_buffer: bytes,
                        buffers: Optional[List[bytes]] = None) -> GLBData:
        if buffers is None:
            buffers = [binary_buffer] if binary_buffer else []

        accessors = self._parse_accessors(json_data.get('accessors', []))
        buffer_views = self._parse_buffer_views(json_data.get('bufferViews', []))
        nodes = self._parse_nodes(json_data.get('nodes', []))
        skins = self._parse_skins(json_data.get('skins', []))
        meshes = self._parse_meshes(json_data.get('meshes', []))
        materials = self._parse_materials(json_data.get('materials', []))
        textures = self._parse_textures(json_data.get('textures', []))
        images = self._parse_images(json_data.get('images', []), buffers, buffer_views)

        self._data = GLBData(
            json_data=json_data,
            binary_buffer=binary_buffer,
            buffers=buffers,
            accessors=accessors,
            buffer_views=buffer_views,
            nodes=nodes,
            skins=skins,
            meshes=meshes,
            materials=materials,
            textures=textures,
            images=images
        )

        return self._data
    
    def _parse_accessors(self, accessors_data: List[Dict]) -> List[Accessor]:
        accessors = []
        
        for acc in accessors_data:
            accessor = Accessor(
                buffer_view=acc.get('bufferView', 0),
                byte_offset=acc.get('byteOffset', 0),
                component_type=acc['componentType'],
                count=acc['count'],
                type=acc['type'],
                min_vals=acc.get('min', []),
                max_vals=acc.get('max', [])
            )
            accessors.append(accessor)
        
        return accessors
    
    def _parse_buffer_views(self, buffer_views_data: List[Dict]) -> List[BufferView]:
        buffer_views = []
        
        for bv in buffer_views_data:
            buffer_view = BufferView(
                buffer=bv.get('buffer', 0),
                byte_offset=bv.get('byteOffset', 0),
                byte_length=bv['byteLength'],
                byte_stride=bv.get('byteStride'),
                target=bv.get('target')
            )
            buffer_views.append(buffer_view)
        
        return buffer_views
    
    def _parse_nodes(self, nodes_data: List[Dict]) -> List[NodeData]:
        nodes = []
        
        for node in nodes_data:
            node_data = NodeData(
                name=node.get('name', f'node_{len(nodes)}'),
                children=node.get('children', []),
                mesh=node.get('mesh'),
                skin=node.get('skin'),
                translation=node.get('translation', [0, 0, 0]),
                rotation=node.get('rotation', [0, 0, 0, 1]),
                scale=node.get('scale', [1, 1, 1]),
                matrix=node.get('matrix')
            )
            nodes.append(node_data)
        
        return nodes
    
    def _parse_skins(self, skins_data: List[Dict]) -> List[SkinData]:
        skins = []
        
        for skin in skins_data:
            skin_data = SkinData(
                name=skin.get('name', f'skin_{len(skins)}'),
                joints=skin['joints'],
                inverse_bind_matrices=skin.get('inverseBindMatrices'),
                skeleton=skin.get('skeleton')
            )
            skins.append(skin_data)
        
        return skins
    
    def _parse_meshes(self, meshes_data: List[Dict]) -> List[RawMeshData]:
        meshes = []

        for mesh in meshes_data:
            mesh_data = RawMeshData(
                name=mesh.get('name', f'mesh_{len(meshes)}'),
                primitives=mesh.get('primitives', [])
            )
            meshes.append(mesh_data)

        return meshes

    def _parse_materials(self, materials_data: List[Dict]) -> List[MaterialData]:
        materials = []

        for mat in materials_data:
            pbr = mat.get('pbrMetallicRoughness', {})
            
            bcf = pbr.get('baseColorFactor', [1.0, 1.0, 1.0, 1.0])
            base_color_factor = (bcf[0], bcf[1], bcf[2], bcf[3] if len(bcf) > 3 else 1.0)
            
            base_color_texture = None
            if 'baseColorTexture' in pbr:
                base_color_texture = pbr['baseColorTexture'].get('index')
            
            metallic_factor = pbr.get('metallicFactor', 1.0)
            roughness_factor = pbr.get('roughnessFactor', 1.0)
            
            metallic_roughness_texture = None
            if 'metallicRoughnessTexture' in pbr:
                metallic_roughness_texture = pbr['metallicRoughnessTexture'].get('index')
            
            normal_texture = None
            if 'normalTexture' in mat:
                normal_texture = mat['normalTexture'].get('index')
            
            ef = mat.get('emissiveFactor', [0.0, 0.0, 0.0])
            emissive_factor = (ef[0], ef[1], ef[2])
            
            alpha_mode = mat.get('alphaMode', 'OPAQUE')
            alpha_cutoff = mat.get('alphaCutoff', 0.5)
            
            material_data = MaterialData(
                name=mat.get('name', f'material_{len(materials)}'),
                base_color_factor=base_color_factor,
                base_color_texture=base_color_texture,
                metallic_factor=metallic_factor,
                roughness_factor=roughness_factor,
                metallic_roughness_texture=metallic_roughness_texture,
                normal_texture=normal_texture,
                emissive_factor=emissive_factor,
                alpha_mode=alpha_mode,
                alpha_cutoff=alpha_cutoff
            )
            materials.append(material_data)

        return materials

    def _parse_textures(self, textures_data: List[Dict]) -> List[TextureData]:
        textures = []

        for tex in textures_data:
            texture_data = TextureData(
                name=tex.get('name', f'texture_{len(textures)}'),
                source_image=tex.get('source'),
                sampler=tex.get('sampler')
            )
            textures.append(texture_data)

        return textures

    def _parse_images(self, images_data: List[Dict], buffers: List[bytes],
        buffer_views: List[BufferView]) -> List[ImageData]:
        images = []

        for img in images_data:
            name = img.get('name', f'image_{len(images)}')
            mime_type = img.get('mimeType', 'image/png')

            if 'bufferView' in img:
                buffer_view_idx = img['bufferView']
                if buffer_view_idx < len(buffer_views):
                    bv = buffer_views[buffer_view_idx]
                    buf_index = getattr(bv, 'buffer', 0) or 0
                    buf = buffers[buf_index] if buf_index < len(buffers) else b''
                    start = bv.byte_offset
                    end = start + bv.byte_length
                    data = buf[start:end]
                else:
                    data = b''
            elif 'uri' in img:
                uri = img['uri']
                if uri.startswith('data:'):
                    comma_idx = uri.index(',')
                    base64_data = uri[comma_idx + 1:]
                    data = base64.b64decode(base64_data)
                else:
                    data = b''
            else:
                data = b''

            image_data = ImageData(
                name=name,
                mime_type=mime_type,
                data=data
            )
            images.append(image_data)

        return images

    def get_positions(self, accessor_index: int) -> List[Tuple[float, float, float]]:
        return self._get_vec3_data(accessor_index)
    
    def get_normals(self, accessor_index: int) -> List[Tuple[float, float, float]]:
        return self._get_vec3_data(accessor_index)
    
    def get_joints(self, accessor_index: int) -> List[Tuple[int, int, int, int]]:
        raw_data = self._data.get_accessor_data(accessor_index)
        accessor = self._data.accessors[accessor_index]
        
        if accessor.component_type == 5121:
            # Unsigned byte
            format_str = '<BBBB'
        elif accessor.component_type == 5123:
            # Unsigned short
            format_str = '<HHHH'
        else:
            format_str = '<HHHH'
        
        component_size = struct.calcsize(format_str)
        joints = []
        
        for i in range(accessor.count):
            offset = i * component_size
            values = struct.unpack(format_str, raw_data[offset:offset+component_size])
            joints.append(values)
        
        return joints
    
    def get_weights(self, accessor_index: int) -> List[Tuple[float, float, float, float]]:
        raw_data = self._data.get_accessor_data(accessor_index)
        accessor = self._data.accessors[accessor_index]
        
        weights = []
        component_size = 16
        
        for i in range(accessor.count):
            offset = i * component_size
            values = struct.unpack('<ffff', raw_data[offset:offset+component_size])
            weights.append(values)
        
        return weights
    
    def get_indices(self, accessor_index: int) -> List[int]:
        raw_data = self._data.get_accessor_data(accessor_index)
        accessor = self._data.accessors[accessor_index]
        
        if accessor.component_type == 5121:
            # Unsigned byte
            format_str = '<B'
        elif accessor.component_type == 5123:
            # Unsigned short
            format_str = '<H'
        elif accessor.component_type == 5125:
            # Unsigned int
            format_str = '<I'
        else:
            format_str = '<H'
        
        component_size = struct.calcsize(format_str)
        indices = []
        
        for i in range(accessor.count):
            offset = i * component_size
            value = struct.unpack(format_str, raw_data[offset:offset+component_size])[0]
            indices.append(value)
        
        return indices
    
    def get_inverse_bind_matrices(self, accessor_index: int) -> List[List[float]]:
        raw_data = self._data.get_accessor_data(accessor_index)
        accessor = self._data.accessors[accessor_index]
        
        matrices = []
        matrix_size = 64  # 16 floats
        
        for i in range(accessor.count):
            offset = i * matrix_size
            values = struct.unpack('<16f', raw_data[offset:offset+matrix_size])
            matrices.append(list(values))
        
        return matrices
    
    def _get_vec3_data(self, accessor_index: int) -> List[Tuple[float, float, float]]:
        raw_data = self._data.get_accessor_data(accessor_index)
        accessor = self._data.accessors[accessor_index]

        vec3s = []
        component_size = 12  # 3 floats

        for i in range(accessor.count):
            offset = i * component_size
            values = struct.unpack('<fff', raw_data[offset:offset+component_size])
            vec3s.append(values)

        return vec3s

    def get_texcoords(self, accessor_index: int) -> List[Tuple[float, float]]:
        raw_data = self._data.get_accessor_data(accessor_index)
        accessor = self._data.accessors[accessor_index]

        texcoords = []
        component_size = 8  # 2 floats

        for i in range(accessor.count):
            offset = i * component_size
            values = struct.unpack('<ff', raw_data[offset:offset+component_size])
            texcoords.append(values)

        return texcoords

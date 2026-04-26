from typing import Optional, List, Tuple
from OpenGL.GL import *
from OpenGL.GL import shaders
import numpy as np

from ..logger import get_logger
logger = get_logger(__name__)

from ..vec3 import Vec3
from ..mat4 import Mat4
from ..quat import Quat
from ..skeleton import Skeleton
from ..skinning import SkinningData, compute_bone_matrices_from_skeleton

# Each bone needs 2 vec4s (real + dual quaternion), so 256 bones = 512 vec4s.
MAX_BONES = 256

VERTEX_SHADER = """
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec4 a_joints;
layout(location = 3) in vec4 a_weights;
layout(location = 4) in vec2 a_texcoord;

out vec3 v_normal;
out vec3 v_position;
out vec2 v_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
uniform vec4 u_bone_dqs[512]; // 256 bones * 2 vec4s per bone (must match MAX_BONES)
uniform bool u_outline_pass;
uniform float u_outline_width;

// Quaternion multiplication
vec4 quat_mul(vec4 q1, vec4 q2) {
    return vec4(
        q1.w * q2.x + q1.x * q2.w + q1.y * q2.z - q1.z * q2.y,
        q1.w * q2.y - q1.x * q2.z + q1.y * q2.w + q1.z * q2.x,
        q1.w * q2.z + q1.x * q2.y - q1.y * q2.x + q1.z * q2.w,
        q1.w * q2.w - q1.x * q2.x - q1.y * q2.y - q1.z * q2.z
    );
}

// Rotate a vector by a unit quaternion
vec3 quat_rotate(vec4 q, vec3 v) {
    vec3 qv = vec3(q.x, q.y, q.z);
    vec3 uv = cross(qv, v);
    vec3 uuv = cross(qv, uv);
    return v + 2.0 * (q.w * uv + uuv);
}

void main() {
    vec4 real_blend = vec4(0.0);
    vec4 dual_blend = vec4(0.0);
    float total_weight = 0.0;

    // First bone reference for antipodality check
    vec4 first_real = vec4(0.0);
    bool has_first = false;

    for (int i = 0; i < 4; i++) {
        int joint = int(a_joints[i]);
        float weight = a_weights[i];

        if (weight > 0.0 && joint >= 0 && joint < 256) {
            vec4 real_q = u_bone_dqs[joint * 2];
            vec4 dual_q = u_bone_dqs[joint * 2 + 1];

            if (!has_first) {
                first_real = real_q;
                has_first = true;
            } else {
                // Antipodality check: q and -q represent the same rotation
                float dot = first_real.x * real_q.x + first_real.y * real_q.y
                    + first_real.z * real_q.z + first_real.w * real_q.w;
                if (dot < 0.0) {
                    real_q = -real_q;
                    dual_q = -dual_q;
                }
            }

            real_blend += weight * real_q;
            dual_blend += weight * dual_q;
            total_weight += weight;
        }
    }

    vec3 skinned_pos;
    vec3 skinned_normal;

    if (total_weight > 0.001) {
        // Normalize the blended dual quaternion
        float norm = sqrt(real_blend.x * real_blend.x + real_blend.y * real_blend.y
            + real_blend.z * real_blend.z + real_blend.w * real_blend.w);
        real_blend /= norm;
        dual_blend /= norm;

        // Extract translation from dual quaternion:
        // translation = 2 * (dual * conjugate(real)).xyz
        vec4 conj = vec4(-real_blend.x, -real_blend.y, -real_blend.z, real_blend.w);
        vec4 t_quat = quat_mul(dual_blend, conj);
        vec3 translation = 2.0 * vec3(t_quat.x, t_quat.y, t_quat.z);

        // Transform position and normal
        skinned_pos = quat_rotate(real_blend, a_position) + translation;
        skinned_normal = quat_rotate(real_blend, a_normal);
    } else {
    skinned_pos = a_position;
    skinned_normal = a_normal;
    }

    if (u_outline_pass) {
        skinned_pos += skinned_normal * u_outline_width;
    }

    v_normal = normalize(mat3(u_model) * skinned_normal);
    v_position = vec3(u_model * vec4(skinned_pos, 1.0));
    v_texcoord = a_texcoord;

    gl_Position = u_projection * u_view * u_model * vec4(skinned_pos, 1.0);
}
"""


FRAGMENT_SHADER = """
#version 330 core

in vec3 v_normal;
in vec3 v_position;
in vec2 v_texcoord;

out vec4 frag_color;

uniform vec3 u_light_dir;
uniform vec3 u_light_color;
uniform vec3 u_ambient;
uniform vec3 u_diffuse_color;
uniform float u_diffuse_alpha; // Separate alpha for diffuse color
uniform sampler2D u_base_color_texture;
uniform bool u_has_texture;

// Distance gradient overlay uniforms
uniform bool u_distance_gradient_enabled;
uniform vec3 u_camera_position;
uniform float u_distance_near;
uniform float u_distance_far;
uniform vec3 u_gradient_color_near;
uniform vec3 u_gradient_color_far;

uniform float u_alpha_mode; // 0=OPAQUE, 1=MASK, 2=BLEND
uniform float u_alpha_cutoff;

// Silhouette mode uniforms
uniform bool u_silhouette_mode;
uniform vec3 u_silhouette_color;
uniform bool u_outline_pass;

void main() {
    if (u_outline_pass) {
        frag_color = vec4(0.08, 0.08, 0.08, 1.0);
        return;
    }

    if (u_silhouette_mode) {
        vec3 normal = normalize(v_normal);
        float ndotl = max(dot(normal, normalize(u_light_dir)), 0.0);
        float lighting = 0.35 + 0.65 * ndotl;
        frag_color = vec4(u_silhouette_color * lighting, 1.0);
        return;
    }

    vec3 normal = normalize(v_normal);

    vec3 base_color;
    float alpha = u_diffuse_alpha;

    if (u_has_texture) {
        vec4 tex_color = texture(u_base_color_texture, v_texcoord);
        base_color = tex_color.rgb * u_diffuse_color;
        alpha = tex_color.a * u_diffuse_alpha;
    } else {
        base_color = u_diffuse_color;
    }

    float diff = max(dot(normal, normalize(u_light_dir)), 0.0);
    vec3 diffuse = diff * u_light_color * base_color;

    vec3 ambient = u_ambient * base_color;

    vec3 result = ambient + diffuse;

    if (u_distance_gradient_enabled) {
        float distance = length(v_position - u_camera_position);
        float t = clamp((distance - u_distance_near) / (u_distance_far - u_distance_near), 0.0, 1.0);

        // Rainbow: cycle hue from 0.0 (red) through the full spectrum
        // Multiply t by 6.0 to get ~1 full rainbow cycle across the range
        // Adjust the multiplier for more/fewer cycles
        float hue = fract(t * 1.0); // 1.0 = one full cycle, 2.0 = two cycles, etc.

        // HSV to RGB conversion (S=1.0, V=1.0 for full saturation/brightness)
        float s = 1.0;
        float v = 1.0;

        float c = v * s;
        float h_prime = hue * 6.0;
        float x = c * (1.0 - abs(mod(h_prime, 2.0) - 1.0));

        vec3 rainbow;
        if (h_prime < 1.0) rainbow = vec3(c, x, 0.0);
        else if (h_prime < 2.0) rainbow = vec3(x, c, 0.0);
        else if (h_prime < 3.0) rainbow = vec3(0.0, c, x);
        else if (h_prime < 4.0) rainbow = vec3(0.0, x, c);
        else if (h_prime < 5.0) rainbow = vec3(x, 0.0, c);
        else rainbow = vec3(c, 0.0, x);

        float m = v - c;
        vec3 gradient_color = rainbow + vec3(m, m, m);

        result = mix(result, result * gradient_color, 0.8);
    }

    if (u_alpha_mode >= 1.0 && u_alpha_mode < 2.0) {
        // MASK
        if (alpha < u_alpha_cutoff) {
            discard;
        }
    }

    if (u_alpha_mode >= 2.0) {
        // BLEND
        frag_color = vec4(result, alpha);
    } else {
        // OPAQUE or MASK
        frag_color = vec4(result, 1.0);
    }
}
"""



class MeshBuffers:

    def __init__(self):
        self.vao: int = 0
        self.vbo_position: int = 0
        self.vbo_normal: int = 0
        self.vbo_joints: int = 0
        self.vbo_weights: int = 0
        self.vbo_texcoord: int = 0
        self.ebo: int = 0
        self.index_count: int = 0
        self.vertex_count: int = 0
        self.has_skinning: bool = False
        self.has_texcoords: bool = False
        self.material_index: Optional[int] = None
        self.diffuse_color: Tuple[float, float, float] = (0.8, 0.8, 0.8)
        self.texture_id: Optional[int] = None
        self.alpha_mode: str = "OPAQUE"  # "OPAQUE", "MASK", "BLEND"
        self.alpha_cutoff: float = 0.5
        self.diffuse_alpha: float = 1.0


class GLRenderer:

    def __init__(self):
        self._program: Optional[int] = None
        self._mesh_buffers: Optional[MeshBuffers] = None
        self._sub_mesh_buffers: List[MeshBuffers] = []
        self._initialized: bool = False
        self._bone_matrices: List[Mat4] = []

        self._texture_cache: dict = {}

        self._distance_gradient_enabled: bool = False
        self._distance_near: float = 2.0
        self._distance_far: float = 20.0
        self._gradient_color_near: Tuple[float, float, float] = (0.0, 0.8, 1.0)
        self._gradient_color_far: Tuple[float, float, float] = (1.0, 0.2, 0.0)

        self._silhouette_mode: bool = False
        self._silhouette_color: Tuple[float, float, float] = (0.35, 0.35, 0.35)
        self._outline_width: float = 0.005

        self._u_model: int = -1
        self._u_view: int = -1
        self._u_projection: int = -1
        self._u_light_dir: int = -1
        self._u_light_color: int = -1
        self._u_ambient: int = -1
        self._u_diffuse_color: int = -1
        self._u_bone_dqs: int = -1
        self._u_has_texture: int = -1
        self._u_base_color_texture: int = -1
        self._u_distance_gradient_enabled: int = -1
        self._u_camera_position: int = -1
        self._u_distance_near: int = -1
        self._u_distance_far: int = -1
        self._u_gradient_color_near: int = -1
        self._u_gradient_color_far: int = -1
        self._u_diffuse_alpha: int = -1
        self._u_alpha_mode: int = -1
        self._u_alpha_cutoff: int = -1
        self._u_silhouette_mode: int = -1
        self._u_silhouette_color: int = -1
        self._u_outline_pass: int = -1
        self._u_outline_width: int = -1

    def initialize(self) -> bool:
        if self._initialized:
            return True

        try:
            vertex_shader = shaders.compileShader(VERTEX_SHADER, GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
            self._program = shaders.compileProgram(vertex_shader, fragment_shader)

            self._u_model = glGetUniformLocation(self._program, 'u_model')
            self._u_view = glGetUniformLocation(self._program, 'u_view')
            self._u_projection = glGetUniformLocation(self._program, 'u_projection')
            self._u_light_dir = glGetUniformLocation(self._program, 'u_light_dir')
            self._u_light_color = glGetUniformLocation(self._program, 'u_light_color')
            self._u_ambient = glGetUniformLocation(self._program, 'u_ambient')
            self._u_diffuse_color = glGetUniformLocation(self._program, 'u_diffuse_color')
            self._u_bone_dqs = glGetUniformLocation(self._program, 'u_bone_dqs[0]')
            self._u_has_texture = glGetUniformLocation(self._program, 'u_has_texture')
            self._u_base_color_texture = glGetUniformLocation(self._program, 'u_base_color_texture')

            self._u_distance_gradient_enabled = glGetUniformLocation(self._program, 'u_distance_gradient_enabled')
            self._u_camera_position = glGetUniformLocation(self._program, 'u_camera_position')
            self._u_distance_near = glGetUniformLocation(self._program, 'u_distance_near')
            self._u_distance_far = glGetUniformLocation(self._program, 'u_distance_far')
            self._u_gradient_color_near = glGetUniformLocation(self._program, 'u_gradient_color_near')
            self._u_gradient_color_far = glGetUniformLocation(self._program, 'u_gradient_color_far')
            self._u_diffuse_alpha = glGetUniformLocation(self._program, 'u_diffuse_alpha')
            self._u_alpha_mode = glGetUniformLocation(self._program, 'u_alpha_mode')
            self._u_alpha_cutoff = glGetUniformLocation(self._program, 'u_alpha_cutoff')
            self._u_silhouette_mode = glGetUniformLocation(self._program, 'u_silhouette_mode')
            self._u_silhouette_color = glGetUniformLocation(self._program, 'u_silhouette_color')
            self._u_outline_pass = glGetUniformLocation(self._program, 'u_outline_pass')
            self._u_outline_width = glGetUniformLocation(self._program, 'u_outline_width')
    
            self._initialized = True
            return True

        except Exception as e:
            logger.debug(f"Failed to initialize renderer: {e}")
            return False

    def upload_mesh(self, positions: List[Vec3], normals: List[Vec3],
                    indices: List[int], skinning_data: Optional[SkinningData] = None,
                    diffuse_color: Optional[Tuple[float, float, float]] = None) -> bool:
        if not self._initialized:
            return False

        if self._mesh_buffers is not None:
            self._delete_buffers(self._mesh_buffers)
        self._sub_mesh_buffers = []

        self._mesh_buffers = MeshBuffers()
        buffers = self._mesh_buffers
        
        if diffuse_color:
            buffers.diffuse_color = diffuse_color

        pos_array = np.array([(p.x, p.y, p.z) for p in positions], dtype=np.float32)
        nrm_array = np.array([(n.x, n.y, n.z) for n in normals], dtype=np.float32)
        idx_array = np.array(indices, dtype=np.uint32)

        buffers.vertex_count = len(positions)
        buffers.index_count = len(indices)

        vao = glGenVertexArrays(1)
        if vao == 0:
            logger.debug("Failed to create VAO")
            return False
        buffers.vao = int(vao)

        glBindVertexArray(buffers.vao)

        buffers.vbo_position = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_position)
        glBufferData(GL_ARRAY_BUFFER, pos_array.nbytes, pos_array, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(0)

        buffers.vbo_normal = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_normal)
        glBufferData(GL_ARRAY_BUFFER, nrm_array.nbytes, nrm_array, GL_STATIC_DRAW)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(1)

        buffers.has_skinning = skinning_data is not None


        joints_array = np.zeros((len(positions), 4), dtype=np.float32)
        weights_array = np.zeros((len(positions), 4), dtype=np.float32)

        if skinning_data is not None:
            for i in range(len(positions)):
                skinning = skinning_data.get_vertex_skinning(i)
                for j, (joint_idx, weight) in enumerate(skinning.get_influences()):
                    if j < 4:
                        joints_array[i, j] = float(joint_idx)
                        weights_array[i, j] = weight

        buffers.vbo_joints = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_joints)
        glBufferData(GL_ARRAY_BUFFER, joints_array.nbytes, joints_array, GL_STATIC_DRAW)
        glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(2)

        buffers.vbo_weights = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_weights)
        glBufferData(GL_ARRAY_BUFFER, weights_array.nbytes, weights_array, GL_STATIC_DRAW)
        glVertexAttribPointer(3, 4, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(3)

        buffers.ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, buffers.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, idx_array.nbytes, idx_array, GL_STATIC_DRAW)

        glBindVertexArray(0)

        return True

    def upload_mesh_with_materials(self, mesh_data) -> bool:
        try:
            if not self._initialized:
                logger.debug("[UPLOAD_DBG] upload_mesh_with_materials: NOT initialized!")
                return False

            for buffers in self._sub_mesh_buffers:
                self._delete_buffers(buffers)
            self._sub_mesh_buffers = []

            if self._mesh_buffers is not None:
                self._delete_buffers(self._mesh_buffers)
                self._mesh_buffers = None

            for texture_id in self._texture_cache.values():
                glDeleteTextures([texture_id])
            self._texture_cache = {}

            all_texcoords = []

            logger.debug(f"[UPLOAD_DBG] sub_meshes count={len(mesh_data.sub_meshes)} materials={len(mesh_data.materials) if mesh_data.materials else 0}")

            for i, sub_mesh in enumerate(mesh_data.sub_meshes):
                all_texcoords.append(sub_mesh.texcoords)
                logger.debug(f"[UPLOAD_DBG] Processing sub_mesh[{i}]: positions={len(sub_mesh.positions)} normals={len(sub_mesh.normals)} indices={len(sub_mesh.indices)} material_index={sub_mesh.material_index}")

                buffers = self._create_sub_mesh_buffers(
                    sub_mesh.positions,
                    sub_mesh.normals,
                    sub_mesh.indices,
                    sub_mesh.skinning_data,
                    sub_mesh.texcoords
                )

                if buffers is None:
                    logger.debug(f"[UPLOAD_DBG] _create_sub_mesh_buffers returned None for sub_mesh[{i}]!")
                    continue

                logger.debug(f"[UPLOAD_DBG] sub_mesh[{i}] buffer created OK, about to set material_index={sub_mesh.material_index}")
                buffers.material_index = sub_mesh.material_index
                logger.debug("[UPLOAD_DBG] material_index set, checking material block...")

                if sub_mesh.material_index is not None and sub_mesh.material_index < len(mesh_data.materials):
                    logger.debug(f"[UPLOAD_DBG] Entering material block for index {sub_mesh.material_index}")
                    mat = mesh_data.materials[sub_mesh.material_index]
                    buffers.diffuse_color = (mat.base_color_factor[0],
                                             mat.base_color_factor[1],
                                             mat.base_color_factor[2])

                    buffers.alpha_mode = mat.alpha_mode
                    buffers.alpha_cutoff = mat.alpha_cutoff
                    buffers.diffuse_alpha = mat.base_color_factor[3]

                    if mat.base_color_texture is not None and mesh_data.textures and mesh_data.images:
                        texture_id = self._create_texture_from_material(
                            mat, mesh_data.textures, mesh_data.images
                        )
                        if texture_id is not None:
                            buffers.texture_id = texture_id

                logger.debug(f"[UPLOAD_DBG] About to append buffer to _sub_mesh_buffers (current count={len(self._sub_mesh_buffers)})")
                self._sub_mesh_buffers.append(buffers)
                logger.debug(f"[UPLOAD_DBG] Appended! count={len(self._sub_mesh_buffers)}")

            logger.debug(f"[UPLOAD_DBG] Loop done, final count={len(self._sub_mesh_buffers)}")
            return len(self._sub_mesh_buffers) > 0
        except Exception as e:
            logger.debug(f"[UPLOAD_DBG] EXCEPTION in upload_mesh_with_materials: {type(e).__name__}: {e}")
            import traceback
            traceback.logger.debug_exc()
            return False

    def _create_sub_mesh_buffers(self, positions: List[Vec3], normals: List[Vec3],
                                 indices: List[int],
                                 skinning_data: Optional[SkinningData] = None,
                                 texcoords: Optional[List[Tuple[float, float]]] = None) -> Optional[MeshBuffers]:
        try:
            buffers = MeshBuffers()

            logger.debug(f"[BUF_DBG] _create_sub_mesh_buffers: positions={len(positions)} normals={len(normals)} indices={len(indices)} texcoords={len(texcoords) if texcoords else 0}")

            pos_array = np.array([(p.x, p.y, p.z) for p in positions], dtype=np.float32)
            nrm_array = np.array([(n.x, n.y, n.z) for n in normals], dtype=np.float32)
            idx_array = np.array(indices, dtype=np.uint32)

            logger.debug(f"[BUF_DBG] numpy arrays created: pos={pos_array.shape} nrm={nrm_array.shape} idx={idx_array.shape}")

            buffers.vertex_count = len(positions)
            buffers.index_count = len(indices)
            buffers.has_texcoords = texcoords is not None and len(texcoords) > 0

            vao = glGenVertexArrays(1)
            logger.debug(f"[BUF_DBG] glGenVertexArrays returned: {vao} type={type(vao)}")
            if vao == 0:
                logger.debug("[BUF_DBG] VAO is 0, returning None")
                return None
            buffers.vao = int(vao)

            glBindVertexArray(buffers.vao)
            logger.debug("[BUF_DBG] VAO bound, creating position VBO")

            buffers.vbo_position = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_position)
            glBufferData(GL_ARRAY_BUFFER, pos_array.nbytes, pos_array, GL_STATIC_DRAW)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(0)
            logger.debug(f"[BUF_DBG] position VBO done: {buffers.vbo_position}")

            buffers.vbo_normal = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_normal)
            glBufferData(GL_ARRAY_BUFFER, nrm_array.nbytes, nrm_array, GL_STATIC_DRAW)
            glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(1)
            logger.debug(f"[BUF_DBG] normal VBO done: {buffers.vbo_normal}")

            buffers.has_skinning = skinning_data is not None

            joints_array = np.zeros((len(positions), 4), dtype=np.float32)
            weights_array = np.zeros((len(positions), 4), dtype=np.float32)

            if skinning_data is not None:
                for i in range(len(positions)):
                    skinning = skinning_data.get_vertex_skinning(i)
                    for j, (joint_idx, weight) in enumerate(skinning.get_influences()):
                        if j < 4:
                            joints_array[i, j] = float(joint_idx)
                            weights_array[i, j] = weight

            buffers.vbo_joints = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_joints)
            glBufferData(GL_ARRAY_BUFFER, joints_array.nbytes, joints_array, GL_STATIC_DRAW)
            glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(2)

            buffers.vbo_weights = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_weights)
            glBufferData(GL_ARRAY_BUFFER, weights_array.nbytes, weights_array, GL_STATIC_DRAW)
            glVertexAttribPointer(3, 4, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(3)
            logger.debug("[BUF_DBG] joints/weights VBOs done")

            if buffers.has_texcoords:
                tex_array = np.array(texcoords, dtype=np.float32)
                logger.debug(f"[BUF_DBG] texcoords array: shape={tex_array.shape}")

                buffers.vbo_texcoord = glGenBuffers(1)
                glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_texcoord)
                glBufferData(GL_ARRAY_BUFFER, tex_array.nbytes, tex_array, GL_STATIC_DRAW)
                glVertexAttribPointer(4, 2, GL_FLOAT, GL_FALSE, 0, None)
                glEnableVertexAttribArray(4)
            else:
                tex_array = np.zeros((len(positions), 2), dtype=np.float32)
                buffers.vbo_texcoord = glGenBuffers(1)
                glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_texcoord)
                glBufferData(GL_ARRAY_BUFFER, tex_array.nbytes, tex_array, GL_STATIC_DRAW)
                glVertexAttribPointer(4, 2, GL_FLOAT, GL_FALSE, 0, None)
                glEnableVertexAttribArray(4)
            logger.debug(f"[BUF_DBG] texcoord VBO done: {buffers.vbo_texcoord}")

            buffers.ebo = glGenBuffers(1)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, buffers.ebo)
            glBufferData(GL_ELEMENT_ARRAY_BUFFER, idx_array.nbytes, idx_array, GL_STATIC_DRAW)
            logger.debug(f"[BUF_DBG] EBO done: {buffers.ebo} index_count={buffers.index_count}")

            glBindVertexArray(0)

            logger.debug(f"[BUF_DBG] SUCCESS: vao={buffers.vao} vertex_count={buffers.vertex_count} index_count={buffers.index_count}")
            return buffers
        except Exception as e:
            logger.debug(f"[BUF_DBG] EXCEPTION in _create_sub_mesh_buffers: {type(e).__name__}: {e}")
            import traceback
            traceback.logger.debug_exc()
            return None

    _debug_render_count: int = 0

    def render(self, skeleton: Optional[Skeleton],
               view_matrix: Mat4, projection_matrix: Mat4,
               model_matrix: Optional[Mat4] = None,
               camera_position: Optional[Vec3] = None) -> None:
        if not self._initialized:
            GLRenderer._debug_render_count += 1
            if GLRenderer._debug_render_count <= 5:
                logger.debug(f"[DEBUG_RENDER] renderer NOT initialized!")
            return

        GLRenderer._debug_render_count += 1
        _dbg = GLRenderer._debug_render_count <= 5
        _dbg_debug_enabled = False

        if _dbg and _dbg_debug_enabled:
            logger.debug(f"[DEBUG_RENDER] sub_mesh_buffers={len(self._sub_mesh_buffers)} "
                  f"mesh_buffers={self._mesh_buffers is not None} "
                  f"has_skeleton={skeleton is not None}")

        if self._sub_mesh_buffers:
            if _dbg and _dbg_debug_enabled:
                for i, buf in enumerate(self._sub_mesh_buffers):
                    logger.debug(f"[DEBUG_RENDER] sub[{i}]: vao={buf.vao} index_count={buf.index_count} "
                          f"diffuse_color={buf.diffuse_color} alpha_mode={buf.alpha_mode} "
                          f"has_skinning={buf.has_skinning} texture_id={buf.texture_id}")
            self._render_sub_meshes(skeleton, view_matrix, projection_matrix, model_matrix, camera_position)
        elif self._mesh_buffers is not None:
            if _dbg and _dbg_debug_enabled:
                buf = self._mesh_buffers
                logger.debug(f"[DEBUG_RENDER] single: vao={buf.vao} index_count={buf.index_count} "
                      f"diffuse_color={buf.diffuse_color} has_skinning={buf.has_skinning}")
            self._render_single_mesh(self._mesh_buffers, skeleton, view_matrix, projection_matrix, model_matrix, camera_position)
        elif _dbg and _dbg_debug_enabled:
            logger.debug(f"[DEBUG_RENDER] NO buffers to render! sub_mesh_buffers=[] mesh_buffers=None")

    def _set_distance_gradient_uniforms(self, camera_position: Optional[Vec3]) -> None:
        if self._distance_gradient_enabled and camera_position is not None:
            glUniform1i(self._u_distance_gradient_enabled, 1)
            glUniform3f(self._u_camera_position, camera_position.x, camera_position.y, camera_position.z)
            glUniform1f(self._u_distance_near, self._distance_near)
            glUniform1f(self._u_distance_far, self._distance_far)
            glUniform3f(self._u_gradient_color_near, *self._gradient_color_near)
            glUniform3f(self._u_gradient_color_far, *self._gradient_color_far)
            glUniform1f(self._u_alpha_mode, 0.0)  # Default to OPAQUE
            glUniform1f(self._u_alpha_cutoff, 0.5)
        else:
            glUniform1i(self._u_distance_gradient_enabled, 0)

    def _set_silhouette_uniforms(self) -> None:
        glUniform1i(self._u_silhouette_mode, 1 if self._silhouette_mode else 0)
        glUniform3f(self._u_silhouette_color, *self._silhouette_color)
        glUniform1i(self._u_outline_pass, 0)
        glUniform1f(self._u_outline_width, self._outline_width)

    def _render_single_mesh(self, buffers: MeshBuffers, skeleton: Optional[Skeleton],
                            view_matrix: Mat4, projection_matrix: Mat4,
                            model_matrix: Optional[Mat4] = None,
                            camera_position: Optional[Vec3] = None) -> None:
        glUseProgram(self._program)

        if model_matrix is None:
            model_matrix = Mat4.identity()

        glUniformMatrix4fv(self._u_model, 1, GL_FALSE, model_matrix.to_list())
        glUniformMatrix4fv(self._u_view, 1, GL_FALSE, view_matrix.to_list())
        glUniformMatrix4fv(self._u_projection, 1, GL_FALSE, projection_matrix.to_list())

        glUniform3f(self._u_light_dir, 0.5, 1.0, 0.5)
        glUniform3f(self._u_light_color, 1.0, 1.0, 1.0)
        glUniform3f(self._u_ambient, 0.2, 0.2, 0.2)
        glUniform3f(self._u_diffuse_color, *buffers.diffuse_color)

        glUniform1f(self._u_diffuse_alpha, 1.0)
        glUniform1f(self._u_alpha_mode, 0.0)
        glUniform1f(self._u_alpha_cutoff, 0.5)

        self._set_distance_gradient_uniforms(camera_position)
        self._set_silhouette_uniforms()

        if skeleton is not None and buffers.has_skinning:
            self._set_bone_dual_quaternions(skeleton)

        if self._silhouette_mode:
            self._draw_mesh_with_outline(buffers)
        else:
            try:
                glBindVertexArray(buffers.vao)
                glDrawElements(GL_TRIANGLES, buffers.index_count, GL_UNSIGNED_INT, None)
                glBindVertexArray(0)
            except Exception as e:
                logger.debug(f"[GL_RENDERER] VAO binding failed (likely offscreen context issue): {e}")
                self._render_without_vao(buffers)

    def _draw_mesh_with_outline(self, buffers: MeshBuffers) -> None:
        glEnable(GL_CULL_FACE)
        glDisable(GL_BLEND)

        glCullFace(GL_FRONT)
        glUniform1i(self._u_outline_pass, 1)
        glDepthMask(GL_TRUE)
        try:
            glBindVertexArray(buffers.vao)
            glDrawElements(GL_TRIANGLES, buffers.index_count, GL_UNSIGNED_INT, None)
            glBindVertexArray(0)
        except Exception as e:
            logger.debug(f"[GL_RENDERER] VAO binding failed in outline pass: {e}")
            self._render_without_vao(buffers)

        glCullFace(GL_BACK)
        glUniform1i(self._u_outline_pass, 0)
        try:
            glBindVertexArray(buffers.vao)
            glDrawElements(GL_TRIANGLES, buffers.index_count, GL_UNSIGNED_INT, None)
            glBindVertexArray(0)
        except Exception as e:
            logger.debug(f"[GL_RENDERER] VAO binding failed in silhouette fill pass: {e}")
            self._render_without_vao(buffers)

        glDisable(GL_CULL_FACE)

    def _render_sub_meshes(self, skeleton, view_matrix, projection_matrix,
                           model_matrix=None, camera_position=None):
        glUseProgram(self._program)

        if model_matrix is None:
            model_matrix = Mat4.identity()

        alpha_mode_map = {"OPAQUE": 0.0, "MASK": 1.0, "BLEND": 2.0}

        glUniformMatrix4fv(self._u_model, 1, GL_FALSE, model_matrix.to_list())
        glUniformMatrix4fv(self._u_view, 1, GL_FALSE, view_matrix.to_list())
        glUniformMatrix4fv(self._u_projection, 1, GL_FALSE, projection_matrix.to_list())

        glUniform3f(self._u_light_dir, 0.5, 1.0, 0.5)
        glUniform3f(self._u_light_color, 1.0, 1.0, 1.0)
        glUniform3f(self._u_ambient, 0.2, 0.2, 0.2)

        self._set_distance_gradient_uniforms(camera_position)
        self._set_silhouette_uniforms()

        if skeleton is not None and any(b.has_skinning for b in self._sub_mesh_buffers):
            self._set_bone_dual_quaternions(skeleton)

        if self._silhouette_mode:
            self._render_sub_meshes_silhouette()
        else:
            self._render_sub_meshes_normal(alpha_mode_map)

        glDepthMask(GL_TRUE)
        glDisable(GL_BLEND)

    def _render_sub_meshes_normal(self, alpha_mode_map: dict) -> None:
        opaque_indices = []
        mask_indices = []
        blend_indices = []
        for i, buffers in enumerate(self._sub_mesh_buffers):
            if buffers.alpha_mode == "BLEND":
                blend_indices.append(i)
            elif buffers.alpha_mode == "MASK":
                mask_indices.append(i)
            else:
                opaque_indices.append(i)
        render_order = opaque_indices + mask_indices + blend_indices

        for i in render_order:
            buffers = self._sub_mesh_buffers[i]

            glUniform3f(self._u_diffuse_color, *buffers.diffuse_color)
            alpha_mode_val = alpha_mode_map.get(buffers.alpha_mode, 0.0)
            glUniform1f(self._u_diffuse_alpha, buffers.diffuse_alpha)
            glUniform1f(self._u_alpha_mode, alpha_mode_val)
            glUniform1f(self._u_alpha_cutoff, buffers.alpha_cutoff)

            if alpha_mode_val >= 2.0:
                glEnable(GL_BLEND)
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                glDepthMask(GL_FALSE)
            else:
                glDisable(GL_BLEND)
                glDepthMask(GL_TRUE)

            if buffers.texture_id is not None and buffers.has_texcoords:
                glActiveTexture(GL_TEXTURE0)
                glBindTexture(GL_TEXTURE_2D, buffers.texture_id)
                glUniform1i(self._u_has_texture, 1)
                glUniform1i(self._u_base_color_texture, 0)
            else:
                glUniform1i(self._u_has_texture, 0)

            try:
                glBindVertexArray(buffers.vao)
                glDrawElements(GL_TRIANGLES, buffers.index_count, GL_UNSIGNED_INT, None)
                glBindVertexArray(0)
            except Exception as e:
                logger.debug(f"[GL_RENDERER] VAO binding failed for sub-mesh: {e}")
                self._render_without_vao(buffers)

            if buffers.texture_id is not None:
                glBindTexture(GL_TEXTURE_2D, 0)

    def _render_sub_meshes_silhouette(self) -> None:
        glEnable(GL_CULL_FACE)
        glUniform1i(self._u_has_texture, 0)
        glUniform1f(self._u_diffuse_alpha, 1.0)
        glUniform1f(self._u_alpha_mode, 0.0)
        glUniform1f(self._u_alpha_cutoff, 0.5)
        glDisable(GL_BLEND)

        glCullFace(GL_FRONT)
        glUniform1i(self._u_outline_pass, 1)
        glDepthMask(GL_TRUE)
        for buffers in self._sub_mesh_buffers:
            try:
                glBindVertexArray(buffers.vao)
                glDrawElements(GL_TRIANGLES, buffers.index_count, GL_UNSIGNED_INT, None)
                glBindVertexArray(0)
            except Exception as e:
                logger.debug(f"[GL_RENDERER] VAO binding failed in outline pass: {e}")
                self._render_without_vao(buffers)

        glCullFace(GL_BACK)
        glUniform1i(self._u_outline_pass, 0)
        glDepthMask(GL_TRUE)
        for buffers in self._sub_mesh_buffers:
            try:
                glBindVertexArray(buffers.vao)
                glDrawElements(GL_TRIANGLES, buffers.index_count, GL_UNSIGNED_INT, None)
                glBindVertexArray(0)
            except Exception as e:
                logger.debug(f"[GL_RENDERER] VAO binding failed in silhouette fill pass: {e}")
                self._render_without_vao(buffers)

        glDisable(GL_CULL_FACE)

    def _set_bone_dual_quaternions(self, skeleton: Skeleton) -> None:
        bone_count = len(skeleton)
        if bone_count > MAX_BONES:
            logger.debug(f"[GL_RENDERER] WARNING: Skeleton has {bone_count} bones, "
                  f"but shader only supports {MAX_BONES}. "
                  f"Bones beyond index {MAX_BONES - 1} will not be skinned.")

        bone_dqs = []
        for bone in skeleton:
            mat = bone.get_final_matrix()
            dq = self._matrix_to_dual_quat(mat)
            bone_dqs.extend(dq)

        
        max_dq_floats = MAX_BONES * 2 * 4  # 2 vec4s per bone, 4 floats per vec4
        while len(bone_dqs) < max_dq_floats:
            bone_dqs.extend([0.0, 0.0, 0.0, 1.0]) 
            bone_dqs.extend([0.0, 0.0, 0.0, 0.0])

        glUniform4fv(self._u_bone_dqs, MAX_BONES * 2, bone_dqs[:max_dq_floats])

    def _render_without_vao(self, buffers: MeshBuffers) -> None:
        if not buffers:
            return

        try:
            logger.debug("[GL_RENDERER] Using fallback rendering without VAO")

            glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_position)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(0)

            # Normal attribute (location 1)
            glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_normal)
            glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(1)

            if buffers.has_skinning:
                # Joint indices (location 2)
                glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_joints)
                glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 0, None)
                glEnableVertexAttribArray(2)
    
                # Joint weights (location 3)
                glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_weights)
                glVertexAttribPointer(3, 4, GL_FLOAT, GL_FALSE, 0, None)
                glEnableVertexAttribArray(3)
    
            # Texture coordinates if available (location 4)
            if buffers.has_texcoords and buffers.vbo_texcoord:
                glBindBuffer(GL_ARRAY_BUFFER, buffers.vbo_texcoord)
                glVertexAttribPointer(4, 2, GL_FLOAT, GL_FALSE, 0, None)
                glEnableVertexAttribArray(4)
    
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, buffers.ebo)
            glDrawElements(GL_TRIANGLES, buffers.index_count, GL_UNSIGNED_INT, None)
    
            glDisableVertexAttribArray(0)
            glDisableVertexAttribArray(1)
            if buffers.has_skinning:
                glDisableVertexAttribArray(2)
                glDisableVertexAttribArray(3)
            if buffers.has_texcoords and buffers.vbo_texcoord:
                glDisableVertexAttribArray(4)
    
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
    
            logger.debug("[GL_RENDERER] Fallback rendering completed")

        except Exception as fallback_e:
            logger.debug(f"[GL_RENDERER] Fallback rendering also failed: {fallback_e}")
            import traceback
            traceback.logger.debug_exc()

    def _matrix_to_dual_quat(self, mat: Mat4) -> List[float]:
        # Quat.from_matrix returns (w, x, y, z) but GLSL uses (x, y, z, w)
        q = Quat.from_matrix(mat)
        q = q.normalized()

        # Extract translation from the matrix (column-major: indices 12, 13, 14)
        tx = mat.m[12]
        ty = mat.m[13]
        tz = mat.m[14]

        # Compute dual quaternion for translation
        # dual = 0.5 * (0, tx, ty, tz) * real
        # Using quaternion multiplication: q1 * q2
        # q is (w, x, y, z), t_quat is (0, tx, ty, tz)
        t_w = 0.0
        t_x = tx
        t_y = ty
        t_z = tz

        # Quaternion multiplication: t * q
        # result.w = t.w*q.w - t.x*q.x - t.y*q.y - t.z*q.z
        # result.x = t.w*q.x + t.x*q.w + t.y*q.z - t.z*q.y
        # result.y = t.w*q.y - t.x*q.z + t.y*q.w + t.z*q.x
        # result.z = t.w*q.z + t.x*q.y - t.y*q.x + t.z*q.w
        dual_w = t_w * q.w - t_x * q.x - t_y * q.y - t_z * q.z
        dual_x = t_w * q.x + t_x * q.w + t_y * q.z - t_z * q.y
        dual_y = t_w * q.y - t_x * q.z + t_y * q.w + t_z * q.x
        dual_z = t_w * q.z + t_x * q.y - t_y * q.x + t_z * q.w

        dual_w *= 0.5
        dual_x *= 0.5
        dual_y *= 0.5
        dual_z *= 0.5

        return [
            q.x, q.y, q.z, q.w,
            dual_x, dual_y, dual_z, dual_w
        ]

    def _create_texture_from_material(self, mat, textures: list, images: list) -> Optional[int]:
        try:
            texture_idx = mat.base_color_texture
            if texture_idx is None or texture_idx >= len(textures):
                return None
            
            texture = textures[texture_idx]
            image_idx = texture.source_image
            if image_idx is None or image_idx >= len(images):
                return None
            
            image = images[image_idx]
            
            # Check cache first - use texture index as key
            cache_key = texture_idx
            if cache_key in self._texture_cache:
                cached_id = self._texture_cache[cache_key]
                return cached_id
            
            from PyQt5.QtGui import QImage
            from PyQt5.QtCore import QByteArray, QBuffer, QIODevice
        
            img_data_bytes = QByteArray(image.data)
            buffer = QBuffer(img_data_bytes)
            buffer.open(QIODevice.ReadOnly)
            img = QImage()
            img.loadFromData(img_data_bytes)
            buffer.close()
        
            if img.isNull():
                logger.debug("[GL_RENDERER] Failed to load image data")
                return None
        
            if img.format() != QImage.Format_RGBA8888:
                img = img.convertToFormat(QImage.Format_RGBA8888)
    
            # Do NOT flip image vertically here. glTF uses top-left origin for images,
            # and UV coordinates are defined relative to that. Flipping the image
            # breaks the texture atlas UV mappings (different regions would get swapped).
            # The shader handles the coordinate system correctly without flipping.
    
            width = img.width()
            height = img.height()
            
            ptr = img.bits()
            ptr.setsize(height * width * 4)
            img_data = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4))
            
            texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, texture_id)
            
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)
            glGenerateMipmap(GL_TEXTURE_2D)
            
            glBindTexture(GL_TEXTURE_2D, 0)
            
            self._texture_cache[cache_key] = int(texture_id)
            

            return int(texture_id)
            
        except Exception as e:
            logger.debug(f"[GL_RENDERER] Failed to create texture: {e}")
            import traceback
            traceback.logger.debug_exc()
            return None

    def _delete_buffers(self, buffers: MeshBuffers) -> None:
        if buffers.vao:
            glDeleteVertexArrays(1, [buffers.vao])
        if buffers.vbo_position:
            glDeleteBuffers(1, [buffers.vbo_position])
        if buffers.vbo_normal:
            glDeleteBuffers(1, [buffers.vbo_normal])
        if buffers.vbo_joints:
            glDeleteBuffers(1, [buffers.vbo_joints])
        if buffers.vbo_weights:
            glDeleteBuffers(1, [buffers.vbo_weights])
        if buffers.vbo_texcoord:
            glDeleteBuffers(1, [buffers.vbo_texcoord])
        if buffers.ebo:
            glDeleteBuffers(1, [buffers.ebo])
        

    def cleanup(self) -> None:
        for buffers in self._sub_mesh_buffers:
            self._delete_buffers(buffers)
        self._sub_mesh_buffers = []

        if self._mesh_buffers is not None:
            self._delete_buffers(self._mesh_buffers)
            self._mesh_buffers = None

        for texture_id in self._texture_cache.values():
            glDeleteTextures([texture_id])
        self._texture_cache = {}

        if self._program is not None:
            glDeleteProgram(self._program)
            self._program = None

        self._initialized = False

    def set_distance_gradient_enabled(self, enabled: bool) -> None:
        self._distance_gradient_enabled = enabled

    def is_distance_gradient_enabled(self) -> bool:
        return self._distance_gradient_enabled

    def set_distance_range(self, near: float, far: float) -> None:
        self._distance_near = max(0.1, near)
        self._distance_far = max(self._distance_near + 0.1, far)

    def set_gradient_colors(self, near_color: Tuple[float, float, float],
                            far_color: Tuple[float, float, float]) -> None:
        self._gradient_color_near = near_color
        self._gradient_color_far = far_color

    def set_silhouette_mode(self, enabled: bool) -> None:
        self._silhouette_mode = enabled

    def is_silhouette_mode(self) -> bool:
        return self._silhouette_mode

    def set_silhouette_color(self, color: Tuple[float, float, float]) -> None:
        self._silhouette_color = color

    def get_silhouette_color(self) -> Tuple[float, float, float]:
        return self._silhouette_color

    def set_outline_width(self, width: float) -> None:
        self._outline_width = max(0.001, width)

    def get_outline_width(self) -> float:
        return self._outline_width

import math
import ctypes
from typing import Optional, Tuple, Dict
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER, 
    GL_FALSE, GL_FLOAT, GL_FRAGMENT_SHADER, GL_STATIC_DRAW, 
    GL_TRIANGLES, GL_UNSIGNED_INT, GL_VERTEX_SHADER, 
    glBindBuffer, glBindVertexArray, glBufferData, glDeleteBuffers, 
    glDeleteProgram, glDeleteVertexArrays, glDrawElements, 
    glEnableVertexAttribArray, glGenBuffers, glGenVertexArrays, 
    glGetUniformLocation, glUniform1f, glUniform3f, glUniformMatrix4fv, 
    glUseProgram, glVertexAttribPointer, shaders
    )
import numpy as np

from ..vec3 import Vec3
from ..mat4 import Mat4
from ..skeleton import Skeleton


JOINT_VERTEX_SHADER = """
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

out vec3 v_normal;
out vec3 v_world_pos;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    v_normal = mat3(u_model) * a_normal;
    v_world_pos = (u_model * vec4(a_position, 1.0)).xyz;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

JOINT_FRAGMENT_SHADER = """
#version 330 core

in vec3 v_normal;
in vec3 v_world_pos;

out vec4 frag_color;

uniform vec3 u_color;
uniform vec3 u_light_dir;
uniform float u_ambient;
uniform float u_highlight;  // 0.0 = normal, 1.0 = selected, 0.5 = hovered

void main() {
    // Diffuse lighting
    vec3 normal = normalize(v_normal);
    float diffuse = max(dot(normal, normalize(u_light_dir)), 0.0);
    float lighting = u_ambient + (1.0 - u_ambient) * diffuse;
    
    // Rim lighting for better 3D perception
    vec3 view_dir = normalize(-v_world_pos);
    float rim = 1.0 - max(dot(view_dir, normal), 0.0);
    rim = pow(rim, 2.0) * 0.3;
    
    vec3 final_color = u_color * lighting + vec3(1.0) * rim;
    
    // Add highlight glow
    if (u_highlight > 0.0) {
        vec3 highlight_color = mix(u_color, vec3(1.0, 0.8, 0.2), u_highlight);
        final_color = mix(final_color, highlight_color, u_highlight * 0.7);
    }
    
    frag_color = vec4(final_color, 1.0);
}
"""


class JointRenderer:   
    COLOR_DEFAULT = (0.2, 0.6, 1.0)
    COLOR_SELECTED = (1.0, 0.5, 0.0)
    COLOR_HOVERED = (1.0, 1.0, 0.3)

    def __init__(self, sphere_radius: float = 0.02, segments: int = 16):
        self._radius = sphere_radius
        self._segments = segments
        
        self._program: Optional[int] = None
        self._vao: int = 0
        self._vbo: int = 0
        self._ebo: int = 0
        self._initialized: bool = False

        self._u_model: int = -1
        self._u_view: int = -1
        self._u_projection: int = -1
        self._u_color: int = -1
        self._u_light_dir: int = -1
        self._u_ambient: int = -1
        self._u_highlight: int = -1

        self._sphere_vertices: np.ndarray = np.array([])
        self._sphere_indices: np.ndarray = np.array([])
        self._sphere_index_count: int = 0

        self._joint_positions: Dict[str, Vec3] = {}
    
    def initialize(self) -> bool:
        
        if self._initialized:
            return True
        
        try:
            vertex_shader = shaders.compileShader(JOINT_VERTEX_SHADER, GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(JOINT_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
            self._program = shaders.compileProgram(vertex_shader, fragment_shader)

            self._u_model = glGetUniformLocation(self._program, 'u_model')
            self._u_view = glGetUniformLocation(self._program, 'u_view')
            self._u_projection = glGetUniformLocation(self._program, 'u_projection')
            self._u_color = glGetUniformLocation(self._program, 'u_color')
            self._u_light_dir = glGetUniformLocation(self._program, 'u_light_dir')
            self._u_ambient = glGetUniformLocation(self._program, 'u_ambient')
            self._u_highlight = glGetUniformLocation(self._program, 'u_highlight')
            
            self._sphere_vertices, self._sphere_indices, self._sphere_index_count = \
                self._generate_sphere_geometry()

            self._vao = glGenVertexArrays(1)
            self._vbo = glGenBuffers(1)
            self._ebo = glGenBuffers(1)

            glBindVertexArray(self._vao)
            
            glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
            glBufferData(GL_ARRAY_BUFFER, self._sphere_vertices.nbytes, self._sphere_vertices, GL_STATIC_DRAW)
            
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ebo)
            glBufferData(GL_ELEMENT_ARRAY_BUFFER, self._sphere_indices.nbytes, self._sphere_indices, GL_STATIC_DRAW)
            
            stride = 6 * 4 # 6 floats per vertex (3 position + 3 normal)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, None)
            glEnableVertexAttribArray(0)
            
            glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
            glEnableVertexAttribArray(1)
            
            glBindVertexArray(0)
            
            self._initialized = True
            return True
            
        except Exception as e:
            print(f"Failed to initialize joint renderer: {e}")
            return False
    
    def _generate_sphere_geometry(self) -> Tuple[np.ndarray, np.ndarray, int]:

        vertices = []
        indices = []
        
        segments = self._segments
        rings = self._segments // 2
        
        for ring in range(rings + 1):
            phi = math.pi * ring / rings
            for seg in range(segments + 1):
                theta = 2 * math.pi * seg / segments

                x = math.sin(phi) * math.cos(theta)
                y = math.cos(phi)
                z = math.sin(phi) * math.sin(theta)

                nx, ny, nz = x, y, z
                
                vertices.extend([x, y, z, nx, ny, nz])
        
        for ring in range(rings):
            for seg in range(segments):
                current = ring * (segments + 1) + seg
                next_ring = current + segments + 1

                indices.extend([
                    current, next_ring, current + 1,
                    current + 1, next_ring, next_ring + 1
                ])
        
        index_count = len(indices)
        vertices_array = np.array(vertices, dtype=np.float32)
        indices_array = np.array(indices, dtype=np.uint32)
        
        return vertices_array, indices_array, index_count
    
    def render(
        self,
        skeleton: Skeleton,
        view_matrix: Mat4,
        projection_matrix: Mat4,
        selected_bone: Optional[str] = None,
        hovered_bone: Optional[str] = None,
        scale: float = 1.0,
        model_matrix: Optional[Mat4] = None
    ) -> None:

        if not self._initialized:
            return

        self._joint_positions.clear()

        glUseProgram(self._program)

        glUniformMatrix4fv(self._u_view, 1, GL_FALSE, view_matrix.to_list())
        glUniformMatrix4fv(self._u_projection, 1, GL_FALSE, projection_matrix.to_list())

        glUniform3f(self._u_light_dir, 0.5, 0.7, 0.5)
        glUniform1f(self._u_ambient, 0.3)

        glBindVertexArray(self._vao)

        for bone in skeleton:
            if not bone.visible:
                continue

            pos = bone.get_world_position()

            if model_matrix is not None:
                pos = model_matrix.transform_point(pos)
            
            self._joint_positions[bone.name] = pos

            if bone.name == selected_bone:
                highlight = 1.0
                color = self.COLOR_SELECTED
            elif bone.name == hovered_bone:
                highlight = 0.5
                color = self.COLOR_HOVERED
            else:
                highlight = 0.0
                color = self.COLOR_DEFAULT

            glUniform3f(self._u_color, color[0], color[1], color[2])
            glUniform1f(self._u_highlight, highlight)

            joint_radius = self._radius * scale
            joint_model_matrix = Mat4([
                joint_radius, 0, 0, 0,
                0, joint_radius, 0, 0,
                0, 0, joint_radius, 0,
                pos.x, pos.y, pos.z, 1
            ])
            glUniformMatrix4fv(self._u_model, 1, GL_FALSE, joint_model_matrix.to_list())

            glDrawElements(GL_TRIANGLES, self._sphere_index_count, GL_UNSIGNED_INT, None)

        glBindVertexArray(0)

    
    def hit_test(
        self,
        mouse_pos: Tuple[int, int],
        skeleton: Skeleton,
        view_matrix: Mat4,
        projection_matrix: Mat4,
        viewport: Tuple[int, int, int, int],
        scale: float = 1.0,
        tolerance: float = 10.0
    ) -> Optional[str]:

        view_proj = projection_matrix * view_matrix
        
        best_bone = None
        best_distance = float('inf')
        
        for bone in skeleton:
            if not bone.visible:
                continue
    
            pos = bone.get_world_position()
            
            screen_x, screen_y = self._project_to_screen(pos, view_proj, viewport)
    
            dx = screen_x - mouse_pos[0]
            dy = screen_y - mouse_pos[1]
            distance = math.sqrt(dx * dx + dy * dy)
            
            joint_tolerance = tolerance + self._radius * scale * 100
            
            if distance < joint_tolerance and distance < best_distance:
                best_distance = distance
                best_bone = bone.name
        
        return best_bone
    
    def _project_to_screen(
        self,
        world_pos: Vec3,
        view_proj: Mat4,
        viewport: Tuple[int, int, int, int]
    ) -> Tuple[float, float]:

        m = view_proj.to_list()
        x = m[0] * world_pos.x + m[4] * world_pos.y + m[8] * world_pos.z + m[12]
        y = m[1] * world_pos.x + m[5] * world_pos.y + m[9] * world_pos.z + m[13]
        w = m[3] * world_pos.x + m[7] * world_pos.y + m[11] * world_pos.z + m[15]
        
        if abs(w) < 1e-10:
            w = 1e-10
        
        ndc_x = x / w
        ndc_y = y / w

        screen_x = viewport[0] + (ndc_x + 1.0) * 0.5 * viewport[2]
        screen_y = viewport[1] + (1.0 - ndc_y) * 0.5 * viewport[3]  # Y is inverted
        
        return (screen_x, screen_y)
    
    def cleanup(self) -> None:
        
        if self._vao:
            glDeleteVertexArrays(1, [self._vao])
            self._vao = 0
        if self._vbo:
            glDeleteBuffers(1, [self._vbo])
            self._vbo = 0
        if self._ebo:
            glDeleteBuffers(1, [self._ebo])
            self._ebo = 0
        if self._program:
            glDeleteProgram(self._program)
            self._program = 0
        
        self._initialized = False

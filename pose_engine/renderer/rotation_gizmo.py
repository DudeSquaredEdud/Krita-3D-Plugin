

import math
import ctypes
from typing import Optional, Tuple, List
from OpenGL.GL import GL_ARRAY_BUFFER, GL_BLEND, GL_DEPTH_TEST, GL_ELEMENT_ARRAY_BUFFER, GL_FALSE, GL_FLOAT, GL_FRAGMENT_SHADER, GL_LEQUAL, GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA, GL_STATIC_DRAW, GL_TRIANGLES, GL_TRUE, GL_UNSIGNED_INT, GL_VERTEX_SHADER, glBindBuffer, glBindVertexArray, glBlendFunc, glBufferData, glDeleteBuffers, glDeleteProgram, glDeleteVertexArrays, glDepthFunc, glDepthMask, glDisable, glDrawElements, glEnable, glEnableVertexAttribArray, glGenBuffers, glGenVertexArrays, glGetUniformLocation, glUniform1f, glUniform3f, glUniformMatrix4fv, glUseProgram, glVertexAttribPointer, shaders
import numpy as np

from ..vec3 import Vec3
from ..mat4 import Mat4
from ..quat import Quat

from .gizmo_base import GIZMO_VERTEX_SHADER, GIZMO_FRAGMENT_SHADER


class RotationGizmo:
    COLOR_X = (0.91, 0.30, 0.24)
    COLOR_Y = (0.15, 0.68, 0.38)
    COLOR_Z = (0.20, 0.60, 0.86)

    COLOR_HOVER = (0.95, 0.77, 0.06)
    COLOR_DRAG = (0.95, 0.61, 0.07)

    def __init__(self, radius: float = 1.0, segments: int = 64, tube_radius: float = 0.05, tube_segments: int = 16):

        self._radius = radius
        self._segments = segments
        self._tube_radius = tube_radius
        self._tube_segments = tube_segments

        self._program: Optional[int] = None
        self._vao: int = 0
        self._vbo: int = 0
        self._ebo: int = 0
        self._initialized: bool = False

        self._u_model: int = -1
        self._u_view: int = -1
        self._u_projection: int = -1
        self._u_color_override: int = -1
        self._u_color_mix: int = -1
        self._u_light_dir: int = -1
        self._u_ambient: int = -1
        self._u_alpha: int = -1

        self._x_vertices: np.ndarray = np.array([])
        self._y_vertices: np.ndarray = np.array([])
        self._z_vertices: np.ndarray = np.array([])

        self._x_indices: np.ndarray = np.array([])
        self._y_indices: np.ndarray = np.array([])
        self._z_indices: np.ndarray = np.array([])

        self._x_index_count: int = 0
        self._y_index_count: int = 0
        self._z_index_count: int = 0

    def initialize(self) -> bool:

        if self._initialized:
            return True

        try:
            vertex_shader = shaders.compileShader(GIZMO_VERTEX_SHADER, GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(GIZMO_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
            self._program = shaders.compileProgram(vertex_shader, fragment_shader)

            self._u_model = glGetUniformLocation(self._program, 'u_model')
            self._u_view = glGetUniformLocation(self._program, 'u_view')
            self._u_projection = glGetUniformLocation(self._program, 'u_projection')
            self._u_color_override = glGetUniformLocation(self._program, 'u_color_override')
            self._u_color_mix = glGetUniformLocation(self._program, 'u_color_mix')
            self._u_light_dir = glGetUniformLocation(self._program, 'u_light_dir')
            self._u_ambient = glGetUniformLocation(self._program, 'u_ambient')
            self._u_alpha = glGetUniformLocation(self._program, 'u_alpha')

            self._x_vertices, self._x_indices, self._x_index_count = self._generate_torus_vertices('X', self.COLOR_X)
            self._y_vertices, self._y_indices, self._y_index_count = self._generate_torus_vertices('Y', self.COLOR_Y)
            self._z_vertices, self._z_indices, self._z_index_count = self._generate_torus_vertices('Z', self.COLOR_Z)

            self._vao = glGenVertexArrays(1)
            self._vbo = glGenBuffers(1)
            self._ebo = glGenBuffers(1)

            self._initialized = True
            return True

        except Exception as e:
            print(f"Failed to initialize rotation gizmo: {e}")
            return False

    def _generate_torus_vertices(self, axis: str, color: Tuple[float, float, float]) -> Tuple[np.ndarray, np.ndarray, int]:

        vertices = []
        indices = []

        major_radius = self._radius
        minor_radius = self._tube_radius
        major_segments = self._segments
        minor_segments = self._tube_segments

        for i in range(major_segments + 1):
            u = (i / major_segments) * 2 * math.pi

            for j in range(minor_segments + 1):
                v = (j / minor_segments) * 2 * math.pi

                x = (major_radius + minor_radius * math.cos(v)) * math.cos(u)
                y = (major_radius + minor_radius * math.cos(v)) * math.sin(u)
                z = minor_radius * math.sin(v)
    
                nx = math.cos(v) * math.cos(u)
                ny = math.cos(v) * math.sin(u)
                nz = math.sin(v)
    
                
                if axis == 'X':
                    
                    pos = (z, x, y)
                    norm = (nz, nx, ny)
                elif axis == 'Y':
                    
                    pos = (x, z, y)
                    norm = (nx, nz, ny)
                else:  
                    
                    pos = (x, y, z)
                    norm = (nx, ny, nz)

                vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])
        
        for i in range(major_segments):
            for j in range(minor_segments):
                v0 = i * (minor_segments + 1) + j
                v1 = v0 + 1
                v2 = (i + 1) * (minor_segments + 1) + j
                v3 = v2 + 1

                indices.extend([v0, v1, v2, v1, v3, v2])

        index_count = len(indices)
        vertices_array = np.array(vertices, dtype=np.float32)
        indices_array = np.array(indices, dtype=np.uint32)

        return vertices_array, indices_array, index_count

    @staticmethod
    def _get_axis_dir(axis: str, axis_rotation: Optional[Mat4] = None) -> Vec3:
        if axis == 'X':
            base = Vec3(1, 0, 0)
        elif axis == 'Y':
            base = Vec3(0, 1, 0)
        else:
            base = Vec3(0, 0, 1)
        if axis_rotation is None:
            return base
        m = axis_rotation.m
        return Vec3(
            m[0] * base.x + m[4] * base.y + m[8] * base.z,
            m[1] * base.x + m[5] * base.y + m[9] * base.z,
            m[2] * base.x + m[6] * base.y + m[10] * base.z
        )

    def render(
        self,
        position: Vec3,
        scale: float,
        view_matrix: Mat4,
        projection_matrix: Mat4,
        hovered_axis: Optional[str] = None,
        dragging_axis: Optional[str] = None,
        axis_rotation: Optional[Mat4] = None
    ) -> None:

        if not self._initialized:
            return

        if axis_rotation is not None:
            rm = axis_rotation.m
            model_matrix = Mat4([
                scale * rm[0], scale * rm[1], scale * rm[2], 0,
                scale * rm[4], scale * rm[5], scale * rm[6], 0,
                scale * rm[8], scale * rm[9], scale * rm[10], 0,
                position.x, position.y, position.z, 1
            ])
        else:
            model_matrix = Mat4([
                scale, 0, 0, 0,
                0, scale, 0, 0,
                0, 0, scale, 0,
                position.x, position.y, position.z, 1
            ])

        glUseProgram(self._program)

        glUniformMatrix4fv(self._u_model, 1, GL_FALSE, model_matrix.to_list())
        glUniformMatrix4fv(self._u_view, 1, GL_FALSE, view_matrix.to_list())
        glUniformMatrix4fv(self._u_projection, 1, GL_FALSE, projection_matrix.to_list())

        glUniform3f(self._u_light_dir, 0.5, 0.7, 0.5)
        glUniform1f(self._u_ambient, 0.3)

        self._render_torus(self._x_vertices, self._x_indices, self._x_index_count, 'X', hovered_axis, dragging_axis)
        self._render_torus(self._y_vertices, self._y_indices, self._y_index_count, 'Y', hovered_axis, dragging_axis)
        self._render_torus(self._z_vertices, self._z_indices, self._z_index_count, 'Z', hovered_axis, dragging_axis)

        glDisable(GL_BLEND)
        glDepthMask(GL_TRUE)


    def _render_torus(
        self,
        vertices: np.ndarray,
        indices: np.ndarray,
        index_count: int,
        axis: str,
        hovered_axis: Optional[str],
        dragging_axis: Optional[str]
    ) -> None:

        if dragging_axis == axis:
            glUniform3f(self._u_color_override, *self.COLOR_DRAG)
            glUniform1f(self._u_color_mix, 1.0)
            glUniform1f(self._u_alpha, 1.0)
        elif hovered_axis == axis:
            glUniform3f(self._u_color_override, *self.COLOR_HOVER)
            glUniform1f(self._u_color_mix, 0.7)
            glUniform1f(self._u_alpha, 1.0)
        else:
            glUniform1f(self._u_color_mix, 0.0)
            glUniform1f(self._u_alpha, 1.0)

        glBindVertexArray(self._vao)

        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

        
        stride = 9 * 4  
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, None)
        glEnableVertexAttribArray(0)

        
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)

        
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(24))
        glEnableVertexAttribArray(2)

        glDrawElements(GL_TRIANGLES, index_count, GL_UNSIGNED_INT, None)

        glBindVertexArray(0)

    def hit_test(
        self,
        mouse_pos: Tuple[int, int],
        gizmo_position: Vec3,
        gizmo_scale: float,
        view_matrix: Mat4,
        projection_matrix: Mat4,
        viewport: Tuple[int, int, int, int],
        axis_rotation: Optional[Mat4] = None
    ) -> Optional[str]:

        view_proj = projection_matrix * view_matrix

        tolerance = 15.0

        best_axis = None
        best_distance = float('inf')

        for axis in ['X', 'Y', 'Z']:
            distance = self._get_screen_distance_to_circle(
                mouse_pos, axis, gizmo_position, gizmo_scale,
                view_proj, viewport, axis_rotation
            )

            if distance < tolerance and distance < best_distance:
                best_distance = distance
                best_axis = axis

        return best_axis

    def _get_screen_distance_to_circle(
        self,
        mouse_pos: Tuple[int, int],
        axis: str,
        center: Vec3,
        scale: float,
        view_proj: Mat4,
        viewport: Tuple[int, int, int, int],
        axis_rotation: Optional[Mat4] = None
    ) -> float:

        min_distance = float('inf')
        radius = self._radius * scale
        axis_dir = self._get_axis_dir(axis, axis_rotation)

        for i in range(self._segments):
            angle = (i / self._segments) * 2 * math.pi

            if axis == 'X':
                local_point = Vec3(0, radius * math.cos(angle), radius * math.sin(angle))
            elif axis == 'Y':
                local_point = Vec3(radius * math.cos(angle), 0, radius * math.sin(angle))
            else:
                local_point = Vec3(radius * math.cos(angle), radius * math.sin(angle), 0)

            if axis_rotation is not None:
                rm = axis_rotation.m
                point = Vec3(
                    rm[0] * local_point.x + rm[4] * local_point.y + rm[8] * local_point.z,
                    rm[1] * local_point.x + rm[5] * local_point.y + rm[9] * local_point.z,
                    rm[2] * local_point.x + rm[6] * local_point.y + rm[10] * local_point.z
                )
            else:
                point = local_point

            world_point = center + point

            screen_x, screen_y = self._project_to_screen(world_point, view_proj, viewport)

            dx = screen_x - mouse_pos[0]
            dy = screen_y - mouse_pos[1]
            distance = math.sqrt(dx * dx + dy * dy)

            min_distance = min(min_distance, distance)

        return min_distance

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

    def get_screen_space_rotation_angle(
        self,
        mouse_pos: Tuple[int, int],
        center: Vec3,
        view_matrix: Mat4,
        projection_matrix: Mat4,
        viewport: Tuple[int, int, int, int]
    ) -> Optional[float]:
        view_proj = projection_matrix * view_matrix
        center_screen = self._project_to_screen(center, view_proj, viewport)

        if center_screen is None:
            return None

        dx = mouse_pos[0] - center_screen[0]
        dy = mouse_pos[1] - center_screen[1]

        # Screen Y is inverted (0 at top), so negate dy for correct rotation
        angle = math.atan2(dx, -dy)

        return angle

    def get_rotation_from_screen_angle(
        self,
        start_angle: float,
        current_angle: float,
        axis: str,
        slow_factor: float = 1.0
    ) -> Quat:

        if axis == 'X':
            axis_vec = Vec3(1, 0, 0)
        elif axis == 'Y':
            axis_vec = Vec3(0, 1, 0)
        else:  # Z
            axis_vec = Vec3(0, 0, 1)

        angle_diff = current_angle - start_angle

        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi

        angle_diff *= slow_factor

        rotation_degrees = math.degrees(angle_diff)
        return Quat.from_axis_angle_degrees(axis_vec, rotation_degrees)

    def get_rotation_from_drag(
        self,
        drag_prev_world: Vec3,
        drag_current_world: Vec3,
        axis: str,
        center: Vec3,
        axis_rotation: Optional[Mat4] = None
    ) -> Quat:

        axis_vec = self._get_axis_dir(axis, axis_rotation)

        def project_to_plane(point: Vec3, axis: Vec3, center: Vec3) -> Vec3:
            relative = point - center
            dot = relative.x * axis.x + relative.y * axis.y + relative.z * axis.z
            return Vec3(
                relative.x - dot * axis.x,
                relative.y - dot * axis.y,
                relative.z - dot * axis.z
            )

        # Project both points onto the rotation plane
        prev_relative = project_to_plane(drag_prev_world, axis_vec, center)
        current_relative = project_to_plane(drag_current_world, axis_vec, center)

        prev_len = prev_relative.length()
        current_len = current_relative.length()

        min_radius = 0.001
        if prev_len < min_radius or current_len < min_radius:
            return Quat.identity()

        prev_dir = Vec3(prev_relative.x / prev_len, prev_relative.y / prev_len, prev_relative.z / prev_len)
        current_dir = Vec3(current_relative.x / current_len, current_relative.y / current_len, current_relative.z / current_len)

        dot = prev_dir.x * current_dir.x + prev_dir.y * current_dir.y + prev_dir.z * current_dir.z

        cross = Vec3(
            prev_dir.y * current_dir.z - prev_dir.z * current_dir.y,
            prev_dir.z * current_dir.x - prev_dir.x * current_dir.z,
            prev_dir.x * current_dir.y - prev_dir.y * current_dir.x
        )

        axis_dot = cross.x * axis_vec.x + cross.y * axis_vec.y + cross.z * axis_vec.z

        dot = max(-1.0, min(1.0, dot))

        angle_radians = math.atan2(axis_dot, dot)

        rotation_degrees = math.degrees(angle_radians)
        return Quat.from_axis_angle_degrees(axis_vec, rotation_degrees)

    def get_point_on_circle_plane(
        self,
        mouse_pos: Tuple[int, int],
        axis: str,
        center: Vec3,
        view_matrix: Mat4,
        projection_matrix: Mat4,
        viewport: Tuple[int, int, int, int],
        axis_rotation: Optional[Mat4] = None
    ) -> Optional[Vec3]:

        ndc_x = (2.0 * (mouse_pos[0] - viewport[0]) / viewport[2]) - 1.0
        ndc_y = 1.0 - (2.0 * (mouse_pos[1] - viewport[1]) / viewport[3])

        view_inv = self._inverse_matrix(view_matrix)
        proj_inv = self._inverse_matrix(projection_matrix)

        cam_pos = Vec3(view_inv[12], view_inv[13], view_inv[14])

        ray_clip = Vec3(ndc_x, ndc_y, -1.0)

        ray_view = Vec3(
            ray_clip.x / proj_inv[0],
            ray_clip.y / proj_inv[5],
            -1.0
        )

        ray_world = Vec3(
            view_inv[0] * ray_view.x + view_inv[4] * ray_view.y + view_inv[8] * ray_view.z,
            view_inv[1] * ray_view.x + view_inv[5] * ray_view.y + view_inv[9] * ray_view.z,
            view_inv[2] * ray_view.x + view_inv[6] * ray_view.y + view_inv[10] * ray_view.z
        )

        ray_len = math.sqrt(ray_world.x**2 + ray_world.y**2 + ray_world.z**2)
        if ray_len < 1e-10:
            return None
        ray_world = Vec3(ray_world.x / ray_len, ray_world.y / ray_len, ray_world.z / ray_len)

        plane_normal = self._get_axis_dir(axis, axis_rotation)

        denom = ray_world.x * plane_normal.x + ray_world.y * plane_normal.y + ray_world.z * plane_normal.z

        if abs(denom) < 1e-10:
            return None

        t = ((center.x - cam_pos.x) * plane_normal.x +
             (center.y - cam_pos.y) * plane_normal.y +
             (center.z - cam_pos.z) * plane_normal.z) / denom

        if t < 0:
            return None

        return Vec3(
            cam_pos.x + t * ray_world.x,
            cam_pos.y + t * ray_world.y,
            cam_pos.z + t * ray_world.z
        )

    def _inverse_matrix(self, m: Mat4) -> List[float]:

        data = m.to_list()
        arr = np.array(data).reshape(4, 4)
        try:
            inv = np.linalg.inv(arr)
            return inv.flatten().tolist()
        except np.linalg.LinAlgError:
            return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]

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

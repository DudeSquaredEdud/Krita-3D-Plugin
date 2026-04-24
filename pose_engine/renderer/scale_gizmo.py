

import ctypes
import math
from typing import List, Optional, Tuple

import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER, GL_FALSE, GL_FLOAT,
    GL_LEQUAL, GL_STATIC_DRAW, GL_TRIANGLES, GL_TRUE, GL_UNSIGNED_INT,
    glBlendFunc, glBufferData, glDeleteBuffers, glDeleteProgram,
    glDeleteVertexArrays, glDepthMask, glDisable, glEnable, glDrawElements,
    glEnableVertexAttribArray, glGenBuffers, glGenVertexArrays,
    glGetUniformLocation, glUniform1f, glUniform3f, glUniformMatrix4fv,
    glUseProgram, glVertexAttribPointer, glBindVertexArray, glBindBuffer,
    GL_BLEND, GL_DEPTH_TEST, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
    glDepthFunc, 
)
from OpenGL.GL import shaders

from ..mat4 import Mat4
from ..vec3 import Vec3
from .gizmo_base import GIZMO_VERTEX_SHADER, GIZMO_FRAGMENT_SHADER


class ScaleGizmo:


    COLOR_X = (1.0, 0.2, 0.2) # Red
    COLOR_Y = (0.2, 1.0, 0.2) # Green
    COLOR_Z = (0.2, 0.2, 1.0) # Blue

    COLOR_HOVER = (1.0, 1.0, 0.2) # Yellow
    COLOR_DRAG = (1.0, 0.8, 0.2) # Orange-yellow

    COLOR_UNIFORM = (0.8, 0.8, 0.8) # Light gray

    CUBE_SIZE = 0.12
    CUBE_OFFSET = 0.85
    SPHERE_RADIUS = 0.15
    SPHERE_SEGMENTS = 16

    def __init__(self, cube_segments: int = 6, sphere_segments: int = 16):

        self._cube_segments = cube_segments
        self._sphere_segments = sphere_segments

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

        self._sphere_vertices: np.ndarray = np.array([])
        self._sphere_indices: np.ndarray = np.array([])
        self._sphere_index_count: int = 0

    def initialize(self) -> bool:

        if self._initialized:
            return True

        try:
            vertex_shader = shaders.compileShader(GIZMO_VERTEX_SHADER, shaders.GL_VERTEX_SHADER)
            fragment_shader = shaders.compileShader(GIZMO_FRAGMENT_SHADER, shaders.GL_FRAGMENT_SHADER)
            self._program = shaders.compileProgram(vertex_shader, fragment_shader)

            self._u_model = glGetUniformLocation(self._program, 'u_model')
            self._u_view = glGetUniformLocation(self._program, 'u_view')
            self._u_projection = glGetUniformLocation(self._program, 'u_projection')
            self._u_color_override = glGetUniformLocation(self._program, 'u_color_override')
            self._u_color_mix = glGetUniformLocation(self._program, 'u_color_mix')
            self._u_light_dir = glGetUniformLocation(self._program, 'u_light_dir')
            self._u_ambient = glGetUniformLocation(self._program, 'u_ambient')
            self._u_alpha = glGetUniformLocation(self._program, 'u_alpha')

            self._x_vertices, self._x_indices, self._x_index_count = self._generate_cube_geometry('X', self.COLOR_X)
            self._y_vertices, self._y_indices, self._y_index_count = self._generate_cube_geometry('Y', self.COLOR_Y)
            self._z_vertices, self._z_indices, self._z_index_count = self._generate_cube_geometry('Z', self.COLOR_Z)

            self._sphere_vertices, self._sphere_indices, self._sphere_index_count = self._generate_sphere_geometry(
                self.SPHERE_RADIUS, self.COLOR_UNIFORM
            )

            self._vao = glGenVertexArrays(1)
            self._vbo = glGenBuffers(1)
            self._ebo = glGenBuffers(1)

            self._initialized = True
            return True

        except Exception as e:
            print(f"Failed to initialize scale gizmo: {e}")
            return False

    def _generate_cube_geometry(self, axis: str, color: Tuple[float, float, float]) -> Tuple[np.ndarray, np.ndarray, int]:

        vertices = []
        indices = []

        size = self.CUBE_SIZE
        half = size / 2.0
        offset = self.CUBE_OFFSET

        face_normals = [
            (1, 0, 0), (-1, 0, 0),
            (0, 1, 0), (0, -1, 0),
            (0, 0, 1), (0, 0, -1)
        ]

        face_corners = [
            [(half, -half, -half), (half, half, -half), (half, half, half), (half, -half, half)],
            [(-half, -half, half), (-half, half, half), (-half, half, -half), (-half, -half, -half)],
            [(-half, half, -half), (-half, half, half), (half, half, half), (half, half, -half)],
            [(-half, -half, half), (-half, -half, -half), (half, -half, -half), (half, -half, half)],
            [(-half, -half, half), (half, -half, half), (half, half, half), (-half, half, half)],
            [(-half, -half, -half), (-half, half, -half), (half, half, -half), (half, -half, -half)]
        ]

        vertex_idx = 0
        for face_idx, (normal, corners) in enumerate(zip(face_normals, face_corners)):
            for corner in corners:
                x, y, z = corner
                if axis == 'X':
                    pos = (x + offset, y, z)
                    norm = normal
                elif axis == 'Y':
                    pos = (x, y + offset, z)
                    norm = normal
                else:  # Z
                    pos = (x, y, z + offset)
                    norm = normal

                vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2], color[0], color[1], color[2]])

            base = vertex_idx
            indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])
            vertex_idx += 4

        index_count = len(indices)
        vertices_array = np.array(vertices, dtype=np.float32)
        indices_array = np.array(indices, dtype=np.uint32)

        return vertices_array, indices_array, index_count

    def _generate_sphere_geometry(self, radius: float, color: Tuple[float, float, float]) -> Tuple[np.ndarray, np.ndarray, int]:

        vertices = []
        indices = []

        segments = self._sphere_segments
        rings = segments

        for ring in range(rings + 1):
            phi = math.pi * ring / rings
            sin_phi = math.sin(phi)
            cos_phi = math.cos(phi)

            for seg in range(segments + 1):
                theta = 2 * math.pi * seg / segments
                sin_theta = math.sin(theta)
                cos_theta = math.cos(theta)

                x = radius * sin_phi * cos_theta
                y = radius * cos_phi
                z = radius * sin_phi * sin_theta

                nx = sin_phi * cos_theta
                ny = cos_phi
                nz = sin_phi * sin_theta

                vertices.extend([x, y, z, nx, ny, nz, color[0], color[1], color[2]])

        for ring in range(rings):
            for seg in range(segments):
                current = ring * (segments + 1) + seg
                next_ring = current + segments + 1

                indices.extend([current, next_ring, current + 1])
                indices.extend([current + 1, next_ring, next_ring + 1])

        index_count = len(indices)
        vertices_array = np.array(vertices, dtype=np.float32)
        indices_array = np.array(indices, dtype=np.uint32)

        return vertices_array, indices_array, index_count

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

        self._render_handle(self._x_vertices, self._x_indices, self._x_index_count, 'X', hovered_axis, dragging_axis)
        self._render_handle(self._y_vertices, self._y_indices, self._y_index_count, 'Y', hovered_axis, dragging_axis)
        self._render_handle(self._z_vertices, self._z_indices, self._z_index_count, 'Z', hovered_axis, dragging_axis)

        self._render_sphere(hovered_axis, dragging_axis)

        glDisable(GL_BLEND)
        glDepthMask(GL_TRUE)

    def _render_handle(
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

    def _render_sphere(
        self,
        hovered_axis: Optional[str],
        dragging_axis: Optional[str]
    ) -> None:

        if dragging_axis == 'UNIFORM':
            glUniform3f(self._u_color_override, *self.COLOR_DRAG)
            glUniform1f(self._u_color_mix, 1.0)
            glUniform1f(self._u_alpha, 1.0)
        elif hovered_axis == 'UNIFORM':
            glUniform3f(self._u_color_override, *self.COLOR_HOVER)
            glUniform1f(self._u_color_mix, 0.7)
            glUniform1f(self._u_alpha, 0.95)
        else:
            glUniform1f(self._u_color_mix, 0.0)
            glUniform1f(self._u_alpha, 0.7)

        glBindVertexArray(self._vao)

        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, self._sphere_vertices.nbytes, self._sphere_vertices, GL_STATIC_DRAW)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self._sphere_indices.nbytes, self._sphere_indices, GL_STATIC_DRAW)

        stride = 9 * 4
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, None)
        glEnableVertexAttribArray(0)

        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)

        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(24))
        glEnableVertexAttribArray(2)

        glDrawElements(GL_TRIANGLES, self._sphere_index_count, GL_UNSIGNED_INT, None)
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

        center_screen_x, center_screen_y = self._project_to_screen(
            gizmo_position, view_proj, viewport
        )
        dx = mouse_pos[0] - center_screen_x
        dy = mouse_pos[1] - center_screen_y
        center_distance = math.sqrt(dx * dx + dy * dy)

        sphere_screen_radius = self.SPHERE_RADIUS * gizmo_scale * 100

        if center_distance < sphere_screen_radius:
            return 'UNIFORM'

        best_axis = None
        best_distance = float('inf')

        for axis in ['X', 'Y', 'Z']:
            distance = self._get_screen_distance_to_handle(
                mouse_pos, axis, gizmo_position, gizmo_scale,
                view_proj, viewport, axis_rotation
            )

            if distance < tolerance and distance < best_distance:
                best_distance = distance
                best_axis = axis

        return best_axis

    def _get_screen_distance_to_handle(
        self,
        mouse_pos: Tuple[int, int],
        axis: str,
        center: Vec3,
        scale: float,
        view_proj: Mat4,
        viewport: Tuple[int, int, int, int],
        axis_rotation: Optional[Mat4] = None
    ) -> float:


        offset = self.CUBE_OFFSET * scale
        if axis == 'X':
            base_dir = Vec3(1, 0, 0)
        elif axis == 'Y':
            base_dir = Vec3(0, 1, 0)
        else:
            base_dir = Vec3(0, 0, 1)

        if axis_rotation is not None:
            rm = axis_rotation.m
            axis_dir = Vec3(
                rm[0] * base_dir.x + rm[4] * base_dir.y + rm[8] * base_dir.z,
                rm[1] * base_dir.x + rm[5] * base_dir.y + rm[9] * base_dir.z,
                rm[2] * base_dir.x + rm[6] * base_dir.y + rm[10] * base_dir.z
            )
        else:
            axis_dir = base_dir

        handle_pos = Vec3(offset * axis_dir.x, offset * axis_dir.y, offset * axis_dir.z)

        world_handle = center + handle_pos

        screen_x, screen_y = self._project_to_screen(world_handle, view_proj, viewport)

        dx = screen_x - mouse_pos[0]
        dy = screen_y - mouse_pos[1]
        distance = math.sqrt(dx * dx + dy * dy)

        return distance

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
        screen_y = viewport[1] + (1.0 - ndc_y) * 0.5 * viewport[3]

        return (screen_x, screen_y)

    def get_scale_from_drag(
        self,
        drag_start_world: Vec3,
        drag_current_world: Vec3,
        axis: str,
        center: Vec3,
        initial_scale: Vec3,
        axis_rotation: Optional[Mat4] = None
    ) -> Vec3:

        start_offset = drag_start_world - center
        current_offset = drag_current_world - center

        if axis == 'UNIFORM':
            start_dist = start_offset.length()
            current_dist = current_offset.length()

            if start_dist < 0.001:
                return initial_scale

            scale_factor = current_dist / start_dist

            return Vec3(
                initial_scale.x * scale_factor,
                initial_scale.y * scale_factor,
                initial_scale.z * scale_factor
            )
        else:
            if axis == 'X':
                base_dir = Vec3(1, 0, 0)
                idx = 0
            elif axis == 'Y':
                base_dir = Vec3(0, 1, 0)
                idx = 1
            else:
                base_dir = Vec3(0, 0, 1)
                idx = 2

            if axis_rotation is not None:
                rm = axis_rotation.m
                axis_dir = Vec3(
                    rm[0] * base_dir.x + rm[4] * base_dir.y + rm[8] * base_dir.z,
                    rm[1] * base_dir.x + rm[5] * base_dir.y + rm[9] * base_dir.z,
                    rm[2] * base_dir.x + rm[6] * base_dir.y + rm[10] * base_dir.z
                )
            else:
                axis_dir = base_dir

            start_component = abs(start_offset.x * axis_dir.x + start_offset.y * axis_dir.y + start_offset.z * axis_dir.z)
            current_component = abs(current_offset.x * axis_dir.x + current_offset.y * axis_dir.y + current_offset.z * axis_dir.z)

            if start_component < 0.001:
                return initial_scale

            scale_factor = current_component / start_component

            new_scale = [initial_scale.x, initial_scale.y, initial_scale.z]
            new_scale[idx] = initial_scale.x * scale_factor if idx == 0 else (
                initial_scale.y * scale_factor if idx == 1 else initial_scale.z * scale_factor
            )

            return Vec3(new_scale[0], new_scale[1], new_scale[2])

    def get_point_on_axis(
        self,
        mouse_pos: Tuple[int, int],
        axis: str,
        center: Vec3,
        scale: float,
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

        if axis == 'UNIFORM':
            plane_normal = Vec3(view_inv[8], view_inv[9], view_inv[10])
            plane_len = math.sqrt(plane_normal.x**2 + plane_normal.y**2 + plane_normal.z**2)
            if plane_len < 1e-10:
                return None
            plane_normal = Vec3(plane_normal.x / plane_len, plane_normal.y / plane_len, plane_normal.z / plane_len)

            denom = ray_world.x * plane_normal.x + ray_world.y * plane_normal.y + ray_world.z * plane_normal.z
            if abs(denom) < 1e-10:
                return None

            diff = center - cam_pos
            t = (diff.x * plane_normal.x + diff.y * plane_normal.y + diff.z * plane_normal.z) / denom

            return Vec3(
                cam_pos.x + t * ray_world.x,
                cam_pos.y + t * ray_world.y,
                cam_pos.z + t * ray_world.z
            )
        else:
            if axis == 'X':
                base_dir = Vec3(1, 0, 0)
            elif axis == 'Y':
                base_dir = Vec3(0, 1, 0)
            else:
                base_dir = Vec3(0, 0, 1)

            if axis_rotation is not None:
                rm = axis_rotation.m
                axis_dir = Vec3(
                    rm[0] * base_dir.x + rm[4] * base_dir.y + rm[8] * base_dir.z,
                    rm[1] * base_dir.x + rm[5] * base_dir.y + rm[9] * base_dir.z,
                    rm[2] * base_dir.x + rm[6] * base_dir.y + rm[10] * base_dir.z
                )
            else:
                axis_dir = base_dir

            cross = Vec3(
                ray_world.y * axis_dir.z - ray_world.z * axis_dir.y,
                ray_world.z * axis_dir.x - ray_world.x * axis_dir.z,
                ray_world.x * axis_dir.y - ray_world.y * axis_dir.x
            )
            cross_len_sq = cross.x**2 + cross.y**2 + cross.z**2

            if cross_len_sq < 1e-10:
                return None

            diff = center - cam_pos
            denom = cross_len_sq
            s = ((diff.x * axis_dir.y * cross.z + diff.y * axis_dir.z * cross.x + diff.z * axis_dir.x * cross.y -
                  diff.x * axis_dir.z * cross.y - diff.y * axis_dir.x * cross.z - diff.z * axis_dir.y * cross.x) / denom)

            ray_point = Vec3(
                cam_pos.x + s * ray_world.x,
                cam_pos.y + s * ray_world.y,
                cam_pos.z + s * ray_world.z
            )

            relative = ray_point - center
            t = relative.x * axis_dir.x + relative.y * axis_dir.y + relative.z * axis_dir.z

            return Vec3(
                center.x + t * axis_dir.x,
                center.y + t * axis_dir.y,
                center.z + t * axis_dir.z
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

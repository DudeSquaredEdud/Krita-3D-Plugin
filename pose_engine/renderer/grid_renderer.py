from typing import Optional, Tuple
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_BLEND, GL_DEPTH_TEST, GL_FALSE, GL_FLOAT,
    GL_FRAGMENT_SHADER, GL_LINES, GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA,
    GL_STATIC_DRAW, GL_TRUE, GL_VERTEX_SHADER,
    glBindBuffer, glBindVertexArray, glBlendFunc, glBufferData,
    glDeleteBuffers, glDeleteProgram, glDeleteVertexArrays,
    glDepthMask, glDisable, glDrawArrays, glEnable,
    glEnableVertexAttribArray, glGenBuffers, glGenVertexArrays,
    glGetUniformLocation, glUniform1f, glUniform3f,
    glUniformMatrix4fv, glUseProgram, glVertexAttribPointer, glLineWidth,
)
from OpenGL.GL import shaders
import numpy as np

from ..mat4 import Mat4
from ..logger import get_logger

logger = get_logger(__name__)

GRID_VERTEX_SHADER = """
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_color;

out vec3 v_color;
out float v_distance;

uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    vec4 world_pos = vec4(a_position, 1.0);
    vec4 view_pos = u_view * world_pos;
    v_distance = length(view_pos.xyz);
    gl_Position = u_projection * view_pos;
    v_color = a_color;
}
"""

GRID_FRAGMENT_SHADER = """
#version 330 core

in vec3 v_color;
in float v_distance;

out vec4 frag_color;

uniform float u_fade_near;
uniform float u_fade_far;

void main() {
    float fade = 1.0 - smoothstep(u_fade_near, u_fade_far, v_distance);
    frag_color = vec4(v_color, fade);
}
"""


class GridRenderer:

    COLOR_AXIS_X = (0.2, 0.2, 0.9)
    COLOR_AXIS_Z = (0.9, 0.2, 0.2)
    COLOR_MAJOR = (0.5, 0.5, 0.5)
    COLOR_MINOR = (0.3, 0.3, 0.3)

    def __init__(self):
        self._program: Optional[int] = None
        self._vao: int = 0
        self._vbo: int = 0
        self._initialized: bool = False
        self._vertex_count: int = 0

        self._u_view: int = -1
        self._u_projection: int = -1
        self._u_fade_near: int = -1
        self._u_fade_far: int = -1

        self._size: int = 10
        self._spacing: float = 1.0
        self._major_every: int = 5
        self._fade_near: float = 5.0
        self._fade_far: float = 30.0

    def initialize(self) -> bool:
        if self._initialized:
            return True

        try:
            vs = shaders.compileShader(GRID_VERTEX_SHADER, GL_VERTEX_SHADER)
            fs = shaders.compileShader(GRID_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
            self._program = shaders.compileProgram(vs, fs)

            self._u_view = glGetUniformLocation(self._program, 'u_view')
            self._u_projection = glGetUniformLocation(self._program, 'u_projection')
            self._u_fade_near = glGetUniformLocation(self._program, 'u_fade_near')
            self._u_fade_far = glGetUniformLocation(self._program, 'u_fade_far')

            self._vao = glGenVertexArrays(1)
            self._vbo = glGenBuffers(1)

            self._build_grid()

            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to initialize GridRenderer: {e}")
            return False

    def _generate_grid_vertices(self) -> list:
        vertices = []
        n = self._size
        spacing = self._spacing
        major_every = self._major_every

        for i in range(-n, n + 1):
            pos = i * spacing
            is_major = (i % major_every == 0) if major_every > 0 else False
            is_axis = (i == 0)

            if is_axis:
                color_x = self.COLOR_AXIS_X
                color_z = self.COLOR_AXIS_Z
            elif is_major:
                color_x = self.COLOR_MAJOR
                color_z = self.COLOR_MAJOR
            else:
                color_x = self.COLOR_MINOR
                color_z = self.COLOR_MINOR

            vertices.extend([
                float(-n) * spacing, 0.0, pos, *color_z,
                float(n) * spacing, 0.0, pos, *color_z,
            ])

            vertices.extend([
                pos, 0.0, float(-n) * spacing, *color_x,
                pos, 0.0, float(n) * spacing, *color_x,
            ])

        return vertices

    def _build_grid(self) -> None:
        vertices = self._generate_grid_vertices()
        self._vertex_count = len(vertices) // 6

        if self._vertex_count > 0 and self._vao:
            vertex_data = np.array(vertices, dtype=np.float32)
            stride = 6 * 4

            glBindVertexArray(self._vao)
            glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
            glBufferData(GL_ARRAY_BUFFER, vertex_data.nbytes, vertex_data, GL_STATIC_DRAW)

            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, None)
            glEnableVertexAttribArray(0)

            from ctypes import c_void_p
            glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, c_void_p(12))
            glEnableVertexAttribArray(1)

            glBindVertexArray(0)

    def set_fade(self, near: float, far: float) -> None:
        self._fade_near = near
        self._fade_far = far

    def set_size(self, size: int) -> None:
        self._size = size
        if self._initialized:
            self._build_grid()

    def render(self, view_matrix: Mat4, projection_matrix: Mat4) -> None:
        if not self._initialized or self._vertex_count == 0:
            return

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDepthMask(False)

        glUseProgram(self._program)

        glUniformMatrix4fv(self._u_view, 1, GL_FALSE, view_matrix.to_list())
        glUniformMatrix4fv(self._u_projection, 1, GL_FALSE, projection_matrix.to_list())
        glUniform1f(self._u_fade_near, self._fade_near)
        glUniform1f(self._u_fade_far, self._fade_far)

        glBindVertexArray(self._vao)
        glDrawArrays(GL_LINES, 0, self._vertex_count)
        glBindVertexArray(0)

        glDepthMask(True)
        glEnable(GL_DEPTH_TEST)

    def cleanup(self) -> None:
        if self._vao:
            glDeleteVertexArrays(1, [self._vao])
            self._vao = 0
        if self._vbo:
            glDeleteBuffers(1, [self._vbo])
            self._vbo = 0
        if self._program:
            glDeleteProgram(self._program)
            self._program = 0

        self._initialized = False

from typing import Optional, Tuple
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_BLEND, GL_DEPTH_TEST, GL_FALSE, GL_FLOAT,
    GL_FRAGMENT_SHADER, GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA,
    GL_STATIC_DRAW, GL_TRIANGLES, GL_TRUE, GL_UNSIGNED_INT,
    GL_VERTEX_SHADER,
    glBindBuffer, glBindVertexArray, glBlendFunc, glBufferData,
    glDeleteBuffers, glDeleteProgram, glDeleteVertexArrays,
    glDepthMask, glDisable, glDrawArrays, glEnable,
    glEnableVertexAttribArray, glGenBuffers, glGenVertexArrays,
    glGetUniformLocation, glUniform1f, glUniform2f, glUniform4f,
    glUniformMatrix4fv, glUseProgram, glVertexAttribPointer,
    shaders
)
import numpy as np
from ..mat4 import Mat4
from ..logger import get_logger

logger = get_logger(__name__)

BBOX_VERTEX_SHADER = """
#version 330 core

layout(location = 0) in vec2 a_position;
layout(location = 1) in vec4 a_color;

out vec4 v_color;

uniform vec2 u_viewport_size;

void main() {
    // Convert pixel coords to NDC (-1..1)
    // Pixel (0,0) maps to NDC (-1, 1), pixel (vp_w, vp_h) maps to (1, -1)
    vec2 ndc = (a_position / u_viewport_size) * 2.0 - 1.0;
    ndc.y = -ndc.y; // Flip Y: pixel Y goes down, NDC Y goes up
    gl_Position = vec4(ndc, 0.0, 1.0);
    v_color = a_color;
}
"""

BBOX_FRAGMENT_SHADER = """
#version 330 core

in vec4 v_color;
out vec4 frag_color;

void main() {
    frag_color = v_color;
}
"""


class BoundingBoxRenderer:
    COLOR_OVERLAY = (0.15, 0.15, 0.15, 1.0)
    COLOR_BORDER = (1.0, 1.0, 1.0, 0.8)

    def __init__(self):
        self._program: Optional[int] = None
        self._vao: int = 0
        self._vbo: int = 0
        self._initialized: bool = False

        self._u_viewport_size: int = -1

    def initialize(self) -> bool:
        if self._initialized:
            return True

        
        try:
            vs = shaders.compileShader(BBOX_VERTEX_SHADER, GL_VERTEX_SHADER)
            fs = shaders.compileShader(BBOX_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
            self._program = shaders.compileProgram(vs, fs)

            self._u_viewport_size = glGetUniformLocation(
                self._program, 'u_viewport_size'
            )

            self._vao = glGenVertexArrays(1)
            self._vbo = glGenBuffers(1)

            glBindVertexArray(self._vao)
            glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
            glBufferData(GL_ARRAY_BUFFER, 0, None, GL_STATIC_DRAW)

            glVertexAttribPointer(
                0, 2, GL_FLOAT, GL_FALSE, 24, None
            )
            glEnableVertexAttribArray(0)

            from ctypes import c_void_p
            glVertexAttribPointer(
                1, 4, GL_FLOAT, GL_FALSE, 24, c_void_p(8)
            )
            glEnableVertexAttribArray(1)

            glBindVertexArray(0)

            self._initialized = True
            return True

        except Exception as e:
            print(f"Failed to initialize BoundingBoxRenderer: {e}")
            return False

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


    def render(self, viewport_w: int, viewport_h: int,
               crop_x: int, crop_y: int,
               crop_w: int, crop_h: int) -> None:
        if not self._initialized:
            logger.debug("[BBOX] render() called but not initialized")
            return

        vertices = self._build_vertices(
            viewport_w, viewport_h, crop_x, crop_y, crop_w, crop_h
        )

        vertex_count = len(vertices) // 6
        if vertex_count == 0:
            logger.debug(
                f"[BBOX] render() produced 0 vertices for "
                f"vp={viewport_w}x{viewport_h} crop=({crop_x},{crop_y},{crop_w},{crop_h})"
            )
            return

        logger.debug(
            f"[BBOX] render() drawing {vertex_count} triangles, "
            f"vp={viewport_w}x{viewport_h}, crop=({crop_x},{crop_y},{crop_w},{crop_h})"
        )

        vertex_data = np.array(vertices, dtype=np.float32)

        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(
            GL_ARRAY_BUFFER, vertex_data.nbytes, vertex_data, GL_STATIC_DRAW
        )

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDepthMask(GL_FALSE)

        glUseProgram(self._program)
        glUniform2f(self._u_viewport_size, float(viewport_w), float(viewport_h))

        glBindVertexArray(self._vao)
        glDrawArrays(GL_TRIANGLES, 0, vertex_count)
        glBindVertexArray(0)

        glDepthMask(GL_TRUE)
        glEnable(GL_DEPTH_TEST)

    def _build_vertices(self, vw: int, vh: int,
                        cx: int, cy: int, cw: int, ch: int) -> list:
        verts = []
        ov = self.COLOR_OVERLAY
        bd = self.COLOR_BORDER
        border_thickness = 2.0

        clamped_cx = max(0, cx)
        clamped_cy = max(0, cy)
        clamped_right = min(cx + cw, vw)
        clamped_bottom = min(cy + ch, vh)
        clamped_cw = clamped_right - clamped_cx
        clamped_ch = clamped_bottom - clamped_cy

        if clamped_cx == 0 and clamped_cy == 0 and clamped_right >= vw and clamped_bottom >= vh:
            return verts

        
        if clamped_cy > 0:
            verts.extend(self._quad(0, 0, vw, clamped_cy, ov))

        
        if clamped_bottom < vh:
            verts.extend(self._quad(0, clamped_bottom, vw, vh - clamped_bottom, ov))

        
        if clamped_cx > 0:
            verts.extend(self._quad(0, clamped_cy, clamped_cx, clamped_ch, ov))

        
        if clamped_right < vw:
            verts.extend(self._quad(clamped_right, clamped_cy, vw - clamped_right, clamped_ch, ov))

        bt = border_thickness
        
        # Top border
        if clamped_cy > 0:
            verts.extend(self._quad(clamped_cx, clamped_cy - bt, clamped_cw, bt, bd))
        # Bottom border
        if clamped_bottom < vh:
            verts.extend(self._quad(clamped_cx, clamped_bottom, clamped_cw, bt, bd))
        # Left border
        if clamped_cx > 0:
            verts.extend(self._quad(clamped_cx - bt, clamped_cy, bt, clamped_ch, bd))
        # Right border
        if clamped_right < vw:
            verts.extend(self._quad(clamped_right, clamped_cy, bt, clamped_ch, bd))

        return verts

    @staticmethod
    def _quad(x: float, y: float, w: float, h: float,
              color: Tuple[float, float, float, float]) -> list:

        r, g, b, a = color
        x2 = x + w
        y2 = y + h
        return [
            # Triangle 1
            x,  y,  r, g, b, a,
            x2, y,  r, g, b, a,
            x2, y2, r, g, b, a,
            # Triangle 2
            x,  y,  r, g, b, a,
            x2, y2, r, g, b, a,
            x,  y2, r, g, b, a,
        ]

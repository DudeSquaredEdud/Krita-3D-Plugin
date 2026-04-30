import pytest
import math
from unittest.mock import MagicMock, patch

from pose_engine.renderer.grid_renderer import GridRenderer
from pose_engine.mat4 import Mat4


class TestGridRendererConstruction:

    def test_grid_renderer_default_attributes(self):
        renderer = GridRenderer()
        assert renderer._program is None
        assert renderer._vao == 0
        assert renderer._vbo == 0
        assert renderer._initialized is False
        assert renderer._vertex_count == 0
        assert renderer._size == 10
        assert renderer._spacing == 1.0
        assert renderer._major_every == 5
        assert renderer._fade_near == 5.0
        assert renderer._fade_far == 30.0

    def test_grid_renderer_color_constants(self):
        assert GridRenderer.COLOR_AXIS_X == (0.9, 0.2, 0.2)
        assert GridRenderer.COLOR_AXIS_Z == (0.2, 0.2, 0.9)
        assert GridRenderer.COLOR_MAJOR == (0.5, 0.5, 0.5)
        assert GridRenderer.COLOR_MINOR == (0.3, 0.3, 0.3)


class TestGridRendererSetters:

    def test_set_fade(self):
        renderer = GridRenderer()
        renderer.set_fade(10.0, 50.0)
        assert renderer._fade_near == 10.0
        assert renderer._fade_far == 50.0

    def test_set_size_not_initialized(self):
        renderer = GridRenderer()
        renderer.set_size(20)
        assert renderer._size == 20


class TestGridRendererBuildGridLogic:

    def test_build_grid_vertex_count_size_2(self):
        renderer = GridRenderer()
        renderer._size = 2
        renderer._major_every = 2
        vertices = renderer._generate_grid_vertices()
        # size=2: lines from -2 to +2 = 5 positions per direction
        # 5 Z-lines + 5 X-lines = 10 lines, each 2 vertices = 20 vertices
        # Each vertex = 6 floats (3 pos + 3 color), so 120 floats total
        assert len(vertices) == 120
        assert len(vertices) // 6 == 20

    def test_build_grid_vertex_count_size_1(self):
        renderer = GridRenderer()
        renderer._size = 1
        renderer._major_every = 5
        vertices = renderer._generate_grid_vertices()
        # size=1: lines at -1, 0, +1 = 3 per direction = 6 total lines
        # 6 lines * 2 verts * 6 floats = 72 floats
        assert len(vertices) == 72

    def test_build_grid_custom_spacing(self):
        renderer = GridRenderer()
        renderer._size = 5
        renderer._spacing = 0.5
        renderer._major_every = 4
        vertices = renderer._generate_grid_vertices()
        # size=5: range(-5, 6) = 11 positions per direction
        # 11 Z-lines + 11 X-lines = 22 lines
        # 22 lines * 2 verts * 6 floats = 264 floats
        # Spacing affects vertex positions, not line count
        assert len(vertices) == 264
        # Verify spacing is applied: first Z-line at i=-5, pos = -5 * 0.5 = -2.5
        assert abs(vertices[0] - (-2.5)) < 1e-6

    def test_build_grid_axis_colors_at_origin(self):
        renderer = GridRenderer()
        renderer._size = 1
        renderer._major_every = 5
        vertices = renderer._generate_grid_vertices()
        # size=1: range(-1, 2) = i=-1, i=0, i=1
        # Each i produces 2 lines (Z then X), each line = 2 verts * 6 floats = 12 floats
        # i=-1: offset 0 (Z-line) and offset 12 (X-line) — minor color
        # i=0:  offset 24 (Z-line) and offset 36 (X-line) — axis color
        # i=1:  offset 48 (Z-line) and offset 60 (X-line) — minor color
        # Check Z-axis line color at i=0
        z_line_color_v0 = vertices[24 + 3:24 + 6]
        z_line_color_v1 = vertices[24 + 9:24 + 12]
        assert z_line_color_v0 == list(GridRenderer.COLOR_AXIS_Z)
        assert z_line_color_v1 == list(GridRenderer.COLOR_AXIS_Z)
        # Check X-axis line color at i=0
        x_line_color_v0 = vertices[36 + 3:36 + 6]
        x_line_color_v1 = vertices[36 + 9:36 + 12]
        assert x_line_color_v0 == list(GridRenderer.COLOR_AXIS_X)
        assert x_line_color_v1 == list(GridRenderer.COLOR_AXIS_X)

    def test_build_grid_major_colors(self):
        renderer = GridRenderer()
        renderer._size = 10
        renderer._major_every = 5
        vertices = renderer._generate_grid_vertices()
        # i=5 is a major line (5 % 5 == 0), not axis (5 != 0)
        # Find the line for i=5: it's the 6th pair (i=-10,-9,...,5)
        # i ranges from -10 to 10, so i=5 is at index 15 in the loop
        # Each i produces 2 lines (Z then X), each line = 12 floats
        # i=5 starts at float offset: 15 * 24 = 360
        offset = 15 * 24
        z_color = vertices[offset + 3:offset + 6]
        assert z_color == list(GridRenderer.COLOR_MAJOR)


class TestGridRendererRender:

    def test_render_not_initialized(self):
        renderer = GridRenderer()
        view = Mat4()
        proj = Mat4()
        renderer.render(view, proj)

    def test_render_zero_lines(self):
        renderer = GridRenderer()
        renderer._initialized = True
        renderer._vertex_count = 0
        view = Mat4()
        proj = Mat4()
        renderer.render(view, proj)


class TestGridRendererCleanup:

    def test_cleanup_resets_state(self):
        renderer = GridRenderer()
        renderer._initialized = True
        renderer._vao = 1
        renderer._vbo = 1
        renderer._program = 1
        with patch('pose_engine.renderer.grid_renderer.glDeleteVertexArrays'), \
             patch('pose_engine.renderer.grid_renderer.glDeleteBuffers'), \
             patch('pose_engine.renderer.grid_renderer.glDeleteProgram'):
            renderer.cleanup()
        assert renderer._vao == 0
        assert renderer._vbo == 0
        assert renderer._program == 0
        assert renderer._initialized is False

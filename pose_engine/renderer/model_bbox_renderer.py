"""
3D Bounding Box Wireframe Renderer.

Renders axis-aligned bounding boxes as wireframe lines in 3D space.
"""

from typing import Optional, Tuple
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_DYNAMIC_DRAW, GL_FALSE, GL_FLOAT, GL_LINES, GL_TRUE,
    GL_VERTEX_SHADER, GL_FRAGMENT_SHADER,
    glBindBuffer, glBindVertexArray, glBufferData, glDeleteBuffers, glDeleteProgram, glDeleteVertexArrays, glDrawArrays,
    glEnableVertexAttribArray, glGenBuffers, glGenVertexArrays,
    glGetUniformLocation, glUniform4f, glUniformMatrix4fv,
    glUseProgram, glVertexAttribPointer, glLineWidth
)
from OpenGL.GL import shaders
import numpy as np
from ..vec3 import Vec3
from ..mat4 import Mat4
from ..logger import get_logger

logger = get_logger(__name__)


MODEL_BBOX_VERTEX_SHADER = """
#version 330 core

layout(location = 0) in vec3 a_position;

uniform mat4 u_mvp;

void main() {
    gl_Position = u_mvp * vec4(a_position, 1.0);
}
"""

MODEL_BBOX_FRAGMENT_SHADER = """
#version 330 core

uniform vec4 u_color;
out vec4 frag_color;

void main() {
    frag_color = u_color;
}
"""


class ModelBBoxRenderer:
    """
    Renders 3D bounding boxes as wireframe lines.
    
    Usage:
        renderer = ModelBBoxRenderer()
        renderer.initialize()
        
        # In render loop:
        renderer.render(min_pt, max_pt, view_matrix, proj_matrix, color)
        
        # Cleanup:
        renderer.cleanup()
    """
    
    # Default colors for different contexts
    COLOR_SELECTED = (1.0, 0.85, 0.0, 1.0)      # Golden yellow
    COLOR_UNSELECTED = (0.4, 0.8, 1.0, 0.7)     # Light blue
    COLOR_HOVER = (1.0, 1.0, 1.0, 0.8)          # White
    
    def __init__(self):
        self._program: Optional[int] = None
        self._vao: int = 0
        self._vbo: int = 0
        self._initialized: bool = False
        
        self._u_mvp: int = -1
        self._u_color: int = -1
    
    def initialize(self) -> bool:
        """Initialize OpenGL resources."""
        if self._initialized:
            return True
        
        try:
            # Compile shaders
            vs = shaders.compileShader(MODEL_BBOX_VERTEX_SHADER, GL_VERTEX_SHADER)
            fs = shaders.compileShader(MODEL_BBOX_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
            self._program = shaders.compileProgram(vs, fs)
            
            # Get uniform locations
            self._u_mvp = glGetUniformLocation(self._program, 'u_mvp')
            self._u_color = glGetUniformLocation(self._program, 'u_color')
            
            # Create VAO and VBO
            self._vao = glGenVertexArrays(1)
            self._vbo = glGenBuffers(1)
            
            # Setup VAO
            glBindVertexArray(self._vao)
            glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
            
            # Pre-allocate buffer for 24 vertices (12 lines * 2 vertices)
            # Each vertex has 3 floats (x, y, z)
            glBufferData(GL_ARRAY_BUFFER, 24 * 3 * 4, None, GL_DYNAMIC_DRAW)
            
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(0)
            
            glBindVertexArray(0)
            
            self._initialized = True
            logger.debug("[ModelBBox] Initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"[ModelBBox] Failed to initialize: {e}")
            return False
    
    def cleanup(self) -> None:
        """Release OpenGL resources."""
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
        logger.debug("[ModelBBox] Cleaned up")
    
    def render(self, min_pt: Vec3, max_pt: Vec3,
               view_matrix: Mat4, proj_matrix: Mat4,
               color: Tuple[float, float, float, float] = None,
               line_width: float = 1.5) -> None:
        """
        Render a 3D bounding box as wireframe lines.
        
        Args:
            min_pt: Minimum corner of the bounding box
            max_pt: Maximum corner of the bounding box
            view_matrix: Camera view matrix
            proj_matrix: Camera projection matrix
            color: RGBA color tuple (default: golden yellow)
            line_width: Line thickness in pixels
        """
        if not self._initialized:
            return
        
        if color is None:
            color = self.COLOR_SELECTED
        
        # Build vertex data for 12 edges of a box
        x0, y0, z0 = min_pt.x, min_pt.y, min_pt.z
        x1, y1, z1 = max_pt.x, max_pt.y, max_pt.z
        
        # 12 edges = 24 vertices (2 per line)
        vertices = np.array([
            # Bottom face edges
            x0, y0, z0,  x1, y0, z0,   # Front edge
            x1, y0, z0,  x1, y0, z1,   # Right edge
            x1, y0, z1,  x0, y0, z1,   # Back edge
            x0, y0, z1,  x0, y0, z0,   # Left edge
            
            # Top face edges
            x0, y1, z0,  x1, y1, z0,   # Front edge
            x1, y1, z0,  x1, y1, z1,   # Right edge
            x1, y1, z1,  x0, y1, z1,   # Back edge
            x0, y1, z1,  x0, y1, z0,   # Left edge
            
            # Vertical edges
            x0, y0, z0,  x0, y1, z0,   # Front-left
            x1, y0, z0,  x1, y1, z0,   # Front-right
            x1, y0, z1,  x1, y1, z1,   # Back-right
            x0, y0, z1,  x0, y1, z1,   # Back-left
        ], dtype=np.float32)
        
        # Compute MVP matrix
        mvp = proj_matrix * view_matrix
        
        # Update buffer
        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_DYNAMIC_DRAW)
        
        # Set uniforms and draw
        glUseProgram(self._program)
        glUniformMatrix4fv(self._u_mvp, 1, GL_TRUE, mvp.to_column_major())
        glUniform4f(self._u_color, *color)
        
        # Set line width
        glLineWidth(line_width)
        
        # Draw lines
        glDrawArrays(GL_LINES, 0, 24)
        
        # Cleanup
        glBindVertexArray(0)
        glUseProgram(0)
    
    def render_with_transform(self, min_pt: Vec3, max_pt: Vec3,
                               model_matrix: Mat4,
                               view_matrix: Mat4, proj_matrix: Mat4,
                               color: Tuple[float, float, float, float] = None,
                               line_width: float = 1.5) -> None:
        """
        Render a transformed bounding box.
        
        Args:
            min_pt: Minimum corner in local space
            max_pt: Maximum corner in local space
            model_matrix: Model transformation matrix
            view_matrix: Camera view matrix
            proj_matrix: Camera projection matrix
            color: RGBA color tuple
            line_width: Line thickness in pixels
        """
        if not self._initialized:
            return
        
        # Transform corners to world space
        corners_local = [
            Vec3(min_pt.x, min_pt.y, min_pt.z),
            Vec3(max_pt.x, min_pt.y, min_pt.z),
            Vec3(max_pt.x, max_pt.y, min_pt.z),
            Vec3(min_pt.x, max_pt.y, min_pt.z),
            Vec3(min_pt.x, min_pt.y, max_pt.z),
            Vec3(max_pt.x, min_pt.y, max_pt.z),
            Vec3(max_pt.x, max_pt.y, max_pt.z),
            Vec3(min_pt.x, max_pt.y, max_pt.z),
        ]
        
        corners_world = [model_matrix.transform_point(c) for c in corners_local]
        
        # Build line vertices from transformed corners
        # Indices for 12 edges
        edge_indices = [
            (0, 1), (1, 2), (2, 3), (3, 0),  # Bottom face
            (4, 5), (5, 6), (6, 7), (7, 4),  # Top face
            (0, 4), (1, 5), (2, 6), (3, 7),  # Vertical edges
        ]
        
        vertices = []
        for i0, i1 in edge_indices:
            v0, v1 = corners_world[i0], corners_world[i1]
            vertices.extend([v0.x, v0.y, v0.z, v1.x, v1.y, v1.z])
        
        vertices = np.array(vertices, dtype=np.float32)
        
        # Compute MVP (no model matrix since corners are already in world space)
        mvp = proj_matrix * view_matrix
        
        # Update buffer and draw
        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_DYNAMIC_DRAW)
        
        glUseProgram(self._program)
        glUniformMatrix4fv(self._u_mvp, 1, GL_TRUE, mvp.to_column_major())
        glUniform4f(self._u_color, *(color or self.COLOR_SELECTED))
        
        glLineWidth(line_width)
        glDrawArrays(GL_LINES, 0, 24)
        
        glBindVertexArray(0)
        glUseProgram(0)
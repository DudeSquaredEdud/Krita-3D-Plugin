

import math
from typing import Tuple

from ..vec3 import Vec3
from ..mat4 import Mat4


class Camera:


    FOV_TRANSITION_SPEED = 60.0
    FOV_MIN = 30.0
    FOV_MAX = 120.0

    def __init__(self):
        
        self.target = Vec3(0, 1, 0) # Look at center
        self.distance = 3.0
        self.yaw = 0.0
        self.pitch = 0.0

        self._head_look_mode = False
        self._head_position = Vec3(0, 1.5, 3)
        self._head_yaw = 0.0
        self._head_pitch = 0.0

        self.near = 0.1
        self.far = 100.0

        self._fov_target: float = 45.0 # Target FOV (what user set)
        self._fov_current: float = 45.0 # Current animated FOV

    @property
    def fov(self) -> float:
        
        return self._fov_target

    @fov.setter
    def fov(self, value: float):
        
        self._fov_target = max(self.FOV_MIN, min(self.FOV_MAX, value))

    @property
    def head_look_mode(self) -> bool:
        
        return self._head_look_mode

    @head_look_mode.setter
    def head_look_mode(self, enabled: bool):

        if enabled == self._head_look_mode:
            return

        if enabled:
            pos = self.get_position()
            self._head_position = pos
            direction = (self.target - pos).normalized()
            self._head_yaw = math.atan2(direction.x, direction.z)
            self._head_pitch = math.asin(max(-1, min(1, direction.y)))
        else:
            forward = self._get_head_forward()
            to_target = self.target - self._head_position
            target_in_front = to_target.dot(forward)

            if target_in_front > 0.01:
                self.distance = max(0.5, min(50.0, to_target.length()))
            else:
                fallback_dist = max(self.distance, 1.0)
                self.target = self._head_position + forward * fallback_dist
                self.distance = fallback_dist

            offset = (self._head_position - self.target) / self.distance
            self.yaw = math.atan2(offset.x, offset.z)
            self.pitch = math.asin(max(-1, min(1, offset.y)))

        self._head_look_mode = enabled

    def _get_head_forward(self) -> Vec3:
        
        x = math.sin(self._head_yaw) * math.cos(self._head_pitch)
        y = math.sin(self._head_pitch)
        z = math.cos(self._head_yaw) * math.cos(self._head_pitch)
        return Vec3(x, y, z)

    def _get_head_right(self) -> Vec3:
        
        forward = self._get_head_forward()
        return Vec3(0, 1, 0).cross(forward).normalized()

    def _get_head_up(self) -> Vec3:
        
        forward = self._get_head_forward()
        right = self._get_head_right()
        return forward.cross(right).normalized()

    def update(self, delta_time: float) -> bool:

        animating = False

        if abs(self._fov_current - self._fov_target) > 0.1:
            animating = True
            direction = 1 if self._fov_target > self._fov_current else -1
            self._fov_current += direction * self.FOV_TRANSITION_SPEED * delta_time
            if direction > 0:
                self._fov_current = min(self._fov_current, self._fov_target)
            else:
                self._fov_current = max(self._fov_current, self._fov_target)
        else:
            self._fov_current = self._fov_target

        return animating

    def get_position(self) -> Vec3:
        
        if self._head_look_mode:
            return self._head_position
        else:
            x = self.distance * math.sin(self.yaw) * math.cos(self.pitch)
            y = self.distance * math.sin(self.pitch)
            z = self.distance * math.cos(self.yaw) * math.cos(self.pitch)
            return self.target + Vec3(x, y, z)

    def get_view_matrix(self) -> Mat4:
        
        if self._head_look_mode:
            pos = self._head_position
            forward = self._get_head_forward()
            right = self._get_head_right()
            up = self._get_head_up()

            return Mat4([
                right.x, up.x, -forward.x, 0,
                right.y, up.y, -forward.y, 0,
                right.z, up.z, -forward.z, 0,
                -right.dot(pos), -up.dot(pos), forward.dot(pos), 1
            ])
        else:
            pos = self.get_position()

            forward = (self.target - pos).normalized()
            right = Vec3(0, 1, 0).cross(forward).normalized()
            up = forward.cross(right).normalized()

            return Mat4([
                right.x, up.x, -forward.x, 0,
                right.y, up.y, -forward.y, 0,
                right.z, up.z, -forward.z, 0,
                -right.dot(pos), -up.dot(pos), forward.dot(pos), 1
            ])

    def get_projection_matrix(self, aspect: float) -> Mat4:
        
        fov_rad = math.radians(self._fov_current)
        f = 1.0 / math.tan(fov_rad * 0.5)

        return Mat4([
            f / aspect, 0, 0, 0,
            0, f, 0, 0,
            0, 0, (self.far + self.near) / (self.near - self.far), -1,
            0, 0, (2 * self.far * self.near) / (self.near - self.far), 0
        ])

    def rotate(self, delta_yaw: float, delta_pitch: float) -> None:
        
        if self._head_look_mode:
            self._head_yaw += delta_yaw
            # Pitch is inverted because positive pitch should look down in first-person
            self._head_pitch = max(-math.pi * 0.49, min(math.pi * 0.49, self._head_pitch - delta_pitch))
        else:
            self.yaw += delta_yaw
            self.pitch = max(-math.pi * 0.49, min(math.pi * 0.49, self.pitch + delta_pitch))

    def zoom(self, delta: float) -> None:

        if self._head_look_mode:
            # Dolly the camera position in head-look mode
            self.move_forward(delta * 3.0)
        else:
            # Dolly the camera distance in orbit mode
            self.distance = max(0.5, min(50.0, self.distance * (1.0 - delta)))

    def move_forward(self, delta: float) -> None:
        
        if self._head_look_mode:
            forward = self._get_head_forward()
            self._head_position = self._head_position + forward * delta
        else:
            self.distance = max(0.5, min(50.0, self.distance - delta))

    def move_target(self, delta: Vec3) -> None:
        
        if self._head_look_mode:
            self._head_position = self._head_position + delta
        else:
            self.target = self.target + delta

    def pan(self, delta_x: float, delta_y: float) -> None:
        
        if self._head_look_mode:
            right = self._get_head_right()
            up = self._get_head_up()
            scale = 0.01
            self._head_position = self._head_position + right * (-delta_x * scale) + up * (delta_y * scale)
        else:
            forward = (self.target - self.get_position()).normalized()
            right = Vec3(0, 1, 0).cross(forward).normalized()
            up = forward.cross(right).normalized()

            scale = self.distance * 0.002
            self.target = self.target + right * (-delta_x * scale) + up * (delta_y * scale)

    def frame_points(self, min_pt: Vec3, max_pt: Vec3) -> None:
        
        center = Vec3(
            (min_pt.x + max_pt.x) / 2,
            (min_pt.y + max_pt.y) / 2,
            (min_pt.z + max_pt.z) / 2
        )

        size = Vec3(
            max_pt.x - min_pt.x,
            max_pt.y - min_pt.y,
            max_pt.z - min_pt.z
        )
        max_dim = max(size.x, size.y, size.z)

        if self._head_look_mode:
            self._head_position = center + Vec3(0, 0, max_dim * 2.0)
            self._head_yaw = math.pi  # Look back at center
            self._head_pitch = 0.0
        else:
            self.target = center
            self.distance = max_dim * 2.0

    def get_forward(self) -> Vec3:
        
        if self._head_look_mode:
            return self._get_head_forward()
        else:
            return (self.target - self.get_position()).normalized()

    def get_right(self) -> Vec3:
        
        if self._head_look_mode:
            return self._get_head_right()
        else:
            forward = self.get_forward()
            return Vec3(0, 1, 0).cross(forward).normalized()

    def get_up(self) -> Vec3:
        
        if self._head_look_mode:
            return self._get_head_up()
        else:
            forward = self.get_forward()
            right = self.get_right()
            return forward.cross(right).normalized()

    def get_effective_view_distance(self) -> float:

        if self._head_look_mode:
            return (self._head_position - self.target).length()
        return self.distance

    def save_state(self) -> dict:

        return {
            'mode': 'head_look' if self._head_look_mode else 'orbit',
            'target': self.target.to_tuple(),
            'distance': self.distance,
            'yaw': self.yaw,
            'pitch': self.pitch,
            'head_position': self._head_position.to_tuple(),
            'head_yaw': self._head_yaw,
            'head_pitch': self._head_pitch,
            'fov': self._fov_target,
            'near': self.near,
            'far': self.far,
        }

    def load_state(self, state: dict) -> None:

        self.target = Vec3.from_tuple(state.get('target', (0, 1, 0)))
        self.distance = state.get('distance', 3.0)
        self.yaw = state.get('yaw', 0.0)
        self.pitch = state.get('pitch', 0.0)
        self._head_position = Vec3.from_tuple(state.get('head_position', (0, 1.5, 3)))
        self._head_yaw = state.get('head_yaw', 0.0)
        self._head_pitch = state.get('head_pitch', 0.0)
        self._fov_target = state.get('fov', 45.0)
        self._fov_current = self._fov_target
        self.near = state.get('near', 0.1)
        self.far = state.get('far', 100.0)
        self._head_look_mode = state.get('mode', 'orbit') == 'head_look'

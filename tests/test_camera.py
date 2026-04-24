#!/usr/bin/env python3


import pytest
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pose_engine.camera import Camera
from pose_engine.vec3 import Vec3
from pose_engine.mat4 import Mat4


class TestCameraCreation:
    

    def test_camera_creation_default_values(self):
        
        camera = Camera()

        assert camera.target.x == 0
        assert camera.target.y == 1
        assert camera.target.z == 0
        assert camera.distance == 3.0
        assert camera.yaw == 0.0
        assert camera.pitch == 0.0

        assert camera.head_look_mode == False

        assert camera.near == 0.1
        assert camera.far == 100.0

        assert camera.fov == 45.0

    def test_camera_default_mode_is_orbit(self):
        
        camera = Camera()
        assert camera.head_look_mode == False

    def test_camera_fov_bounds(self):
        
        camera = Camera()

        camera.fov = 10.0
        assert camera.fov == Camera.FOV_MIN

        camera.fov = 150.0
        assert camera.fov == Camera.FOV_MAX

        camera.fov = 60.0
        assert camera.fov == 60.0


class TestOrbitModePosition:
    

    def test_orbit_mode_position_default(self):
        
        camera = Camera()
        pos = camera.get_position()

        assert abs(pos.x - 0) < 0.001
        assert abs(pos.y - 1) < 0.001
        assert abs(pos.z - 3) < 0.001

    def test_orbit_mode_position_yaw_rotation(self):
        
        camera = Camera()
        camera.yaw = math.pi / 2  

        pos = camera.get_position()

        
        
        assert abs(pos.x - 3) < 0.001
        assert abs(pos.y - 1) < 0.001
        assert abs(pos.z - 0) < 0.001

    def test_orbit_mode_position_pitch_rotation(self):
        
        camera = Camera()
        camera.pitch = math.pi / 4  

        pos = camera.get_position()

        
        
        
        expected_y = 1 + 3 * math.sin(math.pi / 4)
        expected_z = 3 * math.cos(math.pi / 4)

        assert abs(pos.x - 0) < 0.001
        assert abs(pos.y - expected_y) < 0.01
        assert abs(pos.z - expected_z) < 0.01

    def test_orbit_mode_position_combined_rotation(self):
        
        camera = Camera()
        camera.yaw = math.pi / 4  
        camera.pitch = math.pi / 6  

        pos = camera.get_position()

        expected_x = 3 * math.sin(math.pi / 4) * math.cos(math.pi / 6)
        expected_y = 1 + 3 * math.sin(math.pi / 6)
        expected_z = 3 * math.cos(math.pi / 4) * math.cos(math.pi / 6)

        assert abs(pos.x - expected_x) < 0.01
        assert abs(pos.y - expected_y) < 0.01
        assert abs(pos.z - expected_z) < 0.01


class TestOrbitModeRotation:
    

    def test_orbit_rotate_yaw(self):
        
        camera = Camera()
        initial_yaw = camera.yaw

        camera.rotate(0.5, 0)  

        assert abs(camera.yaw - (initial_yaw + 0.5)) < 0.001

    def test_orbit_rotate_pitch(self):
        
        camera = Camera()
        initial_pitch = camera.pitch

        camera.rotate(0, 0.3) 

        assert abs(camera.pitch - (initial_pitch + 0.3)) < 0.001

    def test_orbit_pitch_clamping(self):
        
        camera = Camera()

        camera.rotate(0, math.pi)  

        assert camera.pitch <= math.pi * 0.49
        assert camera.pitch >= -math.pi * 0.49


class TestOrbitModeZoom:
    

    def test_orbit_zoom_in(self):
        
        camera = Camera()
        initial_distance = camera.distance

        camera.zoom(0.5)  

        assert camera.distance < initial_distance

    def test_orbit_zoom_out(self):
        
        camera = Camera()
        initial_distance = camera.distance

        camera.zoom(-0.5)  

        assert camera.distance > initial_distance

    def test_orbit_zoom_distance_clamping(self):
        
        camera = Camera()

        camera.distance = 0.1
        camera.zoom(0.9)
        assert camera.distance >= 0.5

        camera.distance = 100.0
        camera.zoom(-0.9)
        assert camera.distance <= 50.0


class TestHeadLookModeSwitch:
    

    def test_switch_to_head_look_mode(self):
        
        camera = Camera()
        assert camera.head_look_mode == False

        camera.head_look_mode = True

        assert camera.head_look_mode == True

    def test_switch_from_head_look_to_orbit(self):
        
        camera = Camera()
        camera.head_look_mode = True

        camera.head_look_mode = False

        assert camera.head_look_mode == False

    def test_head_look_mode_no_change_when_same(self):
        
        camera = Camera()
        initial_target = Vec3(camera.target.x, camera.target.y, camera.target.z)

        camera.head_look_mode = False  

        assert camera.target.x == initial_target.x
        assert camera.target.y == initial_target.y
        assert camera.target.z == initial_target.z


class TestHeadLookPositionPreserved:
    

    def test_position_preserved_switch_to_head_look(self):
        
        camera = Camera()
        camera.yaw = math.pi / 4
        camera.pitch = math.pi / 6

        orbit_position = camera.get_position()

        camera.head_look_mode = True

        head_position = camera.get_position()
        assert abs(head_position.x - orbit_position.x) < 0.001
        assert abs(head_position.y - orbit_position.y) < 0.001
        assert abs(head_position.z - orbit_position.z) < 0.001


class TestHeadLookForwardDirection:
    

    def test_head_forward_default(self):
        
        camera = Camera()
        
        
        camera.head_look_mode = True

        forward = camera._get_head_forward()

        
        
        
        
        assert abs(forward.x - 0) < 0.001
        assert abs(forward.y - 0) < 0.001
        assert abs(forward.z - (-1)) < 0.001

    def test_head_forward_yaw_rotation(self):
        
        camera = Camera()
        camera.head_look_mode = True
        camera._head_yaw = math.pi / 2  

        forward = camera._get_head_forward()

        assert abs(forward.x - 1) < 0.001
        assert abs(forward.y - 0) < 0.001
        assert abs(forward.z - 0) < 0.001

    def test_head_forward_pitch_rotation(self):
        
        camera = Camera()
        camera.head_look_mode = True
        camera._head_yaw = 0
        camera._head_pitch = math.pi / 4  

        forward = camera._get_head_forward()

        
        assert abs(forward.x - 0) < 0.001
        assert abs(forward.y - math.sin(math.pi / 4)) < 0.001
        assert abs(forward.z - math.cos(math.pi / 4)) < 0.001


class TestHeadLookRotation:
    

    def test_head_look_rotate_yaw(self):
        
        camera = Camera()
        camera.head_look_mode = True
        initial_yaw = camera._head_yaw

        camera.rotate(0.5, 0)

        assert abs(camera._head_yaw - (initial_yaw + 0.5)) < 0.001

    def test_head_look_rotate_pitch(self):
        
        camera = Camera()
        camera.head_look_mode = True
        initial_pitch = camera._head_pitch

        camera.rotate(0, 0.3)

        
        assert abs(camera._head_pitch - (initial_pitch - 0.3)) < 0.001

    def test_head_look_pitch_clamping(self):
        
        camera = Camera()
        camera.head_look_mode = True

        camera.rotate(0, math.pi)

        assert camera._head_pitch <= math.pi * 0.49
        assert camera._head_pitch >= -math.pi * 0.49


class TestHeadLookMovement:
    

    def test_move_forward(self):
        
        camera = Camera()
        camera.head_look_mode = True
        camera._head_yaw = 0
        camera._head_pitch = 0
        initial_pos = Vec3(camera._head_position.x, camera._head_position.y, camera._head_position.z)

        camera.move_forward(1.0)

        assert camera._head_position.z > initial_pos.z

    def test_move_right(self):
        
        camera = Camera()
        camera.head_look_mode = True
        initial_pos = Vec3(camera._head_position.x, camera._head_position.y, camera._head_position.z)

        camera.pan(-100, 0)

        assert camera._head_position.x != initial_pos.x

    def test_move_up(self):
        
        camera = Camera()
        camera.head_look_mode = True
        initial_pos = Vec3(camera._head_position.x, camera._head_position.y, camera._head_position.z)

        camera.pan(0, 100)

        assert camera._head_position.y > initial_pos.y


class TestModeTransition:
    

    def test_transition_orbit_to_head_look(self):
        
        camera = Camera()
        camera.yaw = math.pi / 4
        camera.pitch = math.pi / 6

        orbit_pos = camera.get_position()

        camera.head_look_mode = True

        head_pos = camera.get_position()
        assert abs(head_pos.x - orbit_pos.x) < 0.01
        assert abs(head_pos.y - orbit_pos.y) < 0.01
        assert abs(head_pos.z - orbit_pos.z) < 0.01

    def test_transition_head_look_to_orbit(self):
        
        camera = Camera()
        camera.head_look_mode = True
        camera._head_position = Vec3(0, 2, 5)
        camera._head_yaw = 0
        camera._head_pitch = 0

        camera.head_look_mode = False

        assert camera.distance > 0
        assert camera.target is not None

    def test_round_trip_position_preserved(self):
        
        camera = Camera()
        camera.yaw = math.pi / 4
        camera.pitch = math.pi / 6
        camera.distance = 5.0

        original_pos = camera.get_position()

        camera.head_look_mode = True
        head_pos = camera.get_position()

        assert abs(head_pos.x - original_pos.x) < 0.01
        assert abs(head_pos.y - original_pos.y) < 0.01
        assert abs(head_pos.z - original_pos.z) < 0.01

        camera.head_look_mode = False
        restored_pos = camera.get_position()

        assert abs(restored_pos.x - original_pos.x) < 0.01
        assert abs(restored_pos.y - original_pos.y) < 0.01
        assert abs(restored_pos.z - original_pos.z) < 0.01

    def test_round_trip_target_preserved(self):
        
        camera = Camera()
        camera.target = Vec3(1, 2, 3)
        camera.yaw = 0.5
        camera.pitch = 0.2
        camera.distance = 4.0

        original_target = Vec3(camera.target.x, camera.target.y, camera.target.z)

        camera.head_look_mode = True
        camera.head_look_mode = False

        assert abs(camera.target.x - original_target.x) < 0.01
        assert abs(camera.target.y - original_target.y) < 0.01
        assert abs(camera.target.z - original_target.z) < 0.01

    def test_round_trip_with_non_default_fov(self):
        
        camera = Camera()
        camera.fov = 90.0
        camera._fov_current = 90.0  
        camera.yaw = 0.3
        camera.pitch = 0.1
        camera.distance = 4.0

        original_pos = camera.get_position()

        camera.head_look_mode = True
        camera.head_look_mode = False

        restored_pos = camera.get_position()

        
        
        assert abs(restored_pos.x - original_pos.x) < 0.01
        assert abs(restored_pos.y - original_pos.y) < 0.01
        assert abs(restored_pos.z - original_pos.z) < 0.01

    def test_head_look_to_orbit_target_in_front_preserved(self):
        
        camera = Camera()
        camera.target = Vec3(0, 1, 0)
        camera.distance = 3.0
        camera.yaw = 0.0
        camera.pitch = 0.0

        original_target = Vec3(camera.target.x, camera.target.y, camera.target.z)

        camera.head_look_mode = True
        camera.head_look_mode = False

        assert abs(camera.target.x - original_target.x) < 0.01
        assert abs(camera.target.y - original_target.y) < 0.01
        assert abs(camera.target.z - original_target.z) < 0.01

    def test_head_look_to_orbit_target_behind_repositions(self):
        
        camera = Camera()
        camera.head_look_mode = True
        camera._head_position = Vec3(0, 1, 0)
        camera._head_yaw = 0.0  
        camera._head_pitch = 0.0

        camera.head_look_mode = False

        assert camera.distance > 0
        assert camera.target.z > 0

    def test_look_direction_preserved_orbit_to_head_look(self):
        
        camera = Camera()
        camera.target = Vec3(0, 0, 0)
        camera.yaw = 0.0
        camera.pitch = 0.0
        camera.distance = 5.0

        orbit_forward = camera.get_forward()

        camera.head_look_mode = True
        head_forward = camera.get_forward()

        assert abs(head_forward.x - orbit_forward.x) < 0.01
        assert abs(head_forward.y - orbit_forward.y) < 0.01
        assert abs(head_forward.z - orbit_forward.z) < 0.01


class TestEffectiveViewDistance:
    

    def test_effective_distance_orbit_returns_distance(self):
        
        camera = Camera()
        camera.distance = 5.0

        eff = camera.get_effective_view_distance()
        assert abs(eff - 5.0) < 0.01

    def test_effective_distance_head_look_returns_target_distance(self):
        
        camera = Camera()
        camera.head_look_mode = True
        camera._head_position = Vec3(0, 0, 5)
        camera.target = Vec3(0, 0, 0)

        eff = camera.get_effective_view_distance()
        assert abs(eff - 5.0) < 0.01

    def test_effective_distance_consistent_across_modes(self):
        
        camera = Camera()
        camera.target = Vec3(0, 0, 0)
        camera.distance = 5.0
        camera.yaw = 0.0
        camera.pitch = 0.0

        orbit_eff = camera.get_effective_view_distance()

        camera.head_look_mode = True
        head_eff = camera.get_effective_view_distance()

        assert abs(orbit_eff - head_eff) < 0.01

    def test_effective_distance_independent_of_fov(self):

        camera = Camera()
        camera.distance = 5.0

        camera._fov_current = 45.0
        eff_45 = camera.get_effective_view_distance()

        camera._fov_current = 90.0
        eff_90 = camera.get_effective_view_distance()

        camera._fov_current = 30.0
        eff_30 = camera.get_effective_view_distance()

        
        assert abs(eff_45 - 5.0) < 0.01
        assert abs(eff_90 - 5.0) < 0.01
        assert abs(eff_30 - 5.0) < 0.01

    def test_gizmo_scale_no_jump_on_mode_switch(self):
        
        camera = Camera()
        camera.target = Vec3(0, 0, 0)
        camera.distance = 5.0
        camera.yaw = 0.0
        camera.pitch = 0.0
        camera.fov = 70.0
        camera._fov_current = 70.0  

        orbit_scale = camera.get_effective_view_distance() * 0.15

        camera.head_look_mode = True
        head_scale = camera.get_effective_view_distance() * 0.15

        
        assert abs(head_scale - orbit_scale) / orbit_scale < 0.01


class TestFOVClamping:
    

    def test_fov_min_clamp(self):
        
        camera = Camera()
        camera.fov = 0
        assert camera.fov == Camera.FOV_MIN

    def test_fov_max_clamp(self):
        
        camera = Camera()
        camera.fov = 200
        assert camera.fov == Camera.FOV_MAX

    def test_fov_valid_value(self):
        
        camera = Camera()
        camera.fov = 75
        assert camera.fov == 75


class TestViewMatrixGeneration:
    

    def test_view_matrix_orbit_mode(self):
        
        camera = Camera()

        view_matrix = camera.get_view_matrix()

        assert isinstance(view_matrix, Mat4)

    def test_view_matrix_head_look_mode(self):
        
        camera = Camera()
        camera.head_look_mode = True

        view_matrix = camera.get_view_matrix()

        assert isinstance(view_matrix, Mat4)

    def test_view_matrix_looks_at_target(self):
        
        camera = Camera()
        camera.target = Vec3(0, 0, 0)
        camera.distance = 5.0
        camera.yaw = 0
        camera.pitch = 0

        view_matrix = camera.get_view_matrix()

        assert isinstance(view_matrix, Mat4)


class TestProjectionMatrix:
    

    def test_projection_matrix_creation(self):
        
        camera = Camera()
        aspect = 16.0 / 9.0

        proj_matrix = camera.get_projection_matrix(aspect)

        assert isinstance(proj_matrix, Mat4)

    def test_projection_matrix_aspect_ratio(self):
        
        camera = Camera()
        camera.fov = 60

        proj_16_9 = camera.get_projection_matrix(16.0 / 9.0)
        proj_4_3 = camera.get_projection_matrix(4.0 / 3.0)

        assert isinstance(proj_16_9, Mat4)
        assert isinstance(proj_4_3, Mat4)

    def test_projection_matrix_fov_effect(self):
        
        camera = Camera()

        camera.fov = 45
        proj_45 = camera.get_projection_matrix(1.0)

        camera.fov = 90
        camera._fov_current = 90  
        proj_90 = camera.get_projection_matrix(1.0)

        assert isinstance(proj_45, Mat4)
        assert isinstance(proj_90, Mat4)


class TestCameraStateSaveLoad:
    

    def test_save_state_orbit_mode(self):
        
        camera = Camera()
        camera.yaw = 1.0
        camera.pitch = 0.5
        camera.distance = 10.0

        state = camera.save_state()

        assert state['mode'] == 'orbit'
        assert state['yaw'] == 1.0
        assert state['pitch'] == 0.5
        assert state['distance'] == 10.0

    def test_save_state_head_look_mode(self):
        
        camera = Camera()
        camera.head_look_mode = True
        camera._head_yaw = 1.5
        camera._head_pitch = 0.3

        state = camera.save_state()

        assert state['mode'] == 'head_look'
        assert state['head_yaw'] == 1.5
        assert state['head_pitch'] == 0.3

    def test_load_state_orbit_mode(self):
        
        camera = Camera()

        state = {
            'mode': 'orbit',
            'target': (0, 2, 0),
            'distance': 8.0,
            'yaw': 0.5,
            'pitch': 0.25,
            'fov': 60.0
        }

        camera.load_state(state)

        assert camera.head_look_mode == False
        assert camera.distance == 8.0
        assert camera.yaw == 0.5
        assert camera.pitch == 0.25
        assert camera.fov == 60.0

    def test_load_state_head_look_mode(self):
        
        camera = Camera()

        state = {
            'mode': 'head_look',
            'head_position': (1, 2, 3),
            'head_yaw': 1.0,
            'head_pitch': 0.5,
            'fov': 75.0
        }

        camera.load_state(state)

        assert camera.head_look_mode == True
        assert camera._head_yaw == 1.0
        assert camera._head_pitch == 0.5

    def test_save_load_roundtrip(self):
        
        camera = Camera()
        camera.yaw = 1.2
        camera.pitch = 0.4
        camera.distance = 7.5
        camera.fov = 55

        state = camera.save_state()

        new_camera = Camera()
        new_camera.load_state(state)

        assert new_camera.yaw == camera.yaw
        assert new_camera.pitch == camera.pitch
        assert new_camera.distance == camera.distance
        assert new_camera.fov == camera.fov


class TestFramePoints:
    

    def test_frame_points_orbit_mode(self):
        
        camera = Camera()

        min_pt = Vec3(-1, 0, -1)
        max_pt = Vec3(1, 2, 1)

        camera.frame_points(min_pt, max_pt)

        assert abs(camera.target.x - 0) < 0.01
        assert abs(camera.target.y - 1) < 0.01
        assert abs(camera.target.z - 0) < 0.01

        assert camera.distance > 0

    def test_frame_points_head_look_mode(self):
        
        camera = Camera()
        camera.head_look_mode = True

        min_pt = Vec3(-1, 0, -1)
        max_pt = Vec3(1, 2, 1)

        camera.frame_points(min_pt, max_pt)

        assert camera._head_position is not None


class TestCameraUpdate:
    

    def test_update_animates_fov(self):
        
        camera = Camera()
        camera.fov = 90  

        animating = camera.update(0.1)

        assert animating == True or camera._fov_current == camera._fov_target

    def test_update_returns_false_when_complete(self):
        
        camera = Camera()
        camera.fov = 45
        camera._fov_current = 45
        camera._fov_target = 45

        animating = camera.update(0.1)

        assert animating == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

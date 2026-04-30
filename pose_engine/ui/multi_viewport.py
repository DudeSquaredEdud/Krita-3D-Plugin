import math
from typing import Callable, Optional, Tuple, Dict

from PyQt5.QtWidgets import QOpenGLWidget, QWidget
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QMouseEvent, QKeyEvent, QWheelEvent, QImage, QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat
from OpenGL.GL import (
    GL_LESS, glClearColor, glEnable, glDisable, glBlendFunc,
    GL_DEPTH_TEST, GL_BLEND, GL_SRC_ALPHA,
    GL_ONE_MINUS_SRC_ALPHA, glViewport, glClear,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    glGetIntegerv, GL_VIEWPORT,
    GL_CULL_FACE, glCullFace, GL_BACK, GL_LEQUAL, glDepthFunc
)

from ..vec3 import Vec3
from ..quat import Quat
from ..mat4 import Mat4
from ..bone import Bone
from ..scene import Scene
from ..model_instance import ModelInstance
from ..renderer.gl_renderer import GLRenderer
from ..renderer.skeleton_viz import SkeletonVisualizer
from ..renderer.rotation_gizmo import RotationGizmo
from ..renderer.movement_gizmo import MovementGizmo
from ..renderer.scale_gizmo import ScaleGizmo
from ..renderer.joint_renderer import JointRenderer
from ..settings.settings import PluginSettings
from ..camera import CameraBookmarkManager, Camera
from ..renderer.bounding_box_renderer import BoundingBoxRenderer
from ..renderer.grid_renderer import GridRenderer
from ..logger import get_logger

logger = get_logger(__name__)



class MultiViewport3D(QOpenGLWidget):
    model_selected = pyqtSignal(str) # model_id
    bone_selected = pyqtSignal(str, str) # model_id, bone_name
    pose_changed = pyqtSignal()
    model_selection_changed = pyqtSignal(str) # model_id - emitted when active model changes
    sync_to_layer_requested = pyqtSignal() # Emitted when sync to layer shortcut is pressed
    camera_mode_changed = pyqtSignal(str) # Emitted when camera mode changes (e.g., when loading a bookmark) - "orbit" or "head_look"

    _MOVEMENT_ACTION_MAP = {
        'camera_forward': 'forward',
        'camera_backward': 'backward',
        'camera_left': 'left',
        'camera_right': 'right',
        'camera_up': 'up',
        'camera_down': 'down',
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._scene = Scene()

        self._model_renderers: Dict[str, GLRenderer] = {}
        self._model_skeleton_viz: Dict[str, SkeletonVisualizer] = {}

        self._gizmo: Optional[RotationGizmo] = None
        self._movement_gizmo: Optional[MovementGizmo] = None
        self._scale_gizmo: Optional[ScaleGizmo] = None
        self._joint_renderer: Optional[JointRenderer] = None

        self._gizmo_mode: str = "rotation"
        self._gizmo_transform_space: str = "world"

        self._camera = Camera()

        self._camera_bookmarks: Dict[int, dict] = {}

        self._bookmark_manager: Optional[CameraBookmarkManager] = None

        self._head_look_mode: bool = False

        self._movement_keys_pressed: set = set()

        self._settings: Optional[PluginSettings] = None

        self._last_mouse_pos = None
        self._mouse_button = None

        self._show_mesh = True
        self._show_skeleton = True
        self._show_joints = True
        self._show_gizmo = True
        self._show_grid = True
        self._silhouette_mode = False

        self._hovered_model_id: Optional[str] = None
        self._hovered_bone_name: Optional[str] = None

        self._gizmo_state: str = "idle"
        self._gizmo_hover_axis: Optional[str] = None
        self._gizmo_drag_axis: Optional[str] = None
        self._gizmo_drag_start_point: Optional[Vec3] = None
        self._gizmo_drag_prev_point: Optional[Vec3] = None
        self._accumulated_rotation: Optional[Quat] = None
        self._initial_bone_rotation: Optional[Quat] = None
        self._initial_delta_rotation: Optional[Quat] = None
        self._rotation_slow_factor: float = 1.0
        self._drag_axis_rotation: Optional[Mat4] = None

        self._show_bounding_box: bool = False
        self._bounding_box_doc_size: Tuple[int, int] = (0, 0)
        self._bounding_box_renderer: Optional[BoundingBoxRenderer] = None
        self._grid_renderer: Optional[GridRenderer] = None

        self._key_handlers: Dict[str, Callable] = {
            'frame_model': self.frame_all,
            'toggle_mesh': lambda: self.set_show_mesh(not self._show_mesh),
            'toggle_skeleton': lambda: self.set_show_skeleton(not self._show_skeleton),
            'toggle_gizmo_mode': self.toggle_gizmo_mode,
            'gizmo_rotate': lambda: self.set_gizmo_mode("rotation"),
            'gizmo_move': lambda: self.set_gizmo_mode("movement"),
            'gizmo_scale': lambda: self.set_gizmo_mode("scale"),
            'reset_camera': self._reset_camera,
            'sync_to_layer': self.sync_to_layer_requested.emit,
            'reset_bone': self.reset_bone,
            'toggle_head_look': lambda: self.set_head_look_mode(not self._head_look_mode),
            'deselect': lambda: self.select_bone(self._scene._selected_model_id or '', ''),
            'toggle_transform_space': self.toggle_gizmo_transform_space,
            'toggle_joints': lambda: self.set_show_joints(not self._show_joints),
            'toggle_gizmo': lambda: self.set_show_gizmo(not self._show_gizmo),
            'toggle_grid': lambda: self.set_show_grid(not self._show_grid),

        }
        # Bookmark handlers (1–9)
        for _i in range(1, 10):
            self._key_handlers[f'bookmark_save_{_i}'] = lambda i=_i: self._save_bookmark(i)
            self._key_handlers[f'bookmark_recall_{_i}'] = lambda i=_i: self._recall_bookmark(i)


        self._gl_initialized = False

        self.setFocusPolicy(Qt.StrongFocus)

        self.setMouseTracking(True)

        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._on_update)
        self._update_timer.start(16)  # ~60 FPS

    def get_scene(self) -> Scene:
        
        return self._scene

    def set_settings(self, settings: PluginSettings) -> None:

        self._settings = settings
        self._apply_camera_settings()

        settings.notifier.setting_changed.connect(self._on_setting_changed)

        from pathlib import Path
        settings_path = settings.get_settings_path()
        if settings_path:
            settings_dir = Path(settings_path).parent
            self._bookmark_manager = CameraBookmarkManager(settings_dir)

        self.update()

    def get_settings(self) -> Optional[PluginSettings]:
        
        return self._settings

    def _apply_camera_settings(self) -> None:
        
        if not self._settings:
            return

        cam_settings = self._settings.camera
        self._camera.fov = cam_settings.get('default_fov', 45.0)
        self._camera.distance = cam_settings.get('default_distance', 3.0)

    def _reset_camera(self) -> None:
        self._camera = Camera()
        self._frame_scene()


    def _on_setting_changed(self, category: str, key: str, value) -> None:

        if category == 'camera' and key == 'default_fov':
            self._camera.fov = value
        # Display scale changes just need a repaint - no camera update needed
        if category == 'gizmo' and key in ('display_scale', 'joint_display_scale'):
            pass # type: ignore
        if category == 'ui' and key in ('silhouette_mode', 'silhouette_color', 'silhouette_outline_color', 'rim_intensity', 'outline_width'):
            self._apply_silhouette_settings()
        self.update()

    def _get_gizmo_scale(self) -> float:

        display_scale = 0.15  # Fallback default
        if self._settings:
            display_scale = self._settings.gizmo.get_display_scale()
        return max(0.01, display_scale)

    def _get_joint_scale(self) -> float:

        joint_display_scale = 0.15  # Fallback default
        if self._settings:
            joint_display_scale = self._settings.gizmo.get_joint_display_scale()
        return max(0.01, joint_display_scale)

    def add_model(self, file_path: str, name: Optional[str] = None) -> Optional[ModelInstance]:

        try:
            model = self._scene.add_model_from_file(file_path, name)
            logger.debug(f"[DEBUG_ADD] Loaded model: name={model.name} id={model.id} "
                  f"mesh_data={model.mesh_data is not None} skeleton={model.skeleton is not None} "
                  f"pos={model.transform.position} scale={model.transform.scale}")

            # Must make context current before OpenGL operations
            if self._gl_initialized:
                self.makeCurrent()
                self._init_model_gl_resources(model)
                self.doneCurrent()
            else:
                logger.debug("[DEBUG_ADD] GL not initialized yet, will init later")

            self._frame_scene()

            self.update()
            return model

        except Exception as e:
            logger.debug(f"Error loading model: {e}")
            import traceback
            traceback.logger.debug_exc()
            return None
        
    def _cleanup_all_gl_resources(self) -> None:
        for model_id in self._model_renderers.keys():
            self._model_renderers[model_id].cleanup()
        self._model_renderers.clear()
        for model_id in self._model_skeleton_viz.keys():
            self._model_skeleton_viz[model_id].cleanup()
        self._model_skeleton_viz.clear()
        if self._joint_renderer:
            self._joint_renderer.cleanup()
            self._joint_renderer = None
        if self._gizmo:
            self._gizmo.cleanup()
            self._gizmo = None
        if self._movement_gizmo:
            self._movement_gizmo.cleanup()
            self._movement_gizmo = None
        if self._scale_gizmo:
            self._scale_gizmo.cleanup()
            self._scale_gizmo = None
        if self._bounding_box_renderer:
            self._bounding_box_renderer.cleanup()
            self._bounding_box_renderer = None


    def _cleanup_model_gl_resources(self, model_id: str) -> None:
        if model_id in self._model_renderers:
            self._model_renderers[model_id].cleanup()
            del self._model_renderers[model_id]
        if model_id in self._model_skeleton_viz:
            self._model_skeleton_viz[model_id].cleanup()
            del self._model_skeleton_viz[model_id]

    def remove_model(self, model_id: str) -> None:
        
        if model_id in self._model_renderers:
            self._cleanup_model_gl_resources(model_id)
            del self._model_renderers[model_id]
        if model_id in self._model_skeleton_viz:
            del self._model_skeleton_viz[model_id]

        self._scene.remove_model(model_id)
        self.update()


    def reload_scene(self) -> None:

        logger.debug(f"[Viewport] Reloading scene with {len(list(self._scene.get_all_models()))} models")
        
        self._model_renderers.clear()
        self._model_skeleton_viz.clear()

        if self._gl_initialized:
            self.makeCurrent()
            for model in self._scene.get_all_models():
                logger.debug(f"[Viewport] Initializing GL resources for model: {model.name}")
                self._init_model_gl_resources(model)
            self.doneCurrent()
        
        self.update()

    def duplicate_model(self, model_id: str) -> Optional[ModelInstance]:
        
        copy = self._scene.duplicate_model(model_id)
        if copy and self._gl_initialized:
            self.makeCurrent()
            self._init_model_gl_resources(copy)
            self.doneCurrent()
            self.update()
        return copy

    def select_model(self, model_id: Optional[str]) -> None:
        
        self._scene.select_model(model_id)
        self.update()
        if model_id:
            self.model_selected.emit(model_id)

    def select_bone(self, model_id: str, bone_name: str) -> None:
        
        old_model_id = self._scene.get_selected_model_id()
        self._scene.select_bone(model_id, bone_name)
        self.update()
        self.bone_selected.emit(model_id, bone_name)
        
        if model_id != old_model_id:
            self.model_selection_changed.emit(model_id)

    def get_selected_model(self) -> Optional[ModelInstance]:
        
        return self._scene.get_selected_model()

    def get_selected_bone(self) -> Tuple[Optional[ModelInstance], Optional[Bone]]:
        
        return self._scene.get_selected_bone()

    def set_show_mesh(self, show: bool) -> None:

        self._show_mesh = show
        self.update()

    def set_show_skeleton(self, show: bool) -> None:

        self._show_skeleton = show
        self.update()

    def set_show_joints(self, show: bool) -> None:

        self._show_joints = show
        self.update()

    def set_show_gizmo(self, show: bool) -> None:

        self._show_gizmo = show
        self.update()

    def set_show_grid(self, show: bool) -> None:

        self._show_grid = show
        self.update()

    def set_silhouette_mode(self, enabled: bool) -> None:

        self._silhouette_mode = enabled
        for renderer in self._model_renderers.values():
            renderer.set_silhouette_mode(enabled)
        self.update()

    def is_silhouette_mode(self) -> bool:

        return self._silhouette_mode

    def set_silhouette_color(self, color: Tuple[float, float, float]) -> None:

        for renderer in self._model_renderers.values():
            renderer.set_silhouette_color(color)
        self.update()

    def set_silhouette_outline_color(self, color: Tuple[float, float, float]) -> None:

        for renderer in self._model_renderers.values():
            renderer.set_silhouette_outline_color(color)
        self.update()

    def set_rim_intensity(self, intensity: float) -> None:

        for renderer in self._model_renderers.values():
            renderer.set_rim_intensity(intensity)
        self.update()

    def set_outline_width(self, width: float) -> None:

        for renderer in self._model_renderers.values():
            renderer.set_outline_width(width)
        self.update()

    def set_model_visible(self, model_id: str, visible: bool) -> None:
        
        model = self._scene.get_model(model_id)
        if model:
            model.visible = visible
            self.update()

    def set_gizmo_mode(self, mode: str) -> None:
        
        if mode in ("rotation", "movement", "scale"):
            self._gizmo_mode = mode
            self.update()
    
    def get_gizmo_mode(self) -> str:
        
        return self._gizmo_mode
    
    def toggle_gizmo_mode(self) -> None:

        if self._gizmo_mode == "rotation":
            self._gizmo_mode = "movement"
        elif self._gizmo_mode == "movement":
            self._gizmo_mode = "scale"
        else:
            self._gizmo_mode = "rotation"
        self.update()

    def set_gizmo_transform_space(self, space: str) -> None:

        if space in ("world", "local"):
            self._gizmo_transform_space = space
            self.update()

    def get_gizmo_transform_space(self) -> str:

        return self._gizmo_transform_space

    def toggle_gizmo_transform_space(self) -> None:

        if self._gizmo_transform_space == "world":
            self._gizmo_transform_space = "local"
        else:
            self._gizmo_transform_space = "world"
        self.update()

    def frame_all(self) -> None:
        
        self._frame_scene()

    def frame_selected(self) -> None:
        
        model = self.get_selected_model()
        if model and model.skeleton:
            min_pt, max_pt = Vec3(float('inf'), float('inf'), float('inf')), \
                            Vec3(float('-inf'), float('-inf'), float('-inf'))
            for bone in model.skeleton:
                pos = bone.get_world_position()
                min_pt = Vec3(min(min_pt.x, pos.x), min(min_pt.y, pos.y), min(min_pt.z, pos.z))
                max_pt = Vec3(max(max_pt.x, pos.x), max(max_pt.y, pos.y), max(max_pt.z, pos.z))
            self._camera.frame_points(min_pt, max_pt)
            self.update()

    def _frame_scene(self) -> None:
        min_pt, max_pt = self._scene.get_bounding_box()
        self._camera.frame_points(min_pt, max_pt)
        self.update()

    def initializeGL(self) -> None:
        glClearColor(0.2, 0.2, 0.2, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        self._gizmo = RotationGizmo()
        if not self._gizmo.initialize():
            logger.debug("Failed to initialize RotationGizmo")

        self._movement_gizmo = MovementGizmo()
        if not self._movement_gizmo.initialize():
            logger.debug("Failed to initialize MovementGizmo")

        self._scale_gizmo = ScaleGizmo()
        if not self._scale_gizmo.initialize():
            logger.debug("Failed to initialize ScaleGizmo")

        self._joint_renderer = JointRenderer()
        if not self._joint_renderer.initialize():
            logger.debug("Failed to initialize JointRenderer")

        self._bounding_box_renderer = BoundingBoxRenderer()
        if not self._bounding_box_renderer.initialize():
            logger.debug("Failed to initialize BoundingBoxRenderer")

        self._grid_renderer = GridRenderer()
        if not self._grid_renderer.initialize():
            logger.debug("Failed to initialize GridRenderer")

        for model in self._scene.get_all_models():
            self._init_model_gl_resources(model)

        self._gl_initialized = True

    def _init_model_gl_resources(self, model: ModelInstance) -> None:

        if model.id in self._model_renderers:
            logger.debug(f"[DEBUG_INIT] SKIP _init_model_gl_resources for {model.name} - already in _model_renderers")
            return

        renderer = GLRenderer()
        logger.debug(f"[DEBUG_INIT] Created GLRenderer id={id(renderer)} for model {model.name} ({model.id})")
        if renderer.initialize():
            self._model_renderers[model.id] = renderer
            renderer.set_silhouette_mode(self._silhouette_mode)
            logger.debug(f"[DEBUG_INIT] Renderer initialized, stored in _model_renderers[{model.id}] id={id(renderer)}")
        else:
            logger.debug(f"[DEBUG_INIT] Failed to initialize renderer for model {model.name} ({model.id})")
            return

        stored_renderer = self._model_renderers[model.id]
        logger.debug(f"[DEBUG_INIT] Verification: stored_renderer id={id(stored_renderer)} same={stored_renderer is renderer}")

        logger.debug(f"[DEBUG_INIT] model={model.name} id={model.id} mesh_data={model.mesh_data is not None} "
              f"visible={model.visible} transform=({model.transform.position}, {model.transform.scale})")
        if model.mesh_data:
            has_sub = hasattr(model.mesh_data, 'sub_meshes') and model.mesh_data.sub_meshes
            has_pos = bool(model.mesh_data.positions) if hasattr(model.mesh_data, 'positions') else False
            logger.debug(f"[DEBUG_INIT] has_sub_meshes={has_sub} has_positions={has_pos} "
                  f"materials={len(model.mesh_data.materials) if model.mesh_data.materials else 0} "
                  f"bone_mapping={model.mesh_data.bone_mapping}")
            if has_sub:
                for i, sm in enumerate(model.mesh_data.sub_meshes):
                    logger.debug(f"[DEBUG_INIT] sub_mesh[{i}]: verts={len(sm.positions)} indices={len(sm.indices)} "
                          f"material_index={sm.material_index} has_skinning={sm.skinning_data is not None} "
                          f"has_texcoords={bool(sm.texcoords)}")
                logger.debug(f"[DEBUG_INIT] About to call upload_mesh_with_materials on renderer id={id(renderer)}")
                result = renderer.upload_mesh_with_materials(model.mesh_data)
                logger.debug(f"[DEBUG_INIT] upload_mesh_with_materials result={result} renderer id={id(renderer)}")
                logger.debug(f"[DEBUG_INIT] renderer._sub_mesh_buffers count={len(renderer._sub_mesh_buffers)} renderer id={id(renderer)}")
                for i, buf in enumerate(renderer._sub_mesh_buffers):
                    logger.debug(f"[DEBUG_INIT] buffer[{i}]: vao={buf.vao} index_count={buf.index_count} "
                          f"diffuse_color={buf.diffuse_color} alpha_mode={buf.alpha_mode} "
                          f"has_skinning={buf.has_skinning} has_texcoords={buf.has_texcoords}")
            elif has_pos:
                logger.debug("[DEBUG_INIT]   Using upload_mesh (single mesh path)")
                renderer.upload_mesh(
                    model.mesh_data.positions,
                    model.mesh_data.normals,
                    model.mesh_data.indices,
                    model.mesh_data.skinning_data
                )
            else:
                logger.debug("[DEBUG_INIT]   mesh_data exists but no sub_meshes and no positions!")
        else:
            logger.debug("[DEBUG_INIT]   model.mesh_data is None!")

        viz = SkeletonVisualizer()
        if viz.initialize():
            self._model_skeleton_viz[model.id] = viz

    def resizeGL(self, w: int, h: int) -> None:
        glViewport(0, 0, w, h)

    def paintGL(self) -> None:
        # Re-establish default GL state at the start of every frame.
        # Individual renderers may toggle depth test / blend; we must not
        # rely on state left over from initializeGL() or a prior frame.
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        aspect = self.width() / max(1, self.height())
        view = self._camera.get_view_matrix()
        proj = self._camera.get_projection_matrix(aspect)

        if self._show_grid and self._grid_renderer:
            self._grid_renderer.render(view, proj)

        for model in self._scene.get_all_models():

            model_matrix = model.transform.to_matrix()

            if self._show_mesh and model.id in self._model_renderers and model.mesh_data:
                renderer = self._model_renderers[model.id]
                camera_pos = self._camera.get_position()
                renderer.render(model.skeleton, view, proj, model_matrix, camera_position=camera_pos)

            is_selected = model.id == self._scene.get_selected_model_id()
            if self._show_skeleton and is_selected and model.id in self._model_skeleton_viz and model.skeleton:

                # Disable depth test so skeleton shows through the model (x-ray mode)
                glDisable(GL_DEPTH_TEST)
                viz = self._model_skeleton_viz[model.id]
                viz.update_skeleton(model.skeleton)
                viz.render(view, proj, (1.0, 0.5, 0.0), model_matrix=model_matrix)
                glEnable(GL_DEPTH_TEST)
    
            # disable depth test so they draw through models
            if self._show_joints and self._joint_renderer:
                glDisable(GL_DEPTH_TEST)
                self._render_all_joints(view, proj)
                glEnable(GL_DEPTH_TEST)
    
        if self._show_gizmo:
            glClear(GL_DEPTH_BUFFER_BIT)
            glEnable(GL_DEPTH_TEST)
            glDepthFunc(GL_LEQUAL)
            glEnable(GL_CULL_FACE)
            glCullFace(GL_BACK)
            self._render_gizmo(view, proj)
            glDisable(GL_CULL_FACE)
            glDepthFunc(GL_LESS)

            # bounding box overlay
            if self._show_bounding_box and self._bounding_box_renderer:
                crop = self._calculate_sync_crop()
                if crop:
                    cx, cy, cw, ch = crop
                    logger.debug(
                        f"[BBOX] Rendering: vp={self.width()}x{self.height()}, "
                        f"doc={self._bounding_box_doc_size}, "
                        f"crop=({cx},{cy},{cw},{ch})"
                    )
                    self._bounding_box_renderer.render(
                        self.width(), self.height(), cx, cy, cw, ch
                    )
                else:
                    logger.debug(
                        f"[BBOX] No crop returned: show={self._show_bounding_box}, "
                        f"doc_size={self._bounding_box_doc_size}, "
                        f"renderer={self._bounding_box_renderer is not None}"
                    )
        
    def _render_all_joints(self, view: Mat4, proj: Mat4) -> None:
        selected_model, selected_bone = self._scene.get_selected_bone()

        selected_model_id = self._scene.get_selected_model_id()
        for model in self._scene.get_all_models():
            if not model.visible or not model.skeleton:
                continue
            if selected_model_id is not None and model.id != selected_model_id:
                continue
        

            model_matrix = model.transform.to_matrix()
            joint_scale = self._get_joint_scale()

            sel_bone = selected_bone.name if (selected_model == model and selected_bone) else None
            hov_bone = self._hovered_bone_name if self._hovered_model_id == model.id else None

            self._joint_renderer.render(
                model.skeleton,
                view,
                proj,
                selected_bone=sel_bone,
                hovered_bone=hov_bone,
                scale=joint_scale,
                model_matrix=model_matrix
            )

    def _get_axis_rotation(self) -> Optional[Mat4]:
        if self._gizmo_transform_space != "local":
            return None

        model, bone = self._scene.get_selected_bone()
        if not bone or not model:
            return None

        world_transform = bone.get_world_transform()
        rot = world_transform.rotation
        return rot.to_matrix()

    def _render_gizmo(self, view: Mat4, proj: Mat4) -> None:

        model, bone = self._scene.get_selected_bone()
        if not bone or not model:
            return

        bone_world_pos = bone.get_world_position()
        model_world = model.transform.to_matrix()

        gizmo_pos = model_world.transform_point(bone_world_pos)
        gizmo_scale = self._get_gizmo_scale()
        axis_rotation = self._get_axis_rotation()

        if self._gizmo_mode == "rotation" and self._gizmo:
            self._gizmo.render(
                gizmo_pos,
                gizmo_scale,
                view,
                proj,
                hovered_axis=self._gizmo_hover_axis if self._gizmo_state != "dragging" else None,
                dragging_axis=self._gizmo_drag_axis if self._gizmo_state == "dragging" else None,
                axis_rotation=axis_rotation
            )
        elif self._gizmo_mode == "movement" and self._movement_gizmo:
            self._movement_gizmo.render(
                gizmo_pos,
                gizmo_scale,
                view,
                proj,
                hovered_axis=self._gizmo_hover_axis if self._gizmo_state != "dragging" else None,
                dragging_axis=self._gizmo_drag_axis if self._gizmo_state == "dragging" else None,
                axis_rotation=axis_rotation
            )
        elif self._gizmo_mode == "scale" and self._scale_gizmo:
            self._scale_gizmo.render(
                gizmo_pos,
                gizmo_scale,
                view,
                proj,
                hovered_axis=self._gizmo_hover_axis if self._gizmo_state != "dragging" else None,
                dragging_axis=self._gizmo_drag_axis if self._gizmo_state == "dragging" else None,
                axis_rotation=axis_rotation
            )

    def _calculate_sync_crop(self) -> Optional[Tuple[int, int, int, int]]:
        if self._bounding_box_doc_size == (0, 0):
            logger.debug("[BBOX] _calculate_sync_crop: doc_size is (0,0), returning None")
            return None

        doc_w, doc_h = self._bounding_box_doc_size
        vp_w = self.width()
        vp_h = self.height()

        if vp_w <= 0 or vp_h <= 0 or doc_w <= 0 or doc_h <= 0:
            logger.debug(
                f"[BBOX] _calculate_sync_crop: invalid dims - "
                f"vp={vp_w}x{vp_h}, doc={doc_w}x{doc_h}"
            )
            return None

        vp_aspect = vp_w / vp_h
        doc_aspect = doc_w / doc_h

        # Calculate the largest rectangle matching the document aspect ratio
        # that fits entirely within the viewport (letterbox/pillarbox).
        # The crop rect must be <= viewport in both dimensions so that
        # the overlay renderer can shade the letterbox/pillarbox bars.
        if vp_aspect > doc_aspect:
            # Viewport is wider: letterbox (black bars top/bottom)
            crop_h = vp_h
            crop_w = int(vp_h * doc_aspect)
        else:
            # Viewport is taller: pillarbox (black bars left/right)
            crop_w = vp_w
            crop_h = int(vp_w / doc_aspect)

        crop_x = (vp_w - crop_w) // 2
        crop_y = (vp_h - crop_h) // 2

        logger.debug(
            f"[BBOX] _calculate_sync_crop: vp_aspect={vp_aspect:.3f}, "
            f"doc_aspect={doc_aspect:.3f}, "
            f"crop=({crop_x},{crop_y},{crop_w},{crop_h})"
        )

        return (crop_x, crop_y, crop_w, crop_h)

    def render_to_image(self, width: int, height: int) -> QImage:
        logger.debug(f"[RENDER] Starting render_to_image({width}, {height})")
        
        if not self._gl_initialized:
            logger.debug("[RENDER] ERROR: GL not initialized")
            return QImage()
        
        orig_show_skeleton = self._show_skeleton
        orig_show_joints = self._show_joints
        orig_show_gizmo = self._show_gizmo
        
        # Disable non-model elements for sync
        self._show_skeleton = False
        self._show_joints = False
        self._show_gizmo = False

        try:
            logger.debug("[RENDER] Making widget context current...")
            self.makeCurrent()
            
            orig_viewport = glGetIntegerv(GL_VIEWPORT)
            logger.debug(f"[RENDER] Original viewport: {orig_viewport}")
            
            # Create FBO in the same context as the widget (where GL objects were created)
            fbo_format = QOpenGLFramebufferObjectFormat()
            fbo_format.setSamples(4)  # Anti-aliasing
            fbo_format.setAttachment(QOpenGLFramebufferObject.CombinedDepthStencil)
            
            fbo = QOpenGLFramebufferObject(width, height, fbo_format)
            if not fbo.isValid():
                logger.debug("[RENDER] ERROR: Framebuffer object is not valid")
                return QImage()
                
            logger.debug(f"[RENDER] Framebuffer created successfully: {fbo.width()}x{fbo.height()}")
            
            if not fbo.bind():
                logger.debug("[RENDER] ERROR: Failed to bind framebuffer")
                return QImage()
                
            glViewport(0, 0, width, height)
            logger.debug(f"[RENDER] Viewport set to {width}x{height}")
            
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            logger.debug("[RENDER] Buffers cleared")
            
            aspect = width / max(1, height)
            view = self._camera.get_view_matrix()
            proj = self._camera.get_projection_matrix(aspect)
            logger.debug(f"[RENDER] Matrices calculated (aspect: {aspect})")

            visible_models = [m for m in self._scene.get_all_models() if m.visible]
            logger.debug(f"[RENDER] Found {len(visible_models)} visible models out of {len(self._scene.get_all_models())}")

            for i, model in enumerate(visible_models):
                logger.debug(f"[RENDER] Rendering model {i+1}/{len(visible_models)}: {model.name} (id: {model.id})")

                model_matrix = model.transform.to_matrix()
    
                if self._show_mesh and model.id in self._model_renderers and model.mesh_data:
                    logger.debug(f"[RENDER] - Rendering mesh for {model.name}")
                    renderer = self._model_renderers[model.id]
                    camera_pos = self._camera.get_position()
                    renderer.render(model.skeleton, view, proj, model_matrix, camera_position=camera_pos)
                else:
                    reasons = []
                    if not self._show_mesh: reasons.append("mesh disabled")
                    if model.id not in self._model_renderers: reasons.append("no renderer")
                    if not model.mesh_data: reasons.append("no mesh data")
                    logger.debug(f"[RENDER]   - Skipping mesh: {', '.join(reasons)}")

                if self._show_skeleton and model.id in self._model_skeleton_viz and model.skeleton:
                    # Disable depth test so skeleton shows through the model (x-ray mode)
                    glDisable(GL_DEPTH_TEST)
                    logger.debug(f"[RENDER] - Rendering skeleton for {model.name}")
                    viz = self._model_skeleton_viz[model.id]
                    viz.update_skeleton(model.skeleton)
                    viz.render(view, proj, (1.0, 0.5, 0.0), model_matrix=model_matrix)
                    glEnable(GL_DEPTH_TEST)
                else:
                    reasons = []
                    if not self._show_skeleton: reasons.append("skeleton disabled")
                    if model.id not in self._model_skeleton_viz: reasons.append("no viz")
                    if not model.skeleton: reasons.append("no skeleton")
                    logger.debug(f"[RENDER]   - Skipping skeleton: {', '.join(reasons)}")

            if self._show_joints and self._joint_renderer:
                logger.debug("[RENDER] Rendering joints for all models")
                self._render_all_joints(view, proj)
            else:
                reasons = []
                if not self._show_joints: reasons.append("joints disabled")
                if not self._joint_renderer: reasons.append("no joint renderer")
                logger.debug(f"[RENDER] Skipping joints: {', '.join(reasons)}")

            if self._show_gizmo:
                model, bone = self._scene.get_selected_bone()
                if model and bone:
                    logger.debug(f"[RENDER] Rendering gizmo for {model.name}/{bone.name}")
                    self._render_gizmo(view, proj)
                else:
                    logger.debug("[RENDER] Skipping gizmo: no selected bone")
            else:
                logger.debug("[RENDER] Skipping gizmo: disabled")
            
            logger.debug("[RENDER] Getting rendered image from framebuffer...")
            image = fbo.toImage()
            
            fbo.release()
    
            glViewport(orig_viewport[0], orig_viewport[1], orig_viewport[2], orig_viewport[3])
            logger.debug(f"[RENDER] Restored viewport to {orig_viewport}")
            
            logger.debug(f"[RENDER] Success! Image: {image.width()}x{image.height()}, null: {image.isNull()}")
            return image
            
        except Exception as e:
            logger.debug(f"[RENDER] ERROR: Exception during render: {e}")
            import traceback
            traceback.logger.debug_exc()
            
            try:
                if 'orig_viewport' in locals():
                    glViewport(orig_viewport[0], orig_viewport[1], orig_viewport[2], orig_viewport[3])
            except Exception as cleanup_e:
                logger.debug(f"[RENDER] ERROR: Failed to restore viewport: {cleanup_e}")
            return QImage()
        finally:
            # Restore original visibility states
            self._show_skeleton = orig_show_skeleton
            self._show_joints = orig_show_joints
            self._show_gizmo = orig_show_gizmo
        

    def _on_update(self) -> None:
        
        import time

        if not hasattr(self, '_last_update_time'):
            self._last_update_time = time.time()
            return

        current_time = time.time()
        delta_time = current_time - self._last_update_time
        self._last_update_time = current_time

        camera_animating = self._camera.update(delta_time)

        if self._movement_keys_pressed:
            self._update_keyboard_movement(delta_time)

        if camera_animating or self._movement_keys_pressed:
            self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:

        self._last_mouse_pos = event.pos()
        self._mouse_button = event.button()

        if event.button() == Qt.LeftButton:
            if self._show_gizmo and self._gizmo_hover_axis:
                self._start_gizmo_drag(event.pos())
            else:
                prev_model = self._scene.get_selected_model_id()
                prev_bone = self._scene._selected_bone_name
                self._pick_joint(event.pos())
                cur_model = self._scene.get_selected_model_id()
                cur_bone = self._scene._selected_bone_name
                if cur_model == prev_model and cur_bone == prev_bone:
                    self._scene.deselect_bone()
                self._gizmo_hover_axis = None

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        
        if self._last_mouse_pos is None:
            self._update_gizmo_hover(event.pos())
            self.update()
            return

        dx = event.x() - self._last_mouse_pos.x()
        dy = event.y() - self._last_mouse_pos.y()

        rot_speed = self._settings.camera.get('rotation_speed', 0.01) if self._settings else 0.01

        if self._gizmo_state == "dragging":
            self._update_gizmo_drag(event.pos())
        elif self._mouse_button == Qt.LeftButton:
            modifiers = event.modifiers()
            if modifiers & Qt.ShiftModifier:
                self._camera.rotate(dx * rot_speed, dy * rot_speed)
            elif modifiers & Qt.ControlModifier:
                self._camera.pan(dx, dy)
            else:
                self._update_gizmo_hover(event.pos())
        elif self._mouse_button == Qt.MiddleButton:
            self._camera.pan(dx, dy)
        elif self._mouse_button == Qt.RightButton:
            modifiers = event.modifiers()
            if modifiers & Qt.ShiftModifier:
                self._camera.pan(dx, dy)
            elif modifiers & Qt.ControlModifier:
                self._camera.zoom(dy * 0.01)
            else:
                self._camera.rotate(dx * rot_speed, dy * rot_speed)

        self._last_mouse_pos = event.pos()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        
        if self._gizmo_state == "dragging":
            self._end_gizmo_drag()

        self._mouse_button = None
        self._last_mouse_pos = None
        self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:

        delta = event.angleDelta().y() / 120.0
        modifiers = event.modifiers()
        if modifiers & Qt.ControlModifier:
            dolly_speed = self._settings.mouse.get_scroll_dolly_speed() if self._settings else 0.2
            self._camera.move_forward(delta * dolly_speed)
        else:
            zoom_speed = self._settings.mouse.get_scroll_zoom_speed() if self._settings else 0.1
            self._camera.zoom(delta * zoom_speed)
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()
        kb = self._settings.keyboard if self._settings else None

        movement_key = self._get_movement_key(key, modifiers)
        if movement_key:
            self._movement_keys_pressed.add(movement_key)
            event.accept()
            return

        if kb:
            action = kb.find_action(key, modifiers)
            if action:
                handler = self._key_handlers.get(action)
                if handler: 
                    handler()

        self.update()


    def reset_bone(self):
        _, bone = self._scene.get_selected_bone()
        if bone:
            bone.pose_transform.rotation = Quat()
            bone.pose_transform.position = Vec3()
            bone.pose_transform.scale = Vec3(1, 1, 1)
            bone.pose_transform._matrix_dirty = True
            self.pose_changed.emit()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:

        key = event.key()
        modifiers = event.modifiers()

        movement_key = self._get_movement_key(key, modifiers)
        if movement_key and movement_key in self._movement_keys_pressed:
            self._movement_keys_pressed.discard(movement_key)
            event.accept()
            return

        super().keyReleaseEvent(event)

    def _get_movement_key(self, key: int, modifiers: int) -> Optional[str]:
        if modifiers != Qt.NoModifier:
            return None
        kb = self._settings.keyboard if self._settings else None
        if kb:
            action = kb.find_action(key, Qt.NoModifier)
            if action and action in self._MOVEMENT_ACTION_MAP:
                return self._MOVEMENT_ACTION_MAP[action]
        # Fallback defaults when no settings
        fallback = {Qt.Key_W: 'forward', Qt.Key_S: 'backward', Qt.Key_A: 'left',
                    Qt.Key_D: 'right', Qt.Key_Q: 'up', Qt.Key_E: 'down'}
        return fallback.get(key)


    def _update_keyboard_movement(self, delta_time: float) -> None:
        
        if not self._movement_keys_pressed:
            return
    
        if self._settings:
            base_speed = self._settings.camera.get('keyboard_movement_speed', 0.05)
            precision_factor = self._settings.camera.get('precision_factor', 0.25)
            fast_factor = self._settings.camera.get('fast_factor', 3.0)
        else:
            base_speed = 0.05
            precision_factor = 0.25
            fast_factor = 3.0
    
        # We check keyboard modifiers directly since user might be holding multiple
        speed = base_speed
        from PyQt5.QtGui import QGuiApplication
        modifiers = QGuiApplication.keyboardModifiers()
        if modifiers & Qt.ShiftModifier:
            speed *= precision_factor
        elif modifiers & Qt.ControlModifier:
            speed *= fast_factor
    
        # In head-look mode, movement is relative to the look direction
        # In orbit mode, movement is applied to the orbit target
        if self._camera.head_look_mode:
            forward = self._camera._get_head_forward()
            right = self._camera._get_head_right()
            up = self._camera._get_head_up()
            
            delta = Vec3(0, 0, 0)
            
            if 'forward' in self._movement_keys_pressed:
                delta = delta + forward * speed
            if 'backward' in self._movement_keys_pressed:
                delta = delta - forward * speed
            if 'left' in self._movement_keys_pressed:
                delta = delta - right * speed
            if 'right' in self._movement_keys_pressed:
                delta = delta + right * speed
            if 'up' in self._movement_keys_pressed:
                delta = delta + up * speed
            if 'down' in self._movement_keys_pressed:
                delta = delta - up * speed
            
            if delta.x != 0 or delta.y != 0 or delta.z != 0:
                self._camera._head_position = self._camera._head_position + delta
        else:
            forward = (self._camera.target - self._camera.get_position()).normalized()
            right = Vec3(0, 1, 0).cross(forward).normalized()
            up = Vec3(0, 1, 0)  # World up
    
            delta = Vec3(0, 0, 0)
    
            if 'forward' in self._movement_keys_pressed:
                delta = delta + forward * speed
            if 'backward' in self._movement_keys_pressed:
                delta = delta - forward * speed
            if 'left' in self._movement_keys_pressed:
                delta = delta - right * speed
            if 'right' in self._movement_keys_pressed:
                delta = delta + right * speed
            if 'up' in self._movement_keys_pressed:
                delta = delta + up * speed
            if 'down' in self._movement_keys_pressed:
                delta = delta - up * speed
    
            if delta.x != 0 or delta.y != 0 or delta.z != 0:
                self._camera.move_target(delta)

    def _point_to_segment_dist(self, px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
        abx = bx - ax
        aby = by - ay
        apx = px - ax
        apy = py - ay
        ab_sq = abx * abx + aby * aby
        if ab_sq < 1e-10:
            return math.sqrt(apx * apx + apy * apy)
        t = (apx * abx + apy * aby) / ab_sq
        t = max(0.0, min(1.0, t))
        cx = ax + t * abx
        cy = ay + t * aby
        dx = px - cx
        dy = py - cy
        return math.sqrt(dx * dx + dy * dy)

    def _pick_joint(self, mouse_pos) -> None:

        best_model_id = None
        best_bone_name = None
        best_dist = float('inf')

        aspect = self.width() / max(1, self.height())
        view = self._camera.get_view_matrix()
        proj = self._camera.get_projection_matrix(aspect)
        view_proj = proj * view

        viewport = (0, 0, self.width(), self.height())

        selected_model_id = self._scene.get_selected_model_id()
        mx = mouse_pos.x()
        my = mouse_pos.y()

        for model in self._scene.get_all_models():
            if not model.visible or not model.skeleton:
                continue

            joint_scale = self._get_joint_scale()
            model_matrix = model.transform.to_matrix()

            screen_positions: Dict[str, Tuple[float, float]] = {}
            for bone in model.skeleton:
                if not bone.visible:
                    continue
                bone_pos = bone.get_world_position()
                world_pos = model_matrix.transform_point(bone_pos)
                sx, sy = self._project_to_screen(world_pos, view_proj, viewport)
                screen_positions[bone.name] = (sx, sy)

                dx = mx - sx
                dy = my - sy
                dist = math.sqrt(dx * dx + dy * dy)
                joint_radius = joint_scale * 50
                if dist < joint_radius and dist < best_dist:
                    best_dist = dist
                    best_model_id = model.id
                    best_bone_name = bone.name

            segment_threshold = joint_scale * 30
            for bone in model.skeleton:
                if not bone.visible or bone.parent is None or not bone.parent.visible:
                    continue
                if bone.parent.name not in screen_positions or bone.name not in screen_positions:
                    continue
                parent_sx, parent_sy = screen_positions[bone.parent.name]
                child_sx, child_sy = screen_positions[bone.name]
                seg_dist = self._point_to_segment_dist(mx, my, parent_sx, parent_sy, child_sx, child_sy)
                if seg_dist < segment_threshold and seg_dist < best_dist:
                    best_dist = seg_dist
                    best_model_id = model.id
                    best_bone_name = bone.parent.name

        if best_model_id and best_bone_name:
            if best_model_id != selected_model_id:
                self._scene.select_model(best_model_id)
                self.model_selected.emit(best_model_id)
                self.model_selection_changed.emit(best_model_id)
            self.select_bone(best_model_id, best_bone_name)

    def _project_to_screen(
        self,
        world_pos: Vec3,
        view_proj: Mat4,
        viewport: Tuple[int, int, int, int]
    ) -> Tuple[float, float]:

        m = view_proj.m
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

    def _update_gizmo_hover(self, mouse_pos) -> None:
        
        model, bone = self._scene.get_selected_bone()
        if not bone or not model:
            self._gizmo_hover_axis = None
            return

        gizmo_pos = self._get_gizmo_position()
        if gizmo_pos is None:
            self._gizmo_hover_axis = None
            return

        gizmo_scale = self._get_gizmo_scale()
        aspect = self.width() / max(1, self.height())
        view = self._camera.get_view_matrix()
        proj = self._camera.get_projection_matrix(aspect)
        viewport = (0, 0, self.width(), self.height())

        axis_rotation = self._get_axis_rotation()

        if self._gizmo_mode == "rotation" and self._gizmo:
            self._gizmo_hover_axis = self._gizmo.hit_test(
                (mouse_pos.x(), mouse_pos.y()),
                gizmo_pos, gizmo_scale, view, proj, viewport,
                axis_rotation=axis_rotation
            )
        elif self._gizmo_mode == "movement" and self._movement_gizmo:
            self._gizmo_hover_axis = self._movement_gizmo.hit_test(
                (mouse_pos.x(), mouse_pos.y()),
                gizmo_pos, gizmo_scale, view, proj, viewport,
                axis_rotation=axis_rotation
            )
        elif self._gizmo_mode == "scale" and self._scale_gizmo:
            self._gizmo_hover_axis = self._scale_gizmo.hit_test(
                (mouse_pos.x(), mouse_pos.y()),
                gizmo_pos, gizmo_scale, view, proj, viewport,
                axis_rotation=axis_rotation
            )
        else:
            self._gizmo_hover_axis = None

    def _get_gizmo_position(self) -> Optional[Vec3]:
        
        model, bone = self._scene.get_selected_bone()
        if not bone or not model:
            return None

        bone_pos = bone.get_world_position()

        model_matrix = model.transform.to_matrix()
        return model_matrix.transform_point(bone_pos)

    def _start_gizmo_drag(self, mouse_pos) -> bool:
        
        model, bone = self._scene.get_selected_bone()
        if not bone or not model:
            return False
        
        if model.id != self._scene.get_selected_model_id():
            return False

        gizmo_pos = self._get_gizmo_position()
        if gizmo_pos is None:
            return False

        gizmo_scale = self._get_gizmo_scale()
        aspect = self.width() / max(1, self.height())
        view = self._camera.get_view_matrix()
        proj = self._camera.get_projection_matrix(aspect)
        viewport = (0, 0, self.width(), self.height())
        axis_rotation = self._get_axis_rotation()
        self._drag_axis_rotation = axis_rotation

        if self._gizmo_mode == "rotation":
            if self._gizmo:
                start_point = self._gizmo.get_point_on_circle_plane(
                    (mouse_pos.x(), mouse_pos.y()),
                    self._gizmo_hover_axis,
                    gizmo_pos,
                    view,
                    proj,
                    viewport,
                    axis_rotation=axis_rotation
                )
                if start_point is None:
                    return False

                self._gizmo_state = "dragging"
                self._gizmo_drag_axis = self._gizmo_hover_axis
                self._gizmo_drag_start_point = start_point
                self._gizmo_drag_prev_point = start_point
                self._accumulated_rotation = Quat.identity()
                self._rotation_slow_factor = 1.0
                self._initial_bone_rotation = bone.pose_transform.rotation
                self._initial_delta_rotation = self._get_world_delta_rotation(bone)
                return True
        elif self._gizmo_mode == "movement":
            if self._movement_gizmo:
                if self._gizmo_hover_axis == 'CENTER':
                    start_point = self._movement_gizmo.get_point_on_plane(
                        (mouse_pos.x(), mouse_pos.y()),
                        self._gizmo_hover_axis,
                        gizmo_pos,
                        view,
                        proj,
                        viewport
                    )
                else:
                    start_point = self._movement_gizmo.get_point_on_axis(
                        (mouse_pos.x(), mouse_pos.y()),
                        self._gizmo_hover_axis,
                        gizmo_pos,
                        view,
                        proj,
                        viewport,
                        axis_rotation=axis_rotation
                    )
                if start_point is None:
                    return False

                self._gizmo_state = "dragging"
                self._gizmo_drag_axis = self._gizmo_hover_axis
                self._gizmo_drag_start_point = start_point
                self._gizmo_drag_prev_point = start_point
                self._movement_drag_start_pos = bone.get_world_position()
                self._movement_drag_prev_pos = self._movement_drag_start_pos
                return True
        elif self._gizmo_mode == "scale" and self._scale_gizmo:
            start_point = self._scale_gizmo.get_point_on_axis(
                (mouse_pos.x(), mouse_pos.y()),
                self._gizmo_hover_axis,
                gizmo_pos,
                gizmo_scale,
                view,
                proj,
                viewport,
                axis_rotation=axis_rotation
            )
            if start_point is None:
                return False

            self._gizmo_state = "dragging"
            self._gizmo_drag_axis = self._gizmo_hover_axis
            self._gizmo_drag_start_point = start_point
            self._gizmo_drag_prev_point = start_point
            self._scale_drag_start_scale = model.transform.scale
            return True

        return False

    def _update_gizmo_drag(self, mouse_pos) -> None:
        
        if self._gizmo_state != "dragging" or self._gizmo_drag_axis is None:
            return

        model, bone = self._scene.get_selected_bone()
        if not bone or not model:
            return

        gizmo_pos = self._get_gizmo_position()
        if gizmo_pos is None:
            return

        gizmo_scale = self._get_gizmo_scale()
        aspect = self.width() / max(1, self.height())
        view = self._camera.get_view_matrix()
        proj = self._camera.get_projection_matrix(aspect)
        viewport = (0, 0, self.width(), self.height())

        if self._gizmo_mode == "rotation":
            self._update_rotation_gizmo_drag(mouse_pos, bone, model, gizmo_pos, gizmo_scale, view, proj, viewport)
        elif self._gizmo_mode == "movement":
            self._update_movement_gizmo_drag(mouse_pos, bone, model, gizmo_pos, gizmo_scale, view, proj, viewport)
        elif self._gizmo_mode == "scale":
            self._update_scale_gizmo_drag(mouse_pos, bone, model, gizmo_pos, gizmo_scale, view, proj, viewport)

    def _update_rotation_gizmo_drag(self, mouse_pos, bone, model, gizmo_pos, gizmo_scale, view, proj, viewport) -> None:

        if self._initial_delta_rotation is None or not self._gizmo:
            return

        axis_rotation = self._drag_axis_rotation

        current_point = self._gizmo.get_point_on_circle_plane(
            (mouse_pos.x(), mouse_pos.y()),
            self._gizmo_drag_axis,
            gizmo_pos,
            view,
            proj,
            viewport,
            axis_rotation=axis_rotation
        )

        if current_point is None:
            return

        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QApplication
        modifiers = QApplication.keyboardModifiers()
        new_slow_factor = 0.25 if (modifiers & Qt.ShiftModifier) else 1.0

        if new_slow_factor != self._rotation_slow_factor:
            self._rotation_slow_factor = new_slow_factor

        delta_rotation = self._gizmo.get_rotation_from_drag(
            self._gizmo_drag_prev_point,
            current_point,
            self._gizmo_drag_axis,
            gizmo_pos,
            axis_rotation=axis_rotation
        )

        if (self._rotation_slow_factor - 1.0) > 0.01:
            # TODO: remove if unnessicairy
            # axis_vec = RotationGizmo._get_axis_dir(self._gizmo_drag_axis, axis_rotation) if axis_rotation is not None else (Vec3(1, 0, 0) if self._gizmo_drag_axis == 'X' else (Vec3(0, 1, 0) if self._gizmo_drag_axis == 'Y' else Vec3(0, 0, 1)))
            # import math
            axis_angle = delta_rotation.to_axis_angle()
            axis_dir = axis_angle[0]
            angle_rad = axis_angle[1]
            scaled_angle = angle_rad * self._rotation_slow_factor
            delta_rotation = Quat.from_axis_angle(axis_dir, scaled_angle)

        self._accumulated_rotation = delta_rotation * self._accumulated_rotation
        new_delta_rotation = self._accumulated_rotation * self._initial_delta_rotation

        self._apply_world_delta_rotation(bone, new_delta_rotation)
        self._gizmo_drag_prev_point = current_point

        if model and model.skeleton:
            for b in model.skeleton:
                b._mark_dirty()

    def _update_movement_gizmo_drag(self, mouse_pos, bone, model, gizmo_pos, gizmo_scale, view, proj, viewport) -> None:
        
        if not self._movement_gizmo:
            return

        if self._gizmo_drag_axis == 'CENTER':
            current_point = self._movement_gizmo.get_point_on_plane(
                (mouse_pos.x(), mouse_pos.y()),
                gizmo_pos,
                view,
                proj,
                viewport
            )
            if current_point is None or self._gizmo_drag_prev_point is None:
                return
            delta = current_point - self._gizmo_drag_prev_point
            movement_speed = 0.5
            delta = delta * movement_speed
            self._apply_movement_delta(bone, delta)
            self._gizmo_drag_prev_point = current_point
        else:
            # Use the INITIAL gizmo position as the axis reference point.
            # The axis line must stay fixed in space during the drag, not move with the bone.
            # If we use the current gizmo_pos, the axis shifts as the bone moves, causing drift.
            initial_gizmo_pos = self._movement_drag_start_pos
            if initial_gizmo_pos is None:
                initial_gizmo_pos = gizmo_pos

            axis_rotation = self._drag_axis_rotation
    
            current_point = self._movement_gizmo.get_point_on_axis(
                (mouse_pos.x(), mouse_pos.y()),
                self._gizmo_drag_axis,
                initial_gizmo_pos,
                view,
                proj,
                viewport,
                axis_rotation=axis_rotation
            )
            if current_point is None or self._gizmo_drag_prev_point is None:
                return

            raw_delta = current_point - self._gizmo_drag_prev_point

            if axis_rotation is not None:
                rm = axis_rotation.m
                if self._gizmo_drag_axis == 'X':
                    base_dir = Vec3(1, 0, 0)
                elif self._gizmo_drag_axis == 'Y':
                    base_dir = Vec3(0, 1, 0)
                else:
                    base_dir = Vec3(0, 0, 1)
                axis_dir = Vec3(
                    rm[0] * base_dir.x + rm[4] * base_dir.y + rm[8] * base_dir.z,
                    rm[1] * base_dir.x + rm[5] * base_dir.y + rm[9] * base_dir.z,
                    rm[2] * base_dir.x + rm[6] * base_dir.y + rm[10] * base_dir.z
                )
            else:
                if self._gizmo_drag_axis == 'X':
                    axis_dir = Vec3(1, 0, 0)
                elif self._gizmo_drag_axis == 'Y':
                    axis_dir = Vec3(0, 1, 0)
                else:
                    axis_dir = Vec3(0, 0, 1)

            # Project delta onto the axis to prevent perpendicular drift
            dot_product = raw_delta.x * axis_dir.x + raw_delta.y * axis_dir.y + raw_delta.z * axis_dir.z
            delta = Vec3(
                dot_product * axis_dir.x,
                dot_product * axis_dir.y,
                dot_product * axis_dir.z
            )

            movement_speed = 0.5
            delta = delta * movement_speed
            self._apply_movement_delta(bone, delta)
            self._gizmo_drag_prev_point = current_point

        if model and model.skeleton:
            for b in model.skeleton:
                b._mark_dirty()

    def _get_world_delta_rotation(self, bone: Bone) -> Quat:
        
        if bone.parent is not None:
            parent_world = bone.parent.get_world_transform()
            parent_world_rot = parent_world.rotation
        else:
            parent_world_rot = Quat.identity()

        bind_rot = bone.bind_transform.rotation
        pose_rot = bone.pose_transform.rotation

        current_world_rot = parent_world_rot * (pose_rot * bind_rot)
        bind_world_rot = parent_world_rot * bind_rot
        delta_rot = current_world_rot * bind_world_rot.inverse()

        return delta_rot

    def _apply_world_delta_rotation(self, bone: Bone, delta_rotation: Quat) -> None:
        
        if bone.parent is not None:
            parent_world = bone.parent.get_world_transform()
            parent_world_rot = parent_world.rotation
        else:
            parent_world_rot = Quat.identity()

        bind_rot = bone.bind_transform.rotation
        bind_world_rot = parent_world_rot * bind_rot
        new_world_rot = delta_rotation * bind_world_rot
        pose_rotation = parent_world_rot.inverse() * new_world_rot * bind_rot.inverse()
        bone.pose_transform.rotation = pose_rotation

    def _apply_movement_delta(self, bone: Bone, delta: Vec3) -> None:

        parent = bone.parent

        if parent is None:
            # Root bone: translate the entire model
            # IMPORTANT: The delta is in world space, but we need to apply it in the bone's local space
            # The world transform is: world = bind * pose
            # So: pose_position = bind^-1 * world_delta
            
            # Get the bind rotation to convert world delta to local delta
            bind_rot = bone.bind_transform.rotation
            
            # Convert world-space delta to local space
            # local_delta = bind_rot^-1 * world_delta
            local_delta = bind_rot.inverse().rotate_vector(delta)
            
            bone.pose_transform.position = bone.pose_transform.position + local_delta
            bone._mark_dirty()
            return

        current_pos = bone.get_world_position()

        parent_pos = parent.get_world_position()

        arm_vector = current_pos - parent_pos
        arm_length = arm_vector.length()

        if arm_length < 0.001:
            return

        # The bone moves in an arc around the parent.
        # For small movements, arc_length = arm_length * rotation_angle
        # So: rotation_angle = delta_magnitude / arm_length

        delta_length = delta.length()
        if delta_length < 1e-10:
            return

        rotation_angle = delta_length / arm_length

        # Determine the rotation axis:
        # The axis must be perpendicular to both the arm vector and the desired movement direction
        # This ensures the bone moves in the direction of delta when rotated

        arm_norm = arm_vector.normalized()

        delta_norm = delta.normalized()

        # The rotation axis is perpendicular to both arm and movement direction
        # cross(arm, delta) gives the axis of rotation
        rotation_axis = arm_norm.cross(delta_norm)
        rotation_axis_len = rotation_axis.length()

        if rotation_axis_len < 1e-10:
            # Arm and delta are parallel - can't rotate in that direction
            # This happens when trying to move directly toward/away from parent
            return

        rotation_axis = rotation_axis.normalized()

        # Determine the sign of the rotation
        # Check if the rotation direction is correct by verifying the cross product
        # If we rotate by +angle around rotation_axis, the bone should move in +delta direction
        # The cross product arm * rotation_axis gives the tangent direction
        tangent = arm_norm.cross(rotation_axis)
    
        # The tangent direction is arm * rotation_axis
        # For correct rotation: rotation_axis * arm should point in delta direction
        # Since rotation_axis * arm = -(arm * rotation_axis) = -tangent
        # We need -tangent to align with delta, so tangent should be opposite to delta
        # If tangent.dot(delta_norm) > 0, tangent points same as delta, which is wrong
        if tangent.dot(delta_norm) > 0:
            rotation_axis = rotation_axis * -1

        world_rotation = Quat.from_axis_angle(rotation_axis, rotation_angle)

        parent_world_rot = parent.get_world_rotation()

        if parent.parent is not None:
            grandparent_world_rot = parent.parent.get_world_rotation()
        else:
            grandparent_world_rot = Quat.identity()

        parent_bind_rot = parent.bind_transform.rotation

        new_pose_rot = grandparent_world_rot.inverse() * world_rotation * parent_world_rot * parent_bind_rot.inverse()

        parent.pose_transform.rotation = new_pose_rot
        parent._mark_dirty()

    def _update_scale_gizmo_drag(self, mouse_pos, bone, model, gizmo_pos, gizmo_scale, view, proj, viewport) -> None:

        if not self._scale_gizmo or not hasattr(self, '_scale_drag_start_scale'):
            return

        axis_rotation = self._drag_axis_rotation

        current_point = self._scale_gizmo.get_point_on_axis(
            (mouse_pos.x(), mouse_pos.y()),
            self._gizmo_drag_axis,
            gizmo_pos,
            gizmo_scale,
            view,
            proj,
            viewport,
            axis_rotation=axis_rotation
        )

        if current_point is None or self._gizmo_drag_start_point is None:
            return

        new_scale = self._scale_gizmo.get_scale_from_drag(
            self._gizmo_drag_start_point,
            current_point,
            self._gizmo_drag_axis,
            gizmo_pos,
            self._scale_drag_start_scale,
            axis_rotation=axis_rotation
        )

        model.transform.scale = new_scale

        if model and model.skeleton:
            for b in model.skeleton:
                b._mark_dirty()

        self.pose_changed.emit()
    
    def _end_gizmo_drag(self) -> None:

        self._gizmo_state = "idle"
        self._gizmo_drag_axis = None
        self._gizmo_drag_start_point = None
        self._gizmo_drag_prev_point = None
        self._accumulated_rotation = None
        self._initial_delta_rotation = None
        self._rotation_slow_factor = 1.0
        self._drag_axis_rotation = None
        self.pose_changed.emit()

    def reset_camera(self) -> None:

        self._camera = Camera()
        self._head_look_mode = False
        self._apply_camera_settings()
        self._frame_scene()

    def frame_model(self) -> None:

        self._frame_scene()

    def set_fov(self, fov: float) -> None:

        self._camera.fov = max(30.0, min(120.0, fov))
        self.update()

    def _save_bookmark(self, index: int) -> None:

        if not 1 <= index <= 9:
            return

        if self._bookmark_manager:
            self._bookmark_manager.save_bookmark(index, self._camera)
        else:
            is_head_look = getattr(self._camera, '_head_look_mode', False)
            mode = 'head_look' if is_head_look else 'orbit'
            head_pos = self._camera._head_position if is_head_look else None
            bookmark = {
                'target': (self._camera.target.x, self._camera.target.y, self._camera.target.z),
                'distance': self._camera.distance,
                'yaw': self._camera.yaw,
                'pitch': self._camera.pitch,
                'fov': self._camera.fov,
                'mode': mode,
            }
            if is_head_look and head_pos is not None:
                bookmark['head_position'] = (head_pos.x, head_pos.y, head_pos.z)
                bookmark['head_yaw'] = self._camera._head_yaw
                bookmark['head_pitch'] = self._camera._head_pitch
            self._camera_bookmarks[index] = bookmark

    def _recall_bookmark(self, index: int) -> None:

        if not 1 <= index <= 9:
            return

        # Track old mode to detect changes
        old_mode = 'head_look' if self._head_look_mode else 'orbit'
    
        if self._bookmark_manager:
            if self._bookmark_manager.load_bookmark(index, self._camera):
                # Sync viewport head-look mode flag with camera state
                if hasattr(self._camera, '_head_look_mode'):
                    self._head_look_mode = self._camera._head_look_mode
                # Emit signal if mode changed
                new_mode = 'head_look' if self._head_look_mode else 'orbit'
                if new_mode != old_mode:
                    self.camera_mode_changed.emit(new_mode)
                self.update()
            return
    
        bookmark = self._camera_bookmarks.get(index)
        if bookmark is None:
            return
    
        target = bookmark.get('target', (0, 1, 0))
        self._camera.target = Vec3(target[0], target[1], target[2])
        self._camera.distance = bookmark.get('distance', 3.0)
        self._camera.yaw = bookmark.get('yaw', 0.0)
        self._camera.pitch = bookmark.get('pitch', 0.0)
        self._camera.fov = bookmark.get('fov', 45.0)
    
        # Determine new mode from bookmark
        new_mode = bookmark.get('mode', 'orbit')
    
        # Restore head-look mode state if bookmark was saved in head-look mode
        if new_mode == 'head_look' and hasattr(self._camera, '_head_position'):
            head_pos = bookmark.get('head_position', (0, 1.5, 3))
            self._camera._head_position = Vec3(head_pos[0], head_pos[1], head_pos[2])
            self._camera._head_yaw = bookmark.get('head_yaw', 0.0)
            self._camera._head_pitch = bookmark.get('head_pitch', 0.0)
            if hasattr(self._camera, '_head_look_mode'):
                self._camera._head_look_mode = True
                self._head_look_mode = True
        elif new_mode == 'orbit':
            # Explicitly restore orbit mode if bookmark was saved in orbit mode
            if hasattr(self._camera, '_head_look_mode'):
                self._camera._head_look_mode = False
                self._head_look_mode = False
    
        # Emit signal if mode changed
        if new_mode != old_mode:
            self.camera_mode_changed.emit(new_mode)
    
        self.update()

    def get_bookmark_manager(self) -> Optional[CameraBookmarkManager]:
        
        return self._bookmark_manager

    def has_bookmark(self, index: int) -> bool:
        
        if self._bookmark_manager:
            return self._bookmark_manager.has_bookmark(index)
        return index in self._camera_bookmarks

    def get_bookmark_info(self, index: int) -> Optional[str]:
        
        if self._bookmark_manager:
            bookmark = self._bookmark_manager.get_bookmark(index)
            if bookmark:
                return bookmark.get_summary()
        return None

    def load_project_bookmarks(self, bookmarks: dict) -> None:

        logger.debug(f"[Viewport] Loading {len(bookmarks)} project bookmarks")
        for slot_str, bookmark_data in bookmarks.items():
            try:
                slot = int(slot_str)
                if 1 <= slot <= 9:
                    self._camera_bookmarks[slot] = bookmark_data
                    logger.debug(f"[Viewport] Loaded bookmark {slot}")
            except (ValueError, KeyError) as e:
                logger.debug(f"[Viewport] Error loading bookmark {slot_str}: {e}")
        self.update()

    def get_project_bookmarks(self) -> dict:

        return {str(slot): data for slot, data in self._camera_bookmarks.items()}

    def set_head_look_mode(self, enabled: bool) -> None:

        self._head_look_mode = enabled
        self._camera.head_look_mode = enabled
        self.update()

    def get_head_look_mode(self) -> bool:
        
        return self._head_look_mode
    

    def set_bounding_box_target(self, doc_width: int, doc_height: int) -> None:
        self._bounding_box_doc_size = (doc_width, doc_height)
        self.update()

    def set_show_bounding_box(self, show: bool) -> None:
        self._show_bounding_box = show
        self.update()

    def clear_models(self) -> None:

        self._model_renderers.clear()
        self._model_skeleton_viz.clear()
        self.update()

    def set_distance_gradient_enabled(self, enabled: bool) -> None:

        for renderer in self._model_renderers.values():
            renderer.set_distance_gradient_enabled(enabled)
        self.update()

    def set_distance_range(self, near: float, far: float) -> None:

        for renderer in self._model_renderers.values():
            renderer.set_distance_range(near, far)
        self.update()

    def _apply_silhouette_settings(self) -> None:

        if not self._settings:
            return
        ui = self._settings.ui
        self._silhouette_mode = ui.get('silhouette_mode', False)
        silhouette_color_hex = ui.get('silhouette_color', '#595959')
        outline_color_hex = ui.get('silhouette_outline_color', '#141414')
        rim_intensity = ui.get('rim_intensity', 0.6)
        outline_width = ui.get('outline_width', 0.0001)
        r = int(silhouette_color_hex[1:3], 16) / 255.0
        g = int(silhouette_color_hex[3:5], 16) / 255.0
        b = int(silhouette_color_hex[5:7], 16) / 255.0
        or_ = int(outline_color_hex[1:3], 16) / 255.0
        og = int(outline_color_hex[3:5], 16) / 255.0
        ob = int(outline_color_hex[5:7], 16) / 255.0
        for renderer in self._model_renderers.values():
            renderer.set_silhouette_mode(self._silhouette_mode)
            renderer.set_silhouette_color((r, g, b))
            renderer.set_silhouette_outline_color((or_, og, ob))
            renderer.set_rim_intensity(rim_intensity)
            renderer.set_outline_width(outline_width)

    def set_preset_view(self, view: str) -> None:

        if view == "top":
            self._camera.yaw = 0
            self._camera.pitch = math.pi / 2 - 0.01
        elif view == "front":
            self._camera.yaw = 0
            self._camera.pitch = 0
        elif view == "side":
            self._camera.yaw = math.pi / 2
            self._camera.pitch = 0
        self.update()

    def save_bookmark(self, index: int) -> None:

        self._save_bookmark(index)

    def recall_bookmark(self, index: int) -> None:

        self._recall_bookmark(index)
        
    def __del__(self):
        self._cleanup_all_gl_resources()
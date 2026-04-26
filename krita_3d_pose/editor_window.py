import os
from typing import Optional

from pose_engine.path_setup import ensure_path, get_parent_dir
ensure_path()

_parent_dir = get_parent_dir()

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSplitter, QMessageBox, QCheckBox,
    QTabWidget, QMainWindow, QAction, QShortcut, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QImage, QPainter, QKeySequence

try:
    from krita import Krita # type: ignore
    KRITA_AVAILABLE = True
except ImportError:
    KRITA_AVAILABLE = False

from pose_engine.logger import get_logger
logger = get_logger(__name__)

try:
    from pose_engine.pose_state import UndoRedoStack
    from pose_engine.ui.multi_viewport import MultiViewport3D
    from pose_engine.settings import PluginSettings
    from pose_engine.ui.settings_dialog import AdvancedSettingsDialog
    from pose_engine.ui.tabs import ModelsTab, BonesTab, PosesTab, CameraTab
    logger.info("Core imports successful")
except ImportError as e:
    logger.error(f"Import error: {e}")
    raise

try:
    from pose_engine.project_scene import ProjectScene
    from pose_engine.ui.scene_tab import SceneTab
    logger.info("Scene imports successful")
except ImportError as e:
    logger.warning(f"Scene import error: {e}")
    ProjectScene = None
    SceneTab = None


class PoseEditorWindow(QMainWindow):

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setWindowTitle("3D Pose Editor")
        self.setMinimumSize(1000, 700)

        self._settings = None
        if PluginSettings:
            try:
                self._settings = PluginSettings()
                self._settings.load()
            except Exception as e:
                logger.debug(f"[Editor] Failed to initialize settings: {e}")

        self._undo_stack = UndoRedoStack(max_history=100)

        self._setup_ui()
        self._setup_menubar()
        self._setup_statusbar()
        self._setup_shortcuts()

        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._on_update)
        self._update_timer.start(16) # ~60 FPS

        self._sync_timer = QTimer()
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(200)

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)

        self._tab_widget = QTabWidget()

        # Models tab
        self._models_tab = ModelsTab()
        self._tab_widget.addTab(self._wrap_in_scroll(self._models_tab), "Models")

        # Bones tab
        self._bones_tab = BonesTab()
        self._tab_widget.addTab(self._wrap_in_scroll(self._bones_tab), "Bones")

        # Poses tab
        self._poses_tab = PosesTab()
        self._tab_widget.addTab(self._wrap_in_scroll(self._poses_tab), "Poses")

        # Camera tab
        self._camera_tab = CameraTab(settings=self._settings)
        self._tab_widget.addTab(self._wrap_in_scroll(self._camera_tab), "Camera")

        # Scene tab
        logger.debug(f"[Editor] Adding Scene tab - SceneTab: {SceneTab is not None}, ProjectScene: {ProjectScene is not None}")
        self._scene_tab = None
        self._project_scene = None
        if SceneTab and ProjectScene:
            try:
                self._scene_tab = SceneTab()
                self._tab_widget.addTab(self._wrap_in_scroll(self._scene_tab), "Scene")
                self._scene_tab.reload_from_project_requested.connect(self._on_reload_from_project)
                logger.debug("[Editor] Scene tab added successfully")
            except Exception as e:
                logger.debug(f"[Editor] Failed to create scene tab: {e}")
                import traceback
                traceback.print_exc()
        else:
            logger.debug(f"[Editor] Skipping scene tab - SceneTab: {SceneTab is not None}, ProjectScene: {ProjectScene is not None}")

        left_layout.addWidget(self._tab_widget)

        #  Layer Sync 
        sync_group = QWidget()
        sync_layout = QVBoxLayout(sync_group)
        sync_layout.setContentsMargins(0, 0, 0, 0)

        sync_btn = QPushButton("Sync to Layer")
        sync_btn.clicked.connect(self._on_sync_to_layer)
        sync_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        sync_layout.addWidget(sync_btn)

        self._bounding_box_cb = QCheckBox("Show Bounding Box")
        self._bounding_box_cb.setToolTip(
            "Show which part of the viewport will be copied to the image layer"
        )
        self._bounding_box_cb.toggled.connect(self._on_bounding_box_toggle)
        sync_layout.addWidget(self._bounding_box_cb)

        left_layout.addWidget(sync_group)

        self._status_label = QLabel("No models loaded")
        left_layout.addWidget(self._status_label)

        # Viewport 
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)

        if MultiViewport3D:
            self._viewport = MultiViewport3D()
            splitter.addWidget(self._viewport)

            self._viewport.model_selected.connect(self._on_model_selected)
            self._viewport.bone_selected.connect(self._on_bone_selected)
            self._viewport.model_selection_changed.connect(self._on_model_selection_changed)
            self._viewport.sync_to_layer_requested.connect(self._on_sync_to_layer)
            self._viewport.camera_mode_changed.connect(self._on_camera_mode_changed)
            self._viewport.pose_changed.connect(self._on_pose_changed)

            if self._settings:
                self._viewport.set_settings(self._settings)

            # Wire viewport into all tabs
            self._models_tab.set_viewport(self._viewport)
            self._bones_tab.set_viewport(self._viewport)
            self._poses_tab.set_viewport(self._viewport)
            self._camera_tab.set_viewport(self._viewport)
        else:
            self._viewport = None
            placeholder = QLabel("OpenGL not available")
            placeholder.setAlignment(Qt.AlignCenter)
            splitter.addWidget(placeholder)

        splitter.setSizes([300, 700])
        layout.addWidget(splitter)

        # Wire tab signals 
        self._models_tab.model_tree_changed.connect(self._rebuild_model_tree)
        self._models_tab.bone_tree_changed.connect(self._rebuild_bone_tree)
        self._models_tab.status_message.connect(self._on_status_message)
        self._models_tab.scene_changed.connect(self._on_scene_changed)

        self._bones_tab.bone_tree_changed.connect(self._rebuild_bone_tree)
        self._bones_tab.status_message.connect(self._on_status_message)

        self._poses_tab.bone_tree_changed.connect(self._rebuild_bone_tree)
        self._poses_tab.status_message.connect(self._on_status_message)

        self._camera_tab.status_message.connect(self._on_status_message)

        self._initialize_project_scene()

    @staticmethod
    def _wrap_in_scroll(widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        return scroll

    # Project Scene

    def _initialize_project_scene(self) -> None:
        if not self._viewport or not ProjectScene:
            logger.debug(f"[ProjectScene] Skipping initialization - viewport: {self._viewport is not None}, ProjectScene: {ProjectScene is not None}")
            return

        scene = self._viewport.get_scene() if self._viewport else None
        if scene:
            self._project_scene = ProjectScene(scene)

            if self._scene_tab:
                self._scene_tab.set_project_scene(self._project_scene)

            self._project_scene.add_callback('pre_save', self._on_pre_save)
            self._project_scene.add_callback('scene_saved', self._on_scene_saved)
            self._project_scene.add_callback('scene_loaded', self._on_scene_loaded)
            self._project_scene.add_callback('bookmarks_loaded', self._on_bookmarks_loaded)

            logger.debug("[ProjectScene] Initialized successfully")

            self._try_autoload_scene()
        else:
            logger.debug("[ProjectScene] No scene available from viewport")

    def _try_autoload_scene(self) -> None:
        if not self._project_scene:
            return

        try:
            from krita import Krita # type: ignore
            app = Krita.instance()
            doc = app.activeDocument()

            if doc:
                doc_path = doc.fileName()
                if doc_path:
                    logger.debug(f"[ProjectScene] Found active document: {doc_path}")
                    if self._project_scene.load_for_krita_project(doc_path):
                        logger.debug("[ProjectScene] Auto-loaded scene for project")
                    else:
                        logger.debug("[ProjectScene] No existing scene for project, will create new on save")
                else:
                    logger.debug("[ProjectScene] Document has no file path (unsaved)")
            else:
                logger.debug("[ProjectScene] No active document")
        except Exception as e:
            logger.debug(f"[ProjectScene] Error during auto-load: {e}")

    def _on_pre_save(self, file_path: str) -> None:
        if self._viewport and self._project_scene:
            bookmarks = self._viewport.get_project_bookmarks()
            self._project_scene.pre_save_bookmarks_update(bookmarks)
            logger.debug(f"[Editor] Pre-save: captured {len(bookmarks)} camera bookmarks")

    def _on_scene_saved(self, file_path: str) -> None:
        if self._status_label:
            self._status_label.setText(f"Scene saved: {os.path.basename(file_path)}")

    def _on_scene_loaded(self, file_path: str) -> None:
        logger.debug(f"[Editor] Scene loaded: {file_path}")
        if self._status_label:
            self._status_label.setText(f"Scene loaded: {os.path.basename(file_path)}")

        if self._viewport:
            self._viewport.reload_scene()

        # Explicitly update poses for all models after scene load
        # This ensures the skeleton transforms are computed and GPU data is updated
        if self._project_scene and self._project_scene.scene:
            logger.debug("[Editor] Updating poses for all models after scene load")
            for model in self._project_scene.scene.get_all_models():
                if model.skeleton:
                    logger.debug(f"[Editor] Updating transforms for model: {model.name}")
                    model.skeleton.mark_all_dirty()
                    model.update_transforms()

        self._rebuild_model_tree()
        self._rebuild_bone_tree()

        if self._scene_tab:
            self._scene_tab._update_info()

    def _on_bookmarks_loaded(self, bookmarks: dict) -> None:
        logger.debug(f"[Editor] Loading {len(bookmarks)} camera bookmarks into viewport")
        if self._viewport:
            self._viewport.load_project_bookmarks(bookmarks)

    def _on_reload_from_project(self) -> None:
        if not self._project_scene:
            return

        logger.debug("[Editor] Clearing existing scene for reload")
        self._project_scene.new_scene()

        if self._viewport:
            self._viewport.clear_models()

        self._rebuild_model_tree()
        self._rebuild_bone_tree()

        self._try_autoload_scene()

    #  Menubar 

    def _setup_menubar(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")

        add_model_action = QAction("Add Model...", self)
        add_model_action.setShortcut("Ctrl+O")
        add_model_action.triggered.connect(self._on_add_model)
        file_menu.addAction(add_model_action)

        file_menu.addSeparator()

        load_pose_action = QAction("Load Pose...", self)
        load_pose_action.setShortcut("Ctrl+L")
        load_pose_action.triggered.connect(self._on_load_pose)
        file_menu.addAction(load_pose_action)

        save_pose_action = QAction("Save Pose...", self)
        save_pose_action.setShortcut("Ctrl+S")
        save_pose_action.triggered.connect(self._on_save_pose)
        file_menu.addAction(save_pose_action)

        file_menu.addSeparator()

        close_action = QAction("Close", self)
        close_action.setShortcut("Ctrl+W")
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)

        view_menu = menubar.addMenu("View")

        frame_action = QAction("Frame Model", self)
        frame_action.setShortcut("F")
        frame_action.triggered.connect(self._on_frame_model)
        view_menu.addAction(frame_action)

        reset_action = QAction("Reset Camera", self)
        reset_action.setShortcut("R")
        reset_action.triggered.connect(self._on_reset_camera)
        view_menu.addAction(reset_action)

        view_menu.addSeparator()

        top_action = QAction("Top View", self)
        top_action.triggered.connect(lambda: self._on_preset_view("top"))
        view_menu.addAction(top_action)

        front_action = QAction("Front View", self)
        front_action.triggered.connect(lambda: self._on_preset_view("front"))
        view_menu.addAction(front_action)

        settings_menu = menubar.addMenu("Settings")

        advanced_action = QAction("Advanced Settings...", self)
        advanced_action.triggered.connect(self._show_advanced_settings)
        settings_menu.addAction(advanced_action)

    def _setup_statusbar(self) -> None:
        self.statusBar().showMessage("Ready")

    def _setup_shortcuts(self) -> None:
        undo_sc = QShortcut(QKeySequence(Qt.ControlModifier | Qt.Key_Z), self)
        undo_sc.setContext(Qt.WindowShortcut)
        undo_sc.activated.connect(self._on_undo)

        redo_sc = QShortcut(
            QKeySequence(Qt.ControlModifier | Qt.ShiftModifier | Qt.Key_Z), self
        )
        redo_sc.setContext(Qt.WindowShortcut)
        redo_sc.activated.connect(self._on_redo)

        redo_alt_sc = QShortcut(QKeySequence(Qt.ControlModifier | Qt.Key_Y), self)
        redo_alt_sc.setContext(Qt.WindowShortcut)
        redo_alt_sc.activated.connect(self._on_redo)

    #  Undo / Redo 

    def _on_undo(self) -> None:
        if not self._viewport:
            return
        model = self._viewport.get_selected_model()
        if model and model.skeleton and self._undo_stack.can_undo:
            self._undo_stack.undo(model.skeleton)
            self._viewport.update()
            self.statusBar().showMessage("Undo")

    def _on_redo(self) -> None:
        if not self._viewport:
            return
        model = self._viewport.get_selected_model()
        if model and model.skeleton and self._undo_stack.can_redo:
            self._undo_stack.redo(model.skeleton)
            self._viewport.update()
            self.statusBar().showMessage("Redo")

    def _on_pose_changed(self) -> None:
        
        if not self._viewport:
            return
        model = self._viewport.get_selected_model()
        if model and model.skeleton:
            # Ensure undo stack is initialized for this skeleton
            if self._undo_stack._current_snapshot is None:
                self._undo_stack.initialize(model.skeleton)
            # Push current state to undo stack for future undo
            self._undo_stack.push_state(model.skeleton, "Pose Change")

        if self._project_scene:
            self._project_scene.mark_changed()


    def keyPressEvent(self, event) -> None:
        """Override key press to prevent Ctrl+W from closing the window."""
        if event.key() == Qt.Key_W and event.modifiers() & Qt.ControlModifier:
            event.accept()
            return
        super().keyPressEvent(event)

    #  Menu action delegates 

    def _on_add_model(self) -> None:
        self._models_tab._on_add_model()

    def _on_load_pose(self) -> None:
        self._poses_tab._on_load_pose()

    def _on_save_pose(self) -> None:
        self._poses_tab._on_save_pose()

    def _on_frame_model(self) -> None:
        self._camera_tab._on_frame_model()

    def _on_reset_camera(self) -> None:
        self._camera_tab._on_reset_camera()

    def _on_preset_view(self, view: str) -> None:
        self._camera_tab._on_preset_view(view)

    #  Viewport signal handlers 

    def _on_model_selected(self, model_id: str) -> None:
        self._rebuild_model_tree()
        self._rebuild_bone_tree()
        # Initialize undo stack for the newly selected model's skeleton
        if self._viewport:
            model = self._viewport.get_selected_model()
            if model and model.skeleton:
                self._undo_stack.initialize(model.skeleton)

    def _on_bone_selected(self, model_id: str, bone_name: str) -> None:
        self._rebuild_bone_tree()
        self._bones_tab.update_selected_bone_info(model_id, bone_name)
        if self._status_label:
            self._status_label.setText(f"Selected: {bone_name}")

    def _on_model_selection_changed(self, model_id: str) -> None:
        self._rebuild_model_tree()
        self._rebuild_bone_tree()
    
    def _on_camera_mode_changed(self, mode: str) -> None:
        
        print(f"[DEBUG] _on_camera_mode_changed called with mode: {mode}")
        print(f"[DEBUG] _camera_tab is: {self._camera_tab}")
        if self._camera_tab:
            print(f"[DEBUG] Calling sync_camera_mode_buttons with mode: {mode}")
            self._camera_tab.sync_camera_mode_buttons(mode)
            print("[DEBUG] sync_camera_mode_buttons completed")
    
    # Tree rebuilds (delegated to tabs)

    def _rebuild_model_tree(self) -> None:
        self._models_tab.rebuild_model_tree()

    def _rebuild_bone_tree(self) -> None:
        self._bones_tab.rebuild_bone_tree()

    #  Status / scene helpers 

    def _on_status_message(self, message: str) -> None:
        if self._status_label:
            self._status_label.setText(message)
        self.statusBar().showMessage(message)

    def _on_scene_changed(self) -> None:
        if self._project_scene:
            self._project_scene.mark_changed()

    #  Layer Sync 

    def _on_sync_to_layer(self) -> None:
        if not KRITA_AVAILABLE:
            self.statusBar().showMessage("Sync only available inside Krita")
            QMessageBox.information(self, "Sync", "Layer sync is only available when running inside Krita.")
            return

        if not self._viewport:
            self.statusBar().showMessage("No viewport available")
            return

        self.statusBar().showMessage("Syncing to layer...")
        self._do_sync()

    def _do_sync(self) -> None:
        if not KRITA_AVAILABLE or not self._viewport:
            return

        try:
            logger.debug("[SYNC] Starting layer sync process...")

            app = Krita.instance()
            doc = app.activeDocument()

            if not doc:
                logger.debug("[SYNC] ERROR: No active document")
                self.statusBar().showMessage("No active document")
                return

            doc_w = doc.width()
            doc_h = doc.height()
            logger.debug(f"[SYNC] Document size: {doc_w}x{doc_h}")

            if self._viewport:
                self._viewport.set_bounding_box_target(doc_w, doc_h)

            viewport_w = self._viewport.width()
            viewport_h = self._viewport.height()

            logger.debug(f"[SYNC] Viewport size: {viewport_w}x{viewport_h}")

            if viewport_w > 0 and viewport_h > 0:
                viewport_aspect = viewport_w / viewport_h
                doc_aspect = doc_w / doc_h

                logger.debug(f"[SYNC] Aspect ratios - viewport: {viewport_aspect:.3f}, document: {doc_aspect:.3f}")

                if viewport_aspect > doc_aspect:
                    render_h = doc_h
                    render_w = int(doc_h * viewport_aspect)
                    logger.debug(f"[SYNC] Fitting to document height: {render_w}x{render_h}")
                else:
                    render_w = doc_w
                    render_h = int(doc_w / viewport_aspect)
                    logger.debug(f"[SYNC] Fitting to document width: {render_w}x{render_h}")
            else:
                render_w, render_h = doc_w, doc_h
                logger.debug(f"[SYNC] Using document size directly: {render_w}x{render_h}")

            logger.debug(f"[SYNC] Calling render_to_image({render_w}, {render_h})...")
            img = self._viewport.render_to_image(render_w, render_h)

            if img.isNull():
                logger.debug("[SYNC] ERROR: Render returned null image")
                self.statusBar().showMessage("Render failed - null image")
                return

            logger.debug(f"[SYNC] Render successful: {img.width()}x{img.height()}")

            logger.debug("[SYNC] Converting image format...")
            img = img.convertToFormat(QImage.Format_ARGB32)

            if render_w != doc_w or render_h != doc_h:
                logger.debug(f"[SYNC] Creating centered image {doc_w}x{doc_h} from {render_w}x{render_h}")
                final_img = QImage(doc_w, doc_h, QImage.Format_ARGB32)
                final_img.fill(QColor(0, 0, 0, 0)) 

                offset_x = (doc_w - render_w) // 2
                offset_y = (doc_h - render_h) // 2
                logger.debug(f"[SYNC] Centering offset: ({offset_x}, {offset_y})")

                painter = QPainter(final_img)
                painter.drawImage(offset_x, offset_y, img)
                painter.end()

                img = final_img
                logger.debug("[SYNC] Centering complete")

            logger.debug("[SYNC] Finding or creating '3D View' layer...")
            root = doc.rootNode()
            layer_name = "3D View"

            existing = None
            child_count = 0
            for child in root.childNodes():
                child_count += 1
                logger.debug(f"[SYNC] Checking layer: '{child.name()}'")
                if child.name() == layer_name:
                    existing = child
                    logger.debug(f"[SYNC] Found existing layer: '{layer_name}'")
                    break

            logger.debug(f"[SYNC] Total layers found: {child_count}")

            if existing:
                logger.debug("[SYNC] Using existing layer")
                node = existing
            else:
                logger.debug(f"[SYNC] Creating new layer: '{layer_name}'")
                node = doc.createNode(layer_name, "paintlayer")
                root.addChildNode(node, None)
                logger.debug("[SYNC] Layer created and added to document")

            logger.debug(f"[SYNC] Setting pixel data ({img.byteCount()} bytes)...")
            ptr = img.bits()
            ptr.setsize(img.byteCount())
            node.setPixelData(bytes(ptr), 0, 0, doc_w, doc_h)

            logger.debug("[SYNC] Refreshing document projection...")
            doc.refreshProjection()

            logger.debug(f"[SYNC] SUCCESS! Synced {doc_w}x{doc_h} to layer")
            self.statusBar().showMessage(f"Synced {doc_w}x{doc_h} to layer")

        except Exception as e:
            logger.debug(f"[SYNC] ERROR: Exception during sync: {e}")
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(f"Sync failed: {e}")
            QMessageBox.critical(self, "Sync Error", f"Failed to sync to layer: {e}")

    def _on_bounding_box_toggle(self, checked: bool) -> None:
        if not self._viewport:
            return

        self._viewport.set_show_bounding_box(checked)

        if checked:
            doc_w, doc_h = 0, 0
            try:
                app = Krita.instance()
                doc = app.activeDocument()
                if doc:
                    doc_w = doc.width()
                    doc_h = doc.height()
            except Exception:
                pass

            if doc_w <= 0 or doc_h <= 0:
                doc_w = self._viewport.width()
                doc_h = self._viewport.height()

            if doc_w > 0 and doc_h > 0:
                self._viewport.set_bounding_box_target(doc_w, doc_h)

    #  Advanced Settings 

    def _show_advanced_settings(self) -> None:
        if AdvancedSettingsDialog and self._settings:
            dialog = AdvancedSettingsDialog(self._settings, self)
            dialog.settings_saved.connect(self._on_advanced_settings_saved)
            dialog.exec_()

    def _on_advanced_settings_saved(self) -> None:
        if self._viewport and self._settings:
            self._viewport.set_settings(self._settings)

    #  Lifecycle 

    def _on_update(self) -> None:
        """This is empty because there's nothing there"""
        pass

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()

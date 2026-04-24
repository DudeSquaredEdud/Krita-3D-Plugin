

from typing import Optional, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QCheckBox,
    QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from .labeled_slider import LabeledSlider

if TYPE_CHECKING:
    from ..multi_viewport import MultiViewport3D
    from ...settings import PluginSettings


class CameraTab(QWidget):
    status_message = pyqtSignal(str)

    def __init__(
        self,
        settings: Optional['PluginSettings'] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._viewport: Optional['MultiViewport3D'] = None
        self._settings = settings
        self._setup_ui()

    def set_viewport(self, viewport: 'MultiViewport3D') -> None:
        self._viewport = viewport

    def set_settings(self, settings: 'PluginSettings') -> None:
        self._settings = settings
        self._load_settings_into_sliders()

    def _setup_ui(self) -> None:
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        #  View Mode 
        view_mode_group = QGroupBox("View Mode")
        view_mode_layout = QHBoxLayout(view_mode_group)

        self._orbit_btn = QPushButton("Orbit")
        self._orbit_btn.setCheckable(True)
        self._orbit_btn.setChecked(True)
        self._orbit_btn.setToolTip("Camera orbits around target (QWEASD moves target)")
        self._orbit_btn.clicked.connect(lambda: self._set_camera_mode("orbit"))
        view_mode_layout.addWidget(self._orbit_btn)

        self._head_look_btn = QPushButton("Head Look")
        self._head_look_btn.setCheckable(True)
        self._head_look_btn.setToolTip("Camera rotates in place (QWEASD moves camera)")
        self._head_look_btn.clicked.connect(lambda: self._set_camera_mode("head_look"))
        view_mode_layout.addWidget(self._head_look_btn)

        layout.addWidget(view_mode_group)

        #  Field of View 
        fov_group = QGroupBox("Field of View")
        fov_layout = QHBoxLayout(fov_group)

        self._fov_slider = LabeledSlider(
            label="",
            range_min=30, range_max=120,
            default=45,
            scale=1.0,
            format_fn=lambda v: f"{v:.0f}°",
        )
        self._fov_slider.value_changed.connect(self._on_fov_changed)
        fov_layout.addWidget(self._fov_slider)

        layout.addWidget(fov_group)

        #  Movement Speed 
        speed_group = QGroupBox("Movement Speed")
        speed_layout = QHBoxLayout(speed_group)

        self._speed_slider = LabeledSlider(
            label="",
            range_min=1, range_max=100,
            default=50,
            scale=0.02,
            format_fn=lambda v: f"{v:.1f}x",
        )
        self._speed_slider.value_changed.connect(self._on_speed_changed)
        speed_layout.addWidget(self._speed_slider)

        layout.addWidget(speed_group)

        #  Quick Actions 
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout(actions_group)

        reset_btn = QPushButton("Reset")
        reset_btn.setToolTip("Reset camera to default")
        reset_btn.clicked.connect(self._on_reset_camera)
        actions_layout.addWidget(reset_btn)

        top_btn = QPushButton("Top")
        top_btn.setToolTip("View from top")
        top_btn.clicked.connect(lambda: self._on_preset_view("top"))
        actions_layout.addWidget(top_btn)

        front_btn = QPushButton("Front")
        front_btn.setToolTip("View from front")
        front_btn.clicked.connect(lambda: self._on_preset_view("front"))
        actions_layout.addWidget(front_btn)

        layout.addWidget(actions_group)

        #  Visual Effects 
        effects_group = QGroupBox("Visual Effects")
        effects_layout = QVBoxLayout(effects_group)

        self._distance_gradient_btn = QPushButton("Distance Gradient")
        self._distance_gradient_btn.setCheckable(True)
        self._distance_gradient_btn.setChecked(False)
        self._distance_gradient_btn.setToolTip(
            "Toggle distance-based color gradient overlay.\n"
            "Surfaces are tinted based on distance from camera:\n"
            "Near = Blue, Far = Magenta"
        )
        self._distance_gradient_btn.clicked.connect(
            lambda: self._on_distance_gradient_toggle(self._distance_gradient_btn.isChecked())
        )
        effects_layout.addWidget(self._distance_gradient_btn)

        distance_range = self._settings.gizmo.get('distance_gradient_range', 5.0) if self._settings else 5.0
        self._distance_range_slider = LabeledSlider(
            label="Distance:",
            range_min=10, range_max=500,
            default=int(distance_range * 100),
            scale=0.01,
            format_fn=lambda v: f"{v:.1f}",
            tooltip=(
                "Controls the distance range for the gradient effect.\n"
                "Lower = tighter gradient, Higher = wider gradient"
            ),
        )
        self._distance_range_slider.value_changed.connect(self._on_distance_range_changed)
        effects_layout.addWidget(self._distance_range_slider)

        layout.addWidget(effects_group)

        #  Display Scale 
        scale_group = QGroupBox("Display Scale")
        scale_layout = QVBoxLayout(scale_group)
        scale_layout.setSpacing(4)

        display_scale = self._settings.gizmo.get('display_scale', 0.15) if self._settings else 0.15
        self._gizmo_scale_slider = LabeledSlider(
            label="Gizmo:",
            range_min=1, range_max=100,
            default=int(display_scale * 100),
            scale=0.01,
            format_fn=lambda v: f"{v:.2f}",
            tooltip=(
                "Adjust gizmo display size.\n"
                "Independent of FOV - change zoom to resize proportionally."
            ),
        )
        self._gizmo_scale_slider.value_changed.connect(self._on_gizmo_scale_changed)
        scale_layout.addWidget(self._gizmo_scale_slider)

        joint_display_scale = self._settings.gizmo.get('joint_display_scale', 0.15) if self._settings else 0.15
        self._joint_scale_slider = LabeledSlider(
            label="Joints:",
            range_min=1, range_max=100,
            default=int(joint_display_scale * 100),
            scale=0.01,
            format_fn=lambda v: f"{v:.2f}",
            tooltip=(
                "Adjust joint display size.\n"
                "Independent of FOV - change zoom to resize proportionally."
            ),
        )
        self._joint_scale_slider.value_changed.connect(self._on_joint_scale_changed)
        scale_layout.addWidget(self._joint_scale_slider)

        layout.addWidget(scale_group)

        #  Camera Bookmarks 
        bookmarks_group = QGroupBox("Camera Bookmarks")
        bookmarks_layout = QVBoxLayout(bookmarks_group)

        help_label = QLabel("Ctrl+1-9: Save | 1-9: Recall")
        help_label.setStyleSheet("color: #888; font-size: 9px;")
        bookmarks_layout.addWidget(help_label)

        bookmark_grid = QHBoxLayout()
        self._bookmark_buttons = []
        for i in range(1, 10):
            btn = QPushButton(str(i))
            btn.setFixedSize(28, 28)
            btn.setToolTip(f"Bookmark {i}\nClick to recall, Ctrl+Click to save")
            btn.clicked.connect(lambda checked, idx=i: self._on_bookmark_click(idx))
            bookmark_grid.addWidget(btn)
            self._bookmark_buttons.append(btn)
        bookmarks_layout.addLayout(bookmark_grid)

        io_layout = QHBoxLayout()
        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self._on_import_bookmarks)
        io_layout.addWidget(import_btn)

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._on_export_bookmarks)
        io_layout.addWidget(export_btn)
        bookmarks_layout.addLayout(io_layout)

        layout.addWidget(bookmarks_group)

    #  Settings loading 

    def _load_settings_into_sliders(self) -> None:
        if not self._settings:
            return

        distance_range = self._settings.gizmo.get('distance_gradient_range', 5.0)
        self._distance_range_slider.set_value(distance_range, block_signals=True)

        display_scale = self._settings.gizmo.get('display_scale', 0.15)
        self._gizmo_scale_slider.set_value(display_scale, block_signals=True)

        joint_display_scale = self._settings.gizmo.get('joint_display_scale', 0.15)
        self._joint_scale_slider.set_value(joint_display_scale, block_signals=True)

    #  Camera mode 

    def _set_camera_mode(self, mode: str) -> None:
        self._orbit_btn.setChecked(mode == "orbit")
        self._head_look_btn.setChecked(mode == "head_look")

        if self._viewport:
            self._viewport.set_head_look_mode(mode == "head_look")

    def set_camera_mode(self, mode: str) -> None:
        self._set_camera_mode(mode)

    #  FOV / Speed 

    def _on_fov_changed(self, value: float) -> None:
        if self._viewport:
            self._viewport.set_fov(value)

    def _on_speed_changed(self, value: float) -> None:
        if self._settings:
            self._settings.camera.set('keyboard_movement_speed', value * 0.05)

    #  Quick actions 

    def _on_reset_camera(self) -> None:
        if self._viewport:
            self._viewport.reset_camera()
            self._viewport.frame_all()

    def _on_frame_model(self) -> None:
        if self._viewport:
            self._viewport.frame_all()

    def _on_preset_view(self, view: str) -> None:
        if self._viewport:
            self._viewport.set_preset_view(view)

    #  Visual effects 

    def _on_distance_gradient_toggle(self, checked: bool) -> None:
        if self._viewport:
            self._viewport.set_distance_gradient_enabled(checked)

    def _on_distance_range_changed(self, value: float) -> None:
        if self._viewport:
            self._viewport.set_distance_range(0.0, value)

    #  Display scale 

    def _on_gizmo_scale_changed(self, value: float) -> None:
        if self._settings:
            self._settings.gizmo.set('display_scale', value)
        if self._viewport:
            self._viewport.update()

    def _on_joint_scale_changed(self, value: float) -> None:
        if self._settings:
            self._settings.gizmo.set('joint_display_scale', value)
        if self._viewport:
            self._viewport.update()

    #  Camera bookmarks 

    def _on_bookmark_click(self, index: int) -> None:
        from PyQt5.QtWidgets import QApplication
        if QApplication.keyboardModifiers() & Qt.ControlModifier:
            if self._viewport:
                self._viewport.save_bookmark(index)
                self._update_bookmark_indicator(index, True)
        else:
            if self._viewport:
                self._viewport.recall_bookmark(index)

    def _update_bookmark_indicator(self, index: int, has_bookmark: bool) -> None:
        if 1 <= index <= 9 and hasattr(self, '_bookmark_buttons'):
            btn = self._bookmark_buttons[index - 1]
            if has_bookmark:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2a4a6a;
                        border: 2px solid #4a8aca;
                    }
                """)
            else:
                btn.setStyleSheet("")

    def _on_import_bookmarks(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import Camera Bookmarks",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if not filepath:
            return

        import_error_string = "Import Error"
        
        if not self._viewport:
            QMessageBox.warning(self, import_error_string, "No viewport available.")
            return

        manager = self._viewport.get_bookmark_manager()
        if not manager:
            QMessageBox.warning(self, import_error_string, "No bookmark manager available.")
            return

        from pathlib import Path
        count = manager.import_from_file(Path(filepath))
        if count < 0:
            QMessageBox.warning(self, import_error_string, "Failed to import bookmarks from file.")
        else:
            for i in range(1, 10):
                self._update_bookmark_indicator(i, manager.has_bookmark(i))
            QMessageBox.information(self, "Import Successful", f"Imported {count} bookmark(s).")

    def _on_export_bookmarks(self) -> None:
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Camera Bookmarks",
            "camera_bookmarks.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if not filepath:
            return

        export_error_string = "Export Error"

        if not self._viewport:
            QMessageBox.warning(self, export_error_string, "No viewport available.")
            return

        manager = self._viewport.get_bookmark_manager()
        if not manager:
            QMessageBox.warning(self, export_error_string, "No bookmark manager available.")
            return

        from pathlib import Path
        if manager.export_to_file(Path(filepath)):
            QMessageBox.information(self, "Export Successful", f"Bookmarks exported to:\n{filepath}")
        else:
            QMessageBox.warning(self, export_error_string, "Failed to export bookmarks to file.")

    #  External sync 

    def set_fov_slider(self, fov: float) -> None:
        
        self._fov_slider.set_value(fov, block_signals=True)

    def sync_camera_mode_buttons(self, mode: str) -> None:
        
        self._orbit_btn.setChecked(mode == "orbit")
        self._head_look_btn.setChecked(mode == "head_look")

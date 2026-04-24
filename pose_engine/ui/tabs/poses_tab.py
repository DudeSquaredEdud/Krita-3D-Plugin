

import os
from typing import Optional, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal

from ...path_setup import get_parent_dir, get_user_data_dir

if TYPE_CHECKING:
    from ..multi_viewport import MultiViewport3D


class PosesTab(QWidget):


    bone_tree_changed = pyqtSignal()
    status_message = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._viewport: Optional['MultiViewport3D'] = None
        self._parent_dir = get_parent_dir()
        self._user_poses_dir = get_user_data_dir()
        self._setup_ui()
        self._refresh_pose_list()

    def set_viewport(self, viewport: 'MultiViewport3D') -> None:

        self._viewport = viewport

    def _setup_ui(self) -> None:

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        poses_group = QGroupBox("Poses")
        poses_layout = QVBoxLayout(poses_group)

        pose_btn_layout = QHBoxLayout()

        load_pose_btn = QPushButton("Load")
        load_pose_btn.clicked.connect(self._on_load_pose)
        pose_btn_layout.addWidget(load_pose_btn)

        save_pose_btn = QPushButton("Save")
        save_pose_btn.clicked.connect(self._on_save_pose)
        pose_btn_layout.addWidget(save_pose_btn)

        poses_layout.addLayout(pose_btn_layout)

        self._pose_list = QListWidget()
        self._pose_list.setMaximumHeight(150)
        self._pose_list.itemDoubleClicked.connect(self._on_pose_double_clicked)
        poses_layout.addWidget(self._pose_list)

        apply_pose_btn = QPushButton("Apply")
        apply_pose_btn.clicked.connect(self._on_apply_pose)
        poses_layout.addWidget(apply_pose_btn)

        layout.addWidget(poses_group)

    # Pose actions

    def _on_load_pose(self) -> None:

        if not self._viewport:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Pose",
            self._user_poses_dir,
            "JSON Pose Files (*.json);;All Files (*)"
        )

        if file_path:
            self._apply_pose_file(file_path, self._viewport.get_selected_model())

    def _on_save_pose(self) -> None:

        if not self._viewport:
            return

        default_path = os.path.join(self._user_poses_dir, "untitled_pose.json")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Pose",
            default_path,
            "JSON Pose Files (*.json);;All Files (*)"
        )

        if file_path:
            if not file_path.endswith('.json'):
                file_path += '.json'
            model = self._viewport.get_selected_model()
            if model:
                try:
                    from ...pose_state import PoseSerializer
                    PoseSerializer.save_pose(file_path, model.skeleton)
                    self._refresh_pose_list()
                    self.status_message.emit(f"Pose saved: {os.path.basename(file_path)}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to save pose: {e}")
            else:
                QMessageBox.warning(self, "No Model Selected", "Select a model before saving a pose.")

    def _on_apply_pose(self) -> None:

        if not self._viewport:
            return

        item = self._pose_list.currentItem()
        if item:
            file_path = item.data(Qt.UserRole)
            model = self._viewport.get_selected_model()
            if model:
                self._apply_pose_file(file_path, model)

    def _on_pose_double_clicked(self, item: QListWidgetItem) -> None:

        self._on_apply_pose()

    def _apply_pose_file(self, file_path: str, model) -> None:

        if model:
            try:
                from ...pose_state import PoseSerializer
                PoseSerializer.load_pose(file_path, model.skeleton)
                self.bone_tree_changed.emit()
                if self._viewport:
                    self._viewport.update()
                self.status_message.emit(f"Applied pose: {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load pose: {e}")

    # Pose list

    def _refresh_pose_list(self) -> None:

        self._pose_list.clear()

        seen_names = set()

        bundled_dir = os.path.join(self._parent_dir, "poses")
        if os.path.exists(bundled_dir):
            for filename in sorted(os.listdir(bundled_dir)):
                if filename.endswith(".json"):
                    pose_name = os.path.splitext(filename)[0]
                    file_path = os.path.join(bundled_dir, filename)
                    item = QListWidgetItem(f"[builtin] {pose_name}")
                    item.setData(Qt.UserRole, file_path)
                    item.setData(Qt.UserRole + 1, "bundled")
                    self._pose_list.addItem(item)
                    seen_names.add(pose_name)

        if os.path.exists(self._user_poses_dir):
            for filename in sorted(os.listdir(self._user_poses_dir)):
                if filename.endswith(".json"):
                    pose_name = os.path.splitext(filename)[0]
                    file_path = os.path.join(self._user_poses_dir, filename)
                    display_name = pose_name if pose_name not in seen_names else f"{pose_name} (user)"
                    item = QListWidgetItem(display_name)
                    item.setData(Qt.UserRole, file_path)
                    item.setData(Qt.UserRole + 1, "user")
                    self._pose_list.addItem(item)

    def refresh_pose_list(self) -> None:

        self._refresh_pose_list()

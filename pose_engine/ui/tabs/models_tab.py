

from typing import Optional, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QTreeWidget, QTreeWidgetItem, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from ..styles import Colors

if TYPE_CHECKING:
    from ..multi_viewport import MultiViewport3D


class ModelsTab(QWidget):


    model_tree_changed = pyqtSignal()
    bone_tree_changed = pyqtSignal()
    status_message = pyqtSignal(str)
    scene_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._viewport: Optional['MultiViewport3D'] = None
        self._setup_ui()

    def set_viewport(self, viewport: 'MultiViewport3D') -> None:
        
        self._viewport = viewport

    def _setup_ui(self) -> None:
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        models_group = QGroupBox("Models")
        models_layout = QVBoxLayout(models_group)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._on_add_model)
        btn_layout.addWidget(add_btn)

        dup_btn = QPushButton("Duplicate")
        dup_btn.clicked.connect(self._on_duplicate_model)
        btn_layout.addWidget(dup_btn)

        rem_btn = QPushButton("Remove")
        rem_btn.clicked.connect(self._on_remove_model)
        btn_layout.addWidget(rem_btn)

        models_layout.addLayout(btn_layout)

        self._model_tree = QTreeWidget()
        self._model_tree.setHeaderLabels(["Models"])
        self._model_tree.itemClicked.connect(self._on_model_tree_click)
        self._model_tree.setMaximumHeight(120)
        models_layout.addWidget(self._model_tree)

        layout.addWidget(models_group)

        vis_group = QGroupBox("Visibility")
        vis_layout = QVBoxLayout(vis_group)

        self._show_mesh_cb = QCheckBox("Mesh")
        self._show_mesh_cb.setChecked(True)
        self._show_mesh_cb.toggled.connect(self._on_toggle_mesh)
        vis_layout.addWidget(self._show_mesh_cb)

        self._show_skeleton_cb = QCheckBox("Skeleton")
        self._show_skeleton_cb.setChecked(True)
        self._show_skeleton_cb.toggled.connect(self._on_toggle_skeleton)
        vis_layout.addWidget(self._show_skeleton_cb)

        self._show_joints_cb = QCheckBox("Joints")
        self._show_joints_cb.setChecked(True)
        self._show_joints_cb.toggled.connect(self._on_toggle_joints)
        vis_layout.addWidget(self._show_joints_cb)

        self._show_gizmo_cb = QCheckBox("Gizmo")
        self._show_gizmo_cb.setChecked(True)
        self._show_gizmo_cb.toggled.connect(self._on_toggle_gizmo)
        vis_layout.addWidget(self._show_gizmo_cb)

        layout.addWidget(vis_group)

    #  Model actions 

    def _on_add_model(self) -> None:
        
        from PyQt5.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Add 3D Model",
            "",
            "GLB Files (*.glb);;GLTF Files (*.gltf);;All Files (*)"
        )
        if file_path:
            self._add_model(file_path)

    def _add_model(self, file_path: str) -> None:
        
        if not self._viewport:
            return

        import os
        name = os.path.splitext(os.path.basename(file_path))[0]

        try:
            from PyQt5.QtWidgets import QMessageBox
            model = self._viewport.add_model(file_path, name)

            if model:
                self._refresh_after_model_change(f"Loaded: {name} ({model.get_bone_count()} bones)")
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to load model: {e}")

    def _on_duplicate_model(self) -> None:
        
        if not self._viewport:
            return

        model = self._viewport.get_selected_model()
        if model:
            copy = self._viewport.duplicate_model(model.id)
            if copy:
                self._refresh_after_model_change(f"Duplicated: {copy.name}")

    def _on_remove_model(self) -> None:
        
        if not self._viewport:
            return

        model = self._viewport.get_selected_model()
        if model:
            self._viewport.remove_model(model.id)
            self._refresh_after_model_change(f"Removed: {model.name}")

    def _refresh_after_model_change(self, message: str) -> None:
        
        self.rebuild_model_tree()
        self.model_tree_changed.emit()
        self.bone_tree_changed.emit()
        self.status_message.emit(message)
        self.scene_changed.emit()

    #  Model tree 

    def rebuild_model_tree(self) -> None:
        
        if not self._viewport:
            return

        self._model_tree.clear()

        selected_model_id = self._viewport.get_scene().get_selected_model_id()

        scene = self._viewport.get_scene()
        for model in scene.get_all_models():
            item = QTreeWidgetItem([model.name])
            item.setData(0, Qt.UserRole, model.id)
            item.setCheckState(0, Qt.Checked if model.visible else Qt.Unchecked)

            if model.id == selected_model_id:
                item.setBackground(0, QColor(100, 150, 200, 100))
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)

            self._model_tree.addTopLevelItem(item)

        self._model_tree.expandAll()

    def _on_model_tree_click(self, item: QTreeWidgetItem, column: int) -> None:
        
        if not self._viewport:
            return

        model_id = item.data(0, Qt.UserRole)

        if item.checkState(0) == Qt.Checked:
            self._viewport.set_model_visible(model_id, True)
        else:
            self._viewport.set_model_visible(model_id, False)

        self._viewport.select_model(model_id)
        self.rebuild_model_tree()
        self.bone_tree_changed.emit()

    #  Visibility toggles 

    def _on_toggle_mesh(self, checked: bool) -> None:
        if self._viewport:
            self._viewport.set_show_mesh(checked)

    def _on_toggle_skeleton(self, checked: bool) -> None:
        if self._viewport:
            self._viewport.set_show_skeleton(checked)

    def _on_toggle_joints(self, checked: bool) -> None:
        if self._viewport:
            self._viewport.set_show_joints(checked)

    def _on_toggle_gizmo(self, checked: bool) -> None:
        if self._viewport:
            self._viewport.set_show_gizmo(checked)

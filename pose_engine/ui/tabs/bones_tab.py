

from typing import Optional, Set, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QTreeWidget, QTreeWidgetItem, QLabel,
    QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from ..styles import Colors

if TYPE_CHECKING:
    from ..multi_viewport import MultiViewport3D


class BonesTab(QWidget):

    bone_tree_changed = pyqtSignal()
    status_message = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._viewport: Optional['MultiViewport3D'] = None
        self._setup_ui()

    def set_viewport(self, viewport: 'MultiViewport3D') -> None:

        self._viewport = viewport

    def _setup_ui(self) -> None:

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Selected Joint Info
        info_group = QGroupBox("Selected Joint")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(2)

        self._selected_name_label = QLabel("None")
        self._selected_name_label.setStyleSheet(f"font-weight: bold; color: {Colors.BONE_SELECTED};")
        info_layout.addWidget(self._selected_name_label)

        self._selected_pos_label = QLabel("")
        self._selected_pos_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 9px;")
        info_layout.addWidget(self._selected_pos_label)

        self._selected_parent_label = QLabel("")
        self._selected_parent_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 9px;")
        info_layout.addWidget(self._selected_parent_label)

        self._selected_depth_label = QLabel("")
        self._selected_depth_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 9px;")
        info_layout.addWidget(self._selected_depth_label)

        layout.addWidget(info_group)

        # Bone tree
        bone_group = QGroupBox("Bones")
        bone_layout = QVBoxLayout(bone_group)

        vis_layout = QHBoxLayout()
        self._show_all_btn = QPushButton("Show All")
        self._show_all_btn.clicked.connect(self._on_show_all)
        vis_layout.addWidget(self._show_all_btn)

        self._hide_all_btn = QPushButton("Hide All")
        self._hide_all_btn.clicked.connect(self._on_hide_all)
        vis_layout.addWidget(self._hide_all_btn)

        bone_layout.addLayout(vis_layout)

        self._bone_tree = QTreeWidget()
        self._bone_tree.setHeaderLabels(["Bone Hierarchy"])
        self._bone_tree.itemClicked.connect(self._on_bone_tree_click)
        self._bone_tree.itemChanged.connect(self._on_bone_tree_item_changed)
        self._bone_tree.setMaximumHeight(150)
        bone_layout.addWidget(self._bone_tree)

        layout.addWidget(bone_group)

        gizmo_group = QGroupBox("Gizmo Mode")
        gizmo_layout = QVBoxLayout(gizmo_group)

        mode_layout = QHBoxLayout()

        self._rotation_btn = QPushButton("Rotate")
        self._rotation_btn.setCheckable(True)
        self._rotation_btn.setChecked(True)
        self._rotation_btn.clicked.connect(lambda: self._set_gizmo_mode("rotation"))
        mode_layout.addWidget(self._rotation_btn)

        self._movement_btn = QPushButton("Move")
        self._movement_btn.setCheckable(True)
        self._movement_btn.clicked.connect(lambda: self._set_gizmo_mode("movement"))
        mode_layout.addWidget(self._movement_btn)

        self._scale_btn = QPushButton("Scale")
        self._scale_btn.setCheckable(True)
        self._scale_btn.clicked.connect(lambda: self._set_gizmo_mode("scale"))
        mode_layout.addWidget(self._scale_btn)

        gizmo_layout.addLayout(mode_layout)

        toggle_btn = QPushButton("Toggle (G)")
        toggle_btn.clicked.connect(self._toggle_gizmo_mode)
        gizmo_layout.addWidget(toggle_btn)

        space_layout = QHBoxLayout()
        self._world_btn = QPushButton("World")
        self._world_btn.setCheckable(True)
        self._world_btn.setChecked(True)
        self._world_btn.clicked.connect(lambda: self._set_gizmo_transform_space("world"))
        space_layout.addWidget(self._world_btn)

        self._local_btn = QPushButton("Local")
        self._local_btn.setCheckable(True)
        self._local_btn.clicked.connect(lambda: self._set_gizmo_transform_space("local"))
        space_layout.addWidget(self._local_btn)

        gizmo_layout.addLayout(space_layout)

        space_toggle_btn = QPushButton("Toggle Space (X)")
        space_toggle_btn.clicked.connect(self._toggle_gizmo_transform_space)
        gizmo_layout.addWidget(space_toggle_btn)

        layout.addWidget(gizmo_group)

    # Selected joint info

    def update_selected_bone_info(self, model_id: str, bone_name: str) -> None:

        self._selected_name_label.setText(bone_name if bone_name else "None")

        if not self._viewport or not bone_name:
            self._selected_pos_label.setText("")
            self._selected_parent_label.setText("")
            self._selected_depth_label.setText("")
            return

        model = self._viewport.get_scene().get_model(model_id)
        if not model or not model.skeleton:
            return

        bone = model.skeleton.get_bone(bone_name)
        if not bone:
            return

        pos = bone.get_world_position()
        self._selected_pos_label.setText(f"Pos: ({pos.x:.2f}, {pos.y:.2f}, {pos.z:.2f})")

        parent_name = bone.parent.name if bone.parent else "(root)"
        self._selected_parent_label.setText(f"Parent: {parent_name}")

        self._selected_depth_label.setText(f"Depth: {bone.get_depth()}")

    # Gizmo mode

    def _set_gizmo_mode(self, mode: str) -> None:

        if self._viewport:
            self._viewport.set_gizmo_mode(mode)

        self._rotation_btn.setChecked(mode == "rotation")
        self._movement_btn.setChecked(mode == "movement")
        self._scale_btn.setChecked(mode == "scale")

    def _toggle_gizmo_mode(self) -> None:

        if self._viewport:
            self._viewport.toggle_gizmo_mode()
            mode = self._viewport.get_gizmo_mode()
            self._rotation_btn.setChecked(mode == "rotation")
            self._movement_btn.setChecked(mode == "movement")
            self._scale_btn.setChecked(mode == "scale")

    def _set_gizmo_transform_space(self, space: str) -> None:

        if self._viewport:
            self._viewport.set_gizmo_transform_space(space)

        self._world_btn.setChecked(space == "world")
        self._local_btn.setChecked(space == "local")

    def _toggle_gizmo_transform_space(self) -> None:

        if self._viewport:
            self._viewport.toggle_gizmo_transform_space()
            space = self._viewport.get_gizmo_transform_space()
            self._world_btn.setChecked(space == "world")
            self._local_btn.setChecked(space == "local")

    def sync_gizmo_buttons(self) -> None:

        if self._viewport:
            mode = self._viewport.get_gizmo_mode()
            self._rotation_btn.setChecked(mode == "rotation")
            self._movement_btn.setChecked(mode == "movement")
            self._scale_btn.setChecked(mode == "scale")
            space = self._viewport.get_gizmo_transform_space()
            self._world_btn.setChecked(space == "world")
            self._local_btn.setChecked(space == "local")

    # Bone tree

    def rebuild_bone_tree(self) -> None:

        if not self._viewport:
            return

        self._bone_tree.blockSignals(True)

        expanded_items = self._collect_expanded_items()

        self._bone_tree.clear()

        selected_model_id = self._viewport.get_scene().get_selected_model_id()
        selected_bone_name = self._viewport.get_scene().get_selected_bone_name()

        scene = self._viewport.get_scene()
        for model in scene.get_all_models():
            model_item = QTreeWidgetItem([model.name])
            model_item.setData(0, Qt.UserRole, f"model:{model.id}")

            if model.id == selected_model_id:
                model_item.setBackground(0, QColor(100, 150, 200, 100))
                font = model_item.font(0)
                font.setBold(True)
                model_item.setFont(0, font)

            if model.skeleton:
                for bone in model.skeleton.get_root_bones():
                    self._add_bone_to_tree(bone, model_item, model.id, selected_model_id, selected_bone_name)

            self._bone_tree.addTopLevelItem(model_item)

            self._restore_expansion_state(model_item, expanded_items)

        # Expand model items that were previously expanded
        for i in range(self._bone_tree.topLevelItemCount()):
            item = self._bone_tree.topLevelItem(i)
            item_key = item.data(0, Qt.UserRole)
            if item_key in expanded_items:
                item.setExpanded(True)

        self._bone_tree.blockSignals(False)

        # Scroll to and highlight the selected bone
        if selected_model_id and selected_bone_name:
            self._highlight_and_scroll_to_bone(selected_model_id, selected_bone_name)

    def _highlight_and_scroll_to_bone(self, model_id: str, bone_name: str) -> None:

        target_key = f"bone:{model_id}:{bone_name}"
        item = self._find_tree_item_by_key(target_key)
        if item:
            self._bone_tree.setCurrentItem(item)
            self._bone_tree.scrollToItem(item, QAbstractItemView.EnsureVisible)

    def _find_tree_item_by_key(self, key: str, parent: Optional[QTreeWidgetItem] = None) -> Optional[QTreeWidgetItem]:

        root = self._bone_tree if parent is None else parent
        if parent is None:
            for i in range(root.topLevelItemCount()):
                result = self._find_tree_item_by_key(key, root.topLevelItem(i))
                if result:
                    return result
        else:
            if root.data(0, Qt.UserRole) == key:
                return root
            for i in range(root.childCount()):
                result = self._find_tree_item_by_key(key, root.child(i))
                if result:
                    return result
        return None

    def _collect_expanded_items(self) -> Set[str]:

        expanded: Set[str] = set()
        for i in range(self._bone_tree.topLevelItemCount()):
            self._collect_expanded_recursive(self._bone_tree.topLevelItem(i), expanded)
        return expanded

    def _collect_expanded_recursive(self, item: QTreeWidgetItem, expanded: Set[str]) -> None:

        if item.isExpanded():
            expanded.add(item.data(0, Qt.UserRole))
        for i in range(item.childCount()):
            self._collect_expanded_recursive(item.child(i), expanded)

    def _restore_expansion_state(self, parent_item: QTreeWidgetItem, expanded: Set[str]) -> None:

        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child_key = child.data(0, Qt.UserRole)
            if child_key in expanded:
                child.setExpanded(True)
            self._restore_expansion_state(child, expanded)

    def _add_bone_to_tree(self, bone, parent_item: QTreeWidgetItem, model_id: str,
                          selected_model_id: Optional[str], selected_bone_name: Optional[str]) -> None:

        item = QTreeWidgetItem([bone.name])
        item.setData(0, Qt.UserRole, f"bone:{model_id}:{bone.name}")
        item.setCheckState(0, Qt.Checked if bone.visible else Qt.Unchecked)

        if model_id == selected_model_id and bone.name == selected_bone_name:
            item.setBackground(0, QColor(Colors.BONE_SELECTED))
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)

        parent_item.addChild(item)

        for child in bone.children:
            self._add_bone_to_tree(child, item, model_id, selected_model_id, selected_bone_name)

    def _on_bone_tree_click(self, item: QTreeWidgetItem, column: int) -> None:

        if not self._viewport:
            return

        data = item.data(0, Qt.UserRole)
        if data and data.startswith("bone:"):
            parts = data.split(":")
            model_id = parts[1]
            bone_name = parts[2]
            self._viewport.select_bone(model_id, bone_name)
            self.update_selected_bone_info(model_id, bone_name)
            self.rebuild_bone_tree()

    def _on_bone_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:

        if not self._viewport:
            return

        data = item.data(0, Qt.UserRole)
        if not data or not data.startswith("bone:"):
            return

        parts = data.split(":")
        model_id = parts[1]
        bone_name = parts[2]

        model = self._viewport.get_scene().get_model(model_id)
        if not model or not model.skeleton:
            return

        visible = item.checkState(0) == Qt.Checked
        model.skeleton.set_bone_visible(bone_name, visible, cascade=True)

        self._bone_tree.blockSignals(True)
        self._cascade_check_state(item, visible)
        self._bone_tree.blockSignals(False)

        self._viewport.update()

    def _cascade_check_state(self, parent_item: QTreeWidgetItem, checked: bool) -> None:
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child.setCheckState(0, state)
            self._cascade_check_state(child, checked)

    # Visibility group toggles

    def _on_show_all(self) -> None:

        if not self._viewport:
            return

        scene = self._viewport.get_scene()
        selected_model_id = scene.get_selected_model_id()
        model = scene.get_model(selected_model_id) if selected_model_id else None
        if model and model.skeleton:
            for bone in model.skeleton:
                bone.visible = True
            self.rebuild_bone_tree()
            self._viewport.update()

    def _on_hide_all(self) -> None:

        if not self._viewport:
            return

        scene = self._viewport.get_scene()
        selected_model_id = scene.get_selected_model_id()
        model = scene.get_model(selected_model_id) if selected_model_id else None
        if model and model.skeleton:
            for bone in model.skeleton:
                bone.visible = False
            self.rebuild_bone_tree()
            self._viewport.update()

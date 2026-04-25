


from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal

from pose_engine.ui.settings.key_binding_editor import KeyBindingEditor

from ...settings import PluginSettings
from ...settings.defaults import (
    KEYBOARD_ACTION_NAMES,
)


class KeyboardSettingsWidget(QWidget):
    
    
    bindings_changed = pyqtSignal()
    
    def __init__(self, settings: PluginSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._setup_ui()
        self._load_bindings()
    
    def _setup_ui(self) -> None:
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        instructions = QLabel("Double-click a row to edit the key binding")
        instructions.setStyleSheet("color: #BDC3C7; font-style: italic;")
        layout.addWidget(instructions)
        
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Action", "Key", "Modifiers", ""])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.doubleClicked.connect(self._on_double_click)
        self._table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #4A6572;
                gridline-color: #4A6572;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #34495E;
                padding: 5px;
                border: 1px solid #4A6572;
            }
        """)
        layout.addWidget(self._table)
        
        btn_layout = QHBoxLayout()
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        btn_layout.addWidget(reset_btn)
        
        btn_layout.addStretch()
        
        check_btn = QPushButton("Check Conflicts")
        check_btn.clicked.connect(self._check_conflicts)
        btn_layout.addWidget(check_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_bindings(self) -> None:
        
        bindings = self._settings.keyboard.get_all_bindings()
        self._table.setRowCount(len(bindings))
        
        for row, (action, binding) in enumerate(bindings.items()):
            action_item = QTableWidgetItem(KEYBOARD_ACTION_NAMES.get(action, action))
            action_item.setData(Qt.UserRole, action)
            self._table.setItem(row, 0, action_item)
            
            key_item = QTableWidgetItem(binding.get_key_name())
            self._table.setItem(row, 1, key_item)
            
            mod_names = binding.get_modifier_names()
            mod_item = QTableWidgetItem('+'.join(mod_names) if mod_names else "None")
            self._table.setItem(row, 2, mod_item)
            
            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet("padding: 4px 8px;")
            edit_btn.clicked.connect(lambda checked, a=action: self._edit_binding(a))
            self._table.setCellWidget(row, 3, edit_btn)
    
    def _on_double_click(self, index) -> None:
        
        row = index.row()
        action_item = self._table.item(row, 0)
        if action_item:
            action = action_item.data(Qt.UserRole)
            self._edit_binding(action)
    
    def _edit_binding(self, action: str) -> None:
        
        current = self._settings.keyboard.get_binding(action)
        
        editor = KeyBindingEditor(action, current, self)
        if editor.exec_() == QDialog.Accepted:
            new_binding = editor.get_binding()
            if new_binding:
                self._settings.keyboard.set_binding_from_keybinding(action, new_binding)
                self._load_bindings()
                self.bindings_changed.emit()
    
    def _reset_to_defaults(self) -> None:
        
        reply = QMessageBox.question(
            self, "Reset Key Bindings",
            "Are you sure you want to reset all key bindings to defaults?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._settings.keyboard.reset_to_defaults()
            self._load_bindings()
            self.bindings_changed.emit()
    
    def _check_conflicts(self) -> None:
        
        conflicts = self._settings.keyboard.find_conflicts()
        
        if not conflicts:
            QMessageBox.information(self, "No Conflicts", "No key binding conflicts found.")
            return
        
        msg_lines = ["The following key bindings conflict:"]
        for action1, action2, binding in conflicts:
            msg_lines.append(f"\n• {KEYBOARD_ACTION_NAMES.get(action1, action1)}")
            msg_lines.append(f"  and {KEYBOARD_ACTION_NAMES.get(action2, action2)}")
            msg_lines.append(f"  both use: {binding.get_display_string()}")
        
        QMessageBox.warning(self, "Key Binding Conflicts", '\n'.join(msg_lines))


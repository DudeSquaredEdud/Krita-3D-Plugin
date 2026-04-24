

from typing import Callable, Optional

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QSlider, QLabel
from PyQt5.QtCore import Qt, pyqtSignal


class LabeledSlider(QWidget):

    value_changed = pyqtSignal(float)

    def __init__(
        self,
        label: str,
        range_min: int,
        range_max: int,
        default: int,
        scale: float = 1.0,
        format_fn: Optional[Callable[[float], str]] = None,
        tooltip: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:

        super().__init__(parent)
        self._scale = scale
        self._format_fn = format_fn or (lambda v: f"{v:.2f}")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(label)
        self._label.setMinimumWidth(40)
        layout.addWidget(self._label)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(range_min, range_max)
        self._slider.setValue(default)
        if tooltip:
            self._slider.setToolTip(tooltip)
        self._slider.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self._slider)

        self._value_label = QLabel(self._format_fn(default * scale))
        self._value_label.setMinimumWidth(30)
        self._value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._value_label)

    def _on_value_changed(self, raw_value: int) -> None:
        
        value = raw_value * self._scale
        self._value_label.setText(self._format_fn(value))
        self.value_changed.emit(value)

    def value(self) -> float:
        
        return self._slider.value() * self._scale

    def set_value(self, float_value: float, block_signals: bool = False) -> None:

        int_value = int(float_value / self._scale)
        if block_signals:
            self._slider.blockSignals(True)
        self._slider.setValue(int_value)
        self._value_label.setText(self._format_fn(float_value))
        if block_signals:
            self._slider.blockSignals(False)

    def slider(self) -> QSlider:
        
        return self._slider

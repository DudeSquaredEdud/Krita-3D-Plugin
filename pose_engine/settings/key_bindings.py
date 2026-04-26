

from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple, Any
from PyQt5.QtCore import Qt


@dataclass
class KeyBinding:

    key: int
    modifiers: int = Qt.NoModifier
    action: str = ""
    
    def __post_init__(self):

        if not isinstance(self.key, int) or self.key < 0:
            raise ValueError(f"Invalid key value: {self.key}")

        # Convert to int to handle both int and Qt.KeyboardModifiers types
        valid_modifiers = int(
            Qt.NoModifier |
            Qt.ShiftModifier |
            Qt.ControlModifier |
            Qt.AltModifier |
            Qt.MetaModifier |
            Qt.KeypadModifier |
            Qt.GroupSwitchModifier
        )
        self.modifiers = int(self.modifiers) & valid_modifiers
    
    def matches(self, key: int, modifiers: int) -> bool:
        return self.key == key and self.modifiers == modifiers
    
    def to_dict(self) -> Dict[str, Any]:
        
        return {
            'key': self.key,
            'modifiers': int(self.modifiers),  # Convert to int for JSON serialization
            'action': self.action
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KeyBinding':
        
        return cls(
            key=data.get('key', 0),
            modifiers=data.get('modifiers', Qt.NoModifier),
            action=data.get('action', '')
        )
    
    def get_key_name(self) -> str:
        
        key_names = {
            Qt.Key_Escape: 'Esc',
            Qt.Key_Tab: 'Tab',
            Qt.Key_Backtab: 'Shift+Tab',
            Qt.Key_Backspace: 'Backspace',
            Qt.Key_Return: 'Return',
            Qt.Key_Enter: 'Enter',
            Qt.Key_Insert: 'Insert',
            Qt.Key_Delete: 'Delete',
            Qt.Key_Pause: 'Pause',
            Qt.Key_Print: 'Print',
            Qt.Key_SysReq: 'SysReq',
            Qt.Key_Clear: 'Clear',
            Qt.Key_Home: 'Home',
            Qt.Key_End: 'End',
            Qt.Key_Left: 'Left',
            Qt.Key_Up: 'Up',
            Qt.Key_Right: 'Right',
            Qt.Key_Down: 'Down',
            Qt.Key_PageUp: 'PgUp',
            Qt.Key_PageDown: 'PgDn',
            Qt.Key_CapsLock: 'CapsLock',
            Qt.Key_NumLock: 'NumLock',
            Qt.Key_ScrollLock: 'ScrollLock',
            Qt.Key_F1: 'F1',
            Qt.Key_F2: 'F2',
            Qt.Key_F3: 'F3',
            Qt.Key_F4: 'F4',
            Qt.Key_F5: 'F5',
            Qt.Key_F6: 'F6',
            Qt.Key_F7: 'F7',
            Qt.Key_F8: 'F8',
            Qt.Key_F9: 'F9',
            Qt.Key_F10: 'F10',
            Qt.Key_F11: 'F11',
            Qt.Key_F12: 'F12',
            Qt.Key_Space: 'Space',
            Qt.Key_Exclam: '!',
            Qt.Key_QuoteDbl: '"',
            Qt.Key_NumberSign: '#',
            Qt.Key_Dollar: '$',
            Qt.Key_Percent: '%',
            Qt.Key_Ampersand: '&',
            Qt.Key_Apostrophe: "'",
            Qt.Key_ParenLeft: '(',
            Qt.Key_ParenRight: ')',
            Qt.Key_Asterisk: '*',
            Qt.Key_Plus: '+',
            Qt.Key_Comma: ',',
            Qt.Key_Minus: '-',
            Qt.Key_Period: '.',
            Qt.Key_Slash: '/',
            Qt.Key_0: '0',
            Qt.Key_1: '1',
            Qt.Key_2: '2',
            Qt.Key_3: '3',
            Qt.Key_4: '4',
            Qt.Key_5: '5',
            Qt.Key_6: '6',
            Qt.Key_7: '7',
            Qt.Key_8: '8',
            Qt.Key_9: '9',
            Qt.Key_Colon: ':',
            Qt.Key_Semicolon: ';',
            Qt.Key_Less: '<',
            Qt.Key_Equal: '=',
            Qt.Key_Greater: '>',
            Qt.Key_Question: '?',
            Qt.Key_At: '@',
            Qt.Key_A: 'A',
            Qt.Key_B: 'B',
            Qt.Key_C: 'C',
            Qt.Key_D: 'D',
            Qt.Key_E: 'E',
            Qt.Key_F: 'F',
            Qt.Key_G: 'G',
            Qt.Key_H: 'H',
            Qt.Key_I: 'I',
            Qt.Key_J: 'J',
            Qt.Key_K: 'K',
            Qt.Key_L: 'L',
            Qt.Key_M: 'M',
            Qt.Key_N: 'N',
            Qt.Key_O: 'O',
            Qt.Key_P: 'P',
            Qt.Key_Q: 'Q',
            Qt.Key_R: 'R',
            Qt.Key_S: 'S',
            Qt.Key_T: 'T',
            Qt.Key_U: 'U',
            Qt.Key_V: 'V',
            Qt.Key_W: 'W',
            Qt.Key_X: 'X',
            Qt.Key_Y: 'Y',
            Qt.Key_Z: 'Z',
            Qt.Key_BracketLeft: '[',
            Qt.Key_Backslash: '\\',
            Qt.Key_BracketRight: ']',
            Qt.Key_Underscore: '_',
            Qt.Key_QuoteLeft: '`',
        }
        
        key_name = key_names.get(self.key, chr(self.key) if 32 <= self.key < 127 else f'Key_{self.key}')
        return key_name
    
    def get_modifier_names(self) -> List[str]:
        
        modifiers = []
        if self.modifiers & Qt.ControlModifier:
            modifiers.append('Ctrl')
        if self.modifiers & Qt.ShiftModifier:
            modifiers.append('Shift')
        if self.modifiers & Qt.AltModifier:
            modifiers.append('Alt')
        if self.modifiers & Qt.MetaModifier:
            modifiers.append('Meta')
        return modifiers
    
    def get_display_string(self) -> str:

        parts = self.get_modifier_names()
        parts.append(self.get_key_name())
        return '+'.join(parts)
    
    def __str__(self) -> str:
        return self.get_display_string()
    
    def __repr__(self) -> str:
        return f"KeyBinding(key={self.key}, modifiers={self.modifiers}, action='{self.action}')"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, KeyBinding):
            return False
        return self.key == other.key and self.modifiers == other.modifiers
    
    def __hash__(self) -> int:
        return hash((self.key, self.modifiers))


@dataclass
class MouseBinding:

    button: int
    modifiers: int = Qt.NoModifier
    action: str = ""
    
    def __post_init__(self):
        
        # Convert to int to handle both int and Qt.MouseButtons types
        valid_buttons = int(
            Qt.NoButton |
            Qt.LeftButton |
            Qt.RightButton |
            Qt.MiddleButton |
            Qt.BackButton |
            Qt.ForwardButton |
            Qt.TaskButton |
            Qt.ExtraButton1 |
            Qt.ExtraButton2 |
            Qt.ExtraButton3 |
            Qt.ExtraButton4 |
            Qt.ExtraButton5 |
            Qt.ExtraButton6 |
            Qt.ExtraButton7 |
            Qt.ExtraButton8 |
            Qt.ExtraButton9 |
            Qt.ExtraButton10 |
            Qt.ExtraButton11 |
            Qt.ExtraButton12 |
            Qt.ExtraButton13 |
            Qt.ExtraButton14 |
            Qt.ExtraButton15 |
            Qt.ExtraButton16 |
            Qt.ExtraButton17 |
            Qt.ExtraButton18 |
            Qt.ExtraButton19 |
            Qt.ExtraButton20 |
            Qt.ExtraButton21 |
            Qt.ExtraButton22 |
            Qt.ExtraButton23 |
            Qt.ExtraButton24
        )
        self.button = int(self.button) & valid_buttons

        valid_modifiers = int(
            Qt.NoModifier |
            Qt.ShiftModifier |
            Qt.ControlModifier |
            Qt.AltModifier |
            Qt.MetaModifier
        )
        self.modifiers = int(self.modifiers) & valid_modifiers
    
    def matches(self, button: int, modifiers: int) -> bool:

        return self.button == button and self.modifiers == modifiers
    
    def to_dict(self) -> Dict[str, Any]:
        
        return {
            'button': int(self.button),  # Convert to int for JSON serialization
            'modifiers': int(self.modifiers),  # Convert to int for JSON serialization
            'action': self.action
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MouseBinding':
        
        return cls(
            button=data.get('button', Qt.NoButton),
            modifiers=data.get('modifiers', Qt.NoModifier),
            action=data.get('action', '')
        )
    
    def get_button_name(self) -> str:
        
        button_names = {
            Qt.LeftButton: 'Left',
            Qt.RightButton: 'Right',
            Qt.MiddleButton: 'Middle',
            Qt.BackButton: 'Back',
            Qt.ForwardButton: 'Forward',
        }
        return button_names.get(self.button, f'Button_{self.button}')
    
    def get_modifier_names(self) -> List[str]:
        
        modifiers = []
        if self.modifiers & Qt.ControlModifier:
            modifiers.append('Ctrl')
        if self.modifiers & Qt.ShiftModifier:
            modifiers.append('Shift')
        if self.modifiers & Qt.AltModifier:
            modifiers.append('Alt')
        if self.modifiers & Qt.MetaModifier:
            modifiers.append('Meta')
        return modifiers
    
    def get_display_string(self) -> str:

        parts = self.get_modifier_names()
        parts.append(self.get_button_name())
        return '+'.join(parts)
    
    def __str__(self) -> str:
        return self.get_display_string()
    
    def __repr__(self) -> str:
        return f"MouseBinding(button={self.button}, modifiers={self.modifiers}, action='{self.action}')"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, MouseBinding):
            return False
        return self.button == other.button and self.modifiers == other.modifiers
    
    def __hash__(self) -> int:
        return hash((self.button, self.modifiers))


def find_binding_conflicts(
    bindings: Dict[str, KeyBinding]
) -> List[Tuple[str, str, KeyBinding]]:

    conflicts = []
    seen: Dict[KeyBinding, str] = {}
    
    for action, binding in bindings.items():
        if binding in seen:
            conflicts.append((seen[binding], action, binding))
        else:
            seen[binding] = action
    
    return conflicts


def validate_key_binding(key: int, modifiers: int) -> Tuple[bool, Optional[str]]:

    if key < 0 or key > 0x10FFFF:
        return False, "Invalid key code"

    if key == 0:
        return False, "Cannot bind to modifiers only"

    reserved_keys = [
    ]
    if key in reserved_keys:
        return False, "Key is reserved by the system"
    
    return True, None

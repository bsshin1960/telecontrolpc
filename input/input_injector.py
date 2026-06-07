import ctypes
import time
import logging
from ctypes import wintypes

logger = logging.getLogger("InputInjector")

# Win32 structures and constants for SendInput
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p)
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p)
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort)
    ]

class INPUT_union(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u", INPUT_union)
    ]

# Input Types
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

# Mouse Event Flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

# Keyboard Event Flags
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

# Mappings from Qt Key codes to Windows Virtual Key codes (VK_*)
QT_TO_VK = {
    0x01000000: 0x1B,  # Qt.Key_Escape -> VK_ESCAPE
    0x01000001: 0x09,  # Qt.Key_Tab -> VK_TAB
    0x01000003: 0x08,  # Qt.Key_Backspace -> VK_BACK
    0x01000004: 0x0D,  # Qt.Key_Return -> VK_RETURN
    0x01000005: 0x0D,  # Qt.Key_Enter -> VK_RETURN
    0x01000006: 0x2D,  # Qt.Key_Insert -> VK_INSERT
    0x01000007: 0x2E,  # Qt.Key_Delete -> VK_DELETE
    0x01000008: 0x13,  # Qt.Key_Pause -> VK_PAUSE
    0x01000009: 0x2C,  # Qt.Key_Print -> VK_SNAPSHOT
    0x01000010: 0x24,  # Qt.Key_Home -> VK_HOME
    0x01000011: 0x23,  # Qt.Key_End -> VK_END
    0x01000012: 0x25,  # Qt.Key_Left -> VK_LEFT
    0x01000013: 0x26,  # Qt.Key_Up -> VK_UP
    0x01000014: 0x27,  # Qt.Key_Right -> VK_RIGHT
    0x01000015: 0x28,  # Qt.Key_Down -> VK_DOWN
    0x01000016: 0x21,  # Qt.Key_PageUp -> VK_PRIOR
    0x01000017: 0x22,  # Qt.Key_PageDown -> VK_NEXT
    0x01000020: 0x10,  # Qt.Key_Shift -> VK_SHIFT
    0x01000021: 0x11,  # Qt.Key_Control -> VK_CONTROL
    0x01000022: 0x5B,  # Qt.Key_Meta -> VK_LWIN (Windows key)
    0x01000023: 0x12,  # Qt.Key_Alt -> VK_MENU
    0x01000024: 0x14,  # Qt.Key_CapsLock -> VK_CAPITAL
    0x01000025: 0x90,  # Qt.Key_NumLock -> VK_NUMLOCK
    0x01000026: 0x91,  # Qt.Key_ScrollLock -> VK_SCROLL
    
    # Function keys F1 - F12
    0x01000030: 0x70,  # F1 -> VK_F1
    0x01000031: 0x71,  # F2 -> VK_F2
    0x01000032: 0x72,  # F3 -> VK_F3
    0x01000033: 0x73,  # F4 -> VK_F4
    0x01000034: 0x74,  # F5 -> VK_F5
    0x01000035: 0x75,  # F6 -> VK_F6
    0x01000036: 0x76,  # F7 -> VK_F7
    0x01000037: 0x77,  # F8 -> VK_F8
    0x01000038: 0x78,  # F9 -> VK_F9
    0x01000039: 0x79,  # F10 -> VK_F10
    0x0100003a: 0x7a,  # F11 -> VK_F11
    0x0100003b: 0x7b,  # F12 -> VK_F12
    
    # Common standard keys
    0x20: 0x20,        # Space -> VK_SPACE
}

# Standard alphanumeric letters and numbers share ASCII values between Qt and Win32 Virtual Keys
for code in range(0x30, 0x39 + 1):  # 0-9
    QT_TO_VK[code] = code
for code in range(0x41, 0x5A + 1):  # A-Z
    QT_TO_VK[code] = code
# Numpad keys mapping
QT_TO_VK.update({
    0x01000002: 0x09,  # Backtab -> VK_TAB
    0x2b: 0xBB,        # Plus -> VK_OEM_PLUS
    0x2c: 0xBC,        # Comma -> VK_OEM_COMMA
    0x2d: 0xBD,        # Minus -> VK_OEM_MINUS
    0x2e: 0xBE,        # Period -> VK_OEM_PERIOD
    0x2f: 0xBF,        # Slash -> VK_OEM_2 (/)
    0x3a: 0xBA,        # Colon -> VK_OEM_1 (;)
    0x3b: 0xBA,        # Semicolon -> VK_OEM_1 (;)
    0x3c: 0xBC,        # Less than -> VK_OEM_COMMA
    0x3d: 0xBB,        # Equal -> VK_OEM_PLUS
    0x3e: 0xBE,        # Greater than -> VK_OEM_PERIOD
    0x3f: 0xBF,        # Question -> VK_OEM_2 (/)
    0x40: 0x32,        # At (@)
    0x5b: 0xDB,        # BracketLeft -> VK_OEM_4 ([)
    0x5c: 0xDC,        # Backslash -> VK_OEM_5 (\)
    0x5d: 0xDD,        # BracketRight -> VK_OEM_6 (])
    0x5e: 0x36,        # Caret (^)
    0x5f: 0xBD,        # Underscore (_)
    0x60: 0xC0,        # QuoteLeft -> VK_OEM_3 (`)
})


class InputInjector:
    def __init__(self):
        self.user32 = ctypes.windll.user32
        
        # Explicitly declare ctypes argtypes and restypes for 64-bit stability
        self.user32.SendInput.argtypes = [ctypes.c_uint, ctypes.c_void_p, ctypes.c_int]
        self.user32.SendInput.restype = ctypes.c_uint
        
        self.user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        self.user32.SetCursorPos.restype = ctypes.c_bool
        
    def move_mouse(self, x_ratio: float, y_ratio: float, monitor_info: dict = None):
        """
        Move mouse to absolute coordinates mapped to the specified monitor bounds.
        If monitor_info is None, it maps to the primary display.
        """
        try:
            if monitor_info:
                left = monitor_info.get("left", 0)
                top = monitor_info.get("top", 0)
                width = monitor_info.get("width", 1920)
                height = monitor_info.get("height", 1080)
            else:
                # Default to primary monitor size using win32 API
                left = 0
                top = 0
                width = self.user32.GetSystemMetrics(0)  # SM_CXSCREEN
                height = self.user32.GetSystemMetrics(1) # SM_CYSCREEN
            
            abs_x = left + int(x_ratio * width)
            abs_y = top + int(y_ratio * height)
            
            # Set cursor position directly (fastest and most reliable)
            self.user32.SetCursorPos(abs_x, abs_y)
        except Exception as e:
            logger.error(f"Error moving mouse: {e}")

    def inject_mouse_event(self, flags: int, data: int = 0):
        """
        Send a mouse event using SendInput.
        """
        try:
            mi = MOUSEINPUT(0, 0, data, flags, 0, None)
            union = INPUT_union(mi=mi)
            inp = INPUT(type=INPUT_MOUSE, u=union)
            self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
        except Exception as e:
            logger.error(f"Error injecting mouse event flags={flags}: {e}")

    def press_mouse_button(self, button: str, is_down: bool):
        """
        Simulate mouse button press or release.
        button: 'left', 'right', 'middle'
        """
        flags = 0
        if button == 'left':
            flags = MOUSEEVENTF_LEFTDOWN if is_down else MOUSEEVENTF_LEFTUP
        elif button == 'right':
            flags = MOUSEEVENTF_RIGHTDOWN if is_down else MOUSEEVENTF_RIGHTUP
        elif button == 'middle':
            flags = MOUSEEVENTF_MIDDLEDOWN if is_down else MOUSEEVENTF_MIDDLEUP
            
        if flags:
            self.inject_mouse_event(flags)

    def scroll_mouse(self, dx: float, dy: float):
        """
        Scroll mouse wheel.
        dy > 0: Scroll Up, dy < 0: Scroll Down
        dx is horizontal scroll (not commonly used but supported)
        """
        # Vertical wheel scroll. Wheel delta is 120 per notch.
        wheel_amount = int(dy * 120)
        self.inject_mouse_event(MOUSEEVENTF_WHEEL, wheel_amount)

    def inject_key_event(self, qt_key_code: int, is_down: bool):
        """
        Inject keyboard key down/up using SendInput and VK codes.
        """
        vk = QT_TO_VK.get(qt_key_code)
        if vk is None:
            # Fallback: if it's already a standard VK or ascii, try to use it directly
            if 0 < qt_key_code < 256:
                vk = qt_key_code
            else:
                logger.warning(f"Unknown Qt key code: {qt_key_code}, cannot inject.")
                return

        try:
            flags = 0 if is_down else KEYEVENTF_KEYUP
            # Check if it's an extended key (like arrow keys, insert, delete, home, end, page up/down)
            # Extended keys need KEYEVENTF_EXTENDEDKEY flag on Windows
            if vk in [0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E]:
                flags |= KEYEVENTF_EXTENDEDKEY

            ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=None)
            union = INPUT_union(ki=ki)
            inp = INPUT(type=INPUT_KEYBOARD, u=union)
            self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
        except Exception as e:
            logger.error(f"Error injecting key event vk={vk}: {e}")

    def inject_unicode_char(self, char: str):
        """
        Alternative method: Inject text character directly as Unicode.
        """
        if not char:
            return
        try:
            for c in char:
                code_point = ord(c)
                # Key down
                ki_down = KEYBDINPUT(wVk=0, wScan=code_point, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=None)
                union_down = INPUT_union(ki=ki_down)
                inp_down = INPUT(type=INPUT_KEYBOARD, u=union_down)
                self.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(inp_down))
                
                # Key up
                ki_up = KEYBDINPUT(wVk=0, wScan=code_point, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=None)
                union_up = INPUT_union(ki=ki_up)
                inp_up = INPUT(type=INPUT_KEYBOARD, u=union_up)
                self.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up))
        except Exception as e:
            logger.error(f"Error injecting unicode character {char}: {e}")

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QMetaObject, Q_ARG
from PyQt5.QtGui import QPainter, QPixmap, QImage, QColor, QKeyEvent, QMouseEvent, QWheelEvent, QFont
import logging
import asyncio

logger = logging.getLogger("RemoteViewer")

class RemoteViewerWidget(QWidget):
    # Signal emitted when connection is closed or error occurs (UI feedback)
    connection_lost = pyqtSignal(str)

    # Signal for thread-safe frame updates from asyncio/executor threads
    _frame_signal = pyqtSignal(bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.client = None
        self.current_pixmap = None
        self.dest_rect = QRectF()
        self._status_text = "원격 화면을 기다리는 중..."

        # Configure widget behavior
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setAutoFillBackground(False)
        self.setMinimumSize(320, 240)

        # Track mouse states
        self.is_left_clicked = False

        # Connect signal to slot — always runs on Qt main thread
        self._frame_signal.connect(self._on_frame_received)

    def set_client(self, client):
        self.client = client

    def set_status_text(self, text: str):
        """Update placeholder text shown when no frame is active."""
        self._status_text = text
        self.update()

    # ------------------------------------------------------------------
    # Frame update — called from asyncio receive_loop (main thread via qasync)
    # We still route through the signal for safety, in case executor threads
    # ever call this in the future.
    # ------------------------------------------------------------------
    def update_frame(self, jpeg_bytes: bytes):
        """
        Public API called by the network client when a new JPEG frame arrives.
        Emits a signal so the actual pixmap update always runs on the Qt main thread.
        """
        try:
            logger.debug(f"update_frame called, size={len(jpeg_bytes)} bytes")
            self._frame_signal.emit(jpeg_bytes)
        except Exception as e:
            logger.error(f"update_frame emit error: {e}")

    def _on_frame_received(self, jpeg_bytes: bytes):
        """Slot — always executes on the Qt main thread."""
        if not jpeg_bytes:
            logger.warning("_on_frame_received received empty jpeg_bytes")
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(jpeg_bytes, "JPEG"):
            old_w, old_h = pixmap.width(), pixmap.height()
            self.current_pixmap = self.crop_padding(pixmap)
            logger.debug(f"Successfully decoded JPEG, cropped: {old_w}x{old_h} -> {self.current_pixmap.width()}x{self.current_pixmap.height()}")
            self.update()  # schedule repaint on main thread
        else:
            logger.warning(f"Failed to decode JPEG frame ({len(jpeg_bytes)} bytes)")

    def crop_padding(self, pixmap: QPixmap) -> QPixmap:
        """
        Crops the GPU row padding (stripes) on the right of the image if detected.
        """
        if self.client and self.client.is_windows_host:
            # PC-to-PC mode: no padding expected from Windows screen capture
            return pixmap

        w = pixmap.width()
        h = pixmap.height()

        # Standard scaled widths for Android screens:
        # 576 -> 540 (padding 36), 384 -> 360 (padding 24), 768 -> 720 (padding 48)
        # 1152 -> 1080 (padding 72), 1088 -> 1080 (padding 8)
        mapping = {
            576: 540,
            384: 360,
            768: 720,
            1152: 1080,
            1088: 1080
        }

        if w in mapping:
            actual_w = mapping[w]
            logger.debug(f"Cropping Android frame padding: {w}x{h} -> {actual_w}x{h}")
            return pixmap.copy(0, 0, actual_w, h)

        # Fallback ratio-based detection for non-standard or custom resolutions
        if h > 0 and (w / h) > 0.52:
            for pad in [16, 24, 32, 36, 48, 64, 72, 80, 96]:
                test_w = w - pad
                if 0.43 <= (test_w / h) <= 0.51:
                    logger.debug(f"Cropping Android frame padding (fallback): {w}x{h} -> {test_w}x{h}")
                    return pixmap.copy(0, 0, test_w, h)

        return pixmap

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background fill
        painter.fillRect(self.rect(), QColor(10, 10, 18))

        # Check if left settings panel is visible, to exclude it from drawing calculations
        has_left_panel = False
        panel_width = 0.0
        for child in self.children():
            if child.isWidgetType() and child.objectName() == "cardFrame" and child.isVisible():
                has_left_panel = True
                panel_width = float(child.width())
                break

        # User's specification:
        # Left spacing = 10px, Right spacing = 10px, Right fixed margin = 300px
        # On fullscreen/no panel: Left margin = 10px, Right margin = 10px
        if has_left_panel:
            left_margin = panel_width + 10.0
            right_margin = 300.0 + 10.0
        else:
            left_margin = 10.0
            right_margin = 10.0

        if self.current_pixmap and not self.current_pixmap.isNull():
            # Fit inside the available area while preserving aspect ratio
            view_w = float(self.width()) - left_margin - right_margin
            view_h = float(self.height())
            
            pix_w = float(self.current_pixmap.width())
            pix_h = float(self.current_pixmap.height())
            
            if pix_w > 0 and pix_h > 0:
                scale = min(view_w / pix_w, view_h / pix_h)
                new_w = pix_w * scale
                new_h = pix_h * scale
                
                # Center the destination rectangle in the available width
                x = left_margin + (view_w - new_w) / 2.0
                y = (view_h - new_h) / 2.0
                
                self.dest_rect.setRect(x, y, new_w, new_h)
            else:
                self.dest_rect.setRect(left_margin, 0.0, view_w, view_h)
                
            painter.drawPixmap(self.dest_rect, self.current_pixmap, QRectF(self.current_pixmap.rect()))
        else:
            # Draw placeholder centered in the available area
            view_w = float(self.width()) - left_margin - right_margin
            cx = left_margin + view_w / 2.0
            cy = self.height() / 2.0
            
            self.dest_rect.setRect(left_margin, 0.0, view_w, self.height())

            # Draw dashed border box
            painter.setPen(QColor(55, 65, 90))
            painter.drawRoundedRect(
                int(cx - 180), int(cy - 100), 360, 200, 16, 16
            )

            # Monitor icon (simple rect)
            painter.setPen(QColor(80, 100, 140))
            painter.setBrush(QColor(20, 25, 40))
            painter.drawRoundedRect(int(cx - 60), int(cy - 55), 120, 80, 6, 6)
            painter.setBrush(QColor(55, 65, 90))
            painter.drawRect(int(cx - 10), int(cy + 25), 20, 12)
            painter.drawRect(int(cx - 25), int(cy + 37), 50, 5)

            # Status text
            font = QFont("Segoe UI", 11)
            painter.setFont(font)
            painter.setPen(QColor(148, 163, 184))
            
            text_rect = self.rect().adjusted(int(left_margin), int(cy + 60) - self.height() // 2, -int(right_margin), 0)
            painter.drawText(
                text_rect,
                Qt.AlignHCenter | Qt.AlignTop,
                self._status_text
            )

    def get_normalized_coords(self, x: float, y: float):
        """
        Converts pixel coordinates relative to the widget into a 0.0 - 1.0 ratio
        mapped to the active destination rectangle.
        """
        rect_w = self.dest_rect.width()
        rect_h = self.dest_rect.height()

        if rect_w <= 0 or rect_h <= 0:
            return 0.5, 0.5

        x_in_rect = x - self.dest_rect.left()
        y_in_rect = y - self.dest_rect.top()

        x_ratio = max(0.0, min(1.0, x_in_rect / rect_w))
        y_ratio = max(0.0, min(1.0, y_in_rect / rect_h))

        return x_ratio, y_ratio

    # Mouse Events
    def mousePressEvent(self, event: QMouseEvent):
        if not self.client or not self.client.is_connected:
            return

        x_ratio, y_ratio = self.get_normalized_coords(event.x(), event.y())

        if event.button() == Qt.LeftButton:
            self.is_left_clicked = True
            self.client.send_touch_event(0, x_ratio, y_ratio, "left")
        elif event.button() == Qt.RightButton:
            if self.client.is_windows_host:
                self.client.send_extended_mouse_event("right_down", x_ratio, y_ratio)
        elif event.button() == Qt.MidButton:
            self.client.send_extended_mouse_event("middle_down", x_ratio, y_ratio)

        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if not self.client or not self.client.is_connected:
            return

        x_ratio, y_ratio = self.get_normalized_coords(event.x(), event.y())

        if event.button() == Qt.LeftButton:
            self.is_left_clicked = False
            self.client.send_touch_event(1, x_ratio, y_ratio, "left")
        elif event.button() == Qt.RightButton:
            if self.client.is_windows_host:
                self.client.send_extended_mouse_event("right_up", x_ratio, y_ratio)
            else:
                self.client.send_command("NAV_BACK")
        elif event.button() == Qt.MidButton:
            self.client.send_extended_mouse_event("middle_up", x_ratio, y_ratio)

        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        # Get local mouse position
        y = event.y()
        parent_win = self.window()
        if parent_win and getattr(parent_win, "is_fullscreen_mode", False):
            if y < 15: # top 15 pixels
                if hasattr(parent_win, "show_floating_restore_menu"):
                    parent_win.show_floating_restore_menu()
            elif y > 50: # move below 50 pixels
                if hasattr(parent_win, "floating_restore_btn"):
                    parent_win.floating_restore_btn.hide()

        if not self.client or not self.client.is_connected:
            event.accept()
            return

        is_windows = self.client.is_windows_host
        if is_windows or self.is_left_clicked:
            x_ratio, y_ratio = self.get_normalized_coords(event.x(), event.y())
            self.client.send_touch_event(2, x_ratio, y_ratio, "left")

        event.accept()

    def wheelEvent(self, event: QWheelEvent):
        if not self.client or not self.client.is_connected:
            return

        dy = event.angleDelta().y() / 120.0
        dx = event.angleDelta().x() / 120.0
        self.client.send_scroll_event(dx, dy)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if not self.client or not self.client.is_connected:
            return

        key = event.key()
        modifiers = event.modifiers()
        
        # Check if parent is in full screen mode, and if ESC or Ctrl+C is pressed, exit full screen!
        parent_win = self.window()
        is_fullscreen = False
        if parent_win and hasattr(parent_win, "is_fullscreen_mode"):
            is_fullscreen = parent_win.is_fullscreen_mode
            
        is_esc = (key == Qt.Key_Escape)
        is_ctrl_c = (key == Qt.Key_C and (modifiers & Qt.ControlModifier))
        
        if is_fullscreen and (is_esc or is_ctrl_c):
            if hasattr(parent_win, "exit_fullscreen"):
                parent_win.exit_fullscreen()
            event.accept()
            return

        if key == Qt.Key_Escape:
            asyncio.create_task(self.client.disconnect())
            event.accept()
            return

        if event.isAutoRepeat():
            event.accept()
            return

        self.client.send_key_event("key_down", key)

        text_char = event.text()
        if text_char and text_char.isprintable() and not (event.modifiers() & (Qt.ControlModifier | Qt.AltModifier)):
            self.client.send_char_event(text_char)

        event.accept()

    def keyReleaseEvent(self, event: QKeyEvent):
        if not self.client or not self.client.is_connected:
            return

        if event.isAutoRepeat():
            event.accept()
            return

        self.client.send_key_event("key_up", event.key())
        event.accept()

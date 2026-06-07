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

        if self.current_pixmap and not self.current_pixmap.isNull():
            # Calculate aspect ratio fit
            view_w = float(self.width())
            view_h = float(self.height())
            bmp_w = float(self.current_pixmap.width())
            bmp_h = float(self.current_pixmap.height())

            bmp_aspect = bmp_w / bmp_h
            view_aspect = view_w / view_h

            if bmp_aspect > view_aspect:
                draw_w = view_w
                draw_h = view_w / bmp_aspect
            else:
                draw_h = view_h
                draw_w = view_h * bmp_aspect

            offset_x = (view_w - draw_w) / 2.0
            offset_y = (view_h - draw_h) / 2.0

            self.dest_rect.setRect(offset_x, offset_y, draw_w, draw_h)
            painter.drawPixmap(self.dest_rect, self.current_pixmap, QRectF(self.current_pixmap.rect()))
        else:
            # Draw placeholder when no frame is available
            self.dest_rect.setRect(0, 0, self.width(), self.height())

            # Centered icon area
            cx = self.width() / 2
            cy = self.height() / 2

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
            painter.drawText(
                self.rect().adjusted(0, int(cy + 60) - self.height() // 2, 0, 0),
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
            self.client.send_extended_mouse_event("right_up", x_ratio, y_ratio)
        elif event.button() == Qt.MidButton:
            self.client.send_extended_mouse_event("middle_up", x_ratio, y_ratio)

        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.client or not self.client.is_connected:
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

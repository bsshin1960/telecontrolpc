from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QRectF, pyqtSignal
from PyQt5.QtGui import QPainter, QPixmap, QImage, QColor, QKeyEvent, QMouseEvent, QWheelEvent
import logging
import asyncio

logger = logging.getLogger("RemoteViewer")

class RemoteViewerWidget(QWidget):
    # Signal emitted when connection is closed or error occurs (UI feedback)
    connection_lost = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.client = None
        self.current_pixmap = None
        self.dest_rect = QRectF()
        
        # Configure widget behavior
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setAutoFillBackground(False)
        
        # Track mouse states
        self.is_left_clicked = False

    def set_client(self, client):
        self.client = client

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
        # Android phone aspect ratios (height > width) are usually between 9:16 (0.5625) and 9:22 (0.409)
        # If the aspect ratio w/h is wider than 0.52, it likely has padding on the right.
        if h > 0 and (w / h) > 0.52:
            # Try common pad values
            for pad in [16, 24, 32, 36, 48, 64, 72, 80, 96]:
                test_w = w - pad
                if 0.43 <= (test_w / h) <= 0.51:
                    logger.debug(f"Cropping Android frame padding (fallback): {w}x{h} -> {test_w}x{h}")
                    return pixmap.copy(0, 0, test_w, h)
                    
        return pixmap

    def update_frame(self, jpeg_bytes: bytes):
        """
        Updates the displayed frame with new JPEG bytes received from the host.
        """
        pixmap = QPixmap()
        if pixmap.loadFromData(jpeg_bytes, "JPEG"):
            self.current_pixmap = self.crop_padding(pixmap)
            self.update() # trigger paintEvent
        else:
            logger.warning("Failed to load QPixmap from JPEG bytes")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Background black fill
        painter.fillRect(self.rect(), QColor(10, 10, 15))
        
        if self.current_pixmap and not self.current_pixmap.isNull():
            # Calculate aspect ratio fit
            view_w = float(self.width())
            view_h = float(self.height())
            bmp_w = float(self.current_pixmap.width())
            bmp_h = float(self.current_pixmap.height())
            
            bmp_aspect = bmp_w / bmp_h
            view_aspect = view_w / view_h
            
            if bmp_aspect > view_aspect:
                # Bitmap is wider than view -> scale by width
                draw_w = view_w
                draw_h = view_w / bmp_aspect
            else:
                # Bitmap is taller than view -> scale by height
                draw_h = view_h
                draw_w = view_h * bmp_aspect
                
            offset_x = (view_w - draw_w) / 2.0
            offset_y = (view_h - draw_h) / 2.0
            
            self.dest_rect.setRect(offset_x, offset_y, draw_w, draw_h)
            painter.drawPixmap(self.dest_rect, self.current_pixmap, QRectF(self.current_pixmap.rect()))
        else:
            # Draw placeholder when no frame is available
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(self.rect(), Qt.AlignCenter, "Waiting for screen stream...")

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
        
        # Clamp between 0.0 and 1.0 (clamps clicks in black border regions)
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
            # action: 0 = down
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
            # action: 1 = up
            self.client.send_touch_event(1, x_ratio, y_ratio, "left")
        elif event.button() == Qt.RightButton:
            self.client.send_extended_mouse_event("right_up", x_ratio, y_ratio)
        elif event.button() == Qt.MidButton:
            self.client.send_extended_mouse_event("middle_up", x_ratio, y_ratio)
            
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.client or not self.client.is_connected:
            return
            
        # Optimization: Only send mouse moves to Android if dragging (left click down).
        # For Windows Host, send mouse moves always to support hover cursor updates.
        is_windows = self.client.is_windows_host
        if is_windows or self.is_left_clicked:
            x_ratio, y_ratio = self.get_normalized_coords(event.x(), event.y())
            # action: 2 = move
            self.client.send_touch_event(2, x_ratio, y_ratio, "left")
            
        event.accept()

    def wheelEvent(self, event: QWheelEvent):
        if not self.client or not self.client.is_connected:
            return
            
        # Get wheel delta (typically 120 per notch)
        # y > 0 is scroll up, y < 0 is scroll down
        # x is horizontal scrolling (supported by modern mice)
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
            
        # Prevent auto-repeated keypress events
        if event.isAutoRepeat():
            event.accept()
            return
            
        # Check if we should inject it as character or keycode
        # Characters (like Korean letters or symbols) are better sent as Unicode
        # if no control keys like Ctrl, Alt are active.
        # However, for hotkeys, VK controls work best.
        # Send key_down VK first
        self.client.send_key_event("key_down", key)
        
        # If there's text input (and it's a printable character), send it as char event
        text_char = event.text()
        if text_char and text_char.isprintable() and not (event.modifiers() & (Qt.ControlModifier | Qt.AltModifier)):
            # On Windows hosts, sending text char directly helps with IME input
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

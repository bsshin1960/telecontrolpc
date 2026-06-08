import socket
import asyncio
import os
import json
import logging
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox,
    QMessageBox, QFrame, QSplitter, QApplication
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from gui.styles import QSS_STYLESHEET
from gui.remote_viewer import RemoteViewerWidget
from network.server import RemoteControlServer
from network.client import RemoteControlClient
from capture.screen_capture import ScreenCapturer

logger = logging.getLogger("MainWindow")

# File to store connection history
HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".telecontrol_history.json")

def get_local_ip():
    """
    Retrieves the local IPv4 address of the active network interface.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TeleControl - 원격 데스크톱 제어")
        # Fit primary screen available geometry on startup
        screen = QApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            self.resize(rect.width(), rect.height())
        else:
            self.resize(1024, 768)
        
        # Apply premium dark mode styles
        self.setStyleSheet(QSS_STYLESHEET)
        
        # Initialize modules
        self.server = RemoteControlServer()
        self.client = RemoteControlClient()
        self.capturer = ScreenCapturer()
        
        # Connection History
        self.history = self.load_history()
        
        # GUI Layout Setup
        self.init_ui()
        
        # Set server log callback
        self.server.set_log_callback(self.append_server_log)
        
        # Floating restore button for fullscreen mode
        self.floating_restore_btn = QPushButton("전체 화면 종료 ✕", self)
        self.floating_restore_btn.setObjectName("primaryButton")
        self.floating_restore_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 30, 46, 0.95);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                color: white;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #ef4444;
            }
        """)
        self.floating_restore_btn.setCursor(Qt.PointingHandCursor)
        self.floating_restore_btn.clicked.connect(self.exit_fullscreen)
        self.floating_restore_btn.hide()

        # Show maximized on startup
        self.showMaximized()

    def show_floating_restore_menu(self):
        if self.isFullScreen():
            self.floating_restore_btn.show()
            self.floating_restore_btn.raise_()
        else:
            self.floating_restore_btn.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "floating_restore_btn"):
            btn_w = 120
            btn_h = 28
            x = (self.width() - btn_w) // 2
            self.floating_restore_btn.setGeometry(x, 0, btn_w, btn_h)

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Main layout is vertical (top header bar + content area)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1. Top Header Bar
        self.header_widget = QWidget(self)
        self.header_widget.setObjectName("headerWidget")
        self.header_widget.setStyleSheet("background-color: #0d0d12;")
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(15, 10, 15, 5)
        header_layout.setSpacing(15)
        
        lbl_main_title = QLabel("TeleControl", self.header_widget)
        lbl_main_title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        header_layout.addWidget(lbl_main_title)
        
        header_layout.addStretch(1)
        
        # Full Screen button
        self.btn_fullscreen = QPushButton("전체 화면", self.header_widget)
        self.btn_fullscreen.setCursor(Qt.PointingHandCursor)
        self.btn_fullscreen.setObjectName("fullscreenButton") # Using the 1.4x larger font style
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        header_layout.addWidget(self.btn_fullscreen)
        
        main_layout.addWidget(self.header_widget)
        
        # 2. Main Content Area (Remote Viewer only)
        self.viewer = RemoteViewerWidget(self)
        self.viewer.set_client(self.client)
        main_layout.addWidget(self.viewer)
        
        # 3. Left Panel (Settings) - parent is self.viewer to allow overlay
        self.left_panel = QFrame(self.viewer)
        self.left_panel.setObjectName("cardFrame")
        self.left_panel.setFixedWidth(150)
        
        # Prevent mouse/key/scroll events on settings panel from propagating to viewer
        self.left_panel.mousePressEvent = lambda event: event.accept()
        self.left_panel.mouseReleaseEvent = lambda event: event.accept()
        self.left_panel.mouseMoveEvent = lambda event: event.accept()
        self.left_panel.wheelEvent = lambda event: event.accept()
        self.left_panel.keyPressEvent = lambda event: event.accept()
        self.left_panel.keyReleaseEvent = lambda event: event.accept()
        
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(5, 8, 5, 8)
        left_layout.setSpacing(10)
        
        # Mode Button 1: 도움 받기
        self.btn_menu_receive = QPushButton("도움 받기", self)
        self.btn_menu_receive.setCursor(Qt.PointingHandCursor)
        self.btn_menu_receive.setFixedHeight(26)
        self.btn_menu_receive.setObjectName("btnHelpReceive")
        self.btn_menu_receive.clicked.connect(lambda: self.select_mode("host"))
        left_layout.addWidget(self.btn_menu_receive)
        
        # Mode Button 2: 도움 주기
        self.btn_menu_give = QPushButton("도움 주기", self)
        self.btn_menu_give.setCursor(Qt.PointingHandCursor)
        self.btn_menu_give.setFixedHeight(26)
        self.btn_menu_give.setObjectName("btnHelpGive")
        self.btn_menu_give.clicked.connect(lambda: self.select_mode("client"))
        left_layout.addWidget(self.btn_menu_give)
        
        # Host Container 1 (displays below both buttons)
        self.host_container = QWidget(self.left_panel)
        self.init_left_host_page()
        left_layout.addWidget(self.host_container)
        
        # Client Container 2 (displays below both buttons)
        self.client_container = QWidget(self.left_panel)
        self.init_left_client_page()
        left_layout.addWidget(self.client_container)
        
        left_layout.addStretch(1)
        
        # Pre-fill Client IP and Port if history exists
        if self.history:
            try:
                ip, port = self.history[0].split(":")
                self.edt_client_ip.setText(ip)
                self.spn_client_port.setValue(int(port))
            except Exception:
                pass
        
        # Set layout on self.viewer to overlay left_panel on top
        viewer_layout = QHBoxLayout(self.viewer)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.setSpacing(0)
        viewer_layout.addWidget(self.left_panel)
        viewer_layout.addStretch(1)
        
        # On startup, only show the two buttons (hide both menus initially)
        self.host_container.setVisible(False)
        self.client_container.setVisible(False)

    def init_left_host_page(self):
        layout = QVBoxLayout(self.host_container)
        layout.setContentsMargins(2, 5, 2, 5)
        layout.setSpacing(10)
        
        # Server Status Card
        status_card = QFrame(self.host_container)
        status_card.setObjectName("statusCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(5, 5, 5, 5)
        status_layout.setSpacing(3)
        
        status_title = QLabel("서버 상태", status_card)
        status_title.setStyleSheet("font-weight: bold; color: #a855f7; font-size: 11px; background: transparent;")
        status_layout.addWidget(status_title)
        
        self.lbl_server_status = QLabel("서버 중지됨", status_card)
        self.lbl_server_status.setStyleSheet("color: #ef4444; background-color: #08080c; border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 6px; padding: 2px 4px; font-size: 11px; font-weight: bold; min-height: 16px;")
        self.lbl_server_status.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.lbl_server_status)
        
        layout.addWidget(status_card)
        
        # Host IP Card
        ip_card = QFrame(self.host_container)
        ip_card.setObjectName("statusCard")
        ip_layout = QVBoxLayout(ip_card)
        ip_layout.setContentsMargins(5, 5, 5, 5)
        ip_layout.setSpacing(3)
        
        ip_title = QLabel("내 주소", ip_card)
        ip_title.setStyleSheet("font-weight: bold; color: #818cf8; font-size: 11px; background: transparent;")
        ip_layout.addWidget(ip_title)
        
        self.lbl_ip = QLabel(get_local_ip(), ip_card)
        self.lbl_ip.setObjectName("ipLabel")
        self.lbl_ip.setAlignment(Qt.AlignCenter)
        ip_layout.addWidget(self.lbl_ip)
        
        layout.addWidget(ip_card)
        
        # Start Server Button
        self.btn_toggle_server = QPushButton("원격 도움 요청", self.host_container)
        self.btn_toggle_server.setObjectName("primaryButton")
        self.btn_toggle_server.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_server.setFixedHeight(26)
        self.btn_toggle_server.clicked.connect(self.toggle_server)
        layout.addWidget(self.btn_toggle_server)

    def init_left_client_page(self):
        layout = QVBoxLayout(self.client_container)
        layout.setContentsMargins(2, 5, 2, 5)
        layout.setSpacing(10)
        
        # Connection Form - IP Card
        ip_frame = QFrame(self.client_container)
        ip_frame.setObjectName("statusCard")
        ip_layout = QVBoxLayout(ip_frame)
        ip_layout.setContentsMargins(5, 5, 5, 5)
        ip_layout.setSpacing(3)
        
        lbl_ip_title = QLabel("원격 주소", ip_frame)
        lbl_ip_title.setStyleSheet("font-weight: bold; color: #818cf8; font-size: 11px; background: transparent;")
        
        self.edt_client_ip = QLineEdit(ip_frame)
        self.edt_client_ip.setPlaceholderText("예: 192.168.0.15")
        self.edt_client_ip.setAlignment(Qt.AlignCenter)
        
        ip_layout.addWidget(lbl_ip_title)
        ip_layout.addWidget(self.edt_client_ip)
        layout.addWidget(ip_frame)
        
        # Connection Form - Port Card
        port_frame = QFrame(self.client_container)
        port_frame.setObjectName("statusCard")
        port_layout = QVBoxLayout(port_frame)
        port_layout.setContentsMargins(5, 5, 5, 5)
        port_layout.setSpacing(3)
        
        lbl_port_title = QLabel("원격 포트", port_frame)
        lbl_port_title.setStyleSheet("font-weight: bold; color: #818cf8; font-size: 11px; background: transparent;")
        
        self.spn_client_port = QSpinBox(port_frame)
        self.spn_client_port.setRange(1024, 65535)
        self.spn_client_port.setValue(8080)
        self.spn_client_port.setAlignment(Qt.AlignCenter)
        
        port_layout.addWidget(lbl_port_title)
        port_layout.addWidget(self.spn_client_port)
        layout.addWidget(port_frame)
        
        # Connect Button
        self.btn_connect = QPushButton("연결", self.client_container)
        self.btn_connect.setObjectName("primaryButton")
        self.btn_connect.setCursor(Qt.PointingHandCursor)
        self.btn_connect.setFixedHeight(26)
        self.btn_connect.clicked.connect(self.connect_to_server)
        layout.addWidget(self.btn_connect)
        
        # Client Status Label
        self.lbl_client_status = QLabel("오프라인", self.client_container)
        self.lbl_client_status.setStyleSheet("color: #ef4444; font-size: 10px; font-weight: bold;")
        self.lbl_client_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_client_status)
        


    def select_mode(self, mode: str):
        if mode == "host":
            # Toggle host container, hide client container
            is_visible = self.host_container.isVisible()
            self.host_container.setVisible(not is_visible)
            self.client_container.setVisible(False)
        else:
            # Hide host container, toggle client container
            is_visible = self.client_container.isVisible()
            self.host_container.setVisible(False)
            self.client_container.setVisible(not is_visible)

    def toggle_fullscreen(self):
        if not self.isFullScreen():
            self.enter_fullscreen()
        else:
            self.exit_fullscreen()

    def enter_fullscreen(self):
        self.was_maximized = self.isMaximized()
        self.header_widget.hide()
        self.left_panel.hide()
        self.showFullScreen()
        self.is_fullscreen_mode = True

    def exit_fullscreen(self):
        self.header_widget.show()
        self.left_panel.show()
        if getattr(self, "was_maximized", True):
            self.showMaximized()
        else:
            self.showNormal()
        self.is_fullscreen_mode = False
        self.floating_restore_btn.hide()

    # History Logic
    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_history(self):
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(self.history, f)
        except Exception as e:
            logger.error(f"Error saving history: {e}")

    def add_to_history(self, ip, port):
        entry = f"{ip}:{port}"
        if entry in self.history:
            self.history.remove(entry)
        self.history.insert(0, entry)
        self.history = self.history[:10]  # keep top 10
        self.save_history()

    # Host Action Handlers
    def append_server_log(self, message: str):
        logger.info(f"Server log: {message}")

    def toggle_server(self):
        """
        Starts or stops the hosting WebSocket server.
        """
        if self.server.is_running:
            # Stop server
            asyncio.create_task(self.stop_server_async())
        else:
            # Start server
            asyncio.create_task(self.start_server_async())

    async def start_server_async(self):
        monitor_idx = 1
        scale = 1.0
        quality = 60
        fps = 30
        port = 8080
        
        self.server.port = port
        self.server.update_settings(monitor_idx, scale, quality, fps)
        
        try:
            await self.server.start()
            
            self.lbl_server_status.setText("서버 실행 중")
            self.lbl_server_status.setStyleSheet("color: #22c55e; background-color: #08080c; border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 6px; padding: 2px 4px; font-size: 11px; font-weight: bold; min-height: 16px; qproperty-alignment: AlignCenter;")
            self.btn_toggle_server.setText("원격 도움 중지")
            self.btn_toggle_server.setObjectName("dangerButton")
            self.btn_toggle_server.setStyleSheet("")
            self.setStyleSheet(QSS_STYLESHEET)
        except Exception as e:
            QMessageBox.critical(self, "서버 오류", f"서버를 시작하지 못했습니다:\n{e}")
    async def stop_server_async(self):
        await self.server.stop()
        self.lbl_server_status.setText("서버 중지됨")
        self.lbl_server_status.setStyleSheet("color: #ef4444; background-color: #08080c; border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 6px; padding: 2px 4px; font-size: 11px; font-weight: bold; min-height: 16px; qproperty-alignment: AlignCenter;")
        self.btn_toggle_server.setText("원격 도움 요청")
        self.btn_toggle_server.setObjectName("primaryButton")
        self.btn_toggle_server.setStyleSheet("")
        self.setStyleSheet(QSS_STYLESHEET)

    # Client Action Handlers
    def connect_to_server(self):
        if self.client.is_connected:
            asyncio.create_task(self.disconnect_client_async())
            return
            
        ip = self.edt_client_ip.text().strip()
        port = self.spn_client_port.value()
        
        if not ip:
            QMessageBox.warning(self, "입력 오류", "올바른 원격 IP 주소를 입력하세요.")
            return
            
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("연결 시도 중...")
        
        asyncio.create_task(self.connect_to_server_async(ip, port))

    async def connect_to_server_async(self, ip: str, port: int):
        try:
            # 콜백 먼저 등록 후 연결 (연결 직후 핸드셰이크 메시지 수신 대비)
            self.client.set_callbacks(
                frame_cb=self.viewer.update_frame,
                status_cb=self.handle_client_status_update,
                stats_cb=self.handle_client_stats_update
            )

            # 뷰어에 연결 중 상태 표시
            self.viewer.set_status_text(f"{ip}:{port} 에 연결 중...")
            self.viewer.current_pixmap = None
            self.viewer.update()

            await self.client.connect(ip, port)

            # Save to history on successful connection
            self.add_to_history(ip, port)

            # Update connect button to show disconnect option
            self.btn_connect.setEnabled(True)
            self.btn_connect.setText("연결 종료")
            self.btn_connect.setObjectName("dangerButton")
            self.btn_connect.setStyleSheet("")
            self.btn_menu_receive.hide()
            self.setStyleSheet(QSS_STYLESHEET)

            # 뷰어 상태 텍스트 업데이트 (화면 스트림 대기 중)
            self.viewer.set_status_text("화면 스트림 수신 대기 중...")

            # 설정창은 그대로 유지 (사용자가 직접 접을 수 있음)
            # Focus on the remote viewer so keyboard inputs work immediately
            self.viewer.setFocus()

        except Exception as e:
            self.client.set_callbacks(None, None, None)
            self.viewer.set_status_text("원격 화면을 기다리는 중...")
            self.btn_connect.setEnabled(True)
            self.btn_connect.setText("연결")
            self.btn_connect.setObjectName("primaryButton")
            self.btn_connect.setStyleSheet("")
            self.setStyleSheet(QSS_STYLESHEET)
            QMessageBox.critical(self, "연결 오류", f"{ip}:{port}에 연결할 수 없습니다.\n오류: {e}")

    async def disconnect_client_async(self):
        await self.client.disconnect()

    def handle_client_status_update(self, message: str):
        if "연결이 해제되었습니다" in message or "연결 실패" in message or "연결이 종료되었습니다" in message:
            self.handle_client_closed()

    def handle_client_stats_update(self, fps: float, kb_s: float, latency: float):
        host_type = "Windows PC" if self.client.is_windows_host else "안드로이드"
        stats_text = f"연결됨 ({host_type})"
        self.lbl_client_status.setText(stats_text)

    def handle_client_closed(self):
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText("연결")
        self.btn_connect.setObjectName("primaryButton")
        self.btn_connect.setStyleSheet("")
        self.btn_menu_receive.show()
        self.setStyleSheet(QSS_STYLESHEET)

        self.lbl_client_status.setText("오프라인")
        self.lbl_client_status.setStyleSheet("color: #ef4444; font-size: 10px; font-weight: bold; margin-top: 2px;")

        self.client.set_callbacks(None, None, None)

        # 뷰어 초기화
        self.viewer.current_pixmap = None
        self.viewer.set_status_text("원격 화면을 기다리는 중...")

        # 연결 해제 시 설정창 복원
        self.exit_fullscreen()

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        is_esc = (key == Qt.Key_Escape)
        is_ctrl_c = (key == Qt.Key_C and (modifiers & Qt.ControlModifier))
        
        if self.isFullScreen() and (is_esc or is_ctrl_c):
            self.exit_fullscreen()
            event.accept()
        elif event.key() == Qt.Key_F11 and self.client.is_connected:
            self.toggle_fullscreen()
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """
        Shuts down background server and active client connection before closing.
        """
        loop = asyncio.get_event_loop()
        
        # Stop hosting server
        if self.server.is_running:
            loop.run_until_complete(self.server.stop())
            
        # Disconnect client if active
        if self.client.is_connected:
            loop.run_until_complete(self.client.disconnect())
            
        event.accept()

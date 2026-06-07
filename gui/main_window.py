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
        self.setWindowTitle("TeleControl PC - 원격 데스크톱 제어")
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
        
        # Show maximized on startup
        self.showMaximized()

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Main layout is vertical (top header bar + content area)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 1. Top Header Bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)
        
        lbl_main_title = QLabel("TeleControl PC", self)
        lbl_main_title.setStyleSheet("font-size: 38px; font-weight: bold; color: white;")
        header_layout.addWidget(lbl_main_title)
        
        header_layout.addStretch(1)
        
        # Sidebar toggle button
        self.btn_toggle_sidebar = QPushButton("◀ 설정 창 접기", self)
        self.btn_toggle_sidebar.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_sidebar.setObjectName("backButton") # reuse style
        self.btn_toggle_sidebar.clicked.connect(self.toggle_sidebar)
        header_layout.addWidget(self.btn_toggle_sidebar)
        
        main_layout.addLayout(header_layout)
        
        # 2. Main Content Area (Splitter between Left Panel and Right Panel)
        self.main_splitter = QSplitter(Qt.Horizontal, self)
        self.main_splitter.setHandleWidth(8)
        main_layout.addWidget(self.main_splitter)
        
        # 3. Left Panel (Settings)
        self.left_panel = QFrame(self)
        self.left_panel.setObjectName("cardFrame")
        self.left_panel.setMinimumWidth(288)
        self.left_panel.setMaximumWidth(432)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(10, 20, 10, 20)
        left_layout.setSpacing(20)
        
        # Mode Button 1: 도움 받기
        self.btn_menu_receive = QPushButton("도움 받기", self)
        self.btn_menu_receive.setCursor(Qt.PointingHandCursor)
        self.btn_menu_receive.setFixedHeight(50)
        self.btn_menu_receive.setObjectName("btnHelpReceive")
        self.btn_menu_receive.clicked.connect(lambda: self.select_mode("host"))
        left_layout.addWidget(self.btn_menu_receive)
        
        # Mode Button 2: 도움 주기
        self.btn_menu_give = QPushButton("도움 주기", self)
        self.btn_menu_give.setCursor(Qt.PointingHandCursor)
        self.btn_menu_give.setFixedHeight(50)
        self.btn_menu_give.setObjectName("btnHelpGive")
        self.btn_menu_give.clicked.connect(lambda: self.select_mode("client"))
        left_layout.addWidget(self.btn_menu_give)
        
        # Host Container 1 (displays below both buttons)
        self.host_container = QWidget(self)
        self.init_left_host_page()
        left_layout.addWidget(self.host_container)
        
        # Client Container 2 (displays below both buttons)
        self.client_container = QWidget(self)
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
        
        self.main_splitter.addWidget(self.left_panel)
        
        # 4. Right Panel (Remote Viewer only)
        self.viewer = RemoteViewerWidget(self)
        self.viewer.set_client(self.client)
        self.main_splitter.addWidget(self.viewer)
        
        # Set splitter default sizes: left panel 342px, right panel fills rest
        self.main_splitter.setSizes([342, 800])
        
        # On startup, only show the two buttons (hide both menus initially)
        self.host_container.setVisible(False)
        self.client_container.setVisible(False)

    def init_left_host_page(self):
        layout = QVBoxLayout(self.host_container)
        layout.setContentsMargins(2, 15, 2, 15)
        layout.setSpacing(25)
        
        # Server Status Card
        status_card = QFrame()
        status_card.setObjectName("statusCard")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(12, 15, 12, 15)
        status_layout.setSpacing(10)
        
        status_title = QLabel("서버 상태", self)
        status_title.setStyleSheet("font-weight: bold; color: #a855f7; font-size: 28px; background: transparent;")
        status_layout.addWidget(status_title)
        
        status_layout.addStretch(1)
        
        self.lbl_server_status = QLabel("서버 중지됨", self)
        self.lbl_server_status.setStyleSheet("color: #ef4444; background-color: #08080c; border: 2px solid rgba(255, 255, 255, 0.12); border-radius: 12px; padding: 8px 20px; font-size: 28px; font-weight: bold; min-height: 50px;")
        self.lbl_server_status.setMinimumWidth(220)
        self.lbl_server_status.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.lbl_server_status)
        
        layout.addWidget(status_card)
        
        # Host IP Card
        ip_card = QFrame()
        ip_card.setObjectName("statusCard")
        ip_layout = QHBoxLayout(ip_card)
        ip_layout.setContentsMargins(12, 15, 12, 15)
        ip_layout.setSpacing(10)
        
        ip_title = QLabel("내 주소", self)
        ip_title.setStyleSheet("font-weight: bold; color: #818cf8; font-size: 28px; background: transparent;")
        ip_layout.addWidget(ip_title)
        
        ip_layout.addStretch(1)
        
        self.lbl_ip = QLabel(get_local_ip(), self)
        self.lbl_ip.setObjectName("ipLabel")
        self.lbl_ip.setMinimumWidth(220)
        self.lbl_ip.setAlignment(Qt.AlignCenter)
        ip_layout.addWidget(self.lbl_ip)
        
        layout.addWidget(ip_card)
        
        # Start Server Button
        self.btn_toggle_server = QPushButton("원격 도움 요청", self)
        self.btn_toggle_server.setObjectName("primaryButton")
        self.btn_toggle_server.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_server.clicked.connect(self.toggle_server)
        layout.addWidget(self.btn_toggle_server)

    def init_left_client_page(self):
        layout = QVBoxLayout(self.client_container)
        layout.setContentsMargins(2, 15, 2, 15)
        layout.setSpacing(25)
        
        # Connection Form - IP Card
        ip_frame = QFrame()
        ip_frame.setObjectName("cardFrame")
        ip_layout = QHBoxLayout(ip_frame)
        ip_layout.setContentsMargins(12, 15, 12, 15)
        ip_layout.setSpacing(10)
        
        lbl_ip_title = QLabel("원격 주소", self)
        lbl_ip_title.setStyleSheet("font-weight: bold; color: #818cf8; font-size: 28px; background: transparent;")
        
        self.edt_client_ip = QLineEdit(self)
        self.edt_client_ip.setPlaceholderText("예: 192.168.0.15")
        self.edt_client_ip.setMinimumWidth(220)
        self.edt_client_ip.setAlignment(Qt.AlignCenter)
        
        ip_layout.addWidget(lbl_ip_title)
        ip_layout.addStretch(1)
        ip_layout.addWidget(self.edt_client_ip)
        layout.addWidget(ip_frame)
        
        # Connection Form - Port Card
        port_frame = QFrame()
        port_frame.setObjectName("cardFrame")
        port_layout = QHBoxLayout(port_frame)
        port_layout.setContentsMargins(12, 15, 12, 15)
        port_layout.setSpacing(10)
        
        lbl_port_title = QLabel("원격 포트", self)
        lbl_port_title.setStyleSheet("font-weight: bold; color: #818cf8; font-size: 28px; background: transparent;")
        
        self.spn_client_port = QSpinBox(self)
        self.spn_client_port.setRange(1024, 65535)
        self.spn_client_port.setValue(8080)
        self.spn_client_port.setMinimumWidth(220)
        self.spn_client_port.setAlignment(Qt.AlignCenter)
        
        port_layout.addWidget(lbl_port_title)
        port_layout.addStretch(1)
        port_layout.addWidget(self.spn_client_port)
        layout.addWidget(port_frame)
        
        # Connect Button
        self.btn_connect = QPushButton("연결", self)
        self.btn_connect.setObjectName("primaryButton")
        self.btn_connect.setCursor(Qt.PointingHandCursor)
        self.btn_connect.clicked.connect(self.connect_to_server)
        layout.addWidget(self.btn_connect)
        
        # Client Status Label
        self.lbl_client_status = QLabel("오프라인", self)
        self.lbl_client_status.setStyleSheet("color: #ef4444; font-size: 18px; font-weight: bold;")
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

    def toggle_sidebar(self):
        is_visible = self.left_panel.isVisible()
        self.left_panel.setVisible(not is_visible)
        if is_visible:
            self.btn_toggle_sidebar.setText("▶ 설정 창 펴기")
        else:
            self.btn_toggle_sidebar.setText("◀ 설정 창 접기")

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
            self.lbl_server_status.setStyleSheet("color: #22c55e; background-color: #08080c; border: 2px solid rgba(255, 255, 255, 0.12); border-radius: 12px; padding: 8px 20px; font-size: 28px; font-weight: bold; min-height: 50px; qproperty-alignment: AlignCenter;")
            self.btn_toggle_server.setText("원격 도움 중지")
            self.btn_toggle_server.setObjectName("dangerButton")
            self.btn_toggle_server.setStyleSheet("")
            self.setStyleSheet(QSS_STYLESHEET)
        except Exception as e:
            QMessageBox.critical(self, "서버 오류", f"서버를 시작하지 못했습니다:\n{e}")
    async def stop_server_async(self):
        await self.server.stop()
        self.lbl_server_status.setText("서버 중지됨")
        self.lbl_server_status.setStyleSheet("color: #ef4444; background-color: #08080c; border: 2px solid rgba(255, 255, 255, 0.12); border-radius: 12px; padding: 8px 20px; font-size: 28px; font-weight: bold; min-height: 50px; qproperty-alignment: AlignCenter;")
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
        self.setStyleSheet(QSS_STYLESHEET)

        self.lbl_client_status.setText("오프라인")
        self.lbl_client_status.setStyleSheet("color: #ef4444; font-size: 14px; font-weight: bold; margin-top: 5px;")

        self.client.set_callbacks(None, None, None)

        # 뷰어 초기화
        self.viewer.current_pixmap = None
        self.viewer.set_status_text("원격 화면을 기다리는 중...")

        # 연결 해제 시 설정창 복원
        self.left_panel.setVisible(True)
        self.btn_toggle_sidebar.setText("◀ 설정 창 접기")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11 and self.client.is_connected:
            is_fullscreen = getattr(self, "is_fullscreen_mode", False)
            if not is_fullscreen:
                self.showFullScreen()
                self.is_fullscreen_mode = True
            else:
                self.showNormal()
                self.is_fullscreen_mode = False
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

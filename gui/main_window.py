import socket
import asyncio
import os
import json
import logging
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox,
    QMessageBox, QFrame, QSplitter, QApplication,
    QDialog, QDialogButtonBox, QFormLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

import config as app_config

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
        self.server.set_id_callback(self.handle_server_id_received)
        
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

        # Relay Server settings button
        self.btn_settings = QPushButton("⚙ 서버 설정", self.header_widget)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setObjectName("fullscreenButton")
        self.btn_settings.clicked.connect(self.open_settings_dialog)
        header_layout.addWidget(self.btn_settings)

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
        
        # Pre-fill Client Connection ID if history exists
        if self.history:
            try:
                conn_id = self.history[0]
                self.edt_connection_id.setText(conn_id)
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
        
        ip_title = QLabel("연결 ID", ip_card)
        ip_title.setStyleSheet("font-weight: bold; color: #818cf8; font-size: 11px; background: transparent;")
        ip_layout.addWidget(ip_title)
        
        self.lbl_ip = QLabel("------", ip_card)
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
        
        # Connection Form - ID Card
        id_frame = QFrame(self.client_container)
        id_frame.setObjectName("statusCard")
        id_layout = QVBoxLayout(id_frame)
        id_layout.setContentsMargins(5, 5, 5, 5)
        id_layout.setSpacing(3)
        
        lbl_id_title = QLabel("원격 연결 ID", id_frame)
        lbl_id_title.setStyleSheet("font-weight: bold; color: #818cf8; font-size: 11px; background: transparent;")
        
        self.edt_connection_id = QLineEdit(id_frame)
        self.edt_connection_id.setPlaceholderText("6자리 번호 입력")
        self.edt_connection_id.setAlignment(Qt.AlignCenter)
        
        id_layout.addWidget(lbl_id_title)
        id_layout.addWidget(self.edt_connection_id)
        layout.addWidget(id_frame)
        
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

    # Settings Dialog
    def open_settings_dialog(self):
        """
        릴레이 서버 IP와 포트를 설정하는 다이얼로그를 엽니다.
        """
        cfg = app_config.load_config()

        dialog = QDialog(self)
        dialog.setWindowTitle("릴레이 서버 설정")
        dialog.setMinimumWidth(360)
        dialog.setStyleSheet(self.styleSheet())

        form = QFormLayout(dialog)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)

        desc = QLabel(
            "AWS EC2 릴레이 서버의 IP 주소와 포트를 입력하세요.\n"
            "로컬 테스트 시에는 PC의 로컬 IP(예: 192.168.x.x)를,\n"
            "인터넷 연결 시에는 EC2 공인 IP를 입력합니다.",
            dialog
        )
        desc.setStyleSheet("color: #94a3b8; font-size: 10px; padding-bottom: 8px;")
        desc.setWordWrap(True)
        form.addRow(desc)

        edt_host = QLineEdit(cfg["relay_host"], dialog)
        edt_host.setPlaceholderText("예: 54.123.45.67 또는 127.0.0.1")
        form.addRow("릴레이 서버 IP:", edt_host)

        spn_port = QSpinBox(dialog)
        spn_port.setRange(1, 65535)
        spn_port.setValue(int(cfg["relay_port"]))
        form.addRow("포트:", spn_port)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            dialog
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec_() == QDialog.Accepted:
            new_host = edt_host.text().strip()
            new_port = spn_port.value()
            if not new_host:
                QMessageBox.warning(self, "입력 오류", "IP 주소를 입력하세요.")
                return
            app_config.save_config(new_host, new_port)
            logger.info(f"릴레이 서버 설정 변경: {new_host}:{new_port}")
            QMessageBox.information(
                self,
                "설정 저장 완료",
                f"릴레이 서버 주소가 저장되었습니다:\n{new_host}:{new_port}\n\n"
                "다음 연결 시도부터 적용됩니다."
            )

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

    def add_to_history(self, connection_id):
        if connection_id in self.history:
            self.history.remove(connection_id)
        self.history.insert(0, connection_id)
        self.history = self.history[:10]  # keep top 10
        self.save_history()

    # Host Action Handlers
    def append_server_log(self, message: str):
        logger.info(f"Server log: {message}")

    def handle_server_id_received(self, session_id: str):
        formatted_id = f"{session_id[:3]} {session_id[3:]}"
        self.lbl_ip.setText(formatted_id)

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

        # 최신 설정을 매번 파일에서 읽어 적용
        relay_host = app_config.get_relay_host()
        relay_port = app_config.get_relay_port()

        self.server.host = relay_host
        self.server.port = relay_port
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
            self.lbl_ip.setText("------")
            
    async def stop_server_async(self):
        await self.server.stop()
        self.lbl_server_status.setText("서버 중지됨")
        self.lbl_server_status.setStyleSheet("color: #ef4444; background-color: #08080c; border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 6px; padding: 2px 4px; font-size: 11px; font-weight: bold; min-height: 16px; qproperty-alignment: AlignCenter;")
        self.btn_toggle_server.setText("원격 도움 요청")
        self.btn_toggle_server.setObjectName("primaryButton")
        self.btn_toggle_server.setStyleSheet("")
        self.lbl_ip.setText("------")
        self.setStyleSheet(QSS_STYLESHEET)

    # Client Action Handlers
    def connect_to_server(self):
        if self.client.is_connected:
            asyncio.create_task(self.disconnect_client_async())
            return
            
        connection_id = self.edt_connection_id.text().strip().replace(" ", "")
        
        if not connection_id or len(connection_id) != 6 or not connection_id.isdigit():
            QMessageBox.warning(self, "입력 오류", "올바른 6자리 연결 ID를 입력하세요.")
            return
            
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("연결 시도 중...")
        
        asyncio.create_task(self.connect_to_server_async(connection_id))

    async def connect_to_server_async(self, connection_id: str):
        try:
            # 콜백 먼저 등록 후 연결 (연결 직후 핸드셰이크 메시지 수신 대비)
            self.client.set_callbacks(
                frame_cb=self.viewer.update_frame,
                status_cb=self.handle_client_status_update,
                stats_cb=self.handle_client_stats_update
            )

            # 뷰어에 연결 중 상태 표시
            self.viewer.set_status_text(f"릴레이 서버를 통해 [{connection_id}] 에 연결 중...")
            self.viewer.current_pixmap = None
            self.viewer.update()

            # 최신 릴레이 서버 설정 로드
            relay_host = app_config.get_relay_host()
            relay_port = app_config.get_relay_port()
            await self.client.connect(relay_host, relay_port, session_id=connection_id)

            # Save to history on successful connection
            self.add_to_history(connection_id)

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
            QMessageBox.critical(self, "연결 오류", f"ID [{connection_id}] 에 연결할 수 없습니다.\n오류: {e}")

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

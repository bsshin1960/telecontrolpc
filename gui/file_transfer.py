import os
import base64
import json
import logging
import string
import asyncio
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QPushButton, QLabel, QProgressBar,
    QMessageBox, QListWidgetItem, QFrame
)
from PyQt5.QtCore import Qt

logger = logging.getLogger("FileTransferDialog")

def get_drives():
    """
    윈도우 시스템에 존재하는 드라이브 문자 리스트를 반환합니다.
    """
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.append(drive)
    return drives

class ToastNotification(QDialog):
    def __init__(self, parent=None, text=""):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        layout = QVBoxLayout(self)
        label = QLabel(text, self)
        label.setStyleSheet("""
            background-color: rgba(229, 57, 53, 255);
            color: white;
            font-size: 16px;
            font-weight: bold;
            border-radius: 8px;
            padding: 12px 24px;
            border: 2px solid white;
        """)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.adjustSize()
        
        if parent:
            # Position at the exact center of parent in local coordinates
            x = (parent.width() - self.width()) // 2
            y = (parent.height() - self.height()) // 2
            self.move(x, y)
        
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(5000, self.close)

class FileTransferDialog(QDialog):
    def __init__(self, parent=None, is_client=True, send_cmd_fn=None):
        super().__init__(parent)
        self.is_client = is_client  # True = PC가 '도움 주기' (Client), False = PC가 '도움 받기' (Host/Server)
        self.send_cmd_fn = send_cmd_fn
        
        self.downloads_path = os.path.normpath(os.path.join(os.path.expanduser("~"), "Downloads"))
        
        # 탐색할 절대 경로 추적 (기본 시작은 Downloads 폴더)
        self.local_current_path = self.downloads_path
        self.remote_current_path = "Pending..."  # 스마트폰이 준비 완료되면 초기 경로를 전달받음
        self.is_cancelled = False
        self.active_receivers = {}
            
        self.setWindowTitle("파일 전송 탐색기 (File Transfer)")
        self.resize(1024, 720)
        
        # 최소화/최대화 버튼 활성화 (전체화면이 아닌 기본 크기로 열기)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        
        # 라이트 모드 테마 적용
        self.apply_light_theme()
        
        self.init_ui()
        self.refresh_local_list()
        self.request_remote_list()

    def apply_light_theme(self):
        style = """
        QDialog {
            background-color: #ffffff;
        }
        QLabel {
            color: #1e293b;
            font-size: 11px;
            background: transparent;
        }
        QFrame#cardFrame {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
        }
        QListWidget {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            color: #0f172a;
            font-size: 11px;
            padding: 4px;
        }
        QListWidget::item {
            padding: 6px;
            border-radius: 4px;
            color: #0f172a;
        }
        QListWidget::item:hover {
            background-color: #f1f5f9;
        }
        QListWidget::item:selected {
            background-color: #e0e7ff;
            color: #4f46e5;
            font-weight: bold;
        }
        QPushButton {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 5px 10px;
            color: #334155;
            font-weight: 600;
            font-size: 11px;
            min-height: 20px;
        }
        QPushButton:hover {
            background-color: #f1f5f9;
            border: 1px solid #94a3b8;
        }
        QPushButton#primaryButton {
            background-color: #4f46e5;
            color: #ffffff;
            border: none;
        }
        QPushButton#primaryButton:hover {
            background-color: #4338ca;
        }
        QPushButton#primaryButton:pressed {
            background-color: #3730a3;
        }
        QProgressBar {
            background-color: #f1f5f9;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            text-align: center;
            color: #1e293b;
        }
        QProgressBar::chunk {
            background-color: #4f46e5;
            border-radius: 4px;
        }
        """
        self.setStyleSheet(style)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)
        
        # Top Header Area
        header_layout = QHBoxLayout()
        self.lbl_status = QLabel("파일 전송 대기 중...", self)
        self.lbl_status.setStyleSheet("font-weight: bold; color: #7c3aed; font-size: 12px;")
        header_layout.addWidget(self.lbl_status)
        header_layout.addStretch(1)
        main_layout.addLayout(header_layout)
        
        # Splitter Layout (Left: 도움 받기, Right: 도움 주기)
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setStyleSheet("QSplitter::handle { background-color: #e2e8f0; width: 2px; }")
        
        # --- Left Pane: 도움 받기 ---
        left_widget = QFrame(self)
        left_widget.setFrameShape(QFrame.StyledPanel)
        left_widget.setObjectName("cardFrame")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(6)
        
        # Left Title & Path Info
        left_title_text = "도움 받기 (원격 스마트폰)" if self.is_client else "도움 받기 (로컬 PC)"
        lbl_left_title = QLabel(left_title_text, left_widget)
        lbl_left_title.setStyleSheet("font-weight: bold; color: #4f46e5; font-size: 12px;")
        left_layout.addWidget(lbl_left_title)
        
        self.lbl_left_path = QLabel("경로: Loading...", left_widget)
        self.lbl_left_path.setStyleSheet("color: #475569; font-size: 11px; font-weight: bold;")
        left_layout.addWidget(self.lbl_left_path)
        
        # Left List
        self.list_left = QListWidget(left_widget)
        left_layout.addWidget(self.list_left, 1) # stretch 1 to fill layout vertically
        
        # Left Button (Send left -> right)
        self.btn_left_to_right = QPushButton("오른쪽으로 전송 (도움 주기로) ➔", left_widget)
        self.btn_left_to_right.setObjectName("primaryButton")
        self.btn_left_to_right.clicked.connect(self.transfer_left_to_right)
        left_layout.addWidget(self.btn_left_to_right)
        
        # --- Right Pane: 도움 주기 ---
        right_widget = QFrame(self)
        right_widget.setFrameShape(QFrame.StyledPanel)
        right_widget.setObjectName("cardFrame")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(6)
        
        # Right Title & Path Info
        right_title_text = "도움 주기 (로컬 PC)" if self.is_client else "도움 주기 (원격 스마트폰)"
        lbl_right_title = QLabel(right_title_text, right_widget)
        lbl_right_title.setStyleSheet("font-weight: bold; color: #10b981; font-size: 12px;")
        right_layout.addWidget(lbl_right_title)
        
        self.lbl_right_path = QLabel("경로: Loading...", right_widget)
        self.lbl_right_path.setStyleSheet("color: #475569; font-size: 11px; font-weight: bold;")
        right_layout.addWidget(self.lbl_right_path)
        
        # Right List
        self.list_right = QListWidget(right_widget)
        right_layout.addWidget(self.list_right, 1) # stretch 1 to fill layout vertically
        
        # Right Button (Send right -> left)
        self.btn_right_to_left = QPushButton("⬅ 왼쪽으로 전송 (도움 받기로)", right_widget)
        self.btn_right_to_left.setObjectName("primaryButton")
        self.btn_right_to_left.clicked.connect(self.transfer_right_to_left)
        right_layout.addWidget(self.btn_right_to_left)
        
        # Add to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        main_layout.addWidget(splitter, 1) # stretch 1 to fill main layout vertically
        
        # Double Click Events for Folder Navigation
        self.list_left.itemDoubleClicked.connect(self.on_left_double_click)
        self.list_right.itemDoubleClicked.connect(self.on_right_double_click)
        
        # Bottom Progress Bar & Cancel Button
        bottom_layout = QHBoxLayout()
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(10)
        bottom_layout.addWidget(self.progress_bar, 1)
        
        self.btn_cancel_transfer = QPushButton("전송 중단", self)
        self.btn_cancel_transfer.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold; border: none;")
        self.btn_cancel_transfer.setVisible(False)
        self.btn_cancel_transfer.setFixedHeight(24)
        self.btn_cancel_transfer.clicked.connect(self.cancel_transfer)
        bottom_layout.addWidget(self.btn_cancel_transfer)
        
        main_layout.addLayout(bottom_layout)

    def refresh_all(self):
        self.refresh_local_list()
        self.request_remote_list()

    def refresh_local_list(self):
        """
        로컬 탐색 경로의 파일/폴더 목록을 갱신합니다.
        """
        list_widget = self.list_right if self.is_client else self.list_left
        path_label = self.lbl_right_path if self.is_client else self.lbl_left_path
        
        list_widget.clear()
        
        if self.local_current_path == "My PC":
            path_label.setText("경로: 내 PC (My PC)")
            try:
                drives = get_drives()
                for d in drives:
                    item = QListWidgetItem(f"📁 {d}")
                    item.setData(Qt.UserRole, {"name": d, "is_dir": True, "is_drive": True})
                    list_widget.addItem(item)
            except Exception as e:
                logger.error(f"Failed to load drives: {e}")
            return

        # 절대경로 갱신 및 검증
        self.local_current_path = os.path.normpath(self.local_current_path)
        path_label.setText(f"경로: {self.local_current_path}")
        
        # 상위 폴더 바로가기 추가
        item = QListWidgetItem("📁 .. (상위 폴더)")
        item.setData(Qt.UserRole, {"name": "..", "is_dir": True})
        list_widget.addItem(item)
            
        try:
            items = os.listdir(self.local_current_path)
            dirs = []
            files = []
            for item_name in items:
                try:
                    full_path = os.path.join(self.local_current_path, item_name)
                    if os.path.isdir(full_path):
                        dirs.append(item_name)
                    else:
                        files.append(item_name)
                except Exception:
                    # 권한 문제 등의 파일은 스킵
                    pass
                    
            dirs.sort()
            files.sort()
            
            for d in dirs:
                item = QListWidgetItem(f"📁 {d}")
                item.setData(Qt.UserRole, {"name": d, "is_dir": True})
                list_widget.addItem(item)
                
            for f in files:
                full_path = os.path.join(self.local_current_path, f)
                try:
                    size_kb = os.path.getsize(full_path) / 1024.0
                    item = QListWidgetItem(f"📄 {f} ({size_kb:.1f} KB)")
                    item.setData(Qt.UserRole, {"name": f, "is_dir": False})
                    list_widget.addItem(item)
                except Exception:
                    pass
                
        except Exception as e:
            logger.error(f"Failed to refresh local file list: {e}")
            self.lbl_status.setText(f"로컬 경로 읽기 오류: {e}")

    def request_remote_list(self):
        """
        원격 기기의 지정된 절대 경로 목록을 요청합니다.
        """
        self.lbl_status.setText("원격 기기의 파일 목록 불러오는 중...")
        req_path = self.remote_current_path if self.remote_current_path != "Pending..." else ""
        if self.send_cmd_fn:
            self.send_cmd_fn(f"FS_LIST_REQ|{req_path}")

    def update_remote_file_list(self, files):
        """
        원격 기기로부터 목록 수신 시 UI를 업데이트합니다.
        """
        list_widget = self.list_left if self.is_client else self.list_right
        path_label = self.lbl_left_path if self.is_client else self.lbl_right_path
        
        path_label.setText(f"경로: {self.remote_current_path}")
        list_widget.clear()
        
        # 안드로이드 최상위 내부 저장소 루트가 아니면 상위 폴더 추가
        # 보통 안드로이드 내부저장소 루트는 '/storage/emulated/0'
        if self.remote_current_path != "/storage/emulated/0" and self.remote_current_path != "/":
            item = QListWidgetItem("📁 .. (상위 폴더)")
            item.setData(Qt.UserRole, {"name": "..", "is_dir": True})
            list_widget.addItem(item)
            
        try:
            dirs = [f for f in files if f.get("is_dir", False)]
            file_items = [f for f in files if not f.get("is_dir", False)]
            
            dirs.sort(key=lambda x: x.get("name", ""))
            file_items.sort(key=lambda x: x.get("name", ""))
            
            for d in dirs:
                name = d.get("name", "")
                item = QListWidgetItem(f"📁 {name}")
                item.setData(Qt.UserRole, {"name": name, "is_dir": True})
                list_widget.addItem(item)
                
            for f in file_items:
                name = f.get("name", "")
                size = f.get("size", 0)
                size_kb = size / 1024.0
                item = QListWidgetItem(f"📄 {name} ({size_kb:.1f} KB)")
                item.setData(Qt.UserRole, {"name": name, "is_dir": False})
                list_widget.addItem(item)
                
            current_status = self.lbl_status.text()
            if current_status not in ["파일 전송 완료", "파일 수신 완료", "파일이 있습니다."]:
                self.lbl_status.setText("")
        except Exception as e:
            logger.error(f"Error updating remote list: {e}")
            self.lbl_status.setText("원격 목록 분석 실패")

    def on_left_double_click(self, item):
        self.handle_double_click(item, is_left=True)

    def on_right_double_click(self, item):
        self.handle_double_click(item, is_left=False)

    def handle_double_click(self, item, is_left):
        data = item.data(Qt.UserRole)
        if not data or not data.get("is_dir", False):
            return
            
        name = data.get("name", "")
        
        # 이 Pane이 로컬 영역인지 원격 영역인지 판단
        is_local_pane = (not self.is_client) if is_left else self.is_client
        
        if is_local_pane:
            if self.local_current_path == "My PC":
                # 드라이브 선택 진입
                self.local_current_path = name
            else:
                if name == "..":
                    parent = os.path.dirname(self.local_current_path)
                    # 만약 현재 경로가 드라이브 루트(예: C:\)인 상태에서 ..을 누르면 My PC로 이동
                    if parent == self.local_current_path or len(self.local_current_path) <= 3:
                        self.local_current_path = "My PC"
                    else:
                        self.local_current_path = parent
                else:
                    self.local_current_path = os.path.join(self.local_current_path, name)
            self.refresh_local_list()
        else:
            if self.remote_current_path == "Pending...":
                return
                
            if name == "..":
                if self.remote_current_path == "/storage/emulated/0" or self.remote_current_path == "/":
                    return # 최상위 제한
                
                parts = self.remote_current_path.rstrip("/").split("/")
                if len(parts) > 1:
                    self.remote_current_path = "/".join(parts[:-1])
                else:
                    self.remote_current_path = "/"
            else:
                self.remote_current_path = f"{self.remote_current_path}/{name}".replace("//", "/")
                
            self.request_remote_list()

    def transfer_left_to_right(self):
        list_widget = self.list_left
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "경고", "전송할 파일을 선택하세요.")
            return
            
        data = selected_items[0].data(Qt.UserRole)
        if data.get("is_dir", False):
            QMessageBox.warning(self, "경고", "폴더 전송은 지원하지 않습니다.")
            return
            
        filename = data.get("name")
        
        if self.is_client:
            # Pull: 원격(왼쪽) -> 로컬(오른쪽) 현재 폴더
            if self.local_current_path == "My PC":
                QMessageBox.warning(self, "경고", "드라이브 루트 화면(내 PC)에서는 직접 저장할 수 없습니다. 특정 폴더 안으로 이동해 주세요.")
                return
            src_path = f"{self.remote_current_path}/{filename}".replace("//", "/")
            self.lbl_status.setText(f"'{filename}' 다운로드 요청 중...")
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_REQ|{src_path}")
        else:
            # Push: 로컬(왼쪽) -> 원격(오른쪽) 현재 폴더
            if self.local_current_path == "My PC":
                return
            self.send_local_file(filename)

    def transfer_right_to_left(self):
        list_widget = self.list_right
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "경고", "전송할 파일을 선택하세요.")
            return
            
        data = selected_items[0].data(Qt.UserRole)
        if data.get("is_dir", False):
            QMessageBox.warning(self, "경고", "폴더 전송은 지원하지 않습니다.")
            return
            
        filename = data.get("name")
        
        if self.is_client:
            # Push: 로컬(오른쪽) -> 원격(왼쪽) 현재 폴더
            if self.local_current_path == "My PC":
                return
            self.send_local_file(filename)
        else:
            # Pull: 원격(오른쪽) -> 로컬(왼쪽) 현재 폴더
            if self.local_current_path == "My PC":
                QMessageBox.warning(self, "경고", "드라이브 루트 화면(내 PC)에서는 직접 저장할 수 없습니다. 특정 폴더 안으로 이동해 주세요.")
                return
            src_path = f"{self.remote_current_path}/{filename}".replace("//", "/")
            self.lbl_status.setText(f"'{filename}' 다운로드 요청 중...")
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_REQ|{src_path}")

    def send_local_file(self, filename):
        asyncio.create_task(self.send_local_file_async(filename))

    async def send_local_file_async(self, filename):
        full_path = os.path.normpath(os.path.join(self.local_current_path, filename))
        if not os.path.exists(full_path):
            QMessageBox.warning(self, "오류", "파일이 존재하지 않습니다.")
            return
            
        file_size = os.path.getsize(full_path)
        if file_size > 50 * 1024 * 1024:
            QMessageBox.warning(self, "경고", "50MB 이상의 파일은 전송할 수 없습니다.")
            return
            
        if file_size >= 10 * 1024 * 1024:
            if hasattr(self, "toast") and self.toast:
                try:
                    self.toast.close()
                except Exception:
                    pass
            self.toast = ToastNotification(self, "비용 발생 주의!")
            self.toast.show()

        self.lbl_status.setText(f"'{filename}' 전송 중...")
        self.progress_bar.setVisible(True)
        self.btn_cancel_transfer.setVisible(True)
        
        chunk_size = 512 * 1024  # 512KB
        total_chunks = (file_size + chunk_size - 1) // chunk_size
        self.progress_bar.setRange(0, total_chunks)
        self.progress_bar.setValue(0)
        
        self.is_cancelled = False
        success = False
        
        try:
            target_path = f"{self.remote_current_path}/{filename}".replace("//", "/")
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_START|{target_path}|{total_chunks}")
            
            with open(full_path, "rb") as f:
                chunk_idx = 0
                while True:
                    if self.is_cancelled:
                        if self.send_cmd_fn:
                            self.send_cmd_fn(f"FS_FILE_CANCEL|{filename}")
                        self.lbl_status.setText("전송 취소됨")
                        self.progress_bar.setVisible(False)
                        self.btn_cancel_transfer.setVisible(False)
                        return
                    
                    data = f.read(chunk_size)
                    if not data:
                        break
                    
                    base64_chunk = base64.b64encode(data).decode("utf-8")
                    if self.send_cmd_fn:
                        self.send_cmd_fn(f"FS_FILE_CHUNK|{filename}|{chunk_idx}|{base64_chunk}")
                    
                    chunk_idx += 1
                    self.lbl_status.setText(f"'{filename}' 파일 전송 중...")
                    
                    await asyncio.sleep(0.01)
                    
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_END|{filename}")
            self.lbl_status.setText(f"'{filename}' 전송 완료 대기 중...")
            success = True
        except Exception as e:
            logger.error(f"Failed to send file {filename}: {e}")
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_SEND_ERR|{filename}|{e}")
            QMessageBox.critical(self, "오류", f"파일 전송 실패: {e}")
            self.lbl_status.setText("파일 전송 실패")
        finally:
            if not success:
                self.progress_bar.setVisible(False)
                self.btn_cancel_transfer.setVisible(False)

    def handle_remote_file_requested(self, requested_path):
        """
        원격 기기에서 로컬 파일을 요청했을 때 전송합니다.
        """
        asyncio.create_task(self.send_requested_file_async(requested_path))

    async def send_requested_file_async(self, requested_path):
        if not os.path.exists(requested_path):
            logger.error(f"Requested file does not exist: {requested_path}")
            return
            
        filename = os.path.basename(requested_path)
        file_size = os.path.getsize(requested_path)
        
        self.lbl_status.setText(f"'{filename}' 전송 중...")
        self.progress_bar.setVisible(True)
        self.btn_cancel_transfer.setVisible(True)
        
        chunk_size = 512 * 1024  # 512KB
        total_chunks = (file_size + chunk_size - 1) // chunk_size
        self.progress_bar.setRange(0, total_chunks)
        self.progress_bar.setValue(0)
        
        self.is_cancelled = False
        success = False
        
        try:
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_START|{requested_path}|{total_chunks}")
            
            with open(requested_path, "rb") as f:
                chunk_idx = 0
                while True:
                    if self.is_cancelled:
                        if self.send_cmd_fn:
                            self.send_cmd_fn(f"FS_FILE_CANCEL|{filename}")
                        self.lbl_status.setText("전송 취소됨")
                        self.progress_bar.setVisible(False)
                        self.btn_cancel_transfer.setVisible(False)
                        return
                    
                    data = f.read(chunk_size)
                    if not data:
                        break
                    
                    base64_chunk = base64.b64encode(data).decode("utf-8")
                    if self.send_cmd_fn:
                        self.send_cmd_fn(f"FS_FILE_CHUNK|{filename}|{chunk_idx}|{base64_chunk}")
                    
                    chunk_idx += 1
                    self.lbl_status.setText(f"'{filename}' 파일 전송 중...")
                    
                    await asyncio.sleep(0.01)
                    
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_END|{filename}")
            self.lbl_status.setText(f"'{filename}' 전송 완료 대기 중...")
            success = True
        except Exception as e:
            logger.error(f"Failed to send requested file {requested_path}: {e}")
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_SEND_ERR|{filename}|{e}")
            self.lbl_status.setText("파일 전송 실패")
        finally:
            if not success:
                self.progress_bar.setVisible(False)
                self.btn_cancel_transfer.setVisible(False)

    def handle_file_start(self, target_path, total_chunks_str):
        try:
            total_chunks = int(total_chunks_str)
            filename = os.path.basename(target_path)
            
            if self.local_current_path == "My PC":
                full_path = os.path.normpath(os.path.join(self.downloads_path, filename))
            else:
                full_path = os.path.normpath(os.path.join(self.local_current_path, filename))
                
            if os.path.exists(full_path):
                self.lbl_status.setText("파일이 있습니다.")
                self.progress_bar.setVisible(False)
                self.btn_cancel_transfer.setVisible(False)
                if self.send_cmd_fn:
                    self.send_cmd_fn(f"FS_FILE_EXISTS|{filename}")
                return
                
            self.lbl_status.setText(f"'{filename}' 수신 중...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, total_chunks)
            self.progress_bar.setValue(0)
            self.btn_cancel_transfer.setVisible(True)
            
            tmp_path = full_path + ".tmp"
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                    
            os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
            
            self.active_receivers[filename] = {
                "total_chunks": total_chunks,
                "tmp_path": tmp_path,
                "final_path": full_path
            }
        except Exception as e:
            logger.error(f"Error handling file start: {e}")
            self.lbl_status.setText("수신 시작 실패")

    def handle_file_chunk(self, filename, chunk_idx_str, base64_chunk):
        try:
            chunk_idx = int(chunk_idx_str)
            receiver = self.active_receivers.get(filename)
            if not receiver:
                return
                
            tmp_path = receiver["tmp_path"]
            data = base64.b64decode(base64_chunk)
            
            with open(tmp_path, "ab") as f:
                f.write(data)
                
            self.progress_bar.setValue(chunk_idx + 1)
            self.lbl_status.setText(f"'{filename}' 수신 중 ({chunk_idx + 1}/{receiver['total_chunks']})...")
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_PROGRESS|{filename}|{chunk_idx}")
        except Exception as e:
            logger.error(f"Error handling file chunk: {e}")

    def handle_file_end(self, filename):
        try:
            receiver = self.active_receivers.pop(filename, None)
            if not receiver:
                return
                
            tmp_path = receiver["tmp_path"]
            final_path = receiver["final_path"]
            
            if os.path.exists(tmp_path):
                if os.path.exists(final_path):
                    try:
                        os.remove(final_path)
                    except Exception:
                        pass
                os.rename(tmp_path, final_path)
                
            self.lbl_status.setText("파일 수신 완료")
            self.progress_bar.setVisible(False)
            self.btn_cancel_transfer.setVisible(False)
            self.refresh_local_list()
            
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_SEND_OK|{filename}|{final_path}")
        except Exception as e:
            logger.error(f"Error handling file end: {e}")
            self.lbl_status.setText("수신 완료 처리 실패")
            self.progress_bar.setVisible(False)
            self.btn_cancel_transfer.setVisible(False)

    def handle_file_cancel(self, filename):
        try:
            receiver = self.active_receivers.pop(filename, None)
            if receiver:
                tmp_path = receiver["tmp_path"]
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
            self.lbl_status.setText("전송 취소됨")
            self.progress_bar.setVisible(False)
            self.btn_cancel_transfer.setVisible(False)
        except Exception as e:
            logger.error(f"Error handling file cancel: {e}")

    def handle_file_progress(self, filename, chunk_idx_str):
        try:
            chunk_idx = int(chunk_idx_str)
            self.progress_bar.setValue(chunk_idx + 1)
            self.lbl_status.setText(f"'{filename}' 파일 전송 중 ({chunk_idx + 1}/{self.progress_bar.maximum()})...")
        except Exception as e:
            logger.error(f"Error handling progress: {e}")

    def cancel_transfer(self):
        self.is_cancelled = True
        for filename, receiver in list(self.active_receivers.items()):
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_CANCEL|{filename}")
            tmp_path = receiver["tmp_path"]
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        self.active_receivers.clear()
        
        self.lbl_status.setText("전송 취소됨")
        self.progress_bar.setVisible(False)
        self.btn_cancel_transfer.setVisible(False)

    def closeEvent(self, event):
        self.cancel_transfer()
        if self.send_cmd_fn:
            self.send_cmd_fn("FS_CLOSE_UI")
        event.accept()

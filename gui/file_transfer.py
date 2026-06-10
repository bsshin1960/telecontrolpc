import os
import base64
import json
import logging
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QPushButton, QLabel, QProgressBar,
    QMessageBox, QListWidgetItem, QFrame
)
from PyQt5.QtCore import Qt

logger = logging.getLogger("FileTransferDialog")

class FileTransferDialog(QDialog):
    def __init__(self, parent=None, is_client=True, send_cmd_fn=None):
        super().__init__(parent)
        self.is_client = is_client  # True = PC가 '도움 주기' (Client), False = PC가 '도움 받기' (Host/Server)
        self.send_cmd_fn = send_cmd_fn
        
        self.downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.exists(self.downloads_path):
            os.makedirs(self.downloads_path, exist_ok=True)
            
        self.setWindowTitle("파일 전송 (File Transfer)")
        self.resize(700, 480)
        if parent:
            self.setStyleSheet(parent.styleSheet())
            
        self.init_ui()
        self.refresh_local_list()
        self.request_remote_list()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
        # Top Header Area
        header_layout = QHBoxLayout()
        self.lbl_status = QLabel("파일 전송 대기 중...", self)
        self.lbl_status.setStyleSheet("font-weight: bold; color: #a855f7;")
        
        btn_refresh = QPushButton("🔄 새로고침", self)
        btn_refresh.setFixedWidth(90)
        btn_refresh.clicked.connect(self.refresh_all)
        
        header_layout.addWidget(self.lbl_status)
        header_layout.addStretch(1)
        header_layout.addWidget(btn_refresh)
        main_layout.addLayout(header_layout)
        
        # Splitter Layout (Left: 도움 받기, Right: 도움 주기)
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setStyleSheet("QSplitter::handle { background-color: rgba(255, 255, 255, 0.08); width: 2px; }")
        
        # --- Left Pane: 도움 받기 ---
        left_widget = QFrame(self)
        left_widget.setFrameShape(QFrame.StyledPanel)
        left_widget.setObjectName("cardFrame")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)
        
        # Left Title
        left_title_text = "도움 받기 (원격 스마트폰)" if self.is_client else "도움 받기 (로컬 PC)"
        lbl_left_title = QLabel(left_title_text, left_widget)
        lbl_left_title.setStyleSheet("font-weight: bold; color: #818cf8; font-size: 11px;")
        left_layout.addWidget(lbl_left_title)
        
        # Left List
        self.list_left = QListWidget(left_widget)
        left_layout.addWidget(self.list_left)
        
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
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)
        
        # Right Title
        right_title_text = "도움 주기 (로컬 PC)" if self.is_client else "도움 주기 (원격 스마트폰)"
        lbl_right_title = QLabel(right_title_text, right_widget)
        lbl_right_title.setStyleSheet("font-weight: bold; color: #34d399; font-size: 11px;")
        right_layout.addWidget(lbl_right_title)
        
        # Right List
        self.list_right = QListWidget(right_widget)
        right_layout.addWidget(self.list_right)
        
        # Right Button (Send right -> left)
        self.btn_right_to_left = QPushButton("⬅ 왼쪽으로 전송 (도움 받기로)", right_widget)
        self.btn_right_to_left.setObjectName("primaryButton")
        self.btn_right_to_left.clicked.connect(self.transfer_right_to_left)
        right_layout.addWidget(self.btn_right_to_left)
        
        # Add to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        main_layout.addWidget(splitter)
        
        # Bottom Progress & Control Bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e1e2f;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #6366f1;
                border-radius: 4px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

    def refresh_all(self):
        self.refresh_local_list()
        self.request_remote_list()

    def refresh_local_list(self):
        """
        Loads the list of files in the local downloads directory.
        """
        list_widget = self.list_right if self.is_client else self.list_left
        list_widget.clear()
        
        try:
            files = os.listdir(self.downloads_path)
            for f in files:
                full_path = os.path.join(self.downloads_path, f)
                if os.path.isfile(full_path):
                    size_kb = os.path.getsize(full_path) / 1024.0
                    item = QListWidgetItem(f"{f} ({size_kb:.1f} KB)")
                    item.setData(Qt.UserRole, f)  # Store pure filename
                    list_widget.addItem(item)
        except Exception as e:
            logger.error(f"Failed to refresh local file list: {e}")

    def request_remote_list(self):
        """
        Sends FS_LIST_REQ to the remote device to get its downloads directory list.
        """
        self.lbl_status.setText("원격 기기의 파일 목록 불러오는 중...")
        if self.send_cmd_fn:
            self.send_cmd_fn("FS_LIST_REQ")

    def update_remote_file_list(self, files):
        """
        Updates the remote side's list widget (called when FS_LIST_RESP is received).
        """
        list_widget = self.list_left if self.is_client else self.list_right
        list_widget.clear()
        
        for f in files:
            name = f.get("name", "")
            size = f.get("size", 0)
            size_kb = size / 1024.0
            item = QListWidgetItem(f"{name} ({size_kb:.1f} KB)")
            item.setData(Qt.UserRole, name)
            list_widget.addItem(item)
            
        self.lbl_status.setText("파일 목록이 동기화되었습니다.")

    def transfer_left_to_right(self):
        """
        Left -> Right Transfer:
        - If client mode (local is Right, remote is Left): Pull file from remote to local.
        - If server mode (local is Left, remote is Right): Send local file from Left to remote Right.
        """
        list_widget = self.list_left
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "경고", "전송할 파일을 선택하세요.")
            return
            
        filename = selected_items[0].data(Qt.UserRole)
        
        if self.is_client:
            # Pull file from Remote Phone (Left) to Local PC (Right)
            self.lbl_status.setText(f"'{filename}' 다운로드 요청 중...")
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_REQ|{filename}")
        else:
            # Send file from Local PC (Left) to Remote Phone (Right)
            self.send_local_file(filename)

    def transfer_right_to_left(self):
        """
        Right -> Left Transfer:
        - If client mode (local is Right, remote is Left): Send local file from Right to remote Left.
        - If server mode (local is Left, remote is Right): Pull file from remote Right to local Left.
        """
        list_widget = self.list_right
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "경고", "전송할 파일을 선택하세요.")
            return
            
        filename = selected_items[0].data(Qt.UserRole)
        
        if self.is_client:
            # Send file from Local PC (Right) to Remote Phone (Left)
            self.send_local_file(filename)
        else:
            # Pull file from Remote Phone (Right) to Local PC (Left)
            self.lbl_status.setText(f"'{filename}' 다운로드 요청 중...")
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_REQ|{filename}")

    def send_local_file(self, filename):
        full_path = os.path.join(self.downloads_path, filename)
        if not os.path.exists(full_path):
            QMessageBox.warning(self, "오류", "파일이 존재하지 않습니다.")
            return
            
        file_size = os.path.getsize(full_path)
        if file_size > 10 * 1024 * 1024:
            QMessageBox.warning(self, "경고", "10MB 이상의 파일은 전송할 수 없습니다.")
            return
            
        self.lbl_status.setText(f"'{filename}' 전송 중...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0) # Infinite animation during transmission
        
        try:
            with open(full_path, "rb") as f:
                data = f.read()
            base64_data = base64.b64encode(data).decode("utf-8")
            
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_SEND|{filename}|{base64_data}")
                self.lbl_status.setText(f"'{filename}' 전송 완료!")
        except Exception as e:
            logger.error(f"Failed to send file {filename}: {e}")
            QMessageBox.critical(self, "오류", f"파일 전송 실패: {e}")
            self.lbl_status.setText("파일 전송 실패")
        finally:
            self.progress_bar.setVisible(False)

    def handle_remote_file_received(self, filename, base64_data):
        """
        Called when a remote file is sent to the local downloads directory.
        """
        try:
            self.lbl_status.setText(f"'{filename}' 수신 및 저장 중...")
            full_path = os.path.join(self.downloads_path, filename)
            data = base64.b64decode(base64_data)
            
            with open(full_path, "wb") as f:
                f.write(data)
                
            self.lbl_status.setText(f"'{filename}' 저장 완료!")
            self.refresh_local_list()
        except Exception as e:
            logger.error(f"Failed to save received file {filename}: {e}")
            self.lbl_status.setText("파일 저장 실패")

    def handle_remote_file_requested(self, filename):
        """
        Called when the remote side requests a file from the local downloads directory.
        """
        full_path = os.path.join(self.downloads_path, filename)
        if not os.path.exists(full_path):
            logger.error(f"Requested file does not exist: {filename}")
            return
            
        try:
            with open(full_path, "rb") as f:
                data = f.read()
            base64_data = base64.b64encode(data).decode("utf-8")
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_SEND|{filename}|{base64_data}")
        except Exception as e:
            logger.error(f"Failed to read and send requested file {filename}: {e}")

    def closeEvent(self, event):
        # Notify other side to close UI as well
        if self.send_cmd_fn:
            self.send_cmd_fn("FS_CLOSE_UI")
        event.accept()

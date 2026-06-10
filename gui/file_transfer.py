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
        
        self.downloads_path = os.path.normpath(os.path.join(os.path.expanduser("~"), "Downloads"))
        if not os.path.exists(self.downloads_path):
            os.makedirs(self.downloads_path, exist_ok=True)
            
        # 탐색할 상대 경로 추적 (Downloads 기준 상대 경로, 비어 있으면 Downloads 루트)
        self.local_rel_path = ""
        self.remote_rel_path = ""
            
        self.setWindowTitle("파일 전송 탐색기 (File Transfer)")
        self.resize(800, 520)
        
        # 라이트 모드 (흰 바탕, 검정 글씨) 스타일 적용
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
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
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
        left_layout.setSpacing(8)
        
        # Left Title & Path Info
        left_title_text = "도움 받기 (원격 스마트폰)" if self.is_client else "도움 받기 (로컬 PC)"
        lbl_left_title = QLabel(left_title_text, left_widget)
        lbl_left_title.setStyleSheet("font-weight: bold; color: #4f46e5; font-size: 12px;")
        left_layout.addWidget(lbl_left_title)
        
        self.lbl_left_path = QLabel("경로: Downloads", left_widget)
        self.lbl_left_path.setStyleSheet("color: #64748b; font-size: 10px;")
        left_layout.addWidget(self.lbl_left_path)
        
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
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8)
        
        # Right Title & Path Info
        right_title_text = "도움 주기 (로컬 PC)" if self.is_client else "도움 주기 (원격 스마트폰)"
        lbl_right_title = QLabel(right_title_text, right_widget)
        lbl_right_title.setStyleSheet("font-weight: bold; color: #10b981; font-size: 12px;")
        right_layout.addWidget(lbl_right_title)
        
        self.lbl_right_path = QLabel("경로: Downloads", right_widget)
        self.lbl_right_path.setStyleSheet("color: #64748b; font-size: 10px;")
        right_layout.addWidget(self.lbl_right_path)
        
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
        
        # Double Click Events for Folder Navigation
        self.list_left.itemDoubleClicked.connect(self.on_left_double_click)
        self.list_right.itemDoubleClicked.connect(self.on_right_double_click)
        
        # Bottom Progress & Control Bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(10)
        main_layout.addWidget(self.progress_bar)

    def refresh_all(self):
        self.refresh_local_list()
        self.request_remote_list()

    def refresh_local_list(self):
        """
        로컬 탐색 경로의 파일/폴더 목록을 갱신합니다.
        """
        list_widget = self.list_right if self.is_client else self.list_left
        path_label = self.lbl_right_path if self.is_client else self.lbl_left_path
        
        # 절대경로 확인 및 상위 탈출 차단
        current_rel = self.local_rel_path
        abs_path = os.path.normpath(os.path.join(self.downloads_path, current_rel))
        if not abs_path.startswith(self.downloads_path):
            abs_path = self.downloads_path
            self.local_rel_path = ""
            current_rel = ""
            
        path_label.setText(f"경로: Downloads/{current_rel}" if current_rel else "경로: Downloads")
        list_widget.clear()
        
        # 상위 폴더 바로가기 추가
        if current_rel:
            item = QListWidgetItem("📁 .. (상위 폴더)")
            item.setData(Qt.UserRole, {"name": "..", "is_dir": True})
            list_widget.addItem(item)
            
        try:
            items = os.listdir(abs_path)
            # 폴더와 파일 분리 정렬
            dirs = []
            files = []
            for item_name in items:
                full_path = os.path.join(abs_path, item_name)
                if os.path.isdir(full_path):
                    dirs.append(item_name)
                else:
                    files.append(item_name)
                    
            dirs.sort()
            files.sort()
            
            # 폴더 추가
            for d in dirs:
                item = QListWidgetItem(f"📁 {d}")
                item.setData(Qt.UserRole, {"name": d, "is_dir": True})
                list_widget.addItem(item)
                
            # 파일 추가
            for f in files:
                full_path = os.path.join(abs_path, f)
                size_kb = os.path.getsize(full_path) / 1024.0
                item = QListWidgetItem(f"📄 {f} ({size_kb:.1f} KB)")
                item.setData(Qt.UserRole, {"name": f, "is_dir": False})
                list_widget.addItem(item)
                
        except Exception as e:
            logger.error(f"Failed to refresh local file list: {e}")
            self.lbl_status.setText(f"로컬 경로 읽기 오류: {e}")

    def request_remote_list(self):
        """
        원격 기기의 지정된 상대 경로 목록을 요청합니다.
        """
        self.lbl_status.setText("원격 기기의 파일 목록 불러오는 중...")
        if self.send_cmd_fn:
            self.send_cmd_fn(f"FS_LIST_REQ|{self.remote_rel_path}")

    def update_remote_file_list(self, files):
        """
        원격 기기로부터 목록 수신 시 UI를 업데이트합니다 (FS_LIST_RESP 수신 시 호출).
        """
        list_widget = self.list_left if self.is_client else self.list_right
        path_label = self.lbl_left_path if self.is_client else self.lbl_right_path
        
        current_rel = self.remote_rel_path
        path_label.setText(f"경로: Downloads/{current_rel}" if current_rel else "경로: Downloads")
        list_widget.clear()
        
        # 상위 폴더 바로가기 추가
        if current_rel:
            item = QListWidgetItem("📁 .. (상위 폴더)")
            item.setData(Qt.UserRole, {"name": "..", "is_dir": True})
            list_widget.addItem(item)
            
        try:
            # files: [{"name": "", "is_dir": bool, "size": int}]
            # 폴더와 파일 정렬
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
                
            self.lbl_status.setText("파일 목록이 동기화되었습니다.")
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
            return  # 파일은 더블클릭해도 아무 작업 안함
            
        name = data.get("name", "")
        
        # 이 Pane이 로컬 영역인지 원격 영역인지 판단
        is_local_pane = (not self.is_client) if is_left else self.is_client
        
        if is_local_pane:
            # 로컬 경로 변경
            if name == "..":
                parts = self.local_rel_path.replace("\\", "/").strip("/").split("/")
                self.local_rel_path = "/".join(parts[:-1]) if len(parts) > 1 else ""
            else:
                self.local_rel_path = f"{self.local_rel_path}/{name}".strip("/")
            self.refresh_local_list()
        else:
            # 원격 경로 변경
            if name == "..":
                parts = self.remote_rel_path.replace("\\", "/").strip("/").split("/")
                self.remote_rel_path = "/".join(parts[:-1]) if len(parts) > 1 else ""
            else:
                self.remote_rel_path = f"{self.remote_rel_path}/{name}".strip("/")
            self.request_remote_list()

    def transfer_left_to_right(self):
        """
        왼쪽 -> 오른쪽 전송:
        - 도움 주기(is_client=True)인 경우: 원격 폰(왼쪽)에서 로컬 PC(오른쪽)로 다운로드 (Pull)
        - 도움 받기(is_client=False)인 경우: 로컬 PC(왼쪽)에서 원격 폰(오른쪽)으로 업로드 (Push)
        """
        list_widget = self.list_left
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "경고", "전송할 파일을 선택하세요.")
            return
            
        data = selected_items[0].data(Qt.UserRole)
        if data.get("is_dir", False):
            QMessageBox.warning(self, "경고", "폴더 전송은 지원하지 않습니다. 파일만 전송 가능합니다.")
            return
            
        filename = data.get("name")
        
        if self.is_client:
            # Pull: 원격(왼쪽)에서 파일 요청해서 로컬(오른쪽) 현재 폴더에 저장
            src_path = f"{self.remote_rel_path}/{filename}".strip("/")
            self.lbl_status.setText(f"'{filename}' 다운로드 요청 중...")
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_REQ|{src_path}")
        else:
            # Push: 로컬(왼쪽)에서 원격(오른쪽) 현재 폴더로 전송
            self.send_local_file(filename)

    def transfer_right_to_left(self):
        """
        오른쪽 -> 왼쪽 전송:
        - 도움 주기(is_client=True)인 경우: 로컬 PC(오른쪽)에서 원격 폰(왼쪽)으로 업로드 (Push)
        - 도움 받기(is_client=False)인 경우: 원격 폰(오른쪽)에서 로컬 PC(왼쪽)로 다운로드 (Pull)
        """
        list_widget = self.list_right
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "경고", "전송할 파일을 선택하세요.")
            return
            
        data = selected_items[0].data(Qt.UserRole)
        if data.get("is_dir", False):
            QMessageBox.warning(self, "경고", "폴더 전송은 지원하지 않습니다. 파일만 전송 가능합니다.")
            return
            
        filename = data.get("name")
        
        if self.is_client:
            # Push: 로컬(오른쪽)에서 원격(왼쪽) 현재 폴더로 전송
            self.send_local_file(filename)
        else:
            # Pull: 원격(오른쪽)에서 파일 요청해서 로컬(왼쪽) 현재 폴더에 저장
            src_path = f"{self.remote_rel_path}/{filename}".strip("/")
            self.lbl_status.setText(f"'{filename}' 다운로드 요청 중...")
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_REQ|{src_path}")

    def send_local_file(self, filename):
        full_path = os.path.normpath(os.path.join(self.downloads_path, self.local_rel_path, filename))
        
        # 보안 검증: Downloads 폴더 외부 파일 접근 차단
        if not full_path.startswith(self.downloads_path):
            QMessageBox.warning(self, "오류", "잘못된 경로 접근입니다.")
            return
            
        if not os.path.exists(full_path):
            QMessageBox.warning(self, "오류", "파일이 존재하지 않습니다.")
            return
            
        file_size = os.path.getsize(full_path)
        if file_size > 10 * 1024 * 1024:
            QMessageBox.warning(self, "경고", "10MB 이상의 파일은 전송할 수 없습니다.")
            return
            
        self.lbl_status.setText(f"'{filename}' 전송 중...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        try:
            with open(full_path, "rb") as f:
                data = f.read()
            base64_data = base64.b64encode(data).decode("utf-8")
            
            # 상대방의 현재 디렉토리에 저장되도록 전송 경로 구성
            target_path = f"{self.remote_rel_path}/{filename}".strip("/")
            
            if self.send_cmd_fn:
                self.send_cmd_fn(f"FS_FILE_SEND|{target_path}|{base64_data}")
                self.lbl_status.setText(f"'{filename}' 전송 완료!")
        except Exception as e:
            logger.error(f"Failed to send file {filename}: {e}")
            QMessageBox.critical(self, "오류", f"파일 전송 실패: {e}")
            self.lbl_status.setText("파일 전송 실패")
        finally:
            self.progress_bar.setVisible(False)

    def handle_remote_file_received(self, target_path, base64_data):
        """
        원격에서 파일을 받아 로컬 탐색 경로 밑에 저장합니다.
        """
        try:
            filename = os.path.basename(target_path)
            self.lbl_status.setText(f"'{filename}' 수신 및 저장 중...")
            
            # 보안 경로 조립 및 검증
            full_path = os.path.normpath(os.path.join(self.downloads_path, self.local_rel_path, filename))
            if not full_path.startswith(self.downloads_path):
                logger.error("Path traversal attack detected on file receive!")
                self.lbl_status.setText("경로 오류로 수신이 거부되었습니다.")
                return
                
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            data = base64.b64decode(base64_data)
            
            with open(full_path, "wb") as f:
                f.write(data)
                
            self.lbl_status.setText(f"'{filename}' 저장 완료!")
            
            # 새로고침 자동 수행
            self.refresh_local_list()
        except Exception as e:
            logger.error(f"Failed to save received file: {e}")
            self.lbl_status.setText("파일 저장 실패")

    def handle_remote_file_requested(self, requested_path):
        """
        원격 기기에서 로컬 파일을 요청했을 때 전송합니다.
        """
        # 보안 경로 검증
        full_path = os.path.normpath(os.path.join(self.downloads_path, requested_path))
        if not full_path.startswith(self.downloads_path):
            logger.error("Path traversal attack detected on file request!")
            return
            
        if not os.path.exists(full_path):
            logger.error(f"Requested file does not exist: {requested_path}")
            return
            
        try:
            with open(full_path, "rb") as f:
                data = f.read()
            base64_data = base64.b64encode(data).decode("utf-8")
            if self.send_cmd_fn:
                # 상대방의 현재 상대 경로를 유지하여 전송하도록 상대경로 그대로 돌려줌
                self.send_cmd_fn(f"FS_FILE_SEND|{requested_path}|{base64_data}")
        except Exception as e:
            logger.error(f"Failed to read and send requested file {requested_path}: {e}")

    def closeEvent(self, event):
        if self.send_cmd_fn:
            self.send_cmd_fn("FS_CLOSE_UI")
        event.accept()

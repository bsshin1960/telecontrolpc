# Styling sheet for TeleControl PC Program
# Premium dark mode and glassmorphism styling
# High-DPI scaled with 3x larger text and elements for readability

QSS_STYLESHEET = """
/* Global Styles */
QWidget {
    background-color: #0d0d12;
    color: #f8fafc;
    font-family: 'Segoe UI', 'Outfit', 'Inter', -apple-system, sans-serif;
    font-size: 30px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #12121a;
    width: 16px;
    margin: 0px 0px 0px 0px;
    border-radius: 8px;
}
QScrollBar::handle:vertical {
    background: #3f3f56;
    min-height: 40px;
    border-radius: 8px;
}
QScrollBar::handle:vertical:hover {
    background: #6366f1;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #12121a;
    height: 16px;
    margin: 0px 0px 0px 0px;
    border-radius: 8px;
}
QScrollBar::handle:horizontal {
    background: #3f3f56;
    min-width: 40px;
    border-radius: 8px;
}
QScrollBar::handle:horizontal:hover {
    background: #6366f1;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Tab Widget styling */
QTabWidget::pane {
    border: 2px solid rgba(255, 255, 255, 0.08);
    background-color: rgba(22, 22, 30, 0.65);
    border-radius: 24px;
    top: -1px;
    padding: 25px;
}
QTabBar::tab {
    background-color: #161622;
    color: #94a3b8;
    border: 2px solid rgba(255, 255, 255, 0.05);
    border-bottom: none;
    border-top-left-radius: 20px;
    border-top-right-radius: 20px;
    padding: 20px 40px;
    margin-right: 8px;
    font-weight: 600;
    font-size: 30px;
}
QTabBar::tab:hover {
    background-color: #1e1e2f;
    color: #f8fafc;
}
QTabBar::tab:selected {
    background-color: rgba(22, 22, 30, 0.85);
    color: #6366f1;
    border: 2px solid rgba(99, 102, 241, 0.3);
    border-bottom: none;
}

/* Glassmorphism Cards */
QFrame#cardFrame {
    background-color: rgba(30, 30, 46, 0.45);
    border: 2px solid rgba(255, 255, 255, 0.08);
    border-radius: 28px;
}

QFrame#statusCard {
    background-color: rgba(99, 102, 241, 0.08);
    border: 2px solid rgba(99, 102, 241, 0.2);
    border-radius: 20px;
}

/* Labels */
QLabel {
    background: transparent;
}
QLabel#titleLabel {
    font-size: 54px;
    font-weight: 700;
    color: #ffffff;
    background: transparent;
    padding-bottom: 10px;
}
QLabel#subtitleLabel {
    font-size: 26px;
    color: #94a3b8;
    background: transparent;
}
QLabel#cardTitle {
    font-size: 34px;
    font-weight: 600;
    color: #e2e8f0;
}
QLabel#ipLabel {
    background-color: #08080c;
    border: 2px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    padding: 8px 20px;
    color: #818cf8;
    font-size: 32px;
    font-weight: bold;
    qproperty-alignment: AlignCenter;
    min-height: 50px;
}

/* Line Inputs */
QLineEdit {
    background-color: #08080c;
    border: 2px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    padding: 8px 20px;
    color: #818cf8;
    font-size: 32px;
    font-weight: bold;
    min-height: 50px;
    selection-background-color: #6366f1;
}
QLineEdit:focus {
    border: 2px solid #6366f1;
}

/* Combo Boxes */
QComboBox {
    background-color: #08080c;
    border: 2px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    padding: 8px 20px;
    color: #f8fafc;
    font-size: 32px;
    min-height: 50px;
    min-width: 8em;
}
QComboBox:focus {
    border: 2px solid #6366f1;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 35px;
    border-left-width: 0px;
}
QComboBox QAbstractItemView {
    background-color: #161622;
    border: 2px solid rgba(255, 255, 255, 0.1);
    selection-background-color: #6366f1;
    color: #f8fafc;
    font-size: 32px;
}

/* Spinbox */
QSpinBox {
    background-color: #08080c;
    border: 2px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    padding: 8px 20px;
    color: #818cf8;
    font-size: 32px;
    font-weight: bold;
    min-height: 50px;
}
QSpinBox:focus {
    border: 2px solid #6366f1;
}

/* Push Buttons (Normal) */
QPushButton {
    background-color: #1e1e2f;
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    padding: 16px 32px;
    color: #f8fafc;
    font-weight: 600;
    font-size: 30px;
    min-height: 55px;
}
QPushButton:hover {
    background-color: #2b2b40;
    border: 2px solid rgba(255, 255, 255, 0.2);
}
QPushButton:pressed {
    background-color: #161622;
}

/* Primary Accent Buttons */
QPushButton#primaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366f1, stop:1 #a855f7);
    color: white;
    border: none;
    border-radius: 14px;
    font-weight: bold;
    font-size: 32px;
    min-height: 60px;
}
QPushButton#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4f46e5, stop:1 #9333ea);
}
QPushButton#primaryButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3730a3, stop:1 #7e22ce);
}

/* Destructive / Alert Buttons */
QPushButton#dangerButton {
    background-color: #ef4444;
    color: white;
    border: none;
    border-radius: 14px;
    font-weight: bold;
    font-size: 32px;
    min-height: 60px;
}
QPushButton#dangerButton:hover {
    background-color: #dc2626;
}
QPushButton#dangerButton:pressed {
    background-color: #991b1b;
}

/* Active Clients/Logs Text Edit */
QTextEdit {
    background-color: #08080c;
    border: 2px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 15px;
    color: #94a3b8;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 26px;
}

/* Tables */
QTableWidget {
    background-color: #08080c;
    border: 2px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    gridline-color: rgba(255, 255, 255, 0.05);
}
QHeaderView::section {
    background-color: #161622;
    color: #94a3b8;
    padding: 12px;
    border: none;
    border-bottom: 2px solid rgba(255, 255, 255, 0.08);
    font-weight: bold;
    font-size: 28px;
}
QTableWidget::item {
    padding: 12px;
    color: #e2e8f0;
    font-size: 28px;
}
QTableWidget::item:selected {
    background-color: rgba(99, 102, 241, 0.25);
    color: white;
}

/* List Widget for history */
QListWidget {
    background-color: #08080c;
    border: 2px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 12px;
    color: #e2e8f0;
    font-size: 28px;
}
QListWidget::item {
    padding: 10px;
}
QListWidget::item:hover {
    background-color: rgba(255, 255, 255, 0.05);
    border-radius: 8px;
}
QListWidget::item:selected {
    background-color: rgba(99, 102, 241, 0.25);
    color: white;
}

/* Sliders */
QSlider::groove:horizontal {
    border: none;
    height: 12px;
    background: #1e1e2f;
    border-radius: 6px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #a855f7);
    border-radius: 6px;
}
QSlider::handle:horizontal {
    background: #ffffff;
    border: 3px solid #6366f1;
    width: 32px;
    height: 32px;
    margin-top: -10px;
    border-radius: 16px;
}
QSlider::handle:horizontal:hover {
    background: #6366f1;
    border: 3px solid #ffffff;
}

/* Main Menu Help Buttons (Matching Screenshot) */
QPushButton#btnHelpReceive {
    background-color: #5e00f5;
    color: white;
    border: none;
    border-radius: 18px;
    font-weight: bold;
    font-size: 32px;
    min-height: 50px;
}
QPushButton#btnHelpReceive:hover {
    background-color: #4800c7;
}
QPushButton#btnHelpReceive:pressed {
    background-color: #370098;
}

QPushButton#btnHelpGive {
    background-color: #15803d;
    color: white;
    border: none;
    border-radius: 18px;
    font-weight: bold;
    font-size: 32px;
    min-height: 50px;
}
QPushButton#btnHelpGive:hover {
    background-color: #166534;
}
QPushButton#btnHelpGive:pressed {
    background-color: #14532d;
}

/* Back Button */
QPushButton#backButton {
    background-color: #1e1e2f;
    border: 2px solid rgba(255, 255, 255, 0.15);
    border-radius: 14px;
    padding: 10px 24px;
    font-size: 26px;
    font-weight: bold;
}
QPushButton#backButton:hover {
    background-color: #2b2b40;
}
"""

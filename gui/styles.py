# Styling sheet for TeleControl Program
# Premium dark mode and glassmorphism styling
# Standard DPI scaling (reduced to 1/3 size from High-DPI version)

QSS_STYLESHEET = """
/* Global Styles */
QWidget {
    background-color: #0d0d12;
    color: #f8fafc;
    font-family: 'Segoe UI', 'Outfit', 'Inter', -apple-system, sans-serif;
    font-size: 11px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #12121a;
    width: 8px;
    margin: 0px 0px 0px 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #3f3f56;
    min-height: 15px;
    border-radius: 4px;
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
    height: 8px;
    margin: 0px 0px 0px 0px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #3f3f56;
    min-width: 15px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #6366f1;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Tab Widget styling */
QTabWidget::pane {
    border: 1px solid rgba(255, 255, 255, 0.08);
    background-color: rgba(22, 22, 30, 0.65);
    border-radius: 10px;
    top: -1px;
    padding: 10px;
}
QTabBar::tab {
    background-color: #161622;
    color: #94a3b8;
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 8px 16px;
    margin-right: 4px;
    font-weight: 600;
    font-size: 11px;
}
QTabBar::tab:hover {
    background-color: #1e1e2f;
    color: #f8fafc;
}
QTabBar::tab:selected {
    background-color: rgba(22, 22, 30, 0.85);
    color: #6366f1;
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-bottom: none;
}

/* Glassmorphism Cards */
QFrame#cardFrame {
    background-color: rgba(30, 30, 46, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
}

QFrame#statusCard {
    background-color: rgba(99, 102, 241, 0.08);
    border: 1px solid rgba(99, 102, 241, 0.2);
    border-radius: 8px;
}

/* Labels */
QLabel {
    background: transparent;
}
QLabel#titleLabel {
    font-size: 18px;
    font-weight: 700;
    color: #ffffff;
    background: transparent;
    padding-bottom: 4px;
}
QLabel#subtitleLabel {
    font-size: 10px;
    color: #94a3b8;
    background: transparent;
}
QLabel#cardTitle {
    font-size: 12px;
    font-weight: 600;
    color: #e2e8f0;
}
QLabel#ipLabel {
    background-color: #08080c;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 4px 6px;
    color: #ffffff;
    font-size: 15px;
    font-weight: bold;
    qproperty-alignment: AlignCenter;
    min-height: 22px;
}

/* Line Inputs */
QLineEdit {
    background-color: #08080c;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 4px 6px;
    color: #ffffff;
    font-size: 15px;
    font-weight: bold;
    min-height: 22px;
    selection-background-color: #6366f1;
}
QLineEdit:focus {
    border: 1px solid #6366f1;
}

/* Combo Boxes */
QComboBox {
    background-color: #08080c;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 4px 10px;
    color: #f8fafc;
    font-size: 11px;
    min-height: 24px;
    min-width: 8em;
}
QComboBox:focus {
    border: 1px solid #6366f1;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 15px;
    border-left-width: 0px;
}
QComboBox QAbstractItemView {
    background-color: #161622;
    border: 1px solid rgba(255, 255, 255, 0.1);
    selection-background-color: #6366f1;
    color: #f8fafc;
    font-size: 11px;
}

/* Spinbox */
QSpinBox {
    background-color: #08080c;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 4px 6px;
    color: #ffffff;
    font-size: 15px;
    font-weight: bold;
    min-height: 22px;
}
QSpinBox:focus {
    border: 1px solid #6366f1;
}

/* Push Buttons (Normal) */
QPushButton {
    background-color: #1e1e2f;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 3px 6px;
    color: #f8fafc;
    font-weight: 600;
    font-size: 11px;
    min-height: 16px;
}
QPushButton:hover {
    background-color: #2b2b40;
    border: 1px solid rgba(255, 255, 255, 0.2);
}
QPushButton:pressed {
    background-color: #161622;
}

/* Primary Accent Buttons */
QPushButton#primaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366f1, stop:1 #a855f7);
    color: white;
    border: none;
    border-radius: 6px;
    font-weight: bold;
    font-size: 11px;
    min-height: 24px;
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
    border-radius: 6px;
    font-weight: bold;
    font-size: 11px;
    min-height: 24px;
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
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 6px;
    color: #94a3b8;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 10px;
}

/* Tables */
QTableWidget {
    background-color: #08080c;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    gridline-color: rgba(255, 255, 255, 0.05);
}
QHeaderView::section {
    background-color: #161622;
    color: #94a3b8;
    padding: 4px;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    font-weight: bold;
    font-size: 10px;
}
QTableWidget::item {
    padding: 4px;
    color: #e2e8f0;
    font-size: 10px;
}
QTableWidget::item:selected {
    background-color: rgba(99, 102, 241, 0.25);
    color: white;
}

/* List Widget for history */
QListWidget {
    background-color: #08080c;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 4px;
    color: #e2e8f0;
    font-size: 10px;
}
QListWidget::item {
    padding: 4px;
}
QListWidget::item:hover {
    background-color: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: rgba(99, 102, 241, 0.25);
    color: white;
}

/* Sliders */
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #1e1e2f;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #a855f7);
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #ffffff;
    border: 1px solid #6366f1;
    width: 12px;
    height: 12px;
    margin-top: -4px;
    border-radius: 6px;
}
QSlider::handle:horizontal:hover {
    background: #6366f1;
    border: 1px solid #ffffff;
}

/* Main Menu Help Buttons (Matching Screenshot) */
QPushButton#btnHelpReceive {
    background-color: #5e00f5;
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: bold;
    font-size: 11px;
    min-height: 24px;
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
    border-radius: 8px;
    font-weight: bold;
    font-size: 11px;
    min-height: 24px;
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
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 10px;
    font-weight: bold;
}
QPushButton#backButton:hover {
    background-color: #2b2b40;
}

/* Fullscreen Button (1.4x larger font size) */
QPushButton#fullscreenButton {
    background-color: #1e1e2f;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 14px;
    font-weight: bold;
    color: #ffffff;
}
QPushButton#fullscreenButton:hover {
    background-color: #2b2b40;
    border: 1px solid rgba(255, 255, 255, 0.25);
}
"""

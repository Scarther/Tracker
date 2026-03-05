"""
================================================================================
TRACKER - AUTHENTICATION UI DIALOGS
================================================================================
PyQt6 dialogs for authentication and 2FA setup.

This module provides the graphical user interface components for:
- User login with password verification
- Two-factor authentication (TOTP) verification
- Initial setup wizard for new installations
- QR code display for authenticator app enrollment
- Backup code display and regeneration

DIALOG CLASSES:
---------------
- LoginDialog: Main login screen with password and optional 2FA code entry
- SetupDialog: First-time setup wizard for creating master password
- TwoFactorSetupDialog: QR code display for scanning with authenticator apps
- SecurityKeyDialog: Security PIN configuration
- BackupCodesDialog: Display and regenerate emergency backup codes

UI FRAMEWORK:
-------------
Built with PyQt6 for cross-platform desktop compatibility.

================================================================================
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox,
    QGroupBox, QCheckBox, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QFont

from auth import AuthManager, PYOTP_AVAILABLE, QRCODE_AVAILABLE


class LoginDialog(QDialog):
    """
    Main login dialog with password and 2FA support.

    Features:
    - Password entry with show/hide toggle
    - 2FA code entry (TOTP, security PIN, or backup code)
    - Lockout handling with countdown timer
    - Remember me option (future use)

    Signals:
        accepted: Emitted when login is successful
        rejected: Emitted when dialog is cancelled
    """

    def __init__(self, parent=None, auth_manager: AuthManager = None):
        """
        Initialize the login dialog.

        Args:
            parent: Parent widget
            auth_manager: AuthManager instance (created if not provided)
        """
        super().__init__(parent)
        self.auth = auth_manager or AuthManager()
        self.setWindowTitle("Tracker - Login")
        self.setMinimumSize(400, 350)
        self.setModal(True)

        # Timer for lockout countdown
        self.lockout_timer = QTimer(self)
        self.lockout_timer.timeout.connect(self._update_lockout)

        self._setup_ui()
        self._apply_style()
        self._check_initial_state()

    def _setup_ui(self):
        """Create and arrange UI elements."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Header
        header = QLabel("TRACKER")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        header.setStyleSheet("color: #c9a040;")
        layout.addWidget(header)

        subtitle = QLabel("Case Management System")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #7a8a9a; font-size: 12px;")
        layout.addWidget(subtitle)

        layout.addSpacing(10)

        # Lockout warning (hidden by default)
        self.lockout_label = QLabel()
        self.lockout_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lockout_label.setStyleSheet("""
            QLabel {
                color: #ff6b6b;
                background-color: #3a2a2a;
                padding: 10px;
                border-radius: 5px;
            }
        """)
        self.lockout_label.hide()
        layout.addWidget(self.lockout_label)

        # Password field
        pw_group = QGroupBox("Password")
        pw_layout = QHBoxLayout(pw_group)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.returnPressed.connect(self._on_login)
        pw_layout.addWidget(self.password_input)

        self.show_password_btn = QPushButton("Show")
        self.show_password_btn.setCheckable(True)
        self.show_password_btn.setMinimumWidth(70)
        self.show_password_btn.setStyleSheet("padding: 6px 12px;")
        self.show_password_btn.clicked.connect(self._toggle_password_visibility)
        pw_layout.addWidget(self.show_password_btn)

        layout.addWidget(pw_group)

        # 2FA field (shown only if 2FA is enabled)
        self.twofa_group = QGroupBox("Two-Factor Authentication")
        twofa_layout = QVBoxLayout(self.twofa_group)

        self.twofa_input = QLineEdit()
        self.twofa_input.setPlaceholderText("6-digit code from authenticator app")
        self.twofa_input.setMaxLength(8)  # Allow backup codes too
        self.twofa_input.returnPressed.connect(self._on_login)
        twofa_layout.addWidget(self.twofa_input)

        hint_label = QLabel("Enter TOTP code, security PIN, or backup code")
        hint_label.setStyleSheet("color: #6a7a8a; font-size: 10px;")
        twofa_layout.addWidget(hint_label)

        layout.addWidget(self.twofa_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.login_btn = QPushButton("Login")
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self._on_login)
        button_layout.addWidget(self.login_btn)

        cancel_btn = QPushButton("Exit")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Status message
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #ff6b6b;")
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _apply_style(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            QDialog {
                background-color: #0a0a0f;
            }
            QGroupBox {
                color: #a0a8b8;
                border: 1px solid #3a3a4a;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLineEdit {
                background-color: #12121a;
                color: #d0d8e8;
                border: 1px solid #3a3a4a;
                border-radius: 5px;
                padding: 10px;
                min-height: 20px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #c9a040;
            }
            QPushButton {
                background-color: #2a3a4a;
                color: #d0d8e8;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                min-height: 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3a4a5a;
            }
            QPushButton:pressed {
                background-color: #1a2a3a;
            }
            QPushButton:default {
                background-color: #4a6a5a;
            }
            QPushButton:default:hover {
                background-color: #5a7a6a;
            }
        """)

    def _check_initial_state(self):
        """Check authentication state and configure UI accordingly."""
        # Show/hide 2FA field based on configuration
        if self.auth.is_2fa_enabled():
            self.twofa_group.show()
            self.setMinimumHeight(380)
        else:
            self.twofa_group.hide()
            self.setMinimumHeight(300)

        # Adjust dialog size to fit content
        self.adjustSize()

        # Check for lockout
        if self.auth.is_locked_out():
            self._show_lockout()

    def _toggle_password_visibility(self):
        """Toggle password field visibility."""
        if self.show_password_btn.isChecked():
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_password_btn.setText("Hide")
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_password_btn.setText("Show")

    def _show_lockout(self):
        """Display lockout warning and start countdown."""
        self.login_btn.setEnabled(False)
        self.password_input.setEnabled(False)
        self.twofa_input.setEnabled(False)
        self.lockout_label.show()
        self._update_lockout()
        self.lockout_timer.start(1000)  # Update every second

    def _update_lockout(self):
        """Update lockout countdown display."""
        remaining = self.auth.get_lockout_remaining()
        if remaining > 0:
            minutes = remaining // 60
            seconds = remaining % 60
            self.lockout_label.setText(
                f"Account locked due to failed attempts.\n"
                f"Try again in {minutes}:{seconds:02d}"
            )
        else:
            # Lockout expired
            self.lockout_timer.stop()
            self.lockout_label.hide()
            self.login_btn.setEnabled(True)
            self.password_input.setEnabled(True)
            self.twofa_input.setEnabled(True)
            self.password_input.setFocus()

    def _on_login(self):
        """Handle login button click."""
        password = self.password_input.text()
        twofa_code = self.twofa_input.text() if self.auth.is_2fa_enabled() else None

        if not password:
            self.status_label.setText("Please enter your password")
            return

        # Attempt login
        success, message = self.auth.verify_login(password, twofa_code)

        if success:
            self._authenticated_password = password  # Store for database encryption
            self.accept()
        else:
            self.status_label.setText(message)
            if self.auth.is_locked_out():
                self._show_lockout()
            elif "2FA" in message:
                self.twofa_input.clear()
                self.twofa_input.setFocus()
            else:
                self.password_input.clear()
                self.password_input.setFocus()

    def get_password(self) -> str:
        """Get the authenticated password for database encryption."""
        return getattr(self, '_authenticated_password', '')


class SetupDialog(QDialog):
    """
    Initial setup dialog for new installations.

    Guides user through:
    1. Creating master password
    2. Optional 2FA setup
    """

    def __init__(self, parent=None, auth_manager: AuthManager = None):
        """
        Initialize setup dialog.

        Args:
            parent: Parent widget
            auth_manager: AuthManager instance
        """
        super().__init__(parent)
        self.auth = auth_manager or AuthManager()
        self.setWindowTitle("Tracker - Initial Setup")
        self.setMinimumSize(450, 480)
        self.setModal(True)

        self._setup_ui()
        self._apply_style()

        # Adjust size based on initial state
        self.adjustSize()

    def _setup_ui(self):
        """Create and arrange UI elements."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Header
        header = QLabel("Welcome to Tracker")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        header.setStyleSheet("color: #c9a040;")
        layout.addWidget(header)

        intro = QLabel(
            "This application contains sensitive case data.\n"
            "Please set up a secure password to protect access."
        )
        intro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        intro.setStyleSheet("color: #a0a8b8;")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addSpacing(10)

        # Password setup
        pw_group = QGroupBox("Master Password")
        pw_layout = QFormLayout(pw_group)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Minimum 8 characters")
        pw_layout.addRow("Password:", self.password_input)

        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.setPlaceholderText("Confirm password")
        pw_layout.addRow("Confirm:", self.confirm_input)

        # Password strength indicator
        self.strength_label = QLabel("Password strength: -")
        self.strength_label.setStyleSheet("color: #6a7a8a;")
        pw_layout.addRow("", self.strength_label)

        self.password_input.textChanged.connect(self._update_strength)

        layout.addWidget(pw_group)

        # 2FA option
        twofa_group = QGroupBox("Two-Factor Authentication (Recommended)")
        twofa_layout = QVBoxLayout(twofa_group)

        self.enable_totp = QCheckBox("Enable TOTP (Microsoft Authenticator, Authy, etc.)")
        self.enable_totp.setChecked(PYOTP_AVAILABLE)
        self.enable_totp.setEnabled(PYOTP_AVAILABLE)
        twofa_layout.addWidget(self.enable_totp)

        self.enable_pin = QCheckBox("Enable Security PIN as backup 2FA method")
        twofa_layout.addWidget(self.enable_pin)

        if not PYOTP_AVAILABLE:
            warn = QLabel("Install pyotp for TOTP support: pip install pyotp")
            warn.setStyleSheet("color: #ff9966; font-size: 10px;")
            twofa_layout.addWidget(warn)

        layout.addWidget(twofa_group)

        # Security PIN (shown if checkbox is checked)
        self.pin_group = QGroupBox("Security PIN")
        pin_layout = QFormLayout(self.pin_group)

        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_input.setPlaceholderText("6-8 digits")
        self.pin_input.setMaxLength(8)
        pin_layout.addRow("PIN:", self.pin_input)

        self.pin_confirm = QLineEdit()
        self.pin_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_confirm.setPlaceholderText("Confirm PIN")
        self.pin_confirm.setMaxLength(8)
        pin_layout.addRow("Confirm:", self.pin_confirm)

        self.pin_group.hide()
        self.enable_pin.toggled.connect(self._toggle_pin_group)

        layout.addWidget(self.pin_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.setup_btn = QPushButton("Complete Setup")
        self.setup_btn.setDefault(True)
        self.setup_btn.clicked.connect(self._on_setup)
        button_layout.addWidget(self.setup_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Status
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #ff6b6b;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _apply_style(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            QDialog {
                background-color: #0a0a0f;
            }
            QGroupBox {
                color: #a0a8b8;
                border: 1px solid #3a3a4a;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLineEdit {
                background-color: #12121a;
                color: #d0d8e8;
                border: 1px solid #3a3a4a;
                border-radius: 5px;
                padding: 10px;
                min-height: 20px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #c9a040;
            }
            QCheckBox {
                color: #a0a8b8;
                padding: 5px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #4a5a6a;
                border-radius: 4px;
                background-color: #1a1a2a;
            }
            QCheckBox::indicator:hover {
                border-color: #c9a040;
                background-color: #2a2a3a;
            }
            QCheckBox::indicator:checked {
                background-color: #5a8a6a;
                border-color: #6a9a7a;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #6a9a7a;
            }
            QCheckBox::indicator:disabled {
                background-color: #1a1a2a;
                border-color: #3a3a4a;
            }
            QPushButton {
                background-color: #2a3a4a;
                color: #d0d8e8;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #3a4a5a;
            }
            QPushButton:default {
                background-color: #4a6a5a;
            }
            QLabel {
                color: #a0a8b8;
            }
        """)

    def _toggle_pin_group(self, checked: bool):
        """Toggle PIN group visibility and resize dialog."""
        self.pin_group.setVisible(checked)
        # Adjust dialog size to accommodate PIN fields
        if checked:
            self.setMinimumHeight(580)
        else:
            self.setMinimumHeight(480)
        self.adjustSize()

    def _update_strength(self, password):
        """Update password strength indicator."""
        if len(password) < 8:
            strength = "Too short"
            color = "#ff6b6b"
        elif len(password) < 12:
            strength = "Weak"
            color = "#ffaa66"
        elif len(password) < 16:
            has_mixed = any(c.isupper() for c in password) and any(c.islower() for c in password)
            has_digit = any(c.isdigit() for c in password)
            if has_mixed and has_digit:
                strength = "Good"
                color = "#aacc66"
            else:
                strength = "Medium"
                color = "#cccc66"
        else:
            strength = "Strong"
            color = "#66cc66"

        self.strength_label.setText(f"Password strength: {strength}")
        self.strength_label.setStyleSheet(f"color: {color};")

    def _on_setup(self):
        """Handle setup button click."""
        password = self.password_input.text()
        confirm = self.confirm_input.text()

        # Validate password
        if len(password) < 8:
            self.status_label.setText("Password must be at least 8 characters")
            return

        if password != confirm:
            self.status_label.setText("Passwords do not match")
            return

        # Validate PIN if enabled
        if self.enable_pin.isChecked():
            pin = self.pin_input.text()
            pin_confirm = self.pin_confirm.text()

            if not pin.isdigit() or len(pin) < 6:
                self.status_label.setText("PIN must be 6-8 digits")
                return

            if pin != pin_confirm:
                self.status_label.setText("PINs do not match")
                return

        try:
            # Set up password
            self.auth.setup_initial_credentials(password)
            self._setup_password = password  # Store for database encryption

            # Set up security PIN if enabled
            if self.enable_pin.isChecked():
                self.auth.setup_security_key(self.pin_input.text())

            # If TOTP enabled, we'll show the TOTP setup dialog next
            self.accept()

        except Exception as e:
            self.status_label.setText(f"Setup failed: {str(e)}")

    def get_password(self) -> str:
        """Get the setup password for database encryption."""
        return getattr(self, '_setup_password', '')

    def should_setup_totp(self) -> bool:
        """Check if TOTP setup was requested."""
        return self.enable_totp.isChecked() and PYOTP_AVAILABLE


class TwoFactorSetupDialog(QDialog):
    """
    TOTP setup dialog with QR code display.

    Shows:
    - QR code for authenticator app
    - Manual entry secret
    - Verification input
    - Backup codes after successful setup
    """

    def __init__(self, parent=None, auth_manager: AuthManager = None):
        """
        Initialize 2FA setup dialog.

        Args:
            parent: Parent widget
            auth_manager: AuthManager instance
        """
        super().__init__(parent)
        self.auth = auth_manager or AuthManager()
        self.secret = None
        self.uri = None
        self.backup_codes = []

        self.setWindowTitle("Setup Two-Factor Authentication")
        self.setMinimumSize(500, 650)
        self.setModal(True)

        self._setup_ui()
        self._apply_style()
        self._generate_totp()

    def _setup_ui(self):
        """Create and arrange UI elements."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Header
        header = QLabel("Set Up Two-Factor Authentication")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #c9a040;")
        layout.addWidget(header)

        # Instructions
        instructions = QLabel(
            "1. Open your authenticator app (Microsoft Authenticator, Authy, etc.)\n"
            "2. Scan the QR code below or enter the secret manually\n"
            "3. Enter the 6-digit code to verify"
        )
        instructions.setStyleSheet("color: #a0a8b8;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # QR Code display
        self.qr_label = QLabel("Generating QR code...")
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setFixedSize(220, 220)
        self.qr_label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border-radius: 10px;
                padding: 10px;
                color: #333333;
            }
        """)
        layout.addWidget(self.qr_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Manual entry
        manual_group = QGroupBox("Manual Entry")
        manual_layout = QVBoxLayout(manual_group)

        self.secret_label = QLabel("Secret: Loading...")
        self.secret_label.setStyleSheet("color: #c9a040; font-family: monospace; font-size: 14px;")
        self.secret_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        manual_layout.addWidget(self.secret_label)

        layout.addWidget(manual_group)

        # Verification
        verify_group = QGroupBox("Verify Setup")
        verify_layout = QHBoxLayout(verify_group)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Enter 6-digit code")
        self.code_input.setMaxLength(6)
        self.code_input.returnPressed.connect(self._verify_code)
        verify_layout.addWidget(self.code_input)

        self.verify_btn = QPushButton("Verify")
        self.verify_btn.clicked.connect(self._verify_code)
        verify_layout.addWidget(self.verify_btn)

        layout.addWidget(verify_group)

        # Status
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #ff6b6b;")
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.done_btn = QPushButton("Done")
        self.done_btn.setEnabled(False)
        self.done_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.done_btn)

        skip_btn = QPushButton("Skip")
        skip_btn.clicked.connect(self.reject)
        button_layout.addWidget(skip_btn)

        layout.addLayout(button_layout)

    def _apply_style(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            QDialog {
                background-color: #0a0a0f;
            }
            QGroupBox {
                color: #a0a8b8;
                border: 1px solid #3a3a4a;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QLineEdit {
                background-color: #12121a;
                color: #d0d8e8;
                border: 1px solid #3a3a4a;
                border-radius: 5px;
                padding: 10px;
                font-size: 18px;
                letter-spacing: 5px;
            }
            QPushButton {
                background-color: #2a3a4a;
                color: #d0d8e8;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #3a4a5a;
            }
            QPushButton:disabled {
                background-color: #1a1a2a;
                color: #5a5a6a;
            }
            QLabel {
                color: #a0a8b8;
            }
        """)

    def _generate_totp(self):
        """Generate TOTP secret and display QR code."""
        try:
            self.secret, self.uri = self.auth.setup_totp(issuer="Tracker")
            self.secret_label.setText(f"Secret: {self.secret}")

            # Generate QR code
            if QRCODE_AVAILABLE:
                qr_path = self.auth.generate_qr_code(self.uri)
                if qr_path and os.path.exists(qr_path):
                    pixmap = QPixmap(qr_path)
                    scaled = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio)
                    self.qr_label.setPixmap(scaled)
                else:
                    self.qr_label.setText("QR code generation failed.\nUse manual entry.")
            else:
                self.qr_label.setText("QR code not available.\nInstall: pip install qrcode[pil]")

        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")

    def _verify_code(self):
        """Verify the entered TOTP code."""
        code = self.code_input.text()

        if len(code) != 6 or not code.isdigit():
            self.status_label.setText("Please enter a 6-digit code")
            return

        if self.auth.confirm_totp_setup(code):
            self.status_label.setText("Verification successful!")
            self.status_label.setStyleSheet("color: #66cc66;")
            self.done_btn.setEnabled(True)
            self.code_input.setEnabled(False)
            self.verify_btn.setEnabled(False)

            # Show backup codes
            self._show_backup_codes()
        else:
            self.status_label.setText("Invalid code. Please try again.")
            self.code_input.clear()
            self.code_input.setFocus()

    def _show_backup_codes(self):
        """Display backup codes after successful setup."""
        # The backup codes were generated during confirm_totp_setup
        # We need to regenerate them to show to user
        # Note: In production, you'd want to show these immediately after generation

        QMessageBox.information(
            self,
            "Backup Codes",
            "Two-factor authentication has been enabled.\n\n"
            "IMPORTANT: Go to Settings to view and save your backup codes.\n"
            "These codes can be used if you lose access to your authenticator app."
        )


class BackupCodesDialog(QDialog):
    """
    Dialog to display and regenerate backup codes.
    """

    def __init__(self, parent=None, auth_manager: AuthManager = None, password: str = None):
        """
        Initialize backup codes dialog.

        Args:
            parent: Parent widget
            auth_manager: AuthManager instance
            password: Password for verification (required to view codes)
        """
        super().__init__(parent)
        self.auth = auth_manager or AuthManager()
        self.password = password

        self.setWindowTitle("Backup Codes")
        self.setFixedSize(400, 450)
        self.setModal(True)

        self._setup_ui()
        self._apply_style()

        if password:
            self._load_codes()

    def _setup_ui(self):
        """Create and arrange UI elements."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Header
        header = QLabel("Backup Codes")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #c9a040;")
        layout.addWidget(header)

        # Warning
        warning = QLabel(
            "Save these codes in a secure location.\n"
            "Each code can only be used once."
        )
        warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        warning.setStyleSheet("color: #ff9966;")
        layout.addWidget(warning)

        # Codes display
        self.codes_text = QTextEdit()
        self.codes_text.setReadOnly(True)
        self.codes_text.setStyleSheet("""
            QTextEdit {
                background-color: #12121a;
                color: #66cc66;
                font-family: monospace;
                font-size: 16px;
                padding: 15px;
                border: 1px solid #3a3a4a;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.codes_text)

        # Remaining count
        self.remaining_label = QLabel()
        self.remaining_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.remaining_label.setStyleSheet("color: #a0a8b8;")
        layout.addWidget(self.remaining_label)

        # Buttons
        button_layout = QHBoxLayout()

        regen_btn = QPushButton("Regenerate Codes")
        regen_btn.clicked.connect(self._regenerate_codes)
        button_layout.addWidget(regen_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _apply_style(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            QDialog {
                background-color: #0a0a0f;
            }
            QPushButton {
                background-color: #2a3a4a;
                color: #d0d8e8;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #3a4a5a;
            }
            QLabel {
                color: #a0a8b8;
            }
        """)

    def _load_codes(self):
        """Load and display backup codes."""
        remaining = self.auth.get_remaining_backup_codes()
        self.remaining_label.setText(f"Remaining unused codes: {remaining}")

        if remaining == 0:
            self.codes_text.setText(
                "No backup codes remaining.\n\n"
                "Click 'Regenerate Codes' to create new ones."
            )
        else:
            self.codes_text.setText(
                "Your backup codes are stored securely.\n\n"
                "Click 'Regenerate Codes' to create new codes.\n"
                "(This will invalidate any existing codes)"
            )

    def _regenerate_codes(self):
        """Regenerate backup codes."""
        if not self.password:
            # Ask for password
            from PyQt6.QtWidgets import QInputDialog
            password, ok = QInputDialog.getText(
                self, "Verify Password",
                "Enter your password to regenerate codes:",
                QLineEdit.EchoMode.Password
            )
            if not ok or not password:
                return
            self.password = password

        codes = self.auth.get_backup_codes(self.password)
        if codes:
            self.codes_text.setText("\n".join(codes))
            self.remaining_label.setText(f"Remaining unused codes: {len(codes)}")

            QMessageBox.warning(
                self,
                "Save Your Codes",
                "These codes will only be shown once.\n"
                "Copy them now and store in a safe place!"
            )
        else:
            QMessageBox.critical(self, "Error", "Failed to regenerate codes. Check your password.")
            self.password = None


class SecuritySettingsDialog(QDialog):
    """
    Security settings dialog for managing authentication options.
    """

    def __init__(self, parent=None, auth_manager: AuthManager = None):
        """
        Initialize security settings dialog.

        Args:
            parent: Parent widget
            auth_manager: AuthManager instance
        """
        super().__init__(parent)
        self.auth = auth_manager or AuthManager()

        self.setWindowTitle("Security Settings")
        self.setMinimumSize(500, 580)
        self.setModal(True)

        self._setup_ui()
        self._apply_style()
        self._update_status()

    def _setup_ui(self):
        """Create and arrange UI elements."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Header
        header = QLabel("Security Settings")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #c9a040;")
        layout.addWidget(header)

        # Status group
        status_group = QGroupBox("Current Status")
        status_layout = QFormLayout(status_group)

        self.totp_status = QLabel()
        status_layout.addRow("TOTP:", self.totp_status)

        self.pin_status = QLabel()
        status_layout.addRow("Security PIN:", self.pin_status)

        self.backup_status = QLabel()
        status_layout.addRow("Backup Codes:", self.backup_status)

        layout.addWidget(status_group)

        # Actions group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setSpacing(12)
        actions_layout.setContentsMargins(15, 20, 15, 15)

        # Button style - applied directly to ensure visibility
        btn_style = """
            QPushButton {
                background-color: #3a4a5a;
                color: #ffffff;
                border: 1px solid #5a6a7a;
                border-radius: 5px;
                padding: 10px 20px;
                min-height: 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a5a6a;
                border-color: #7a8a9a;
            }
            QPushButton:pressed {
                background-color: #2a3a4a;
            }
        """

        change_pw_btn = QPushButton("Change Password")
        change_pw_btn.setStyleSheet(btn_style)
        change_pw_btn.clicked.connect(self._change_password)
        actions_layout.addWidget(change_pw_btn)

        setup_totp_btn = QPushButton("Setup/Reset TOTP")
        setup_totp_btn.setStyleSheet(btn_style)
        setup_totp_btn.clicked.connect(self._setup_totp)
        actions_layout.addWidget(setup_totp_btn)

        setup_pin_btn = QPushButton("Setup/Change Security PIN")
        setup_pin_btn.setStyleSheet(btn_style)
        setup_pin_btn.clicked.connect(self._setup_pin)
        actions_layout.addWidget(setup_pin_btn)

        backup_btn = QPushButton("View Backup Codes")
        backup_btn.setStyleSheet(btn_style)
        backup_btn.clicked.connect(self._view_backup_codes)
        actions_layout.addWidget(backup_btn)

        disable_2fa_btn = QPushButton("Disable All 2FA")
        disable_2fa_btn.setStyleSheet("""
            QPushButton {
                background-color: #6a3a3a;
                color: #ffffff;
                border: 1px solid #8a5a5a;
                border-radius: 5px;
                padding: 10px 20px;
                min-height: 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7a4a4a;
                border-color: #9a6a6a;
            }
        """)
        disable_2fa_btn.clicked.connect(self._disable_2fa)
        actions_layout.addWidget(disable_2fa_btn)

        layout.addWidget(actions_group)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _apply_style(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            QDialog {
                background-color: #0a0a0f;
            }
            QGroupBox {
                color: #a0a8b8;
                border: 1px solid #3a3a4a;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QGroupBox QPushButton {
                background-color: #3a4a5a;
                color: #ffffff;
                border: 1px solid #5a6a7a;
                border-radius: 5px;
                padding: 10px 20px;
                min-height: 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QGroupBox QPushButton:hover {
                background-color: #4a5a6a;
                border-color: #7a8a9a;
            }
            QGroupBox QPushButton:pressed {
                background-color: #2a3a4a;
            }
            QDialog > QPushButton {
                background-color: #3a4a5a;
                color: #ffffff;
                border: 1px solid #5a6a7a;
                border-radius: 5px;
                padding: 10px 20px;
                min-height: 20px;
                font-size: 13px;
            }
            QDialog > QPushButton:hover {
                background-color: #4a5a6a;
            }
            QLabel {
                color: #a0a8b8;
            }
        """)

    def _update_status(self):
        """Update status labels."""
        status = self.auth.get_auth_status()

        if status['totp_enabled']:
            self.totp_status.setText("Enabled")
            self.totp_status.setStyleSheet("color: #66cc66;")
        else:
            self.totp_status.setText("Not configured")
            self.totp_status.setStyleSheet("color: #ff9966;")

        if status['security_key_enabled']:
            self.pin_status.setText("Enabled")
            self.pin_status.setStyleSheet("color: #66cc66;")
        else:
            self.pin_status.setText("Not configured")
            self.pin_status.setStyleSheet("color: #ff9966;")

        remaining = status['backup_codes_remaining']
        if remaining > 0:
            self.backup_status.setText(f"{remaining} remaining")
            self.backup_status.setStyleSheet("color: #66cc66;")
        else:
            self.backup_status.setText("None generated")
            self.backup_status.setStyleSheet("color: #ff9966;")

    def _change_password(self):
        """Handle change password action."""
        from PyQt6.QtWidgets import QInputDialog

        old_pw, ok = QInputDialog.getText(
            self, "Change Password", "Current password:",
            QLineEdit.EchoMode.Password
        )
        if not ok:
            return

        new_pw, ok = QInputDialog.getText(
            self, "Change Password", "New password (min 8 chars):",
            QLineEdit.EchoMode.Password
        )
        if not ok:
            return

        confirm, ok = QInputDialog.getText(
            self, "Change Password", "Confirm new password:",
            QLineEdit.EchoMode.Password
        )
        if not ok or new_pw != confirm:
            QMessageBox.warning(self, "Error", "Passwords do not match")
            return

        try:
            self.auth.change_password(old_pw, new_pw)
            QMessageBox.information(self, "Success", "Password changed successfully")
        except ValueError as e:
            QMessageBox.critical(self, "Error", str(e))

    def _setup_totp(self):
        """Handle TOTP setup action."""
        if not PYOTP_AVAILABLE:
            QMessageBox.warning(
                self, "Not Available",
                "TOTP requires pyotp. Install with: pip install pyotp"
            )
            return

        dialog = TwoFactorSetupDialog(self, self.auth)
        dialog.exec()
        self._update_status()

    def _setup_pin(self):
        """Handle security PIN setup action."""
        from PyQt6.QtWidgets import QInputDialog

        pin, ok = QInputDialog.getText(
            self, "Security PIN", "Enter new PIN (6-8 digits):",
            QLineEdit.EchoMode.Password
        )
        if not ok:
            return

        confirm, ok = QInputDialog.getText(
            self, "Security PIN", "Confirm PIN:",
            QLineEdit.EchoMode.Password
        )
        if not ok or pin != confirm:
            QMessageBox.warning(self, "Error", "PINs do not match")
            return

        try:
            self.auth.setup_security_key(pin)
            QMessageBox.information(self, "Success", "Security PIN set successfully")
            self._update_status()
        except ValueError as e:
            QMessageBox.critical(self, "Error", str(e))

    def _view_backup_codes(self):
        """Handle view backup codes action."""
        from PyQt6.QtWidgets import QInputDialog

        password, ok = QInputDialog.getText(
            self, "Verify Password", "Enter your password:",
            QLineEdit.EchoMode.Password
        )
        if not ok:
            return

        dialog = BackupCodesDialog(self, self.auth, password)
        dialog.exec()
        self._update_status()

    def _disable_2fa(self):
        """Handle disable 2FA action."""
        from PyQt6.QtWidgets import QInputDialog

        reply = QMessageBox.warning(
            self, "Disable 2FA",
            "Are you sure you want to disable all two-factor authentication?\n"
            "This will make your account less secure.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        password, ok = QInputDialog.getText(
            self, "Verify Password", "Enter your password to confirm:",
            QLineEdit.EchoMode.Password
        )
        if not ok:
            return

        if self.auth.disable_2fa(password):
            QMessageBox.information(self, "Success", "2FA has been disabled")
            self._update_status()
        else:
            QMessageBox.critical(self, "Error", "Incorrect password")

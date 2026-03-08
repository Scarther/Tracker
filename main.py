"""
================================================================================
TRACKER - MAIN APPLICATION
================================================================================
Case Management & Digital Footprint Tracking for Law Enforcement

This is the primary application module containing:
- Main application window and navigation
- All dialog classes for entity creation/editing
- Profile panel for viewing entity details
- Relationship graph visualization
- Multi-entry widgets for complex data types

ARCHITECTURE:
-------------
The application uses a three-panel layout:
  LEFT:   Quick action buttons and case checklist
  CENTER: Relationship graph visualization (vis.js)
  RIGHT:  Entity profile panel with edit/delete actions

All dialogs follow a consistent pattern:
  1. Form-based data entry with validation
  2. Photo/media attachment support
  3. Entity linking (connect to other records)
  4. Save to database via TrackerDB class

BASE64 USAGE NOTE:
------------------
This module uses base64 encoding ONLY for runtime photo embedding in the
graph visualization. QtWebEngine security prevents direct file:// access,
so photos must be converted to data URLs at runtime. This is NOT hardcoded
data - it's dynamic conversion of user-uploaded images. See update_graph().

UI FRAMEWORK:
-------------
Built with PyQt6 and PyQt6-WebEngine for cross-platform compatibility.

================================================================================
"""

import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QPushButton, QLabel,
    QLineEdit, QTextEdit, QFormLayout, QDialog, QDialogButtonBox,
    QComboBox, QDateEdit, QMessageBox, QFileDialog, QScrollArea,
    QFrame, QGridLayout, QTabWidget, QMenu, QStatusBar, QGroupBox,
    QCheckBox, QSpinBox, QTreeWidget, QTreeWidgetItem, QInputDialog,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, QUrl, pyqtSignal, pyqtSlot, QObject
from PyQt6.QtGui import QAction, QPixmap, QDesktopServices, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

from database import TrackerDB
from auth import AuthManager
from auth_dialogs import (
    LoginDialog, SetupDialog, TwoFactorSetupDialog,
    SecuritySettingsDialog
)
import json
import shutil
from datetime import datetime


# ============ MULTI-ENTRY WIDGETS ============

class MultiEntryWidget(QFrame):
    """Base widget for multiple entries (social, phone, email, etc.)"""

    def __init__(self, parent=None, label="Item"):
        super().__init__(parent)
        self.label = label
        self.entries = []
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("QFrame { border: 1px solid #3a3a4a; border-radius: 4px; padding: 5px; background-color: #12121a; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel(self.label))
        header.addStretch()
        add_btn = QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setStyleSheet("background-color: #c9a040; color: #0a0a0f; font-weight: bold; font-size: 14px;")
        add_btn.clicked.connect(self.add_entry)
        header.addWidget(add_btn)
        layout.addLayout(header)

        # Entries container
        self.entries_layout = QVBoxLayout()
        layout.addLayout(self.entries_layout)

    def add_entry(self):
        """Override in subclass"""
        pass

    def remove_entry(self, widget):
        self.entries.remove(widget)
        widget.deleteLater()

    def get_data(self) -> list:
        """Override in subclass"""
        return []


class SocialMediaEntry(QFrame):
    """Single social media entry"""
    removed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.platform = QComboBox()
        self.platform.setEditable(True)
        self.platform.addItems(["Facebook", "Instagram", "Twitter/X", "TikTok", "Snapchat", "YouTube", "LinkedIn"])
        self.platform.setFixedWidth(100)

        self.url = QLineEdit()
        self.url.setPlaceholderText("URL or username")

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("background-color: #8a5a5a; padding: 0;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))

        layout.addWidget(self.platform)
        layout.addWidget(self.url)
        layout.addWidget(remove_btn)


class SocialMediaWidget(MultiEntryWidget):
    """Widget for multiple social media entries"""

    def __init__(self, parent=None):
        super().__init__(parent, "Social Media")

    def add_entry(self):
        entry = SocialMediaEntry()
        entry.removed.connect(self.remove_entry)
        self.entries.append(entry)
        self.entries_layout.addWidget(entry)

    def get_data(self) -> list:
        return [{'platform': e.platform.currentText(), 'url': e.url.text().strip()}
                for e in self.entries if e.url.text().strip()]


class PhoneEntry(QFrame):
    """Single phone number entry"""
    removed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.phone_type = QComboBox()
        self.phone_type.addItems(["Cell", "Home", "Work", "Burner", "Other"])
        self.phone_type.setFixedWidth(80)

        self.number = QLineEdit()
        self.number.setPlaceholderText("Phone number")

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("background-color: #8a5a5a; padding: 0;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))

        layout.addWidget(self.phone_type)
        layout.addWidget(self.number)
        layout.addWidget(remove_btn)


class PhoneWidget(MultiEntryWidget):
    """Widget for multiple phone entries"""

    def __init__(self, parent=None):
        super().__init__(parent, "Phone Numbers")

    def add_entry(self):
        entry = PhoneEntry()
        entry.removed.connect(self.remove_entry)
        self.entries.append(entry)
        self.entries_layout.addWidget(entry)

    def get_data(self) -> list:
        return [{'phone_type': e.phone_type.currentText(), 'number': e.number.text().strip()}
                for e in self.entries if e.number.text().strip()]


class EmailEntry(QFrame):
    """Single email entry"""
    removed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.email_type = QComboBox()
        self.email_type.addItems(["Personal", "Work", "Other"])
        self.email_type.setFixedWidth(80)

        self.email = QLineEdit()
        self.email.setPlaceholderText("Email address")

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("background-color: #8a5a5a; padding: 0;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))

        layout.addWidget(self.email_type)
        layout.addWidget(self.email)
        layout.addWidget(remove_btn)


class EmailWidget(MultiEntryWidget):
    """Widget for multiple email entries"""

    def __init__(self, parent=None):
        super().__init__(parent, "Email Addresses")

    def add_entry(self):
        entry = EmailEntry()
        entry.removed.connect(self.remove_entry)
        self.entries.append(entry)
        self.entries_layout.addWidget(entry)

    def get_data(self) -> list:
        return [{'email_type': e.email_type.currentText(), 'email': e.email.text().strip()}
                for e in self.entries if e.email.text().strip()]


class FamilyEntry(QFrame):
    """Single family member entry"""
    removed = pyqtSignal(object)

    def __init__(self, parent=None, subjects=None):
        super().__init__(parent)
        self.subjects = subjects or []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.relationship = QComboBox()
        self.relationship.setEditable(True)
        self.relationship.addItems(["Mother", "Father", "Brother", "Sister", "Son", "Daughter",
                                     "Spouse", "Cousin", "Uncle", "Aunt", "Grandparent", "Other"])
        self.relationship.setFixedWidth(90)

        self.name = QLineEdit()
        self.name.setPlaceholderText("Name (or select existing)")

        self.linked_subject = QComboBox()
        self.linked_subject.addItem("-- Link to existing --", None)
        for s in self.subjects:
            self.linked_subject.addItem(f"{s['first_name']} {s['last_name']}", s['id'])
        self.linked_subject.setFixedWidth(150)

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("background-color: #8a5a5a; padding: 0;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))

        layout.addWidget(self.relationship)
        layout.addWidget(self.name)
        layout.addWidget(self.linked_subject)
        layout.addWidget(remove_btn)


class FamilyWidget(MultiEntryWidget):
    """Widget for multiple family member entries"""

    def __init__(self, parent=None, subjects=None):
        self.subjects = subjects or []
        super().__init__(parent, "Family Members")

    def set_subjects(self, subjects):
        self.subjects = subjects

    def add_entry(self):
        entry = FamilyEntry(subjects=self.subjects)
        entry.removed.connect(self.remove_entry)
        self.entries.append(entry)
        self.entries_layout.addWidget(entry)

    def get_data(self) -> list:
        return [{
            'relationship': e.relationship.currentText(),
            'family_name': e.name.text().strip(),
            'family_member_id': e.linked_subject.currentData()
        } for e in self.entries if e.name.text().strip() or e.linked_subject.currentData()]


class PhotoViewerDialog(QDialog):
    """Full-size photo viewer dialog. Click or press Escape to close."""

    def __init__(self, photo_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Photo Viewer")
        self.setMinimumSize(400, 400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        pixmap = QPixmap(photo_path)
        if not pixmap.isNull():
            # Scale to screen size while keeping aspect ratio
            screen = self.screen().availableGeometry()
            max_w = int(screen.width() * 0.8)
            max_h = int(screen.height() * 0.8)
            scaled = pixmap.scaled(max_w, max_h,
                                   Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            label = QLabel()
            label.setPixmap(scaled)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.mousePressEvent = lambda e: self.accept()
            layout.addWidget(label)
            self.resize(scaled.width() + 20, scaled.height() + 20)
        else:
            layout.addWidget(QLabel("Could not load image"))


class ClickablePhotoLabel(QLabel):
    """A QLabel that shows a photo thumbnail and opens full-size on click."""

    def __init__(self, photo_path, max_w=100, max_h=100, parent=None):
        super().__init__(parent)
        self.photo_path = photo_path
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to view full size")

        pixmap = QPixmap(photo_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(max_w, max_h,
                                   Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(scaled)

    def mousePressEvent(self, event):
        if self.photo_path and os.path.exists(self.photo_path):
            dlg = PhotoViewerDialog(self.photo_path, self.window())
            dlg.exec()


def get_app_dir():
    """Get the application's base directory for portable paths."""
    return os.path.dirname(os.path.abspath(__file__))


class CollapsibleSection(QWidget):
    """A collapsible section widget with header and content area."""

    def __init__(self, title: str, parent=None, expanded=True):
        super().__init__(parent)
        self._expanded = expanded

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header button
        self.toggle_btn = QPushButton(f"{'▼' if expanded else '▶'} {title}")
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1a24;
                color: #c9a040;
                border: 1px solid #3a3a4a;
                border-radius: 4px;
                padding: 8px 12px;
                text-align: left;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #252532;
            }
        """)
        self.toggle_btn.clicked.connect(self._toggle)
        self._title = title
        layout.addWidget(self.toggle_btn)

        # Content container
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 5, 0, 5)
        self.content.setVisible(expanded)
        layout.addWidget(self.content)

    def _toggle(self):
        self._expanded = not self._expanded
        self.content.setVisible(self._expanded)
        self.toggle_btn.setText(f"{'▼' if self._expanded else '▶'} {self._title}")

    def addWidget(self, widget):
        self.content_layout.addWidget(widget)

    def setExpanded(self, expanded: bool):
        self._expanded = expanded
        self.content.setVisible(expanded)
        self.toggle_btn.setText(f"{'▼' if expanded else '▶'} {self._title}")


def get_media_dir():
    """Get the media storage directory."""
    media_dir = os.path.join(get_app_dir(), 'data', 'media', 'uploads')
    os.makedirs(media_dir, exist_ok=True)
    return media_dir


def to_relative_path(abs_path: str) -> str:
    """Convert absolute path to relative path from app directory."""
    if not abs_path:
        return abs_path
    app_dir = get_app_dir()
    if abs_path.startswith(app_dir):
        return os.path.relpath(abs_path, app_dir)
    return abs_path


def to_absolute_path(rel_path: str) -> str:
    """Convert relative path to absolute path from app directory."""
    if not rel_path:
        return rel_path
    if os.path.isabs(rel_path):
        return rel_path
    return os.path.join(get_app_dir(), rel_path)


class PhotoUploadWidget(QFrame):
    """Widget for uploading photos with preview - supports browse, drag-drop, and paste.

    All photos are copied to data/media/uploads/ for portability (USB support).
    Paths are stored relative to the app directory.
    """

    def __init__(self, parent=None, label="Photo"):
        super().__init__(parent)
        self.photo_path = None  # Relative path to copied photo
        self._label = label
        self.setStyleSheet("QFrame { border: 1px dashed #3a4a6a; border-radius: 4px; }")
        self.setMinimumHeight(120)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.preview = QLabel(f"Drop {label} here\nClick to browse, or Ctrl+V to paste")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("color: #8a8a9a; border: none;")
        layout.addWidget(self.preview)

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse)
        layout.addWidget(self.browse_btn)

    def _copy_to_media(self, source_path: str) -> str:
        """Copy photo to media/uploads folder and return relative path."""
        import time

        media_dir = get_media_dir()

        # Generate unique filename with timestamp
        ext = os.path.splitext(source_path)[1].lower() or '.png'
        filename = f"photo_{int(time.time() * 1000)}{ext}"
        dest_path = os.path.join(media_dir, filename)

        # Copy file to media folder
        shutil.copy2(source_path, dest_path)

        # Return relative path for portability
        return to_relative_path(dest_path)

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Photo", "",
                                               "Images (*.jpg *.jpeg *.png *.gif *.bmp)")
        if path:
            self.set_photo(path)

    def set_photo(self, path: str):
        """Set photo - copies to media folder if external, displays preview."""
        # Check if already in our media folder
        app_dir = get_app_dir()
        if not path.startswith(app_dir):
            # External file - copy to our media folder
            path = self._copy_to_media(path)
        else:
            # Already in app folder - use relative path
            path = to_relative_path(path)

        self.photo_path = path

        # Display preview using absolute path
        abs_path = to_absolute_path(path)
        pixmap = QPixmap(abs_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            self.preview.setPixmap(scaled)
            self.preview.setText("")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                self.set_photo(path)
                break
        event.acceptProposedAction()

    def keyPressEvent(self, event):
        """Handle Ctrl+V paste from clipboard"""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_V:
            self.paste_from_clipboard()
        else:
            super().keyPressEvent(event)

    def paste_from_clipboard(self):
        """Paste image from clipboard - saves directly to media folder."""
        from PyQt6.QtWidgets import QApplication
        import time

        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()

        # Check for image data in clipboard
        if mime_data.hasImage():
            image = clipboard.image()
            if not image.isNull():
                # Save directly to media/uploads folder
                media_dir = get_media_dir()
                filename = f"pasted_{int(time.time() * 1000)}.png"
                save_path = os.path.join(media_dir, filename)

                image.save(save_path, "PNG")
                self.photo_path = to_relative_path(save_path)

                # Display preview
                pixmap = QPixmap(save_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
                    self.preview.setPixmap(scaled)
                    self.preview.setText("")
                return

        # Check for file URLs in clipboard (copied files)
        if mime_data.hasUrls():
            for url in mime_data.urls():
                path = url.toLocalFile()
                if path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                    self.set_photo(path)
                    return

    def mousePressEvent(self, event):
        """Click to focus (enables paste) or browse"""
        self.setFocus()
        super().mousePressEvent(event)

    def get_path(self) -> str:
        """Get the relative path to the photo."""
        return self.photo_path

    def get_absolute_path(self) -> str:
        """Get the absolute path to the photo."""
        return to_absolute_path(self.photo_path) if self.photo_path else None


# ============ PHOTO GALLERY WIDGET ============

class PhotoGalleryWidget(QWidget):
    """Widget to display and manage photos with pinning for bubble display.

    Shows all photos for an entity, allows pinning one to show in graph bubbles.
    """

    pin_changed = pyqtSignal()  # Emitted when a photo is pinned/unpinned

    def __init__(self, db, entity_type: str, entity_id: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Note about pinned photos
        note = QLabel("📌 The pinned photo will be shown in the bubble of the spider web graph")
        note.setStyleSheet("color: #7a8a9a; font-size: 11px; font-style: italic;")
        note.setWordWrap(True)
        layout.addWidget(note)

        # Photo grid
        self.photo_container = QWidget()
        self.photo_layout = QHBoxLayout(self.photo_container)
        self.photo_layout.setContentsMargins(0, 0, 0, 0)
        self.photo_layout.setSpacing(8)
        self.photo_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.photo_container)

    def refresh(self):
        """Reload photos from database."""
        # Clear existing photos
        while self.photo_layout.count():
            item = self.photo_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Get all media for this entity
        media_list = self.db.get_entity_media(self.entity_type, self.entity_id)

        # Filter to images only
        images = [m for m in media_list if m.get('file_path', '').lower().endswith(
            ('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]

        if not images:
            no_photos = QLabel("No photos uploaded")
            no_photos.setStyleSheet("color: #6a6a7a; font-style: italic;")
            self.photo_layout.addWidget(no_photos)
            return

        for media in images:
            self._add_photo_thumbnail(media)

        # Add stretch to keep photos left-aligned
        self.photo_layout.addStretch()

    def _add_photo_thumbnail(self, media: dict):
        """Add a photo thumbnail with pin overlay."""
        container = QFrame()
        container.setFixedSize(85, 100)
        container.setStyleSheet("QFrame { border: 1px solid #3a4a6a; border-radius: 4px; }")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(2, 2, 2, 2)
        container_layout.setSpacing(0)

        # Photo with pin overlay
        photo_frame = QWidget()
        photo_frame.setFixedSize(80, 75)

        abs_path = to_absolute_path(media['file_path'])
        pixmap = QPixmap(abs_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(75, 70, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)

            photo_label = QLabel(photo_frame)
            photo_label.setPixmap(scaled)
            photo_label.move(2, 2)
            photo_label.setCursor(Qt.CursorShape.PointingHandCursor)
            photo_label.setToolTip("Click to view full size")
            photo_label.mousePressEvent = lambda e, p=abs_path: PhotoViewerDialog(p, self.window()).exec()

            # Pin indicator
            is_pinned = media.get('is_pinned', 0) == 1
            if is_pinned:
                pin_label = QLabel("📌", photo_frame)
                pin_label.setStyleSheet("background: rgba(0,0,0,0.6); border-radius: 3px; padding: 2px;")
                pin_label.move(55, 2)

        container_layout.addWidget(photo_frame)

        # Pin button
        pin_btn = QPushButton("📌 Pin" if not media.get('is_pinned') else "✓ Pinned")
        pin_btn.setFixedHeight(18)
        pin_btn.setStyleSheet("""
            QPushButton {
                font-size: 10px;
                padding: 0px 2px;
                background-color: #3a5a7a;
                border-radius: 2px;
            }
            QPushButton:hover { background-color: #4a6a8a; }
        """ if not media.get('is_pinned') else """
            QPushButton {
                font-size: 10px;
                padding: 0px 2px;
                background-color: #4a8a5a;
                border-radius: 2px;
            }
            QPushButton:hover { background-color: #5a9a6a; }
        """)
        pin_btn.clicked.connect(lambda checked, m=media: self._toggle_pin(m))
        container_layout.addWidget(pin_btn)

        self.photo_layout.addWidget(container)

    def _toggle_pin(self, media: dict):
        """Toggle pin status for a photo."""
        if media.get('is_pinned'):
            self.db.unpin_media(media['id'])
        else:
            self.db.set_media_pinned(self.entity_type, self.entity_id, media['id'])
        self.refresh()
        self.pin_changed.emit()


# ============ TATTOO WIDGET ============

class TattooEntry(QFrame):
    """Single tattoo entry"""
    removed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.body_location = QComboBox()
        self.body_location.setEditable(True)
        self.body_location.addItems(["Left Arm", "Right Arm", "Left Leg", "Right Leg", "Chest",
                                     "Back", "Neck", "Face", "Hand", "Torso", "Other"])
        self.body_location.setFixedWidth(100)

        self.description = QLineEdit()
        self.description.setPlaceholderText("Description")

        self.gang_affiliated = QCheckBox("Gang")
        self.gang_affiliated.setFixedWidth(50)

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("background-color: #8a5a5a; padding: 0;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))

        layout.addWidget(self.body_location)
        layout.addWidget(self.description)
        layout.addWidget(self.gang_affiliated)
        layout.addWidget(remove_btn)


class TattooWidget(MultiEntryWidget):
    """Widget for multiple tattoo entries"""

    def __init__(self, parent=None):
        super().__init__(parent, "Tattoos")

    def add_entry(self):
        entry = TattooEntry()
        entry.removed.connect(self.remove_entry)
        self.entries.append(entry)
        self.entries_layout.addWidget(entry)

    def get_data(self) -> list:
        return [{
            'body_location': e.body_location.currentText(),
            'description': e.description.text().strip(),
            'is_gang_affiliated': 1 if e.gang_affiliated.isChecked() else 0
        } for e in self.entries if e.description.text().strip()]


# ============ VEHICLE WIDGET ============

class VehicleEntry(QFrame):
    """Single vehicle entry"""
    removed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        row1 = QHBoxLayout()
        self.plate = QLineEdit()
        self.plate.setPlaceholderText("Plate")
        self.plate.setFixedWidth(80)

        self.state = QComboBox()
        self.state.setEditable(True)
        self.state.addItems(US_STATES)
        self.state.setFixedWidth(50)

        self.make = QLineEdit()
        self.make.setPlaceholderText("Make")
        self.make.setFixedWidth(70)

        self.model = QLineEdit()
        self.model.setPlaceholderText("Model")
        self.model.setFixedWidth(70)

        self.year = QLineEdit()
        self.year.setPlaceholderText("Year")
        self.year.setFixedWidth(50)

        self.color = QLineEdit()
        self.color.setPlaceholderText("Color")
        self.color.setFixedWidth(60)

        self.relationship = QComboBox()
        self.relationship.addItems(["Owner", "Driver", "Passenger", "Associated"])
        self.relationship.setFixedWidth(80)

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("background-color: #8a5a5a; padding: 0;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))

        row1.addWidget(self.plate)
        row1.addWidget(self.state)
        row1.addWidget(self.make)
        row1.addWidget(self.model)
        row1.addWidget(self.year)
        row1.addWidget(self.color)
        row1.addWidget(self.relationship)
        row1.addWidget(remove_btn)
        layout.addLayout(row1)


class VehicleWidget(MultiEntryWidget):
    """Widget for multiple vehicle entries"""

    def __init__(self, parent=None):
        super().__init__(parent, "Vehicles")

    def add_entry(self):
        entry = VehicleEntry()
        entry.removed.connect(self.remove_entry)
        self.entries.append(entry)
        self.entries_layout.addWidget(entry)

    def get_data(self) -> list:
        return [{
            'plate': e.plate.text().strip(),
            'state': e.state.currentText(),
            'make': e.make.text().strip(),
            'model': e.model.text().strip(),
            'year': e.year.text().strip(),
            'color': e.color.text().strip(),
            'relationship': e.relationship.currentText()
        } for e in self.entries if e.plate.text().strip() or e.make.text().strip()]


# ============ WEAPON WIDGET ============

class WeaponEntry(QFrame):
    """Single weapon entry"""
    removed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.weapon_type = QComboBox()
        self.weapon_type.setEditable(True)
        self.weapon_type.addItems(["Handgun", "Rifle", "Shotgun", "Knife", "Other"])
        self.weapon_type.setFixedWidth(80)

        self.make = QLineEdit()
        self.make.setPlaceholderText("Make")
        self.make.setFixedWidth(70)

        self.model = QLineEdit()
        self.model.setPlaceholderText("Model")
        self.model.setFixedWidth(70)

        self.caliber = QLineEdit()
        self.caliber.setPlaceholderText("Caliber")
        self.caliber.setFixedWidth(60)

        self.serial = QLineEdit()
        self.serial.setPlaceholderText("Serial #")
        self.serial.setFixedWidth(90)

        self.relationship = QComboBox()
        self.relationship.addItems(["Owner", "Possessed", "Associated", "Recovered"])
        self.relationship.setFixedWidth(80)

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("background-color: #8a5a5a; padding: 0;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))

        layout.addWidget(self.weapon_type)
        layout.addWidget(self.make)
        layout.addWidget(self.model)
        layout.addWidget(self.caliber)
        layout.addWidget(self.serial)
        layout.addWidget(self.relationship)
        layout.addWidget(remove_btn)


class WeaponWidget(MultiEntryWidget):
    """Widget for multiple weapon entries"""

    def __init__(self, parent=None):
        super().__init__(parent, "Weapons")

    def add_entry(self):
        entry = WeaponEntry()
        entry.removed.connect(self.remove_entry)
        self.entries.append(entry)
        self.entries_layout.addWidget(entry)

    def get_data(self) -> list:
        return [{
            'weapon_type': e.weapon_type.currentText(),
            'make': e.make.text().strip(),
            'model': e.model.text().strip(),
            'caliber': e.caliber.text().strip(),
            'serial_number': e.serial.text().strip(),
            'relationship': e.relationship.currentText()
        } for e in self.entries if e.weapon_type.currentText()]


# ============ STATE ID WIDGET ============

US_STATES = ["", "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
             "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
             "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
             "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
             "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"]


class StateIdEntry(QFrame):
    """Single government identifier entry (SSN, OLN, State ID, RISSAFE, etc.)"""
    removed = pyqtSignal(object)

    def __init__(self, parent=None, default_type=""):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.id_type = QComboBox()
        self.id_type.setEditable(True)
        self.id_type.addItems(["SSN", "OLN", "State ID", "RISSAFE", "FBI#", "SID#", "NCIC#", "Other"])
        self.id_type.setFixedWidth(90)
        if default_type:
            self.id_type.setCurrentText(default_type)

        self.id_number = QLineEdit()
        self.id_number.setPlaceholderText("ID Number")

        self.state = QComboBox()
        self.state.setEditable(True)
        self.state.setFixedWidth(60)
        self.state.addItems(US_STATES)

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("background-color: #8a5a5a; padding: 0;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))

        layout.addWidget(self.id_type)
        layout.addWidget(self.id_number)
        layout.addWidget(self.state)
        layout.addWidget(remove_btn)


class StateIdWidget(MultiEntryWidget):
    """Widget for multiple government identifier entries"""

    def __init__(self, parent=None):
        super().__init__(parent, "Government Identifiers")

    def add_entry(self, default_type=""):
        entry = StateIdEntry(default_type=default_type)
        entry.removed.connect(self.remove_entry)
        self.entries.append(entry)
        self.entries_layout.addWidget(entry)

    def get_data(self) -> list:
        return [{
            'id_type': e.id_type.currentText(),
            'id_number': e.id_number.text().strip(),
            'state': e.state.currentText()
        } for e in self.entries if e.id_number.text().strip()]


# ============ LOCATION ENTRY WIDGET ============

class LocationEntry(QFrame):
    """Single address entry with type dropdown"""
    removed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.loc_type = QComboBox()
        self.loc_type.setEditable(True)
        self.loc_type.addItems(["Residence", "Hang-Out", "Affiliated", "Family Member",
                                "Work", "Frequented", "Last Known", "Other"])
        self.loc_type.setFixedWidth(110)

        self.address = QLineEdit()
        self.address.setPlaceholderText("Address")

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("background-color: #8a5a5a; padding: 0;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))

        layout.addWidget(self.loc_type)
        layout.addWidget(self.address)
        layout.addWidget(remove_btn)


class LocationWidget(MultiEntryWidget):
    """Widget for multiple address entries with type"""

    def __init__(self, parent=None):
        super().__init__(parent, "Locations")

    def add_entry(self, default_type=""):
        entry = LocationEntry()
        if default_type:
            entry.loc_type.setCurrentText(default_type)
        entry.removed.connect(self.remove_entry)
        self.entries.append(entry)
        self.entries_layout.addWidget(entry)

    def get_data(self) -> list:
        return [{
            'loc_type': e.loc_type.currentText(),
            'address': e.address.text().strip()
        } for e in self.entries if e.address.text().strip()]


# ============ EMPLOYMENT WIDGET ============

class EmploymentEntry(QFrame):
    """Single employment/business entry"""
    removed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        row1 = QHBoxLayout()
        self.employer = QLineEdit()
        self.employer.setPlaceholderText("Employer / Business Name")
        self.position = QLineEdit()
        self.position.setPlaceholderText("Position/Title")
        self.position.setFixedWidth(140)
        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("background-color: #8a5a5a; padding: 0;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))
        row1.addWidget(self.employer)
        row1.addWidget(self.position)
        row1.addWidget(remove_btn)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.address = QLineEdit()
        self.address.setPlaceholderText("Work Address")
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("Work Phone")
        self.phone.setFixedWidth(140)
        row2.addWidget(self.address)
        row2.addWidget(self.phone)
        layout.addLayout(row2)


class EmploymentWidget(MultiEntryWidget):
    """Widget for multiple employment entries"""

    def __init__(self, parent=None):
        super().__init__(parent, "Employment")

    def add_entry(self):
        entry = EmploymentEntry()
        entry.removed.connect(self.remove_entry)
        self.entries.append(entry)
        self.entries_layout.addWidget(entry)

    def get_data(self) -> list:
        return [{
            'employer': e.employer.text().strip(),
            'position': e.position.text().strip(),
            'address': e.address.text().strip(),
            'phone': e.phone.text().strip()
        } for e in self.entries if e.employer.text().strip()]


# ============ CASE NUMBER WIDGET ============

class CaseNumberEntry(QFrame):
    """Single court case entry"""
    removed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.case_number = QLineEdit()
        self.case_number.setPlaceholderText("Court Case Number")

        self.case_type = QComboBox()
        self.case_type.setEditable(True)
        self.case_type.addItems(["Criminal", "Traffic", "Civil", "Other"])
        self.case_type.setFixedWidth(80)

        self.status = QComboBox()
        self.status.addItems(["Pending", "Convicted", "Dismissed", "Acquitted", "Pled"])
        self.status.setFixedWidth(80)

        self.url = QLineEdit()
        self.url.setPlaceholderText("Court URL")

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("background-color: #8a5a5a; padding: 0;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))

        layout.addWidget(self.case_number)
        layout.addWidget(self.case_type)
        layout.addWidget(self.status)
        layout.addWidget(self.url)
        layout.addWidget(remove_btn)


class CaseNumberWidget(MultiEntryWidget):
    """Widget for multiple court case entries"""

    def __init__(self, parent=None):
        super().__init__(parent, "Court Cases")

    def add_entry(self):
        entry = CaseNumberEntry()
        entry.removed.connect(self.remove_entry)
        self.entries.append(entry)
        self.entries_layout.addWidget(entry)

    def get_data(self) -> list:
        return [{
            'case_number': e.case_number.text().strip(),
            'case_type': e.case_type.currentText(),
            'status': e.status.currentText(),
            'url': e.url.text().strip()
        } for e in self.entries if e.case_number.text().strip()]


# ============ EVIDENCE WIDGET ============

class EvidenceEntry(QFrame):
    """Single evidence entry"""
    removed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.evidence_type = QComboBox()
        self.evidence_type.setEditable(True)
        self.evidence_type.addItems(["Firearm", "Drugs", "Currency", "Document", "Electronics", "Clothing", "Other"])
        self.evidence_type.setFixedWidth(90)

        self.description = QLineEdit()
        self.description.setPlaceholderText("Description")

        self.disposition = QComboBox()
        self.disposition.addItems(["Seized", "Photographed", "Released", "Destroyed"])
        self.disposition.setFixedWidth(90)

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("background-color: #8a5a5a; padding: 0;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))

        layout.addWidget(self.evidence_type)
        layout.addWidget(self.description)
        layout.addWidget(self.disposition)
        layout.addWidget(remove_btn)


class EvidenceWidget(MultiEntryWidget):
    """Widget for multiple evidence entries"""

    def __init__(self, parent=None):
        super().__init__(parent, "Evidence")

    def add_entry(self):
        entry = EvidenceEntry()
        entry.removed.connect(self.remove_entry)
        self.entries.append(entry)
        self.entries_layout.addWidget(entry)

    def get_data(self) -> list:
        return [{
            'evidence_type': e.evidence_type.currentText(),
            'description': e.description.text().strip(),
            'disposition': e.disposition.currentText()
        } for e in self.entries if e.description.text().strip()]


# ============ SUBJECT INTAKE DIALOG ============

class SubjectIntakeDialog(QDialog):
    """Full subject intake form - standalone entry point"""

    def __init__(self, parent, db: TrackerDB, subject_data=None):
        super().__init__(parent)
        self.db = db
        self.subject_data = subject_data
        self.setWindowTitle("New Subject" if not subject_data else "Edit Subject")
        self.setMinimumSize(650, 800)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        form = QVBoxLayout(content)

        # Photo
        photo_row = QHBoxLayout()
        self.photo = PhotoUploadWidget(label="Profile Photo")
        self.photo.setFixedSize(150, 150)
        photo_row.addWidget(self.photo)

        # Basic info next to photo
        basic_form = QFormLayout()
        name_row = QHBoxLayout()
        self.first_name = QLineEdit()
        self.first_name.setPlaceholderText("First")
        self.last_name = QLineEdit()
        self.last_name.setPlaceholderText("Last")
        name_row.addWidget(self.first_name)
        name_row.addWidget(self.last_name)
        basic_form.addRow("Name:", name_row)

        self.dob = QDateEdit()
        self.dob.setCalendarPopup(True)
        self.dob.setDisplayFormat("yyyy-MM-dd")
        self.dob.setSpecialValueText("Unknown")
        basic_form.addRow("DOB:", self.dob)

        self.monikers = QLineEdit()
        self.monikers.setPlaceholderText("Aliases, nicknames")
        basic_form.addRow("Monikers:", self.monikers)

        photo_row.addLayout(basic_form)
        form.addLayout(photo_row)

        # Photo gallery (shown when editing existing subject with photos)
        self.gallery_container = QWidget()
        self.gallery_layout = QVBoxLayout(self.gallery_container)
        self.gallery_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery_container.hide()  # Hidden until populated
        form.addWidget(self.gallery_container)

        # Government Identifiers Section (SSN, OLN, State ID, RISSAFE, etc.)
        id_group = QGroupBox("Government Identifiers")
        id_layout = QVBoxLayout(id_group)
        self.state_ids = StateIdWidget()
        id_layout.addWidget(self.state_ids)
        form.addWidget(id_group)

        # Physical Descriptors Section
        phys_group = QGroupBox("Physical Descriptors")
        phys_layout = QFormLayout(phys_group)

        phys_row1 = QHBoxLayout()
        self.sex = QComboBox()
        self.sex.addItems(["", "Male", "Female", "Other"])
        self.sex.setFixedWidth(80)
        phys_row1.addWidget(QLabel("Sex:"))
        phys_row1.addWidget(self.sex)

        self.race = QComboBox()
        self.race.setEditable(True)
        self.race.addItems(["", "White", "Black", "Hispanic", "Asian", "Native American", "Pacific Islander", "Other"])
        self.race.setFixedWidth(120)
        phys_row1.addWidget(QLabel("Race:"))
        phys_row1.addWidget(self.race)
        phys_row1.addStretch()
        phys_layout.addRow(phys_row1)

        phys_row2 = QHBoxLayout()
        self.height = QLineEdit()
        self.height.setPlaceholderText("5'10\"")
        self.height.setFixedWidth(60)
        phys_row2.addWidget(QLabel("Height:"))
        phys_row2.addWidget(self.height)

        self.weight = QLineEdit()
        self.weight.setPlaceholderText("180")
        self.weight.setFixedWidth(50)
        phys_row2.addWidget(QLabel("Weight:"))
        phys_row2.addWidget(self.weight)

        self.build = QComboBox()
        self.build.setEditable(True)
        self.build.addItems(["", "Slim", "Medium", "Heavy", "Athletic", "Muscular"])
        self.build.setFixedWidth(80)
        phys_row2.addWidget(QLabel("Build:"))
        phys_row2.addWidget(self.build)
        phys_row2.addStretch()
        phys_layout.addRow(phys_row2)

        phys_row3 = QHBoxLayout()
        self.hair_color = QComboBox()
        self.hair_color.setEditable(True)
        self.hair_color.addItems(["", "Black", "Brown", "Blonde", "Red", "Gray", "White", "Bald"])
        self.hair_color.setFixedWidth(80)
        phys_row3.addWidget(QLabel("Hair:"))
        phys_row3.addWidget(self.hair_color)

        self.eye_color = QComboBox()
        self.eye_color.setEditable(True)
        self.eye_color.addItems(["", "Brown", "Blue", "Green", "Hazel", "Gray", "Black"])
        self.eye_color.setFixedWidth(80)
        phys_row3.addWidget(QLabel("Eyes:"))
        phys_row3.addWidget(self.eye_color)
        phys_row3.addStretch()
        phys_layout.addRow(phys_row3)

        form.addWidget(phys_group)

        # Gang/Organization Section
        gang_group = QGroupBox("Gang/Organization")
        gang_layout = QFormLayout(gang_group)

        gang_row = QHBoxLayout()
        self.gang = QComboBox()
        self.gang.setEditable(True)
        self.gang.addItem("")
        for g in self.db.get_all_gangs():
            self.gang.addItem(g['name'], g['id'])
        gang_row.addWidget(self.gang)

        self.gang_role = QComboBox()
        self.gang_role.setEditable(True)
        self.gang_role.addItems([
            "Member", "Associate", "Prospect", "OG", "Shot Caller",
            # 1% Outlaw MC positions
            "President", "Vice President", "Secretary", "Treasurer",
            "Sergeant at Arms", "Road Captain", "Enforcer",
            "Prospect (MC)", "Hang-Around", "Nomad",
            # General
            "Leader", "Founder", "Lieutenant", "Soldier", "Recruit"
        ])
        gang_row.addWidget(self.gang_role)
        gang_layout.addRow("Gang/Org:", gang_row)

        form.addWidget(gang_group)

        # Locations Section
        loc_group = QGroupBox("Locations")
        loc_layout = QVBoxLayout(loc_group)
        self.locations = LocationWidget()
        loc_layout.addWidget(self.locations)
        form.addWidget(loc_group)

        # Contact Info Section
        contact_group = QGroupBox("Contact Information")
        contact_layout = QVBoxLayout(contact_group)

        self.phones = PhoneWidget()
        contact_layout.addWidget(self.phones)

        self.emails = EmailWidget()
        contact_layout.addWidget(self.emails)

        self.socials = SocialMediaWidget()
        contact_layout.addWidget(self.socials)

        form.addWidget(contact_group)

        # Family Section
        family_group = QGroupBox("Family")
        family_layout = QVBoxLayout(family_group)
        self.family = FamilyWidget(subjects=self.db.get_all_subjects())
        family_layout.addWidget(self.family)
        form.addWidget(family_group)

        # Tattoos Section
        tattoo_group = QGroupBox("Tattoos")
        tattoo_layout = QVBoxLayout(tattoo_group)
        self.tattoos = TattooWidget()
        tattoo_layout.addWidget(self.tattoos)
        form.addWidget(tattoo_group)

        # Vehicles Section
        vehicle_group = QGroupBox("Vehicles")
        vehicle_layout = QVBoxLayout(vehicle_group)
        self.vehicles = VehicleWidget()
        vehicle_layout.addWidget(self.vehicles)
        form.addWidget(vehicle_group)

        # Weapons Section
        weapon_group = QGroupBox("Weapons")
        weapon_layout = QVBoxLayout(weapon_group)
        self.weapons = WeaponWidget()
        weapon_layout.addWidget(self.weapons)
        form.addWidget(weapon_group)

        # Employment / Business Affiliation Section
        emp_group = QGroupBox("Employment / Business Affiliation")
        emp_layout = QVBoxLayout(emp_group)
        self.employment = EmploymentWidget()
        emp_layout.addWidget(self.employment)
        form.addWidget(emp_group)

        # Court Cases Section
        case_group = QGroupBox("Court Cases")
        case_layout = QVBoxLayout(case_group)
        self.case_numbers = CaseNumberWidget()
        case_layout.addWidget(self.case_numbers)
        form.addWidget(case_group)

        # Intel Section
        intel_group = QGroupBox("Intelligence")
        intel_layout = QFormLayout(intel_group)

        self.mo = QTextEdit()
        self.mo.setMaximumHeight(80)
        self.mo.setPlaceholderText("Modus Operandi - patterns, methods, behaviors")
        intel_layout.addRow("MO:", self.mo)

        self.criminal_history = QTextEdit()
        self.criminal_history.setMaximumHeight(80)
        self.criminal_history.setPlaceholderText("Prior arrests, convictions, warrants")
        intel_layout.addRow("Crim History:", self.criminal_history)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        self.notes.setPlaceholderText("Additional notes")
        intel_layout.addRow("Notes:", self.notes)

        form.addWidget(intel_group)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Pre-fill if editing
        if self.subject_data:
            self.populate_fields()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Subject")
        save_btn.setStyleSheet("background-color: #5a8a6a; font-weight: bold;")
        save_btn.clicked.connect(self.save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def populate_fields(self):
        """Pre-fill fields when editing"""
        d = self.subject_data
        self.first_name.setText(d.get('first_name', ''))
        self.last_name.setText(d.get('last_name', ''))
        if d.get('dob'):
            self.dob.setDate(QDate.fromString(d['dob'], "yyyy-MM-dd"))
        self.monikers.setText(d.get('monikers', ''))

        # Load legacy SSN/OLN fields into the identifiers widget
        if d.get('ssn'):
            self.state_ids.add_entry(default_type="SSN")
            self.state_ids.entries[-1].id_number.setText(d['ssn'])
        if d.get('oln'):
            self.state_ids.add_entry(default_type="OLN")
            self.state_ids.entries[-1].id_number.setText(d['oln'])

        # Physical descriptors
        self.sex.setCurrentText(d.get('sex', ''))
        self.race.setCurrentText(d.get('race', ''))
        self.height.setText(d.get('height', ''))
        self.weight.setText(d.get('weight', ''))
        self.build.setCurrentText(d.get('build', ''))
        self.hair_color.setCurrentText(d.get('hair_color', ''))
        self.eye_color.setCurrentText(d.get('eye_color', ''))
        self.mo.setText(d.get('mo', ''))
        self.criminal_history.setText(d.get('criminal_history', ''))
        self.notes.setText(d.get('notes', ''))

        # Show photo gallery if there are existing photos
        media_list = self.db.get_entity_media('subject', d['id'])
        images = [m for m in media_list if m.get('file_path', '').lower().endswith(
            ('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]
        if images:
            gallery = PhotoGalleryWidget(self.db, 'subject', d['id'], self)
            self.gallery_layout.addWidget(gallery)
            self.gallery_container.show()

    def get_or_create_gang_with_dialog(self, gang_name: str, existing_id=None) -> str:
        """If gang is new, open dialog to fill details. Returns gang_id."""
        if existing_id:
            return existing_id

        # Check if gang exists
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id FROM gangs WHERE LOWER(name) = LOWER(?)", (gang_name,))
        row = cursor.fetchone()
        if row:
            return row['id']

        # New gang - open dialog with name pre-filled
        dialog = GangDialog(self, self.db)
        dialog.name.setText(gang_name)
        dialog.setWindowTitle(f"New Gang: {gang_name}")
        if dialog.exec():
            data = dialog.get_data()
            name = data.pop('name')
            photo_path = data.pop('photo', None)
            gang_id = self.db.add_gang(name, **data)
            if photo_path and gang_id:
                self.db.add_media('gang', gang_id, photo_path, file_type='image')
            return gang_id
        else:
            # User cancelled - create minimal entry
            return self.db.add_gang(gang_name)

    def save(self):
        """Save the subject"""
        if not self.first_name.text().strip() and not self.last_name.text().strip():
            QMessageBox.warning(self, "Missing Data", "Name is required.")
            return

        # Create or update subject
        data = {
            'first_name': self.first_name.text().strip(),
            'last_name': self.last_name.text().strip(),
            'dob': self.dob.date().toString("yyyy-MM-dd") if self.dob.date().isValid() else '',
            'monikers': self.monikers.text().strip(),
            'sex': self.sex.currentText(),
            'race': self.race.currentText(),
            'height': self.height.text().strip(),
            'weight': self.weight.text().strip(),
            'build': self.build.currentText(),
            'hair_color': self.hair_color.currentText(),
            'eye_color': self.eye_color.currentText(),
            'mo': self.mo.toPlainText().strip(),
            'criminal_history': self.criminal_history.toPlainText().strip(),
            'notes': self.notes.toPlainText().strip()
        }

        if self.subject_data:
            # Update existing
            subject_id = self.subject_data['id']
            self.db.update_subject(subject_id, **data)
        else:
            # Create new - extract names, pass rest as kwargs
            first = data.pop('first_name')
            last = data.pop('last_name')
            subject_id = self.db.add_subject(first, last, **data)

        # Handle photo (already copied by PhotoUploadWidget)
        if self.photo.photo_path:
            self.db.update_subject(subject_id, profile_photo=self.photo.photo_path)
            # Also register in media table for gallery and pinning
            self.db.add_media('subject', subject_id, self.photo.photo_path, file_type='image')

        # Handle gang - prompt for details if new
        gang_name = self.gang.currentText().strip()
        if gang_name:
            gang_id = self.get_or_create_gang_with_dialog(gang_name, self.gang.currentData())
            self.db.link_subject_to_gang(subject_id, gang_id, role=self.gang_role.currentText())

        # Handle locations
        for loc in self.locations.get_data():
            loc_type = loc['loc_type'].lower()
            is_primary = 1 if loc_type == 'residence' else 0
            loc_id = self.db.find_or_create_location(loc['address'], type=loc_type)
            self.db.link_subject_to_location(subject_id, loc_id,
                                              relationship=loc['loc_type'],
                                              is_primary_residence=is_primary)

        # Handle phones
        for phone in self.phones.get_data():
            self.db.add_phone_number(subject_id, phone['number'], phone_type=phone['phone_type'])

        # Handle emails
        for email in self.emails.get_data():
            self.db.add_email(subject_id, email['email'], email_type=email['email_type'])

        # Handle social media
        for social in self.socials.get_data():
            self.db.add_social_profile(subject_id, social['platform'], url=social['url'])

        # Handle family
        for fam in self.family.get_data():
            self.db.add_family_member(subject_id, fam['relationship'],
                                       family_name=fam['family_name'],
                                       family_member_id=fam['family_member_id'])

        # Handle tattoos
        for tattoo in self.tattoos.get_data():
            self.db.add_tattoo(subject_id, tattoo['description'],
                              body_location=tattoo['body_location'],
                              is_gang_affiliated=tattoo['is_gang_affiliated'])

        # Handle vehicles
        for vehicle in self.vehicles.get_data():
            vehicle_id = self.db.find_or_create_vehicle(
                vehicle['plate'],
                state=vehicle['state'],
                make=vehicle['make'],
                model=vehicle['model'],
                year=vehicle['year'],
                color=vehicle['color']
            )
            self.db.link_subject_to_vehicle(subject_id, vehicle_id,
                                            relationship=vehicle['relationship'])

        # Handle weapons
        for weapon in self.weapons.get_data():
            weapon_id = self.db.find_or_create_weapon(
                weapon['serial_number'],
                weapon_type=weapon['weapon_type'],
                make=weapon['make'],
                model=weapon['model'],
                caliber=weapon['caliber']
            )
            self.db.link_subject_to_weapon(subject_id, weapon_id,
                                           relationship=weapon['relationship'])

        # Handle government identifiers (SSN, OLN, State ID, etc.)
        for sid in self.state_ids.get_data():
            id_type = sid['id_type']
            id_num = sid['id_number']
            # Store SSN/OLN on the subject record too (for search/backward compat)
            if id_type == 'SSN':
                self.db.update_subject(subject_id, ssn=id_num)
            elif id_type == 'OLN':
                state = sid.get('state', '')
                oln_val = f"{id_num} ({state})" if state else id_num
                self.db.update_subject(subject_id, oln=oln_val)
            self.db.add_state_id(subject_id, id_num,
                                 id_type=id_type,
                                 state=sid['state'])

        # Handle employment
        for emp in self.employment.get_data():
            self.db.add_employment(subject_id, emp['employer'],
                                   position=emp['position'],
                                   address=emp['address'],
                                   phone=emp['phone'])

        # Handle court cases
        for case in self.case_numbers.get_data():
            self.db.add_case_number(subject_id, case['case_number'],
                                    case_type=case['case_type'],
                                    status=case['status'],
                                    url=case['url'])

        self.accept()


# ============ EVENT INTAKE (Simplified for space) ============

class SubjectEventEntry(QFrame):
    """Subject entry within event intake"""
    removed = pyqtSignal(object)

    def __init__(self, parent=None, num=1, gangs=None):
        super().__init__(parent)
        self.num = num
        self.gangs = gangs or []
        self.setStyleSheet("QFrame { background: #1e2a4a; border: 1px solid #3a4a6a; border-radius: 6px; padding: 8px; margin: 4px; }")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        self.header_label = QLabel(f"Subject #{self.num}")
        self.header_label.setStyleSheet("font-weight: bold; color: #4a7c9b;")
        header.addWidget(self.header_label)
        header.addStretch()
        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setStyleSheet("background-color: #8a5a5a;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))
        header.addWidget(remove_btn)
        layout.addLayout(header)

        # Fields
        form = QFormLayout()

        name_row = QHBoxLayout()
        self.first_name = QLineEdit()
        self.first_name.setPlaceholderText("First")
        self.last_name = QLineEdit()
        self.last_name.setPlaceholderText("Last")
        name_row.addWidget(self.first_name)
        name_row.addWidget(self.last_name)
        form.addRow("Name:", name_row)

        self.dob = QDateEdit()
        self.dob.setCalendarPopup(True)
        self.dob.setDisplayFormat("yyyy-MM-dd")
        form.addRow("DOB:", self.dob)

        pii_row = QHBoxLayout()
        self.ssn = QLineEdit()
        self.ssn.setPlaceholderText("SSN")
        self.oln = QLineEdit()
        self.oln.setPlaceholderText("OLN")
        self.state_id = QLineEdit()
        self.state_id.setPlaceholderText("State ID")
        pii_row.addWidget(self.ssn)
        pii_row.addWidget(self.oln)
        pii_row.addWidget(self.state_id)
        form.addRow("IDs:", pii_row)

        self.monikers = QLineEdit()
        self.monikers.setPlaceholderText("Aliases")
        form.addRow("Monikers:", self.monikers)

        gang_row = QHBoxLayout()
        self.gang = QComboBox()
        self.gang.setEditable(True)
        self.gang.addItem("")
        for g in self.gangs:
            self.gang.addItem(g['name'], g['id'])
        self.gang_role = QComboBox()
        self.gang_role.setEditable(True)
        self.gang_role.addItems([
            "Member", "Associate", "Prospect", "OG", "Shot Caller",
            "President", "Vice President", "Sergeant at Arms", "Road Captain",
            "Leader", "Soldier"
        ])
        gang_row.addWidget(self.gang)
        gang_row.addWidget(self.gang_role)
        form.addRow("Gang:", gang_row)

        self.residence = QLineEdit()
        self.residence.setPlaceholderText("Address")
        form.addRow("Residence:", self.residence)

        self.event_role = QComboBox()
        self.event_role.setEditable(True)
        self.event_role.addItems(["Arrested", "Suspect", "Witness", "Victim", "POI", "Driver", "Passenger"])
        form.addRow("Role:", self.event_role)

        layout.addLayout(form)

    def set_number(self, n):
        self.num = n
        self.header_label.setText(f"Subject #{n}")

    def is_valid(self):
        return bool(self.first_name.text().strip() or self.last_name.text().strip())

    def get_data(self):
        return {
            'first_name': self.first_name.text().strip(),
            'last_name': self.last_name.text().strip(),
            'dob': self.dob.date().toString("yyyy-MM-dd") if self.dob.date().isValid() else '',
            'ssn': self.ssn.text().strip(),
            'oln': self.oln.text().strip(),
            'state_id': self.state_id.text().strip(),
            'monikers': self.monikers.text().strip(),
            'gang_name': self.gang.currentText().strip(),
            'gang_id': self.gang.currentData(),
            'gang_role': self.gang_role.currentText(),
            'residence': self.residence.text().strip(),
            'event_role': self.event_role.currentText()
        }


class ExistingSubjectEntry(QFrame):
    """Displays an existing subject attached to an event"""
    removed = pyqtSignal(object)

    def __init__(self, subject_data, parent=None):
        super().__init__(parent)
        self.subject_data = subject_data
        self.subject_id = subject_data['id']
        self.setStyleSheet("QFrame { background: #1e3a2a; border: 1px solid #3a6a4a; border-radius: 6px; padding: 8px; margin: 4px; }")
        layout = QHBoxLayout(self)

        name = f"{subject_data.get('first_name', '')} {subject_data.get('last_name', '')}".strip()
        monikers = subject_data.get('monikers', '')
        display = name or "(Unknown)"
        if monikers:
            display += f'  aka "{monikers}"'
        label = QLabel(display)
        label.setStyleSheet("font-weight: bold; color: #6aaa8a;")
        layout.addWidget(label)

        layout.addStretch()

        self.event_role = QComboBox()
        self.event_role.setEditable(True)
        self.event_role.addItems(["Arrested", "Suspect", "Witness", "Victim", "POI", "Driver", "Passenger"])
        self.event_role.setFixedWidth(120)
        layout.addWidget(QLabel("Role:"))
        layout.addWidget(self.event_role)

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setStyleSheet("background-color: #8a5a5a;")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(remove_btn)


class EventIntakeDialog(QDialog):
    """Event intake with multiple subjects"""

    def __init__(self, parent, db: TrackerDB):
        super().__init__(parent)
        self.db = db
        self.subjects = []
        self.existing_subjects = []
        self.setWindowTitle("New Event")
        self.setMinimumSize(700, 750)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Create scroll area for entire form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container widget for all form content
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # Event details
        event_group = QGroupBox("Event Details")
        event_form = QFormLayout(event_group)
        event_form.setSpacing(10)

        self.event_number = QLineEdit()
        self.event_number.setPlaceholderText("Case/Event Number")
        event_form.addRow("Event #:", self.event_number)

        self.event_date = QDateEdit()
        self.event_date.setCalendarPopup(True)
        self.event_date.setDate(QDate.currentDate())
        event_form.addRow("Date:", self.event_date)

        self.event_type = QComboBox()
        self.event_type.setEditable(True)
        self.event_type.addItems(["Arrest", "Traffic Stop", "Field Interview", "Crime Report", "Shooting", "Other"])
        event_form.addRow("Type:", self.event_type)

        # Location - Street Number and Name
        loc_street_row = QHBoxLayout()
        self.loc_street_num = QLineEdit()
        self.loc_street_num.setPlaceholderText("#")
        self.loc_street_num.setFixedWidth(80)
        loc_street_row.addWidget(self.loc_street_num)
        self.loc_street_name = QLineEdit()
        self.loc_street_name.setPlaceholderText("Street")
        loc_street_row.addWidget(self.loc_street_name)
        event_form.addRow("Address:", loc_street_row)

        # Location - City, State, Zip
        loc_city_row = QHBoxLayout()
        self.loc_city = QLineEdit()
        self.loc_city.setPlaceholderText("City")
        loc_city_row.addWidget(self.loc_city)
        self.loc_state = QComboBox()
        self.loc_state.setEditable(True)
        self.loc_state.setFixedWidth(70)
        self.loc_state.addItems(US_STATES)
        loc_city_row.addWidget(self.loc_state)
        self.loc_zip = QLineEdit()
        self.loc_zip.setPlaceholderText("Zip")
        self.loc_zip.setFixedWidth(80)
        loc_city_row.addWidget(self.loc_zip)
        event_form.addRow("City/State/Zip:", loc_city_row)

        self.gang = QComboBox()
        self.gang.setEditable(True)
        self.gang.addItem("")
        for g in self.db.get_all_gangs():
            self.gang.addItem(g['name'], g['id'])
        event_form.addRow("Gang:", self.gang)

        self.details = QTextEdit()
        self.details.setMinimumHeight(80)
        self.details.setPlaceholderText("Event details...")
        event_form.addRow("Details:", self.details)

        self.notes = QTextEdit()
        self.notes.setMinimumHeight(80)
        self.notes.setPlaceholderText("Additional notes...")
        event_form.addRow("Notes:", self.notes)

        # Call Source Section
        source_row = QHBoxLayout()
        self.generated_source = QComboBox()
        self.generated_source.setEditable(True)
        self.generated_source.addItems(["", "911", "Patrol", "Walk-in", "Dispatch", "Self-Initiated", "Other"])
        source_row.addWidget(QLabel("Generated Source:"))
        source_row.addWidget(self.generated_source)

        self.code_400 = QLineEdit()
        self.code_400.setPlaceholderText("400 Code")
        self.code_400.setFixedWidth(100)
        source_row.addWidget(QLabel("400 Code:"))
        source_row.addWidget(self.code_400)
        source_row.addStretch()
        event_form.addRow(source_row)

        layout.addWidget(event_group)

        # Weapons Section
        weapon_group = QGroupBox("Weapons Involved")
        weapon_layout = QVBoxLayout(weapon_group)
        self.weapons = WeaponWidget()
        weapon_layout.addWidget(self.weapons)
        layout.addWidget(weapon_group)

        # Evidence Section
        evidence_group = QGroupBox("Evidence Collected")
        evidence_layout = QVBoxLayout(evidence_group)
        self.evidence = EvidenceWidget()
        evidence_layout.addWidget(self.evidence)
        layout.addWidget(evidence_group)

        # Vehicles Section
        vehicle_group = QGroupBox("Vehicles Involved")
        vehicle_layout = QVBoxLayout(vehicle_group)
        self.event_vehicles = VehicleWidget()
        vehicle_layout.addWidget(self.event_vehicles)
        layout.addWidget(vehicle_group)

        # Photo upload
        photo_group = QGroupBox("Photo/Evidence")
        photo_layout = QVBoxLayout(photo_group)
        self.photo = PhotoUploadWidget(label="event photo")
        photo_layout.addWidget(self.photo)
        layout.addWidget(photo_group)

        # Subjects Section
        subjects_group = QGroupBox("Subjects Involved (Optional)")
        subjects_layout = QVBoxLayout(subjects_group)

        # Button row
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add New Subject")
        add_btn.setStyleSheet("background-color: #5a8a6a; padding: 8px; font-weight: bold; font-size: 14px;")
        add_btn.clicked.connect(self.add_subject)
        btn_row.addWidget(add_btn)

        attach_btn = QPushButton("+ Attach Existing Subject")
        attach_btn.setStyleSheet("background-color: #4a6a8a; padding: 8px; font-weight: bold; font-size: 14px;")
        attach_btn.clicked.connect(self.attach_existing_subject)
        btn_row.addWidget(attach_btn)
        subjects_layout.addLayout(btn_row)

        # Subject entries container
        self.subj_container = QWidget()
        self.subj_layout = QVBoxLayout(self.subj_container)
        self.subj_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.subj_layout.setSpacing(10)
        subjects_layout.addWidget(self.subj_container)

        layout.addWidget(subjects_group)

        # Add stretch at bottom
        layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Buttons - outside scroll area
        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        save = QPushButton("Save Event")
        save.setStyleSheet("background-color: #5a8a6a; padding: 10px 20px;")
        save.clicked.connect(self.save)
        btns.addWidget(save)
        main_layout.addLayout(btns)

    def add_subject(self):
        gangs = self.db.get_all_gangs()
        entry = SubjectEventEntry(num=len(self.subjects) + 1, gangs=gangs)
        entry.removed.connect(self.remove_subject)
        self.subjects.append(entry)
        self.subj_layout.addWidget(entry)

    def remove_subject(self, widget):
        if widget in self.subjects:
            self.subjects.remove(widget)
            widget.deleteLater()
            for i, s in enumerate(self.subjects):
                s.set_number(i + 1)
        elif widget in self.existing_subjects:
            self.existing_subjects.remove(widget)
            widget.deleteLater()

    def attach_existing_subject(self):
        """Open search dialog to find and attach an existing subject"""
        dlg = QDialog(self)
        dlg.setWindowTitle("Attach Existing Subject")
        dlg.setMinimumSize(400, 350)
        lay = QVBoxLayout(dlg)

        search_row = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search by name, alias, SSN, OLN...")
        search_row.addWidget(search_input)
        search_btn = QPushButton("Search")
        search_row.addWidget(search_btn)
        lay.addLayout(search_row)

        results_list = QListWidget()
        lay.addWidget(results_list)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)
        select_btn = QPushButton("Attach Selected")
        select_btn.setStyleSheet("background-color: #5a8a6a; padding: 8px;")
        select_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(select_btn)
        lay.addLayout(btn_row)

        subjects_cache = []

        def do_search():
            query = search_input.text().strip()
            results_list.clear()
            subjects_cache.clear()
            if not query:
                return
            results = self.db.search_subjects(query)
            # Filter out already-attached existing subjects
            attached_ids = {e.subject_id for e in self.existing_subjects}
            for subj in results:
                if subj['id'] in attached_ids:
                    continue
                name = f"{subj.get('first_name', '')} {subj.get('last_name', '')}".strip()
                monikers = subj.get('monikers', '')
                display = name or "(Unknown)"
                if monikers:
                    display += f'  aka "{monikers}"'
                if subj.get('dob'):
                    display += f"  DOB: {subj['dob']}"
                item = QListWidgetItem(display)
                results_list.addItem(item)
                subjects_cache.append(subj)

        search_btn.clicked.connect(do_search)
        search_input.returnPressed.connect(do_search)
        results_list.itemDoubleClicked.connect(dlg.accept)

        if dlg.exec():
            row = results_list.currentRow()
            if 0 <= row < len(subjects_cache):
                subj = subjects_cache[row]
                entry = ExistingSubjectEntry(subj)
                entry.removed.connect(self.remove_subject)
                self.existing_subjects.append(entry)
                self.subj_layout.addWidget(entry)

    def get_or_create_gang_with_dialog(self, gang_name: str, existing_id=None) -> str:
        """If gang is new, open dialog to fill details. Returns gang_id."""
        if existing_id:
            return existing_id

        # Check if gang exists
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id FROM gangs WHERE LOWER(name) = LOWER(?)", (gang_name,))
        row = cursor.fetchone()
        if row:
            return row['id']

        # New gang - open dialog with name pre-filled
        dialog = GangDialog(self, self.db)
        dialog.name.setText(gang_name)
        dialog.setWindowTitle(f"New Gang: {gang_name}")
        if dialog.exec():
            data = dialog.get_data()
            name = data.pop('name')
            photo_path = data.pop('photo', None)
            gang_id = self.db.add_gang(name, **data)
            if photo_path and gang_id:
                self.db.add_media('gang', gang_id, photo_path, file_type='image')
            return gang_id
        else:
            # User cancelled - create minimal entry
            return self.db.add_gang(gang_name)

    def save(self):
        if not self.event_number.text().strip():
            QMessageBox.warning(self, "Error", "Event number required.")
            return

        valid = [s for s in self.subjects if s.is_valid()]

        # Build location address from components
        loc_parts = []
        street_num = self.loc_street_num.text().strip()
        street_name = self.loc_street_name.text().strip()
        city = self.loc_city.text().strip()
        state = self.loc_state.currentText().strip()
        zipcode = self.loc_zip.text().strip()

        if street_num or street_name:
            loc_parts.append(f"{street_num} {street_name}".strip())
        if city:
            loc_parts.append(city)
        if state or zipcode:
            loc_parts.append(f"{state} {zipcode}".strip())

        loc_text = ", ".join(loc_parts) if loc_parts else ""
        loc_id = self.db.find_or_create_location(loc_text) if loc_text else None

        # Create event
        event_id = self.db.add_event(
            self.event_number.text().strip(),
            event_date=self.event_date.date().toString("yyyy-MM-dd"),
            event_type=self.event_type.currentText(),
            location_id=loc_id,
            location_text=loc_text,
            generated_source=self.generated_source.currentText(),
            code_400=self.code_400.text().strip(),
            details=self.details.toPlainText().strip(),
            case_notes=self.notes.toPlainText().strip()
        )

        # Link gang to event - prompt for details if new
        gang_name = self.gang.currentText().strip()
        if gang_name:
            gang_id = self.get_or_create_gang_with_dialog(gang_name, self.gang.currentData())
            self.db.link_gang_to_event(gang_id, event_id)

        # Process subjects
        subj_ids = []
        for s in valid:
            d = s.get_data()
            subj_id = self.db.find_or_create_subject(
                d['first_name'], d['last_name'],
                dob=d['dob'], ssn=d['ssn'], oln=d['oln'],
                monikers=d['monikers']
            )
            subj_ids.append(subj_id)
            self.db.link_subject_to_event(subj_id, event_id, role=d['event_role'])

            # Save IDs from event form as government identifiers
            if d.get('ssn'):
                self.db.add_state_id(subj_id, d['ssn'], id_type='SSN')
            if d.get('oln'):
                self.db.add_state_id(subj_id, d['oln'], id_type='OLN')
            if d.get('state_id'):
                self.db.add_state_id(subj_id, d['state_id'], id_type='State ID')

            # Handle subject's gang - prompt for details if new
            if d['gang_name']:
                gid = self.get_or_create_gang_with_dialog(d['gang_name'], d['gang_id'])
                self.db.link_subject_to_gang(subj_id, gid, role=d['gang_role'])

            if d['residence']:
                rid = self.db.find_or_create_location(d['residence'], type='residence')
                self.db.link_subject_to_location(subj_id, rid,
                                                  relationship='Residence',
                                                  is_primary_residence=1)

        # Process existing (attached) subjects
        for entry in self.existing_subjects:
            sid = entry.subject_id
            subj_ids.append(sid)
            self.db.link_subject_to_event(sid, event_id, role=entry.event_role.currentText())

        # Link subjects together
        for i, s1 in enumerate(subj_ids):
            for s2 in subj_ids[i+1:]:
                self.db.link_subjects(s1, s2, relationship='co-event')

        # Handle weapons
        for weapon in self.weapons.get_data():
            weapon_id = self.db.find_or_create_weapon(
                weapon['serial_number'],
                weapon_type=weapon['weapon_type'],
                make=weapon['make'],
                model=weapon['model'],
                caliber=weapon['caliber']
            )
            self.db.link_event_to_weapon(event_id, weapon_id,
                                         disposition=weapon.get('relationship', ''))

        # Handle evidence
        for ev in self.evidence.get_data():
            self.db.add_evidence(event_id, ev['description'],
                                evidence_type=ev['evidence_type'],
                                disposition=ev['disposition'])

        # Handle vehicles
        for vehicle in self.event_vehicles.get_data():
            vehicle_id = self.db.find_or_create_vehicle(
                vehicle['plate'],
                state=vehicle['state'],
                make=vehicle['make'],
                model=vehicle['model'],
                year=vehicle['year'],
                color=vehicle['color']
            )
            self.db.link_event_to_vehicle(event_id, vehicle_id)
            # Link vehicle to all subjects in this event
            for sid in subj_ids:
                if not self.db.is_subject_linked_to_vehicle(sid, vehicle_id):
                    self.db.link_subject_to_vehicle(sid, vehicle_id)

        # Register photo in media table (already copied by PhotoUploadWidget)
        if self.photo.photo_path and event_id:
            self.db.add_media('event', event_id, self.photo.photo_path, file_type='image')

        self.accept()


# ============ GANG DIALOG ============

class GangDialog(QDialog):
    def __init__(self, parent, db, gang_data=None):
        super().__init__(parent)
        self.db = db
        self.gang_data = gang_data
        self.setWindowTitle("New Gang" if not gang_data else "Edit Gang")
        self.setMinimumSize(500, 450)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QFormLayout(container)
        layout.setSpacing(15)

        self.name = QLineEdit()
        self.name.setPlaceholderText("Gang name")
        layout.addRow("Name:", self.name)

        self.details = QTextEdit()
        self.details.setMinimumHeight(100)
        self.details.setPlaceholderText("Gang details, history, structure...")
        layout.addRow("Details:", self.details)

        self.territory = QLineEdit()
        self.territory.setPlaceholderText("Known territory/turf")
        layout.addRow("Territory:", self.territory)

        self.identifiers = QTextEdit()
        self.identifiers.setMinimumHeight(100)
        self.identifiers.setPlaceholderText("Colors, signs, tattoos, symbols...")
        layout.addRow("Identifiers:", self.identifiers)

        # Photo upload
        photo_group = QGroupBox("Photo")
        photo_layout = QVBoxLayout(photo_group)
        self.photo = PhotoUploadWidget(label="gang photo/logo")
        photo_layout.addWidget(self.photo)

        # Photo gallery container (shown when editing with existing photos)
        self.gallery_container = QWidget()
        self.gallery_layout = QVBoxLayout(self.gallery_container)
        self.gallery_layout.setContentsMargins(0, 5, 0, 0)
        self.gallery_container.hide()
        photo_layout.addWidget(self.gallery_container)

        layout.addRow(photo_group)

        if self.gang_data:
            self.name.setText(self.gang_data.get('name', ''))
            self.details.setText(self.gang_data.get('details', ''))
            self.territory.setText(self.gang_data.get('territory', ''))
            self.identifiers.setText(self.gang_data.get('identifiers', ''))
            if self.gang_data.get('photo'):
                self.photo.set_photo(self.gang_data['photo'])
            # Show photo gallery if there are existing photos
            media_list = self.db.get_entity_media('gang', self.gang_data['id'])
            images = [m for m in media_list if m.get('file_path', '').lower().endswith(
                ('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]
            if images:
                gallery = PhotoGalleryWidget(self.db, 'gang', self.gang_data['id'], self)
                self.gallery_layout.addWidget(gallery)
                self.gallery_container.show()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Buttons outside scroll
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

    def get_data(self):
        return {
            'name': self.name.text().strip(),
            'details': self.details.toPlainText().strip(),
            'territory': self.territory.text().strip(),
            'identifiers': self.identifiers.toPlainText().strip(),
            'photo': self.photo.photo_path
        }


# ============ CHARGE DIALOG ============

class ChargeDialog(QDialog):
    """Criminal Activity / Charge intake"""

    def __init__(self, parent, db: TrackerDB, charge_data=None):
        super().__init__(parent)
        self.db = db
        self.charge_data = charge_data
        self.setWindowTitle("New Criminal Activity" if not charge_data else "Edit Charge")
        self.setMinimumSize(600, 600)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # Charge Details Group
        charge_group = QGroupBox("Charge Details")
        form = QFormLayout(charge_group)
        form.setSpacing(10)

        self.charges_text = QLineEdit()
        self.charges_text.setPlaceholderText("Charge(s) - e.g., NRS 200.380 Robbery")
        form.addRow("Charges:", self.charges_text)

        self.charge_date = QDateEdit()
        self.charge_date.setCalendarPopup(True)
        self.charge_date.setDate(QDate.currentDate())
        form.addRow("Date:", self.charge_date)

        # Location - Street Number and Name
        loc_street_row = QHBoxLayout()
        self.loc_street_num = QLineEdit()
        self.loc_street_num.setPlaceholderText("#")
        self.loc_street_num.setFixedWidth(80)
        loc_street_row.addWidget(self.loc_street_num)
        self.loc_street_name = QLineEdit()
        self.loc_street_name.setPlaceholderText("Street")
        loc_street_row.addWidget(self.loc_street_name)
        form.addRow("Address:", loc_street_row)

        # Location - City, State, Zip
        loc_city_row = QHBoxLayout()
        self.loc_city = QLineEdit()
        self.loc_city.setPlaceholderText("City")
        loc_city_row.addWidget(self.loc_city)
        self.loc_state = QComboBox()
        self.loc_state.setEditable(True)
        self.loc_state.setFixedWidth(70)
        self.loc_state.addItems(US_STATES)
        loc_city_row.addWidget(self.loc_state)
        self.loc_zip = QLineEdit()
        self.loc_zip.setPlaceholderText("Zip")
        self.loc_zip.setFixedWidth(80)
        loc_city_row.addWidget(self.loc_zip)
        form.addRow("City/State/Zip:", loc_city_row)

        self.arrestee = QComboBox()
        self.arrestee.setEditable(True)
        self.arrestee.addItem("-- Select Arrestee --", None)
        for s in self.db.get_all_subjects():
            self.arrestee.addItem(f"{s['first_name']} {s['last_name']}", s['id'])
        form.addRow("Arrestee:", self.arrestee)

        self.event_link = QComboBox()
        self.event_link.addItem("-- Link to Event --", None)
        for e in self.db.get_all_events():
            self.event_link.addItem(f"{e['event_number']} ({e['event_date']})", e['id'])
        form.addRow("Event #:", self.event_link)

        self.court_case = QLineEdit()
        self.court_case.setPlaceholderText("Court Case Number")
        form.addRow("Court Case #:", self.court_case)

        self.court_url = QLineEdit()
        self.court_url.setPlaceholderText("Court URL for case lookup")
        form.addRow("Court URL:", self.court_url)

        self.gang = QComboBox()
        self.gang.setEditable(True)
        self.gang.addItem("", None)
        for g in self.db.get_all_gangs():
            self.gang.addItem(g['name'], g['id'])
        form.addRow("Gang:", self.gang)

        self.details = QTextEdit()
        self.details.setMinimumHeight(100)
        self.details.setPlaceholderText("Details about the charge...")
        form.addRow("Details:", self.details)

        layout.addWidget(charge_group)

        # Affiliates section
        aff_group = QGroupBox("Affiliates / Co-defendants")
        aff_layout = QVBoxLayout(aff_group)

        # Affiliate selector row
        aff_row = QHBoxLayout()
        self.affiliate_combo = QComboBox()
        self.affiliate_combo.addItem("-- Select Affiliate --", None)
        for s in self.db.get_all_subjects():
            self.affiliate_combo.addItem(f"{s['first_name']} {s['last_name']}", s['id'])
        aff_row.addWidget(self.affiliate_combo)

        add_aff_btn = QPushButton("Add")
        add_aff_btn.setFixedWidth(60)
        add_aff_btn.clicked.connect(self._add_selected_affiliate)
        aff_row.addWidget(add_aff_btn)

        new_aff_btn = QPushButton("+New")
        new_aff_btn.setFixedWidth(60)
        new_aff_btn.setStyleSheet("background-color: #5a8a6a; font-weight: bold; font-size: 14px;")
        new_aff_btn.clicked.connect(self._create_new_affiliate)
        aff_row.addWidget(new_aff_btn)
        aff_layout.addLayout(aff_row)

        # List of added affiliates
        self.selected_affiliates = []
        self.affiliates_list = QListWidget()
        self.affiliates_list.setMinimumHeight(100)
        self.affiliates_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.affiliates_list.customContextMenuRequested.connect(self._remove_affiliate_menu)
        aff_layout.addWidget(self.affiliates_list)

        remove_hint = QLabel("Right-click to remove affiliates")
        remove_hint.setStyleSheet("color: #888; font-size: 10px;")
        aff_layout.addWidget(remove_hint)
        layout.addWidget(aff_group)

        # Photo upload
        photo_group = QGroupBox("Photo/Evidence")
        photo_layout = QVBoxLayout(photo_group)
        self.photo = PhotoUploadWidget(label="evidence photo")
        photo_layout.addWidget(self.photo)
        layout.addWidget(photo_group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Buttons outside scroll
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

        # Load existing data for edit mode
        if self.charge_data:
            d = self.charge_data
            self.charges_text.setText(d.get('charges_text', ''))
            if d.get('charge_date'):
                self.charge_date.setDate(QDate.fromString(d['charge_date'], "yyyy-MM-dd"))
            if d.get('court_case_number'):
                self.court_case.setText(d['court_case_number'])
            if d.get('court_url'):
                self.court_url.setText(d['court_url'])
            if d.get('details'):
                self.details.setText(d['details'])
            # Select arrestee
            if d.get('subject_id'):
                for i in range(self.arrestee.count()):
                    if self.arrestee.itemData(i) == d['subject_id']:
                        self.arrestee.setCurrentIndex(i)
                        break
            # Select event
            if d.get('event_id'):
                for i in range(self.event_link.count()):
                    if self.event_link.itemData(i) == d['event_id']:
                        self.event_link.setCurrentIndex(i)
                        break
            # Select gang
            if d.get('gang_id'):
                for i in range(self.gang.count()):
                    if self.gang.itemData(i) == d['gang_id']:
                        self.gang.setCurrentIndex(i)
                        break

    def _add_selected_affiliate(self):
        """Add the currently selected affiliate from dropdown to the list"""
        affiliate_id = self.affiliate_combo.currentData()
        if affiliate_id is None:
            return
        # Check if already added
        if affiliate_id in self.selected_affiliates:
            QMessageBox.information(self, "Info", "Affiliate already added.")
            return
        affiliate_name = self.affiliate_combo.currentText()
        self.selected_affiliates.append(affiliate_id)
        item = QListWidgetItem(affiliate_name)
        item.setData(Qt.ItemDataRole.UserRole, affiliate_id)
        self.affiliates_list.addItem(item)
        self.affiliate_combo.setCurrentIndex(0)

    def _create_new_affiliate(self):
        """Open dialog to create a new subject/affiliate"""
        dlg = SubjectIntakeDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Refresh the dropdowns
            self.affiliate_combo.clear()
            self.affiliate_combo.addItem("-- Select Affiliate --", None)
            self.arrestee.clear()
            self.arrestee.addItem("-- Select Arrestee --", None)
            for s in self.db.get_all_subjects():
                name = f"{s['first_name']} {s['last_name']}"
                self.affiliate_combo.addItem(name, s['id'])
                self.arrestee.addItem(name, s['id'])

    def _remove_affiliate_menu(self, pos):
        """Show context menu to remove affiliate"""
        item = self.affiliates_list.itemAt(pos)
        if item:
            menu = QMenu(self)
            remove_action = menu.addAction("Remove")
            action = menu.exec(self.affiliates_list.mapToGlobal(pos))
            if action == remove_action:
                affiliate_id = item.data(Qt.ItemDataRole.UserRole)
                self.selected_affiliates.remove(affiliate_id)
                self.affiliates_list.takeItem(self.affiliates_list.row(item))

    def save(self):
        arrestee_id = self.arrestee.currentData()
        if not arrestee_id:
            QMessageBox.warning(self, "Error", "Arrestee is required.")
            return

        if not self.charges_text.text().strip():
            QMessageBox.warning(self, "Error", "Charges are required.")
            return

        # Build location address from components
        loc_parts = []
        street_num = self.loc_street_num.text().strip()
        street_name = self.loc_street_name.text().strip()
        city = self.loc_city.text().strip()
        state = self.loc_state.currentText().strip()
        zipcode = self.loc_zip.text().strip()

        if street_num or street_name:
            loc_parts.append(f"{street_num} {street_name}".strip())
        if city:
            loc_parts.append(city)
        if state or zipcode:
            loc_parts.append(f"{state} {zipcode}".strip())

        loc_text = ", ".join(loc_parts) if loc_parts else ""
        loc_id = self.db.find_or_create_location(loc_text) if loc_text else None

        # Get gang
        gang_name = self.gang.currentText().strip()
        gang_id = None
        if gang_name:
            gang_id = self.gang.currentData() or self.db.find_or_create_gang(gang_name)

        charge_kwargs = dict(
            charges_text=self.charges_text.text().strip(),
            event_id=self.event_link.currentData(),
            charge_date=self.charge_date.date().toString("yyyy-MM-dd"),
            location_id=loc_id,
            location_text=loc_text,
            court_case_number=self.court_case.text().strip(),
            court_url=self.court_url.text().strip(),
            gang_id=gang_id,
            details=self.details.toPlainText().strip()
        )

        if self.charge_data:
            # Update existing charge
            charge_id = self.charge_data['id']
            self.db.update_charge(charge_id, subject_id=arrestee_id, **charge_kwargs)
        else:
            # Create new charge
            charge_id = self.db.add_charge(
                arrestee_id,
                charge_kwargs.pop('charges_text'),
                **charge_kwargs
            )

        # Add affiliates
        for affiliate_id in self.selected_affiliates:
            if affiliate_id != arrestee_id:
                self.db.add_charge_affiliate(charge_id, affiliate_id, role='co-defendant')

        # Register photo in media table (already copied by PhotoUploadWidget)
        if self.photo.photo_path and charge_id:
            self.db.add_media('charge', charge_id, self.photo.photo_path, file_type='image')

        self.accept()


# ============ GRAFFITI DIALOG ============

class GraffitiDialog(QDialog):
    """Graffiti tracking intake"""

    def __init__(self, parent, db: TrackerDB, graffiti_data=None):
        super().__init__(parent)
        self.db = db
        self.graffiti_data = graffiti_data
        self.setWindowTitle("New Graffiti" if not graffiti_data else "Edit Graffiti")
        self.setMinimumSize(550, 600)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # Graffiti Details Group
        details_group = QGroupBox("Graffiti Details")
        form = QFormLayout(details_group)
        form.setSpacing(10)

        # Location - Street Number and Name
        loc_street_row = QHBoxLayout()
        self.loc_street_num = QLineEdit()
        self.loc_street_num.setPlaceholderText("#")
        self.loc_street_num.setFixedWidth(80)
        loc_street_row.addWidget(self.loc_street_num)
        self.loc_street_name = QLineEdit()
        self.loc_street_name.setPlaceholderText("Street")
        loc_street_row.addWidget(self.loc_street_name)
        form.addRow("Address:", loc_street_row)

        # Location - City, State, Zip
        loc_city_row = QHBoxLayout()
        self.loc_city = QLineEdit()
        self.loc_city.setPlaceholderText("City")
        loc_city_row.addWidget(self.loc_city)
        self.loc_state = QComboBox()
        self.loc_state.setEditable(True)
        self.loc_state.setFixedWidth(70)
        self.loc_state.addItems(US_STATES)
        loc_city_row.addWidget(self.loc_state)
        self.loc_zip = QLineEdit()
        self.loc_zip.setPlaceholderText("Zip")
        self.loc_zip.setFixedWidth(80)
        loc_city_row.addWidget(self.loc_zip)
        form.addRow("City/State/Zip:", loc_city_row)

        self.tags = QTextEdit()
        self.tags.setMinimumHeight(80)
        self.tags.setPlaceholderText("Graffiti tags observed")
        form.addRow("Graffiti Tags:", self.tags)

        self.gang = QComboBox()
        self.gang.setEditable(True)
        self.gang.addItem("", None)
        for g in self.db.get_all_gangs():
            self.gang.addItem(g['name'], g['id'])
        form.addRow("Gang:", self.gang)

        self.monikers = QLineEdit()
        self.monikers.setPlaceholderText("Monikers/names observed")
        form.addRow("Monikers:", self.monikers)

        self.sector_beat = QLineEdit()
        self.sector_beat.setPlaceholderText("Sector/Beat")
        form.addRow("Sector/Beat:", self.sector_beat)

        self.area_command = QLineEdit()
        self.area_command.setPlaceholderText("Area Command")
        form.addRow("Area Command:", self.area_command)

        self.date_observed = QDateEdit()
        self.date_observed.setCalendarPopup(True)
        self.date_observed.setDate(QDate.currentDate())
        form.addRow("Date Observed:", self.date_observed)

        self.notes = QTextEdit()
        self.notes.setMinimumHeight(80)
        self.notes.setPlaceholderText("Additional notes...")
        form.addRow("Notes:", self.notes)

        layout.addWidget(details_group)

        # Photo upload group
        photo_group = QGroupBox("Graffiti Photo")
        photo_layout = QVBoxLayout(photo_group)
        self.photo = PhotoUploadWidget(label="Graffiti Photo")
        photo_layout.addWidget(self.photo)
        layout.addWidget(photo_group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Buttons outside scroll
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

        # Load existing data for edit mode
        if self.graffiti_data:
            d = self.graffiti_data
            if d.get('tags'):
                self.tags.setText(d['tags'])
            if d.get('monikers'):
                self.monikers.setText(d['monikers'])
            if d.get('sector_beat'):
                self.sector_beat.setText(d['sector_beat'])
            if d.get('area_command'):
                self.area_command.setText(d['area_command'])
            if d.get('date_observed'):
                self.date_observed.setDate(QDate.fromString(d['date_observed'], "yyyy-MM-dd"))
            if d.get('notes'):
                self.notes.setText(d['notes'])
            if d.get('gang_id'):
                for i in range(self.gang.count()):
                    if self.gang.itemData(i) == d['gang_id']:
                        self.gang.setCurrentIndex(i)
                        break

    def save(self):
        # Build location address from components
        loc_parts = []
        street_num = self.loc_street_num.text().strip()
        street_name = self.loc_street_name.text().strip()
        city = self.loc_city.text().strip()
        state = self.loc_state.currentText().strip()
        zipcode = self.loc_zip.text().strip()

        if street_num or street_name:
            loc_parts.append(f"{street_num} {street_name}".strip())
        if city:
            loc_parts.append(city)
        if state or zipcode:
            loc_parts.append(f"{state} {zipcode}".strip())

        loc_text = ", ".join(loc_parts) if loc_parts else ""

        if not loc_text and not self.tags.toPlainText().strip():
            QMessageBox.warning(self, "Error", "Location or tags required.")
            return

        loc_id = self.db.find_or_create_location(loc_text) if loc_text else None

        # Get gang
        gang_name = self.gang.currentText().strip()
        gang_id = None
        if gang_name:
            gang_id = self.gang.currentData() or self.db.find_or_create_gang(gang_name)

        graffiti_kwargs = dict(
            location_id=loc_id,
            location_text=loc_text,
            tags=self.tags.toPlainText().strip(),
            gang_id=gang_id,
            monikers=self.monikers.text().strip(),
            sector_beat=self.sector_beat.text().strip(),
            area_command=self.area_command.text().strip(),
            date_observed=self.date_observed.date().toString("yyyy-MM-dd"),
            notes=self.notes.toPlainText().strip()
        )

        if self.graffiti_data:
            graffiti_id = self.graffiti_data['id']
            self.db.update_graffiti(graffiti_id, **graffiti_kwargs)
        else:
            graffiti_id = self.db.add_graffiti(**graffiti_kwargs)

        # Handle photo (already copied by PhotoUploadWidget)
        if self.photo.photo_path:
            self.db.add_media('graffiti', graffiti_id, self.photo.photo_path, file_type='image')

        self.accept()


# ============ INTEL REPORT DIALOG ============

class IntelReportDialog(QDialog):
    """Intelligence Report intake"""

    def __init__(self, parent, db: TrackerDB, report_data=None):
        super().__init__(parent)
        self.db = db
        self.report_data = report_data
        self.setWindowTitle("New Intel Report" if not report_data else "Edit Intel Report")
        self.setMinimumSize(550, 600)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # Intel Details Group
        details_group = QGroupBox("Intelligence Details")
        form = QFormLayout(details_group)
        form.setSpacing(10)

        self.report_date = QDateEdit()
        self.report_date.setCalendarPopup(True)
        self.report_date.setDate(QDate.currentDate())
        form.addRow("Date:", self.report_date)

        self.source_type = QComboBox()
        self.source_type.addItems(["Social Media", "Patrol", "Concerned Citizen", "Other"])
        form.addRow("Source Type:", self.source_type)

        self.reliability = QComboBox()
        self.reliability.addItems(["High", "Medium", "Low", "Unknown"])
        form.addRow("Reliability:", self.reliability)

        self.details = QTextEdit()
        self.details.setMinimumHeight(120)
        self.details.setPlaceholderText("Intelligence details...")
        form.addRow("Details:", self.details)

        layout.addWidget(details_group)

        # Links section
        links_group = QGroupBox("Link To (Optional)")
        links_layout = QFormLayout(links_group)
        links_layout.setSpacing(10)

        # Subject link with New button
        subj_row = QHBoxLayout()
        self.subject_link = QComboBox()
        self.subject_link.addItem("-- Select Subject --", None)
        for s in self.db.get_all_subjects():
            self.subject_link.addItem(f"{s['first_name']} {s['last_name']}", s['id'])
        subj_row.addWidget(self.subject_link)
        new_subj_btn = QPushButton("+")
        new_subj_btn.setFixedWidth(30)
        new_subj_btn.setStyleSheet("background-color: #c9a040; color: #0a0a0f; font-weight: bold; font-size: 16px;")
        new_subj_btn.setToolTip("Create new subject")
        new_subj_btn.clicked.connect(self.create_new_subject)
        subj_row.addWidget(new_subj_btn)
        links_layout.addRow("Subject:", subj_row)

        # Gang link with New button
        gang_row = QHBoxLayout()
        self.gang_link = QComboBox()
        self.gang_link.addItem("-- Select Gang --", None)
        for g in self.db.get_all_gangs():
            self.gang_link.addItem(g['name'], g['id'])
        gang_row.addWidget(self.gang_link)
        new_gang_btn = QPushButton("+")
        new_gang_btn.setFixedWidth(30)
        new_gang_btn.setStyleSheet("background-color: #c9a040; color: #0a0a0f; font-weight: bold; font-size: 16px;")
        new_gang_btn.setToolTip("Create new gang")
        new_gang_btn.clicked.connect(self.create_new_gang)
        gang_row.addWidget(new_gang_btn)
        links_layout.addRow("Gang:", gang_row)

        # Location link with New button
        loc_row = QHBoxLayout()
        self.location_link = QComboBox()
        self.location_link.addItem("-- Select Location --", None)
        for loc in self.db.get_all_locations():
            self.location_link.addItem(loc['address'][:40], loc['id'])
        loc_row.addWidget(self.location_link)
        new_loc_btn = QPushButton("+")
        new_loc_btn.setFixedWidth(30)
        new_loc_btn.setStyleSheet("background-color: #c9a040; color: #0a0a0f; font-weight: bold; font-size: 16px;")
        new_loc_btn.setToolTip("Create new location")
        new_loc_btn.clicked.connect(self.create_new_location)
        loc_row.addWidget(new_loc_btn)
        links_layout.addRow("Location:", loc_row)

        # Event link with New button
        evt_row = QHBoxLayout()
        self.event_link = QComboBox()
        self.event_link.addItem("-- Select Event --", None)
        for e in self.db.get_all_events():
            self.event_link.addItem(f"{e['event_number']} ({e['event_date']})", e['id'])
        evt_row.addWidget(self.event_link)
        new_evt_btn = QPushButton("+")
        new_evt_btn.setFixedWidth(30)
        new_evt_btn.setStyleSheet("background-color: #c9a040; color: #0a0a0f; font-weight: bold; font-size: 16px;")
        new_evt_btn.setToolTip("Create new event")
        new_evt_btn.clicked.connect(self.create_new_event)
        evt_row.addWidget(new_evt_btn)
        links_layout.addRow("Event:", evt_row)

        layout.addWidget(links_group)

        # Notes Group
        notes_group = QGroupBox("Additional Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes = QTextEdit()
        self.notes.setMinimumHeight(80)
        self.notes.setPlaceholderText("Additional notes...")
        notes_layout.addWidget(self.notes)
        layout.addWidget(notes_group)

        # Photo upload
        photo_group = QGroupBox("Photo/Evidence")
        photo_layout = QVBoxLayout(photo_group)
        self.photo = PhotoUploadWidget(label="intel photo")
        photo_layout.addWidget(self.photo)
        layout.addWidget(photo_group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Buttons outside scroll
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

        # Load existing data for edit mode
        if self.report_data:
            d = self.report_data
            if d.get('report_date'):
                self.report_date.setDate(QDate.fromString(d['report_date'], "yyyy-MM-dd"))
            if d.get('source_type'):
                self.source_type.setCurrentText(d['source_type'])
            if d.get('reliability'):
                self.reliability.setCurrentText(d['reliability'])
            if d.get('details'):
                self.details.setText(d['details'])
            if d.get('notes'):
                self.notes.setText(d['notes'])
            if d.get('subject_id'):
                for i in range(self.subject_link.count()):
                    if self.subject_link.itemData(i) == d['subject_id']:
                        self.subject_link.setCurrentIndex(i)
                        break
            if d.get('gang_id'):
                for i in range(self.gang_link.count()):
                    if self.gang_link.itemData(i) == d['gang_id']:
                        self.gang_link.setCurrentIndex(i)
                        break
            if d.get('location_id'):
                for i in range(self.location_link.count()):
                    if self.location_link.itemData(i) == d['location_id']:
                        self.location_link.setCurrentIndex(i)
                        break
            if d.get('event_id'):
                for i in range(self.event_link.count()):
                    if self.event_link.itemData(i) == d['event_id']:
                        self.event_link.setCurrentIndex(i)
                        break

    def save(self):
        if not self.details.toPlainText().strip():
            QMessageBox.warning(self, "Error", "Details are required.")
            return

        intel_kwargs = dict(
            report_date=self.report_date.date().toString("yyyy-MM-dd"),
            reliability=self.reliability.currentText(),
            subject_id=self.subject_link.currentData(),
            gang_id=self.gang_link.currentData(),
            location_id=self.location_link.currentData(),
            event_id=self.event_link.currentData(),
            notes=self.notes.toPlainText().strip()
        )

        if self.report_data:
            report_id = self.report_data['id']
            self.db.update_intel_report(report_id,
                                         source_type=self.source_type.currentText(),
                                         details=self.details.toPlainText().strip(),
                                         **intel_kwargs)
        else:
            report_id = self.db.add_intel_report(
                self.source_type.currentText(),
                self.details.toPlainText().strip(),
                **intel_kwargs
            )

        # Register photo in media table (already copied by PhotoUploadWidget)
        if self.photo.photo_path and report_id:
            self.db.add_media('intel', report_id, self.photo.photo_path, file_type='image')

        self.accept()

    def create_new_subject(self):
        """Create new subject and add to dropdown"""
        dialog = SubjectIntakeDialog(self, self.db)
        if dialog.exec():
            # Refresh dropdown and select new subject
            self.subject_link.clear()
            self.subject_link.addItem("-- Select Subject --", None)
            for s in self.db.get_all_subjects():
                self.subject_link.addItem(f"{s['first_name']} {s['last_name']}", s['id'])
            # Select the last one (just created)
            self.subject_link.setCurrentIndex(self.subject_link.count() - 1)

    def create_new_gang(self):
        """Create new gang and add to dropdown"""
        dialog = GangDialog(self, self.db)
        if dialog.exec():
            data = dialog.get_data()
            name = data.pop('name')
            photo_path = data.pop('photo', None)
            gang_id = self.db.add_gang(name, **data)
            if photo_path and gang_id:
                self.db.add_media('gang', gang_id, photo_path, file_type='image')
            # Refresh dropdown
            self.gang_link.clear()
            self.gang_link.addItem("-- Select Gang --", None)
            for g in self.db.get_all_gangs():
                self.gang_link.addItem(g['name'], g['id'])
            # Select the new gang
            for i in range(self.gang_link.count()):
                if self.gang_link.itemData(i) == gang_id:
                    self.gang_link.setCurrentIndex(i)
                    break

    def create_new_location(self):
        """Create new location via simple input"""
        address, ok = QInputDialog.getText(self, "New Location", "Enter address:")
        if ok and address.strip():
            loc_id = self.db.find_or_create_location(address.strip())
            # Refresh dropdown
            self.location_link.clear()
            self.location_link.addItem("-- Select Location --", None)
            for loc in self.db.get_all_locations():
                self.location_link.addItem(loc['address'][:40], loc['id'])
            # Select the new location
            for i in range(self.location_link.count()):
                if self.location_link.itemData(i) == loc_id:
                    self.location_link.setCurrentIndex(i)
                    break

    def create_new_event(self):
        """Create new event and add to dropdown"""
        dialog = EventIntakeDialog(self, self.db)
        if dialog.exec():
            # Refresh dropdown
            self.event_link.clear()
            self.event_link.addItem("-- Select Event --", None)
            for e in self.db.get_all_events():
                self.event_link.addItem(f"{e['event_number']} ({e['event_date']})", e['id'])
            # Select the last one (just created)
            self.event_link.setCurrentIndex(self.event_link.count() - 1)


# ============ VEHICLE DIALOG ============

class VehicleDialog(QDialog):
    """Vehicle intake dialog"""

    def __init__(self, parent, db: TrackerDB, vehicle_data=None):
        super().__init__(parent)
        self.db = db
        self.vehicle_data = vehicle_data
        self.existing_match_id = None  # Will store ID if duplicate found
        self.setWindowTitle("New Vehicle" if not vehicle_data else "Edit Vehicle")
        self.setMinimumSize(550, 600)
        self.setup_ui()
        if vehicle_data:
            self.load_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # Duplicate warning label (hidden by default)
        self.duplicate_warning = QLabel("⚠️ Already Exists: Will Link To Existing. Not Duplicate.")
        self.duplicate_warning.setStyleSheet("color: #ff6b6b; font-weight: bold; padding: 8px; background: #3a2a2a; border-radius: 4px;")
        self.duplicate_warning.setVisible(False)
        layout.addWidget(self.duplicate_warning)

        # Vehicle Details Group
        details_group = QGroupBox("Vehicle Details")
        form = QFormLayout(details_group)
        form.setSpacing(10)

        self.plate = QLineEdit()
        self.plate.setPlaceholderText("License plate number")
        self.plate.textChanged.connect(self.check_duplicate)
        form.addRow("Plate:", self.plate)

        self.state = QComboBox()
        self.state.setEditable(True)
        states = US_STATES
        self.state.addItems(states)
        form.addRow("State:", self.state)

        self.make = QLineEdit()
        self.make.setPlaceholderText("e.g., Toyota, Ford, Honda")
        form.addRow("Make:", self.make)

        self.model = QLineEdit()
        self.model.setPlaceholderText("e.g., Camry, F-150, Civic")
        form.addRow("Model:", self.model)

        self.year = QSpinBox()
        self.year.setRange(1900, 2030)
        self.year.setValue(2020)
        form.addRow("Year:", self.year)

        self.color = QLineEdit()
        self.color.setPlaceholderText("Primary color")
        form.addRow("Color:", self.color)

        self.vin = QLineEdit()
        self.vin.setPlaceholderText("Vehicle Identification Number")
        self.vin.textChanged.connect(self.check_duplicate)
        form.addRow("VIN:", self.vin)

        layout.addWidget(details_group)

        # Link to subjects
        subj_group = QGroupBox("Associated Subjects")
        subj_layout = QVBoxLayout(subj_group)

        # Subject selector row
        subj_row = QHBoxLayout()
        self.subject_combo = QComboBox()
        self.subject_combo.addItem("-- Select Subject --", None)
        for s in self.db.get_all_subjects():
            self.subject_combo.addItem(f"{s['first_name']} {s['last_name']}", s['id'])
        subj_row.addWidget(self.subject_combo)

        add_subj_btn = QPushButton("Add")
        add_subj_btn.setFixedWidth(60)
        add_subj_btn.clicked.connect(self._add_selected_subject)
        subj_row.addWidget(add_subj_btn)

        new_subj_btn = QPushButton("+New")
        new_subj_btn.setFixedWidth(60)
        new_subj_btn.setStyleSheet("background-color: #5a8a6a; font-weight: bold; font-size: 14px;")
        new_subj_btn.clicked.connect(self._create_new_subject)
        subj_row.addWidget(new_subj_btn)
        subj_layout.addLayout(subj_row)

        # List of added subjects
        self.selected_subjects = []
        self.subjects_list = QListWidget()
        self.subjects_list.setMinimumHeight(80)
        self.subjects_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.subjects_list.customContextMenuRequested.connect(self._remove_subject_menu)
        subj_layout.addWidget(self.subjects_list)

        remove_hint = QLabel("Right-click to remove subjects")
        remove_hint.setStyleSheet("color: #888; font-size: 10px;")
        subj_layout.addWidget(remove_hint)
        layout.addWidget(subj_group)

        # Link to event
        event_group = QGroupBox("Link to Event")
        event_layout = QVBoxLayout(event_group)
        self.event_link = QComboBox()
        self.event_link.addItem("-- None --", None)
        for e in self.db.get_all_events():
            self.event_link.addItem(f"{e['event_number']} ({e['event_date']})", e['id'])
        event_layout.addWidget(self.event_link)
        layout.addWidget(event_group)

        # Notes
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes = QTextEdit()
        self.notes.setMinimumHeight(80)
        self.notes.setPlaceholderText("Additional notes...")
        notes_layout.addWidget(self.notes)
        layout.addWidget(notes_group)

        # Photo upload
        photo_group = QGroupBox("Photo")
        photo_layout = QVBoxLayout(photo_group)
        self.photo = PhotoUploadWidget(label="vehicle photo")
        photo_layout.addWidget(self.photo)

        # Photo gallery container (shown when editing with existing photos)
        self.gallery_container = QWidget()
        self.gallery_layout = QVBoxLayout(self.gallery_container)
        self.gallery_layout.setContentsMargins(0, 5, 0, 0)
        self.gallery_container.hide()
        photo_layout.addWidget(self.gallery_container)

        layout.addWidget(photo_group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Buttons outside scroll
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

    def load_data(self):
        """Load existing vehicle data for editing"""
        if self.vehicle_data:
            self.plate.setText(self.vehicle_data.get('plate', ''))
            self.state.setCurrentText(self.vehicle_data.get('state', ''))
            self.make.setText(self.vehicle_data.get('make', ''))
            self.model.setText(self.vehicle_data.get('model', ''))
            if self.vehicle_data.get('year'):
                self.year.setValue(int(self.vehicle_data['year']))
            self.color.setText(self.vehicle_data.get('color', ''))
            self.vin.setText(self.vehicle_data.get('vin', ''))
            self.notes.setText(self.vehicle_data.get('notes', ''))
            if self.vehicle_data.get('photo'):
                self.photo.set_photo(self.vehicle_data['photo'])
            # Show photo gallery if there are existing photos
            media_list = self.db.get_entity_media('vehicle', self.vehicle_data['id'])
            images = [m for m in media_list if m.get('file_path', '').lower().endswith(
                ('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]
            if images:
                gallery = PhotoGalleryWidget(self.db, 'vehicle', self.vehicle_data['id'], self)
                self.gallery_layout.addWidget(gallery)
                self.gallery_container.show()

    def _add_selected_subject(self):
        """Add the currently selected subject from dropdown to the list"""
        subject_id = self.subject_combo.currentData()
        if subject_id is None:
            return
        # Check if already added
        if subject_id in self.selected_subjects:
            QMessageBox.information(self, "Info", "Subject already added.")
            return
        subject_name = self.subject_combo.currentText()
        self.selected_subjects.append(subject_id)
        item = QListWidgetItem(subject_name)
        item.setData(Qt.ItemDataRole.UserRole, subject_id)
        self.subjects_list.addItem(item)
        self.subject_combo.setCurrentIndex(0)

    def _create_new_subject(self):
        """Open dialog to create a new subject"""
        dlg = SubjectIntakeDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Refresh the dropdown
            self.subject_combo.clear()
            self.subject_combo.addItem("-- Select Subject --", None)
            for s in self.db.get_all_subjects():
                self.subject_combo.addItem(f"{s['first_name']} {s['last_name']}", s['id'])

    def _remove_subject_menu(self, pos):
        """Show context menu to remove subject"""
        item = self.subjects_list.itemAt(pos)
        if item:
            menu = QMenu(self)
            remove_action = menu.addAction("Remove")
            action = menu.exec(self.subjects_list.mapToGlobal(pos))
            if action == remove_action:
                subject_id = item.data(Qt.ItemDataRole.UserRole)
                self.selected_subjects.remove(subject_id)
                self.subjects_list.takeItem(self.subjects_list.row(item))

    def check_duplicate(self):
        """Check if vehicle already exists and show warning"""
        if self.vehicle_data:  # Skip check when editing
            return

        plate = self.plate.text().strip()
        vin = self.vin.text().strip()

        if not plate and not vin:
            self.existing_match_id = None
            self.duplicate_warning.setVisible(False)
            self.plate.setStyleSheet("")
            self.vin.setStyleSheet("")
            return

        existing_id = self.db.find_existing_vehicle(plate=plate, vin=vin)

        if existing_id:
            self.existing_match_id = existing_id
            existing = self.db.get_vehicle(existing_id)
            desc = f"{existing.get('plate', '')} - {existing.get('make', '')} {existing.get('model', '')}".strip(' -')
            self.duplicate_warning.setText(f"⚠️ Already Exists: {desc} - Will Link To Existing")
            self.duplicate_warning.setVisible(True)
            if plate:
                self.plate.setStyleSheet("border: 2px solid #ff6b6b;")
            if vin:
                self.vin.setStyleSheet("border: 2px solid #ff6b6b;")
        else:
            self.existing_match_id = None
            self.duplicate_warning.setVisible(False)
            self.plate.setStyleSheet("")
            self.vin.setStyleSheet("")

    def save(self):
        if not self.plate.text().strip() and not self.vin.text().strip():
            QMessageBox.warning(self, "Error", "Plate or VIN is required.")
            return

        if self.vehicle_data:
            # Update existing vehicle
            vehicle_id = self.vehicle_data['id']
            cursor = self.db.conn.cursor()
            cursor.execute("""
                UPDATE vehicles SET plate=?, state=?, make=?, model=?, year=?, color=?, vin=?, notes=?
                WHERE id=?
            """, (
                self.plate.text().strip(),
                self.state.currentText(),
                self.make.text().strip(),
                self.model.text().strip(),
                self.year.value() if self.year.value() > 1900 else None,
                self.color.text().strip(),
                self.vin.text().strip(),
                self.notes.toPlainText().strip(),
                vehicle_id
            ))
            self.db.conn.commit()
            # Save photo to media table if provided
            if self.photo.photo_path:
                self.db.add_media('vehicle', vehicle_id, self.photo.photo_path, file_type='image')
        elif self.existing_match_id:
            # Duplicate found - show merge review dialog
            vehicle_id = self.existing_match_id
            existing = self.db.get_vehicle(vehicle_id)

            # Build new data from form
            new_data = {
                'plate': self.plate.text().strip(),
                'state': self.state.currentText(),
                'make': self.make.text().strip(),
                'model': self.model.text().strip(),
                'year': str(self.year.value()) if self.year.value() > 1900 else '',
                'color': self.color.text().strip(),
                'vin': self.vin.text().strip(),
                'notes': self.notes.toPlainText().strip()
            }

            # Field labels for display
            field_labels = {
                'plate': 'License Plate',
                'state': 'State',
                'make': 'Make',
                'model': 'Model',
                'year': 'Year',
                'color': 'Color',
                'vin': 'VIN',
                'notes': 'Notes'
            }

            # Show merge review dialog
            merge_dialog = MergeReviewDialog(self, 'vehicle', existing, new_data, field_labels)
            if merge_dialog.exec() != QDialog.DialogCode.Accepted:
                return  # User cancelled

            # Apply merged data
            merged = merge_dialog.get_merged_data()
            cursor = self.db.conn.cursor()
            cursor.execute("""
                UPDATE vehicles SET plate=?, state=?, make=?, model=?, year=?, color=?, vin=?, notes=?
                WHERE id=?
            """, (
                merged.get('plate', ''),
                merged.get('state', ''),
                merged.get('make', ''),
                merged.get('model', ''),
                merged.get('year') if merged.get('year') else None,
                merged.get('color', ''),
                merged.get('vin', ''),
                merged.get('notes', ''),
                vehicle_id
            ))
            self.db.conn.commit()

            # Link to subjects
            for subject_id in self.selected_subjects:
                if not self.db.is_subject_linked_to_vehicle(subject_id, vehicle_id):
                    self.db.link_subject_to_vehicle(subject_id, vehicle_id)

            # Link to event
            event_id = self.event_link.currentData()
            if event_id and not self.db.is_event_linked_to_vehicle(event_id, vehicle_id):
                self.db.link_event_to_vehicle(event_id, vehicle_id)

            # Redirect to existing record
            self.redirect_to = ('vehicle', vehicle_id)
            self.reject()
            return
        else:
            # No existing - create new vehicle
            plate = self.plate.text().strip()
            vin = self.vin.text().strip()
            vehicle_id = self.db.add_vehicle(
                plate=plate,
                state=self.state.currentText(),
                make=self.make.text().strip(),
                model=self.model.text().strip(),
                year=self.year.value() if self.year.value() > 1900 else None,
                color=self.color.text().strip(),
                vin=vin,
                notes=self.notes.toPlainText().strip(),
                photo=self.photo.photo_path
            )

            # Link to subjects
            for subject_id in self.selected_subjects:
                self.db.link_subject_to_vehicle(subject_id, vehicle_id)

            # Link to event
            event_id = self.event_link.currentData()
            if event_id:
                if not self.db.is_event_linked_to_vehicle(event_id, vehicle_id):
                    self.db.link_event_to_vehicle(event_id, vehicle_id)

        # Register photo in media table (already copied by PhotoUploadWidget)
        if self.photo.photo_path and vehicle_id:
            self.db.add_media('vehicle', vehicle_id, self.photo.photo_path, file_type='image')

        self.accept()


# ============ LOCATION DIALOG ============

class LocationDialog(QDialog):
    """Location intake dialog"""

    def __init__(self, parent, db: TrackerDB, location_data=None):
        super().__init__(parent)
        self.db = db
        self.location_data = location_data
        self.existing_match_id = None  # Will store ID if duplicate found
        self.setWindowTitle("New Location" if not location_data else "Edit Location")
        self.setMinimumSize(550, 600)
        self.setup_ui()
        if location_data:
            self.load_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # Duplicate warning label (hidden by default)
        self.duplicate_warning = QLabel("⚠️ Already Exists: Will Link To Existing. Not Duplicate.")
        self.duplicate_warning.setStyleSheet("color: #ff6b6b; font-weight: bold; padding: 8px; background: #3a2a2a; border-radius: 4px;")
        self.duplicate_warning.setVisible(False)
        layout.addWidget(self.duplicate_warning)

        # Location Details Group
        details_group = QGroupBox("Location Details")
        form = QFormLayout(details_group)
        form.setSpacing(10)

        # Street Number and Name on same row
        street_row = QHBoxLayout()
        self.street_number = QLineEdit()
        self.street_number.setPlaceholderText("1234")
        self.street_number.setFixedWidth(80)
        self.street_number.textChanged.connect(self.check_duplicate)
        street_row.addWidget(self.street_number)
        self.street_name = QLineEdit()
        self.street_name.setPlaceholderText("Main St")
        self.street_name.textChanged.connect(self.check_duplicate)
        street_row.addWidget(self.street_name)
        form.addRow("Address:", street_row)

        # City, State, Zip on same row
        city_row = QHBoxLayout()
        self.city = QLineEdit()
        self.city.setPlaceholderText("City")
        city_row.addWidget(self.city)
        self.state = QComboBox()
        self.state.setEditable(True)
        self.state.setFixedWidth(70)
        states = US_STATES
        self.state.addItems(states)
        city_row.addWidget(self.state)
        self.zipcode = QLineEdit()
        self.zipcode.setPlaceholderText("Zip")
        self.zipcode.setFixedWidth(80)
        city_row.addWidget(self.zipcode)
        form.addRow("City/State/Zip:", city_row)

        self.loc_type = QComboBox()
        self.loc_type.setEditable(True)
        self.loc_type.addItems(["", "Residence", "Business", "Park", "School", "Hangout", "Other"])
        form.addRow("Type:", self.loc_type)

        self.description = QLineEdit()
        self.description.setPlaceholderText("Brief description")
        form.addRow("Description:", self.description)

        layout.addWidget(details_group)

        # Link to subjects
        subj_group = QGroupBox("Associated Subjects")
        subj_layout = QVBoxLayout(subj_group)

        # Subject selector row
        subj_row = QHBoxLayout()
        self.subject_combo = QComboBox()
        self.subject_combo.addItem("-- Select Subject --", None)
        for s in self.db.get_all_subjects():
            self.subject_combo.addItem(f"{s['first_name']} {s['last_name']}", s['id'])
        subj_row.addWidget(self.subject_combo)

        add_subj_btn = QPushButton("Add")
        add_subj_btn.setFixedWidth(60)
        add_subj_btn.clicked.connect(self._add_selected_subject)
        subj_row.addWidget(add_subj_btn)

        new_subj_btn = QPushButton("+New")
        new_subj_btn.setFixedWidth(60)
        new_subj_btn.setStyleSheet("background-color: #5a8a6a; font-weight: bold; font-size: 14px;")
        new_subj_btn.clicked.connect(self._create_new_subject)
        subj_row.addWidget(new_subj_btn)
        subj_layout.addLayout(subj_row)

        # List of added subjects
        self.selected_subjects = []
        self.subjects_list = QListWidget()
        self.subjects_list.setMinimumHeight(80)
        self.subjects_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.subjects_list.customContextMenuRequested.connect(self._remove_subject_menu)
        subj_layout.addWidget(self.subjects_list)

        remove_hint = QLabel("Right-click to remove subjects")
        remove_hint.setStyleSheet("color: #888; font-size: 10px;")
        subj_layout.addWidget(remove_hint)
        layout.addWidget(subj_group)

        # Link to gang
        gang_group = QGroupBox("Associated Gang")
        gang_layout = QVBoxLayout(gang_group)
        self.gang_link = QComboBox()
        self.gang_link.addItem("-- None --", None)
        for g in self.db.get_all_gangs():
            self.gang_link.addItem(g['name'], g['id'])
        gang_layout.addWidget(self.gang_link)
        layout.addWidget(gang_group)

        # Notes
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes = QTextEdit()
        self.notes.setMinimumHeight(80)
        self.notes.setPlaceholderText("Additional notes...")
        notes_layout.addWidget(self.notes)
        layout.addWidget(notes_group)

        # Photo upload
        photo_group = QGroupBox("Photo")
        photo_layout = QVBoxLayout(photo_group)
        self.photo = PhotoUploadWidget(label="location photo")
        photo_layout.addWidget(self.photo)

        # Photo gallery container (shown when editing with existing photos)
        self.gallery_container = QWidget()
        self.gallery_layout = QVBoxLayout(self.gallery_container)
        self.gallery_layout.setContentsMargins(0, 5, 0, 0)
        self.gallery_container.hide()
        photo_layout.addWidget(self.gallery_container)

        layout.addWidget(photo_group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Buttons outside scroll
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

    def load_data(self):
        """Load existing location data for editing"""
        if self.location_data:
            # Try to parse the address into components
            address = self.location_data.get('address', '')
            if address:
                # Try to parse "1234 Main St, City, ST 12345" format
                parts = address.split(',')
                if len(parts) >= 1:
                    # First part: street number and name
                    street_parts = parts[0].strip().split(' ', 1)
                    if len(street_parts) >= 1:
                        self.street_number.setText(street_parts[0])
                    if len(street_parts) >= 2:
                        self.street_name.setText(street_parts[1])
                if len(parts) >= 2:
                    # Second part: city
                    self.city.setText(parts[1].strip())
                if len(parts) >= 3:
                    # Third part: state and zip
                    state_zip = parts[2].strip().split(' ')
                    if len(state_zip) >= 1:
                        self.state.setCurrentText(state_zip[0])
                    if len(state_zip) >= 2:
                        self.zipcode.setText(state_zip[1])
            self.loc_type.setCurrentText(self.location_data.get('type', ''))
            self.description.setText(self.location_data.get('description', ''))
            self.notes.setText(self.location_data.get('notes', ''))
            if self.location_data.get('photo'):
                self.photo.set_photo(self.location_data['photo'])
            # Show photo gallery if there are existing photos
            media_list = self.db.get_entity_media('location', self.location_data['id'])
            images = [m for m in media_list if m.get('file_path', '').lower().endswith(
                ('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]
            if images:
                gallery = PhotoGalleryWidget(self.db, 'location', self.location_data['id'], self)
                self.gallery_layout.addWidget(gallery)
                self.gallery_container.show()

    def _add_selected_subject(self):
        """Add the currently selected subject from dropdown to the list"""
        subject_id = self.subject_combo.currentData()
        if subject_id is None:
            return
        # Check if already added
        if subject_id in self.selected_subjects:
            QMessageBox.information(self, "Info", "Subject already added.")
            return
        subject_name = self.subject_combo.currentText()
        self.selected_subjects.append(subject_id)
        item = QListWidgetItem(subject_name)
        item.setData(Qt.ItemDataRole.UserRole, subject_id)
        self.subjects_list.addItem(item)
        self.subject_combo.setCurrentIndex(0)

    def _create_new_subject(self):
        """Open dialog to create a new subject"""
        dlg = SubjectIntakeDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Refresh the dropdown
            self.subject_combo.clear()
            self.subject_combo.addItem("-- Select Subject --", None)
            for s in self.db.get_all_subjects():
                self.subject_combo.addItem(f"{s['first_name']} {s['last_name']}", s['id'])

    def _remove_subject_menu(self, pos):
        """Show context menu to remove subject"""
        item = self.subjects_list.itemAt(pos)
        if item:
            menu = QMenu(self)
            remove_action = menu.addAction("Remove")
            action = menu.exec(self.subjects_list.mapToGlobal(pos))
            if action == remove_action:
                subject_id = item.data(Qt.ItemDataRole.UserRole)
                self.selected_subjects.remove(subject_id)
                self.subjects_list.takeItem(self.subjects_list.row(item))

    def check_duplicate(self):
        """Check if location already exists and show warning"""
        if self.location_data:  # Skip check when editing
            return

        street_num = self.street_number.text().strip()
        street = self.street_name.text().strip()

        if not street_num and not street:
            self.existing_match_id = None
            self.duplicate_warning.setVisible(False)
            self.street_number.setStyleSheet("")
            self.street_name.setStyleSheet("")
            return

        # Build partial address for checking
        address = f"{street_num} {street}".strip()
        existing_id = self.db.find_existing_location(address)

        if existing_id:
            self.existing_match_id = existing_id
            existing = self.db.get_location(existing_id)
            self.duplicate_warning.setText(f"⚠️ Already Exists: {existing.get('address', address)} - Will Link To Existing")
            self.duplicate_warning.setVisible(True)
            self.street_number.setStyleSheet("border: 2px solid #ff6b6b;")
            self.street_name.setStyleSheet("border: 2px solid #ff6b6b;")
        else:
            self.existing_match_id = None
            self.duplicate_warning.setVisible(False)
            self.street_number.setStyleSheet("")
            self.street_name.setStyleSheet("")

    def save(self):
        # Build full address from components
        street_num = self.street_number.text().strip()
        street = self.street_name.text().strip()
        city = self.city.text().strip()
        state = self.state.currentText().strip()
        zipcode = self.zipcode.text().strip()

        if not street_num and not street:
            QMessageBox.warning(self, "Error", "Street address is required.")
            return

        # Build address string: "1234 Main St, City, ST 12345"
        address_parts = []
        if street_num or street:
            address_parts.append(f"{street_num} {street}".strip())
        if city:
            address_parts.append(city)
        if state or zipcode:
            address_parts.append(f"{state} {zipcode}".strip())

        full_address = ", ".join(address_parts)

        if self.location_data:
            # Update existing location
            location_id = self.location_data['id']
            cursor = self.db.conn.cursor()
            cursor.execute("""
                UPDATE locations SET address=?, type=?, description=?, notes=?
                WHERE id=?
            """, (
                full_address,
                self.loc_type.currentText(),
                self.description.text().strip(),
                self.notes.toPlainText().strip(),
                location_id
            ))
            self.db.conn.commit()
        elif self.existing_match_id:
            # Duplicate found - show merge review dialog
            location_id = self.existing_match_id
            existing = self.db.get_location(location_id)

            # Build new data from form
            new_data = {
                'address': full_address,
                'type': self.loc_type.currentText(),
                'description': self.description.text().strip(),
                'notes': self.notes.toPlainText().strip()
            }

            # Field labels for display
            field_labels = {
                'address': 'Address',
                'type': 'Location Type',
                'description': 'Description',
                'notes': 'Notes'
            }

            # Show merge review dialog
            merge_dialog = MergeReviewDialog(self, 'location', existing, new_data, field_labels)
            if merge_dialog.exec() != QDialog.DialogCode.Accepted:
                return  # User cancelled

            # Apply merged data
            merged = merge_dialog.get_merged_data()
            cursor = self.db.conn.cursor()
            cursor.execute("""
                UPDATE locations SET address=?, type=?, description=?, notes=?
                WHERE id=?
            """, (
                merged.get('address', ''),
                merged.get('type', ''),
                merged.get('description', ''),
                merged.get('notes', ''),
                location_id
            ))
            self.db.conn.commit()

            # Link to subjects
            for subject_id in self.selected_subjects:
                if not self.db.is_subject_linked_to_location(subject_id, location_id):
                    self.db.link_subject_to_location(subject_id, location_id)

            # Link to gang
            gang_id = self.gang_link.currentData()
            if gang_id and not self.db.is_gang_linked_to_location(gang_id, location_id):
                self.db.link_gang_to_location(gang_id, location_id)

            # Redirect to existing record
            self.redirect_to = ('location', location_id)
            self.reject()
            return
        else:
            # No existing - create new location
            location_id = self.db.add_location(
                full_address,
                type=self.loc_type.currentText(),
                description=self.description.text().strip(),
                notes=self.notes.toPlainText().strip()
            )

            # Link to subjects
            for subject_id in self.selected_subjects:
                self.db.link_subject_to_location(subject_id, location_id)

            # Link to gang
            gang_id = self.gang_link.currentData()
            if gang_id:
                self.db.link_gang_to_location(gang_id, location_id)

        # Register photo in media table (already copied by PhotoUploadWidget)
        if self.photo.photo_path and location_id:
            self.db.add_media('location', location_id, self.photo.photo_path, file_type='image')

        self.accept()


# ============ WEAPON DIALOG ============

class WeaponDialog(QDialog):
    """Weapon intake dialog"""

    def __init__(self, parent, db: TrackerDB, weapon_data=None):
        super().__init__(parent)
        self.db = db
        self.weapon_data = weapon_data
        self.setWindowTitle("New Weapon" if not weapon_data else "Edit Weapon")
        self.setMinimumSize(550, 600)
        self.setup_ui()
        if weapon_data:
            self.load_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # Weapon Details Group
        details_group = QGroupBox("Weapon Details")
        form = QFormLayout(details_group)
        form.setSpacing(10)

        self.weapon_type = QComboBox()
        self.weapon_type.setEditable(True)
        self.weapon_type.addItems(["", "Handgun", "Rifle", "Shotgun", "Knife", "Other"])
        form.addRow("Type:", self.weapon_type)

        self.make = QLineEdit()
        self.make.setPlaceholderText("Manufacturer (e.g., Glock, Smith & Wesson)")
        form.addRow("Make:", self.make)

        self.model = QLineEdit()
        self.model.setPlaceholderText("Model (e.g., 19, M&P Shield)")
        form.addRow("Model:", self.model)

        self.caliber = QLineEdit()
        self.caliber.setPlaceholderText("Caliber/Gauge (e.g., 9mm, .45 ACP, 12 gauge)")
        form.addRow("Caliber:", self.caliber)

        self.serial_number = QLineEdit()
        self.serial_number.setPlaceholderText("Serial number")
        form.addRow("Serial #:", self.serial_number)

        layout.addWidget(details_group)

        # Link to subjects
        subj_group = QGroupBox("Associated Subjects")
        subj_layout = QVBoxLayout(subj_group)

        # Subject selector row
        subj_row = QHBoxLayout()
        self.subject_combo = QComboBox()
        self.subject_combo.addItem("-- Select Subject --", None)
        for s in self.db.get_all_subjects():
            self.subject_combo.addItem(f"{s['first_name']} {s['last_name']}", s['id'])
        subj_row.addWidget(self.subject_combo)

        add_subj_btn = QPushButton("Add")
        add_subj_btn.setFixedWidth(60)
        add_subj_btn.clicked.connect(self._add_selected_subject)
        subj_row.addWidget(add_subj_btn)

        new_subj_btn = QPushButton("+New")
        new_subj_btn.setFixedWidth(60)
        new_subj_btn.setStyleSheet("background-color: #5a8a6a; font-weight: bold; font-size: 14px;")
        new_subj_btn.clicked.connect(self._create_new_subject)
        subj_row.addWidget(new_subj_btn)
        subj_layout.addLayout(subj_row)

        # List of added subjects
        self.selected_subjects = []
        self.subjects_list = QListWidget()
        self.subjects_list.setMinimumHeight(80)
        self.subjects_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.subjects_list.customContextMenuRequested.connect(self._remove_subject_menu)
        subj_layout.addWidget(self.subjects_list)

        remove_hint = QLabel("Right-click to remove subjects")
        remove_hint.setStyleSheet("color: #888; font-size: 10px;")
        subj_layout.addWidget(remove_hint)
        layout.addWidget(subj_group)

        # Link to event
        event_group = QGroupBox("Link to Event")
        event_layout = QVBoxLayout(event_group)
        self.event_link = QComboBox()
        self.event_link.addItem("-- None --", None)
        for e in self.db.get_all_events():
            self.event_link.addItem(f"{e['event_number']} ({e['event_date']})", e['id'])
        event_layout.addWidget(self.event_link)
        layout.addWidget(event_group)

        # Notes
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes = QTextEdit()
        self.notes.setMinimumHeight(80)
        self.notes.setPlaceholderText("Additional notes...")
        notes_layout.addWidget(self.notes)
        layout.addWidget(notes_group)

        # Photo upload
        photo_group = QGroupBox("Photo")
        photo_layout = QVBoxLayout(photo_group)
        self.photo = PhotoUploadWidget(label="weapon photo")
        photo_layout.addWidget(self.photo)

        # Photo gallery container (shown when editing with existing photos)
        self.gallery_container = QWidget()
        self.gallery_layout = QVBoxLayout(self.gallery_container)
        self.gallery_layout.setContentsMargins(0, 5, 0, 0)
        self.gallery_container.hide()
        photo_layout.addWidget(self.gallery_container)

        layout.addWidget(photo_group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Buttons outside scroll
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

    def load_data(self):
        """Load existing weapon data for editing"""
        if self.weapon_data:
            self.weapon_type.setCurrentText(self.weapon_data.get('weapon_type', ''))
            self.make.setText(self.weapon_data.get('make', ''))
            self.model.setText(self.weapon_data.get('model', ''))
            self.caliber.setText(self.weapon_data.get('caliber', ''))
            self.serial_number.setText(self.weapon_data.get('serial_number', ''))
            self.notes.setText(self.weapon_data.get('notes', ''))
            if self.weapon_data.get('photo'):
                self.photo.set_photo(self.weapon_data['photo'])
            # Show photo gallery if there are existing photos
            media_list = self.db.get_entity_media('weapon', self.weapon_data['id'])
            images = [m for m in media_list if m.get('file_path', '').lower().endswith(
                ('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]
            if images:
                gallery = PhotoGalleryWidget(self.db, 'weapon', self.weapon_data['id'], self)
                self.gallery_layout.addWidget(gallery)
                self.gallery_container.show()

    def _add_selected_subject(self):
        """Add the currently selected subject from dropdown to the list"""
        subject_id = self.subject_combo.currentData()
        if subject_id is None:
            return
        # Check if already added
        if subject_id in self.selected_subjects:
            QMessageBox.information(self, "Info", "Subject already added.")
            return
        subject_name = self.subject_combo.currentText()
        self.selected_subjects.append(subject_id)
        item = QListWidgetItem(subject_name)
        item.setData(Qt.ItemDataRole.UserRole, subject_id)
        self.subjects_list.addItem(item)
        self.subject_combo.setCurrentIndex(0)

    def _create_new_subject(self):
        """Open dialog to create a new subject"""
        dlg = SubjectIntakeDialog(self, self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Refresh the dropdown
            self.subject_combo.clear()
            self.subject_combo.addItem("-- Select Subject --", None)
            for s in self.db.get_all_subjects():
                self.subject_combo.addItem(f"{s['first_name']} {s['last_name']}", s['id'])

    def _remove_subject_menu(self, pos):
        """Show context menu to remove subject"""
        item = self.subjects_list.itemAt(pos)
        if item:
            menu = QMenu(self)
            remove_action = menu.addAction("Remove")
            action = menu.exec(self.subjects_list.mapToGlobal(pos))
            if action == remove_action:
                subject_id = item.data(Qt.ItemDataRole.UserRole)
                self.selected_subjects.remove(subject_id)
                self.subjects_list.takeItem(self.subjects_list.row(item))

    def save(self):
        if not self.weapon_type.currentText().strip():
            QMessageBox.warning(self, "Error", "Weapon type is required.")
            return

        if self.weapon_data:
            # Update existing weapon
            weapon_id = self.weapon_data['id']
            cursor = self.db.conn.cursor()
            cursor.execute("""
                UPDATE weapons SET weapon_type=?, make=?, model=?, caliber=?, serial_number=?, notes=?, photo=?
                WHERE id=?
            """, (
                self.weapon_type.currentText(),
                self.make.text().strip(),
                self.model.text().strip(),
                self.caliber.text().strip(),
                self.serial_number.text().strip(),
                self.notes.toPlainText().strip(),
                self.photo.photo_path,
                weapon_id
            ))
            self.db.conn.commit()
        else:
            # Create new weapon
            weapon_id = self.db.add_weapon(
                weapon_type=self.weapon_type.currentText(),
                make=self.make.text().strip(),
                model=self.model.text().strip(),
                caliber=self.caliber.text().strip(),
                serial_number=self.serial_number.text().strip(),
                notes=self.notes.toPlainText().strip(),
                photo=self.photo.photo_path
            )

            # Link to subjects (only for new weapons)
            for subject_id in self.selected_subjects:
                self.db.link_subject_to_weapon(subject_id, weapon_id)

            # Link to event (only for new weapons)
            event_id = self.event_link.currentData()
            if event_id:
                self.db.link_event_to_weapon(event_id, weapon_id)

        # Register photo in media table (already copied by PhotoUploadWidget)
        if self.photo.photo_path and weapon_id:
            self.db.add_media('weapon', weapon_id, self.photo.photo_path, file_type='image')

        self.accept()


# ============ CHECKLIST EDITOR DIALOG ============

class ChecklistEditorDialog(QDialog):
    """Dialog to edit checklist items"""

    def __init__(self, parent, db: TrackerDB):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Edit Checklist")
        self.setMinimumSize(500, 400)
        self.setup_ui()
        self.load_items()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.item_list = QListWidget()
        self.item_list.itemClicked.connect(self.on_item_selected)
        layout.addWidget(self.item_list)

        # Edit fields
        edit_group = QGroupBox("Edit Item")
        edit_layout = QFormLayout(edit_group)

        self.edit_name = QLineEdit()
        edit_layout.addRow("Name:", self.edit_name)

        self.edit_category = QComboBox()
        self.edit_category.setEditable(True)
        edit_layout.addRow("Category:", self.edit_category)

        self.edit_url = QLineEdit()
        edit_layout.addRow("URL:", self.edit_url)

        self.edit_desc = QLineEdit()
        edit_layout.addRow("Description:", self.edit_desc)

        layout.addWidget(edit_group)

        # Buttons
        btn_layout = QHBoxLayout()

        save_btn = QPushButton("Save Changes")
        save_btn.clicked.connect(self.save_item)
        btn_layout.addWidget(save_btn)

        delete_btn = QPushButton("Delete Item")
        delete_btn.setStyleSheet("background-color: #8a5a5a;")
        delete_btn.clicked.connect(self.delete_item)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        self.current_item_id = None

    def load_items(self):
        self.item_list.clear()
        categories = set()

        for item in self.db.get_all_checklist_items():
            list_item = QListWidgetItem(f"[{item['category']}] {item['name']}")
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.item_list.addItem(list_item)
            categories.add(item['category'])

        self.edit_category.clear()
        self.edit_category.addItems(sorted(categories))

    def on_item_selected(self, list_item):
        item = list_item.data(Qt.ItemDataRole.UserRole)
        self.current_item_id = item['id']
        self.edit_name.setText(item['name'])
        self.edit_category.setCurrentText(item['category'])
        self.edit_url.setText(item.get('url', ''))
        self.edit_desc.setText(item.get('description', ''))

    def save_item(self):
        if not self.current_item_id:
            return

        self.db.update_checklist_item(
            self.current_item_id,
            name=self.edit_name.text().strip(),
            category=self.edit_category.currentText(),
            url=self.edit_url.text().strip(),
            description=self.edit_desc.text().strip()
        )
        self.load_items()

    def delete_item(self):
        if not self.current_item_id:
            return

        reply = QMessageBox.question(self, "Delete", "Delete this checklist item?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_checklist_item(self.current_item_id)
            self.current_item_id = None
            self.load_items()


class CascadeDeleteDialog(QDialog):
    """Dialog to select related items to delete along with main entity"""

    def __init__(self, parent, db: TrackerDB, entity_type: str, entity_id: str):
        super().__init__(parent)
        self.db = db
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.related_items = []
        self.setWindowTitle(f"Delete {entity_type.title()}")
        self.setMinimumWidth(400)
        self.setup_ui()
        self.find_related()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Apply dark theme with visible checkbox styling
        self.setStyleSheet("""
            QDialog {
                background-color: #0a0a0f;
                color: #a0a8b8;
            }
            QLabel {
                color: #a0a8b8;
            }
            QGroupBox {
                border: 1px solid #3a3a4a;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
                color: #a0a8b8;
            }
            QGroupBox::title {
                color: #c9a040;
                subcontrol-origin: margin;
                left: 10px;
            }
            QCheckBox {
                color: #a0a8b8;
                spacing: 10px;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #2a2a34;
                border: 2px solid #6a6a7a;
            }
            QCheckBox::indicator:unchecked:hover {
                background-color: #3a3a44;
                border: 2px solid #c9a040;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9a5a;
                border: 2px solid #6aba7a;
                image: url(icons/x-bold-white.svg);
            }
            QCheckBox::indicator:checked:hover {
                background-color: #5aaa6a;
                border: 2px solid #7aca8a;
                image: url(icons/x-bold-white.svg);
            }
            QCheckBox::indicator:disabled:checked {
                background-color: #3a7a4a;
                border: 2px solid #4a8a5a;
                image: url(icons/x-bold-gray.svg);
            }
            QCheckBox::indicator:disabled:unchecked {
                background-color: #1a1a24;
                border: 2px solid #3a3a4a;
            }
            QPushButton {
                background-color: #6b5b8a;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                color: #e0e0e8;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7b6b9a;
            }
        """)

        # Header
        self.header = QLabel(f"Deleting {self.entity_type}...")
        self.header.setStyleSheet("font-size: 14px; font-weight: bold; color: #c9a040; padding: 5px;")
        layout.addWidget(self.header)

        # Main item checkbox (always checked, disabled)
        self.main_check = QCheckBox(f"Delete this {self.entity_type}")
        self.main_check.setChecked(True)
        self.main_check.setEnabled(False)
        layout.addWidget(self.main_check)

        # Related items section
        self.related_group = QGroupBox("Also delete related items:")
        self.related_layout = QVBoxLayout(self.related_group)
        self.related_group.setVisible(False)
        layout.addWidget(self.related_group)

        # Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()

        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet("background-color: #8a5a5a;")
        delete_btn.clicked.connect(self.accept)
        btn_layout.addWidget(delete_btn)

        layout.addLayout(btn_layout)

    def find_related(self):
        """Find all entities related to the one being deleted"""
        cursor = self.db.conn.cursor()

        if self.entity_type == 'subject':
            subj = self.db.get_subject(self.entity_id)
            if subj:
                self.header.setText(f"Delete Subject: {subj['first_name']} {subj['last_name']}")

            # Find linked vehicles
            cursor.execute("SELECT v.* FROM vehicles v JOIN subject_vehicles sv ON v.id = sv.vehicle_id WHERE sv.subject_id = ?", (self.entity_id,))
            for row in cursor.fetchall():
                self.add_related_item('vehicle', dict(row), f"Vehicle: {row['plate']} {row['make']} {row['model']}")

            # Find linked weapons
            cursor.execute("SELECT w.* FROM weapons w JOIN subject_weapons sw ON w.id = sw.weapon_id WHERE sw.subject_id = ?", (self.entity_id,))
            for row in cursor.fetchall():
                self.add_related_item('weapon', dict(row), f"Weapon: {row['weapon_type']} {row['make']} {row['model']}")

        elif self.entity_type == 'event':
            evt = self.db.get_event(self.entity_id)
            if evt:
                self.header.setText(f"Delete Event: {evt['event_number']}")

            # Find linked subjects
            cursor.execute("SELECT s.* FROM subjects s JOIN subject_events se ON s.id = se.subject_id WHERE se.event_id = ?", (self.entity_id,))
            for row in cursor.fetchall():
                self.add_related_item('subject', dict(row), f"Subject: {row['first_name']} {row['last_name']}")

            # Find linked vehicles
            cursor.execute("SELECT v.* FROM vehicles v JOIN event_vehicles ev ON v.id = ev.vehicle_id WHERE ev.event_id = ?", (self.entity_id,))
            for row in cursor.fetchall():
                self.add_related_item('vehicle', dict(row), f"Vehicle: {row['plate']} {row['make']} {row['model']}")

            # Find linked weapons
            cursor.execute("SELECT w.* FROM weapons w JOIN event_weapons ew ON w.id = ew.weapon_id WHERE ew.event_id = ?", (self.entity_id,))
            for row in cursor.fetchall():
                self.add_related_item('weapon', dict(row), f"Weapon: {row['weapon_type']} {row['make']} {row['model']}")

            # Find evidence
            cursor.execute("SELECT * FROM evidence WHERE event_id = ?", (self.entity_id,))
            for row in cursor.fetchall():
                self.add_related_item('evidence', dict(row), f"Evidence: {row['description'][:30]}")

        elif self.entity_type == 'vehicle':
            veh = self.db.get_vehicle(self.entity_id)
            if veh:
                self.header.setText(f"Delete Vehicle: {veh['plate']} {veh['make']} {veh['model']}")

            # Find linked subjects
            cursor.execute("SELECT s.* FROM subjects s JOIN subject_vehicles sv ON s.id = sv.subject_id WHERE sv.vehicle_id = ?", (self.entity_id,))
            for row in cursor.fetchall():
                self.add_related_item('subject', dict(row), f"Subject: {row['first_name']} {row['last_name']}")

        elif self.entity_type == 'weapon':
            weap = self.db.get_weapon(self.entity_id)
            if weap:
                self.header.setText(f"Delete Weapon: {weap['weapon_type']} {weap.get('make', '')} {weap.get('model', '')}")

            # Find linked subjects
            cursor.execute("SELECT s.* FROM subjects s JOIN subject_weapons sw ON s.id = sw.subject_id WHERE sw.weapon_id = ?", (self.entity_id,))
            for row in cursor.fetchall():
                self.add_related_item('subject', dict(row), f"Subject: {row['first_name']} {row['last_name']}")

        elif self.entity_type == 'gang':
            gang = self.db.get_gang(self.entity_id)
            if gang:
                self.header.setText(f"Delete Gang: {gang['name']}")

            # Find linked subjects
            cursor.execute("SELECT s.* FROM subjects s JOIN subject_gangs sg ON s.id = sg.subject_id WHERE sg.gang_id = ?", (self.entity_id,))
            for row in cursor.fetchall():
                self.add_related_item('subject', dict(row), f"Subject: {row['first_name']} {row['last_name']}")

        elif self.entity_type == 'location':
            loc = self.db.get_location(self.entity_id)
            if loc:
                self.header.setText(f"Delete Location: {loc['address'][:40]}")

            # Find linked subjects
            cursor.execute("SELECT s.* FROM subjects s JOIN subject_locations sl ON s.id = sl.subject_id WHERE sl.location_id = ?", (self.entity_id,))
            for row in cursor.fetchall():
                self.add_related_item('subject', dict(row), f"Subject: {row['first_name']} {row['last_name']}")

        elif self.entity_type == 'online_account':
            acct = self.db.get_online_account(self.entity_id)
            if acct:
                display = f"@{acct.get('username', 'Unknown')}" if acct.get('username') else acct.get('platform', 'Account')
                self.header.setText(f"Delete Account: {acct.get('platform', '')} {display}")

            # Find linked vehicles
            for v in self.db.get_account_vehicles(self.entity_id):
                self.add_related_item('vehicle', v, f"Vehicle: {v.get('plate', 'No Plate')} {v.get('make', '')} {v.get('model', '')}")

        elif self.entity_type == 'dns':
            dns = self.db.get_dns_investigation(self.entity_id)
            if dns:
                self.header.setText(f"Delete DNS: {dns.get('domain_name', 'Unknown')}")

        elif self.entity_type == 'phone':
            phone = self.db.get_tracked_phone(self.entity_id)
            if phone:
                self.header.setText(f"Delete Phone: {phone.get('phone_number', 'Unknown')}")

    def add_related_item(self, item_type: str, item_data: dict, display_text: str):
        """Add a related item checkbox"""
        self.related_group.setVisible(True)
        checkbox = QCheckBox(display_text)
        checkbox.setChecked(False)
        checkbox.setProperty('item_type', item_type)
        checkbox.setProperty('item_id', item_data['id'])
        self.related_layout.addWidget(checkbox)
        self.related_items.append(checkbox)

    def get_items_to_delete(self) -> list:
        """Return list of (type, id) tuples for items to delete"""
        items = [(self.entity_type, self.entity_id)]
        for checkbox in self.related_items:
            if checkbox.isChecked():
                items.append((checkbox.property('item_type'), checkbox.property('item_id')))
        return items


class MergeImportDialog(QDialog):
    """Dialog for intelligent merge import with duplicate detection"""

    def __init__(self, parent, db: TrackerDB, import_data: dict):
        super().__init__(parent)
        self.db = db
        self.import_data = import_data
        self.setWindowTitle("Merge Import")
        self.setMinimumSize(700, 500)
        self.potential_duplicates = []
        self.setup_ui()
        self.analyze_import()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Merge Import - Combine Investigations")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #c9a040; padding: 10px;")
        layout.addWidget(header)

        # Options
        options_group = QGroupBox("Import Options")
        options_layout = QVBoxLayout(options_group)

        self.skip_existing = QCheckBox("Skip records that already exist (by ID)")
        self.skip_existing.setChecked(True)
        options_layout.addWidget(self.skip_existing)

        self.update_existing = QCheckBox("Update existing records with imported data")
        self.update_existing.setChecked(False)
        options_layout.addWidget(self.update_existing)

        self.remap_ids = QCheckBox("Generate new IDs for all imported records (full merge)")
        self.remap_ids.setChecked(False)
        self.remap_ids.setToolTip("Use this when merging data from a completely separate investigation")
        options_layout.addWidget(self.remap_ids)

        layout.addWidget(options_group)

        # Preview tabs
        self.preview_tabs = QTabWidget()

        # Summary tab
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.preview_tabs.addTab(self.summary_text, "Summary")

        # Duplicates tab
        self.duplicates_list = QListWidget()
        self.preview_tabs.addTab(self.duplicates_list, "Potential Duplicates")

        layout.addWidget(self.preview_tabs)

        # Buttons
        btn_layout = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()

        merge_btn = QPushButton("Merge Import")
        merge_btn.setStyleSheet("background-color: #5a8a6a; color: #e0e0e8;")
        merge_btn.clicked.connect(self.accept)
        btn_layout.addWidget(merge_btn)

        layout.addLayout(btn_layout)

    def analyze_import(self):
        """Analyze the import file and detect potential duplicates"""
        summary_lines = []
        data = self.import_data

        # Count records in import file
        summary_lines.append(f"Import file date: {data.get('export_date', 'Unknown')}")
        summary_lines.append(f"Export version: {data.get('export_version', '1.0')}")
        summary_lines.append("")
        summary_lines.append("Records in import file:")

        entity_counts = {
            'subjects': 'Subjects',
            'gangs': 'Gangs',
            'events': 'Events',
            'locations': 'Locations',
            'vehicles': 'Vehicles',
            'weapons': 'Weapons',
            'charges': 'Charges',
            'graffiti': 'Graffiti',
            'intel_reports': 'Intel Reports',
        }

        for key, label in entity_counts.items():
            count = len(data.get(key, []))
            if count > 0:
                summary_lines.append(f"  • {label}: {count}")

        summary_lines.append("")
        summary_lines.append("Linking records:")
        link_counts = ['subject_gangs', 'subject_events', 'social_profiles',
                       'phone_numbers', 'emails', 'tattoos', 'case_numbers',
                       'state_ids', 'employment', 'media']
        for key in link_counts:
            count = len(data.get(key, []))
            if count > 0:
                summary_lines.append(f"  • {key}: {count}")

        self.summary_text.setText("\n".join(summary_lines))

        # Detect potential duplicate subjects
        existing_subjects = self.db.get_all_subjects()
        import_subjects = data.get('subjects', [])

        self.potential_duplicates = []
        for imp_subj in import_subjects:
            imp_name = (imp_subj.get('first_name', '') + ' ' + imp_subj.get('last_name', '')).strip().lower()
            imp_dob = imp_subj.get('dob', '')

            for exist_subj in existing_subjects:
                exist_name = (exist_subj.get('first_name', '') + ' ' + exist_subj.get('last_name', '')).strip().lower()
                exist_dob = exist_subj.get('dob', '')

                # Check for name match
                name_match = imp_name and exist_name and imp_name == exist_name
                # Check for DOB match
                dob_match = imp_dob and exist_dob and imp_dob == exist_dob
                # Check for same ID (exact duplicate)
                id_match = imp_subj.get('id') == exist_subj.get('id')

                if name_match or (dob_match and (imp_name in exist_name or exist_name in imp_name)):
                    self.potential_duplicates.append({
                        'import': imp_subj,
                        'existing': exist_subj,
                        'reason': 'Same ID' if id_match else ('Same name' if name_match else 'Similar name + same DOB')
                    })

        # Populate duplicates list
        for dup in self.potential_duplicates:
            imp = dup['import']
            exist = dup['existing']
            item_text = f"[{dup['reason']}] Import: {imp.get('first_name', '')} {imp.get('last_name', '')} ↔ Existing: {exist.get('first_name', '')} {exist.get('last_name', '')}"
            self.duplicates_list.addItem(item_text)

        if not self.potential_duplicates:
            self.duplicates_list.addItem("No potential duplicates detected - safe to merge!")

        # Update tab text with count
        dup_count = len(self.potential_duplicates)
        self.preview_tabs.setTabText(1, f"Potential Duplicates ({dup_count})")


# ============ ONLINE ACCOUNT DIALOG ============

class OnlineAccountDialog(QDialog):
    """Dialog for creating/editing online accounts"""

    def __init__(self, parent, db: TrackerDB, account_data=None):
        super().__init__(parent)
        self.db = db
        self.account_data = account_data
        self.existing_match_id = None  # Will store ID if duplicate found
        self.setWindowTitle("New Online Account" if not account_data else "Edit Online Account")
        self.setMinimumSize(550, 650)
        self.setup_ui()
        if account_data:
            self.load_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # Duplicate warning label (hidden by default)
        self.duplicate_warning = QLabel("⚠️ Already Exists: Will Link To Existing. Not Duplicate.")
        self.duplicate_warning.setStyleSheet("color: #ff6b6b; font-weight: bold; padding: 8px; background: #3a2a2a; border-radius: 4px;")
        self.duplicate_warning.setVisible(False)
        layout.addWidget(self.duplicate_warning)

        # Account Details Group
        details_group = QGroupBox("Account Details")
        form = QFormLayout(details_group)
        form.setSpacing(10)

        self.platform = QComboBox()
        self.platform.setEditable(True)
        self.platform.addItems(["Twitter/X", "Instagram", "TikTok", "Facebook", "Telegram",
                                "Reddit", "Discord", "Snapchat", "YouTube", "LinkedIn", "Website", "Other"])
        self.platform.currentTextChanged.connect(self.check_duplicate)
        form.addRow("Platform:", self.platform)

        self.platform_account_id = QLineEdit()
        self.platform_account_id.setPlaceholderText("Permanent platform ID (if known)")
        self.platform_account_id.textChanged.connect(self.check_duplicate)
        form.addRow("Platform ID:", self.platform_account_id)

        self.username = QLineEdit()
        self.username.setPlaceholderText("Current username/handle")
        self.username.textChanged.connect(self.check_duplicate)
        form.addRow("Username:", self.username)

        self.display_name = QLineEdit()
        self.display_name.setPlaceholderText("Display name on profile")
        form.addRow("Display Name:", self.display_name)

        self.profile_url = QLineEdit()
        self.profile_url.setPlaceholderText("https://...")
        self.profile_url.textChanged.connect(self.check_duplicate)
        form.addRow("Profile URL:", self.profile_url)

        self.account_type = QComboBox()
        self.account_type.addItems(["Unknown", "Personal", "Business", "Bot"])
        form.addRow("Account Type:", self.account_type)

        self.status = QComboBox()
        self.status.addItems(["Active", "Suspended", "Deleted", "Private"])
        form.addRow("Status:", self.status)

        layout.addWidget(details_group)

        # Link to Subject
        subj_group = QGroupBox("Link to Subject (Optional)")
        subj_layout = QVBoxLayout(subj_group)
        self.subject_link = QComboBox()
        self.subject_link.addItem("-- None --", None)
        for s in self.db.get_all_subjects():
            self.subject_link.addItem(f"{s['first_name']} {s['last_name']}", s['id'])
        subj_layout.addWidget(self.subject_link)
        layout.addWidget(subj_group)

        # Profile Screenshot
        photo_group = QGroupBox("Profile Screenshot")
        photo_layout = QVBoxLayout(photo_group)
        self.photo = PhotoUploadWidget(label="profile screenshot")
        photo_layout.addWidget(self.photo)
        layout.addWidget(photo_group)

        # Notes
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes = QTextEdit()
        self.notes.setMinimumHeight(80)
        self.notes.setPlaceholderText("Investigation notes...")
        notes_layout.addWidget(self.notes)
        layout.addWidget(notes_group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

    def check_duplicate(self):
        """Check if account already exists and show warning"""
        if self.account_data:  # Skip check when editing
            return

        platform = self.platform.currentText().strip()
        username = self.username.text().strip()
        platform_account_id = self.platform_account_id.text().strip()
        profile_url = self.profile_url.text().strip()

        existing_id = self.db.find_existing_online_account(
            platform=platform,
            username=username,
            platform_account_id=platform_account_id,
            profile_url=profile_url
        )

        if existing_id:
            self.existing_match_id = existing_id
            existing = self.db.get_online_account(existing_id)
            self.duplicate_warning.setText(f"⚠️ Already Exists: {existing.get('platform')}: @{existing.get('username', 'N/A')} - Will Link To Existing")
            self.duplicate_warning.setVisible(True)
            self.username.setStyleSheet("border: 2px solid #ff6b6b;")
        else:
            self.existing_match_id = None
            self.duplicate_warning.setVisible(False)
            self.username.setStyleSheet("")

    def load_data(self):
        """Load existing account data for editing"""
        if self.account_data:
            self.platform.setCurrentText(self.account_data.get('platform', ''))
            self.platform_account_id.setText(self.account_data.get('platform_account_id', ''))
            self.username.setText(self.account_data.get('username', ''))
            self.display_name.setText(self.account_data.get('display_name', ''))
            self.profile_url.setText(self.account_data.get('profile_url', ''))
            self.account_type.setCurrentText(self.account_data.get('account_type', 'Unknown'))
            self.status.setCurrentText(self.account_data.get('status', 'Active'))
            self.notes.setText(self.account_data.get('notes', ''))
            # Set subject link
            if self.account_data.get('subject_id'):
                for i in range(self.subject_link.count()):
                    if self.subject_link.itemData(i) == self.account_data['subject_id']:
                        self.subject_link.setCurrentIndex(i)
                        break

    def save(self):
        if not self.platform.currentText().strip():
            QMessageBox.warning(self, "Error", "Platform is required.")
            return

        platform = self.platform.currentText().strip()
        username = self.username.text().strip()
        platform_account_id = self.platform_account_id.text().strip()
        profile_url = self.profile_url.text().strip()

        if self.account_data:
            # Update existing
            self.db.update_online_account(
                self.account_data['id'],
                platform=platform,
                platform_account_id=platform_account_id,
                username=username,
                display_name=self.display_name.text().strip(),
                profile_url=profile_url,
                account_type=self.account_type.currentText(),
                status=self.status.currentText(),
                subject_id=self.subject_link.currentData(),
                notes=self.notes.toPlainText().strip()
            )
            # Save photo if provided
            if self.photo.photo_path:
                self.db.add_media('online_account', self.account_data['id'], self.photo.photo_path, file_type='image')
        elif self.existing_match_id:
            # Duplicate found - show merge review dialog
            existing = self.db.get_online_account(self.existing_match_id)

            # Build new data from form
            new_data = {
                'platform': platform,
                'platform_account_id': platform_account_id,
                'username': username,
                'display_name': self.display_name.text().strip(),
                'profile_url': profile_url,
                'account_type': self.account_type.currentText(),
                'status': self.status.currentText(),
                'notes': self.notes.toPlainText().strip()
            }

            # Field labels for display
            field_labels = {
                'platform': 'Platform',
                'platform_account_id': 'Platform ID',
                'username': 'Username',
                'display_name': 'Display Name',
                'profile_url': 'Profile URL',
                'account_type': 'Account Type',
                'status': 'Status',
                'notes': 'Notes'
            }

            # Show merge review dialog
            merge_dialog = MergeReviewDialog(self, 'online_account', existing, new_data, field_labels)
            if merge_dialog.exec() != QDialog.DialogCode.Accepted:
                return  # User cancelled

            # Apply merged data
            merged = merge_dialog.get_merged_data()
            self.db.update_online_account(
                self.existing_match_id,
                platform=merged.get('platform', ''),
                platform_account_id=merged.get('platform_account_id', ''),
                username=merged.get('username', ''),
                display_name=merged.get('display_name', ''),
                profile_url=merged.get('profile_url', ''),
                account_type=merged.get('account_type', 'Unknown'),
                status=merged.get('status', 'Active'),
                notes=merged.get('notes', '')
            )

            # Link to subject if specified
            subject_id = self.subject_link.currentData()
            if subject_id and not existing.get('subject_id'):
                self.db.update_online_account(self.existing_match_id, subject_id=subject_id)

            # Save photo if provided
            if self.photo.photo_path:
                self.db.add_media('online_account', self.existing_match_id, self.photo.photo_path, file_type='image')

            # Redirect to existing record
            self.redirect_to = ('online_account', self.existing_match_id)
            self.reject()
            return
        else:
            # Create new
            account_id = self.db.add_online_account(
                platform=platform,
                platform_account_id=platform_account_id,
                username=username,
                display_name=self.display_name.text().strip(),
                profile_url=profile_url,
                account_type=self.account_type.currentText(),
                status=self.status.currentText(),
                subject_id=self.subject_link.currentData(),
                notes=self.notes.toPlainText().strip()
            )
            # Save photo if provided
            if self.photo.photo_path and account_id:
                self.db.add_media('online_account', account_id, self.photo.photo_path, file_type='image')
        self.accept()


# ============ ACCOUNT POST DIALOG ============

class AccountPostDialog(QDialog):
    """Dialog for creating/editing account posts/activity"""

    def __init__(self, parent, db: TrackerDB, account_id: str = None, post_data: dict = None):
        super().__init__(parent)
        self.db = db
        self.account_id = account_id
        self.post_data = post_data
        self.setWindowTitle("Edit Post" if post_data else "Add Post/Activity")
        self.setMinimumSize(550, 600)
        self.photo_path = None
        self.setup_ui()
        if post_data:
            self.load_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # Linked Account Group
        account_group = QGroupBox("Linked Account")
        account_form = QFormLayout(account_group)
        self.account_select = QComboBox()
        self.account_select.addItem("-- Select Account --", None)
        for a in self.db.get_all_online_accounts():
            display = f"@{a['username']}" if a.get('username') else a['platform']
            self.account_select.addItem(f"{a['platform']}: {display}", a['id'])
        # Pre-select if account_id provided
        if self.account_id:
            for i in range(self.account_select.count()):
                if self.account_select.itemData(i) == self.account_id:
                    self.account_select.setCurrentIndex(i)
                    break
        account_form.addRow("Account:", self.account_select)
        layout.addWidget(account_group)

        # Post Details Group
        details_group = QGroupBox("Post Details")
        form = QFormLayout(details_group)
        form.setSpacing(10)

        self.title = QLineEdit()
        self.title.setPlaceholderText("e.g., 'Gun flash video', 'Drug sale listing', 'Threat to rival'")
        form.addRow("Title:", self.title)

        self.post_type = QComboBox()
        self.post_type.addItems(["Post", "Comment", "Story", "Reel", "Message", "Listing", "Bio", "Other"])
        form.addRow("Post Type:", self.post_type)

        self.post_date = QDateEdit()
        self.post_date.setCalendarPopup(True)
        self.post_date.setDate(QDate.currentDate())
        form.addRow("Post Date:", self.post_date)

        self.post_url = QLineEdit()
        self.post_url.setPlaceholderText("Direct link to post")
        form.addRow("Post URL:", self.post_url)

        self.activity_type = QComboBox()
        self.activity_type.setEditable(True)
        self.activity_type.addItems(["", "Drug Sale", "Weapon Sale", "Threat", "Gang Activity",
                                     "Money Laundering", "Fraud", "Stolen Property", "Other"])
        form.addRow("Activity Type:", self.activity_type)

        layout.addWidget(details_group)

        # Content
        content_group = QGroupBox("Content")
        content_layout = QVBoxLayout(content_group)
        self.content_text = QTextEdit()
        self.content_text.setMinimumHeight(100)
        self.content_text.setPlaceholderText("Text content of the post...")
        content_layout.addWidget(self.content_text)
        layout.addWidget(content_group)

        # Screenshot
        screenshot_group = QGroupBox("Screenshot")
        screenshot_layout = QVBoxLayout(screenshot_group)
        self.photo = PhotoUploadWidget(label="screenshot")
        screenshot_layout.addWidget(self.photo)
        layout.addWidget(screenshot_group)

        # Notes
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes = QTextEdit()
        self.notes.setMinimumHeight(60)
        self.notes.setPlaceholderText("Investigation notes...")
        notes_layout.addWidget(self.notes)
        layout.addWidget(notes_group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

    def load_data(self):
        """Load existing post data for editing"""
        p = self.post_data
        if p:
            # Set account
            if p.get('account_id'):
                for i in range(self.account_select.count()):
                    if self.account_select.itemData(i) == p['account_id']:
                        self.account_select.setCurrentIndex(i)
                        break
            # Set other fields
            self.title.setText(p.get('title', ''))
            if p.get('post_date'):
                self.post_date.setDate(QDate.fromString(p['post_date'], "yyyy-MM-dd"))
            self.post_type.setCurrentText(p.get('post_type', 'Post'))
            self.post_url.setText(p.get('post_url', ''))
            self.activity_type.setCurrentText(p.get('activity_type', ''))
            self.content_text.setText(p.get('content_text', ''))
            self.notes.setText(p.get('notes', ''))

    def save(self):
        selected_account_id = self.account_select.currentData()
        if not selected_account_id:
            QMessageBox.warning(self, "Error", "Please select a linked account.")
            return

        title = self.title.text().strip()
        if not title:
            QMessageBox.warning(self, "Error", "Please enter a title for the post.")
            return

        if self.post_data:
            # Update existing post
            self.db.update_account_post(
                self.post_data['id'],
                account_id=selected_account_id,
                title=title,
                post_date=self.post_date.date().toString("yyyy-MM-dd"),
                post_url=self.post_url.text().strip(),
                post_type=self.post_type.currentText(),
                content_text=self.content_text.toPlainText().strip(),
                activity_type=self.activity_type.currentText().strip(),
                notes=self.notes.toPlainText().strip()
            )
            post_id = self.post_data['id']
        else:
            # Create new post
            post_id = self.db.add_account_post(
                selected_account_id,
                title=title,
                post_date=self.post_date.date().toString("yyyy-MM-dd"),
                captured_date=datetime.now().strftime('%Y-%m-%d'),
                post_url=self.post_url.text().strip(),
                post_type=self.post_type.currentText(),
                content_text=self.content_text.toPlainText().strip(),
                activity_type=self.activity_type.currentText().strip(),
                notes=self.notes.toPlainText().strip()
            )

        # Save screenshot if provided
        if self.photo.photo_path and post_id:
            self.db.add_media('post', post_id, self.photo.photo_path, file_type='image')

        self.accept()


# ============ DNS INVESTIGATION DIALOG ============

class DNSInvestigationDialog(QDialog):
    """Dialog for creating/editing DNS investigations"""

    def __init__(self, parent, db: TrackerDB, dns_data=None):
        super().__init__(parent)
        self.db = db
        self.dns_data = dns_data
        self.setWindowTitle("New DNS Investigation" if not dns_data else "Edit DNS Investigation")
        self.setMinimumSize(600, 700)
        self.setup_ui()
        if dns_data:
            self.load_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # Domain Details Group
        domain_group = QGroupBox("Domain Information")
        form = QFormLayout(domain_group)
        form.setSpacing(10)

        self.domain_name = QLineEdit()
        self.domain_name.setPlaceholderText("example.com")
        form.addRow("Domain:", self.domain_name)

        self.investigation_date = QDateEdit()
        self.investigation_date.setCalendarPopup(True)
        self.investigation_date.setDate(QDate.currentDate())
        form.addRow("Investigation Date:", self.investigation_date)

        layout.addWidget(domain_group)

        # DNS Records Group
        dns_group = QGroupBox("DNS Records")
        dns_form = QFormLayout(dns_group)
        dns_form.setSpacing(8)

        self.a_records = QLineEdit()
        self.a_records.setPlaceholderText("IPv4 addresses (comma-separated)")
        dns_form.addRow("A Records:", self.a_records)

        self.aaaa_records = QLineEdit()
        self.aaaa_records.setPlaceholderText("IPv6 addresses (comma-separated)")
        dns_form.addRow("AAAA Records:", self.aaaa_records)

        self.mx_records = QLineEdit()
        self.mx_records.setPlaceholderText("Mail servers (comma-separated)")
        dns_form.addRow("MX Records:", self.mx_records)

        self.txt_records = QTextEdit()
        self.txt_records.setMaximumHeight(60)
        self.txt_records.setPlaceholderText("TXT records (SPF, DKIM, etc.)")
        dns_form.addRow("TXT Records:", self.txt_records)

        self.cname_records = QLineEdit()
        self.cname_records.setPlaceholderText("Canonical names")
        dns_form.addRow("CNAME:", self.cname_records)

        self.ns_records = QLineEdit()
        self.ns_records.setPlaceholderText("Nameservers")
        dns_form.addRow("NS Records:", self.ns_records)

        layout.addWidget(dns_group)

        # WHOIS Group
        whois_group = QGroupBox("WHOIS Information")
        whois_form = QFormLayout(whois_group)
        whois_form.setSpacing(8)

        self.registrar = QLineEdit()
        self.registrar.setPlaceholderText("Domain registrar")
        whois_form.addRow("Registrar:", self.registrar)

        self.registrant_name = QLineEdit()
        self.registrant_name.setPlaceholderText("Registrant name")
        whois_form.addRow("Registrant:", self.registrant_name)

        self.registrant_email = QLineEdit()
        self.registrant_email.setPlaceholderText("Registrant email")
        whois_form.addRow("Email:", self.registrant_email)

        self.registration_date = QLineEdit()
        self.registration_date.setPlaceholderText("YYYY-MM-DD")
        whois_form.addRow("Registered:", self.registration_date)

        self.expiration_date = QLineEdit()
        self.expiration_date.setPlaceholderText("YYYY-MM-DD")
        whois_form.addRow("Expires:", self.expiration_date)

        layout.addWidget(whois_group)

        # Hosting Group
        hosting_group = QGroupBox("Hosting Information")
        hosting_form = QFormLayout(hosting_group)
        hosting_form.setSpacing(8)

        self.hosting_provider = QLineEdit()
        self.hosting_provider.setPlaceholderText("Hosting provider")
        hosting_form.addRow("Provider:", self.hosting_provider)

        self.ip_addresses = QLineEdit()
        self.ip_addresses.setPlaceholderText("Associated IPs (comma-separated)")
        hosting_form.addRow("IP Addresses:", self.ip_addresses)

        layout.addWidget(hosting_group)

        # Links Group
        links_group = QGroupBox("Linked Entities (Optional)")
        links_form = QFormLayout(links_group)

        self.subject_link = QComboBox()
        self.subject_link.addItem("-- None --", None)
        for s in self.db.get_all_subjects():
            self.subject_link.addItem(f"{s['first_name']} {s['last_name']}", s['id'])
        links_form.addRow("Subject:", self.subject_link)

        self.account_link = QComboBox()
        self.account_link.addItem("-- None --", None)
        for a in self.db.get_all_online_accounts():
            self.account_link.addItem(f"@{a['username']} ({a['platform']})", a['id'])
        links_form.addRow("Account:", self.account_link)

        layout.addWidget(links_group)

        # Screenshot
        photo_group = QGroupBox("Screenshot")
        photo_layout = QVBoxLayout(photo_group)
        self.photo = PhotoUploadWidget(label="DNS screenshot")
        photo_layout.addWidget(self.photo)
        layout.addWidget(photo_group)

        # Notes
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes = QTextEdit()
        self.notes.setMinimumHeight(60)
        self.notes.setPlaceholderText("Investigation notes...")
        notes_layout.addWidget(self.notes)
        layout.addWidget(notes_group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

    def load_data(self):
        """Load existing DNS data for editing"""
        d = self.dns_data
        if d:
            self.domain_name.setText(d.get('domain_name', ''))
            if d.get('investigation_date'):
                self.investigation_date.setDate(QDate.fromString(d['investigation_date'], "yyyy-MM-dd"))
            self.a_records.setText(d.get('a_records', ''))
            self.aaaa_records.setText(d.get('aaaa_records', ''))
            self.mx_records.setText(d.get('mx_records', ''))
            self.txt_records.setText(d.get('txt_records', ''))
            self.cname_records.setText(d.get('cname_records', ''))
            self.ns_records.setText(d.get('ns_records', ''))
            self.registrar.setText(d.get('registrar', ''))
            self.registrant_name.setText(d.get('registrant_name', ''))
            self.registrant_email.setText(d.get('registrant_email', ''))
            self.registration_date.setText(d.get('registration_date', ''))
            self.expiration_date.setText(d.get('expiration_date', ''))
            self.hosting_provider.setText(d.get('hosting_provider', ''))
            self.ip_addresses.setText(d.get('ip_addresses', ''))
            self.notes.setText(d.get('notes', ''))
            # Set links
            if d.get('subject_id'):
                for i in range(self.subject_link.count()):
                    if self.subject_link.itemData(i) == d['subject_id']:
                        self.subject_link.setCurrentIndex(i)
                        break
            if d.get('account_id'):
                for i in range(self.account_link.count()):
                    if self.account_link.itemData(i) == d['account_id']:
                        self.account_link.setCurrentIndex(i)
                        break

    def save(self):
        if not self.domain_name.text().strip():
            QMessageBox.warning(self, "Error", "Domain name is required.")
            return

        kwargs = {
            'investigation_date': self.investigation_date.date().toString("yyyy-MM-dd"),
            'a_records': self.a_records.text().strip(),
            'aaaa_records': self.aaaa_records.text().strip(),
            'mx_records': self.mx_records.text().strip(),
            'txt_records': self.txt_records.toPlainText().strip(),
            'cname_records': self.cname_records.text().strip(),
            'ns_records': self.ns_records.text().strip(),
            'registrar': self.registrar.text().strip(),
            'registrant_name': self.registrant_name.text().strip(),
            'registrant_email': self.registrant_email.text().strip(),
            'registration_date': self.registration_date.text().strip(),
            'expiration_date': self.expiration_date.text().strip(),
            'hosting_provider': self.hosting_provider.text().strip(),
            'ip_addresses': self.ip_addresses.text().strip(),
            'subject_id': self.subject_link.currentData(),
            'account_id': self.account_link.currentData(),
            'notes': self.notes.toPlainText().strip()
        }

        if self.dns_data:
            # Update existing
            self.db.update_dns_investigation(self.dns_data['id'], domain_name=self.domain_name.text().strip(), **kwargs)
            dns_id = self.dns_data['id']
        else:
            # Create new
            dns_id = self.db.add_dns_investigation(self.domain_name.text().strip(), **kwargs)

        # Save photo if provided
        if self.photo.photo_path and dns_id:
            self.db.add_media('dns', dns_id, self.photo.photo_path, file_type='image')

        self.accept()


# ============ CUSTOM LINK DIALOG ============

class CustomLinkDialog(QDialog):
    """Dialog for creating custom links to entities"""

    def __init__(self, parent, db: TrackerDB, entity_type: str, entity_id: str):
        super().__init__(parent)
        self.db = db
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.setWindowTitle("Add Custom Link")
        self.setMinimumSize(450, 400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Link Details Group
        details_group = QGroupBox("Link Details")
        form = QFormLayout(details_group)
        form.setSpacing(10)

        self.link_type = QComboBox()
        self.link_type.setEditable(True)
        self.link_type.addItems(["", "Evidence", "Related Case", "Informant Tip", "Intel Report",
                                 "Court Document", "Surveillance", "Social Media", "Other"])
        form.addRow("Link Type:", self.link_type)

        self.title = QLineEdit()
        self.title.setPlaceholderText("Short title for this link")
        form.addRow("Title:", self.title)

        self.url = QLineEdit()
        self.url.setPlaceholderText("Optional URL (https://...)")
        form.addRow("URL:", self.url)

        layout.addWidget(details_group)

        # Description
        desc_group = QGroupBox("Description")
        desc_layout = QVBoxLayout(desc_group)
        self.description = QTextEdit()
        self.description.setMinimumHeight(80)
        self.description.setPlaceholderText("Detailed description...")
        desc_layout.addWidget(self.description)
        layout.addWidget(desc_group)

        # Notes
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes = QTextEdit()
        self.notes.setMinimumHeight(60)
        self.notes.setPlaceholderText("Additional notes...")
        notes_layout.addWidget(self.notes)
        layout.addWidget(notes_group)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def save(self):
        if not self.title.text().strip():
            QMessageBox.warning(self, "Error", "Title is required.")
            return

        self.db.add_custom_link(
            self.entity_type,
            self.entity_id,
            self.title.text().strip(),
            link_type=self.link_type.currentText().strip(),
            description=self.description.toPlainText().strip(),
            url=self.url.text().strip(),
            notes=self.notes.toPlainText().strip()
        )
        self.accept()


# ============ TRACKED PHONE DIALOG ============

class TrackedPhoneDialog(QDialog):
    """Dialog for creating/editing tracked phone numbers"""

    def __init__(self, parent, db: TrackerDB, phone_data=None):
        super().__init__(parent)
        self.db = db
        self.phone_data = phone_data
        self.existing_match_id = None  # Will store ID if duplicate found
        self.setWindowTitle("New Phone Number" if not phone_data else "Edit Phone Number")
        self.setMinimumSize(500, 600)
        self.setup_ui()
        if phone_data:
            self.load_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # Duplicate warning label (hidden by default)
        self.duplicate_warning = QLabel("⚠️ Already Exists: Will Link To Existing. Not Duplicate.")
        self.duplicate_warning.setStyleSheet("color: #ff6b6b; font-weight: bold; padding: 8px; background: #3a2a2a; border-radius: 4px;")
        self.duplicate_warning.setVisible(False)
        layout.addWidget(self.duplicate_warning)

        # Phone Details Group
        details_group = QGroupBox("Phone Details")
        form = QFormLayout(details_group)
        form.setSpacing(10)

        self.phone_number = QLineEdit()
        self.phone_number.setPlaceholderText("123-456-7890")
        self.phone_number.textChanged.connect(self.check_duplicate)
        form.addRow("Phone Number:", self.phone_number)

        self.phone_type = QComboBox()
        self.phone_type.addItems(["Unknown", "Cell", "Landline", "VoIP", "Burner", "Prepaid"])
        form.addRow("Phone Type:", self.phone_type)

        self.status = QComboBox()
        self.status.addItems(["Active", "Disconnected", "Unknown"])
        form.addRow("Status:", self.status)

        layout.addWidget(details_group)

        # Carrier Info Group
        carrier_group = QGroupBox("Carrier Information")
        carrier_form = QFormLayout(carrier_group)

        self.carrier = QLineEdit()
        self.carrier.setPlaceholderText("e.g., Verizon, AT&T, T-Mobile")
        carrier_form.addRow("Carrier:", self.carrier)

        self.carrier_type = QComboBox()
        self.carrier_type.setEditable(True)
        self.carrier_type.addItems(["", "Wireless", "Landline", "VoIP", "Prepaid"])
        carrier_form.addRow("Carrier Type:", self.carrier_type)

        self.location_area = QLineEdit()
        self.location_area.setPlaceholderText("City, State")
        carrier_form.addRow("Location/Area:", self.location_area)

        self.registered_name = QLineEdit()
        self.registered_name.setPlaceholderText("Name from carrier lookup (if known)")
        carrier_form.addRow("Registered To:", self.registered_name)

        layout.addWidget(carrier_group)

        # Activity Dates
        dates_group = QGroupBox("Activity")
        dates_form = QFormLayout(dates_group)

        self.first_seen = QDateEdit()
        self.first_seen.setCalendarPopup(True)
        self.first_seen.setDate(QDate.currentDate())
        dates_form.addRow("First Seen:", self.first_seen)

        self.last_seen = QDateEdit()
        self.last_seen.setCalendarPopup(True)
        self.last_seen.setDate(QDate.currentDate())
        dates_form.addRow("Last Seen:", self.last_seen)

        layout.addWidget(dates_group)

        # Links Group
        links_group = QGroupBox("Link To (Optional)")
        links_form = QFormLayout(links_group)

        self.subject_link = QComboBox()
        self.subject_link.addItem("-- None --", None)
        for s in self.db.get_all_subjects():
            self.subject_link.addItem(f"{s['first_name']} {s['last_name']}", s['id'])
        links_form.addRow("Subject:", self.subject_link)

        self.account_link = QComboBox()
        self.account_link.addItem("-- None --", None)
        for a in self.db.get_all_online_accounts():
            display = f"@{a['username']}" if a['username'] else a['platform']
            self.account_link.addItem(f"{a['platform']}: {display}", a['id'])
        links_form.addRow("Online Account:", self.account_link)

        layout.addWidget(links_group)

        # Screenshot/Photo
        photo_group = QGroupBox("Photo/Screenshot")
        photo_layout = QVBoxLayout(photo_group)
        self.photo = PhotoUploadWidget(label="phone screenshot")
        photo_layout.addWidget(self.photo)
        layout.addWidget(photo_group)

        # Notes
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes = QTextEdit()
        self.notes.setMinimumHeight(80)
        self.notes.setPlaceholderText("Investigation notes, where number was found, etc.")
        notes_layout.addWidget(self.notes)
        layout.addWidget(notes_group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

    def load_data(self):
        """Load existing phone data for editing"""
        p = self.phone_data
        if p:
            self.phone_number.setText(p.get('phone_number', ''))
            self.phone_type.setCurrentText(p.get('phone_type', 'Unknown'))
            self.status.setCurrentText(p.get('status', 'Active'))
            self.carrier.setText(p.get('carrier', ''))
            self.carrier_type.setCurrentText(p.get('carrier_type', ''))
            self.location_area.setText(p.get('location_area', ''))
            self.registered_name.setText(p.get('registered_name', ''))
            if p.get('first_seen_date'):
                self.first_seen.setDate(QDate.fromString(p['first_seen_date'], "yyyy-MM-dd"))
            if p.get('last_seen_date'):
                self.last_seen.setDate(QDate.fromString(p['last_seen_date'], "yyyy-MM-dd"))
            self.notes.setText(p.get('notes', ''))
            # Set links
            if p.get('subject_id'):
                for i in range(self.subject_link.count()):
                    if self.subject_link.itemData(i) == p['subject_id']:
                        self.subject_link.setCurrentIndex(i)
                        break
            if p.get('account_id'):
                for i in range(self.account_link.count()):
                    if self.account_link.itemData(i) == p['account_id']:
                        self.account_link.setCurrentIndex(i)
                        break

    def check_duplicate(self):
        """Check if phone already exists and show warning"""
        if self.phone_data:  # Skip check when editing
            return

        phone_number = self.phone_number.text().strip()
        if not phone_number:
            self.existing_match_id = None
            self.duplicate_warning.setVisible(False)
            self.phone_number.setStyleSheet("")
            return

        existing_id = self.db.find_existing_tracked_phone(phone_number)

        if existing_id:
            self.existing_match_id = existing_id
            existing = self.db.get_tracked_phone(existing_id)
            self.duplicate_warning.setText(f"⚠️ Already Exists: {existing.get('phone_number', 'N/A')} - Will Link To Existing")
            self.duplicate_warning.setVisible(True)
            self.phone_number.setStyleSheet("border: 2px solid #ff6b6b;")
        else:
            self.existing_match_id = None
            self.duplicate_warning.setVisible(False)
            self.phone_number.setStyleSheet("")

    def save(self):
        phone_number = self.phone_number.text().strip()
        if not phone_number:
            QMessageBox.warning(self, "Error", "Phone number is required.")
            return

        kwargs = {
            'phone_type': self.phone_type.currentText(),
            'carrier': self.carrier.text().strip(),
            'carrier_type': self.carrier_type.currentText().strip(),
            'location_area': self.location_area.text().strip(),
            'status': self.status.currentText(),
            'registered_name': self.registered_name.text().strip(),
            'first_seen_date': self.first_seen.date().toString("yyyy-MM-dd"),
            'last_seen_date': self.last_seen.date().toString("yyyy-MM-dd"),
            'subject_id': self.subject_link.currentData(),
            'account_id': self.account_link.currentData(),
            'notes': self.notes.toPlainText().strip()
        }

        if self.phone_data:
            # Update existing
            self.db.update_tracked_phone(self.phone_data['id'], phone_number=phone_number, **kwargs)
            # Save photo if provided
            if self.photo.photo_path:
                self.db.add_media('phone', self.phone_data['id'], self.photo.photo_path, file_type='image')
        elif self.existing_match_id:
            # Duplicate found - show merge review dialog
            existing = self.db.get_tracked_phone(self.existing_match_id)

            # Build new data from form
            new_data = {
                'phone_number': phone_number,
                'phone_type': kwargs['phone_type'],
                'carrier': kwargs['carrier'],
                'carrier_type': kwargs['carrier_type'],
                'location_area': kwargs['location_area'],
                'status': kwargs['status'],
                'registered_name': kwargs['registered_name'],
                'notes': kwargs['notes']
            }

            # Field labels for display
            field_labels = {
                'phone_number': 'Phone Number',
                'phone_type': 'Phone Type',
                'carrier': 'Carrier',
                'carrier_type': 'Carrier Type',
                'location_area': 'Location/Area',
                'status': 'Status',
                'registered_name': 'Registered Name',
                'notes': 'Notes'
            }

            # Show merge review dialog
            merge_dialog = MergeReviewDialog(self, 'phone', existing, new_data, field_labels)
            if merge_dialog.exec() != QDialog.DialogCode.Accepted:
                return  # User cancelled

            # Apply merged data
            merged = merge_dialog.get_merged_data()
            self.db.update_tracked_phone(
                self.existing_match_id,
                phone_number=merged.get('phone_number', ''),
                phone_type=merged.get('phone_type', 'Unknown'),
                carrier=merged.get('carrier', ''),
                carrier_type=merged.get('carrier_type', ''),
                location_area=merged.get('location_area', ''),
                status=merged.get('status', 'Active'),
                registered_name=merged.get('registered_name', ''),
                notes=merged.get('notes', '')
            )

            # Link to subject/account if specified
            if kwargs.get('subject_id') and not existing.get('subject_id'):
                self.db.update_tracked_phone(self.existing_match_id, subject_id=kwargs['subject_id'])
            if kwargs.get('account_id') and not existing.get('account_id'):
                self.db.update_tracked_phone(self.existing_match_id, account_id=kwargs['account_id'])

            # Save photo if provided
            if self.photo.photo_path:
                self.db.add_media('phone', self.existing_match_id, self.photo.photo_path, file_type='image')

            # Redirect to existing record
            self.redirect_to = ('phone', self.existing_match_id)
            self.reject()
            return
        else:
            # Create new
            phone_id = self.db.add_tracked_phone(phone_number, **kwargs)
            # Save photo if provided
            if self.photo.photo_path and phone_id:
                self.db.add_media('phone', phone_id, self.photo.photo_path, file_type='image')

        self.accept()


# ============ MERGE REVIEW DIALOG ============

class MergeReviewDialog(QDialog):
    """Dialog for reviewing and merging duplicate records field by field"""

    def __init__(self, parent, entity_type: str, existing_data: dict, new_data: dict, field_labels: dict):
        """
        Args:
            entity_type: Type of entity (vehicle, location, online_account, phone)
            existing_data: Dict of existing record values
            new_data: Dict of new input values
            field_labels: Dict mapping field names to display labels
        """
        super().__init__(parent)
        self.entity_type = entity_type
        self.existing_data = existing_data
        self.new_data = new_data
        self.field_labels = field_labels
        self.merge_choices = {}  # field -> 'existing', 'new', 'both', or 'skip'
        self.setWindowTitle(f"Review Merge - {entity_type.replace('_', ' ').title()}")
        self.setMinimumSize(650, 500)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        header = QLabel("⚠️ Duplicate Record Found - Review Differences")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff6b6b;")
        layout.addWidget(header)

        hint = QLabel("Choose how to handle each field that differs. 'Keep Both' will store both values.")
        hint.setStyleSheet("color: #8a8a9a; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Scroll area for field comparisons
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        self.fields_layout = QVBoxLayout(container)
        self.fields_layout.setSpacing(10)

        # Build comparison rows for differing fields
        self.field_widgets = {}
        differences_found = False

        for field, label in self.field_labels.items():
            existing_val = str(self.existing_data.get(field, '') or '').strip()
            new_val = str(self.new_data.get(field, '') or '').strip()

            # Only show fields that differ and where new value exists
            if new_val and existing_val != new_val:
                differences_found = True
                self._add_field_row(field, label, existing_val, new_val)

        if not differences_found:
            no_diff = QLabel("No differences found - records are identical.")
            no_diff.setStyleSheet("color: #6a9a6a; font-style: italic; padding: 20px;")
            self.fields_layout.addWidget(no_diff)

        self.fields_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Buttons
        btn_layout = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()

        merge_btn = QPushButton("Apply Merge")
        merge_btn.setStyleSheet("background-color: #5a8a5a; font-weight: bold;")
        merge_btn.clicked.connect(self.accept)
        btn_layout.addWidget(merge_btn)

        layout.addLayout(btn_layout)

    def _add_field_row(self, field: str, label: str, existing_val: str, new_val: str):
        """Add a comparison row for a single field"""
        group = QGroupBox(label)
        group.setStyleSheet("QGroupBox { font-weight: bold; }")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(8)

        # Existing value row
        existing_row = QHBoxLayout()
        existing_label = QLabel("Existing:")
        existing_label.setFixedWidth(70)
        existing_label.setStyleSheet("color: #7a9aca;")
        existing_row.addWidget(existing_label)

        existing_value = QLabel(existing_val if existing_val else "(empty)")
        existing_value.setStyleSheet("background: #2a2a3a; padding: 5px; border-radius: 3px;")
        existing_value.setWordWrap(True)
        existing_row.addWidget(existing_value, 1)
        group_layout.addLayout(existing_row)

        # New value row
        new_row = QHBoxLayout()
        new_label = QLabel("New:")
        new_label.setFixedWidth(70)
        new_label.setStyleSheet("color: #ca9a7a;")
        new_row.addWidget(new_label)

        new_value = QLabel(new_val if new_val else "(empty)")
        new_value.setStyleSheet("background: #3a2a2a; padding: 5px; border-radius: 3px;")
        new_value.setWordWrap(True)
        new_row.addWidget(new_value, 1)
        group_layout.addLayout(new_row)

        # Action buttons row
        action_row = QHBoxLayout()
        action_row.addStretch()

        btn_group = QButtonGroup(self)

        keep_existing_btn = QRadioButton("Keep Existing")
        keep_existing_btn.setChecked(True)  # Default
        btn_group.addButton(keep_existing_btn)
        action_row.addWidget(keep_existing_btn)

        use_new_btn = QRadioButton("Use New")
        btn_group.addButton(use_new_btn)
        action_row.addWidget(use_new_btn)

        keep_both_btn = QRadioButton("Keep Both")
        keep_both_btn.setToolTip("Store both values (comma-separated)")
        btn_group.addButton(keep_both_btn)
        action_row.addWidget(keep_both_btn)

        skip_btn = QPushButton("✕")
        skip_btn.setFixedSize(24, 24)
        skip_btn.setToolTip("Skip/ignore this field")
        skip_btn.setStyleSheet("background: #5a3a3a; border-radius: 12px;")
        skip_btn.clicked.connect(lambda: self._skip_field(field, group))
        action_row.addWidget(skip_btn)

        group_layout.addLayout(action_row)

        self.fields_layout.addWidget(group)
        self.field_widgets[field] = {
            'group': group,
            'existing': existing_val,
            'new': new_val,
            'keep_existing': keep_existing_btn,
            'use_new': use_new_btn,
            'keep_both': keep_both_btn,
            'skipped': False
        }

    def _skip_field(self, field: str, group: QGroupBox):
        """Mark a field as skipped (won't be included in merge)"""
        if field in self.field_widgets:
            self.field_widgets[field]['skipped'] = True
            group.setStyleSheet("QGroupBox { color: #5a5a5a; }")
            group.setTitle(f"{self.field_labels.get(field, field)} (Skipped)")

    def get_merged_data(self) -> dict:
        """Get the final merged data based on user selections"""
        merged = dict(self.existing_data)  # Start with existing

        for field, widgets in self.field_widgets.items():
            if widgets['skipped']:
                continue  # Don't change this field

            existing_val = widgets['existing']
            new_val = widgets['new']

            if widgets['use_new'].isChecked():
                merged[field] = new_val
            elif widgets['keep_both'].isChecked():
                # Combine values
                if existing_val and new_val:
                    # Check if already contains the value
                    existing_parts = [v.strip() for v in existing_val.split(',')]
                    if new_val not in existing_parts:
                        merged[field] = f"{existing_val}, {new_val}"
                elif new_val:
                    merged[field] = new_val
            # else keep_existing is default - no change needed

        return merged


# ============ LINK ACCOUNTS DIALOG ============

class LinkAccountsDialog(QDialog):
    """Dialog for linking online accounts together (like associates for subjects)"""

    def __init__(self, parent, db: TrackerDB, account_id: str):
        super().__init__(parent)
        self.db = db
        self.account_id = account_id
        self.setWindowTitle("Link Associated Accounts")
        self.setMinimumSize(500, 450)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        account = self.db.get_online_account(self.account_id)
        header = QLabel(f"Link accounts to @{account.get('username', 'Unknown')}")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #c9a040;")
        layout.addWidget(header)

        hint = QLabel("Link accounts that show coordinated activity, same ownership, or related content.")
        hint.setStyleSheet("color: #6a6a7a; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Account selector
        select_group = QGroupBox("Select Account to Link")
        select_layout = QVBoxLayout(select_group)

        self.account_combo = QComboBox()
        self.account_combo.addItem("-- Select Account --", None)
        for a in self.db.get_all_online_accounts():
            if a['id'] != self.account_id:  # Don't show current account
                display = f"@{a['username']}" if a['username'] else a['platform']
                self.account_combo.addItem(f"{a['platform']}: {display}", a['id'])
        select_layout.addWidget(self.account_combo)
        layout.addWidget(select_group)

        # Association details
        details_group = QGroupBox("Association Details")
        form = QFormLayout(details_group)

        self.assoc_type = QComboBox()
        self.assoc_type.setEditable(True)
        self.assoc_type.addItems([
            "Promoting same content",
            "Same person suspected",
            "Coordinated activity",
            "Shared audience/followers",
            "Cross-posting",
            "Business relationship",
            "Same location/events",
            "Other"
        ])
        form.addRow("Association Type:", self.assoc_type)

        self.confidence = QComboBox()
        self.confidence.addItems(["Low", "Medium", "High", "Confirmed"])
        self.confidence.setCurrentText("Medium")
        form.addRow("Confidence:", self.confidence)

        self.evidence = QTextEdit()
        self.evidence.setMaximumHeight(80)
        self.evidence.setPlaceholderText("What evidence links these accounts? (same photos, mutual promotion, etc.)")
        form.addRow("Evidence:", self.evidence)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(60)
        self.notes.setPlaceholderText("Additional notes...")
        form.addRow("Notes:", self.notes)

        layout.addWidget(details_group)

        # Current associations list
        assoc_group = QGroupBox("Current Linked Accounts")
        assoc_layout = QVBoxLayout(assoc_group)

        self.assoc_list = QListWidget()
        self.assoc_list.setMaximumHeight(100)
        self._refresh_associations()
        assoc_layout.addWidget(self.assoc_list)

        remove_btn = QPushButton("Remove Selected Link")
        remove_btn.setStyleSheet("background-color: #8a5a5a;")
        remove_btn.clicked.connect(self._remove_selected)
        assoc_layout.addWidget(remove_btn)

        layout.addWidget(assoc_group)

        # Buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Link")
        add_btn.setStyleSheet("background-color: #5a8a6a;")
        add_btn.clicked.connect(self.add_link)
        btn_layout.addWidget(add_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _refresh_associations(self):
        """Refresh the list of current associations"""
        self.assoc_list.clear()
        assocs = self.db.get_account_associations(self.account_id)
        for a in assocs:
            text = f"@{a['linked_username']} ({a['linked_platform']}) - {a.get('association_type', 'Linked')} [{a.get('confidence', 'Medium')}]"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, a['id'])
            self.assoc_list.addItem(item)

    def _remove_selected(self):
        """Remove selected association"""
        item = self.assoc_list.currentItem()
        if not item:
            return
        assoc_id = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "Remove Link",
                                     "Remove this account association?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_account_association(assoc_id)
            self._refresh_associations()

    def add_link(self):
        """Add a new account association"""
        other_id = self.account_combo.currentData()
        if not other_id:
            QMessageBox.warning(self, "Error", "Please select an account to link.")
            return

        result = self.db.add_account_association(
            self.account_id,
            other_id,
            association_type=self.assoc_type.currentText().strip(),
            confidence=self.confidence.currentText(),
            evidence=self.evidence.toPlainText().strip(),
            notes=self.notes.toPlainText().strip()
        )

        if result:
            self._refresh_associations()
            self.account_combo.setCurrentIndex(0)
            self.evidence.clear()
            self.notes.clear()
            QMessageBox.information(self, "Success", "Account link added.")
        else:
            QMessageBox.warning(self, "Error", "These accounts are already linked.")


class LinkAccountVehicleDialog(QDialog):
    """Dialog for linking vehicles to online accounts"""

    def __init__(self, parent, db: TrackerDB, account_id: str):
        super().__init__(parent)
        self.db = db
        self.account_id = account_id
        self.setWindowTitle("Link Vehicle to Account")
        self.setMinimumSize(500, 400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        account = self.db.get_online_account(self.account_id)
        header = QLabel(f"Link vehicle to @{account.get('username', 'Unknown')}")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #c9a040;")
        layout.addWidget(header)

        hint = QLabel("Link vehicles that appear in posts, are for sale, or are associated with this account.")
        hint.setStyleSheet("color: #6a6a7a; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Vehicle selector
        select_group = QGroupBox("Select Vehicle")
        select_layout = QVBoxLayout(select_group)

        self.vehicle_combo = QComboBox()
        self.vehicle_combo.addItem("-- Select Vehicle --", None)
        for v in self.db.get_all_vehicles():
            plate = v.get('plate') or 'No Plate'
            desc = f"{v.get('color', '')} {v.get('year', '')} {v.get('make', '')} {v.get('model', '')}".strip()
            self.vehicle_combo.addItem(f"{plate} - {desc}", v['id'])
        select_layout.addWidget(self.vehicle_combo)
        layout.addWidget(select_group)

        # Relationship details
        details_group = QGroupBox("Link Details")
        form = QFormLayout(details_group)

        self.relationship = QComboBox()
        self.relationship.setEditable(True)
        self.relationship.addItems([
            "Driven in video/post",
            "For sale",
            "Pictured with",
            "Mentioned",
            "Background/location",
            "Other"
        ])
        form.addRow("Relationship:", self.relationship)

        self.evidence = QTextEdit()
        self.evidence.setMaximumHeight(60)
        self.evidence.setPlaceholderText("Where did you see this? (post URL, screenshot, etc.)")
        form.addRow("Evidence:", self.evidence)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(60)
        self.notes.setPlaceholderText("Additional notes...")
        form.addRow("Notes:", self.notes)

        layout.addWidget(details_group)

        # Current links
        links_group = QGroupBox("Currently Linked Vehicles")
        links_layout = QVBoxLayout(links_group)

        self.links_list = QListWidget()
        self.links_list.setMaximumHeight(100)
        self._refresh_links()
        links_layout.addWidget(self.links_list)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.setStyleSheet("background-color: #8a5a5a;")
        remove_btn.clicked.connect(self._remove_selected)
        links_layout.addWidget(remove_btn)

        layout.addWidget(links_group)

        # Buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Link")
        add_btn.setStyleSheet("background-color: #5a8a6a;")
        add_btn.clicked.connect(self.add_link)
        btn_layout.addWidget(add_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _refresh_links(self):
        """Refresh the list of linked vehicles"""
        self.links_list.clear()
        links = self.db.get_account_vehicles(self.account_id)
        for link in links:
            plate = link.get('plate') or 'No Plate'
            desc = f"{link.get('make', '')} {link.get('model', '')}".strip()
            rel = f" - {link['relationship']}" if link.get('relationship') else ""
            item = QListWidgetItem(f"{plate}: {desc}{rel}")
            item.setData(Qt.ItemDataRole.UserRole, link['id'])
            self.links_list.addItem(item)

    def _remove_selected(self):
        """Remove selected vehicle link"""
        item = self.links_list.currentItem()
        if not item:
            return
        link_id = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "Remove Link",
                                     "Remove this vehicle link?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_account_vehicle_link(link_id)
            self._refresh_links()

    def add_link(self):
        """Add a new vehicle link"""
        vehicle_id = self.vehicle_combo.currentData()
        if not vehicle_id:
            QMessageBox.warning(self, "Error", "Please select a vehicle.")
            return

        result = self.db.link_account_to_vehicle(
            self.account_id,
            vehicle_id,
            relationship=self.relationship.currentText().strip(),
            evidence=self.evidence.toPlainText().strip(),
            notes=self.notes.toPlainText().strip()
        )

        if result:
            self._refresh_links()
            self.vehicle_combo.setCurrentIndex(0)
            self.evidence.clear()
            self.notes.clear()
            QMessageBox.information(self, "Success", "Vehicle linked to account.")
        else:
            QMessageBox.warning(self, "Error", "This vehicle is already linked to this account.")


# ============ UNIVERSAL LINK DIALOG ============

class UniversalLinkDialog(QDialog):
    """Universal dialog for linking any entity to any other entity - the spider web builder"""

    # All linkable entity types with display names and icons
    ENTITY_TYPES = [
        ('subject', '👤 Subject'),
        ('vehicle', '🚗 Vehicle'),
        ('online_account', '🌐 Online Account'),
        ('event', '📋 Event'),
        ('gang', '👥 Gang'),
        ('location', '🏠 Location'),
        ('weapon', '🔫 Weapon'),
        ('phone', '📱 Phone'),
        ('dns', '🔍 DNS'),
        ('post', '📝 Post'),
    ]

    # Common relationship types by category
    RELATIONSHIP_TYPES = [
        "",
        "Associated with",
        "Connected to",
        "Owned by",
        "Used by",
        "Located at",
        "Involved in",
        "Related to",
        "Seen with",
        "Mentioned in",
        "Pictured with",
        "Drives",
        "Lives at",
        "Works at",
        "Frequents",
        "Sold by",
        "Purchased from",
        "Evidence of",
        "Witness to",
        "Suspect in",
    ]

    def __init__(self, parent, db, source_type: str, source_id: str, source_name: str = ""):
        super().__init__(parent)
        self.db = db
        self.source_type = source_type
        self.source_id = source_id
        self.source_name = source_name or f"{source_type}: {source_id[:8]}"
        self.main_window = parent
        self.link_added = False  # Track if a link was added
        self.setWindowTitle("Add New Link")
        self.setMinimumSize(600, 650)
        self.setup_ui()
        self.load_existing_links()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header showing source entity
        header = QLabel(f"Link from: {self.source_name}")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #c9a040;")
        layout.addWidget(header)

        hint = QLabel("Create connections between entities to build the investigation web.")
        hint.setStyleSheet("color: #6a6a7a; font-size: 11px;")
        layout.addWidget(hint)

        # Target Entity Type Selection
        type_group = QGroupBox("Link To (Entity Type)")
        type_layout = QFormLayout(type_group)

        self.target_type = QComboBox()
        self.target_type.addItem("-- Select Type --", None)
        for type_code, type_display in self.ENTITY_TYPES:
            self.target_type.addItem(type_display, type_code)
        self.target_type.currentIndexChanged.connect(self.on_type_changed)
        type_layout.addRow("Entity Type:", self.target_type)

        layout.addWidget(type_group)

        # Target Entity Selection (populated when type is selected)
        entity_group = QGroupBox("Select Entity")
        entity_layout = QVBoxLayout(entity_group)

        self.target_entity = QComboBox()
        self.target_entity.addItem("-- Select entity type first --", None)
        entity_layout.addWidget(self.target_entity)

        # Create New button
        btn_row = QHBoxLayout()
        self.create_new_btn = QPushButton("+ Create New")
        self.create_new_btn.setStyleSheet("background-color: #5a8a6a;")
        self.create_new_btn.setEnabled(False)
        self.create_new_btn.clicked.connect(self.create_new_entity)
        btn_row.addWidget(self.create_new_btn)
        btn_row.addStretch()
        entity_layout.addLayout(btn_row)

        layout.addWidget(entity_group)

        # Relationship Details
        details_group = QGroupBox("Link Details")
        details_form = QFormLayout(details_group)
        details_form.setSpacing(8)

        self.relationship = QComboBox()
        self.relationship.setEditable(True)
        self.relationship.addItems(self.RELATIONSHIP_TYPES)
        details_form.addRow("Relationship:", self.relationship)

        self.confidence = QComboBox()
        self.confidence.addItems(["Medium", "Low", "High", "Confirmed"])
        details_form.addRow("Confidence:", self.confidence)

        self.evidence = QTextEdit()
        self.evidence.setMaximumHeight(60)
        self.evidence.setPlaceholderText("Evidence or proof of this connection...")
        details_form.addRow("Evidence:", self.evidence)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(60)
        self.notes.setPlaceholderText("Additional notes...")
        details_form.addRow("Notes:", self.notes)

        layout.addWidget(details_group)

        # Add Link Button
        add_btn = QPushButton("Add Link")
        add_btn.setStyleSheet("background-color: #5a8a6a; padding: 8px;")
        add_btn.clicked.connect(self.add_link)
        layout.addWidget(add_btn)

        # Current Links Display
        links_group = QGroupBox("Current Links")
        links_layout = QVBoxLayout(links_group)

        self.links_list = QListWidget()
        self.links_list.setMaximumHeight(150)
        links_layout.addWidget(self.links_list)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.setStyleSheet("background-color: #8a5a5a;")
        remove_btn.clicked.connect(self.remove_link)
        links_layout.addWidget(remove_btn)

        layout.addWidget(links_group)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def on_type_changed(self):
        """When target type changes, populate the entity dropdown"""
        target_type = self.target_type.currentData()
        self.target_entity.clear()
        self.create_new_btn.setEnabled(target_type is not None)

        if not target_type:
            self.target_entity.addItem("-- Select entity type first --", None)
            return

        self.target_entity.addItem("-- Select --", None)

        # Populate based on type
        if target_type == 'subject':
            for s in self.db.get_all_subjects():
                if target_type == self.source_type and s['id'] == self.source_id:
                    continue  # Skip self
                self.target_entity.addItem(f"👤 {s['first_name']} {s['last_name']}", s['id'])
        elif target_type == 'vehicle':
            for v in self.db.get_all_vehicles():
                self.target_entity.addItem(f"🚗 {v.get('plate', 'No Plate')} - {v.get('make', '')} {v.get('model', '')}", v['id'])
        elif target_type == 'online_account':
            for a in self.db.get_all_online_accounts():
                display = f"@{a['username']}" if a.get('username') else a.get('platform', 'Account')
                self.target_entity.addItem(f"🌐 {a.get('platform', '')}: {display}", a['id'])
        elif target_type == 'event':
            for e in self.db.get_all_events():
                self.target_entity.addItem(f"📋 {e.get('title', 'Event')}", e['id'])
        elif target_type == 'gang':
            for g in self.db.get_all_gangs():
                self.target_entity.addItem(f"👥 {g.get('name', 'Gang')}", g['id'])
        elif target_type == 'location':
            for l in self.db.get_all_locations():
                self.target_entity.addItem(f"🏠 {l.get('address', 'Location')}", l['id'])
        elif target_type == 'weapon':
            for w in self.db.get_all_weapons():
                self.target_entity.addItem(f"🔫 {w.get('weapon_type', '')} - {w.get('make', '')} {w.get('model', '')}", w['id'])
        elif target_type == 'phone':
            for p in self.db.get_all_tracked_phones():
                self.target_entity.addItem(f"📱 {p.get('phone_number', 'Phone')}", p['id'])
        elif target_type == 'dns':
            for d in self.db.get_all_dns_investigations():
                self.target_entity.addItem(f"🔍 {d.get('domain_name', 'Domain')}", d['id'])
        elif target_type == 'post':
            # Account posts - need to fetch them
            for a in self.db.get_all_online_accounts():
                for p in self.db.get_account_posts(a['id']):
                    text = p.get('content_text', '')[:25] + '...' if p.get('content_text') and len(p.get('content_text', '')) > 25 else (p.get('content_text') or p.get('post_type', 'Post'))
                    self.target_entity.addItem(f"📝 {text}", p['id'])

    def create_new_entity(self):
        """Open the appropriate dialog to create a new entity"""
        target_type = self.target_type.currentData()
        if not target_type:
            return

        new_id = None
        dialog = None

        # Find main window to get db reference
        main_win = self.main_window
        while main_win and not hasattr(main_win, 'db'):
            main_win = main_win.parent()

        if not main_win:
            return

        if target_type == 'subject':
            dialog = SubjectIntakeDialog(self, self.db)
        elif target_type == 'vehicle':
            dialog = VehicleIntakeDialog(self, self.db)
        elif target_type == 'online_account':
            dialog = OnlineAccountDialog(self, self.db)
        elif target_type == 'event':
            dialog = EventIntakeDialog(self, self.db)
        elif target_type == 'gang':
            dialog = GangIntakeDialog(self, self.db)
        elif target_type == 'location':
            dialog = LocationIntakeDialog(self, self.db)
        elif target_type == 'weapon':
            dialog = WeaponIntakeDialog(self, self.db)
        elif target_type == 'phone':
            dialog = TrackedPhoneDialog(self, self.db)
        elif target_type == 'dns':
            dialog = DNSInvestigationDialog(self, self.db)

        if dialog and dialog.exec() == QDialog.DialogCode.Accepted:
            # Refresh the entity dropdown
            self.on_type_changed()
            # Select the last item (newly created)
            if self.target_entity.count() > 1:
                self.target_entity.setCurrentIndex(self.target_entity.count() - 1)

    def add_link(self):
        """Add the link to the database"""
        target_type = self.target_type.currentData()
        target_id = self.target_entity.currentData()

        if not target_type or not target_id:
            QMessageBox.warning(self, "Error", "Please select an entity type and entity to link.")
            return

        link_id = self.db.add_entity_link(
            source_type=self.source_type,
            source_id=self.source_id,
            target_type=target_type,
            target_id=target_id,
            relationship=self.relationship.currentText().strip(),
            evidence=self.evidence.toPlainText().strip(),
            confidence=self.confidence.currentText(),
            notes=self.notes.toPlainText().strip()
        )

        if link_id:
            QMessageBox.information(self, "Success", "Link created successfully.")
            self.link_added = True  # Signal that refresh is needed
            self.load_existing_links()
            # Clear form
            self.relationship.setCurrentIndex(0)
            self.evidence.clear()
            self.notes.clear()
            self.confidence.setCurrentIndex(0)
        else:
            QMessageBox.warning(self, "Error", "Link already exists or could not be created.")

    def load_existing_links(self):
        """Load and display existing links for this entity"""
        self.links_list.clear()
        links = self.db.get_entity_links(self.source_type, self.source_id)

        for link in links:
            direction_arrow = "→" if link['link_direction'] == 'outgoing' else "←"
            rel = f" ({link['relationship']})" if link.get('relationship') else ""
            item_text = f"{direction_arrow} {link['linked_name']}{rel}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, link['id'])
            self.links_list.addItem(item)

    def remove_link(self):
        """Remove the selected link"""
        current = self.links_list.currentItem()
        if not current:
            return

        link_id = current.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "Remove Link", "Remove this link?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.db.delete_entity_link(link_id):
                self.load_existing_links()


# ============ EDGE EDIT DIALOG ============

class EdgeEditDialog(QDialog):
    """Dialog for viewing/editing connections (edges) between entities"""

    def __init__(self, parent, db, from_type: str, from_id: str, to_type: str, to_id: str):
        super().__init__(parent)
        self.db = db
        self.from_type = from_type
        self.from_id = from_id
        self.to_type = to_type
        self.to_id = to_id
        self.main_window = parent
        self.link_deleted = False  # Track if a link was deleted
        self.setWindowTitle("Edit Connection")
        self.setMinimumSize(500, 400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header = QLabel("🔗 Connection Details")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #c9a040;")
        layout.addWidget(header)

        # Get display names
        from_name = self.db._get_entity_display_name(self.from_type, self.from_id)
        to_name = self.db._get_entity_display_name(self.to_type, self.to_id)

        # Connection info
        info_group = QGroupBox("Connected Entities")
        info_layout = QFormLayout(info_group)

        from_label = QLabel(f"{from_name}")
        from_label.setStyleSheet("color: #4a9cdb; font-weight: bold;")
        info_layout.addRow(f"From ({self.from_type}):", from_label)

        to_label = QLabel(f"{to_name}")
        to_label.setStyleSheet("color: #4a9cdb; font-weight: bold;")
        info_layout.addRow(f"To ({self.to_type}):", to_label)

        layout.addWidget(info_group)

        # Find existing link info
        self.link_id = None
        self.link_info = self._find_link_info()

        if self.link_info:
            link_group = QGroupBox("Link Information")
            link_layout = QFormLayout(link_group)
            link_layout.addRow("Type:", QLabel(self.link_info.get('type', 'Connection')))
            if self.link_info.get('relationship'):
                link_layout.addRow("Relationship:", QLabel(self.link_info['relationship']))
            if self.link_info.get('notes'):
                notes_lbl = QLabel(self.link_info['notes'])
                notes_lbl.setWordWrap(True)
                link_layout.addRow("Notes:", notes_lbl)
            layout.addWidget(link_group)

        # Actions
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)

        # View buttons
        view_row = QHBoxLayout()
        view_from_btn = QPushButton(f"View {self.from_type.replace('_', ' ').title()}")
        view_from_btn.setStyleSheet("background-color: #4a7c9b;")
        view_from_btn.clicked.connect(self.view_from_entity)
        view_row.addWidget(view_from_btn)

        view_to_btn = QPushButton(f"View {self.to_type.replace('_', ' ').title()}")
        view_to_btn.setStyleSheet("background-color: #4a7c9b;")
        view_to_btn.clicked.connect(self.view_to_entity)
        view_row.addWidget(view_to_btn)
        actions_layout.addLayout(view_row)

        # Add link button (if no universal link exists)
        if not self.link_id:
            add_link_btn = QPushButton("+ Add as Universal Link")
            add_link_btn.setStyleSheet("background-color: #5a8a6a;")
            add_link_btn.clicked.connect(self.add_universal_link)
            actions_layout.addWidget(add_link_btn)

        # Delete link button (if universal link exists)
        if self.link_id:
            delete_btn = QPushButton("🗑️ Delete This Link")
            delete_btn.setStyleSheet("background-color: #8a5a5a;")
            delete_btn.clicked.connect(self.delete_link)
            actions_layout.addWidget(delete_btn)

        layout.addWidget(actions_group)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _find_link_info(self) -> dict:
        """Find info about the link between these entities"""
        # Check entity_links table
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT id, relationship, notes FROM entity_links
            WHERE (source_type = ? AND source_id = ? AND target_type = ? AND target_id = ?)
               OR (source_type = ? AND source_id = ? AND target_type = ? AND target_id = ?)
        """, (self.from_type, self.from_id, self.to_type, self.to_id,
              self.to_type, self.to_id, self.from_type, self.from_id))
        row = cursor.fetchone()
        if row:
            self.link_id = row['id']
            return {'type': 'Universal Link', 'relationship': row['relationship'], 'notes': row['notes']}

        # Return generic info for built-in relationships
        return {'type': 'Built-in Connection'}

    def view_from_entity(self):
        """Open the from entity in the profile panel"""
        self._view_entity(self.from_type, self.from_id)
        self.accept()

    def view_to_entity(self):
        """Open the to entity in the profile panel"""
        self._view_entity(self.to_type, self.to_id)
        self.accept()

    def _view_entity(self, entity_type: str, entity_id: str):
        """View an entity in the main window"""
        if hasattr(self.main_window, 'on_subject_selected') and entity_type == 'subject':
            self.main_window.on_subject_selected(entity_id)
        elif hasattr(self.main_window, 'on_vehicle_selected') and entity_type == 'vehicle':
            self.main_window.on_vehicle_selected(entity_id)
        elif hasattr(self.main_window, 'on_online_account_selected') and entity_type == 'online_account':
            self.main_window.on_online_account_selected(entity_id)
        elif hasattr(self.main_window, 'on_event_selected') and entity_type == 'event':
            self.main_window.on_event_selected(entity_id)
        elif hasattr(self.main_window, 'on_gang_selected') and entity_type == 'gang':
            self.main_window.on_gang_selected(entity_id)
        elif hasattr(self.main_window, 'on_location_selected') and entity_type == 'location':
            self.main_window.on_location_selected(entity_id)
        elif hasattr(self.main_window, 'on_weapon_selected') and entity_type == 'weapon':
            self.main_window.on_weapon_selected(entity_id)
        elif hasattr(self.main_window, 'on_phone_selected') and entity_type == 'phone':
            self.main_window.on_phone_selected(entity_id)
        elif hasattr(self.main_window, 'on_dns_selected') and entity_type == 'dns':
            self.main_window.on_dns_selected(entity_id)
        elif hasattr(self.main_window, 'on_post_selected') and entity_type == 'post':
            self.main_window.on_post_selected(entity_id)

    def add_universal_link(self):
        """Open the universal link dialog to add a link"""
        from_name = self.db._get_entity_display_name(self.from_type, self.from_id)
        dlg = UniversalLinkDialog(self, self.db, self.from_type, self.from_id, from_name)
        dlg.exec()
        self.accept()

    def delete_link(self):
        """Delete the universal link"""
        if not self.link_id:
            QMessageBox.warning(self, "Cannot Delete", "Built-in connections cannot be deleted from here.\nUse the entity's profile to modify relationships.")
            return

        reply = QMessageBox.question(self, "Delete Link",
                                     "Are you sure you want to delete this link?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_entity_link(self.link_id)
            self.link_deleted = True  # Signal that refresh is needed
            self.accept()


# ============ ADD NEW DIALOG ============

class AddNewDialog(QDialog):
    """Unified dialog for selecting which entities to create"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Add New Records")
        self.setMinimumSize(400, 500)
        self.selected_types = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        header = QLabel("Select what to add:")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #c9a040;")
        layout.addWidget(header)

        hint = QLabel("Check all that apply. Dialogs will open in sequence.")
        hint.setStyleSheet("color: #6a6a7a; font-size: 11px;")
        layout.addWidget(hint)

        # Entity checkboxes grouped by category
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        check_layout = QVBoxLayout(container)
        check_layout.setSpacing(10)

        # People & Organizations
        people_group = QGroupBox("People & Organizations")
        people_layout = QVBoxLayout(people_group)
        self.cb_subject = QCheckBox("Subject (Person of Interest)")
        self.cb_gang = QCheckBox("Gang / Organization")
        people_layout.addWidget(self.cb_subject)
        people_layout.addWidget(self.cb_gang)
        check_layout.addWidget(people_group)

        # Events & Locations
        events_group = QGroupBox("Events & Locations")
        events_layout = QVBoxLayout(events_group)
        self.cb_event = QCheckBox("Event / Incident")
        self.cb_location = QCheckBox("Location / Address")
        events_layout.addWidget(self.cb_event)
        events_layout.addWidget(self.cb_location)
        check_layout.addWidget(events_group)

        # Digital / Online
        digital_group = QGroupBox("Digital / Online")
        digital_layout = QVBoxLayout(digital_group)
        self.cb_account = QCheckBox("Online Account (Social Media)")
        self.cb_phone = QCheckBox("Phone Number")
        self.cb_dns = QCheckBox("DNS / Domain Investigation")
        digital_layout.addWidget(self.cb_account)
        digital_layout.addWidget(self.cb_phone)
        digital_layout.addWidget(self.cb_dns)
        check_layout.addWidget(digital_group)

        # Physical Evidence
        physical_group = QGroupBox("Physical Evidence")
        physical_layout = QVBoxLayout(physical_group)
        self.cb_vehicle = QCheckBox("Vehicle")
        self.cb_weapon = QCheckBox("Weapon")
        physical_layout.addWidget(self.cb_vehicle)
        physical_layout.addWidget(self.cb_weapon)
        check_layout.addWidget(physical_group)

        # Intel & Records
        intel_group = QGroupBox("Intel & Records")
        intel_layout = QVBoxLayout(intel_group)
        self.cb_charge = QCheckBox("Charge / Arrest")
        self.cb_graffiti = QCheckBox("Graffiti")
        self.cb_intel = QCheckBox("Intel Report")
        intel_layout.addWidget(self.cb_charge)
        intel_layout.addWidget(self.cb_graffiti)
        intel_layout.addWidget(self.cb_intel)
        check_layout.addWidget(intel_group)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Quick select buttons
        quick_layout = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_all.clicked.connect(self.select_all)
        quick_layout.addWidget(select_all)

        clear_all = QPushButton("Clear All")
        clear_all.clicked.connect(self.clear_all)
        quick_layout.addWidget(clear_all)
        layout.addLayout(quick_layout)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def select_all(self):
        for cb in [self.cb_subject, self.cb_gang, self.cb_event, self.cb_location,
                   self.cb_account, self.cb_phone, self.cb_dns, self.cb_vehicle, self.cb_weapon,
                   self.cb_charge, self.cb_graffiti, self.cb_intel]:
            cb.setChecked(True)

    def clear_all(self):
        for cb in [self.cb_subject, self.cb_gang, self.cb_event, self.cb_location,
                   self.cb_account, self.cb_phone, self.cb_dns, self.cb_vehicle, self.cb_weapon,
                   self.cb_charge, self.cb_graffiti, self.cb_intel]:
            cb.setChecked(False)

    def get_selected_types(self) -> list:
        """Return list of selected entity types in order they should be created"""
        types = []
        # Order matters - create subjects first so they can be linked
        if self.cb_subject.isChecked(): types.append('subject')
        if self.cb_gang.isChecked(): types.append('gang')
        if self.cb_location.isChecked(): types.append('location')
        if self.cb_event.isChecked(): types.append('event')
        if self.cb_account.isChecked(): types.append('online_account')
        if self.cb_phone.isChecked(): types.append('phone')
        if self.cb_dns.isChecked(): types.append('dns')
        if self.cb_vehicle.isChecked(): types.append('vehicle')
        if self.cb_weapon.isChecked(): types.append('weapon')
        if self.cb_charge.isChecked(): types.append('charge')
        if self.cb_graffiti.isChecked(): types.append('graffiti')
        if self.cb_intel.isChecked(): types.append('intel')
        return types


# ============ GRAPH VIEW ============

class GraphBridge(QObject):
    """
    Simple bridge object for JavaScript to Python communication.
    Only exposes the methods needed by the web channel, avoiding
    the warnings from exposing the entire QWebEngineView.
    """
    deleteRequested = pyqtSignal(str, str)  # entity_type, entity_id
    nodeClicked = pyqtSignal(str, str, str)  # entity_type, entity_id, label
    edgeClicked = pyqtSignal(str, str, str, str)  # from_type, from_id, to_type, to_id

    @pyqtSlot(str, str)
    def requestDelete(self, entity_type: str, entity_id: str):
        """Called from JavaScript when user double-clicks to delete"""
        self.deleteRequested.emit(entity_type, entity_id)

    @pyqtSlot(str, str, str)
    def onNodeClicked(self, entity_type: str, entity_id: str, label: str):
        """Called from JavaScript when user single-clicks a node"""
        self.nodeClicked.emit(entity_type, entity_id, label)

    @pyqtSlot(str, str, str, str)
    def onEdgeClicked(self, from_type: str, from_id: str, to_type: str, to_id: str):
        """Called from JavaScript when user clicks an edge"""
        self.edgeClicked.emit(from_type, from_id, to_type, to_id)


class GraphView(QWebEngineView):
    # Signal emitted when user double-clicks a node to delete
    nodeDeleteRequested = pyqtSignal(str, str)  # entity_type, entity_id
    # Signal emitted when user single-clicks a node to show info
    nodeClicked = pyqtSignal(str, str, str)  # entity_type, entity_id, label
    # Signal emitted when user clicks an edge
    edgeClicked = pyqtSignal(str, str, str, str)  # from_type, from_id, to_type, to_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self._ready = False
        self._pending_data = None
        self._bridge = GraphBridge()
        self._bridge.deleteRequested.connect(self.nodeDeleteRequested.emit)
        self._bridge.nodeClicked.connect(self._on_node_clicked)
        self._bridge.edgeClicked.connect(self._on_edge_clicked)
        self._setup_graph_html()

    def _on_node_clicked(self, entity_type, entity_id, label):
        self.nodeClicked.emit(entity_type, entity_id, label)

    def _on_edge_clicked(self, from_type, from_id, to_type, to_id):
        self.edgeClicked.emit(from_type, from_id, to_type, to_id)

    def _setup_graph_html(self):
        """Initialize the graph HTML and JavaScript."""
        # Load vis.js locally - NO INTERNET CONNECTION
        vis_js = ""
        vis_path = os.path.join(os.path.dirname(__file__), 'data', 'vis-network.min.js')
        if os.path.exists(vis_path):
            with open(vis_path, 'r') as f:
                vis_js = f.read()

        # Load qwebchannel.js locally - for Python-JS bridge
        qwebchannel_js = ""
        qwc_path = os.path.join(os.path.dirname(__file__), 'data', 'qwebchannel.js')
        if os.path.exists(qwc_path):
            with open(qwc_path, 'r') as f:
                qwebchannel_js = f.read()

        # Icons: 👤 subject, 👥 gang, 🏠 location, 📅 event, 🚗 vehicle, 🔫 weapon, 🎨 graffiti, ⚖️ charge, 🌐 online_account, 🔍 dns
        # Build HTML with embedded vis.js and qwebchannel.js - NO INTERNET CONNECTION
        html = """<!DOCTYPE html><html><head>
<script>""" + qwebchannel_js + """</script>
<script>""" + vis_js + """</script>
<style>* {margin:0;padding:0;} body {background:#0a0a0f;} #g {width:100vw;height:100vh;}
#tooltip {position:absolute;background:#1a1a24;color:#a0a8b8;padding:8px 12px;border-radius:4px;
border:1px solid #4a7c9b;font-size:12px;display:none;pointer-events:none;z-index:999;}
</style>
</head><body><div id="g"></div><div id="tooltip"></div><script>
var icons = {subject:'👤',gang:'👥',location:'🏠',event:'📋',vehicle:'🚗',weapon:'🔫',graffiti:'🎨',charge:'⚖️',online_account:'🌐',dns:'🔍',phone:'📱',post:'📝'};
var n=new vis.DataSet([]),e=new vis.DataSet([]);
var net=new vis.Network(document.getElementById('g'),{nodes:n,edges:e},{
nodes:{shape:'ellipse',size:35,font:{color:'#e0e0e8',size:28,face:'Arial'},borderWidth:3,shadow:true,widthConstraint:{minimum:50},heightConstraint:{minimum:50}},
edges:{width:2,color:{color:'#3a3a4a',highlight:'#c9a040'},smooth:{enabled:true,type:'dynamic',roundness:0.5}},
physics:{barnesHut:{gravitationalConstant:-8000,centralGravity:0.3,springLength:350,springConstant:0.04,damping:0.6,avoidOverlap:1.0},solver:'barnesHut',stabilization:{iterations:800,fit:true},timestep:0.3,maxVelocity:25,minVelocity:0.5},
interaction:{hover:true,tooltipDelay:200},
groups:{
subject:{color:{background:'#4a7c9b',border:'#5a8cab',highlight:{background:'#5a9cbf',border:'#7abcdf'}}},
gang:{color:{background:'#8a5a5a',border:'#9a6a6a',highlight:{background:'#aa7a7a',border:'#ca9a9a'}}},
location:{color:{background:'#c9a040',border:'#d9b050',highlight:{background:'#e9c060',border:'#f9d080'}}},
event:{color:{background:'#5a8a6a',border:'#6a9a7a',highlight:{background:'#7aaa8a',border:'#9aca9a'}}},
vehicle:{color:{background:'#6b5b8a',border:'#7b6b9a',highlight:{background:'#8b7baa',border:'#ab9bca'}}},
weapon:{color:{background:'#9a6a4a',border:'#aa7a5a',highlight:{background:'#ba8a6a',border:'#daaa8a'}}},
graffiti:{color:{background:'#4a8a9a',border:'#5a9aaa',highlight:{background:'#6aaaba',border:'#8acada'}}},
charge:{color:{background:'#7a5a7a',border:'#8a6a8a',highlight:{background:'#9a7a9a',border:'#ba9aba'}}},
online_account:{color:{background:'#3a9a8a',border:'#4aaaa0',highlight:{background:'#5abab0',border:'#7adad0'}}},
dns:{color:{background:'#8a4a9a',border:'#9a5aaa',highlight:{background:'#aa6aba',border:'#ca8ada'}}},
phone:{color:{background:'#4a7a9a',border:'#5a8aaa',highlight:{background:'#6a9aba',border:'#8abada'}}},
post:{color:{background:'#5a8a6a',border:'#6a9a7a',highlight:{background:'#7aaa8a',border:'#9aca9a'}}}
}
});
net.on('stabilizationIterationsDone',function(){net.setOptions({physics:false});});
net.on('dragStart',function(){net.setOptions({physics:{enabled:true,barnesHut:{gravitationalConstant:-8000,centralGravity:0.3,springLength:350,springConstant:0.04,damping:0.6,avoidOverlap:1.0},solver:'barnesHut',timestep:0.3,maxVelocity:25,minVelocity:0.5}});});
net.on('dragEnd',function(){setTimeout(function(){net.setOptions({physics:false});},2000);});
var tooltip=document.getElementById('tooltip');
net.on('hoverNode',function(p){
var node=n.get(p.node);
var type;
var multiWordTypes=['online_account'];
for(var i=0;i<multiWordTypes.length;i++){
if(p.node.startsWith(multiWordTypes[i]+'_')){type=multiWordTypes[i];break;}
}
if(!type){type=p.node.split('_')[0];}
tooltip.innerHTML='<b>'+node.title+'</b><br><small style="color:#6b5b8a">'+type.toUpperCase().replace('_',' ')+'</small><br><small>Double-click to delete</small>';
tooltip.style.display='block';
});
net.on('blurNode',function(){tooltip.style.display='none';});
document.addEventListener('mousemove',function(e){
tooltip.style.left=(e.pageX+15)+'px';
tooltip.style.top=(e.pageY+15)+'px';
});
net.on('click',function(p){
if(p.nodes.length>0){
var nodeId=p.nodes[0];
var node=n.get(nodeId);
var type,id;
var multiWordTypes=['online_account'];
for(var i=0;i<multiWordTypes.length;i++){
if(nodeId.startsWith(multiWordTypes[i]+'_')){
type=multiWordTypes[i];
id=nodeId.substring(type.length+1);
break;
}
}
if(!type){
var parts=nodeId.split('_');
type=parts[0];
id=parts.slice(1).join('_');
}
window.pyNodeClicked(type,id,node.title||'');
}
});
net.on('doubleClick',function(p){
if(p.nodes.length>0){
var nodeId=p.nodes[0];
var type,id;
var multiWordTypes=['online_account'];
for(var i=0;i<multiWordTypes.length;i++){
if(nodeId.startsWith(multiWordTypes[i]+'_')){
type=multiWordTypes[i];
id=nodeId.substring(type.length+1);
break;
}
}
if(!type){
var parts=nodeId.split('_');
type=parts[0];
id=parts.slice(1).join('_');
}
if(confirm('Delete this '+type.replace('_',' ')+'?')){
window.pyDeleteNode(type,id);
}
}
});
var edgeIdCounter=0;
var edgeData={};
function updateGraph(d){n.clear();e.clear();edgeData={};edgeIdCounter=0;
d.nodes.forEach(x=>{
var icon=icons[x.type]||'●';
var nodeOpts={id:x.id,group:x.type,title:x.label};
if(x.x!==undefined&&x.y!==undefined){
nodeOpts.x=x.x;
nodeOpts.y=x.y;
}
if(x.photo){
nodeOpts.shape='circularImage';
nodeOpts.image=x.photo;
var displayLabel=x.label.length>18?x.label.substring(0,18)+'...':x.label;
nodeOpts.label=displayLabel;
nodeOpts.font={size:14,color:'#e0e8f0',vadjust:8,strokeWidth:3,strokeColor:'#0a0a0f'};
nodeOpts.size=32;
nodeOpts.borderWidth=3;
}else{
nodeOpts.label=icon+'\\n'+x.label.substring(0,12);
nodeOpts.font={size:11,color:'#c0c8d8',multi:'html'};
}
n.add(nodeOpts);
});
d.edges.forEach(x=>{
var eid='edge_'+edgeIdCounter++;
edgeData[eid]={from:x.from,to:x.to,type:x.type||'link'};
e.add({id:eid,from:x.from,to:x.to});
});
net.setOptions({physics:{enabled:true}});
net.stabilize(500);
net.fit();
}
net.on('selectEdge',function(p){
if(p.edges.length>0){
var eid=p.edges[0];
var ed=edgeData[eid];
if(ed){
var fromParts=parseNodeId(ed.from);
var toParts=parseNodeId(ed.to);
window.pyEdgeClicked(fromParts.type,fromParts.id,toParts.type,toParts.id);
}
}
});
function parseNodeId(nodeId){
var multiWordTypes=['online_account'];
for(var i=0;i<multiWordTypes.length;i++){
if(nodeId.startsWith(multiWordTypes[i]+'_')){
return{type:multiWordTypes[i],id:nodeId.substring(multiWordTypes[i].length+1)};
}
}
var parts=nodeId.split('_');
return{type:parts[0],id:parts.slice(1).join('_')};
}
function focusNode(id){net.focus(id,{scale:1.5,animation:true});net.selectNodes([id]);}
</script></body></html>"""

        # Set up JS to Python bridge BEFORE loading HTML
        from PyQt6.QtWebChannel import QWebChannel
        self.channel = QWebChannel()
        self.channel.registerObject('backend', self._bridge)
        self.page().setWebChannel(self.channel)

        self.setHtml(html)
        self.loadFinished.connect(self._on_load_finished)

    def _on_load_finished(self, ok):
        if ok:
            # Inject the webchannel bridge
            self.page().runJavaScript("""
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    window.pyDeleteNode = function(type, id) {
                        channel.objects.backend.requestDelete(type, id);
                    };
                    window.pyNodeClicked = function(type, id, label) {
                        channel.objects.backend.onNodeClicked(type, id, label);
                    };
                    window.pyEdgeClicked = function(fromType, fromId, toType, toId) {
                        channel.objects.backend.onEdgeClicked(fromType, fromId, toType, toId);
                    };
                });
            """)
            self._ready = True
            if self._pending_data:
                self.page().runJavaScript(f"updateGraph({json.dumps(self._pending_data)});")
                self._pending_data = None

    def update_graph(self, data):
        # RUNTIME BASE64 ENCODING - NOT HARDCODED DATA
        # WebEngine security prevents direct file:// access to local images.
        # Photos must be converted to data URLs at runtime for display.
        # This reads the user's photo files and encodes them for the graph.
        # Alternative would require running a local HTTP server - overkill.
        import base64
        for node in data.get('nodes', []):
            if node.get('photo'):
                # Convert relative path to absolute for file access
                photo_path = to_absolute_path(node['photo'])
                if photo_path and os.path.exists(photo_path):
                    try:
                        with open(photo_path, 'rb') as f:
                            img_data = f.read()
                        # Detect image type
                        ext = photo_path.lower().split('.')[-1]
                        mime = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'gif': 'gif', 'bmp': 'bmp'}.get(ext, 'png')
                        b64 = base64.b64encode(img_data).decode('utf-8')
                        node['photo'] = f"data:image/{mime};base64,{b64}"
                    except Exception:
                        del node['photo']  # Remove if can't load
                else:
                    del node['photo']  # Remove if file doesn't exist

        if self._ready:
            self.page().runJavaScript(f"updateGraph({json.dumps(data)});")
        else:
            self._pending_data = data

    def focus_node(self, node_id):
        if self._ready:
            self.page().runJavaScript(f"focusNode('{node_id}');")


# ============ PROFILE PANEL ============

class ProfilePanel(QWidget):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.main_window = parent  # Store direct reference to MainWindow
        self.current_type = None
        self.current_id = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.header = QLabel("Select an item")
        self.header.setStyleSheet("font-size: 18px; font-weight: bold; color: #4a7c9b;")
        layout.addWidget(self.header)

        # Scrollable content area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 5, 0, 5)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.content)
        layout.addWidget(self.scroll_area, 1)  # Give scroll area stretch priority

        # Entity-specific action buttons (fixed, above edit/delete)
        self.action_btns_widget = QWidget()
        self.action_btns_layout = QHBoxLayout(self.action_btns_widget)
        self.action_btns_layout.setContentsMargins(0, 5, 0, 0)
        self.action_btns_widget.hide()  # Hidden by default
        layout.addWidget(self.action_btns_widget)

        # Buttons at bottom (fixed, don't scroll)
        btns = QHBoxLayout()
        btns.setContentsMargins(0, 5, 0, 0)
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self.edit_current)
        self.edit_btn.setEnabled(False)
        btns.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet("background-color: #8a5a5a;")
        self.delete_btn.clicked.connect(self.delete_current)
        self.delete_btn.setEnabled(False)
        btns.addWidget(self.delete_btn)

        self.link_btn = QPushButton("+ Link")
        self.link_btn.setStyleSheet("background-color: #3a9a8a;")
        self.link_btn.clicked.connect(self.open_link_dialog)
        self.link_btn.setEnabled(False)
        btns.addWidget(self.link_btn)

        layout.addLayout(btns)

    def open_link_dialog(self):
        """Open the universal link dialog for the current entity"""
        if not self.current_type or not self.current_id:
            return

        # Get display name for the current entity
        name = self.db._get_entity_display_name(self.current_type, self.current_id)

        dialog = UniversalLinkDialog(self, self.db, self.current_type, self.current_id, name)
        dialog.exec()

        # Refresh the current profile to show new links
        self.refresh_current()

        # Refresh the graph to show new/removed edges
        main_win = self.parent()
        while main_win and not isinstance(main_win, MainWindow):
            main_win = main_win.parent()
        if main_win:
            main_win.refresh_graph(self.current_type, self.current_id)

    def refresh_current(self):
        """Refresh the current entity display"""
        if not self.current_type or not self.current_id:
            return

        if self.current_type == 'subject':
            self.show_subject(self.current_id)
        elif self.current_type == 'gang':
            self.show_gang(self.current_id)
        elif self.current_type == 'location':
            self.show_location(self.current_id)
        elif self.current_type == 'event':
            self.show_event(self.current_id)
        elif self.current_type == 'vehicle':
            self.show_vehicle(self.current_id)
        elif self.current_type == 'weapon':
            self.show_weapon(self.current_id)
        elif self.current_type == 'graffiti':
            self.show_graffiti(self.current_id)
        elif self.current_type == 'charge':
            self.show_charge(self.current_id)
        elif self.current_type == 'online_account':
            self.show_online_account(self.current_id)
        elif self.current_type == 'dns':
            self.show_dns_investigation(self.current_id)
        elif self.current_type == 'phone':
            self.show_tracked_phone(self.current_id)
        elif self.current_type == 'post':
            self.show_post(self.current_id)

    def _edit_gang_role(self, subject_id, gang_id, current_role):
        """Edit a member's role in a gang/organization"""
        roles = ["Leader", "Co-Leader", "Lieutenant", "Enforcer", "Member",
                 "Associate", "Recruit", "Informant", "Former Member", "Prospect"]
        role, ok = QInputDialog.getItem(self, "Edit Role", "Select role:",
                                         roles, roles.index(current_role) if current_role in roles else 4, True)
        if ok and role:
            self.db.update_subject_gang_role(subject_id, gang_id, role)
            self.show_gang(gang_id)  # Refresh

    def show_universal_links(self, entity_type: str, entity_id: str):
        """Show universal links for any entity - call this from show_* methods"""
        links = self.db.get_entity_links(entity_type, entity_id)
        if not links:
            return

        links_grp = QGroupBox(f"Linked Entities ({len(links)})")
        links_l = QVBoxLayout(links_grp)

        for link in links:
            direction_arrow = "→" if link['link_direction'] == 'outgoing' else "←"
            rel = f" ({link['relationship']})" if link.get('relationship') else ""
            conf = f" [{link['confidence']}]" if link.get('confidence') and link['confidence'] != 'Medium' else ""

            link_text = f"{direction_arrow} {link['linked_name']}{rel}{conf}"
            lbl = QLabel(link_text)
            lbl.setStyleSheet("color: #8a9a8a;")
            links_l.addWidget(lbl)

        self.content_layout.addWidget(links_grp)

    def clear(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Also clear entity-specific action buttons
        while self.action_btns_layout.count():
            item = self.action_btns_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.action_btns_widget.hide()

    def show_subject(self, subject_id):
        self.current_type = 'subject'
        self.current_id = subject_id
        p = self.db.get_subject_full_profile(subject_id)
        if not p:
            return

        self.clear()
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.link_btn.setEnabled(True)

        self.header.setText(f"{p['first_name']} {p['last_name']}")

        # Profile photo (clickable to expand)
        if p.get('profile_photo') and os.path.exists(p['profile_photo']):
            photo_label = ClickablePhotoLabel(p['profile_photo'], 100, 100)
            self.content_layout.addWidget(photo_label)

        # PII
        pii = QGroupBox("Subject Information")
        pii_l = QFormLayout(pii)
        pii_l.addRow("DOB:", QLabel(p.get('dob') or '-'))
        pii_l.addRow("Monikers:", QLabel(p.get('monikers') or '-'))
        self.content_layout.addWidget(pii)

        # Government Identifiers (SSN, OLN, State ID, RISSAFE, etc.)
        # Combine legacy SSN/OLN fields with state_ids table entries
        all_ids = list(p.get('state_ids', []))
        # Add legacy SSN if not already in state_ids
        if p.get('ssn'):
            has_ssn = any(s['id_type'] == 'SSN' and s['id_number'] == p['ssn'] for s in all_ids)
            if not has_ssn:
                all_ids.insert(0, {'id_type': 'SSN', 'id_number': p['ssn'], 'state': ''})
        if p.get('oln'):
            has_oln = any(s['id_type'] == 'OLN' and s['id_number'] == p['oln'] for s in all_ids)
            if not has_oln:
                all_ids.insert(0, {'id_type': 'OLN', 'id_number': p['oln'], 'state': ''})
        if all_ids:
            ids_grp = QGroupBox(f"Government Identifiers ({len(all_ids)})")
            ids_l = QVBoxLayout(ids_grp)
            for sid in all_ids:
                state_str = f" ({sid['state']})" if sid.get('state') else ""
                ids_l.addWidget(QLabel(f"- {sid['id_type']}: {sid['id_number']}{state_str}"))
            self.content_layout.addWidget(ids_grp)

        # Physical Descriptors
        phys_parts = []
        if p.get('sex'): phys_parts.append(f"Sex: {p['sex']}")
        if p.get('race'): phys_parts.append(f"Race: {p['race']}")
        if p.get('height'): phys_parts.append(f"Ht: {p['height']}")
        if p.get('weight'): phys_parts.append(f"Wt: {p['weight']}")
        if p.get('build'): phys_parts.append(f"Build: {p['build']}")
        if p.get('hair_color'): phys_parts.append(f"Hair: {p['hair_color']}")
        if p.get('eye_color'): phys_parts.append(f"Eyes: {p['eye_color']}")
        if phys_parts:
            phys = QGroupBox("Physical Description")
            phys_l = QVBoxLayout(phys)
            phys_l.addWidget(QLabel(" | ".join(phys_parts)))
            self.content_layout.addWidget(phys)

        # MO/History
        if p.get('mo') or p.get('criminal_history'):
            intel = QGroupBox("Intelligence")
            intel_l = QVBoxLayout(intel)
            if p.get('mo'):
                lbl = QLabel(f"MO: {p['mo']}")
                lbl.setWordWrap(True)
                intel_l.addWidget(lbl)
            if p.get('criminal_history'):
                lbl = QLabel(f"History: {p['criminal_history']}")
                lbl.setWordWrap(True)
                intel_l.addWidget(lbl)
            self.content_layout.addWidget(intel)

        # Contact info
        if p.get('phone_numbers') or p.get('emails') or p.get('social_profiles'):
            contact = QGroupBox("Contact Info")
            contact_l = QVBoxLayout(contact)
            for ph in p.get('phone_numbers', []):
                contact_l.addWidget(QLabel(f"Phone ({ph['phone_type']}): {ph['number']}"))
            for em in p.get('emails', []):
                contact_l.addWidget(QLabel(f"Email ({em['email_type']}): {em['email']}"))
            for soc in p.get('social_profiles', []):
                contact_l.addWidget(QLabel(f"{soc['platform']}: {soc['url']}"))
            self.content_layout.addWidget(contact)

        # Gangs
        if p.get('gangs'):
            gangs = QGroupBox(f"Gang/Organization ({len(p['gangs'])})")
            g_l = QVBoxLayout(gangs)
            for g in p['gangs']:
                g_l.addWidget(QLabel(f"• {g['name']} ({g.get('role', 'Member')})"))
            self.content_layout.addWidget(gangs)

        # Locations
        if p.get('locations'):
            locs = QGroupBox(f"Locations ({len(p['locations'])})")
            l_l = QVBoxLayout(locs)
            for loc in p['locations']:
                rel = loc.get('relationship', '')
                tag = f"[{rel}] " if rel else ("[Residence] " if loc.get('is_primary_residence') else "")
                l_l.addWidget(QLabel(f"- {tag}{loc['address']}"))
            self.content_layout.addWidget(locs)

        # Family
        if p.get('family'):
            fam = QGroupBox(f"Family ({len(p['family'])})")
            f_l = QVBoxLayout(fam)
            for f in p['family']:
                name = f.get('family_name') or f"{f.get('member_first', '')} {f.get('member_last', '')}".strip()
                f_l.addWidget(QLabel(f"• {f['relationship']}: {name}"))
            self.content_layout.addWidget(fam)

        # Events
        if p.get('events'):
            events = QGroupBox(f"Events ({len(p['events'])})")
            e_l = QVBoxLayout(events)
            for e in p['events']:
                e_l.addWidget(QLabel(f"• {e['event_number']} - {e['event_date']}"))
            self.content_layout.addWidget(events)

        # Associates
        if p.get('associates'):
            assoc = QGroupBox(f"Associates ({len(p['associates'])})")
            a_l = QVBoxLayout(assoc)
            for a in p['associates']:
                a_l.addWidget(QLabel(f"• {a['first_name']} {a['last_name']}"))
            self.content_layout.addWidget(assoc)

        # Tattoos
        if p.get('tattoos'):
            tattoos = QGroupBox(f"Tattoos ({len(p['tattoos'])})")
            t_l = QVBoxLayout(tattoos)
            for t in p['tattoos']:
                gang_marker = " [GANG]" if t.get('is_gang_affiliated') else ""
                t_l.addWidget(QLabel(f"• {t['body_location']}: {t['description']}{gang_marker}"))
            self.content_layout.addWidget(tattoos)

        # Vehicles
        if p.get('vehicles'):
            vehicles = QGroupBox(f"Vehicles ({len(p['vehicles'])})")
            v_l = QVBoxLayout(vehicles)
            for v in p['vehicles']:
                v_l.addWidget(QLabel(f"• {v['year']} {v['color']} {v['make']} {v['model']} - {v['plate']} ({v.get('relationship', '')})"))
            self.content_layout.addWidget(vehicles)

        # Weapons
        if p.get('weapons'):
            weapons = QGroupBox(f"Weapons ({len(p['weapons'])})")
            w_l = QVBoxLayout(weapons)
            for w in p['weapons']:
                serial = f" S/N: {w['serial_number']}" if w.get('serial_number') else ""
                w_l.addWidget(QLabel(f"• {w['weapon_type']} {w['make']} {w['model']} {w['caliber']}{serial}"))
            self.content_layout.addWidget(weapons)

        # Charges
        if p.get('charges'):
            charges = QGroupBox(f"Charges ({len(p['charges'])})")
            c_l = QVBoxLayout(charges)
            for c in p['charges']:
                c_l.addWidget(QLabel(f"• {c['charge_date']}: {c['charges_text']}"))
                if c.get('court_case_number'):
                    c_l.addWidget(QLabel(f"  Case #: {c['court_case_number']}"))
            self.content_layout.addWidget(charges)

        # Employment
        if p.get('employment'):
            emp_grp = QGroupBox(f"Employment ({len(p['employment'])})")
            emp_l = QVBoxLayout(emp_grp)
            for emp in p['employment']:
                pos = f" - {emp['position']}" if emp.get('position') else ""
                emp_l.addWidget(QLabel(f"- {emp['employer']}{pos}"))
                if emp.get('address'):
                    emp_l.addWidget(QLabel(f"  {emp['address']}"))
            self.content_layout.addWidget(emp_grp)

        # Court Cases
        if p.get('case_numbers'):
            cases = QGroupBox(f"Court Cases ({len(p['case_numbers'])})")
            cn_l = QVBoxLayout(cases)
            for cn in p['case_numbers']:
                cn_l.addWidget(QLabel(f"- {cn['case_number']} ({cn['case_type']}) - {cn['status']}"))
            self.content_layout.addWidget(cases)

        # Notes
        if p.get('notes'):
            notes_grp = QGroupBox("Notes")
            notes_l = QVBoxLayout(notes_grp)
            lbl = QLabel(p['notes'])
            lbl.setWordWrap(True)
            notes_l.addWidget(lbl)
            self.content_layout.addWidget(notes_grp)

        # Universal Links (spider web)
        self.show_universal_links('subject', subject_id)

    def show_gang(self, gang_id):
        self.current_type = 'gang'
        self.current_id = gang_id
        p = self.db.get_gang_full_profile(gang_id)
        if not p:
            return

        self.clear()
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.link_btn.setEnabled(True)
        self.header.setText(p['name'])

        # Photo
        photo_path = self.db.get_entity_first_photo('gang', gang_id)
        if photo_path and os.path.exists(photo_path):
            photo_label = ClickablePhotoLabel(photo_path, 100, 100)
            self.content_layout.addWidget(photo_label)

        info = QGroupBox("Gang/Organization Information")
        info_l = QFormLayout(info)
        info_l.addRow("Territory:", QLabel(p.get('territory') or '-'))
        if p.get('details'):
            lbl = QLabel(p['details'])
            lbl.setWordWrap(True)
            info_l.addRow("Details:", lbl)
        if p.get('history'):
            lbl = QLabel(p['history'])
            lbl.setWordWrap(True)
            info_l.addRow("History:", lbl)
        if p.get('identifiers'):
            lbl = QLabel(p['identifiers'])
            lbl.setWordWrap(True)
            info_l.addRow("Identifiers:", lbl)
        if p.get('notes'):
            lbl = QLabel(p['notes'])
            lbl.setWordWrap(True)
            info_l.addRow("Notes:", lbl)
        self.content_layout.addWidget(info)

        if p.get('members'):
            members = QGroupBox(f"Members ({len(p['members'])})")
            m_l = QVBoxLayout(members)
            for m in p['members']:
                role = m.get('role') or 'Member'
                btn = QPushButton(f"• {m['first_name']} {m['last_name']} ({role})")
                btn.setStyleSheet("text-align: left; background: transparent; border: none; color: #c0c0c0; padding: 2px;")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                member_id = m['id']
                btn.clicked.connect(lambda checked, sid=member_id, gid=gang_id, r=role: self._edit_gang_role(sid, gid, r))
                m_l.addWidget(btn)
            self.content_layout.addWidget(members)

        if p.get('events'):
            events = QGroupBox(f"Events ({len(p['events'])})")
            e_l = QVBoxLayout(events)
            for e in p['events']:
                e_l.addWidget(QLabel(f"• {e['event_number']} - {e['event_date']}"))
            self.content_layout.addWidget(events)

        # Universal Links
        self.show_universal_links('gang', gang_id)

    def show_location(self, location_id):
        self.current_type = 'location'
        self.current_id = location_id
        p = self.db.get_location_full_profile(location_id)
        if not p:
            return

        self.clear()
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.link_btn.setEnabled(True)
        self.header.setText(p['address'][:40])

        info = QGroupBox("Location")
        info_l = QFormLayout(info)
        info_l.addRow("Address:", QLabel(p['address']))
        info_l.addRow("Type:", QLabel(p.get('type') or '-'))
        if p.get('description'):
            lbl = QLabel(p['description'])
            lbl.setWordWrap(True)
            info_l.addRow("Description:", lbl)
        if p.get('notes'):
            lbl = QLabel(p['notes'])
            lbl.setWordWrap(True)
            info_l.addRow("Notes:", lbl)
        self.content_layout.addWidget(info)

        if p.get('subjects'):
            subjs = QGroupBox(f"Subjects ({len(p['subjects'])})")
            s_l = QVBoxLayout(subjs)
            for s in p['subjects']:
                prefix = "[RESIDENT] " if s.get('is_primary_residence') else ""
                s_l.addWidget(QLabel(f"• {prefix}{s['first_name']} {s['last_name']}"))
            self.content_layout.addWidget(subjs)

        if p.get('gangs'):
            gangs = QGroupBox(f"Gangs ({len(p['gangs'])})")
            g_l = QVBoxLayout(gangs)
            for g in p['gangs']:
                g_l.addWidget(QLabel(f"• {g['name']}"))
            self.content_layout.addWidget(gangs)

        # Universal Links
        self.show_universal_links('location', location_id)

    def show_event(self, event_id):
        self.current_type = 'event'
        self.current_id = event_id
        p = self.db.get_event_full_details(event_id)
        if not p:
            return

        self.clear()
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.link_btn.setEnabled(True)
        self.header.setText(f"Event: {p['event_number']}")

        info = QGroupBox("Event Details")
        info_l = QFormLayout(info)
        info_l.addRow("Event #:", QLabel(p['event_number']))
        info_l.addRow("Date:", QLabel(p.get('event_date') or '-'))
        info_l.addRow("Type:", QLabel(p.get('event_type') or '-'))
        info_l.addRow("Location:", QLabel(p.get('location_text') or '-'))
        if p.get('generated_source'):
            info_l.addRow("Source:", QLabel(p['generated_source']))
        if p.get('code_400'):
            info_l.addRow("400 Code:", QLabel(p['code_400']))
        if p.get('details'):
            lbl = QLabel(p['details'])
            lbl.setWordWrap(True)
            info_l.addRow("Details:", lbl)
        if p.get('case_notes'):
            lbl = QLabel(p['case_notes'])
            lbl.setWordWrap(True)
            info_l.addRow("Notes:", lbl)
        self.content_layout.addWidget(info)

        if p.get('subjects'):
            subjs = QGroupBox(f"Subjects ({len(p['subjects'])})")
            s_l = QVBoxLayout(subjs)
            for s in p['subjects']:
                s_l.addWidget(QLabel(f"• {s['first_name']} {s['last_name']} ({s.get('event_role', '')})"))
            self.content_layout.addWidget(subjs)

        if p.get('weapons'):
            weapons = QGroupBox(f"Weapons ({len(p['weapons'])})")
            w_l = QVBoxLayout(weapons)
            for w in p['weapons']:
                w_l.addWidget(QLabel(f"• {w['weapon_type']} {w['make']} {w['model']} {w['caliber']}"))
            self.content_layout.addWidget(weapons)

        if p.get('vehicles'):
            vehicles = QGroupBox(f"Vehicles ({len(p['vehicles'])})")
            v_l = QVBoxLayout(vehicles)
            for v in p['vehicles']:
                v_l.addWidget(QLabel(f"• {v['plate']} - {v['year']} {v['color']} {v['make']} {v['model']}"))
            self.content_layout.addWidget(vehicles)

        if p.get('evidence'):
            evidence = QGroupBox(f"Evidence ({len(p['evidence'])})")
            e_l = QVBoxLayout(evidence)
            for ev in p['evidence']:
                e_l.addWidget(QLabel(f"• [{ev['evidence_type']}] {ev['description']} - {ev['disposition']}"))
            self.content_layout.addWidget(evidence)

        # Universal Links
        self.show_universal_links('event', event_id)

    def show_charge(self, charge_id):
        self.current_type = 'charge'
        self.current_id = charge_id
        c = self.db.get_charge(charge_id)
        if not c:
            return

        self.clear()
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.link_btn.setEnabled(True)
        self.header.setText(f"Charge: {c['charges_text'][:30]}")

        info = QGroupBox("Charge Details")
        info_l = QFormLayout(info)
        info_l.addRow("Charges:", QLabel(c['charges_text']))
        info_l.addRow("Date:", QLabel(c.get('charge_date') or '-'))
        info_l.addRow("Location:", QLabel(c.get('location_text') or '-'))
        info_l.addRow("Court Case #:", QLabel(c.get('court_case_number') or '-'))
        if c.get('court_url'):
            url_lbl = QLabel(f"<a href='{c['court_url']}'>{c['court_url'][:40]}</a>")
            url_lbl.setOpenExternalLinks(True)
            info_l.addRow("Court URL:", url_lbl)
        if c.get('details'):
            lbl = QLabel(c['details'])
            lbl.setWordWrap(True)
            info_l.addRow("Details:", lbl)
        if c.get('notes'):
            lbl = QLabel(c['notes'])
            lbl.setWordWrap(True)
            info_l.addRow("Notes:", lbl)
        self.content_layout.addWidget(info)

        # Arrestee
        if c.get('subject_id'):
            subj = self.db.get_subject(c['subject_id'])
            if subj:
                arr = QGroupBox("Arrestee")
                arr_l = QVBoxLayout(arr)
                arr_l.addWidget(QLabel(f"{subj['first_name']} {subj['last_name']}"))
                self.content_layout.addWidget(arr)

        # Affiliates
        affiliates = self.db.get_charge_affiliates(charge_id)
        if affiliates:
            aff = QGroupBox(f"Affiliates ({len(affiliates)})")
            aff_l = QVBoxLayout(aff)
            for a in affiliates:
                aff_l.addWidget(QLabel(f"• {a['first_name']} {a['last_name']} ({a['role']})"))
            self.content_layout.addWidget(aff)

    def show_graffiti(self, graffiti_id):
        self.current_type = 'graffiti'
        self.current_id = graffiti_id
        g = self.db.get_graffiti(graffiti_id)
        if not g:
            return

        self.clear()
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.link_btn.setEnabled(True)
        self.header.setText("Graffiti")

        info = QGroupBox("Graffiti Details")
        info_l = QFormLayout(info)
        info_l.addRow("Location:", QLabel(g.get('location_text') or '-'))
        info_l.addRow("Date:", QLabel(g.get('date_observed') or '-'))
        info_l.addRow("Sector/Beat:", QLabel(g.get('sector_beat') or '-'))
        info_l.addRow("Area Command:", QLabel(g.get('area_command') or '-'))
        if g.get('tags'):
            lbl = QLabel(g['tags'])
            lbl.setWordWrap(True)
            info_l.addRow("Tags:", lbl)
        if g.get('monikers'):
            info_l.addRow("Monikers:", QLabel(g['monikers']))
        if g.get('notes'):
            lbl = QLabel(g['notes'])
            lbl.setWordWrap(True)
            info_l.addRow("Notes:", lbl)
        self.content_layout.addWidget(info)

        # Gang
        if g.get('gang_id'):
            gang = self.db.get_gang(g['gang_id'])
            if gang:
                gang_grp = QGroupBox("Gang")
                gang_l = QVBoxLayout(gang_grp)
                gang_l.addWidget(QLabel(gang['name']))
                self.content_layout.addWidget(gang_grp)

    def show_intel(self, intel_id):
        self.current_type = 'intel'
        self.current_id = intel_id
        i = self.db.get_intel_report(intel_id)
        if not i:
            return

        self.clear()
        self.edit_btn.setEnabled(False)
        self.delete_btn.setEnabled(True)
        self.header.setText("Intel Report")

        info = QGroupBox("Report Details")
        info_l = QFormLayout(info)
        info_l.addRow("Date:", QLabel(i.get('report_date') or '-'))
        info_l.addRow("Source:", QLabel(i.get('source_type') or '-'))
        info_l.addRow("Reliability:", QLabel(i.get('reliability') or '-'))
        if i.get('details'):
            lbl = QLabel(i['details'])
            lbl.setWordWrap(True)
            info_l.addRow("Details:", lbl)
        self.content_layout.addWidget(info)

        # Links
        links = []
        if i.get('subject_id'):
            subj = self.db.get_subject(i['subject_id'])
            if subj:
                links.append(f"Subject: {subj['first_name']} {subj['last_name']}")
        if i.get('gang_id'):
            gang = self.db.get_gang(i['gang_id'])
            if gang:
                links.append(f"Gang: {gang['name']}")
        if i.get('location_id'):
            loc = self.db.get_location(i['location_id'])
            if loc:
                links.append(f"Location: {loc['address'][:30]}")
        if i.get('event_id'):
            ev = self.db.get_event(i['event_id'])
            if ev:
                links.append(f"Event: {ev['event_number']}")

        if links:
            link_grp = QGroupBox("Linked To")
            link_l = QVBoxLayout(link_grp)
            for link in links:
                link_l.addWidget(QLabel(f"• {link}"))
            self.content_layout.addWidget(link_grp)

    def show_vehicle(self, vehicle_id):
        self.current_type = 'vehicle'
        self.current_id = vehicle_id
        v = self.db.get_vehicle(vehicle_id)
        if not v:
            return

        self.clear()
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.link_btn.setEnabled(True)
        self.header.setText(f"Vehicle: {v['plate']}")

        info = QGroupBox("Vehicle Details")
        info_l = QFormLayout(info)
        info_l.addRow("Plate:", QLabel(f"{v['plate']} ({v['state']})"))
        info_l.addRow("Year:", QLabel(v.get('year') or '-'))
        info_l.addRow("Make:", QLabel(v.get('make') or '-'))
        info_l.addRow("Model:", QLabel(v.get('model') or '-'))
        info_l.addRow("Color:", QLabel(v.get('color') or '-'))
        info_l.addRow("VIN:", QLabel(v.get('vin') or '-'))
        if v.get('notes'):
            lbl = QLabel(v['notes'])
            lbl.setWordWrap(True)
            info_l.addRow("Notes:", lbl)
        self.content_layout.addWidget(info)

        # Find linked subjects
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT s.*, sv.relationship
            FROM subjects s
            JOIN subject_vehicles sv ON s.id = sv.subject_id
            WHERE sv.vehicle_id = ?
        """, (vehicle_id,))
        subjects = [dict(row) for row in cursor.fetchall()]

        if subjects:
            subj_grp = QGroupBox(f"Associated Subjects ({len(subjects)})")
            subj_l = QVBoxLayout(subj_grp)
            for s in subjects:
                subj_l.addWidget(QLabel(f"• {s['first_name']} {s['last_name']} ({s['relationship']})"))
            self.content_layout.addWidget(subj_grp)

        # Find linked online accounts
        accounts = self.db.get_vehicle_accounts(vehicle_id)
        if accounts:
            acct_grp = QGroupBox(f"Linked Accounts ({len(accounts)})")
            acct_l = QVBoxLayout(acct_grp)
            for a in accounts:
                display = f"@{a['username']}" if a.get('username') else a.get('platform', 'Unknown')
                rel = f" - {a['relationship']}" if a.get('relationship') else ""
                acct_l.addWidget(QLabel(f"• {a.get('platform', '')}: {display}{rel}"))
            self.content_layout.addWidget(acct_grp)

        # Universal Links
        self.show_universal_links('vehicle', vehicle_id)

    def show_weapon(self, weapon_id):
        self.current_type = 'weapon'
        self.current_id = weapon_id
        w = self.db.get_weapon(weapon_id)
        if not w:
            return

        self.clear()
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.link_btn.setEnabled(True)
        self.header.setText(f"Weapon: {w.get('weapon_type', 'Unknown')}")

        info = QGroupBox("Weapon Details")
        info_l = QFormLayout(info)
        info_l.addRow("Type:", QLabel(w.get('weapon_type') or '-'))
        info_l.addRow("Make:", QLabel(w.get('make') or '-'))
        info_l.addRow("Model:", QLabel(w.get('model') or '-'))
        info_l.addRow("Caliber:", QLabel(w.get('caliber') or '-'))
        info_l.addRow("Serial #:", QLabel(w.get('serial_number') or '-'))
        if w.get('notes'):
            info_l.addRow("Notes:", QLabel(w.get('notes')))
        self.content_layout.addWidget(info)

        # Find linked subjects
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT s.*, sw.relationship
            FROM subjects s
            JOIN subject_weapons sw ON s.id = sw.subject_id
            WHERE sw.weapon_id = ?
        """, (weapon_id,))
        subjects = [dict(row) for row in cursor.fetchall()]

        if subjects:
            subj_grp = QGroupBox(f"Associated Subjects ({len(subjects)})")
            subj_l = QVBoxLayout(subj_grp)
            for s in subjects:
                subj_l.addWidget(QLabel(f"• {s['first_name']} {s['last_name']} ({s.get('relationship', '-')})"))
            self.content_layout.addWidget(subj_grp)

        # Find linked events
        cursor.execute("""
            SELECT e.*, ew.disposition
            FROM events e
            JOIN event_weapons ew ON e.id = ew.event_id
            WHERE ew.weapon_id = ?
        """, (weapon_id,))
        events = [dict(row) for row in cursor.fetchall()]

        if events:
            evt_grp = QGroupBox(f"Linked Events ({len(events)})")
            evt_l = QVBoxLayout(evt_grp)
            for e in events:
                evt_l.addWidget(QLabel(f"• {e['event_number']} - {e['event_date']}"))
            self.content_layout.addWidget(evt_grp)

        # Universal Links
        self.show_universal_links('weapon', weapon_id)

    def show_online_account(self, account_id):
        self.current_type = 'online_account'
        self.current_id = account_id
        a = self.db.get_online_account(account_id)
        if not a:
            return

        self.clear()
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.link_btn.setEnabled(True)
        self.header.setText(f"@{a.get('username', 'Unknown')}")

        # Profile photo/screenshot
        photo_path = self.db.get_entity_first_photo('online_account', account_id)
        if photo_path and os.path.exists(photo_path):
            photo_label = ClickablePhotoLabel(photo_path, 150, 150)
            self.content_layout.addWidget(photo_label)

        # Account info
        info = QGroupBox("Account Information")
        info_l = QFormLayout(info)
        info_l.addRow("Platform:", QLabel(a.get('platform') or '-'))
        info_l.addRow("Username:", QLabel(a.get('username') or '-'))
        info_l.addRow("Display Name:", QLabel(a.get('display_name') or '-'))
        info_l.addRow("Platform ID:", QLabel(a.get('platform_account_id') or '-'))
        info_l.addRow("Type:", QLabel(a.get('account_type') or '-'))
        info_l.addRow("Status:", QLabel(a.get('status') or '-'))
        if a.get('profile_url'):
            url_label = QLabel(f"<a href='{a['profile_url']}'>{a['profile_url'][:40]}...</a>")
            url_label.setOpenExternalLinks(True)
            info_l.addRow("URL:", url_label)
        self.content_layout.addWidget(info)

        # Linked subject
        if a.get('subject_id'):
            subj = self.db.get_subject(a['subject_id'])
            if subj:
                subj_grp = QGroupBox("Linked Subject")
                subj_l = QVBoxLayout(subj_grp)
                subj_l.addWidget(QLabel(f"• {subj['first_name']} {subj['last_name']}"))
                self.content_layout.addWidget(subj_grp)

        # Posts/Activity - clickable to view details
        posts = self.db.get_account_posts(account_id)
        if posts:
            posts_grp = QGroupBox(f"Posts/Activity ({len(posts)})")
            posts_l = QVBoxLayout(posts_grp)
            for p in posts[:10]:  # Show first 10
                title = p.get('title', '').strip() if p.get('title') else ''
                activity = f" [{p['activity_type']}]" if p.get('activity_type') else ""
                if title:
                    display = f"{title}{activity}"
                else:
                    display = f"{p['post_date']} - {p['post_type']}{activity}"
                post_btn = QPushButton(f"📝 {display}")
                post_btn.setStyleSheet("""
                    QPushButton {
                        text-align: left;
                        background: #1a2a3a;
                        border: 1px solid #3a5a7a;
                        border-radius: 4px;
                        color: #4a9cdb;
                        padding: 5px 8px;
                        margin: 2px 0;
                    }
                    QPushButton:hover {
                        background: #2a3a4a;
                        border-color: #4a7c9b;
                    }
                """)
                post_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                post_btn.clicked.connect(lambda checked, pid=p['id']: self._view_post(pid))
                posts_l.addWidget(post_btn)
            if len(posts) > 10:
                posts_l.addWidget(QLabel(f"  ... and {len(posts) - 10} more"))
            self.content_layout.addWidget(posts_grp)

        # Associated Accounts (like associates for subjects)
        assocs = self.db.get_account_associations(account_id)
        if assocs:
            assoc_grp = QGroupBox(f"Linked Accounts ({len(assocs)})")
            assoc_l = QVBoxLayout(assoc_grp)
            for assoc in assocs:
                conf = f" [{assoc.get('confidence', 'Medium')}]" if assoc.get('confidence') else ""
                assoc_type = f" - {assoc['association_type']}" if assoc.get('association_type') else ""
                assoc_l.addWidget(QLabel(f"• @{assoc['linked_username']} ({assoc['linked_platform']}){assoc_type}{conf}"))
            self.content_layout.addWidget(assoc_grp)

        # Linked Vehicles
        vehicles = self.db.get_account_vehicles(account_id)
        if vehicles:
            veh_grp = QGroupBox(f"Linked Vehicles ({len(vehicles)})")
            veh_l = QVBoxLayout(veh_grp)
            for v in vehicles:
                plate = v.get('plate') or 'No Plate'
                desc = f"{v.get('color', '')} {v.get('year', '')} {v.get('make', '')} {v.get('model', '')}".strip()
                rel = f" - {v['relationship']}" if v.get('relationship') else ""
                veh_l.addWidget(QLabel(f"• {plate}: {desc}{rel}"))
            self.content_layout.addWidget(veh_grp)

        # Action buttons (in fixed bar outside scroll area)
        add_post_btn = QPushButton("+ Post")
        add_post_btn.setStyleSheet("background-color: #5a8a6a;")
        add_post_btn.clicked.connect(lambda checked, aid=account_id: self._add_account_post(aid))
        self.action_btns_layout.addWidget(add_post_btn)

        link_acct_btn = QPushButton("Link Accounts")
        link_acct_btn.setStyleSheet("background-color: #3a9a8a;")
        link_acct_btn.clicked.connect(lambda checked, aid=account_id: self._link_accounts(aid))
        self.action_btns_layout.addWidget(link_acct_btn)

        link_veh_btn = QPushButton("Link Vehicle")
        link_veh_btn.setStyleSheet("background-color: #7a6a9a;")
        link_veh_btn.clicked.connect(lambda checked, aid=account_id: self._link_account_vehicle(aid))
        self.action_btns_layout.addWidget(link_veh_btn)

        self.action_btns_widget.show()

        # Notes
        if a.get('notes'):
            notes_grp = QGroupBox("Notes")
            notes_l = QVBoxLayout(notes_grp)
            notes_lbl = QLabel(a['notes'])
            notes_lbl.setWordWrap(True)
            notes_l.addWidget(notes_lbl)
            self.content_layout.addWidget(notes_grp)

        # Universal Links
        self.show_universal_links('online_account', account_id)

    def _link_accounts(self, account_id):
        """Open dialog to link this account to other accounts"""
        widget = self
        while widget.parent():
            widget = widget.parent()
            if hasattr(widget, 'db'):
                break
        dlg = LinkAccountsDialog(self, self.db, account_id)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.show_online_account(account_id)
            if hasattr(widget, 'refresh_all'):
                widget.refresh_all()

    def _add_account_post(self, account_id):
        """Open dialog to add a post to an online account"""
        widget = self
        while widget.parent():
            widget = widget.parent()
            if hasattr(widget, 'db'):
                break
        dlg = AccountPostDialog(self, self.db, account_id)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.show_online_account(account_id)
            if hasattr(widget, 'refresh_all'):
                widget.refresh_all()

    def _link_account_vehicle(self, account_id):
        """Open dialog to link a vehicle to this account"""
        widget = self
        while widget.parent():
            widget = widget.parent()
            if hasattr(widget, 'db'):
                break
        dlg = LinkAccountVehicleDialog(self, self.db, account_id)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.show_online_account(account_id)
            if hasattr(widget, 'refresh_all'):
                widget.refresh_all()

    def _view_post(self, post_id):
        """View a post in the profile panel"""
        self.show_post(post_id)

    def show_post(self, post_id):
        """Display an account post in the profile panel"""
        self.current_type = 'post'
        self.current_id = post_id
        p = self.db.get_account_post(post_id)
        if not p:
            return

        self.clear()
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.link_btn.setEnabled(True)

        # Get linked account info
        acct = self.db.get_online_account(p['account_id']) if p.get('account_id') else None
        acct_display = f"@{acct['username']}" if acct and acct.get('username') else (acct['platform'] if acct else 'No Account')

        # Use title in header if available
        title = p.get('title', '').strip() if p.get('title') else ''
        if title:
            self.header.setText(f"📝 {title}")
        else:
            self.header.setText(f"📝 Post: {acct_display}")

        # Screenshot/photo for post
        photo_path = self.db.get_entity_first_photo('post', post_id)
        if photo_path and os.path.exists(photo_path):
            photo_label = ClickablePhotoLabel(photo_path, 200, 200)
            self.content_layout.addWidget(photo_label)

        # Post info
        info = QGroupBox("Post Details")
        info_l = QFormLayout(info)
        if title:
            info_l.addRow("Title:", QLabel(title))
        info_l.addRow("Account:", QLabel(acct_display))
        info_l.addRow("Post Type:", QLabel(p.get('post_type') or '-'))
        info_l.addRow("Activity Type:", QLabel(p.get('activity_type') or '-'))
        info_l.addRow("Post Date:", QLabel(p.get('post_date') or '-'))
        info_l.addRow("Captured Date:", QLabel(p.get('captured_date') or '-'))
        if p.get('post_url'):
            url_label = QLabel(f"<a href='{p['post_url']}'>{p['post_url'][:50]}...</a>")
            url_label.setOpenExternalLinks(True)
            info_l.addRow("Post URL:", url_label)
        self.content_layout.addWidget(info)

        # Content
        if p.get('content_text'):
            content_grp = QGroupBox("Content")
            content_l = QVBoxLayout(content_grp)
            content_lbl = QLabel(p['content_text'])
            content_lbl.setWordWrap(True)
            content_l.addWidget(content_lbl)
            self.content_layout.addWidget(content_grp)

        # Linked Account
        if acct:
            acct_grp = QGroupBox("Linked Account")
            acct_l = QVBoxLayout(acct_grp)
            acct_l.addWidget(QLabel(f"• {acct['platform']}: @{acct.get('username', 'Unknown')}"))
            self.content_layout.addWidget(acct_grp)

        # Notes
        if p.get('notes'):
            notes_grp = QGroupBox("Notes")
            notes_l = QVBoxLayout(notes_grp)
            notes_lbl = QLabel(p['notes'])
            notes_lbl.setWordWrap(True)
            notes_l.addWidget(notes_lbl)
            self.content_layout.addWidget(notes_grp)

        # Universal Links
        self.show_universal_links('post', post_id)

    def show_dns_investigation(self, dns_id):
        self.current_type = 'dns'
        self.current_id = dns_id
        d = self.db.get_dns_investigation(dns_id)
        if not d:
            return

        self.clear()
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.link_btn.setEnabled(True)
        self.header.setText(f"DNS: {d.get('domain_name', 'Unknown')}")

        # Screenshot
        photo_path = self.db.get_entity_first_photo('dns', dns_id)
        if photo_path and os.path.exists(photo_path):
            photo_label = ClickablePhotoLabel(photo_path, 150, 150)
            self.content_layout.addWidget(photo_label)

        # Domain info
        info = QGroupBox("Domain Information")
        info_l = QFormLayout(info)
        info_l.addRow("Domain:", QLabel(d.get('domain_name') or '-'))
        info_l.addRow("Investigation Date:", QLabel(d.get('investigation_date') or '-'))
        self.content_layout.addWidget(info)

        # DNS Records
        dns_grp = QGroupBox("DNS Records")
        dns_l = QFormLayout(dns_grp)
        if d.get('a_records'):
            dns_l.addRow("A:", QLabel(d['a_records']))
        if d.get('aaaa_records'):
            dns_l.addRow("AAAA:", QLabel(d['aaaa_records']))
        if d.get('mx_records'):
            dns_l.addRow("MX:", QLabel(d['mx_records']))
        if d.get('cname_records'):
            dns_l.addRow("CNAME:", QLabel(d['cname_records']))
        if d.get('ns_records'):
            dns_l.addRow("NS:", QLabel(d['ns_records']))
        if d.get('txt_records'):
            txt_lbl = QLabel(d['txt_records'][:200])
            txt_lbl.setWordWrap(True)
            dns_l.addRow("TXT:", txt_lbl)
        self.content_layout.addWidget(dns_grp)

        # WHOIS info
        whois_grp = QGroupBox("WHOIS Information")
        whois_l = QFormLayout(whois_grp)
        if d.get('registrar'):
            whois_l.addRow("Registrar:", QLabel(d['registrar']))
        if d.get('registrant_name'):
            whois_l.addRow("Registrant:", QLabel(d['registrant_name']))
        if d.get('registrant_email'):
            whois_l.addRow("Email:", QLabel(d['registrant_email']))
        if d.get('registration_date'):
            whois_l.addRow("Registered:", QLabel(d['registration_date']))
        if d.get('expiration_date'):
            whois_l.addRow("Expires:", QLabel(d['expiration_date']))
        self.content_layout.addWidget(whois_grp)

        # Hosting info
        if d.get('hosting_provider') or d.get('ip_addresses'):
            hosting_grp = QGroupBox("Hosting")
            hosting_l = QFormLayout(hosting_grp)
            if d.get('hosting_provider'):
                hosting_l.addRow("Provider:", QLabel(d['hosting_provider']))
            if d.get('ip_addresses'):
                hosting_l.addRow("IPs:", QLabel(d['ip_addresses']))
            self.content_layout.addWidget(hosting_grp)

        # Linked entities
        if d.get('subject_id'):
            subj = self.db.get_subject(d['subject_id'])
            if subj:
                link_grp = QGroupBox("Linked Subject")
                link_l = QVBoxLayout(link_grp)
                link_l.addWidget(QLabel(f"• {subj['first_name']} {subj['last_name']}"))
                self.content_layout.addWidget(link_grp)

        if d.get('account_id'):
            acct = self.db.get_online_account(d['account_id'])
            if acct:
                acct_grp = QGroupBox("Linked Account")
                acct_l = QVBoxLayout(acct_grp)
                acct_l.addWidget(QLabel(f"• @{acct['username']} ({acct['platform']})"))
                self.content_layout.addWidget(acct_grp)

        # Notes
        if d.get('notes'):
            notes_grp = QGroupBox("Notes")
            notes_l = QVBoxLayout(notes_grp)
            notes_lbl = QLabel(d['notes'])
            notes_lbl.setWordWrap(True)
            notes_l.addWidget(notes_lbl)
            self.content_layout.addWidget(notes_grp)

        # Universal Links
        self.show_universal_links('dns', dns_id)

    def show_tracked_phone(self, phone_id):
        self.current_type = 'phone'
        self.current_id = phone_id
        p = self.db.get_tracked_phone(phone_id)
        if not p:
            return

        self.clear()
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.link_btn.setEnabled(True)
        self.header.setText(f"📱 {p.get('phone_number', 'Unknown')}")

        # Screenshot/photo
        photo_path = self.db.get_entity_first_photo('phone', phone_id)
        if photo_path and os.path.exists(photo_path):
            photo_label = ClickablePhotoLabel(photo_path, 150, 150)
            self.content_layout.addWidget(photo_label)

        # Phone info
        info = QGroupBox("Phone Information")
        info_l = QFormLayout(info)
        info_l.addRow("Phone Number:", QLabel(p.get('phone_number') or '-'))
        info_l.addRow("Type:", QLabel(p.get('phone_type') or '-'))
        info_l.addRow("Carrier:", QLabel(p.get('carrier') or '-'))
        info_l.addRow("Carrier Type:", QLabel(p.get('carrier_type') or '-'))
        info_l.addRow("Location/Area:", QLabel(p.get('location_area') or '-'))
        info_l.addRow("Status:", QLabel(p.get('status') or '-'))
        self.content_layout.addWidget(info)

        # Registration info
        if p.get('registered_name') or p.get('first_seen_date') or p.get('last_seen_date'):
            reg_grp = QGroupBox("Registration Info")
            reg_l = QFormLayout(reg_grp)
            if p.get('registered_name'):
                reg_l.addRow("Registered Name:", QLabel(p['registered_name']))
            if p.get('first_seen_date'):
                reg_l.addRow("First Seen:", QLabel(p['first_seen_date']))
            if p.get('last_seen_date'):
                reg_l.addRow("Last Seen:", QLabel(p['last_seen_date']))
            self.content_layout.addWidget(reg_grp)

        # Linked subject
        if p.get('subject_id'):
            subj = self.db.get_subject(p['subject_id'])
            if subj:
                subj_grp = QGroupBox("Linked Subject")
                subj_l = QVBoxLayout(subj_grp)
                subj_l.addWidget(QLabel(f"• {subj['first_name']} {subj['last_name']}"))
                self.content_layout.addWidget(subj_grp)

        # Linked account
        if p.get('account_id'):
            acct = self.db.get_online_account(p['account_id'])
            if acct:
                acct_grp = QGroupBox("Linked Account")
                acct_l = QVBoxLayout(acct_grp)
                acct_l.addWidget(QLabel(f"• @{acct['username']} ({acct['platform']})"))
                self.content_layout.addWidget(acct_grp)

        # Notes
        if p.get('notes'):
            notes_grp = QGroupBox("Notes")
            notes_l = QVBoxLayout(notes_grp)
            notes_lbl = QLabel(p['notes'])
            notes_lbl.setWordWrap(True)
            notes_l.addWidget(notes_lbl)
            self.content_layout.addWidget(notes_grp)

        # Universal Links
        self.show_universal_links('phone', phone_id)

    def edit_current(self):
        if not self.current_id:
            return
        # Use stored MainWindow reference
        if self.main_window and hasattr(self.main_window, 'edit_entity'):
            self.main_window.edit_entity(self.current_type, self.current_id)

    def delete_current(self):
        if not self.current_id:
            return

        # Use cascade delete dialog for types that have relationships
        cascade_types = ['subject', 'event', 'vehicle', 'weapon', 'gang', 'location', 'online_account']

        if self.current_type in cascade_types:
            dialog = CascadeDeleteDialog(self, self.db, self.current_type, self.current_id)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                items_to_delete = dialog.get_items_to_delete()
                for item_type, item_id in items_to_delete:
                    self._delete_item(item_type, item_id)
        else:
            # Simple delete for types without relationships
            reply = QMessageBox.question(self, "Delete", f"Delete this {self.current_type}?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self._delete_item(self.current_type, self.current_id)

        # Refresh using stored MainWindow reference
        if self.main_window and hasattr(self.main_window, 'refresh_all'):
            self.main_window.refresh_all()

    def _delete_item(self, item_type: str, item_id: str):
        """Delete a single item by type"""
        if item_type == 'subject':
            self.db.delete_subject(item_id)
        elif item_type == 'gang':
            self.db.delete_gang(item_id)
        elif item_type == 'location':
            self.db.delete_location(item_id)
        elif item_type == 'event':
            self.db.delete_event(item_id)
        elif item_type == 'charge':
            self.db.delete_charge(item_id)
        elif item_type == 'graffiti':
            self.db.delete_graffiti(item_id)
        elif item_type == 'intel':
            self.db.delete_intel_report(item_id)
        elif item_type == 'vehicle':
            self.db.delete_vehicle(item_id)
        elif item_type == 'weapon':
            self.db.delete_weapon(item_id)
        elif item_type == 'evidence':
            self.db.delete_evidence(item_id)
        elif item_type == 'online_account':
            self.db.delete_online_account(item_id)
        elif item_type == 'dns':
            self.db.delete_dns_investigation(item_id)
        elif item_type == 'phone':
            self.db.delete_tracked_phone(item_id)
        elif item_type == 'post':
            self.db.delete_account_post(item_id)


# ============ MAIN WINDOW ============

class MainWindow(QMainWindow):
    """
    Main application window for Tracker case management system.

    This is the primary interface for OSINT investigations and case management.
    Provides:
    - Tree view navigation for all entities
    - Detail panel for viewing/editing records
    - Network graph visualization
    - OSINT checklist tracking
    - Google dorking tools

    Attributes:
        db (TrackerDB): Database interface
        auth (AuthManager): Authentication manager
        current_subject_id (str): Currently selected subject ID
    """

    def __init__(self, auth_manager: AuthManager = None, encryption_password: str = None):
        """
        Initialize the main window.

        Args:
            auth_manager: Authentication manager instance (for security menu)
            encryption_password: User's password for database encryption/decryption
        """
        super().__init__()
        self.auth = auth_manager or AuthManager()
        self._encryption_password = encryption_password

        # Decrypt database if encrypted
        self._db_path = os.path.join(os.path.dirname(__file__), 'data', 'database.db')
        self._encrypted_db_path = self._db_path + '.enc'
        self._decrypt_database()

        self.db = TrackerDB(self._db_path)
        self.setWindowTitle("Tracker - Case Management")
        self.setMinimumSize(1400, 900)
        self.setup_ui()
        self.setup_menu()
        self.refresh_all()

    def _decrypt_database(self):
        """Decrypt the database file on startup if it exists encrypted."""
        from encryption import is_encrypted, decrypt_file

        # If unencrypted database exists, use it directly (legacy/migration case)
        if os.path.exists(self._db_path):
            # Check if encrypted version also exists - prefer unencrypted for safety
            if os.path.exists(self._encrypted_db_path):
                # Both exist - use unencrypted, remove encrypted (likely stale)
                try:
                    os.remove(self._encrypted_db_path)
                except:
                    pass
            return  # Use existing unencrypted database

        # Check if encrypted version exists
        if os.path.exists(self._encrypted_db_path) and self._encryption_password:
            try:
                # Decrypt to the regular db path
                decrypt_file(self._encrypted_db_path, self._db_path, self._encryption_password)
                # Remove encrypted version (we'll re-encrypt on close)
                os.remove(self._encrypted_db_path)
            except Exception as e:
                # Decryption failed - offer options
                reply = QMessageBox.critical(None, "Database Error",
                    f"Failed to decrypt database:\n{str(e)}\n\n"
                    "This may happen if your password changed or the database is corrupted.\n\n"
                    "Click 'Yes' to start with a fresh database (old data will be backed up)\n"
                    "Click 'No' to exit and manually fix the issue.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

                if reply == QMessageBox.StandardButton.Yes:
                    # Backup encrypted file and start fresh
                    backup_path = self._encrypted_db_path + '.backup'
                    try:
                        os.rename(self._encrypted_db_path, backup_path)
                        QMessageBox.information(None, "Backup Created",
                            f"Encrypted database backed up to:\n{backup_path}")
                    except:
                        pass
                else:
                    sys.exit(1)

    def _encrypt_database(self):
        """Encrypt the database file on shutdown."""
        from encryption import encrypt_file

        if self._encryption_password and os.path.exists(self._db_path):
            try:
                # Encrypt the database
                encrypt_file(self._db_path, self._encrypted_db_path, self._encryption_password)
                # Remove unencrypted version
                os.remove(self._db_path)
            except Exception as e:
                QMessageBox.warning(None, "Encryption Warning",
                    f"Failed to encrypt database on close:\n{str(e)}\n\n"
                    "Your data may not be fully protected.")

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ============ LEFT PANEL - Tree View ============
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left.setMaximumWidth(280)

        # Title
        title = QLabel("Tracker")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #c9a040; padding: 5px; letter-spacing: 2px;")
        left_layout.addWidget(title)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search all...")
        self.search.textChanged.connect(self.on_search)
        left_layout.addWidget(self.search)

        # Single unified Add New button
        add_new_btn = QPushButton("+ Add New")
        add_new_btn.setStyleSheet("""
            QPushButton {
                background-color: #c9a040;
                color: #0a0a0f;
                padding: 12px 20px;
                font-weight: bold;
                font-size: 16px;
                border-radius: 6px;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #d9b050;
            }
            QPushButton:pressed {
                background-color: #b99030;
            }
        """)
        add_new_btn.clicked.connect(self.show_add_new_dialog)
        left_layout.addWidget(add_new_btn)

        # Tree View
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self.on_tree_item_clicked)
        left_layout.addWidget(self.tree)

        splitter.addWidget(left)

        # ============ CENTER - Graph with controls ============
        graph_container = QWidget()
        graph_layout = QVBoxLayout(graph_container)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_layout.setSpacing(0)

        # Graph toolbar
        graph_toolbar = QHBoxLayout()
        graph_toolbar.setContentsMargins(5, 5, 5, 5)

        self.show_all_btn = QPushButton("🌐 Refresh")
        self.show_all_btn.setToolTip("Refresh graph with all entities")
        self.show_all_btn.setStyleSheet("background-color: #3a5a7a; padding: 5px 10px;")
        self.show_all_btn.clicked.connect(lambda: self.refresh_graph())
        graph_toolbar.addWidget(self.show_all_btn)

        self.add_link_btn = QPushButton("🔗 Add Link")
        self.add_link_btn.setToolTip("Add a connection between two entities")
        self.add_link_btn.setStyleSheet("background-color: #5a8a6a; padding: 5px 10px;")
        self.add_link_btn.clicked.connect(self.open_add_link_dialog)
        graph_toolbar.addWidget(self.add_link_btn)

        graph_toolbar.addStretch()

        self.graph_info_label = QLabel("Select an item to see its connections")
        self.graph_info_label.setStyleSheet("color: #6a7a8a; font-size: 11px;")
        graph_toolbar.addWidget(self.graph_info_label)

        graph_layout.addLayout(graph_toolbar)

        self.graph = GraphView()
        self.graph.nodeDeleteRequested.connect(self.on_graph_delete_requested)
        self.graph.edgeClicked.connect(self.on_graph_edge_clicked)
        graph_layout.addWidget(self.graph, 1)

        splitter.addWidget(graph_container)

        # ============ RIGHT PANEL - Single scrollable area with collapsible sections ============
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setMinimumWidth(380)
        right_scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: #0a0a0f; }
            QScrollBar:vertical { background-color: #12121a; width: 12px; }
            QScrollBar::handle:vertical { background-color: #3a3a4a; border-radius: 6px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background-color: #4a4a5a; }
        """)

        right_content = QWidget()
        right_content_layout = QVBoxLayout(right_content)
        right_content_layout.setContentsMargins(5, 5, 5, 5)
        right_content_layout.setSpacing(10)
        right_content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Full Profile Section (collapsible, expanded by default)
        self.profile_section = CollapsibleSection("Full Profile", expanded=True)
        self.profile = ProfilePanel(self, self.db)
        self.profile_section.addWidget(self.profile)
        right_content_layout.addWidget(self.profile_section)

        # Selected Node Section (collapsible, collapsed by default)
        self.node_section = CollapsibleSection("Selected Node", expanded=False)
        node_container = QWidget()
        node_layout = QVBoxLayout(node_container)
        node_layout.setContentsMargins(5, 5, 5, 5)

        self.node_info_label = QLabel("Click a node on the graph to see details")
        self.node_info_label.setWordWrap(True)
        self.node_info_label.setStyleSheet("padding: 10px; background-color: #1a1a24; border-radius: 4px;")
        node_layout.addWidget(self.node_info_label)

        self.view_node_btn = QPushButton("View Full Profile")
        self.view_node_btn.clicked.connect(self.view_selected_node)
        self.view_node_btn.setEnabled(False)
        node_layout.addWidget(self.view_node_btn)

        self.node_section.addWidget(node_container)
        right_content_layout.addWidget(self.node_section)

        # Connect graph click signal
        self.graph.nodeClicked.connect(self.on_graph_node_clicked)
        self._selected_node = None  # Store selected node info

        # Checklist Section (collapsible, collapsed by default)
        self.checklist_section = CollapsibleSection("Checklist", expanded=False)
        check_container = QWidget()
        check_layout = QVBoxLayout(check_container)
        check_layout.setContentsMargins(5, 5, 5, 5)

        self.checklist_tree = QTreeWidget()
        self.checklist_tree.setHeaderHidden(True)
        self.checklist_tree.itemChanged.connect(self.on_checklist_item_changed)
        self.checklist_tree.itemDoubleClicked.connect(self.on_checklist_item_double_clicked)
        # Disable internal scrolling - let parent scroll area handle it
        self.checklist_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.checklist_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.checklist_tree.setSizeAdjustPolicy(QTreeWidget.SizeAdjustPolicy.AdjustToContents)
        self.checklist_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.checklist_tree.setToolTip("Double-click items with URLs to open in browser")
        # Explicit checkbox styling for checklist
        self.checklist_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #12121a;
                border: 1px solid #3a3a4a;
                border-radius: 4px;
                color: #a0a8b8;
            }
            QTreeWidget::item {
                padding: 6px;
                border-bottom: 1px solid #1a1a24;
            }
            QTreeWidget::item:selected {
                background-color: #2a3a4a;
                color: #c9a040;
            }
            QTreeWidget::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
            }
            QTreeWidget::indicator:unchecked {
                background-color: #2a2a34;
                border: 2px solid #6a6a7a;
            }
            QTreeWidget::indicator:unchecked:hover {
                background-color: #3a3a44;
                border: 2px solid #c9a040;
            }
            QTreeWidget::indicator:checked {
                background-color: #4a9a5a;
                border: 2px solid #6aba7a;
            }
            QTreeWidget::indicator:checked:hover {
                background-color: #5aaa6a;
                border: 2px solid #7aca8a;
            }
        """)
        check_layout.addWidget(self.checklist_tree)

        check_btns = QHBoxLayout()
        add_item_btn = QPushButton("+ Add Item")
        add_item_btn.setStyleSheet("background-color: #c9a040; color: #0a0a0f; font-weight: bold; font-size: 14px;")
        add_item_btn.clicked.connect(self.add_checklist_item)
        check_btns.addWidget(add_item_btn)

        edit_list_btn = QPushButton("Edit List")
        edit_list_btn.clicked.connect(self.edit_checklist)
        check_btns.addWidget(edit_list_btn)
        check_layout.addLayout(check_btns)

        self.checklist_section.addWidget(check_container)
        right_content_layout.addWidget(self.checklist_section)

        right_scroll.setWidget(right_content)
        splitter.addWidget(right_scroll)

        splitter.setSizes([250, 600, 400])
        layout.addWidget(splitter)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.current_subject_id = None
        self.apply_theme()

    def apply_theme(self):
        # Muted Cyber Palette - Easy on the eyes, professional with an edge
        # Background: #0a0a0f | Secondary: #12121a | Text: #a0a8b8
        # Accent: #4a7c9b (teal) | Buttons: #6b5b8a (purple) | Headers: #c9a040 (gold)
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0a0a0f;
                color: #a0a8b8;
            }
            QLabel { color: #a0a8b8; }
            QTreeWidget, QListWidget {
                background-color: #12121a;
                border: 1px solid #3a3a4a;
                border-radius: 4px;
                color: #a0a8b8;
            }
            QTreeWidget::item, QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #1a1a24;
            }
            QTreeWidget::item:selected, QListWidget::item:selected {
                background-color: #2a3a4a;
                color: #c9a040;
            }
            QTreeWidget::item:hover, QListWidget::item:hover {
                background-color: #1a1a24;
            }
            QTreeWidget::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
            }
            QTreeWidget::indicator:checked {
                background-color: #4a9a5a;
                border: 2px solid #6aba7a;
                image: url(icons/x-bold-white.svg);
            }
            QTreeWidget::indicator:unchecked {
                background-color: #2a2a34;
                border: 2px solid #6a6a7a;
            }
            QTreeWidget::indicator:unchecked:hover {
                border: 2px solid #c9a040;
                background-color: #3a3a44;
            }
            QTreeWidget::indicator:checked:hover {
                background-color: #5aaa6a;
                border: 2px solid #7aca8a;
                image: url(icons/x-bold-white.svg);
            }
            QLineEdit, QTextEdit, QComboBox, QDateEdit, QSpinBox {
                background-color: #12121a;
                border: 1px solid #3a3a4a;
                border-radius: 4px;
                padding: 6px;
                color: #a0a8b8;
                selection-background-color: #2a3a4a;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border: 1px solid #4a7c9b;
            }
            QPushButton {
                background-color: #6b5b8a;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                color: #e0e0e8;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7b6b9a;
            }
            QPushButton:pressed {
                background-color: #5b4b7a;
            }
            QGroupBox {
                border: 1px solid #3a3a4a;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
                color: #a0a8b8;
            }
            QGroupBox::title {
                color: #c9a040;
                subcontrol-origin: margin;
                left: 10px;
                font-weight: bold;
            }
            QScrollBar:vertical {
                background-color: #0a0a0f;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #3a3a4a;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4a7c9b;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollArea { border: none; }
            QCheckBox {
                color: #a0a8b8;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9a5a;
                border: 2px solid #6aba7a;
                image: url(icons/x-bold-white.svg);
            }
            QCheckBox::indicator:unchecked {
                background-color: #2a2a34;
                border: 2px solid #6a6a7a;
            }
            QCheckBox::indicator:unchecked:hover {
                border: 2px solid #c9a040;
                background-color: #3a3a44;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #5aaa6a;
                border: 2px solid #7aca8a;
                image: url(icons/x-bold-white.svg);
            }
            QCheckBox::indicator:disabled:checked {
                background-color: #3a7a4a;
                border: 2px solid #4a8a5a;
                image: url(icons/x-bold-gray.svg);
            }
            QCheckBox::indicator:disabled:unchecked {
                background-color: #1a1a24;
                border: 2px solid #3a3a4a;
            }
            QCheckBox:disabled {
                color: #6a6a7a;
            }
            QMenuBar {
                background-color: #0a0a0f;
                color: #a0a8b8;
            }
            QMenuBar::item:selected {
                background-color: #2a3a4a;
            }
            QMenu {
                background-color: #12121a;
                color: #a0a8b8;
                border: 1px solid #3a3a4a;
            }
            QMenu::item:selected {
                background-color: #2a3a4a;
                color: #c9a040;
            }
            QStatusBar {
                background-color: #0a0a0f;
                color: #5a8a6a;
            }
            QDialog {
                background-color: #0a0a0f;
            }
            QMessageBox {
                background-color: #0a0a0f;
            }
            QDialogButtonBox QPushButton {
                min-width: 80px;
            }
            QTabWidget::pane {
                border: 1px solid #3a3a4a;
                background-color: #12121a;
            }
            QTabBar::tab {
                background-color: #12121a;
                color: #a0a8b8;
                padding: 8px 16px;
                border: 1px solid #3a3a4a;
                border-bottom: none;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #2a3a4a;
                color: #c9a040;
            }
            QTabBar::tab:hover:!selected {
                background-color: #1a1a24;
            }
        """)

    def setup_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("File")

        export_act = QAction("Export Case Data...", self)
        export_act.triggered.connect(self.export_data)
        file_menu.addAction(export_act)

        import_act = QAction("Import Case Data...", self)
        import_act.triggered.connect(self.import_data)
        file_menu.addAction(import_act)

        file_menu.addSeparator()

        backup_act = QAction("Backup Database (Encrypted)...", self)
        backup_act.triggered.connect(self.backup_database)
        file_menu.addAction(backup_act)

        restore_act = QAction("Restore Database from Backup...", self)
        restore_act.triggered.connect(self.restore_database)
        file_menu.addAction(restore_act)

        file_menu.addSeparator()

        exit_act = QAction("Exit", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        view_menu = menu.addMenu("View")
        refresh = QAction("Refresh All", self)
        refresh.triggered.connect(self.refresh_all)
        view_menu.addAction(refresh)

        # Security menu for authentication settings
        security_menu = menu.addMenu("Security")

        security_settings = QAction("Security Settings...", self)
        security_settings.triggered.connect(self.show_security_settings)
        security_menu.addAction(security_settings)

        security_menu.addSeparator()

        lock_act = QAction("Lock Application", self)
        lock_act.triggered.connect(self.lock_application)
        security_menu.addAction(lock_act)

    def show_security_settings(self):
        """Open security settings dialog."""
        dialog = SecuritySettingsDialog(self, self.auth)
        dialog.exec()

    def lock_application(self):
        """Lock the application and require re-authentication."""
        self.hide()
        dialog = LoginDialog(None, self.auth)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.show()
        else:
            self.close()

    def refresh_all(self):
        self.refresh_tree()
        self.refresh_graph()
        self.refresh_checklist()

    def refresh_tree(self, filter_text=""):
        """Refresh the tree view with all entities"""
        self.tree.clear()

        # Helper to style category based on child count
        def style_category(root_item, count):
            if count > 0:
                root_item.setText(0, f"{root_item.text(0)} ({count})")
                root_item.setForeground(0, QColor("#c9a040"))  # Gold highlight
            else:
                root_item.setForeground(0, QColor("#6a6a7a"))  # Dim gray

        # Subjects
        subjects_root = QTreeWidgetItem(self.tree, ["Subjects"])
        subjects_root.setData(0, Qt.ItemDataRole.UserRole, ('category', 'subjects'))
        subjects = self.db.search_subjects(filter_text) if filter_text else self.db.get_all_subjects()
        for s in subjects:
            text = f"{s['last_name']}, {s['first_name']}"
            if s.get('monikers'):
                text += f" ({s['monikers'][:12]})"
            item = QTreeWidgetItem(subjects_root, [text])
            item.setData(0, Qt.ItemDataRole.UserRole, ('subject', s['id']))
        style_category(subjects_root, len(subjects))

        # Gangs
        gangs_root = QTreeWidgetItem(self.tree, ["Gangs"])
        gangs_root.setData(0, Qt.ItemDataRole.UserRole, ('category', 'gangs'))
        gangs = self.db.get_all_gangs()
        for g in gangs:
            item = QTreeWidgetItem(gangs_root, [g['name']])
            item.setData(0, Qt.ItemDataRole.UserRole, ('gang', g['id']))
        style_category(gangs_root, len(gangs))

        # Events
        events_root = QTreeWidgetItem(self.tree, ["Events"])
        events_root.setData(0, Qt.ItemDataRole.UserRole, ('category', 'events'))
        events = self.db.get_all_events()
        for e in events:
            item = QTreeWidgetItem(events_root, [f"{e['event_number']} ({e['event_date']})"])
            item.setData(0, Qt.ItemDataRole.UserRole, ('event', e['id']))
        style_category(events_root, len(events))

        # Locations
        locations_root = QTreeWidgetItem(self.tree, ["Locations"])
        locations_root.setData(0, Qt.ItemDataRole.UserRole, ('category', 'locations'))
        locations = self.db.get_all_locations()
        for loc in locations:
            item = QTreeWidgetItem(locations_root, [loc['address'][:35]])
            item.setData(0, Qt.ItemDataRole.UserRole, ('location', loc['id']))
        style_category(locations_root, len(locations))

        # Vehicles
        vehicles_root = QTreeWidgetItem(self.tree, ["Vehicles"])
        vehicles_root.setData(0, Qt.ItemDataRole.UserRole, ('category', 'vehicles'))
        vehicles = self.db.get_all_vehicles()
        for v in vehicles:
            item = QTreeWidgetItem(vehicles_root, [f"{v['plate']} - {v['make']} {v['model']}"])
            item.setData(0, Qt.ItemDataRole.UserRole, ('vehicle', v['id']))
        style_category(vehicles_root, len(vehicles))

        # Weapons
        weapons_root = QTreeWidgetItem(self.tree, ["Weapons"])
        weapons_root.setData(0, Qt.ItemDataRole.UserRole, ('category', 'weapons'))
        weapons = self.db.get_all_weapons()
        for w in weapons:
            desc = f"{w.get('weapon_type', 'Unknown')} - {w.get('make', '')} {w.get('model', '')}".strip()
            if w.get('serial_number'):
                desc += f" (S/N: {w['serial_number']})"
            item = QTreeWidgetItem(weapons_root, [desc[:40]])
            item.setData(0, Qt.ItemDataRole.UserRole, ('weapon', w['id']))
        style_category(weapons_root, len(weapons))

        # Charges
        charges_root = QTreeWidgetItem(self.tree, ["Charges"])
        charges_root.setData(0, Qt.ItemDataRole.UserRole, ('category', 'charges'))
        charges = self.db.get_all_charges()
        for c in charges:
            name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or "?"
            item = QTreeWidgetItem(charges_root, [f"{c['charges_text'][:20]} - {name}"])
            item.setData(0, Qt.ItemDataRole.UserRole, ('charge', c['id']))
        style_category(charges_root, len(charges))

        # Graffiti
        graffiti_root = QTreeWidgetItem(self.tree, ["Graffiti"])
        graffiti_root.setData(0, Qt.ItemDataRole.UserRole, ('category', 'graffiti'))
        graffiti = self.db.get_all_graffiti()
        for g in graffiti:
            item = QTreeWidgetItem(graffiti_root, [f"{g['location_text'][:25]}"])
            item.setData(0, Qt.ItemDataRole.UserRole, ('graffiti', g['id']))
        style_category(graffiti_root, len(graffiti))

        # Intel
        intel_root = QTreeWidgetItem(self.tree, ["Intel"])
        intel_root.setData(0, Qt.ItemDataRole.UserRole, ('category', 'intel'))
        intel = self.db.get_all_intel_reports()
        for i in intel:
            item = QTreeWidgetItem(intel_root, [f"[{i['source_type']}] {i['details'][:20]}"])
            item.setData(0, Qt.ItemDataRole.UserRole, ('intel', i['id']))
        style_category(intel_root, len(intel))

        # Online Accounts
        accounts_root = QTreeWidgetItem(self.tree, ["Online Accounts"])
        accounts_root.setData(0, Qt.ItemDataRole.UserRole, ('category', 'online_accounts'))
        accounts = self.db.get_all_online_accounts()
        for a in accounts:
            display = f"@{a['username']}" if a['username'] else a['platform']
            item = QTreeWidgetItem(accounts_root, [f"{a['platform']}: {display}"])
            item.setData(0, Qt.ItemDataRole.UserRole, ('online_account', a['id']))
        style_category(accounts_root, len(accounts))

        # DNS Investigations
        dns_root = QTreeWidgetItem(self.tree, ["DNS Investigations"])
        dns_root.setData(0, Qt.ItemDataRole.UserRole, ('category', 'dns'))
        dns_list = self.db.get_all_dns_investigations()
        for d in dns_list:
            item = QTreeWidgetItem(dns_root, [d['domain_name']])
            item.setData(0, Qt.ItemDataRole.UserRole, ('dns', d['id']))
        style_category(dns_root, len(dns_list))

        # Tracked Phones
        phones_root = QTreeWidgetItem(self.tree, ["Tracked Phones"])
        phones_root.setData(0, Qt.ItemDataRole.UserRole, ('category', 'phones'))
        phones = self.db.get_all_tracked_phones()
        for ph in phones:
            display = ph['phone_number']
            if ph.get('registered_name'):
                display = f"{ph['phone_number']} ({ph['registered_name']})"
            item = QTreeWidgetItem(phones_root, [display])
            item.setData(0, Qt.ItemDataRole.UserRole, ('phone', ph['id']))
        style_category(phones_root, len(phones))

        # Account Posts
        posts_root = QTreeWidgetItem(self.tree, ["Posts"])
        posts_root.setData(0, Qt.ItemDataRole.UserRole, ('category', 'posts'))
        all_posts = self.db.get_all_account_posts()
        for p in all_posts:
            # Get account info for display
            acct = self.db.get_online_account(p['account_id']) if p.get('account_id') else None
            acct_name = f"@{acct['username']}" if acct and acct.get('username') else (acct['platform'] if acct else 'Unknown')
            # Use title if available, otherwise fall back to content preview
            title = p.get('title', '').strip() if p.get('title') else ''
            if title:
                display = f"{acct_name}: {title}"
            else:
                content_preview = (p.get('content_text', '') or p.get('post_type', 'Post'))[:20]
                display = f"{acct_name}: {content_preview}"
            item = QTreeWidgetItem(posts_root, [display])
            item.setData(0, Qt.ItemDataRole.UserRole, ('post', p['id']))
        style_category(posts_root, len(all_posts))

        # Expand subjects by default if they have items
        if subjects_root.childCount() > 0:
            subjects_root.setExpanded(True)

    def on_tree_item_clicked(self, item, column):
        """Handle tree item click"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        entity_type, entity_id = data
        if entity_type == 'category':
            # Toggle expand/collapse when clicking category header
            item.setExpanded(not item.isExpanded())
            return

        if entity_type == 'subject':
            self.on_subject_selected(entity_id)
        elif entity_type == 'gang':
            self.on_gang_selected(entity_id)
        elif entity_type == 'event':
            self.on_event_selected(entity_id)
        elif entity_type == 'location':
            self.on_location_selected(entity_id)
        elif entity_type == 'vehicle':
            self.on_vehicle_selected(entity_id)
        elif entity_type == 'weapon':
            self.on_weapon_selected(entity_id)
        elif entity_type == 'charge':
            self.on_charge_selected(entity_id)
        elif entity_type == 'graffiti':
            self.on_graffiti_selected(entity_id)
        elif entity_type == 'intel':
            self.on_intel_selected(entity_id)
        elif entity_type == 'online_account':
            self.on_online_account_selected(entity_id)
        elif entity_type == 'dns':
            self.on_dns_selected(entity_id)
        elif entity_type == 'phone':
            self.on_phone_selected(entity_id)
        elif entity_type == 'post':
            self.on_post_selected(entity_id)

    def refresh_graph(self, entity_type=None, entity_id=None):
        """Refresh the graph - show connected web for selected entity, or all if none selected"""
        if entity_type and entity_id:
            # Show only the connected web for this entity
            data = self.db.get_focused_graph_data(entity_type, entity_id)
            self.graph.update_graph(data)
            name = self.db._get_entity_display_name(entity_type, entity_id)
            self.graph_info_label.setText(f"Web for: {name} ({len(data['nodes'])} connected)")
        else:
            # Show all entities
            data = self.db.get_graph_data()
            self.graph.update_graph(data)
            self.graph_info_label.setText(f"Showing all entities ({len(data['nodes'])} nodes)")

    def refresh_checklist(self):
        """Refresh checklist for current subject"""
        self.checklist_tree.blockSignals(True)
        self.checklist_tree.clear()

        checklist_by_cat = self.db.get_checklist_by_category()
        progress = {}
        if self.current_subject_id:
            progress = self.db.get_subject_checklist_progress(self.current_subject_id)

        for category, items in checklist_by_cat.items():
            cat_item = QTreeWidgetItem(self.checklist_tree, [category])
            cat_item.setData(0, Qt.ItemDataRole.UserRole, ('category', category))
            cat_item.setExpanded(True)

            for item in items:
                # Show link icon for items with URLs
                display_name = item['name']
                if item.get('url'):
                    display_name = f"🔗 {item['name']}"

                check_item = QTreeWidgetItem(cat_item, [display_name])
                check_item.setData(0, Qt.ItemDataRole.UserRole, ('item', item['id']))
                check_item.setFlags(check_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

                # Set tooltip with URL and description
                tooltip_parts = []
                if item.get('description'):
                    tooltip_parts.append(item['description'])
                if item.get('url'):
                    tooltip_parts.append(f"URL: {item['url']}")
                    tooltip_parts.append("Double-click to open")
                else:
                    tooltip_parts.append("(No URL - internal system)")
                check_item.setToolTip(0, "\n".join(tooltip_parts))

                # Set checked state from progress
                if item['id'] in progress and progress[item['id']]['completed']:
                    check_item.setCheckState(0, Qt.CheckState.Checked)
                else:
                    check_item.setCheckState(0, Qt.CheckState.Unchecked)

        self.checklist_tree.blockSignals(False)

        # Resize tree to fit contents (no internal scroll)
        self.checklist_tree.updateGeometry()

    def on_checklist_item_changed(self, item, column):
        """Handle checklist item check/uncheck"""
        if not self.current_subject_id:
            QMessageBox.warning(self, "No Subject", "Select a subject first to track checklist progress.")
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data[0] != 'item':
            return

        item_id = data[1]
        completed = item.checkState(0) == Qt.CheckState.Checked
        self.db.update_checklist_progress(self.current_subject_id, item_id, completed)

    def on_checklist_item_double_clicked(self, item, column):
        """Handle double-click on checklist item to open URL"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data[0] != 'item':
            return

        item_id = data[1]
        # Get the URL for this checklist item from the database
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT url FROM checklist_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()

        if row and row['url']:
            url = row['url']
            QDesktopServices.openUrl(QUrl(url))

    def on_search(self, text):
        self.refresh_tree(text)

    def on_subject_selected(self, subject_id):
        self.current_subject_id = subject_id
        self.profile.show_subject(subject_id)
        self.refresh_graph('subject', subject_id)
        self.refresh_checklist()

    # ============ DORKING ============

    # ============ CHECKLIST MANAGEMENT ============

    def add_checklist_item(self):
        """Add a new checklist item"""
        name, ok = QInputDialog.getText(self, "Add Checklist Item", "Item name:")
        if not ok or not name.strip():
            return

        # Get category
        categories = list(self.db.get_checklist_by_category().keys())
        category, ok = QInputDialog.getItem(self, "Category", "Select category:", categories, 0, True)
        if not ok:
            return

        # Optional URL
        url, _ = QInputDialog.getText(self, "URL (optional)", "URL to open when clicked:")

        self.db.add_checklist_item(category, name.strip(), url=url.strip())
        self.refresh_checklist()
        self.status.showMessage(f"Added checklist item: {name}")

    def edit_checklist(self):
        """Open checklist editor dialog"""
        dialog = ChecklistEditorDialog(self, self.db)
        if dialog.exec():
            self.refresh_checklist()

    def on_gang_selected(self, gang_id):
        self.profile.show_gang(gang_id)
        self.refresh_graph('gang', gang_id)

    def on_location_selected(self, location_id):
        self.profile.show_location(location_id)
        self.refresh_graph('location', location_id)

    def on_event_selected(self, event_id):
        self.profile.show_event(event_id)
        self.refresh_graph('event', event_id)

    def on_charge_selected(self, charge_id):
        self.profile.show_charge(charge_id)
        self.refresh_graph('charge', charge_id)

    def on_graffiti_selected(self, graffiti_id):
        self.profile.show_graffiti(graffiti_id)
        self.refresh_graph('graffiti', graffiti_id)

    def on_intel_selected(self, intel_id):
        self.profile.show_intel(intel_id)

    def on_vehicle_selected(self, vehicle_id):
        self.profile.show_vehicle(vehicle_id)
        self.refresh_graph('vehicle', vehicle_id)

    def on_weapon_selected(self, weapon_id):
        self.profile.show_weapon(weapon_id)
        self.refresh_graph('weapon', weapon_id)

    def on_online_account_selected(self, account_id):
        self.profile.show_online_account(account_id)
        self.refresh_graph('online_account', account_id)

    def on_dns_selected(self, dns_id):
        self.profile.show_dns_investigation(dns_id)
        self.refresh_graph('dns', dns_id)

    def on_phone_selected(self, phone_id):
        self.profile.show_tracked_phone(phone_id)
        self.refresh_graph('phone', phone_id)

    def on_post_selected(self, post_id):
        self.profile.show_post(post_id)
        self.refresh_graph('post', post_id)

    def on_graph_delete_requested(self, entity_type: str, entity_id: str):
        """Handle delete request from graph double-click"""
        # Types that need cascade delete dialog
        cascade_types = ['subject', 'event', 'vehicle', 'weapon', 'gang', 'location', 'online_account']

        if entity_type in cascade_types:
            dialog = CascadeDeleteDialog(self, self.db, entity_type, entity_id)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                items_to_delete = dialog.get_items_to_delete()
                for item_type, item_id in items_to_delete:
                    self.profile._delete_item(item_type, item_id)
                self.refresh_all()
                self.status.showMessage(f"Deleted {entity_type}")
        else:
            # Simple delete for types without cascade relationships
            reply = QMessageBox.question(self, "Delete", f"Delete this {entity_type}?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.profile._delete_item(entity_type, entity_id)
                self.refresh_all()
                self.status.showMessage(f"Deleted {entity_type}")

    def on_graph_edge_clicked(self, from_type: str, from_id: str, to_type: str, to_id: str):
        """Handle click on graph edge (connection line) - show edit dialog"""
        dialog = EdgeEditDialog(self, self.db, from_type, from_id, to_type, to_id)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.link_deleted:
            self.refresh_graph()  # Only refresh if link was actually deleted

    def open_add_link_dialog(self):
        """Open dialog to add a new link between entities"""
        # If there's a currently selected entity, use that as the source
        if self.profile.current_type and self.profile.current_id:
            source_type = self.profile.current_type
            source_id = self.profile.current_id
            source_name = self.db._get_entity_display_name(source_type, source_id)
            dialog = UniversalLinkDialog(self, self.db, source_type, source_id, source_name)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.link_added:
                self.refresh_graph()  # Only refresh if link was actually added
        else:
            QMessageBox.information(self, "Select Entity First",
                                    "Please select an entity from the left panel or graph first,\n"
                                    "then click 'Add Link' to connect it to other entities.")

    def on_graph_node_clicked(self, entity_type: str, entity_id: str, label: str):
        """Handle single-click on graph node - show full profile just like tree click"""
        self._selected_node = (entity_type, entity_id)
        self.view_node_btn.setEnabled(True)

        # Show the full profile in the right panel (same as tree click)
        if entity_type == 'subject':
            self.on_subject_selected(entity_id)
        elif entity_type == 'gang':
            self.on_gang_selected(entity_id)
        elif entity_type == 'event':
            self.on_event_selected(entity_id)
        elif entity_type == 'location':
            self.on_location_selected(entity_id)
        elif entity_type == 'vehicle':
            self.on_vehicle_selected(entity_id)
        elif entity_type == 'weapon':
            self.on_weapon_selected(entity_id)
        elif entity_type == 'charge':
            self.on_charge_selected(entity_id)
        elif entity_type == 'graffiti':
            self.on_graffiti_selected(entity_id)
        elif entity_type == 'intel':
            self.on_intel_selected(entity_id)
        elif entity_type == 'online_account':
            self.on_online_account_selected(entity_id)
        elif entity_type == 'dns':
            self.on_dns_selected(entity_id)
        elif entity_type == 'phone':
            self.on_phone_selected(entity_id)
        elif entity_type == 'post':
            self.on_post_selected(entity_id)

        # Update the node info label with basic info
        self.node_section.setExpanded(True)
        self.node_info_label.setText(f"<b>{label}</b><br><small style='color:#6b5b8a;'>Type: {entity_type.upper()}</small>")

    def _update_profile_for_node(self, entity_type: str, entity_id: str):
        """Update the profile panel for the selected node so Edit/Delete buttons work"""
        # Auto-expand the Full Profile section
        self.profile_section.setExpanded(True)

        if entity_type == 'subject':
            self.profile.show_subject(entity_id)
        elif entity_type == 'gang':
            self.profile.show_gang(entity_id)
        elif entity_type == 'location':
            self.profile.show_location(entity_id)
        elif entity_type == 'event':
            self.profile.show_event(entity_id)
        elif entity_type == 'vehicle':
            self.profile.show_vehicle(entity_id)
        elif entity_type == 'weapon':
            self.profile.show_weapon(entity_id)
        elif entity_type == 'charge':
            self.profile.show_charge(entity_id)
        elif entity_type == 'graffiti':
            self.profile.show_graffiti(entity_id)
        elif entity_type == 'intel':
            self.profile.show_intel(entity_id)
        elif entity_type == 'online_account':
            self.profile.show_online_account(entity_id)
        elif entity_type == 'dns':
            self.profile.show_dns_investigation(entity_id)
        elif entity_type == 'phone':
            self.profile.show_tracked_phone(entity_id)
        elif entity_type == 'post':
            self.profile.show_post(entity_id)

    def view_selected_node(self):
        """View full profile of selected node"""
        if not self._selected_node:
            return
        entity_type, entity_id = self._selected_node
        if entity_type == 'subject':
            self.profile.show_subject(entity_id)
        elif entity_type == 'gang':
            self.profile.show_gang(entity_id)
        elif entity_type == 'location':
            self.profile.show_location(entity_id)
        elif entity_type == 'event':
            self.profile.show_event(entity_id)
        elif entity_type == 'vehicle':
            self.profile.show_vehicle(entity_id)
        elif entity_type == 'weapon':
            self.profile.show_weapon(entity_id)
        elif entity_type == 'charge':
            self.profile.show_charge(entity_id)
        elif entity_type == 'online_account':
            self.profile.show_online_account(entity_id)
        elif entity_type == 'dns':
            self.profile.show_dns_investigation(entity_id)
        elif entity_type == 'phone':
            self.profile.show_tracked_phone(entity_id)

    def show_add_new_dialog(self):
        """Show the unified Add New dialog and process selected entity types"""
        dialog = AddNewDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected_types = dialog.get_selected_types()
        if not selected_types:
            return

        created_count = 0
        for entity_type in selected_types:
            result = self._create_entity_dialog(entity_type)
            if result:
                created_count += 1

        if created_count > 0:
            self.refresh_all()
            self.status.showMessage(f"Created {created_count} record(s)")

    def _handle_dialog_redirect(self, dialog):
        """Check if dialog wants to redirect to existing record and navigate there."""
        if hasattr(dialog, 'redirect_to') and dialog.redirect_to:
            entity_type, entity_id = dialog.redirect_to
            self.refresh_all()
            # Navigate to existing record and open edit dialog
            if entity_type == 'location':
                self.on_location_selected(entity_id)
            elif entity_type == 'vehicle':
                self.on_vehicle_selected(entity_id)
            elif entity_type == 'online_account':
                self.on_online_account_selected(entity_id)
            elif entity_type == 'phone':
                self.on_phone_selected(entity_id)
            elif entity_type == 'dns':
                self.on_dns_selected(entity_id)
            # Open edit dialog for the existing record
            self.edit_entity(entity_type, entity_id)
            return True
        return False

    def _create_entity_dialog(self, entity_type: str) -> bool:
        """Open the appropriate dialog for an entity type. Returns True if created."""
        if entity_type == 'subject':
            dialog = SubjectIntakeDialog(self, self.db)
            return dialog.exec() == QDialog.DialogCode.Accepted
        elif entity_type == 'gang':
            dialog = GangDialog(self, self.db)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                name = data.pop('name')
                photo_path = data.pop('photo', None)
                gang_id = self.db.add_gang(name, **data)
                if photo_path and gang_id:
                    self.db.add_media('gang', gang_id, photo_path, file_type='image')
                return True
            return False
        elif entity_type == 'event':
            dialog = EventIntakeDialog(self, self.db)
            return dialog.exec() == QDialog.DialogCode.Accepted
        elif entity_type == 'location':
            dialog = LocationDialog(self, self.db)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                return True
            return self._handle_dialog_redirect(dialog)
        elif entity_type == 'online_account':
            dialog = OnlineAccountDialog(self, self.db)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                return True
            return self._handle_dialog_redirect(dialog)
        elif entity_type == 'dns':
            dialog = DNSInvestigationDialog(self, self.db)
            return dialog.exec() == QDialog.DialogCode.Accepted
        elif entity_type == 'phone':
            dialog = TrackedPhoneDialog(self, self.db)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                return True
            return self._handle_dialog_redirect(dialog)
        elif entity_type == 'vehicle':
            dialog = VehicleDialog(self, self.db)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                return True
            return self._handle_dialog_redirect(dialog)
        elif entity_type == 'weapon':
            dialog = WeaponDialog(self, self.db)
            return dialog.exec() == QDialog.DialogCode.Accepted
        elif entity_type == 'charge':
            dialog = ChargeDialog(self, self.db)
            return dialog.exec() == QDialog.DialogCode.Accepted
        elif entity_type == 'graffiti':
            dialog = GraffitiDialog(self, self.db)
            return dialog.exec() == QDialog.DialogCode.Accepted
        elif entity_type == 'intel':
            dialog = IntelReportDialog(self, self.db)
            return dialog.exec() == QDialog.DialogCode.Accepted
        return False

    def new_event(self):
        dialog = EventIntakeDialog(self, self.db)
        if dialog.exec():
            self.refresh_all()
            self.status.showMessage("Event created")

    def new_subject(self):
        dialog = SubjectIntakeDialog(self, self.db)
        if dialog.exec():
            self.refresh_all()
            self.status.showMessage("Subject created")

    def new_gang(self):
        dialog = GangDialog(self, self.db)
        if dialog.exec():
            data = dialog.get_data()
            name = data.pop('name')
            photo_path = data.pop('photo', None)
            gang_id = self.db.add_gang(name, **data)

            # Register photo in media table (already copied by PhotoUploadWidget)
            if photo_path and gang_id:
                self.db.add_media('gang', gang_id, photo_path, file_type='image')

            self.refresh_all()

    def new_charge(self):
        dialog = ChargeDialog(self, self.db)
        if dialog.exec():
            self.refresh_all()
            self.status.showMessage("Charge created")

    def new_graffiti(self):
        dialog = GraffitiDialog(self, self.db)
        if dialog.exec():
            self.refresh_all()
            self.status.showMessage("Graffiti created")

    def new_intel(self):
        dialog = IntelReportDialog(self, self.db)
        if dialog.exec():
            self.refresh_all()
            self.status.showMessage("Intel report created")

    def new_vehicle(self):
        dialog = VehicleDialog(self, self.db)
        if dialog.exec():
            self.refresh_all()
            self.status.showMessage("Vehicle added")
        else:
            self._handle_dialog_redirect(dialog)

    def new_location(self):
        dialog = LocationDialog(self, self.db)
        if dialog.exec():
            self.refresh_all()
            self.status.showMessage("Location added")
        else:
            self._handle_dialog_redirect(dialog)

    def new_weapon(self):
        dialog = WeaponDialog(self, self.db)
        if dialog.exec():
            self.refresh_all()
            self.status.showMessage("Weapon added")

    def new_online_account(self):
        dialog = OnlineAccountDialog(self, self.db)
        if dialog.exec():
            self.refresh_all()
            self.status.showMessage("Online account added")
        else:
            self._handle_dialog_redirect(dialog)

    def new_dns(self):
        dialog = DNSInvestigationDialog(self, self.db)
        if dialog.exec():
            self.refresh_all()
            self.status.showMessage("DNS investigation added")
        else:
            self._handle_dialog_redirect(dialog)

    def new_tracked_phone(self):
        dialog = TrackedPhoneDialog(self, self.db)
        if dialog.exec():
            self.refresh_all()
            self.status.showMessage("Tracked phone added")
        else:
            self._handle_dialog_redirect(dialog)

    def edit_entity(self, entity_type, entity_id):
        if entity_type == 'subject':
            subject = self.db.get_subject(entity_id)
            dialog = SubjectIntakeDialog(self, self.db, subject)
            if dialog.exec():
                self.refresh_all()
                self.profile.show_subject(entity_id)
        elif entity_type == 'gang':
            gang = self.db.get_gang(entity_id)
            dialog = GangDialog(self, self.db, gang)
            if dialog.exec():
                data = dialog.get_data()
                photo_path = data.pop('photo', None)
                self.db.update_gang(entity_id, **data)
                if photo_path:
                    self.db.add_media('gang', entity_id, photo_path, file_type='image')
                self.refresh_all()
                self.profile.show_gang(entity_id)
        elif entity_type == 'vehicle':
            vehicle = self.db.get_vehicle(entity_id)
            dialog = VehicleDialog(self, self.db, vehicle)
            if dialog.exec():
                self.refresh_all()
                self.profile.show_vehicle(entity_id)
        elif entity_type == 'weapon':
            weapon = self.db.get_weapon(entity_id)
            dialog = WeaponDialog(self, self.db, weapon)
            if dialog.exec():
                self.refresh_all()
                self.profile.show_weapon(entity_id)
        elif entity_type == 'location':
            location = self.db.get_location(entity_id)
            dialog = LocationDialog(self, self.db, location)
            if dialog.exec():
                self.refresh_all()
                self.profile.show_location(entity_id)
        elif entity_type == 'online_account':
            account = self.db.get_online_account(entity_id)
            dialog = OnlineAccountDialog(self, self.db, account)
            if dialog.exec():
                self.refresh_all()
                self.profile.show_online_account(entity_id)
        elif entity_type == 'dns':
            dns = self.db.get_dns_investigation(entity_id)
            dialog = DNSInvestigationDialog(self, self.db, dns)
            if dialog.exec():
                self.refresh_all()
                self.profile.show_dns_investigation(entity_id)
        elif entity_type == 'phone':
            phone = self.db.get_tracked_phone(entity_id)
            dialog = TrackedPhoneDialog(self, self.db, phone)
            if dialog.exec():
                self.refresh_all()
                self.profile.show_tracked_phone(entity_id)
        elif entity_type == 'post':
            post = self.db.get_account_post(entity_id)
            dialog = AccountPostDialog(self, self.db, post_data=post)
            if dialog.exec():
                self.refresh_all()
                self.profile.show_post(entity_id)
        elif entity_type == 'charge':
            charge = self.db.get_charge(entity_id)
            dialog = ChargeDialog(self, self.db, charge)
            if dialog.exec():
                self.refresh_all()
                self.profile.show_charge(entity_id)
        elif entity_type == 'graffiti':
            graffiti = self.db.get_graffiti(entity_id)
            dialog = GraffitiDialog(self, self.db, graffiti)
            if dialog.exec():
                self.refresh_all()
                self.profile.show_graffiti(entity_id)
        elif entity_type == 'intel':
            intel = self.db.get_intel_report(entity_id)
            dialog = IntelReportDialog(self, self.db, intel)
            if dialog.exec():
                self.refresh_all()
                self.profile.show_intel(entity_id)

    def export_data(self):
        """Export all case data with AES-256 encryption + media files as zip."""
        import zipfile
        import tempfile
        from encryption import encrypt_json

        # Get encryption password
        password, ok = QInputDialog.getText(
            self, "Encryption Password",
            "Enter a password to encrypt the export:\n(You'll need this to import later)",
            QLineEdit.EchoMode.Password
        )
        if not ok or not password:
            return

        # Confirm password
        confirm, ok = QInputDialog.getText(
            self, "Confirm Password",
            "Confirm encryption password:",
            QLineEdit.EchoMode.Password
        )
        if not ok or confirm != password:
            QMessageBox.warning(self, "Error", "Passwords do not match.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export Case Data (with Photos)",
                                               "tracker_export.zip", "Tracker Export (*.zip)")
        if not path:
            return

        cursor = self.db.conn.cursor()

        # Get all data from all tables
        data = {
            'export_version': '3.1',  # Full database export
            'export_date': datetime.now().isoformat(),
            'encryption': 'AES-256-GCM',
            'subjects': self.db.get_all_subjects(),
            'gangs': self.db.get_all_gangs(),
            'locations': self.db.get_all_locations(),
            'events': self.db.get_all_events(),
            'vehicles': self.db.get_all_vehicles(),
            'weapons': self.db.get_all_weapons(),
            'charges': self.db.get_all_charges(),
            'graffiti': self.db.get_all_graffiti(),
            'intel_reports': self.db.get_all_intel_reports(),
            'online_accounts': self.db.get_all_online_accounts(),
            'dns_investigations': self.db.get_all_dns_investigations(),
            'tracked_phones': self.db.get_all_tracked_phones(),
            'entity_links': self.db.get_all_entity_links(),
        }

        # Get linking/detail tables including media
        tables = ['subject_gangs', 'subject_locations', 'subject_events',
                  'subject_vehicles', 'subject_weapons', 'gang_events',
                  'gang_locations', 'event_vehicles', 'event_weapons',
                  'subject_associations', 'social_profiles', 'phone_numbers',
                  'emails', 'family_members', 'tattoos', 'evidence',
                  'charge_affiliates', 'case_numbers', 'state_ids', 'employment',
                  'checklist_items', 'checklist_progress', 'media',
                  'account_posts', 'account_associations', 'account_vehicles',
                  'custom_links']

        for table in tables:
            try:
                cursor.execute(f"SELECT * FROM {table}")
                data[table] = [dict(row) for row in cursor.fetchall()]
            except:
                data[table] = []

        try:
            # Create zip file with encrypted data + media files
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add encrypted JSON data
                encrypted = encrypt_json(data, password)
                zf.writestr('tracker_data.enc', encrypted)

                # Add all media files from data/media folder
                media_base = os.path.join(get_app_dir(), 'data', 'media')
                if os.path.exists(media_base):
                    for root, dirs, files in os.walk(media_base):
                        for file in files:
                            file_path = os.path.join(root, file)
                            # Store with relative path inside zip
                            arc_name = os.path.relpath(file_path, get_app_dir())
                            zf.write(file_path, arc_name)

            self.status.showMessage(f"Exported to {path}")
            QMessageBox.information(self, "Export Complete",
                                    f"Case data + photos exported to:\n{path}\n\n"
                                    "This file includes all photos and can be shared with your team.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")

    def import_data(self):
        """Import case data from zip (with photos), encrypted, or JSON file."""
        import uuid
        import zipfile
        import tempfile
        from encryption import is_encrypted, decrypt_json

        path, _ = QFileDialog.getOpenFileName(self, "Import Case Data",
                                               "", "Tracker Export (*.zip);;Encrypted (*.enc);;JSON (*.json);;All Files (*)")
        if not path:
            return

        data = None
        media_extracted = False

        try:
            # Check if it's a zip file (new format with photos)
            if path.lower().endswith('.zip') and zipfile.is_zipfile(path):
                # Get decryption password first
                password, ok = QInputDialog.getText(
                    self, "Decryption Password",
                    "Enter the password to decrypt this export:",
                    QLineEdit.EchoMode.Password
                )
                if not ok or not password:
                    return

                with zipfile.ZipFile(path, 'r') as zf:
                    # Extract and decrypt the data file
                    if 'tracker_data.enc' in zf.namelist():
                        encrypted_data = zf.read('tracker_data.enc')
                        try:
                            data = decrypt_json(encrypted_data, password)
                        except ValueError:
                            QMessageBox.critical(self, "Decryption Error",
                                                "Wrong password or corrupted file.")
                            return

                        # Extract media files to app directory
                        app_dir = get_app_dir()
                        for name in zf.namelist():
                            if name.startswith('data/media/') and not name.endswith('/'):
                                # Extract to local media folder
                                dest_path = os.path.join(app_dir, name)
                                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                                with zf.open(name) as src, open(dest_path, 'wb') as dst:
                                    dst.write(src.read())
                        media_extracted = True
                    else:
                        QMessageBox.critical(self, "Import Error",
                                            "Invalid export file - missing data.")
                        return

            # Check if file is encrypted (legacy format)
            elif is_encrypted(path):
                password, ok = QInputDialog.getText(
                    self, "Decryption Password",
                    "Enter the password to decrypt this file:",
                    QLineEdit.EchoMode.Password
                )
                if not ok or not password:
                    return

                with open(path, 'rb') as f:
                    encrypted_data = f.read()

                try:
                    data = decrypt_json(encrypted_data, password)
                except ValueError:
                    QMessageBox.critical(self, "Decryption Error",
                                        "Wrong password or corrupted file.")
                    return
            else:
                # Try reading as plain JSON (legacy format)
                with open(path, 'r') as f:
                    data = json.load(f)

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to read file:\n{str(e)}")
            return

        # Show merge dialog
        dialog = MergeImportDialog(self, self.db, data)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Get options
        skip_existing = dialog.skip_existing.isChecked()
        update_existing = dialog.update_existing.isChecked()
        remap_ids = dialog.remap_ids.isChecked()

        try:
            cursor = self.db.conn.cursor()
            imported_counts = {}
            updated_counts = {}

            # ID mapping for remap mode
            id_map = {
                'subjects': {},
                'gangs': {},
                'locations': {},
                'events': {},
                'vehicles': {},
                'weapons': {},
                'charges': {},
                'graffiti': {},
                'intel_reports': {},
                'online_accounts': {},
                'dns_investigations': {},
                'tracked_phones': {},
                'entity_links': {},
            }

            # Import main entities
            entity_tables = {
                'subjects': 'subjects',
                'gangs': 'gangs',
                'locations': 'locations',
                'events': 'events',
                'vehicles': 'vehicles',
                'weapons': 'weapons',
                'charges': 'charges',
                'graffiti': 'graffiti',
                'intel_reports': 'intel_reports',
                'online_accounts': 'online_accounts',
                'dns_investigations': 'dns_investigations',
                'tracked_phones': 'tracked_phones',
            }

            for key, table in entity_tables.items():
                if key not in data:
                    continue

                count = 0
                updated = 0

                for item in data[key]:
                    old_id = item.get('id')

                    if remap_ids:
                        # Generate new ID and track mapping
                        new_id = str(uuid.uuid4())
                        id_map[key][old_id] = new_id
                        item['id'] = new_id

                        # Remap embedded FKs in primary entity tables
                        for col, map_key in entity_map.items():
                            if col in item and item[col] and map_key in id_map:
                                old_fk = item[col]
                                if old_fk in id_map[map_key]:
                                    item[col] = id_map[map_key][old_fk]

                    try:
                        cols = ', '.join(item.keys())
                        placeholders = ', '.join(['?' for _ in item])

                        if update_existing and not remap_ids:
                            # Try update first
                            update_cols = [f"{k} = ?" for k in item.keys() if k != 'id']
                            if update_cols:
                                cursor.execute(f"UPDATE {table} SET {', '.join(update_cols)} WHERE id = ?",
                                               [v for k, v in item.items() if k != 'id'] + [item.get('id')])
                                if cursor.rowcount > 0:
                                    updated += 1
                                    continue

                        # Insert
                        if skip_existing:
                            cursor.execute(f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})",
                                           list(item.values()))
                        else:
                            cursor.execute(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})",
                                           list(item.values()))

                        if cursor.rowcount > 0:
                            count += 1
                    except Exception as e:
                        pass

                if count > 0:
                    imported_counts[key] = count
                if updated > 0:
                    updated_counts[key] = updated

            # Import linking tables with ID remapping if needed
            link_tables = {
                'subject_gangs': ('subject_id', 'gang_id'),
                'subject_locations': ('subject_id', 'location_id'),
                'subject_events': ('subject_id', 'event_id'),
                'subject_vehicles': ('subject_id', 'vehicle_id'),
                'subject_weapons': ('subject_id', 'weapon_id'),
                'gang_events': ('gang_id', 'event_id'),
                'gang_locations': ('gang_id', 'location_id'),
                'event_vehicles': ('event_id', 'vehicle_id'),
                'event_weapons': ('event_id', 'weapon_id'),
                'subject_associations': ('subject1_id', 'subject2_id'),
                'social_profiles': ('subject_id', None),
                'phone_numbers': ('subject_id', None),
                'emails': ('subject_id', None),
                'family_members': ('subject_id', None),
                'tattoos': ('subject_id', None),
                'evidence': ('event_id', None),
                'charge_affiliates': ('charge_id', 'subject_id'),
                'case_numbers': ('subject_id', None),
                'state_ids': ('subject_id', None),
                'employment': ('subject_id', None),
                'checklist_items': (None, None),
                'checklist_progress': ('subject_id', None),
                'media': (None, None),  # polymorphic - handled separately
                'account_posts': ('account_id', None),
                'account_associations': ('account1_id', 'account2_id'),
                'account_vehicles': ('account_id', 'vehicle_id'),
                'custom_links': (None, None),  # polymorphic - handled separately
                'entity_links': (None, None),  # polymorphic - handled separately
            }

            entity_map = {
                'subject_id': 'subjects',
                'subject1_id': 'subjects',
                'subject2_id': 'subjects',
                'gang_id': 'gangs',
                'location_id': 'locations',
                'event_id': 'events',
                'vehicle_id': 'vehicles',
                'weapon_id': 'weapons',
                'charge_id': 'charges',
                'account_id': 'online_accounts',
                'account1_id': 'online_accounts',
                'account2_id': 'online_accounts',
            }

            # Map entity_type strings to id_map keys for polymorphic tables
            type_to_map = {
                'subject': 'subjects', 'gang': 'gangs', 'location': 'locations',
                'event': 'events', 'vehicle': 'vehicles', 'weapon': 'weapons',
                'charge': 'charges', 'graffiti': 'graffiti', 'intel': 'intel_reports',
                'online_account': 'online_accounts', 'dns': 'dns_investigations',
                'phone': 'tracked_phones', 'post': 'online_accounts',
            }

            # Deduplication keys: which fields identify a unique record
            # (beyond just the primary key ID)
            dedup_keys = {
                'phone_numbers': ('subject_id', 'number'),
                'emails': ('subject_id', 'email'),
                'social_profiles': ('subject_id', 'platform', 'url'),
                'case_numbers': ('subject_id', 'case_number'),
                'state_ids': ('subject_id', 'id_number', 'id_type'),
                'employment': ('subject_id', 'employer'),
                'tattoos': ('subject_id', 'description', 'body_location'),
                'family_members': ('subject_id', 'relationship', 'family_name'),
                'media': ('entity_type', 'entity_id', 'file_path'),
            }

            for table, (fk1, fk2) in link_tables.items():
                if table not in data:
                    continue

                count = 0
                for item in data[table]:
                    # Remap IDs if needed
                    if remap_ids:
                        # Standard FK remapping
                        if fk1 and fk1 in entity_map:
                            entity = entity_map[fk1]
                            old_fk = item.get(fk1)
                            if old_fk and entity in id_map and old_fk in id_map[entity]:
                                item[fk1] = id_map[entity][old_fk]
                        if fk2 and fk2 in entity_map:
                            entity = entity_map[fk2]
                            old_fk = item.get(fk2)
                            if old_fk and entity in id_map and old_fk in id_map[entity]:
                                item[fk2] = id_map[entity][old_fk]

                        # Polymorphic table remapping (media, entity_links, custom_links)
                        if table == 'media':
                            etype = item.get('entity_type', '')
                            map_key = type_to_map.get(etype)
                            if map_key and map_key in id_map:
                                old_eid = item.get('entity_id')
                                if old_eid and old_eid in id_map[map_key]:
                                    item['entity_id'] = id_map[map_key][old_eid]
                        elif table == 'entity_links':
                            for prefix in ('source', 'target'):
                                etype = item.get(f'{prefix}_type', '')
                                map_key = type_to_map.get(etype)
                                if map_key and map_key in id_map:
                                    old_eid = item.get(f'{prefix}_id')
                                    if old_eid and old_eid in id_map[map_key]:
                                        item[f'{prefix}_id'] = id_map[map_key][old_eid]
                        elif table == 'custom_links':
                            etype = item.get('entity_type', '')
                            map_key = type_to_map.get(etype)
                            if map_key and map_key in id_map:
                                old_eid = item.get('entity_id')
                                if old_eid and old_eid in id_map[map_key]:
                                    item['entity_id'] = id_map[map_key][old_eid]

                    try:
                        # Check for content-based duplicates
                        if table in dedup_keys:
                            keys = dedup_keys[table]
                            where_parts = [f"{k} = ?" if item.get(k) else f"{k} IS NULL" for k in keys]
                            where_vals = [item[k] for k in keys if item.get(k)]
                            if any(item.get(k) for k in keys):
                                cursor.execute(
                                    f"SELECT COUNT(*) FROM {table} WHERE {' AND '.join(where_parts)}",
                                    where_vals)
                                if cursor.fetchone()[0] > 0:
                                    continue  # Skip duplicate

                        # Generate new ID to avoid PK collision
                        if remap_ids and 'id' in item:
                            item['id'] = str(uuid.uuid4())[:8]

                        cols = ', '.join(item.keys())
                        placeholders = ', '.join(['?' for _ in item])
                        cursor.execute(f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})",
                                       list(item.values()))
                        if cursor.rowcount > 0:
                            count += 1
                    except:
                        pass

                if count > 0:
                    imported_counts[table] = count

            self.db.conn.commit()
            self.refresh_all()

            # Show summary
            summary = "Merge Import Complete\n"
            summary += "=" * 30 + "\n\n"

            if remap_ids:
                summary += "Mode: Full merge (new IDs generated)\n\n"

            if imported_counts:
                summary += "New records imported:\n"
                for key, count in imported_counts.items():
                    summary += f"  • {key}: {count}\n"
            else:
                summary += "No new records imported.\n"

            if updated_counts:
                summary += "\nExisting records updated:\n"
                for key, count in updated_counts.items():
                    summary += f"  • {key}: {count}\n"

            if not imported_counts and not updated_counts:
                summary = "No changes made - all data already exists."

            if media_extracted:
                summary += "\n\nMedia files (photos) were also imported."

            QMessageBox.information(self, "Import Complete", summary)
            self.status.showMessage("Import complete")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import:\n{str(e)}")

    def backup_database(self):
        """Create an encrypted backup of the database file"""
        from datetime import datetime
        from encryption import encrypt_file

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"tracker_backup_{timestamp}.enc"

        # Get encryption password
        password, ok = QInputDialog.getText(
            self, "Backup Encryption Password",
            "Enter a password to encrypt the backup:\n(You'll need this to restore later)",
            QLineEdit.EchoMode.Password
        )
        if not ok or not password:
            return

        # Confirm password
        confirm, ok = QInputDialog.getText(
            self, "Confirm Password",
            "Confirm encryption password:",
            QLineEdit.EchoMode.Password
        )
        if not ok or confirm != password:
            QMessageBox.warning(self, "Error", "Passwords do not match.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Backup Database (Encrypted)",
                                               default_name, "Encrypted Backup (*.enc)")
        if path:
            try:
                encrypt_file(self.db.db_path, path, password)
                self.status.showMessage(f"Database backed up (encrypted) to {path}")
                QMessageBox.information(self, "Backup Complete",
                                        f"Database backed up with AES-256 encryption to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Backup Error", f"Failed to backup:\n{str(e)}")

    def restore_database(self):
        """Restore database from an encrypted backup"""
        from encryption import is_encrypted, decrypt_file
        import shutil

        path, _ = QFileDialog.getOpenFileName(self, "Restore Database from Backup",
                                               "", "Encrypted Backup (*.enc);;All Files (*)")
        if not path:
            return

        # Warn user
        reply = QMessageBox.warning(
            self, "Restore Database",
            "This will REPLACE your current database with the backup.\n\n"
            "All current data will be lost!\n\n"
            "Are you sure you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if is_encrypted(path):
                # Get decryption password
                password, ok = QInputDialog.getText(
                    self, "Decryption Password",
                    "Enter the password to decrypt this backup:",
                    QLineEdit.EchoMode.Password
                )
                if not ok or not password:
                    return

                # Close current database connection
                self.db.close()

                try:
                    decrypt_file(path, self.db.db_path, password)
                except ValueError:
                    # Reopen database on failure
                    self.db = TrackerDB(self.db.db_path)
                    QMessageBox.critical(self, "Restore Error",
                                        "Wrong password or corrupted backup file.")
                    return

                # Reopen database
                self.db = TrackerDB(self.db.db_path)
            else:
                # Plain database file
                self.db.close()
                shutil.copy2(path, self.db.db_path)
                self.db = TrackerDB(self.db.db_path)

            self.refresh_all()
            self.status.showMessage("Database restored from backup")
            QMessageBox.information(self, "Restore Complete",
                                    "Database has been restored from backup.")
        except Exception as e:
            QMessageBox.critical(self, "Restore Error", f"Failed to restore:\n{str(e)}")

    def closeEvent(self, event):
        """Handle window close - encrypt database before exiting."""
        self.db.close()
        self._encrypt_database()
        event.accept()


def main():
    """
    Application entry point with authentication flow.

    Flow:
    1. Check if authentication is configured
    2. If not, show setup dialog for initial password
    3. If configured, show login dialog
    4. On successful auth, decrypt database and launch main window
    5. On close, re-encrypt database
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Tracker")

    # Initialize authentication manager
    auth = AuthManager()
    user_password = None

    # Check if initial setup is needed
    if not auth.is_configured():
        # First run - setup password
        setup_dialog = SetupDialog(None, auth)
        if setup_dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)

        user_password = setup_dialog.get_password()

        # Check if user wants to setup TOTP
        if setup_dialog.should_setup_totp():
            totp_dialog = TwoFactorSetupDialog(None, auth)
            totp_dialog.exec()  # Optional - user can skip

    else:
        # Normal login flow
        login_dialog = LoginDialog(None, auth)
        if login_dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)

        user_password = login_dialog.get_password()

    # Authentication successful - launch main window with encryption key
    window = MainWindow(auth, user_password)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

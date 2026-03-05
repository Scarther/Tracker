# TRACKER
## Case Management & Digital Footprint Tracking

---

## What is Tracker?

Tracker is a standalone desktop application designed for law enforcement professionals to manage cases, track subjects, and visualize relationships between people, gangs, events, and locations. Built with security and offline capability in mind, all data stays local on your machine.

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Subject Management** | Track individuals with photos, aliases, affiliations, contact info, social media, and physical descriptions |
| **Gang Intelligence** | Document gangs, sets, territories, and hierarchies |
| **Event Logging** | Record incidents with dates, locations, and involved parties with full media attachment support |
| **Location Tracking** | Map addresses and associate them with subjects/events |
| **Vehicle Database** | Track vehicles with plates, descriptions, and owners |
| **Weapon Registry** | Document weapons linked to subjects or events |
| **Charge Tracking** | Record criminal charges and case information |
| **Online Accounts** | Track social media accounts and posts even before linked to a subject |
| **DNS Investigations** | Document domain lookups, WHOIS data, and hosting information |
| **Graffiti/Intel Logs** | Store graffiti photos and intelligence notes |
| **Relationship Graph** | Interactive visualization showing connections between all entities - click nodes to view/edit details |

---

## How It Works

1. **Authentication** - Secure login with optional two-factor authentication (2FA)
2. **Data Entry** - Add subjects, gangs, events, locations via intuitive forms
3. **Link Entities** - Connect subjects to gangs, events to locations, etc.
4. **Visualize** - View the relationship graph to see connections at a glance
5. **Investigate** - Click any node in the graph to drill into full details
6. **Export/Backup** - Encrypted export for secure data backup and transfer

All data is stored in an encrypted local SQLite database. Media files (photos, documents) are organized in the `data/media` directory structure.

---

## Script Breakdown

### Python Modules

#### `main.py` (Primary Application)
**Purpose:** Main application entry point containing all UI components and logic.

**Key Components:**
- `MultiEntryWidgets` - Reusable widgets for social media, phones, emails
- `Dialog Classes` - Forms for creating/editing all entity types
- `ProfilePanel` - Right sidebar showing selected entity details
- `GraphWidget` - Interactive relationship visualization
- `TrackerMainWindow` - Main application window and navigation

**Dependencies:** PyQt6, PyQt6-WebEngine, database.py, auth.py, auth_dialogs.py

> **Note on base64 usage:** When displaying the relationship graph, subject photos must be embedded as data URLs because QtWebEngine security prevents direct file:// access. Photos are read from disk and encoded at runtime. This is NOT hardcoded data - it's dynamic conversion of user-uploaded images.

---

#### `database.py`
**Purpose:** SQLite database abstraction layer with full CRUD operations.

**Key Components:**
- `TrackerDB class` - Main database interface
- Table creation - Schema for all entity types
- CRUD methods - get_*, add_*, update_*, delete_* for each entity
- Link management - Methods to connect entities (subject-gang, etc.)
- Search functions - Query methods for finding records
- Export/Import - JSON-based data portability

**Security:** All database operations use parameterized queries to prevent SQL injection. No raw string concatenation in SQL statements.

---

#### `auth.py`
**Purpose:** Authentication and security management.

**Key Components:**
- `AuthManager class` - Handles login, password hashing, session management
- Password hashing - SHA-256 with unique salts per user
- TOTP 2FA - Time-based one-time passwords (Google Authenticator)
- Session tokens - Secure session management
- Lockout protection - Brute-force prevention

**Dependencies:** hashlib, secrets, pyotp (optional), qrcode (optional)

---

#### `auth_dialogs.py`
**Purpose:** PyQt6 dialog windows for authentication flows.

**Key Components:**
- `LoginDialog` - Main login screen with 2FA support
- `SetupDialog` - First-time setup wizard
- `TwoFactorSetupDialog` - QR code display for authenticator app setup
- `SecuritySettings` - Password change, 2FA enable/disable

---

#### `encryption.py`
**Purpose:** AES-256-GCM encryption for data export and backup.

**Key Components:**
- `derive_key()` - PBKDF2 key derivation (600,000 iterations)
- `encrypt_data()` - AES-256-GCM encryption with random nonce
- `decrypt_data()` - Decryption with authentication verification
- `encrypt_json()` - Convenience wrapper for dict encryption
- File operations - encrypt_file(), decrypt_file(), is_encrypted()

**Security Details:**
| Parameter | Value |
|-----------|-------|
| Algorithm | AES-256-GCM (authenticated encryption) |
| Key Derivation | PBKDF2-HMAC-SHA256, 600,000 iterations |
| Salt | 16 bytes, randomly generated per encryption |
| Nonce | 12 bytes (96-bit), randomly generated per encryption |
| File Header | "TRACKER_AES256_V1" identifies encrypted files |

---

### Build Scripts

#### `build/linux/build.sh`
**Purpose:** Creates standalone Linux executable using PyInstaller.

**Process:**
1. Detects Debian-based systems for apt package installation
2. Creates isolated virtual environment to avoid system conflicts
3. Installs PyInstaller and all Python dependencies
4. Bundles application with all required data files
5. Outputs single executable to `dist/Tracker`

**Requirements:** Python 3.10+, pip, venv

---

#### `build/linux/create_appimage.sh`
**Purpose:** Packages the built executable into a portable AppImage.

**Process:**
1. Creates AppDir structure (usr/bin, usr/share, etc.)
2. Copies executable and creates desktop entry
3. Generates AppRun launcher script
4. Uses appimagetool to create final .AppImage file

**Requirements:** appimagetool, successful build.sh run first

---

#### `build/windows/build.bat`
**Purpose:** Creates standalone Windows .exe using PyInstaller.

**Process:**
1. Verifies Python installation
2. Installs dependencies from requirements.txt
3. Installs PyInstaller if not present
4. Bundles application with Windows-specific paths
5. Outputs Tracker.exe to dist folder

**Requirements:** Python 3.10+, pip (included with Python on Windows)

---

### Data Files

| File | Description |
|------|-------------|
| `data/vis-network.min.js` | vis.js Network visualization library (Apache 2.0 / MIT) |
| `data/qwebchannel.js` | Qt-provided JavaScript for Python-JS communication |
| `icons/*.svg` | SVG icons for UI elements |

---

## Security Notes

### Encryption
- Database exports use AES-256-GCM authenticated encryption
- Key derivation uses PBKDF2 with 600,000 iterations (OWASP recommended)
- Each encryption operation uses unique random salt and nonce
- No hardcoded keys or secrets in source code

### Authentication
- Passwords hashed with SHA-256 + unique salt per user
- Optional TOTP two-factor authentication
- Session tokens for maintaining login state
- Account lockout after failed attempts

### Data Storage
- All data stored locally in SQLite database
- No cloud connectivity or external API calls
- No telemetry, analytics, or data collection
- Media files stored in local `data/media` directory

### SQL Injection Prevention
- All database queries use parameterized statements
- No string concatenation in SQL queries
- Input validation on all user-provided data

---

## System Requirements

| Requirement | Specification |
|-------------|---------------|
| Operating System | Linux (Debian/Ubuntu/Kali) or Windows 10/11 |
| Python | 3.10 or higher (for running from source) |
| Dependencies | PyQt6, PyQt6-WebEngine, pyotp, qrcode, cryptography |
| Disk Space | 500MB minimum (plus space for media files) |
| Memory | 4GB RAM recommended |

---

## Installation

### From Source (Development)

1. Install Python 3.10+

2. Install dependencies:

   **Linux (Debian-based):**
   ```bash
   sudo apt install python3-pyqt6 python3-pyqt6.qtwebengine
   pip install pyotp qrcode[pil] cryptography
   ```

   **Windows/Other:**
   ```bash
   pip install -r requirements.txt
   ```

3. Run:
   ```bash
   python main.py
   ```

### Build Executable

**Linux:**
```bash
cd Tracker
./build/linux/build.sh
./build/linux/create_appimage.sh  # optional, for portable AppImage
# Output: dist/Tracker or Tracker-x86_64.AppImage
```

**Windows:**
```cmd
cd Tracker
build\windows\build.bat
# Output: dist\Tracker.exe
```

---

## Intended Use

Tracker is designed for authorized law enforcement personnel conducting legitimate investigations. It provides a structured way to organize case information that would otherwise be scattered across notebooks, spreadsheets, and various files. The relationship graph helps identify connections that might not be obvious when data is siloed.

**Typical use cases:**
- Gang unit investigations
- Case file organization
- Subject tracking and monitoring
- Intelligence gathering and analysis
- Multi-agency information sharing (via encrypted exports)

---

## License

This software is provided for law enforcement and educational purposes. All usage must comply with applicable laws and department policies.

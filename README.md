# Alpha Testing At This time
Periodic updates to scripts. Complete Release will have AppImage and .exe files for simpler use


# TRACKER
## Case Management & Digital Footprint Tracking

---

## What is Tracker?

Tracker is a standalone desktop application for OSINT professionals and investigators to manage cases, track subjects, and visualize relationships between people, organizations, events, and locations. Built with security and offline capability in mind, all data stays local on your machine.

---

## Testing Phase

This repo is currently in the **testing phase**. Run directly from source — no builds or executables. This allows quick updates via `git pull` without losing your local database or media files.

---

## Setup & Run

### 1. Clone the repo

```bash
git clone <repo-url>
cd Tracker
```

### 2. Install dependencies

**Linux (Debian/Ubuntu/Kali):**
```bash
sudo apt install python3-pyqt6 python3-pyqt6.qtwebengine
pip install pyotp qrcode[pil] cryptography
```

**Windows:**
```bash
pip install -r requirements.txt
```

### 3. Run

```bash
python3 main.py
```

On first launch you'll be prompted to create a username and password. Your database and auth files are created locally and are excluded from the repo via `.gitignore`.

---

## Updating

Pull the latest changes — your local data is unaffected:

```bash
git pull
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Subject Management** | Track individuals with photos, aliases, affiliations, contact info, social media, and physical descriptions |
| **Organization Intelligence** | Document organizations, sets, territories, and hierarchies |
| **Event Logging** | Record incidents with dates, locations, and involved parties with full media attachment support |
| **Location Tracking** | Map addresses and associate them with subjects/events |
| **Vehicle Database** | Track vehicles with plates, descriptions, and owners |
| **Weapon Registry** | Document weapons linked to subjects or events |
| **Charge Tracking** | Record charges and case information |
| **Online Accounts** | Track social media accounts and posts even before linked to a subject |
| **DNS Investigations** | Document domain lookups, WHOIS data, and hosting information |
| **Graffiti/Intel Logs** | Store graffiti photos and intelligence notes |
| **Relationship Graph** | Interactive visualization showing connections between all entities - click nodes to view/edit details |

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

### Data Files

| File | Description |
|------|-------------|
| `data/vis-network.min.js` | vis.js Network visualization library (Apache 2.0 / MIT) |
| `data/qwebchannel.js` | Qt-provided JavaScript for Python-JS communication |
| `icons/*.svg` | SVG icons for UI elements |

---

## System Requirements

| Requirement | Specification |
|-------------|---------------|
| Operating System | Linux (Debian/Ubuntu/Kali) or Windows 10/11 |
| Python | 3.10 or higher |
| Dependencies | PyQt6, PyQt6-WebEngine, pyotp, qrcode, cryptography |
| Disk Space | 500MB minimum (plus space for media files) |
| Memory | 4GB RAM recommended |

---

## Reporting Issues

If something isn't working, open an issue on the repo with:
- What you were doing
- What happened vs what you expected
- Your OS and Python version

---

## License

This software is provided for OSINT research and educational purposes. All usage must comply with applicable laws and regulations.

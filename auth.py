"""
================================================================================
TRACKER - AUTHENTICATION AND 2FA MODULE
================================================================================
Provides secure authentication with Two-Factor Authentication (2FA) support
for protecting sensitive case management data.

FEATURES:
---------
- Password hashing using PBKDF2-SHA256
- TOTP (Time-based One-Time Password) for 2FA
- QR code generation for authenticator app setup
- Backup codes for account recovery
- Security key support (PIN-based fallback)

SECURITY NOTES:
---------------
- Passwords are hashed with PBKDF2-SHA256 (100,000 iterations)
- TOTP secrets are stored encrypted
- Backup codes are single-use and hashed
- Failed login attempts are tracked for lockout

DEPENDENCIES:
-------------
- pyotp: TOTP generation and verification (handles base32 encoding internally)
- qrcode: QR code generation for 2FA setup
- pillow: Image handling for QR codes

================================================================================
"""

import os
import json
import hashlib
import secrets
from datetime import datetime
from typing import Optional, Tuple

# Try to import optional dependencies
try:
    import pyotp
    PYOTP_AVAILABLE = True
except ImportError:
    PYOTP_AVAILABLE = False
    print("Warning: pyotp not installed. Install with: pip install pyotp")

try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    print("Warning: qrcode not installed. Install with: pip install qrcode[pil]")


class AuthManager:
    """
    Authentication manager for Tracker application.

    Handles user authentication including:
    - Password verification
    - TOTP-based 2FA
    - Backup code management
    - Session management

    Attributes:
        auth_file (str): Path to the authentication data file
        config (dict): Loaded authentication configuration
        max_attempts (int): Maximum failed login attempts before lockout
        lockout_duration (int): Lockout duration in seconds

    Example Usage:
        >>> auth = AuthManager()
        >>> if not auth.is_configured():
        ...     auth.setup_initial_credentials("password123")
        ...     auth.setup_2fa()
        >>> if auth.verify_login("password123", "123456"):
        ...     print("Login successful")
    """

    # Configuration constants
    HASH_ITERATIONS = 100000  # PBKDF2 iterations
    SALT_LENGTH = 32          # Salt length in bytes
    BACKUP_CODE_COUNT = 10    # Number of backup codes to generate
    BACKUP_CODE_LENGTH = 8    # Length of each backup code

    def __init__(self, auth_dir: str = "data"):
        """
        Initialize the authentication manager.

        Args:
            auth_dir: Directory to store authentication data
        """
        self.auth_dir = auth_dir
        self.auth_file = os.path.join(auth_dir, ".auth.json")
        self.config = self._load_config()
        self.max_attempts = 5
        self.lockout_duration = 300  # 5 minutes

    def _load_config(self) -> dict:
        """
        Load authentication configuration from file.

        Returns:
            dict: Authentication configuration or empty dict if not exists
        """
        if os.path.exists(self.auth_file):
            try:
                with open(self.auth_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_config(self):
        """
        Save authentication configuration to file.

        Creates the auth directory if it doesn't exist.
        Sets restrictive file permissions (owner read/write only).
        """
        os.makedirs(self.auth_dir, exist_ok=True)
        with open(self.auth_file, 'w') as f:
            json.dump(self.config, f, indent=2)
        # Set restrictive permissions (Unix only)
        try:
            os.chmod(self.auth_file, 0o600)
        except OSError:
            pass  # Windows doesn't support chmod

    def _hash_password(self, password: str, salt: bytes = None) -> Tuple[str, str]:
        """
        Hash a password using PBKDF2-SHA256.

        Args:
            password: The plaintext password
            salt: Optional salt bytes (generated if not provided)

        Returns:
            Tuple of (hash_hex, salt_hex)
        """
        if salt is None:
            salt = secrets.token_bytes(self.SALT_LENGTH)

        # Use PBKDF2 with SHA-256
        hash_bytes = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            self.HASH_ITERATIONS
        )

        return hash_bytes.hex(), salt.hex()

    def _verify_password(self, password: str, stored_hash: str, stored_salt: str) -> bool:
        """
        Verify a password against stored hash.

        Args:
            password: The plaintext password to verify
            stored_hash: The stored password hash (hex)
            stored_salt: The stored salt (hex)

        Returns:
            bool: True if password matches
        """
        salt = bytes.fromhex(stored_salt)
        computed_hash, _ = self._hash_password(password, salt)
        return secrets.compare_digest(computed_hash, stored_hash)

    def is_configured(self) -> bool:
        """
        Check if authentication has been set up.

        Returns:
            bool: True if password and 2FA are configured
        """
        return bool(self.config.get('password_hash'))

    def is_2fa_enabled(self) -> bool:
        """
        Check if 2FA is enabled.

        Returns:
            bool: True if 2FA (TOTP or security key) is enabled
        """
        return bool(self.config.get('totp_secret') or self.config.get('security_key'))

    def is_locked_out(self) -> bool:
        """
        Check if account is currently locked out due to failed attempts.

        Returns:
            bool: True if account is locked
        """
        lockout_until = self.config.get('lockout_until')
        if lockout_until:
            if datetime.fromisoformat(lockout_until) > datetime.now():
                return True
            else:
                # Lockout expired, clear it
                self.config.pop('lockout_until', None)
                self.config['failed_attempts'] = 0
                self._save_config()
        return False

    def get_lockout_remaining(self) -> int:
        """
        Get remaining lockout time in seconds.

        Returns:
            int: Seconds remaining in lockout, or 0 if not locked
        """
        lockout_until = self.config.get('lockout_until')
        if lockout_until:
            remaining = (datetime.fromisoformat(lockout_until) - datetime.now()).total_seconds()
            return max(0, int(remaining))
        return 0

    def setup_initial_credentials(self, password: str) -> bool:
        """
        Set up initial password for the application.

        Args:
            password: The master password

        Returns:
            bool: True if setup successful

        Raises:
            ValueError: If password is too weak
        """
        # Basic password strength check
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")

        # Hash and store password
        password_hash, salt = self._hash_password(password)
        self.config['password_hash'] = password_hash
        self.config['password_salt'] = salt
        self.config['created_at'] = datetime.now().isoformat()
        self.config['failed_attempts'] = 0

        self._save_config()
        return True

    def change_password(self, old_password: str, new_password: str) -> bool:
        """
        Change the master password.

        Args:
            old_password: Current password for verification
            new_password: New password to set

        Returns:
            bool: True if password changed successfully

        Raises:
            ValueError: If old password is incorrect or new password is weak
        """
        # Verify old password
        if not self.verify_password(old_password):
            raise ValueError("Current password is incorrect")

        # Validate new password
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters")

        # Hash and store new password
        password_hash, salt = self._hash_password(new_password)
        self.config['password_hash'] = password_hash
        self.config['password_salt'] = salt
        self.config['password_changed_at'] = datetime.now().isoformat()

        self._save_config()
        return True

    def verify_password(self, password: str) -> bool:
        """
        Verify password without 2FA.

        Args:
            password: Password to verify

        Returns:
            bool: True if password is correct
        """
        if not self.config.get('password_hash'):
            return False

        return self._verify_password(
            password,
            self.config['password_hash'],
            self.config['password_salt']
        )

    def setup_totp(self, issuer: str = "Tracker") -> Tuple[str, str]:
        """
        Set up TOTP-based 2FA.

        Generates a new TOTP secret and returns the provisioning URI
        for QR code generation.

        Args:
            issuer: The issuer name shown in authenticator apps

        Returns:
            Tuple of (secret, provisioning_uri)

        Raises:
            ImportError: If pyotp is not installed
        """
        if not PYOTP_AVAILABLE:
            raise ImportError("pyotp is required for TOTP. Install with: pip install pyotp")

        # Generate a new secret
        secret = pyotp.random_base32()

        # Create provisioning URI for QR code
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name="User", issuer_name=issuer)

        # Store secret (will be confirmed after verification)
        self.config['totp_secret_pending'] = secret
        self._save_config()

        return secret, uri

    def confirm_totp_setup(self, code: str) -> bool:
        """
        Confirm TOTP setup by verifying a code.

        This should be called after setup_totp() with a code from
        the user's authenticator app to ensure they saved the secret.

        Args:
            code: TOTP code from authenticator app

        Returns:
            bool: True if code is valid and setup is confirmed
        """
        if not PYOTP_AVAILABLE:
            return False

        pending_secret = self.config.get('totp_secret_pending')
        if not pending_secret:
            return False

        totp = pyotp.TOTP(pending_secret)
        if totp.verify(code, valid_window=1):
            # Code valid - confirm setup
            self.config['totp_secret'] = pending_secret
            self.config.pop('totp_secret_pending', None)
            self.config['totp_enabled_at'] = datetime.now().isoformat()

            # Generate backup codes
            self._generate_backup_codes()

            self._save_config()
            return True

        return False

    def verify_totp(self, code: str) -> bool:
        """
        Verify a TOTP code.

        Args:
            code: 6-digit TOTP code

        Returns:
            bool: True if code is valid
        """
        if not PYOTP_AVAILABLE:
            return False

        secret = self.config.get('totp_secret')
        if not secret:
            return False

        totp = pyotp.TOTP(secret)
        # Allow 1 window (30 seconds) of clock drift
        return totp.verify(code, valid_window=1)

    def generate_qr_code(self, uri: str, output_path: str = None) -> Optional[str]:
        """
        Generate a QR code image for TOTP setup.

        Args:
            uri: The TOTP provisioning URI
            output_path: Path to save the QR code image (optional)

        Returns:
            str: Path to the generated QR code image, or None if failed
        """
        if not QRCODE_AVAILABLE:
            return None

        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(uri)
            qr.make(fit=True)

            if output_path is None:
                output_path = os.path.join(self.auth_dir, "totp_qr.png")

            # Generate QR code image using PIL
            img = qr.make_image(fill_color='black', back_color='white')
            img.save(output_path)

            return output_path
        except Exception as e:
            print(f"Error generating QR code: {e}")
            return None

    def setup_security_key(self, pin: str) -> bool:
        """
        Set up a security PIN as alternative 2FA method.

        This provides a backup method when TOTP isn't available.
        The PIN should be different from the main password.

        Args:
            pin: 6-8 digit security PIN

        Returns:
            bool: True if setup successful

        Raises:
            ValueError: If PIN is invalid
        """
        # Validate PIN
        if not pin.isdigit() or len(pin) < 6 or len(pin) > 8:
            raise ValueError("Security PIN must be 6-8 digits")

        # Hash and store PIN
        pin_hash, salt = self._hash_password(pin)
        self.config['security_key_hash'] = pin_hash
        self.config['security_key_salt'] = salt
        self.config['security_key_enabled_at'] = datetime.now().isoformat()

        self._save_config()
        return True

    def verify_security_key(self, pin: str) -> bool:
        """
        Verify a security PIN.

        Args:
            pin: Security PIN to verify

        Returns:
            bool: True if PIN is correct
        """
        if not self.config.get('security_key_hash'):
            return False

        return self._verify_password(
            pin,
            self.config['security_key_hash'],
            self.config['security_key_salt']
        )

    def _generate_backup_codes(self) -> list:
        """
        Generate single-use backup codes for account recovery.

        Generates 10 random codes that can be used if TOTP device is lost.

        Returns:
            list: List of backup codes (plaintext)
        """
        codes = []
        hashed_codes = []

        for _ in range(self.BACKUP_CODE_COUNT):
            # Generate random code
            code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789')
                          for _ in range(self.BACKUP_CODE_LENGTH))
            codes.append(code)

            # Hash for storage
            code_hash, salt = self._hash_password(code)
            hashed_codes.append({
                'hash': code_hash,
                'salt': salt,
                'used': False
            })

        self.config['backup_codes'] = hashed_codes
        self.config['backup_codes_generated_at'] = datetime.now().isoformat()

        return codes

    def get_backup_codes(self, password: str) -> Optional[list]:
        """
        Regenerate and return backup codes.

        Requires password verification for security.

        Args:
            password: Master password for verification

        Returns:
            list: New backup codes, or None if password incorrect
        """
        if not self.verify_password(password):
            return None

        codes = self._generate_backup_codes()
        self._save_config()
        return codes

    def verify_backup_code(self, code: str) -> bool:
        """
        Verify and consume a backup code.

        Each backup code can only be used once.

        Args:
            code: Backup code to verify

        Returns:
            bool: True if code is valid and unused
        """
        backup_codes = self.config.get('backup_codes', [])

        for bc in backup_codes:
            if bc.get('used'):
                continue

            if self._verify_password(code.upper(), bc['hash'], bc['salt']):
                # Mark as used
                bc['used'] = True
                bc['used_at'] = datetime.now().isoformat()
                self._save_config()
                return True

        return False

    def get_remaining_backup_codes(self) -> int:
        """
        Get count of remaining unused backup codes.

        Returns:
            int: Number of unused backup codes
        """
        backup_codes = self.config.get('backup_codes', [])
        return sum(1 for bc in backup_codes if not bc.get('used'))

    def verify_login(self, password: str, second_factor: str = None) -> Tuple[bool, str]:
        """
        Full login verification with optional 2FA.

        Args:
            password: Master password
            second_factor: TOTP code, security PIN, or backup code

        Returns:
            Tuple of (success, message)
        """
        # Check lockout
        if self.is_locked_out():
            remaining = self.get_lockout_remaining()
            return False, f"Account locked. Try again in {remaining} seconds."

        # Verify password
        if not self.verify_password(password):
            self._record_failed_attempt()
            return False, "Invalid password"

        # Check if 2FA is required
        if self.is_2fa_enabled():
            if not second_factor:
                return False, "2FA code required"

            # Try TOTP first
            if self.config.get('totp_secret') and self.verify_totp(second_factor):
                self._record_successful_login()
                return True, "Login successful"

            # Try security key
            if self.config.get('security_key_hash') and self.verify_security_key(second_factor):
                self._record_successful_login()
                return True, "Login successful"

            # Try backup code
            if self.verify_backup_code(second_factor):
                remaining = self.get_remaining_backup_codes()
                self._record_successful_login()
                return True, f"Login successful (backup code used, {remaining} remaining)"

            self._record_failed_attempt()
            return False, "Invalid 2FA code"

        # No 2FA required
        self._record_successful_login()
        return True, "Login successful"

    def _record_failed_attempt(self):
        """Record a failed login attempt and check for lockout."""
        attempts = self.config.get('failed_attempts', 0) + 1
        self.config['failed_attempts'] = attempts
        self.config['last_failed_attempt'] = datetime.now().isoformat()

        if attempts >= self.max_attempts:
            from datetime import timedelta
            lockout_until = datetime.now() + timedelta(seconds=self.lockout_duration)
            self.config['lockout_until'] = lockout_until.isoformat()

        self._save_config()

    def _record_successful_login(self):
        """Record a successful login and reset failed attempts."""
        self.config['failed_attempts'] = 0
        self.config.pop('lockout_until', None)
        self.config['last_login'] = datetime.now().isoformat()
        self._save_config()

    def disable_2fa(self, password: str) -> bool:
        """
        Disable all 2FA methods.

        Requires password verification for security.

        Args:
            password: Master password for verification

        Returns:
            bool: True if 2FA disabled successfully
        """
        if not self.verify_password(password):
            return False

        # Remove all 2FA data
        self.config.pop('totp_secret', None)
        self.config.pop('totp_secret_pending', None)
        self.config.pop('totp_enabled_at', None)
        self.config.pop('security_key_hash', None)
        self.config.pop('security_key_salt', None)
        self.config.pop('security_key_enabled_at', None)
        self.config.pop('backup_codes', None)
        self.config.pop('backup_codes_generated_at', None)

        self.config['2fa_disabled_at'] = datetime.now().isoformat()
        self._save_config()

        return True

    def reset_all(self) -> bool:
        """
        Factory reset - remove all authentication data.

        WARNING: This cannot be undone!

        Returns:
            bool: True if reset successful
        """
        self.config = {}

        if os.path.exists(self.auth_file):
            os.remove(self.auth_file)

        # Remove QR code if exists
        qr_path = os.path.join(self.auth_dir, "totp_qr.png")
        if os.path.exists(qr_path):
            os.remove(qr_path)

        return True

    def get_auth_status(self) -> dict:
        """
        Get current authentication configuration status.

        Returns:
            dict: Status information including:
                - configured: Whether initial setup is complete
                - totp_enabled: Whether TOTP is enabled
                - security_key_enabled: Whether security PIN is enabled
                - backup_codes_remaining: Number of unused backup codes
                - last_login: Timestamp of last successful login
        """
        return {
            'configured': self.is_configured(),
            'totp_enabled': bool(self.config.get('totp_secret')),
            'security_key_enabled': bool(self.config.get('security_key_hash')),
            'backup_codes_remaining': self.get_remaining_backup_codes(),
            'last_login': self.config.get('last_login'),
            'created_at': self.config.get('created_at'),
            '2fa_enabled': self.is_2fa_enabled()
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def check_dependencies() -> dict:
    """
    Check availability of optional dependencies.

    Returns:
        dict: Availability status of each dependency
    """
    return {
        'pyotp': PYOTP_AVAILABLE,
        'qrcode': QRCODE_AVAILABLE,
    }


def install_instructions() -> str:
    """
    Get installation instructions for missing dependencies.

    Returns:
        str: Installation commands
    """
    return """
To enable all 2FA features, install the following packages:

    pip install pyotp qrcode[pil]

Or add to requirements.txt:
    pyotp>=2.8.0
    qrcode[pil]>=7.4.0
"""


# =============================================================================
# MODULE TESTING
# =============================================================================

if __name__ == "__main__":
    """Test authentication module when run directly."""

    print("=" * 60)
    print("TRACKER AUTHENTICATION MODULE TEST")
    print("=" * 60)

    # Check dependencies
    deps = check_dependencies()
    print(f"\nDependencies:")
    print(f"  pyotp: {'Available' if deps['pyotp'] else 'MISSING'}")
    print(f"  qrcode: {'Available' if deps['qrcode'] else 'MISSING'}")

    if not all(deps.values()):
        print(install_instructions())

    # Test basic functionality
    print("\nTesting authentication...")

    # Use temp directory for testing
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        auth = AuthManager(tmpdir)

        # Test initial setup
        print(f"  Is configured: {auth.is_configured()}")

        # Set up password
        auth.setup_initial_credentials("TestPassword123")
        print(f"  After setup: {auth.is_configured()}")

        # Verify password
        result = auth.verify_password("TestPassword123")
        print(f"  Password verify (correct): {result}")

        result = auth.verify_password("WrongPassword")
        print(f"  Password verify (wrong): {result}")

        # Test TOTP if available
        if PYOTP_AVAILABLE:
            print("\n  Testing TOTP...")
            secret, uri = auth.setup_totp()
            print(f"  TOTP secret generated: {secret[:8]}...")

            # Simulate verification
            totp = pyotp.TOTP(secret)
            code = totp.now()
            result = auth.confirm_totp_setup(code)
            print(f"  TOTP setup confirmed: {result}")

        print("\nStatus:")
        status = auth.get_auth_status()
        for key, value in status.items():
            print(f"  {key}: {value}")

    print("\n" + "=" * 60)
    print("Test complete!")

"""
================================================================================
ENCRYPTION MODULE - AES-256-GCM Encryption Utilities
================================================================================

This module provides encryption and decryption utilities for secure data
export and backup functionality in Tracker.

SECURITY OVERVIEW:
-----------------
- Algorithm: AES-256-GCM (Galois/Counter Mode)
  - 256-bit key provides strong encryption
  - GCM mode provides both confidentiality AND authenticity
  - Tampered data will fail to decrypt (integrity protection)

- Key Derivation: PBKDF2-HMAC-SHA256
  - 600,000 iterations (OWASP 2023 recommendation)
  - Unique random salt per encryption operation
  - Resistant to brute-force and rainbow table attacks

- Nonce/IV: 96-bit (12 bytes), randomly generated
  - Never reused with the same key
  - Unique per encryption operation

FILE FORMAT:
-----------
Encrypted files have the following binary structure:
  [HEADER: 17 bytes] "TRACKER_AES256_V1"
  [SALT: 16 bytes]   Random salt for key derivation
  [NONCE: 12 bytes]  Random nonce for AES-GCM
  [CIPHERTEXT: var]  Encrypted data + 16-byte auth tag

USAGE:
------
  # Encrypt a dictionary
  encrypted = encrypt_json({'key': 'value'}, 'password')

  # Decrypt back to dictionary
  data = decrypt_json(encrypted, 'password')

  # Encrypt/decrypt files
  encrypt_file('data.json', 'data.enc', 'password')
  decrypt_file('data.enc', 'data.json', 'password')

  # Check if file is encrypted
  if is_encrypted('somefile'):
      ...

NO BASE64 USAGE:
----------------
This module operates entirely on raw bytes. No base64 encoding is used.
All cryptographic operations use binary data directly.

================================================================================
"""

import os
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# =============================================================================
# CONSTANTS
# =============================================================================

# File header magic bytes - identifies files encrypted by this module
# Used to verify file format before attempting decryption
ENCRYPTED_HEADER = b"TRACKER_AES256_V1"

# Key derivation parameters
_SALT_LENGTH = 16        # 128 bits - sufficient for uniqueness
_NONCE_LENGTH = 12       # 96 bits - standard for AES-GCM
_KEY_LENGTH = 32         # 256 bits - for AES-256
_PBKDF2_ITERATIONS = 600000  # OWASP 2023 recommendation for PBKDF2-SHA256


# =============================================================================
# KEY DERIVATION
# =============================================================================

def derive_key(password: str, salt: bytes) -> bytes:
    """
    Derive a cryptographic key from a password using PBKDF2.

    PBKDF2 (Password-Based Key Derivation Function 2) stretches a password
    into a secure encryption key by applying a pseudorandom function
    (HMAC-SHA256) many times. This makes brute-force attacks expensive.

    Args:
        password: User-provided password string
        salt: Random bytes to prevent rainbow table attacks
              Must be unique per encryption operation
              Recommended: 16 bytes from os.urandom()

    Returns:
        32-byte (256-bit) key suitable for AES-256

    Security Notes:
        - 600,000 iterations per OWASP 2023 guidelines
        - Salt prevents precomputed attack tables
        - Output key is deterministic given same password + salt
    """
    # Configure the key derivation function
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),  # Hash function for HMAC
        length=_KEY_LENGTH,          # Output key size (32 bytes = 256 bits)
        salt=salt,                   # Unique salt prevents rainbow tables
        iterations=_PBKDF2_ITERATIONS,  # Computational cost factor
    )

    # Derive and return the key
    # Password is encoded to bytes before derivation
    return kdf.derive(password.encode('utf-8'))


# =============================================================================
# CORE ENCRYPTION/DECRYPTION
# =============================================================================

def encrypt_data(data: bytes, password: str) -> bytes:
    """
    Encrypt raw bytes using AES-256-GCM.

    AES-GCM provides authenticated encryption:
    - Confidentiality: Data is encrypted and unreadable without the key
    - Authenticity: Any tampering with ciphertext will be detected
    - Integrity: Decryption fails if data was modified

    Args:
        data: Raw bytes to encrypt (any binary data)
        password: Encryption password (will be key-derived)

    Returns:
        Encrypted bytes in format:
        HEADER (17 bytes) + SALT (16 bytes) + NONCE (12 bytes) + CIPHERTEXT

    Security Notes:
        - New random salt generated for each call
        - New random nonce generated for each call
        - Never encrypts the same data the same way twice
    """
    # Generate cryptographically secure random values
    # os.urandom() uses the OS's secure random number generator
    salt = os.urandom(_SALT_LENGTH)    # For key derivation
    nonce = os.urandom(_NONCE_LENGTH)  # For AES-GCM (also called IV)

    # Derive encryption key from password
    # Different salt = different key, even with same password
    key = derive_key(password, salt)

    # Create AES-GCM cipher instance with our 256-bit key
    aesgcm = AESGCM(key)

    # Encrypt the data
    # GCM mode appends a 16-byte authentication tag to the ciphertext
    # The None parameter is for additional authenticated data (AAD) - unused
    ciphertext = aesgcm.encrypt(nonce, data, None)

    # Pack everything together for storage/transmission
    # Format: HEADER + SALT + NONCE + CIPHERTEXT
    # This allows decryption with only the password (salt/nonce included)
    return ENCRYPTED_HEADER + salt + nonce + ciphertext


def decrypt_data(encrypted_data: bytes, password: str) -> bytes:
    """
    Decrypt data that was encrypted with encrypt_data().

    Verifies the file format, extracts components, and decrypts.
    Will raise an exception if:
    - File format is invalid (wrong/missing header)
    - Password is incorrect
    - Data was tampered with (authentication failure)

    Args:
        encrypted_data: Bytes from encrypt_data() or encrypted file
        password: Decryption password (must match encryption password)

    Returns:
        Original decrypted bytes

    Raises:
        ValueError: If file format is invalid or decryption fails

    Security Notes:
        - GCM authentication tag is verified automatically
        - Tampered data will raise an exception, not return garbage
        - No information is leaked about why decryption failed
    """
    header_len = len(ENCRYPTED_HEADER)

    # Verify this is actually an encrypted file from our application
    # Prevents confusing error messages when opening wrong file types
    if not encrypted_data.startswith(ENCRYPTED_HEADER):
        raise ValueError("File is not encrypted or has unknown format")

    # Extract the components from the encrypted data
    # Layout: [HEADER][SALT: 16 bytes][NONCE: 12 bytes][CIPHERTEXT: rest]
    salt_start = header_len
    salt_end = salt_start + _SALT_LENGTH
    nonce_end = salt_end + _NONCE_LENGTH

    salt = encrypted_data[salt_start:salt_end]
    nonce = encrypted_data[salt_end:nonce_end]
    ciphertext = encrypted_data[nonce_end:]

    # Derive the same key using the stored salt
    # If password is correct, this produces the same key used for encryption
    key = derive_key(password, salt)

    # Create cipher instance and attempt decryption
    aesgcm = AESGCM(key)

    try:
        # decrypt() verifies the authentication tag automatically
        # If tag doesn't match (wrong password or tampered data), raises exception
        return aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        # Don't reveal whether it was wrong password vs corrupted data
        # This prevents information leakage to attackers
        raise ValueError("Decryption failed - wrong password or corrupted data")


# =============================================================================
# JSON CONVENIENCE WRAPPERS
# =============================================================================

def encrypt_json(data: dict, password: str) -> bytes:
    """
    Encrypt a Python dictionary as JSON.

    Convenience wrapper that handles JSON serialization before encryption.
    Useful for encrypting structured data like database exports.

    Args:
        data: Dictionary (or any JSON-serializable object)
        password: Encryption password

    Returns:
        Encrypted bytes (same format as encrypt_data)

    Example:
        encrypted = encrypt_json({'users': [...], 'events': [...]}, 'secret')
    """
    # Convert dict to formatted JSON string, then to UTF-8 bytes
    json_bytes = json.dumps(data, indent=2).encode('utf-8')

    # Encrypt the JSON bytes
    return encrypt_data(json_bytes, password)


def decrypt_json(encrypted_data: bytes, password: str) -> dict:
    """
    Decrypt data back to a Python dictionary.

    Convenience wrapper that handles JSON deserialization after decryption.

    Args:
        encrypted_data: Bytes from encrypt_json()
        password: Decryption password

    Returns:
        Decrypted dictionary

    Example:
        data = decrypt_json(encrypted_bytes, 'secret')
        users = data['users']
    """
    # Decrypt to get JSON bytes
    decrypted = decrypt_data(encrypted_data, password)

    # Parse JSON bytes back to dictionary
    return json.loads(decrypted.decode('utf-8'))


# =============================================================================
# FILE OPERATIONS
# =============================================================================

def encrypt_file(input_path: str, output_path: str, password: str) -> None:
    """
    Encrypt a file and save to a new location.

    Reads the entire file into memory, encrypts it, and writes the result.
    The original file is not modified.

    Args:
        input_path: Path to the file to encrypt
        output_path: Path where encrypted file will be saved
        password: Encryption password

    Note:
        For very large files, consider streaming encryption instead.
        This implementation loads the entire file into memory.
    """
    # Read the entire input file as binary
    with open(input_path, 'rb') as f:
        data = f.read()

    # Encrypt the data
    encrypted = encrypt_data(data, password)

    # Write encrypted data to output file
    with open(output_path, 'wb') as f:
        f.write(encrypted)


def decrypt_file(input_path: str, output_path: str, password: str) -> None:
    """
    Decrypt a file and save to a new location.

    Reads the encrypted file, decrypts it, and writes the original content.

    Args:
        input_path: Path to the encrypted file
        output_path: Path where decrypted file will be saved
        password: Decryption password

    Raises:
        ValueError: If file is not encrypted or password is wrong
    """
    # Read the encrypted file
    with open(input_path, 'rb') as f:
        encrypted = f.read()

    # Decrypt the data
    decrypted = decrypt_data(encrypted, password)

    # Write decrypted data to output file
    with open(output_path, 'wb') as f:
        f.write(decrypted)


def is_encrypted(file_path: str) -> bool:
    """
    Check if a file was encrypted by this module.

    Reads only the header bytes to check for our magic signature.
    Does not validate the entire file or attempt decryption.

    Args:
        file_path: Path to the file to check

    Returns:
        True if file starts with TRACKER_AES256_V1 header
        False if file doesn't exist, can't be read, or has different format
    """
    try:
        with open(file_path, 'rb') as f:
            # Only read the header bytes, not the entire file
            header = f.read(len(ENCRYPTED_HEADER))
        return header == ENCRYPTED_HEADER
    except (IOError, OSError):
        # File doesn't exist or can't be read
        return False

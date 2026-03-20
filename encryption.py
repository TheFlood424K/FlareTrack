"""Encryption utilities for FlareTrack - secure health data storage.

Provides AES-256 encryption for sensitive health data including:
- Medications and dosages
- Symptoms and severity levels
- Environmental factors
- Personal health notes
"""
import os
import json
import base64
import hashlib
import secrets
from pathlib import Path
from typing import Any, Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# File names (stored alongside key_file)
_PASSWORD_FILE_SUFFIX = ".password"  # stores salt + hashed password
_SALT_FILE_SUFFIX = ".salt"           # stores salt used to wrap the Fernet key


class DataEncryption:
    """Handles encryption and decryption of sensitive health data."""

    def __init__(self, key_file: str = ".flaretrack.key"):
        """Initialize encryption system.

        Args:
            key_file: Path to store the encryption key
        """
        self.key_file = Path.home() / key_file
        self._password_file = Path.home() / (key_file + _PASSWORD_FILE_SUFFIX)
        self._salt_file = Path.home() / (key_file + _SALT_FILE_SUFFIX)
        self.fernet = self._load_or_create_key()

    # ------------------------------------------------------------------
    # Internal key management
    # ------------------------------------------------------------------

    def _load_or_create_key(self) -> Fernet:
        """Load existing encryption key or create a new one."""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                key = f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            # Save key with restricted permissions
            self.key_file.touch(mode=0o600)
            with open(self.key_file, 'wb') as f:
                f.write(key)

        return Fernet(key)

    # ------------------------------------------------------------------
    # App-password management
    # ------------------------------------------------------------------

    def has_password(self) -> bool:
        """Return True if an app password has been set."""
        return self._password_file.exists()

    def set_password(self, password: str) -> None:
        """Set (or change) the app password.

        Stores a salted SHA-256 hash of the password so it can be
        verified on the next launch without storing the plaintext.

        Args:
            password: The new app password chosen by the user
        """
        salt = secrets.token_bytes(32)
        pw_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            480_000
        )
        # Store as hex: "<salt_hex>:<hash_hex>"
        payload = salt.hex() + ":" + pw_hash.hex()
        self._password_file.touch(mode=0o600)
        with open(self._password_file, 'w') as f:
            f.write(payload)

    def verify_password(self, password: str) -> bool:
        """Verify a password against the stored hash.

        Args:
            password: The password to verify

        Returns:
            True if the password matches, False otherwise
        """
        if not self._password_file.exists():
            return True  # no password set, always passes

        with open(self._password_file, 'r') as f:
            payload = f.read().strip()

        try:
            salt_hex, stored_hash_hex = payload.split(":")
            salt = bytes.fromhex(salt_hex)
        except ValueError:
            return False

        pw_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            480_000
        )
        return secrets.compare_digest(pw_hash.hex(), stored_hash_hex)

    def change_password(self, old_password: str, new_password: str) -> bool:
        """Change the app password after verifying the old one.

        Args:
            old_password: Current password for verification
            new_password: New password to set

        Returns:
            True if the change succeeded, False if old_password was wrong
        """
        if not self.verify_password(old_password):
            return False
        self.set_password(new_password)
        return True

    def remove_password(self, password: str) -> bool:
        """Remove app password protection after verifying the current password.

        Args:
            password: Current password for verification

        Returns:
            True if removed, False if password was wrong
        """
        if not self.verify_password(password):
            return False
        if self._password_file.exists():
            self._password_file.unlink()
        return True

    # ------------------------------------------------------------------
    # Encrypt / decrypt helpers
    # ------------------------------------------------------------------

    def encrypt_data(self, data: Dict[str, Any]) -> bytes:
        """Encrypt dictionary data to bytes.

        Args:
            data: Dictionary containing health data

        Returns:
            Encrypted bytes
        """
        json_data = json.dumps(data).encode('utf-8')
        encrypted = self.fernet.encrypt(json_data)
        return encrypted

    def decrypt_data(self, encrypted_data: bytes) -> Dict[str, Any]:
        """Decrypt bytes back to dictionary.

        Args:
            encrypted_data: Encrypted bytes

        Returns:
            Decrypted dictionary
        """
        decrypted = self.fernet.decrypt(encrypted_data)
        return json.loads(decrypted.decode('utf-8'))

    def encrypt_file(self, input_file: Path, output_file: Optional[Path] = None) -> Path:
        """Encrypt a JSON file.

        Args:
            input_file: Path to unencrypted JSON file
            output_file: Path for encrypted output (defaults to input_file.enc)

        Returns:
            Path to encrypted file
        """
        with open(input_file, 'r') as f:
            data = json.load(f)

        encrypted = self.encrypt_data(data)

        if output_file is None:
            output_file = input_file.with_suffix('.enc')

        with open(output_file, 'wb') as f:
            f.write(encrypted)

        return output_file

    def decrypt_file(self, input_file: Path, output_file: Optional[Path] = None) -> Dict[str, Any]:
        """Decrypt an encrypted file.

        Args:
            input_file: Path to encrypted file
            output_file: Optional path to save decrypted JSON

        Returns:
            Decrypted data dictionary
        """
        with open(input_file, 'rb') as f:
            encrypted = f.read()

        data = self.decrypt_data(encrypted)

        if output_file:
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)

        return data


class DataMigration:
    """Handles migration of legacy unencrypted JSON files to encrypted format."""

    def __init__(self, encryption: DataEncryption):
        """Initialize migration system.

        Args:
            encryption: DataEncryption instance to use
        """
        self.encryption = encryption

    def migrate_file(self, json_file: Path, backup: bool = True) -> Path:
        """Migrate a legacy JSON file to encrypted format.

        Args:
            json_file: Path to legacy JSON file
            backup: Whether to create a backup of original file

        Returns:
            Path to encrypted file
        """
        # Create backup if requested
        if backup:
            backup_file = json_file.with_suffix('.json.backup')
            backup_file.write_bytes(json_file.read_bytes())
            print(f"Created backup: {backup_file}")

        # Encrypt the file
        encrypted_file = self.encryption.encrypt_file(json_file)
        print(f"Encrypted: {json_file} -> {encrypted_file}")

        # Optionally remove original
        # json_file.unlink()  # Uncomment to delete original after encryption

        return encrypted_file

    def migrate_directory(self, directory: Path, pattern: str = "*.json", backup: bool = True) -> list[Path]:
        """Migrate all JSON files in a directory.

        Args:
            directory: Directory containing JSON files
            pattern: File pattern to match (default: *.json)
            backup: Whether to create backups

        Returns:
            List of encrypted file paths
        """
        encrypted_files = []
        json_files = list(directory.glob(pattern))

        if not json_files:
            print(f"No files matching '{pattern}' found in {directory}")
            return encrypted_files

        print(f"Found {len(json_files)} file(s) to migrate")

        for json_file in json_files:
            # Skip backup files
            if json_file.suffix == '.backup':
                continue

            try:
                encrypted_file = self.migrate_file(json_file, backup=backup)
                encrypted_files.append(encrypted_file)
            except Exception as e:
                print(f"Error migrating {json_file}: {e}")

        print(f"\nMigration complete: {len(encrypted_files)} file(s) encrypted")
        return encrypted_files

    def verify_migration(self, original_file: Path, encrypted_file: Path) -> bool:
        """Verify that encrypted file can be decrypted to match original.

        Args:
            original_file: Original JSON file
            encrypted_file: Encrypted version

        Returns:
            True if data matches after decryption
        """
        with open(original_file, 'r') as f:
            original_data = json.load(f)

        decrypted_data = self.encryption.decrypt_file(encrypted_file)

        return original_data == decrypted_data


if __name__ == "__main__":
    # Example usage and testing
    import sys

    print("FlareTrack Data Encryption System")
    print("=" * 40)

    # Initialize encryption
    enc = DataEncryption()
    migration = DataMigration(enc)

    if len(sys.argv) > 1:
        # Command line usage
        if sys.argv[1] == "migrate":
            if len(sys.argv) > 2:
                path = Path(sys.argv[2])
                if path.is_dir():
                    migration.migrate_directory(path)
                elif path.is_file():
                    migration.migrate_file(path)
                else:
                    print(f"Error: {path} is not a valid file or directory")
            else:
                print("Usage: python encryption.py migrate <file_or_directory>")
        else:
            print("\nUsage:")
            print(" python encryption.py migrate <file_or_directory>")
            print("\nExamples:")
            print(" python encryption.py migrate data/")
            print(" python encryption.py migrate medications.json")

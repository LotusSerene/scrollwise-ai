import os
import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path
from fastapi import HTTPException
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class SecurityManager:
    def __init__(self):
        self.key_path = Path(os.path.dirname(__file__)) / "encryption.key"
        self.fernet = self._initialize_encryption()

    def _initialize_encryption(self) -> Fernet:
        try:
            # Try to load existing key
            if self.key_path.exists():
                encryption_key = self.key_path.read_bytes()
            else:
                # Generate new key if none exists
                encryption_key = Fernet.generate_key()
                # Save key securely with restricted permissions
                self.key_path.write_bytes(encryption_key)
                # Set file permissions (on Unix systems)
                if os.name != "nt":  # not Windows
                    self.key_path.chmod(0o600)
                logger.info("Generated new encryption key")

            return Fernet(encryption_key)

        except Exception as e:
            logger.error(f"Error initializing encryption: {e}")
            raise

    def encrypt_data(self, data: str) -> str:
        try:
            return self.fernet.encrypt(data.encode()).decode()
        except Exception as e:
            logger.error(f"Error encrypting data: {e}")
            raise

    def decrypt_data(self, encrypted_data: str) -> str:
        try:
            return self.fernet.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {type(e).__name__} - {str(e)}")
            logger.error(f"Encrypted data length: {len(encrypted_data)}")
            raise ValueError(
                "Failed to decrypt data - may be corrupted or using wrong encryption key"
            ) from e


class ApiKeyManager:
    API_KEY_FILE = Path("./api_key.dat")

    def __init__(self, security_manager: SecurityManager):
        self.security_manager = security_manager

    async def save_api_key(self, api_key: str) -> None:
        if api_key is None:
            logger.error("API key cannot be None")
            raise HTTPException(status_code=400, detail="API key cannot be None")
        try:
            encrypted_key = self.security_manager.encrypt_data(api_key)
            self.API_KEY_FILE.write_text(encrypted_key)
            logger.info(f"API key saved locally to {self.API_KEY_FILE}")
        except IOError as e:
            logger.error(f"Error writing API key file: {e}")
            raise HTTPException(status_code=500, detail="Error saving API key file")
        except Exception as e:
            logger.error(f"Error saving API key: {e}")
            raise HTTPException(status_code=500, detail="Error saving API key")

    async def get_api_key(self) -> Optional[str]:
        try:
            if not self.API_KEY_FILE.exists():
                logger.info("Local API key file not found.")
                return None

            encrypted_key = self.API_KEY_FILE.read_text()
            if not encrypted_key:
                logger.warning("Local API key file is empty.")
                return None

            try:
                decrypted_key = self.security_manager.decrypt_data(encrypted_key)
                return decrypted_key
            except ValueError as e:
                logger.error(f"Decryption failed for local API key: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error during decryption: {e}")
                return None

        except IOError as e:
            logger.error(f"Error reading API key file: {e}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving API key: {e}")
            return None

    async def remove_api_key(self) -> None:
        """Removes the locally stored API key file."""
        try:
            if self.API_KEY_FILE.exists():
                self.API_KEY_FILE.unlink()
                logger.info(f"Local API key file removed: {self.API_KEY_FILE}")
            else:
                logger.info("Local API key file not found, nothing to remove.")
        except IOError as e:
            logger.error(f"Error removing API key file: {e}")
            raise HTTPException(status_code=500, detail="Error removing API key file")
        except Exception as e:
            logger.error(f"Error removing API key: {e}")
            raise HTTPException(status_code=500, detail="Error removing API key")

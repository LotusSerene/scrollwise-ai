import os
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException
from sqlalchemy import select
from cryptography.fernet import Fernet
from database import User, db_instance

logger = logging.getLogger(__name__)

class SecurityManager:
    def __init__(self):
        self.key_path = os.path.join(os.path.dirname(__file__), 'encryption.key')
        self.fernet = self._initialize_encryption()

    def _initialize_encryption(self) -> Fernet:
        try:
            # Try to load existing key
            if os.path.exists(self.key_path):
                with open(self.key_path, 'rb') as key_file:
                    encryption_key = key_file.read()
            else:
                # Generate new key if none exists
                encryption_key = Fernet.generate_key()
                # Save key securely with restricted permissions
                with open(self.key_path, 'wb') as key_file:
                    key_file.write(encryption_key)
                # Set file permissions (on Unix systems)
                if os.name != 'nt':  # not Windows
                    os.chmod(self.key_path, 0o600)
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
            raise ValueError("Failed to decrypt data - may be corrupted or using wrong encryption key") from e

class ApiKeyManager:
    def __init__(self, security_manager: SecurityManager):
        self.security_manager = security_manager

    async def save_api_key(self, user_id: str, api_key: str) -> None:
        if api_key is None:  # Check if api_key is None
            logger.error("API key cannot be None")
            raise HTTPException(status_code=400, detail="API key cannot be None")
        try:
            encrypted_key = self.security_manager.encrypt_data(api_key)
            async with db_instance.Session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalars().first()
                if user:
                    user.api_key = encrypted_key
                    user.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                else:
                    raise HTTPException(status_code=404, detail="User not found")
        except Exception as e:
            logger.error(f"Error saving API key: {e}")
            raise HTTPException(status_code=500, detail="Error saving API key")

    async def get_api_key(self, user_id: str) -> Optional[str]:
        try:
            async with db_instance.Session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalars().first()
                if user and user.api_key:
                    try:
                        decrypted_key = self.security_manager.decrypt_data(user.api_key)
                        return decrypted_key
                    except Exception as e:
                        logger.error(f"Decryption failed for user {user_id}:")
                        logger.error(f"Stored key length: {len(user.api_key)}")
                        logger.error(f"Error type: {type(e).__name__}, Details: {str(e)}")
                        return None
                return None
        except Exception as e:
            logger.error(f"Error retrieving API key: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving API key")

    async def remove_api_key(self, user_id: str) -> None:
        """New method to safely clear API key"""
        try:
            async with db_instance.Session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalars().first()
                if user:
                    user.api_key = None
                    user.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                else:
                    raise HTTPException(status_code=404, detail="User not found")
        except Exception as e:
            logger.error(f"Error removing API key: {e}")
            raise HTTPException(status_code=500, detail="Error removing API key")
        
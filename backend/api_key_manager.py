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
        encryption_key = os.getenv('ENCRYPTION_KEY')
        if not encryption_key:
            encryption_key = Fernet.generate_key()
            logger.warning("No ENCRYPTION_KEY found in environment, generated new key")
        self.fernet = Fernet(encryption_key)

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
            logger.error(f"Error decrypting data: {e}")
            raise

class ApiKeyManager:
    def __init__(self, security_manager: SecurityManager):
        self.security_manager = security_manager

    async def save_api_key(self, user_id: str, api_key: str) -> None:
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
                        logger.error(f"Error decrypting API key for user {user_id}: {e}")
                        return None
                return None
        except Exception as e:
            logger.error(f"Error retrieving API key: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving API key")
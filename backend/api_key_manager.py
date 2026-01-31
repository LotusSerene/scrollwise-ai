import os
import logging
import base64
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select

from cryptography.fernet import Fernet
from database import User, db_instance

logger = logging.getLogger(__name__)

class SecurityManager:
    def __init__(self):
        self.key_file = "local_secret.key"
        self.fernet = None
        self._initialize_encryption()

    def _get_or_create_key(self) -> bytes:
        """Retrieve the secret key from a local file, or create it if missing."""
        if os.path.exists(self.key_file):
            try:
                with open(self.key_file, "rb") as f:
                    key = f.read()
                logger.info(f"Loaded encryption key from {self.key_file}")
                return key
            except Exception as e:
                logger.error(f"Failed to read encryption key file: {e}")
                raise HTTPException(status_code=500, detail="Failed to load encryption key.")
        else:
            try:
                key = Fernet.generate_key()
                with open(self.key_file, "wb") as f:
                    f.write(key)
                logger.info(f"Generated new encryption key and saved to {self.key_file}")
                return key
            except Exception as e:
                logger.error(f"Failed to create encryption key file: {e}")
                raise HTTPException(status_code=500, detail="Failed to create encryption key.")

    def _initialize_encryption(self):
        """Initialize the Fernet instance with the local key."""
        try:
            key = self._get_or_create_key()
            self.fernet = Fernet(key)
            logger.info("Successfully initialized encryption engine.")
        except Exception as e:
            logger.error(f"Failed to initialize Fernet: {e}")
            raise HTTPException(status_code=500, detail="Failed to initialize encryption engine.")

    def encrypt_data(self, data: str) -> str:
        """Encrypt data using Fernet."""
        if self.fernet is None:
            logger.error("Encryption attempted before Fernet was initialized.")
            raise HTTPException(status_code=500, detail="Encryption service not available.")
        if data is None:
            return None
        try:
            encrypted_bytes = self.fernet.encrypt(data.encode("utf-8"))
            return encrypted_bytes.decode("utf-8")
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise HTTPException(status_code=500, detail="Data encryption failed.")

    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt data using Fernet."""
        if self.fernet is None:
            logger.error("Decryption attempted before Fernet was initialized.")
            raise HTTPException(status_code=500, detail="Decryption service not available.")
        if encrypted_data is None:
            return None
        try:
            decrypted_bytes = self.fernet.decrypt(encrypted_data.encode("utf-8"))
            return decrypted_bytes.decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise HTTPException(status_code=500, detail="Data decryption failed.")


class ApiKeyManager:
    def __init__(self, security_manager: SecurityManager):
        self.security_manager = security_manager

    # --- Gemini/Default API Key Methods ---
    async def save_api_key(self, user_id: str, api_key: str) -> None:
        """Saves the primary (e.g., Gemini) API key."""
        if api_key is None:
            logger.error("API key cannot be None")
            raise HTTPException(status_code=400, detail="API key cannot be None")
        try:
            # Encrypt the API key before saving
            encrypted_key = self.security_manager.encrypt_data(api_key)
            async with db_instance.Session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalars().first()
                if user:
                    user.api_key = encrypted_key  # Store encrypted key
                    user.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                else:
                    logger.warning(
                        f"Attempted to save API key for non-existent user ID: {user_id}"
                    )
                    raise HTTPException(status_code=404, detail="User not found")
        except HTTPException:
            raise  # Re-raise HTTP exceptions from security manager or not found
        except Exception as e:
            logger.exception(
                f"Error saving encrypted API key for user {user_id}: {e}"
            )  # Use exception for stack trace
            raise HTTPException(status_code=500, detail="Error saving API key")

    async def get_api_key(self, user_id: str) -> Optional[str]:
        """Gets the primary (e.g., Gemini) API key."""
        try:
            async with db_instance.Session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalars().first()
                if user and user.api_key:
                    try:
                        # Decrypt the API key after retrieving
                        decrypted_key = self.security_manager.decrypt_data(user.api_key)
                        return decrypted_key
                    except HTTPException:
                        raise  # Re-raise HTTP exceptions from decrypt_data
                    except Exception as e:
                        # Log decryption errors specifically tied to a user
                        logger.error(
                            f"Decryption failed for user {user_id}'s stored primary key: {e}"
                        )
                        raise HTTPException(
                            status_code=500, detail="Failed to decrypt stored API key."
                        ) from e
                elif user and not user.api_key:
                    logger.debug(
                        f"User {user_id} found but has no primary API key stored."
                    )
                    return None  # User exists but no key
                else:
                    logger.debug(
                        f"User not found for primary API key retrieval: {user_id}"
                    )
                    return None  # User not found
        except HTTPException:
            raise  # Re-raise HTTP exceptions
        except Exception as e:
            logger.exception(
                f"Error retrieving primary API key for user {user_id}: {e}"
            )  # Use exception for stack trace
            raise HTTPException(
                status_code=500, detail="Error retrieving primary API key"
            )

    async def remove_api_key(self, user_id: str) -> None:
        """Safely clears the primary (e.g., Gemini) API key (sets field to None)"""
        try:
            async with db_instance.Session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalars().first()
                if user:
                    if user.api_key is None:
                        logger.info(f"No primary API key to remove for user {user_id}.")
                        # No need to commit if nothing changed
                        return
                    user.api_key = None  # Set to None
                    user.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    logger.info(
                        f"Successfully removed primary API key for user {user_id}."
                    )
                else:
                    logger.warning(
                        f"Attempted to remove primary API key for non-existent user ID: {user_id}"
                    )
                    raise HTTPException(status_code=404, detail="User not found")
        except HTTPException:
            raise  # Re-raise HTTP exceptions
        except Exception as e:
            logger.exception(
                f"Error removing primary API key for user {user_id}: {e}"
            )  # Use exception for stack trace
            raise HTTPException(
                status_code=500, detail="Error removing primary API key"
            )

    # --- OpenRouter API Key Methods ---

    async def save_openrouter_api_key(self, user_id: str, api_key: str) -> None:
        """Saves the OpenRouter API key."""
        if api_key is None:
            logger.error("OpenRouter API key cannot be None")
            raise HTTPException(
                status_code=400, detail="OpenRouter API key cannot be None"
            )
        try:
            encrypted_key = self.security_manager.encrypt_data(api_key)
            async with db_instance.Session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalars().first()
                if user:
                    user.openrouter_api_key = encrypted_key
                    user.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                else:
                    logger.warning(
                        f"Attempted to save OpenRouter API key for non-existent user ID: {user_id}"
                    )
                    raise HTTPException(status_code=404, detail="User not found")
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(
                f"Error saving encrypted OpenRouter API key for user {user_id}: {e}"
            )
            raise HTTPException(
                status_code=500, detail="Error saving OpenRouter API key"
            )

    async def get_openrouter_api_key(self, user_id: str) -> Optional[str]:
        """Gets the OpenRouter API key."""
        try:
            async with db_instance.Session() as session:
                query = select(User).where(User.id == user_id)
                result = await session.execute(query)
                user = result.scalars().first()
                if user and user.openrouter_api_key:
                    try:
                        decrypted_key = self.security_manager.decrypt_data(
                            user.openrouter_api_key
                        )
                        return decrypted_key
                    except HTTPException:
                        raise
                    except Exception as e:
                        logger.error(
                            f"Decryption failed for user {user_id}'s stored OpenRouter key: {e}"
                        )
                        raise HTTPException(
                            status_code=500,
                            detail="Failed to decrypt stored OpenRouter API key.",
                        ) from e
                elif user and not user.openrouter_api_key:
                    logger.debug(
                        f"User {user_id} found but has no OpenRouter API key stored."
                    )
                    return None
                else:
                    logger.debug(
                        f"User not found for OpenRouter API key retrieval: {user_id}"
                    )
                    return None
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(
                f"Error retrieving OpenRouter API key for user {user_id}: {e}"
            )
            raise HTTPException(
                status_code=500, detail="Error retrieving OpenRouter API key"
            )

    async def remove_openrouter_api_key(self, user_id: str) -> None:
        """Removes the OpenRouter API key for a user."""
        logger.info(f"Removing OpenRouter API key for user {user_id}")
        try:
            async with db_instance.Session() as session:
                user = await session.get(User, user_id)
                if user:
                    if user.openrouter_api_key is None:
                        logger.info(
                            f"No OpenRouter API key to remove for user {user_id}."
                        )
                        return
                    user.openrouter_api_key = None
                    user.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    logger.info(
                        f"Successfully removed OpenRouter API key for user {user_id}."
                    )
                else:
                    logger.warning(
                        f"Attempted to remove OpenRouter API key for non-existent user ID: {user_id}"
                    )
                    raise HTTPException(status_code=404, detail="User not found")
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(
                f"Error removing OpenRouter API key for user {user_id}: {e}"
            )
            raise HTTPException(
                status_code=500, detail="Error removing OpenRouter API key"
            )

    async def save_anthropic_api_key(self, user_id: str, api_key: str) -> None:
        """Saves an encrypted Anthropic API key for a user."""
        logger.info(f"Saving Anthropic API key for user {user_id}")
        encrypted_key = self.security_manager.encrypt_data(api_key)
        try:
            await db_instance.save_anthropic_api_key(user_id, encrypted_key)
            logger.info(f"Anthropic API key saved for user {user_id}")
        except Exception as e:
            logger.error(
                f"Error saving Anthropic API key for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_anthropic_api_key(self, user_id: str) -> Optional[str]:
        """Retrieves and decrypts the Anthropic API key for a user."""
        logger.debug(f"Getting Anthropic API key for user {user_id}")
        try:
            encrypted_key = await db_instance.get_anthropic_api_key(user_id)
            if encrypted_key:
                decrypted_key = self.security_manager.decrypt_data(encrypted_key)
                logger.debug(f"Anthropic API key retrieved for user {user_id}")
                return decrypted_key
            return None
        except Exception as e:
            logger.error(
                f"Error getting Anthropic API key for user {user_id}: {e}",
                exc_info=True,
            )
            return None

    async def remove_anthropic_api_key(self, user_id: str) -> None:
        """Removes the Anthropic API key for a user."""
        logger.info(f"Removing Anthropic API key for user {user_id}")
        try:
            await db_instance.save_anthropic_api_key(user_id, None)
            logger.info(f"Anthropic API key removed for user {user_id}")
        except Exception as e:
            logger.error(
                f"Error removing Anthropic API key for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def save_openai_api_key(self, user_id: str, api_key: str) -> None:
        """Saves an encrypted OpenAI API key for a user."""
        logger.info(f"Saving OpenAI API key for user {user_id}")
        encrypted_key = self.security_manager.encrypt_data(api_key)
        try:
            await db_instance.save_openai_api_key(user_id, encrypted_key)
            logger.info(f"OpenAI API key saved for user {user_id}")
        except Exception as e:
            logger.error(
                f"Error saving OpenAI API key for user {user_id}: {e}", exc_info=True
            )
            raise

    async def get_openai_api_key(self, user_id: str) -> Optional[str]:
        """Retrieves and decrypts the OpenAI API key for a user."""
        logger.debug(f"Getting OpenAI API key for user {user_id}")
        try:
            encrypted_key = await db_instance.get_openai_api_key(user_id)
            if encrypted_key:
                decrypted_key = self.security_manager.decrypt_data(encrypted_key)
                logger.debug(f"OpenAI API key retrieved for user {user_id}")
                return decrypted_key
            return None
        except Exception as e:
            logger.error(
                f"Error getting OpenAI API key for user {user_id}: {e}", exc_info=True
            )
            return None

    async def remove_openai_api_key(self, user_id: str) -> None:
        """Removes the OpenAI API key for a user."""
        logger.info(f"Removing OpenAI API key for user {user_id}")
        try:
            await db_instance.save_openai_api_key(user_id, None)
            logger.info(f"OpenAI API key removed for user {user_id}")
        except Exception as e:
            logger.error(
                f"Error removing OpenAI API key for user {user_id}: {e}", exc_info=True
            )
            raise

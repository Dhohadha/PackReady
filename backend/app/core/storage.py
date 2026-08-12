import shutil
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO
from app.core.config import settings

class StorageService(ABC):
    @abstractmethod
    def save(self, file_data: BinaryIO, extension: str) -> str:
        """
        Saves the file data and returns a unique storage key.
        """
        pass

    @abstractmethod
    def get_path(self, storage_key: str) -> Path:
        """
        Returns the absolute path to the stored file.
        """
        pass

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """
        Deletes the file from storage.
        """
        pass


class LocalStorage(StorageService):
    def __init__(self, media_root: Path):
        self.media_root = media_root
        self.media_root.mkdir(parents=True, exist_ok=True)

    def save(self, file_data: BinaryIO, extension: str) -> str:
        # Enforce leading dot on extension
        if extension and not extension.startswith("."):
            extension = f".{extension}"
            
        # Generate safe storage filename using UUID
        safe_filename = f"{uuid.uuid4()}{extension}"
        storage_key = f"images/{safe_filename}"
        
        target_path = self.get_path(storage_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file data
        file_data.seek(0)
        with open(target_path, "wb") as f:
            shutil.copyfileobj(file_data, f)
            
        return storage_key

    def get_path(self, storage_key: str) -> Path:
        # Resolve target path
        target_path = (self.media_root / storage_key).resolve()
        
        # Prevent path traversal
        if not str(target_path).startswith(str(self.media_root)):
            raise ValueError("Path traversal detected")
            
        return target_path

    def delete(self, storage_key: str) -> None:
        target_path = self.get_path(storage_key)
        if target_path.exists() and target_path.is_file():
            target_path.unlink()


# Instantiate storage service configured with settings
media_root_path = Path(settings.MEDIA_ROOT).resolve()
storage_service = LocalStorage(media_root_path)

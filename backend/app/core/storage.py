"""
Firebase Storage configuration and utilities
"""
import os


class StorageConfig:
    """Configuration for Firebase Storage operations"""

    @classmethod
    def get_file_path(cls, project_id: str, file_id: str, timestamp: int) -> str:
        """
        Generate cloud storage path for file
        
        Format: /{env}/projects/{project_id}/files/{file_id}_{timestamp}.pdf
        """
        env_prefix = cls._get_env_prefix()
        return f"{env_prefix}/projects/{project_id}/files/{file_id}_{timestamp}.pdf"

    @classmethod
    def _get_env_prefix(cls) -> str:
        """Get environment prefix for storage paths"""
        env = os.getenv('ENVIRONMENT', 'development')
        if env == 'production':
            return 'prod'
        elif env == 'test':
            return 'test'
        else:
            return 'dev'

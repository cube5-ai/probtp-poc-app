"""
Cloud Storage configuration and utilities
"""
import os


class StorageConfig:
    """Configuration for Google Cloud Storage operations"""

    # Environment-based bucket configuration (using single bucket for POC)
    BUCKET_NAMES: dict[str, str] = {
        'production': 'probtp-poc-prod',
        'development': 'probtp-poc-prod',
        'test': 'probtp-poc-prod'
    }

    @classmethod
    def get_bucket_name(cls) -> str:
        """Get bucket name based on current environment"""
        env = os.getenv('ENVIRONMENT', 'development')
        return cls.BUCKET_NAMES.get(env, cls.BUCKET_NAMES['development'])

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

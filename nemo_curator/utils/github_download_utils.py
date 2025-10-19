import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def download_with_url(to_file_path: str, urls: list[str], min_bytes=1E0, error_msg=''):
    """Download a file from a URL."""
    logger.info(f"Downloading file from URL: {urls} to {to_file_path}")
    file = Path(str(to_file_path).strip().replace("'", ""))
    if file.exists():
        logger.info(f"File {file} already exists")
        return

def download_repo(to_file_path, repo_name, tag):
    """Download a repo from GitHub."""
    logger.info(f"Downloading repo from GitHub: {repo_name} to {to_file_path}")
    file = Path(str(to_file_path).strip().replace("'", ""))
    if file.exists():
        logger.info(f"File {file} already exists")
        return

    return 
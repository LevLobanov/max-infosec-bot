from typing import Dict, Any, Tuple
import logging
import os
from config import settings
import vt


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

_VIRUSTOTAL_CLIENT: vt.Client | None = None


async def setup_vt_client():
    """Инициализирует асинхронный клиент VirusTotal."""
    global _VIRUSTOTAL_CLIENT
    if not _VIRUSTOTAL_CLIENT:
        _VIRUSTOTAL_CLIENT = vt.Client(settings.VIRUSTOTAL_API_TOKEN, timeout=15)
        logging.info("VirusTotal API client initialized.")


async def exit_vt_client():
    """Закрывает асинхронный клиент VirusTotal."""
    global _VIRUSTOTAL_CLIENT
    if _VIRUSTOTAL_CLIENT:
        await _VIRUSTOTAL_CLIENT.close_async()
        _VIRUSTOTAL_CLIENT = None
        logging.info("VirusTotal API client closed.")


async def check_link(link: str) -> Tuple[str, Dict[str, int]]:
    """
    Сканирует ссылку на вредоносы в VirusTotal.
    """
    await setup_vt_client()
    if _VIRUSTOTAL_CLIENT is None:
        raise RuntimeError("VirusTotal client not initialized.")

    logging.info(f"Submitting link for analysis: {link}")

    try:
        analysis = await _VIRUSTOTAL_CLIENT.scan_url_async(
            link, wait_for_completion=True
        )
        return analysis.id, analysis.stats  # type: ignore

    except vt.APIError as e:
        logging.error(f"VT URL submission failed: {e}")
        raise


async def check_file(file_path: str) -> Tuple[str, Dict[str, Any]]:
    """
    Сканирует файл на вредоносы в VirusTotal.
    """
    await setup_vt_client()
    if _VIRUSTOTAL_CLIENT is None:
        raise RuntimeError("VirusTotal client not initialized.")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    logging.info(f"Submitting file for analysis: {file_path}")

    try:
        with open(file_path, "rb") as file:
            analysis = await _VIRUSTOTAL_CLIENT.scan_file_async(
                file, wait_for_completion=True
            )
            print(analysis)
            return analysis.id, analysis.stats  # type: ignore

    except vt.APIError as e:
        logging.error(f"VT File upload failed: {e}")
        raise
    except Exception as e:
        logging.error(f"An error occurred during file check: {e}")
        raise

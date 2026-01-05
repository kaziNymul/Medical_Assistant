"""Utilities module for the Medical Assistant."""

from src.utils.masking import (
    MaskingResult,
    PIIMasker,
    get_masker,
    mask_text,
    pseudonymize_id,
)
from src.utils.logging import (
    logger,
    log_error,
    log_extraction,
    log_query,
    setup_logging,
)

__all__ = [
    "MaskingResult",
    "PIIMasker",
    "get_masker",
    "mask_text",
    "pseudonymize_id",
    "logger",
    "log_error",
    "log_extraction",
    "log_query",
    "setup_logging",
]

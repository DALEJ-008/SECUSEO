"""Twilio integration removed.

This module used to provide Twilio-based SMS and Verify APIs. Per project
decision, Twilio support has been removed; these functions are kept as
no-op shims so callers won't fail with ImportError. They return conservative
failure values and log a message.
"""
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def send_sms(to_phone: str, body: str) -> bool:
    """No-op SMS sender. Always returns False (message not sent).

    Kept so existing call sites can continue to import this module without
    raising errors. Use the local file-based OTP flow in the application
    for verification instead.
    """
    logger.info('Twilio integration removed: send_sms no-op called for %s', to_phone)
    return False


def send_verification(to_phone: str, channel: str = 'sms') -> Tuple[bool, str]:
    """No-op verification starter. Returns (False, 'twilio_removed')."""
    logger.info('Twilio integration removed: send_verification no-op for %s', to_phone)
    return False, 'twilio_removed'


def check_verification(to_phone: str, code: str) -> Tuple[bool, str]:
    """No-op verification checker. Returns (False, 'twilio_removed')."""
    logger.info('Twilio integration removed: check_verification no-op for %s', to_phone)
    return False, 'twilio_removed'

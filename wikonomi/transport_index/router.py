"""Inbound WhatsApp routing hooks for the transport index app."""

import logging

logger = logging.getLogger(__name__)


def dispatch_inbound_message(message, metadata=None):
    """Dispatch a parsed WhatsApp inbound message.

    This is the integration seam for future transport-index conversation logic
    (or a future gst_agent integration). It currently records the inbound event
    and returns ``None`` so webhook acknowledgement remains fast and reliable.
    """
    logger.info(
        'Received WhatsApp message for transport_index',
        extra={'message': message, 'metadata': metadata or {}},
    )
    return None

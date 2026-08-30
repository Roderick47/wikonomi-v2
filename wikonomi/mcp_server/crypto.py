import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def hash_secret(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _fernet():
    configured_key = getattr(settings, 'WIKONOMI_MCP_OAUTH_ENCRYPTION_KEY', '')
    if configured_key:
        key = configured_key.encode('ascii')
    else:
        digest = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value):
    if not value:
        return ''
    return _fernet().encrypt(value.encode('utf-8')).decode('ascii')


def decrypt_secret(value):
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode('ascii')).decode('utf-8')
    except InvalidToken:
        return None

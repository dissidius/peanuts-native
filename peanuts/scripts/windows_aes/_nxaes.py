"""Windows Unreal pak AES helper compatible with uepak.py's _nxaes.ecb_decrypt.

Uses PyCryptodome's maintained AES implementation on the PC, not Nintendo SDK
and not the Android packer's own native _nxaes extension. Do not log keys.
"""
from Crypto.Cipher import AES


def ecb_decrypt(key, data):
    if not isinstance(key, bytes) or len(key) not in (16, 32):
        raise ValueError("AES key must be 16 or 32 bytes")
    if not isinstance(data, bytes) or len(data) % 16:
        raise ValueError("AES ECB input must be whole 16-byte blocks")
    return AES.new(key, AES.MODE_ECB).decrypt(data)

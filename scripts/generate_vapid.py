"""
Standalone script to generate VAPID keys for Web Push Notifications.
"""

from __future__ import annotations

import base64

import cryptography.hazmat.primitives.serialization as serialization
from py_vapid import Vapid


def generate_vapid_keys():
    vapid = Vapid()
    vapid.generate_keys()

    pub = vapid.public_key
    priv = vapid.private_key

    # Make sure Pylance and runtime both know
    # that the generated keys actually exist.
    if pub is None:
        raise RuntimeError(
            "VAPID public key generation returned None."
        )

    if priv is None:
        raise RuntimeError(
            "VAPID private key generation returned None."
        )

    pub_bytes = pub.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )

    priv_bytes = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )

    pub_b64 = (
        base64.urlsafe_b64encode(pub_bytes)
        .rstrip(b"=")
        .decode()
    )

    priv_pem = priv_bytes.decode()

    print("=" * 60)
    print("VAPID Keys Generated Successfully!")
    print("=" * 60)

    print("\nVAPID_PUBLIC_KEY:")
    print(pub_b64)

    print("\nVAPID_PRIVATE_KEY:")
    print(priv_pem)

    print("=" * 60)

    return pub_b64, priv_pem


if __name__ == "__main__":
    generate_vapid_keys()
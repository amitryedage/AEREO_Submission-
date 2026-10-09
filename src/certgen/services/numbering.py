"""Unique certificate number generator using Crockford Base32 alphabet."""

import secrets

# Crockford Base32 alphabet excluding I, L, O, and U to prevent visual ambiguity
CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_certificate_number(length: int = 10) -> str:
    """Generate a unique human-readable certificate identifier (e.g. CG-7K3M9PX2QD)."""
    random_chars = "".join(secrets.choice(CROCKFORD_BASE32) for _ in range(length))
    return f"CG-{random_chars}"

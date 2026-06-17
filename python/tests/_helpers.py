import hashlib
import structlog

from app.models.database import NodeTier


logger = structlog.get_logger(__name__)


def _sample_public_key_pem() -> str:
    return (
        "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzF7u0BBFUwMZ8aZ1NFxl\n"
        "loQvIIKJQ6TFBnDQdfF1QsNhOtbC6DqnDcbxkhBtUkcBFlWclqscSPLTQASzGcbXmC\n"
        "3RFAjQn3zF5M0SHTb8XPZ0k9lBbRtN+rFJOIat4Or7W6LW/xYdCW5ZfqIYhK0GLIM\n"
        "zJ8T5wN6SSPQPyMNmFxzGbOJAZZfRfHJCXuIygH3oHTnMFvg8R8ZF5fxZtNZPBSIb\n"
        "nWcwgaBjFOEjDPbTzkp4W9FqvLO5BNqsi5mQd9LgHsY8kCCln2Kuk0Xb0qxJwDlFY\n"
        "T8zpM7UQnH7xn1y3NNyBNZ2KucqgUCYbMdJmRAWExC5djA0P+4RJEEDwQIDAQAB\n"
        "-----END PUBLIC KEY-----\n"
    )


def fingerprint_of(public_key_pem: str) -> str:
    raw = public_key_pem.replace("\n", "").encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def sample_node_id() -> str:
    return fingerprint_of(_sample_public_key_pem())

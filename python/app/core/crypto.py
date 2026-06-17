from rsa import PublicKey, PrivateKey, generate_key
from pydantic import BaseModel


class KeyPair(BaseModel):
    public_key_pem: str
    private_key_pem: str
    fingerprint: str

    @classmethod
    def generate(cls) -> "KeyPair":
        key = generate_key(2048)
        pub_raw = key.public_key()
        pub_pem = pub_raw.save_pkcs1()
        priv_pem = key.save_pkcs1()
        fp = hashlib.sha256(pub_pem).hexdigest()[:16]
        return cls(public_key_pem=pub_pem, private_key_pem=priv_pem, fingerprint=fp)


async def verify_signature(
    public_key_pem: str,
    signature: bytes,
    message: bytes,
) -> bool:
    pub = load_pkcs1_public_key(public_key_pem.encode())
    try:
        pub.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False

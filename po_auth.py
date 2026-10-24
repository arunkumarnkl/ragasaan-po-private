"""Password verification with legacy migration compatibility."""
import hashlib
import hmac

def authenticate(username,password,users):
    for row in users:
        if str(row.get("username","")).casefold().strip()!=username.casefold().strip():continue
        stored=str(row.get("password", ""))
        if stored.startswith("pbkdf2_sha256$"):
            try:
                _, iterations, salt, digest = stored.split("$",3)
                attempt=hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(salt),int(iterations))
                matches=hmac.compare_digest(attempt.hex(),digest)
            except (ValueError,TypeError):matches=False
        else:
            matches=hmac.compare_digest(password,stored)
        if matches:return row
    return None


def password_hash(raw):
    import secrets
    salt=secrets.token_bytes(16)
    derived=hashlib.pbkdf2_hmac("sha256",raw.encode(),salt,260000)
    return f"pbkdf2_sha256$260000${salt.hex()}${derived.hex()}"



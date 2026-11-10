import base64, hashlib, hmac, secrets, time
import jwt
from app.config import JWT_SECRET

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000)
    return "pbkdf2_sha256$600000$" + salt + "$" + base64.b64encode(digest).decode()

def verify_password(password, stored):
    try:
        alg, iterations, salt, digest = stored.split("$")
        if alg != "pbkdf2_sha256": return False
        actual = base64.b64encode(hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))).decode()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError): return False

def token(user_id):
    now = int(time.time())
    return jwt.encode({"sub":str(user_id),"iat":now,"exp":now+3600}, JWT_SECRET, algorithm="HS256")

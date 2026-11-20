import os
import errno
from contextlib import contextmanager
import secrets
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres@127.0.0.1:55432/linchong")
JWT_SECRET_MIN_LENGTH = 32
JWT_SECRET_LOCK_TIMEOUT = 5.0
JWT_SECRET_LOCK_POLL_INTERVAL = 0.05


def _read_valid_secret(secret_path):
    try:
        secret = secret_path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, UnicodeError):
        return None
    return secret if len(secret) >= JWT_SECRET_MIN_LENGTH else None


@contextmanager
def _secret_lock(lock_path):
    # Keep the file: unlinking it could let waiters lock different inodes.
    # The OS releases the actual lock even if the process is killed.
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    deadline = time.monotonic() + JWT_SECRET_LOCK_TIMEOUT
    try:
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                if time.monotonic() >= deadline:
                    raise RuntimeError("Timed out waiting for JWT_SECRET initialization") from exc
                time.sleep(JWT_SECRET_LOCK_POLL_INTERVAL)
        yield
    finally:
        try:
            if acquired:
                if os.name == "nt":
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _initialize_local_secret(secret_path):
    existing = _read_valid_secret(secret_path)
    if existing is not None:
        return existing
    lock_path = secret_path.with_name(secret_path.name + ".lock")
    temp_path = secret_path.with_name(secret_path.name + ".tmp")
    with _secret_lock(lock_path):
        existing = _read_valid_secret(secret_path)
        if existing is not None:
            return existing
        try:
            secret = secrets.token_urlsafe(32)
            fd = os.open(temp_path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as secret_file:
                secret_file.write(secret)
                secret_file.flush()
                os.fsync(secret_file.fileno())
            os.replace(temp_path, secret_path)
            return secret
        finally:
            temp_path.unlink(missing_ok=True)


def _load_jwt_secret():
    configured = os.getenv("JWT_SECRET")
    if configured is not None:
        if len(configured) < JWT_SECRET_MIN_LENGTH:
            raise RuntimeError("JWT_SECRET must contain at least 32 characters")
        return configured

    if os.getenv("APP_ENV", "development").strip().lower() == "production":
        raise RuntimeError("JWT_SECRET must be explicitly configured in production")

    secret_path = ROOT / ".runtime" / "jwt_secret"
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    return _initialize_local_secret(secret_path)


JWT_SECRET = _load_jwt_secret()
COMMUNITY = os.getenv("COMMUNITY_CODE", "linchong-001")
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(ROOT / "storage"))).resolve()
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

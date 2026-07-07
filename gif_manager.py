import hashlib
import shutil
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from config import ASSETS_DIR, ensure_dirs


def _safe_name(url: str) -> str:
    digest = hashlib.md5(url.encode("utf-8")).hexdigest()[:10]
    parsed = urlparse(url)
    tail = Path(parsed.path).name or "pet.gif"
    if not tail.lower().endswith((".gif", ".png", ".webp", ".apng")):
        tail = f"{tail}.gif"
    return f"{digest}_{tail}"


def import_local(path: str) -> str:
    """Copy a local GIF/image file into the asset cache and return the new path."""
    ensure_dirs()
    src = Path(path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(path)
    dst = ASSETS_DIR / src.name
    if src != dst:
        shutil.copy2(src, dst)
    return str(dst)


def download(url: str, timeout: int = 20) -> str:
    """Download a remote GIF into the asset cache and return the local path."""
    ensure_dirs()
    dst = ASSETS_DIR / _safe_name(url)
    if dst.exists() and dst.stat().st_size > 0:
        return str(dst)
    req = Request(url, headers={"User-Agent": "desktop-pet/1.0"})
    with urlopen(req, timeout=timeout) as resp, open(dst, "wb") as fp:
        shutil.copyfileobj(resp, fp)
    if dst.stat().st_size == 0:
        dst.unlink(missing_ok=True)
        raise IOError(f"Empty download: {url}")
    return str(dst)


def list_local() -> list[str]:
    ensure_dirs()
    exts = {".gif", ".png", ".webp", ".apng"}
    return sorted(
        str(p) for p in ASSETS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in exts
    )

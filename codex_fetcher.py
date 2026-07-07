import json
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

from config import CONFIG_DIR, ensure_dirs

PETS_DIR = CONFIG_DIR / "codex-pets"
API = "https://codex-pets.net/api/pets"


def _get_json(url: str, timeout: int = 20) -> dict:
    req = Request(url, headers={"User-Agent": "desktop-pet/1.0", "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, dst: Path, timeout: int = 30) -> None:
    req = Request(url, headers={"User-Agent": "desktop-pet/1.0"})
    with urlopen(req, timeout=timeout) as resp, open(dst, "wb") as fp:
        shutil.copyfileobj(resp, fp)


def fetch(slug: str) -> Path:
    """
    Fetch a codex-pets pet by slug (e.g. "hoshimachi-suisei").
    Downloads spritesheet.webp + pet.json into ~/.desktop-pet/codex-pets/<slug>/.
    Returns the path to the local spritesheet.webp.
    """
    ensure_dirs()
    PETS_DIR.mkdir(parents=True, exist_ok=True)
    meta = _get_json(f"{API}/{slug}")
    pet = meta.get("pet") or meta
    sheet_url = pet.get("spritesheetUrl")
    if not sheet_url:
        raise ValueError(f"No spritesheetUrl for '{slug}'")
    pet_dir = PETS_DIR / slug
    pet_dir.mkdir(parents=True, exist_ok=True)
    sheet_path = pet_dir / "spritesheet.webp"
    if not sheet_path.exists() or sheet_path.stat().st_size == 0:
        _download(sheet_url, sheet_path)
    manifest = {
        "id": pet.get("id", slug),
        "displayName": pet.get("displayName", slug),
        "description": pet.get("description", ""),
        "spritesheetPath": "spritesheet.webp",
        "kind": pet.get("kind", "person"),
    }
    (pet_dir / "pet.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return sheet_path


def list_local() -> list[str]:
    if not PETS_DIR.exists():
        return []
    out = []
    for d in sorted(PETS_DIR.iterdir()):
        sheet = d / "spritesheet.webp"
        if sheet.is_file():
            out.append(str(sheet))
    return out

"""Guards for the modular layout: file-relative paths must still point at backend/."""
from pathlib import Path

from app.core import config


def test_base_dir_is_backend_root():
    backend = Path(__file__).resolve().parents[1]
    assert config.BASE_DIR == backend
    assert config.DATA_DIR == backend / "data"
    assert (config.BASE_DIR / "app" / "main.py").is_file()


def test_every_module_registers_a_router():
    from app.modules import MODULES, routers

    assert len(list(routers())) >= len(MODULES)

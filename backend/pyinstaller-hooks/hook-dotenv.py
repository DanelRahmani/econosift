"""PyInstaller hook for python-dotenv."""
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('dotenv')

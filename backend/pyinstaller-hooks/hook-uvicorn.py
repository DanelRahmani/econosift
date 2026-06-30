"""PyInstaller hook for uvicorn — collect all submodules and data files."""
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules('uvicorn')
datas = collect_data_files('uvicorn')

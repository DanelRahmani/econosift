from backend.services.bulk_data_service import _download_worldbank, _download_famafrench, _download_imf

print("Testing World Bank...")
wb = _download_worldbank()
print(f"  rows={wb['rows']}")
print(f"  error={wb['error'][:200] if wb['error'] else 'OK'}")

print("Testing Fama-French...")
ff = _download_famafrench()
print(f"  rows={ff['rows']}")
print(f"  error={ff['error'][:200] if ff['error'] else 'OK'}")

print("Testing IMF...")
imf = _download_imf()
print(f"  rows={imf['rows']}")
print(f"  error={imf['error'][:200] if imf['error'] else 'OK'}")

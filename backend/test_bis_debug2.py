"""Debug BIS property VALUE column"""
import asyncio
import sys
sys.path.insert(0, "/app")

async def test():
    from backend.sources.source_bis import _fetch_bis_zip
    
    df = _fetch_bis_zip("property")
    if df is None:
        print("None")
        return
    
    # Check VALUE column
    val_cols = [c for c in df.columns if c.startswith("VALUE:")]
    print(f"VALUE columns: {val_cols}")
    for vc in val_cols:
        print(f"\n{vc} unique values:")
        print(df[vc].unique()[:20])
    
    # Check REF_SECTOR
    sector_cols = [c for c in df.columns if "REF_SECTOR" in c.upper() or "SECTOR" in c.upper()]
    print(f"\nSECTOR columns: {sector_cols}")
    if sector_cols:
        print(df[sector_cols[0]].unique()[:20])
    
    # After filtering 628:
    col_measure = next(c for c in df.columns if "MEASURE" in c.upper())
    df_idx = df[df[col_measure].str.startswith("628:", na=False)]
    print(f"\nAfter 628 filter: {len(df_idx)} rows")
    
    # Check VALUE column in filtered
    for vc in val_cols:
        print(f"\n{vc} after 628 filter:")
        print(df_idx[vc].unique()[:20])
    
    # Check REF_SECTOR after 628 filter
    if sector_cols:
        print(f"\n{sector_cols[0]} after 628 filter:")
        print(df_idx[sector_cols[0]].unique()[:20])

asyncio.run(test())

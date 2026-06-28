"""Quick BIS property data debug — run inside Docker: python test_bis_debug.py"""
import asyncio
import sys
sys.path.insert(0, "/app")

async def test():
    from backend.sources.source_bis import _fetch_bis_zip, _parse_bis_flat
    
    print("=== Testing BIS property ZIP fetch ===")
    df = _fetch_bis_zip("property")
    if df is None:
        print("ZIP fetch returned None")
        return
    print(f"Columns ({len(df.columns)}): {list(df.columns)[:20]}")
    print(f"Rows: {len(df)}")
    
    # Check MEASURE column
    measure_cols = [c for c in df.columns if "MEASURE" in c]
    if measure_cols:
        mc = measure_cols[0]
        print(f"MEASURE column: {mc}")
        print(f"Unique MEASURE values: {df[mc].unique()[:20]}")
        print(f"R with 'R:' prefix: {(df[mc].str.startswith('R:', na=False)).sum()}")
    
    # Check REF_AREA column  
    area_cols = [c for c in df.columns if "REF_AREA" in c]
    if area_cols:
        ac = area_cols[0]
        print(f"REF_AREA column: {ac}")
        print(f"Unique REF_AREA values: {df[ac].unique()[:20]}")
        print(f"US rows: {(df[ac].str.startswith('US:', na=False)).sum()}")
    
    # Check FREQ
    freq_cols = [c for c in df.columns if "FREQ" in c]
    print(f"FREQ column: {freq_cols}")
    
    # Try parsing for US
    print("\n=== Parsing for US ===")
    parsed = _parse_bis_flat(df, iso2_filter="US", freq="Q")
    print(f"Parsed US rows: {len(parsed)}")
    if len(parsed) > 0:
        print(parsed.head())
        print(parsed.tail())
    else:
        print("No parsed rows!")
        
        # Try without filtering
        parsed2 = _parse_bis_flat(df, freq="Q")
        print(f"Parsed all rows (Q): {len(parsed2)}")
        if len(parsed2) > 0:
            print(f"Unique iso2s: {parsed2['iso2'].unique()[:10]}")
    
    print("\n=== Testing credit_gap ===")
    df2 = _fetch_bis_zip("credit_gap")
    if df2 is not None:
        print(f"Columns: {list(df2.columns)[:20]}")
        print(f"Rows: {len(df2)}")
        cg_cols = [c for c in df2.columns if "CG_DTYPE" in c]
        if cg_cols:
            print(f"Unique CG_DTYPE: {df2[cg_cols[0]].unique()[:20]}")

asyncio.run(test())

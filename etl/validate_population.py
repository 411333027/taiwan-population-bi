# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas", "xlrd"]
# ///
"""驗證 data/population_by_year.csv：和原始 .xls 獨立比對，不共用 ETL 的程式碼

用法：uv run etl/validate_population.py
"""
import re
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "raw" / "縣市三階段人口及扶養比(96).xls"
CSV = ROOT / "data" / "population_by_year.csv"
RATIOS = ['pct_0_14', 'pct_15_64', 'pct_65_plus',
          'young_dependency_ratio', 'old_dependency_ratio', 'dependency_ratio', 'aging_index']

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}" + (f"：{detail}" if detail else ""))


def raw_rows():
    """原始檔裡每一列有人口數的資料，名稱只去空白、不做任何對映"""
    xls = pd.ExcelFile(SRC)
    out = []
    for s in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=s, header=None)
        for _, r in df.iterrows():
            if isinstance(r[1], (int, float)) and pd.notna(r[1]):
                out.append([int(s), re.sub(r'\s+', '', str(r[0]))] + list(r[1:12]))
    return pd.DataFrame(out, columns=['roc_year', 'raw_region', 'pop_total', 'pop_0_14', 'pop_15_64',
                                      'pop_65_plus'] + RATIOS)


df = pd.read_csv(CSV, encoding='utf-8-sig')
raw = raw_rows()
cty = df[df['level'] == '縣市']

print("— 結構 —")
check("年份數 19（民國 96～114）", df['roc_year'].nunique() == 19, f"{df['roc_year'].min()}～{df['roc_year'].max()}")
check("每年都是 22 縣市", (cty.groupby('roc_year').size() == 22).all())
check("每個縣市都有 19 年", (cty.groupby('region').size() == 19).all(), f"{cty['region'].nunique()} 個縣市")
check("每年 1 列全國、2 列省", (df[df.level == '全國'].groupby('roc_year').size() == 1).all()
      and (df[df.level == '省'].groupby('roc_year').size() == 2).all())
check("沒有空值", int(df.isna().sum().sum()) == 0)
check("人口數都 > 0", (df['pop_total'] > 0).all())

print("\n— 加總 —")
tot = df[df['region'] == '總計'].set_index('roc_year')['pop_total']
check("縣市加總 = 總計（每年）", cty.groupby('roc_year')['pop_total'].sum().equals(tot))
check("0～14 + 15～64 + 65+ = 總人口（每列）",
      (df['pop_0_14'] + df['pop_15_64'] + df['pop_65_plus'] == df['pop_total']).all())
raw_tot = raw[raw['raw_region'] == '總計'].set_index('roc_year')['pop_total'].astype('int64')
check("總計和原始檔一致", raw_tot.sort_index().equals(tot.sort_index()))

print("\n— 和原始檔逐列比對 —")
raw_cty = raw[~raw['raw_region'].isin(['總計', '臺灣地區', '臺灣省', '福建省'])]
merged_back = (df[df.level == '縣市']
               .assign(raw_region=lambda d: d['raw_region'].str.split('+')).explode('raw_region'))
check("原始檔每個縣市列都對得到 CSV",
      len(raw_cty.merge(merged_back, on=['roc_year', 'raw_region'])) == len(raw_cty),
      f"原始 {len(raw_cty)} 列")
single = df[~df['raw_region'].str.contains(r'\+', regex=True)]
m = single.merge(raw, on=['roc_year', 'raw_region'], suffixes=('', '_raw'))
check("未合併的列：人數與原始檔完全相同",
      all((m[c] == m[c + '_raw'].astype('int64')).all() for c in ['pop_total', 'pop_0_14', 'pop_15_64', 'pop_65_plus']),
      f"{len(m)} 列")
err = max((m[c] - m[c + '_raw'].astype(float)).abs().max() for c in RATIOS)
check("未合併的列：重算的比例與原始檔相同（誤差 < 1e-9）", err < 1e-9, f"最大誤差 {err:.1e}")

print("\n— 縣市合併紀錄 —")
for _, r in df[df['raw_region'] != df['region']].drop_duplicates(['region', 'raw_region']).iterrows():
    yrs = df[(df.region == r.region) & (df.raw_region == r.raw_region)]['roc_year']
    print(f"   {r.raw_region} → {r.region}（{yrs.min()}～{yrs.max()} 年）")

ok = all(results)
print(f"\n{'🎉 全部 ' + str(len(results)) + ' 項通過' if ok else '⚠️ 有檢查未通過'}")
sys.exit(0 if ok else 1)

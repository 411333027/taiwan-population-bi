# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas"]
# ///
"""把 data/population_by_year.csv 轉成網頁可直接載入的 docs/data.js（雙擊 index.html 就能開，不需要伺服器）

用法：uv run etl/build_data.py
"""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "population_by_year.csv"
OUT = ROOT / "docs" / "data.js"

FIELDS = ['roc_year', 'region', 'raw_region', 'pop_total', 'pop_0_14', 'pop_15_64', 'pop_65_plus']

df = pd.read_csv(CSV, encoding='utf-8-sig')
# 網頁只用全國與縣市；省不含直轄市，放進去容易被誤加
df = df[df['level'].isin(['全國', '縣市'])].sort_values(['roc_year', 'pop_total'], ascending=[True, False])

# 只送人數，比例在網頁端由人數計算（和 ETL 的定義相同），檔案比較小
rows = df[FIELDS].values.tolist()
payload = {
    'fields': FIELDS,
    'rows': rows,
    'source': '內政部戶政司｜各縣市年底三階段年齡人口數、扶養比及老化指數',
    'years': [int(df['roc_year'].min()), int(df['roc_year'].max())],
}
OUT.parent.mkdir(exist_ok=True)
OUT.write_text('window.POP_DATA = ' + json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + ';\n',
               encoding='utf-8')

# 核對：114 年全國總人口應與原始報表相同
tot114 = df[(df.roc_year == 114) & (df.region == '總計')]['pop_total'].item()
assert tot114 == 23299132, f"114 年總計 {tot114} 與原始報表 23299132 不符"
cty = df[df.region != '總計'].groupby('roc_year')['pop_total'].sum()
assert cty.equals(df[df.region == '總計'].set_index('roc_year')['pop_total']), "縣市加總不等於總計"
print(f"✅ 寫出 {OUT.relative_to(ROOT)}：{len(rows)} 列（{df.region.nunique() - 1} 縣市 + 全國 × "
      f"{df.roc_year.nunique()} 年），{OUT.stat().st_size / 1024:.1f} KB；114 年總計 {tot114:,} 人")

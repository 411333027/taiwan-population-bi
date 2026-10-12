# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas", "xlrd"]
# ///
"""把「縣市三階段人口及扶養比」.xls 的 19 個工作表（民國 96～114 年）轉成 data/population_by_year.csv

用法：uv run etl/etl_population.py
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "raw" / "縣市三階段人口及扶養比(96).xls"
OUT = ROOT / "data" / "population_by_year.csv"

COLUMNS = [
    'region', 'pop_total', 'pop_0_14', 'pop_15_64', 'pop_65_plus',
    'pct_0_14', 'pct_15_64', 'pct_65_plus',
    'young_dependency_ratio', 'old_dependency_ratio', 'dependency_ratio', 'aging_index',
]
POP_COLS = ['pop_total', 'pop_0_14', 'pop_15_64', 'pop_65_plus']

# 舊縣市對映至現行縣市（99 年 12 月 25 日縣市改制；桃園縣 103 年改制為桃園市）
COUNTY_MAPPING = {
    '臺北縣': '新北市',
    '桃園縣': '桃園市',
    '臺中縣': '臺中市',
    '臺南縣': '臺南市',
    '高雄縣': '高雄市',
}


def get_level(region):
    if region == '總計':
        return '全國'
    if region in ('臺灣省', '福建省'):
        return '省'
    return '縣市'


def read_sheet(xls, sheet_name):
    df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
    roc_year = int(sheet_name)

    data_df = df.iloc[3:].copy()
    data_df.columns = COLUMNS

    # 1. 清除區域名稱的多餘空格（含全形空白）
    data_df['region'] = data_df['region'].astype(str).str.replace(r'\s+', '', regex=True)

    # 2. 有效數據列的 pop_total 一定是數字：排除表頭、空白列與表尾說明；『臺灣地區』是 96～98 年的區域小計
    data_df = data_df[pd.to_numeric(data_df['pop_total'], errors='coerce').notna()]
    data_df = data_df[data_df['region'] != '臺灣地區']

    # 3. 行政區層級
    data_df['level'] = data_df['region'].apply(get_level)

    # 4. 保留原始名稱，並將舊縣市名稱映射至現行名稱
    data_df['raw_region'] = data_df['region']
    data_df['region'] = data_df['region'].replace(COUNTY_MAPPING)

    data_df['roc_year'] = roc_year
    data_df['year'] = roc_year + 1911

    for c in POP_COLS:
        data_df[c] = pd.to_numeric(data_df[c])
    return data_df


def main():
    xls = pd.ExcelFile(SRC)
    final_df = pd.concat([read_sheet(xls, s) for s in xls.sheet_names], ignore_index=True)

    # 5. 合併同年同名的列（96～98 年的臺中縣＋臺中市等），比例不能相加，只加總人數
    grouped = final_df.groupby(['year', 'roc_year', 'region', 'level'], as_index=False).agg(
        raw_region=('raw_region', lambda s: '+'.join(sorted(set(s)))),
        pop_total=('pop_total', 'sum'),
        pop_0_14=('pop_0_14', 'sum'),
        pop_15_64=('pop_15_64', 'sum'),
        pop_65_plus=('pop_65_plus', 'sum'),
    )

    # 6. 由人數重新計算比例與指標
    g = grouped
    g['pct_0_14'] = g['pop_0_14'] / g['pop_total'] * 100
    g['pct_15_64'] = g['pop_15_64'] / g['pop_total'] * 100
    g['pct_65_plus'] = g['pop_65_plus'] / g['pop_total'] * 100
    g['young_dependency_ratio'] = g['pop_0_14'] / g['pop_15_64'] * 100
    g['old_dependency_ratio'] = g['pop_65_plus'] / g['pop_15_64'] * 100
    g['dependency_ratio'] = (g['pop_0_14'] + g['pop_65_plus']) / g['pop_15_64'] * 100
    g['aging_index'] = g['pop_65_plus'] / g['pop_0_14'] * 100

    # 7. 基本檢查（完整驗證見 etl/validate_population.py）
    assert g.isna().sum().sum() == 0, "❌ 存在空值 (NaN)"
    assert (g['pop_total'] > 0).all(), "❌ 存在人口數 <= 0 的列"
    assert (g[g['level'] == '縣市'].groupby('roc_year').size() == 22).all(), "❌ 每年縣市數量不等於 22 個"
    assert g['roc_year'].nunique() == 19, "❌ 年份數量不等於 19 個"
    cty_sum = g[g['level'] == '縣市'].groupby('roc_year')['pop_total'].sum()
    tot = g[g['region'] == '總計'].set_index('roc_year')['pop_total']
    assert cty_sum.equals(tot), "❌ 縣市加總不等於總計（年份未對齊或數據有誤）"

    OUT.parent.mkdir(exist_ok=True)
    g.to_csv(OUT, index=False, encoding='utf-8-sig')
    print(f"✅ 檢查通過，寫出 {len(g)} 列 → {OUT.relative_to(ROOT)}")


if __name__ == '__main__':
    main()

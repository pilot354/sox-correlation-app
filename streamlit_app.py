from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import yfinance as yf

SOX_TICKER = "^SOX"
MIN_OBSERVATIONS = 8
ROLLING_WINDOW = 20
ROLLING_MIN_PERIODS = 5
DETAIL_ROWS = 20
BATCH_SIZE = 20
CACHE_TTL_SECONDS = 60 * 60


class AppError(Exception):
    """画面に安全に表示できるアプリ用エラー。"""


@dataclass(frozen=True)
class StockInfo:
    code: str
    name: str
    category: str
    focus: str

    @property
    def ticker(self) -> str:
        return f"{self.code}.T"

    @property
    def label(self) -> str:
        return f"{self.name}（{self.code}）｜{self.category}"


# ユーザー指定の半導体関連銘柄ユニバース。
STOCKS: tuple[StockInfo, ...] = (
    StockInfo("167A", "リョーサン菱洋ホールディングス", "商社・流通", "半導体・電子部品商社"),
    StockInfo("2760", "東京エレクトロン デバイス", "商社・流通", "半導体商社・技術支援"),
    StockInfo("285A", "キオクシアホールディングス", "半導体・デバイス", "NAND型フラッシュメモリ"),
    StockInfo("3132", "マクニカホールディングス", "商社・流通", "半導体・ネットワーク商社"),
    StockInfo("3156", "レスター", "商社・流通", "半導体・電子部品の販売／技術支援"),
    StockInfo("3402", "東レ", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("3407", "旭化成", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("3436", "SUMCO", "材料・化学・ガス", "シリコンウェハー"),
    StockInfo("4004", "レゾナック・ホールディングス", "材料・化学・ガス", "半導体・電子材料"),
    StockInfo("4005", "住友化学", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4021", "日産化学", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4043", "トクヤマ", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4044", "セントラル硝子", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4047", "関東電化工業", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4062", "イビデン", "材料・化学・ガス", "ICパッケージ基板・電子材料"),
    StockInfo("4063", "信越化学工業", "材料・化学・ガス", "シリコンウェハー・高機能材料"),
    StockInfo("4078", "堺化学工業", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4088", "エア・ウォーター", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4091", "日本酸素ホールディングス", "材料・化学・ガス", "高純度産業ガス"),
    StockInfo("4092", "日本化学工業", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4097", "高圧ガス工業", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4098", "第一稀元素化学工業", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4109", "ステラケミファ", "材料・化学・ガス", "高純度フッ素化学品"),
    StockInfo("4112", "保土谷化学工業", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4183", "三井化学", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4186", "東京応化工業", "材料・化学・ガス", "フォトレジスト"),
    StockInfo("4187", "大阪有機化学工業", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4188", "三菱ケミカルグループ", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4203", "住友ベークライト", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4206", "アイカ工業", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4369", "トリケミカル研究所", "材料・化学・ガス", "高純度半導体用化学品"),
    StockInfo("4401", "ADEKA", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4966", "上村工業", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("4970", "東洋合成工業", "材料・化学・ガス", "感光性材料"),
    StockInfo("4971", "メック", "材料・化学・ガス", "電子基板向け薬品"),
    StockInfo("4973", "高純度化学", "材料・化学・ガス", "貴金属化合物・高純度材料"),
    StockInfo("4975", "JCU", "材料・化学・ガス", "表面処理薬品"),
    StockInfo("4980", "デクセリアルズ", "材料・化学・ガス", "光学・接合材料"),
    StockInfo("5201", "AGC", "材料・化学・ガス", "ガラス・電子材料"),
    StockInfo("5214", "日本電気硝子", "材料・化学・ガス", "電子部品用ガラス"),
    StockInfo("5301", "東海カーボン", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("5302", "日本カーボン", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("5331", "ノリタケカンパニーリミテド", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("5332", "TOTO", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("5333", "日本ガイシ", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("5334", "日本特殊陶業", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("5384", "フジミインコーポレーテッド", "材料・化学・ガス", "CMP用研磨材"),
    StockInfo("5393", "ニチアス", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("5471", "大同特殊鋼", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("5483", "日本精線", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("6072", "エー・アンド・デイ ホロンホールディングス", "半導体製造装置・検査", "電子計測・半導体検査装置"),
    StockInfo("6146", "ディスコ", "半導体製造装置・検査", "切断・研削・研磨装置"),
    StockInfo("6240", "芝浦メカトロニクス", "半導体製造装置・検査", "製造装置・洗浄・真空"),
    StockInfo("6254", "野村マイクロ・サイエンス", "半導体製造装置・検査", "超純水製造装置"),
    StockInfo("6258", "平田機工", "半導体製造装置・検査", "前後工程装置・検査・搬送・真空"),
    StockInfo("6264", "マルマエ", "半導体製造装置・検査", "前後工程装置・検査・搬送・真空"),
    StockInfo("6266", "タツモ", "半導体製造装置・検査", "塗布・搬送装置"),
    StockInfo("6273", "SMC", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6298", "ワイエイシイホールディングス", "半導体製造装置・検査", "前後工程装置・検査・搬送・真空"),
    StockInfo("6315", "TOWA", "半導体製造装置・検査", "モールディング装置"),
    StockInfo("6323", "ローツェ", "半導体製造装置・検査", "ウェハー搬送ロボット"),
    StockInfo("6326", "クボタ", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6331", "三菱化工機", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6337", "テセック", "半導体製造装置・検査", "前後工程装置・検査・搬送・真空"),
    StockInfo("6361", "荏原製作所", "産業機械・FA・工場設備", "真空ポンプ・工場設備"),
    StockInfo("6367", "ダイキン工業", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6368", "オルガノ", "産業機械・FA・工場設備", "超純水・水処理設備"),
    StockInfo("6370", "栗田工業", "産業機械・FA・工場設備", "水処理薬品・設備"),
    StockInfo("6383", "ダイフク", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6384", "昭和真空", "半導体製造装置・検査", "真空成膜装置"),
    StockInfo("6407", "CKD", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6471", "日本精工", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6472", "NTN", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6473", "ジェイテクト", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6474", "不二越", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6490", "ピラー工業", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6501", "日立製作所", "総合電機・完成品", "総合電機・家電・画像・産業システム"),
    StockInfo("6503", "三菱電機", "総合電機・完成品", "総合電機・家電・画像・産業システム"),
    StockInfo("6504", "富士電機", "総合電機・完成品", "総合電機・家電・画像・産業システム"),
    StockInfo("6506", "安川電機", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6507", "シンフォニアテクノロジー", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6525", "KOKUSAI ELECTRIC", "半導体製造装置・検査", "成膜・熱処理装置"),
    StockInfo("6526", "ソシオネクスト", "半導体・デバイス", "カスタムSoC"),
    StockInfo("6616", "トレックス・セミコンダクター", "半導体・デバイス", "電源IC・アナログ半導体"),
    StockInfo("6627", "テラプローブ", "半導体・デバイス", "半導体テスト受託"),
    StockInfo("6640", "I-PEX", "電子部品・精密機器", "コネクタ・受動部品・光学・計測"),
    StockInfo("6645", "オムロン", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6707", "サンケン電気", "半導体・デバイス", "パワー半導体"),
    StockInfo("6723", "ルネサスエレクトロニクス", "半導体・デバイス", "車載・産業用半導体"),
    StockInfo("6728", "アルバック", "半導体製造装置・検査", "真空装置"),
    StockInfo("6752", "パナソニック ホールディングス", "総合電機・完成品", "総合電機・家電・画像・産業システム"),
    StockInfo("6753", "シャープ", "総合電機・完成品", "総合電機・家電・画像・産業システム"),
    StockInfo("6758", "ソニーグループ", "総合電機・完成品", "イメージセンサー・エレクトロニクス"),
    StockInfo("6823", "リオン", "電子部品・精密機器", "コネクタ・受動部品・光学・計測"),
    StockInfo("6834", "精工技研", "電子部品・精密機器", "コネクタ・受動部品・光学・計測"),
    StockInfo("6841", "横河電機", "電子部品・精密機器", "コネクタ・受動部品・光学・計測"),
    StockInfo("6844", "新電元工業", "半導体・デバイス", "メモリ・SoC・パワー半導体など"),
    StockInfo("6857", "アドバンテスト", "半導体製造装置・検査", "半導体テスト装置"),
    StockInfo("6859", "エスペック", "半導体製造装置・検査", "前後工程装置・検査・搬送・真空"),
    StockInfo("6861", "キーエンス", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6871", "日本マイクロニクス", "半導体製造装置・検査", "プローブカード"),
    StockInfo("6920", "レーザーテック", "半導体製造装置・検査", "マスク・ウェハー検査装置"),
    StockInfo("6941", "山一電機", "電子部品・精密機器", "コネクタ・受動部品・光学・計測"),
    StockInfo("6951", "日本電子", "電子部品・精密機器", "コネクタ・受動部品・光学・計測"),
    StockInfo("6954", "ファナック", "産業機械・FA・工場設備", "FA・搬送・流体制御・工場インフラ"),
    StockInfo("6961", "エンプラス", "電子部品・精密機器", "コネクタ・受動部品・光学・計測"),
    StockInfo("6963", "ローム", "半導体・デバイス", "パワー・アナログ半導体"),
    StockInfo("6967", "新光電気工業", "電子部品・精密機器", "半導体パッケージ"),
    StockInfo("6971", "京セラ", "電子部品・精密機器", "コネクタ・受動部品・光学・計測"),
    StockInfo("6976", "太陽誘電", "電子部品・精密機器", "コンデンサ・電子部品"),
    StockInfo("6981", "村田製作所", "電子部品・精密機器", "積層セラミックコンデンサ"),
    StockInfo("6988", "日東電工", "材料・化学・ガス", "機能性材料・テープ"),
    StockInfo("7012", "川崎重工業", "総合電機・完成品", "総合電機・家電・画像・産業システム"),
    StockInfo("7420", "佐鳥電機", "商社・流通", "半導体・電子部品の販売／技術支援"),
    StockInfo("7467", "萩原電気ホールディングス", "商社・流通", "半導体・電子部品の販売／技術支援"),
    StockInfo("7729", "東京精密", "半導体製造装置・検査", "ウェハープローバ・精密計測"),
    StockInfo("7731", "ニコン", "電子部品・精密機器", "露光・光学機器"),
    StockInfo("7735", "SCREENホールディングス", "半導体製造装置・検査", "洗浄・塗布現像装置"),
    StockInfo("7751", "キヤノン", "電子部品・精密機器", "コネクタ・受動部品・光学・計測"),
    StockInfo("7966", "リンテック", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("7995", "バルカー", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("8035", "東京エレクトロン", "半導体製造装置・検査", "前工程製造装置"),
    StockInfo("8088", "岩谷産業", "材料・化学・ガス", "ウェハー・レジスト・高純度材料・産業ガス"),
    StockInfo("8154", "加賀電子", "商社・流通", "半導体・電子部品の販売／技術支援"),
)

STOCK_BY_CODE = {stock.code: stock for stock in STOCKS}
CATEGORIES = tuple(dict.fromkeys(stock.category for stock in STOCKS))

FEATURED_CODES = (
    "8035",
    "6857",
    "6920",
    "6146",
    "7735",
    "6525",
    "6723",
    "6526",
    "285A",
    "3436",
    "4063",
    "4004",
    "4186",
    "6315",
    "6323",
    "6871",
    "6963",
    "6981",
    "2760",
    "3132",
)

PERIOD_OPTIONS = {
    "1か月": "1mo",
    "3か月": "3mo",
    "6か月": "6mo",
    "1年": "1y",
}


st.set_page_config(
    page_title="SOX連動度ダッシュボード",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      :root {
        --app-bg: #f5f7fb;
        --card-bg: rgba(255, 255, 255, .94);
        --card-border: rgba(15, 23, 42, .09);
        --muted: #64748b;
        --text: #0f172a;
        --blue: #2563eb;
      }

      .stApp {
        background:
          radial-gradient(circle at 100% 0%, rgba(37, 99, 235, .06), transparent 28rem),
          var(--app-bg);
      }

      .block-container {
        max-width: 1220px;
        padding-top: 1rem;
        padding-right: 1.2rem;
        padding-left: 1.2rem;
        padding-bottom: 4rem;
      }

      .hero {
        padding: 1.55rem 1.65rem;
        border-radius: 24px;
        color: white;
        background:
          radial-gradient(circle at 88% 8%, rgba(255,255,255,.22), transparent 27%),
          linear-gradient(135deg, #0f172a 0%, #1d4ed8 56%, #0891b2 100%);
        box-shadow: 0 20px 55px rgba(30, 64, 175, .20);
        margin-bottom: 1rem;
      }

      .hero h1 {
        font-size: clamp(1.7rem, 4vw, 2.5rem);
        line-height: 1.14;
        margin: 0 0 .55rem 0;
        letter-spacing: -.035em;
      }

      .hero p {
        margin: 0;
        max-width: 820px;
        color: rgba(255,255,255,.88);
        font-size: 1rem;
        line-height: 1.7;
      }

      .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: .35rem;
        padding: .32rem .68rem;
        border-radius: 999px;
        margin-bottom: .8rem;
        background: rgba(255,255,255,.15);
        border: 1px solid rgba(255,255,255,.24);
        font-size: .76rem;
        font-weight: 800;
        letter-spacing: .04em;
      }

      div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--card-bg);
        border-color: var(--card-border) !important;
        border-radius: 20px;
        box-shadow: 0 8px 28px rgba(15, 23, 42, .05);
      }

      div[data-testid="stMetric"] {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        padding: .95rem 1rem;
        border-radius: 17px;
        box-shadow: 0 5px 18px rgba(15, 23, 42, .045);
      }

      div[data-testid="stMetricLabel"] { color: var(--muted); }

      div[data-testid="stButton"] button,
      div[data-testid="stDownloadButton"] button,
      div[data-testid="stLinkButton"] a {
        min-height: 48px;
        border-radius: 13px;
        font-size: .98rem;
        font-weight: 750;
      }

      div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
      div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
      div[data-testid="stTextInput"] input {
        min-height: 48px;
        border-radius: 13px;
      }

      div[data-testid="stDataFrame"] {
        border-radius: 14px;
        overflow: hidden;
      }

      .section-kicker {
        color: var(--blue);
        font-size: .76rem;
        font-weight: 850;
        letter-spacing: .09em;
        text-transform: uppercase;
        margin-bottom: .18rem;
      }

      .selection-summary {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: .5rem;
        padding: .8rem .95rem;
        margin: .65rem 0 .9rem 0;
        border-radius: 15px;
        background: #eff6ff;
        border: 1px solid #dbeafe;
        color: #1e3a8a;
        font-size: .9rem;
        line-height: 1.5;
      }

      .selection-pill {
        display: inline-flex;
        padding: .24rem .55rem;
        border-radius: 999px;
        background: white;
        border: 1px solid #bfdbfe;
        font-weight: 750;
      }

      .company-card {
        padding: 1rem 1.05rem;
        border-radius: 17px;
        background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid var(--card-border);
        margin-bottom: .85rem;
      }

      .company-card h3 {
        margin: .3rem 0 .3rem 0;
        font-size: 1.25rem;
        color: var(--text);
      }

      .company-code {
        display: inline-flex;
        padding: .22rem .55rem;
        border-radius: 999px;
        background: #dbeafe;
        color: #1d4ed8;
        font-size: .78rem;
        font-weight: 850;
      }

      .company-meta {
        color: var(--muted);
        font-size: .9rem;
        line-height: 1.55;
      }

      .hint {
        color: var(--muted);
        font-size: .87rem;
        line-height: 1.55;
      }

      @media (max-width: 640px) {
        .block-container {
          padding-top: .55rem;
          padding-right: .7rem;
          padding-left: .7rem;
        }

        .hero {
          border-radius: 18px;
          padding: 1.2rem 1rem;
        }

        .hero p { font-size: .91rem; }
        div[data-testid="stMetricValue"] { font-size: 1.38rem; }
        .company-card h3 { font-size: 1.1rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def download_market_data(tickers: tuple[str, ...], period: str) -> pd.DataFrame:
    """指定した銘柄の日足データを一括取得する。"""
    try:
        data = yf.download(
            list(tickers),
            period=period,
            interval="1d",
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=True,
            ignore_tz=True,
            timeout=45,
            group_by="ticker",
            multi_level_index=True,
        )
    except Exception as exc:
        raise AppError(
            "株価データを取得できませんでした。通信状況を確認し、少し時間を置いて再実行してください。"
        ) from exc

    if data is None or data.empty:
        raise AppError(
            "株価データが空でした。Yahoo Finance側の一時的な制限の可能性があります。"
        )
    return data


def extract_close(data: pd.DataFrame, ticker: str) -> pd.Series:
    """yfinanceのDataFrameから指定銘柄の終値を取り出す。"""
    if data is None or data.empty:
        raise AppError(f"{ticker} のデータがありません。")

    close: pd.Series | pd.DataFrame

    if isinstance(data.columns, pd.MultiIndex):
        level0 = data.columns.get_level_values(0)
        level1 = data.columns.get_level_values(1)

        if ticker in level0 and "Close" in level1:
            close = data[ticker]["Close"]
        elif "Close" in level0 and ticker in level1:
            close = data["Close"][ticker]
        else:
            raise AppError(f"{ticker} の終値列が見つかりませんでした。")
    else:
        if "Close" not in data.columns:
            raise AppError(f"{ticker} の終値列が見つかりませんでした。")
        close = data["Close"]

    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    close = pd.to_numeric(close, errors="coerce").dropna()
    if close.empty:
        raise AppError(f"{ticker} の有効な終値がありません。")

    index = pd.DatetimeIndex(close.index)
    if index.tz is not None:
        index = index.tz_localize(None)

    close.index = index.normalize()
    close = close[~close.index.duplicated(keep="last")].sort_index()
    close.name = ticker
    return close


def calculate_lagged_correlation(
    japanese_close: pd.Series,
    sox_close: pd.Series,
) -> tuple[float, pd.DataFrame]:
    """
    各日本株取引日に対し、その前日以前で最も新しいSOX取引日のリターンを対応させる。
    日米の土日・祝日の違いはmerge_asofで吸収する。
    """
    japanese_return = (
        japanese_close.pct_change(fill_method=None).dropna().rename("日本株リターン")
    )
    sox_return = sox_close.pct_change(fill_method=None).dropna().rename("前日SOXリターン")

    if japanese_return.empty or sox_return.empty:
        raise AppError("リターン計算に必要な価格データが不足しています。")

    japan = japanese_return.rename_axis("日本株取引日").reset_index()
    japan["SOX参照上限日"] = japan["日本株取引日"] - pd.Timedelta(days=1)

    sox = sox_return.rename_axis("SOX取引日").reset_index()

    aligned = pd.merge_asof(
        japan.sort_values("SOX参照上限日"),
        sox.sort_values("SOX取引日"),
        left_on="SOX参照上限日",
        right_on="SOX取引日",
        direction="backward",
        allow_exact_matches=True,
    )

    aligned = (
        aligned.dropna(subset=["日本株リターン", "前日SOXリターン"])
        .set_index("日本株取引日")
        .sort_index()
    )

    if len(aligned) < MIN_OBSERVATIONS:
        raise AppError(
            f"有効な比較日が{len(aligned)}日しかありません。最低{MIN_OBSERVATIONS}日必要です。"
        )

    correlation = aligned["日本株リターン"].corr(
        aligned["前日SOXリターン"], method="pearson"
    )

    if pd.isna(correlation):
        raise AppError("値動きが一定、またはデータ不足のため相関係数を計算できません。")

    aligned[f"{ROLLING_WINDOW}日ローリング相関"] = (
        aligned["日本株リターン"]
        .rolling(window=ROLLING_WINDOW, min_periods=ROLLING_MIN_PERIODS)
        .corr(aligned["前日SOXリターン"])
    )

    return float(correlation), aligned


def describe_correlation(value: float) -> str:
    if value >= 0.70:
        return "強い正の相関"
    if value >= 0.40:
        return "中程度の正の相関"
    if value >= 0.20:
        return "弱い正の相関"
    if value > -0.20:
        return "相関はほぼなし"
    if value > -0.40:
        return "弱い負の相関"
    if value > -0.70:
        return "中程度の負の相関"
    return "強い負の相関"


def chunked(values: list[StockInfo], size: int) -> Iterable[list[StockInfo]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def analyze_stocks(
    selected_stocks: Iterable[StockInfo],
    period: str,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> tuple[list[dict[str, object]], dict[str, pd.DataFrame], list[str]]:
    selected = list(selected_stocks)
    batches = list(chunked(selected, BATCH_SIZE))
    total_steps = len(batches) + 1

    sox_data = download_market_data((SOX_TICKER,), period)
    try:
        sox_close = extract_close(sox_data, SOX_TICKER)
    except AppError as exc:
        raise AppError("SOX指数のデータを取得できませんでした。") from exc

    if progress_callback:
        progress_callback(1, total_steps, "SOX指数の取得が完了しました")

    results: list[dict[str, object]] = []
    details: dict[str, pd.DataFrame] = {}
    failures: list[str] = []

    for batch_number, stock_batch in enumerate(batches, start=1):
        tickers = tuple(stock.ticker for stock in stock_batch)

        try:
            market_data = download_market_data(tickers, period)
        except AppError as exc:
            failures.extend(
                f"{stock.name}（{stock.code}）: 一括取得に失敗しました"
                for stock in stock_batch
            )
            if progress_callback:
                progress_callback(
                    batch_number + 1,
                    total_steps,
                    f"{batch_number}/{len(batches)}グループを処理しました",
                )
            continue

        for stock in stock_batch:
            try:
                japanese_close = extract_close(market_data, stock.ticker)
                correlation, aligned = calculate_lagged_correlation(
                    japanese_close, sox_close
                )
                latest_return = float(aligned["日本株リターン"].iloc[-1])
                latest_rolling = aligned[f"{ROLLING_WINDOW}日ローリング相関"].iloc[-1]

                results.append(
                    {
                        "会社名": stock.name,
                        "コード": stock.code,
                        "分野": stock.category,
                        "関連領域": stock.focus,
                        "相関係数": correlation,
                        "判定": describe_correlation(correlation),
                        "最新騰落率": latest_return,
                        "最新20日相関": (
                            float(latest_rolling) if pd.notna(latest_rolling) else None
                        ),
                        "観測日数": len(aligned),
                        "開始日": aligned.index.min(),
                        "終了日": aligned.index.max(),
                    }
                )
                details[stock.code] = aligned
            except AppError as exc:
                failures.append(f"{stock.name}（{stock.code}）: {exc}")

        if progress_callback:
            progress_callback(
                batch_number + 1,
                total_steps,
                f"{batch_number}/{len(batches)}グループを処理しました",
            )

    if not results:
        raise AppError("選択した銘柄の分析結果を作成できませんでした。")

    results.sort(key=lambda item: float(item["相関係数"]), reverse=True)
    return results, details, failures


def build_summary_dataframe(results: list[dict[str, object]]) -> pd.DataFrame:
    rows = []
    for rank, result in enumerate(results, start=1):
        rows.append(
            {
                "順位": rank,
                "会社名": result["会社名"],
                "コード": result["コード"],
                "分野": result["分野"],
                "関連領域": result["関連領域"],
                "期間相関": result["相関係数"],
                "最新20日相関": result["最新20日相関"],
                "判定": result["判定"],
                "最新騰落率": float(result["最新騰落率"]) * 100,
                "観測日数": result["観測日数"],
            }
        )
    return pd.DataFrame(rows)


def render_summary_table(summary: pd.DataFrame) -> None:
    st.dataframe(
        summary,
        width="stretch",
        hide_index=True,
        row_height=42,
        column_config={
            "順位": st.column_config.NumberColumn("#", width="small", format="%d"),
            "会社名": st.column_config.TextColumn("会社名", width="medium"),
            "コード": st.column_config.TextColumn("コード", width="small"),
            "分野": st.column_config.TextColumn("分野", width="medium"),
            "関連領域": st.column_config.TextColumn("関連領域", width="large"),
            "期間相関": st.column_config.NumberColumn(
                "期間相関",
                help="選択期間全体のピアソン相関係数",
                format="%.3f",
            ),
            "最新20日相関": st.column_config.NumberColumn(
                "最新20日相関",
                help="直近20観測日のローリング相関",
                format="%.3f",
            ),
            "判定": st.column_config.TextColumn("判定", width="medium"),
            "最新騰落率": st.column_config.NumberColumn(
                "最新騰落率", format="%.2f%%"
            ),
            "観測日数": st.column_config.NumberColumn("日数", format="%d日"),
        },
    )


def render_detail_table(aligned: pd.DataFrame) -> None:
    detail = aligned.tail(DETAIL_ROWS).copy()
    detail.index.name = "日本株取引日"
    detail["日本株騰落率"] = detail["日本株リターン"] * 100
    detail["前日SOX騰落率"] = detail["前日SOXリターン"] * 100
    detail["対応SOX日"] = pd.to_datetime(detail["SOX取引日"]).dt.strftime("%Y-%m-%d")
    rolling_column = f"{ROLLING_WINDOW}日ローリング相関"

    display = detail[
        ["日本株騰落率", "前日SOX騰落率", "対応SOX日", rolling_column]
    ]

    st.dataframe(
        display,
        width="stretch",
        hide_index=False,
        row_height=39,
        column_config={
            "日本株騰落率": st.column_config.NumberColumn(
                "日本株", format="%.2f%%"
            ),
            "前日SOX騰落率": st.column_config.NumberColumn(
                "前日SOX", format="%.2f%%"
            ),
            "対応SOX日": st.column_config.TextColumn("対応SOX日"),
            rolling_column: st.column_config.NumberColumn(
                "20日相関",
                help="この日までの最大20観測日を使ったローリング相関（最低5観測日）",
                format="%.3f",
            ),
        },
    )


def render_stock_detail(
    result: dict[str, object],
    aligned: pd.DataFrame,
) -> None:
    code = str(result["コード"])
    stock = STOCK_BY_CODE[code]
    safe_name = html.escape(stock.name)
    safe_category = html.escape(stock.category)
    safe_focus = html.escape(stock.focus)

    st.markdown(
        f"""
        <div class="company-card">
          <span class="company-code">{code}</span>
          <h3>{safe_name}</h3>
          <div class="company-meta">{safe_category}　｜　{safe_focus}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_row_1 = st.columns(2)
    metric_row_1[0].metric("期間相関", f"{float(result['相関係数']):.3f}")
    latest_rolling = result["最新20日相関"]
    metric_row_1[1].metric(
        "最新20日相関",
        f"{float(latest_rolling):.3f}" if latest_rolling is not None else "—",
    )

    metric_row_2 = st.columns(2)
    metric_row_2[0].metric(
        "最新騰落率", f"{float(result['最新騰落率']) * 100:+.2f}%"
    )
    metric_row_2[1].metric("観測日数", f"{int(result['観測日数'])}日")

    st.caption(
        f"比較期間: {pd.Timestamp(result['開始日']):%Y-%m-%d}〜"
        f"{pd.Timestamp(result['終了日']):%Y-%m-%d}　｜　{result['判定']}"
    )

    button_cols = st.columns(2)
    button_cols[0].link_button(
        "Yahoo!ファイナンスで確認",
        f"https://finance.yahoo.co.jp/quote/{stock.ticker}",
        width="stretch",
    )

    detail_csv = aligned.tail(DETAIL_ROWS).copy()
    detail_csv.index.name = "日本株取引日"
    button_cols[1].download_button(
        "20日データをCSV保存",
        data=detail_csv.to_csv(index=True).encode("utf-8-sig"),
        file_name=f"{code}_sox_correlation_detail.csv",
        mime="text/csv",
        width="stretch",
    )

    return_chart = aligned.tail(DETAIL_ROWS)[
        ["日本株リターン", "前日SOXリターン"]
    ].copy()
    return_chart.columns = [stock.name, "前日SOX"]
    return_chart *= 100

    st.markdown("#### 直近20日の騰落率")
    st.line_chart(return_chart, height=260)

    rolling_column = f"{ROLLING_WINDOW}日ローリング相関"
    rolling_chart = aligned.tail(max(DETAIL_ROWS * 3, 60))[[rolling_column]].copy()
    rolling_chart.columns = ["20日ローリング相関"]

    st.markdown("#### 相関の推移")
    st.line_chart(rolling_chart, height=230)

    st.markdown("#### 直近20日分の対応データ")
    st.caption(
        "「20日相関」は各日を終点として最大20観測日から計算したローリング相関です。"
    )
    render_detail_table(aligned)


def render_universe_table() -> None:
    st.markdown('<div class="section-kicker">Stock universe</div>', unsafe_allow_html=True)
    st.subheader(f"登録銘柄一覧（{len(STOCKS)}銘柄）")

    search_cols = st.columns([1.5, 1])
    keyword = search_cols[0].text_input(
        "会社名・コード・関連領域で検索",
        placeholder="例: 東京エレクトロン / 8035 / フォトレジスト",
        key="universe_keyword",
    )
    category_filter = search_cols[1].multiselect(
        "分野で絞り込み",
        options=list(CATEGORIES),
        default=[],
        key="universe_categories",
        placeholder="すべての分野",
    )

    universe = pd.DataFrame(
        [
            {
                "コード": stock.code,
                "会社名": stock.name,
                "分野": stock.category,
                "関連領域": stock.focus,
            }
            for stock in STOCKS
        ]
    )

    if category_filter:
        universe = universe[universe["分野"].isin(category_filter)]

    normalized_keyword = keyword.strip().lower()
    if normalized_keyword:
        search_text = (
            universe["コード"].astype(str)
            + " "
            + universe["会社名"].astype(str)
            + " "
            + universe["分野"].astype(str)
            + " "
            + universe["関連領域"].astype(str)
        ).str.lower()
        universe = universe[search_text.str.contains(normalized_keyword, regex=False)]

    st.caption(f"{len(universe)}銘柄を表示中")
    st.dataframe(
        universe,
        width="stretch",
        hide_index=True,
        row_height=40,
        column_config={
            "コード": st.column_config.TextColumn("コード", width="small"),
            "会社名": st.column_config.TextColumn("会社名", width="medium"),
            "分野": st.column_config.TextColumn("分野", width="medium"),
            "関連領域": st.column_config.TextColumn("関連領域", width="large"),
        },
    )

    st.download_button(
        "登録銘柄一覧をCSV保存",
        data=universe.to_csv(index=False).encode("utf-8-sig"),
        file_name="semiconductor_stock_universe.csv",
        mime="text/csv",
        width="stretch",
    )


def selected_codes_from_ui(selection_mode: str) -> list[str]:
    if selection_mode == "注目20銘柄":
        st.caption("代表的な装置・デバイス・材料・商社をバランスよく選んだ20銘柄です。")
        return list(FEATURED_CODES)

    if selection_mode == "全銘柄":
        st.warning(
            f"{len(STOCKS)}銘柄を複数回に分けて取得します。Yahoo Financeの混雑状況により時間がかかる場合があります。"
        )
        return [stock.code for stock in STOCKS]

    if selection_mode == "分野から選ぶ":
        selected_categories = st.multiselect(
            "分析する分野",
            options=list(CATEGORIES),
            default=["半導体製造装置・検査", "半導体・デバイス"],
            key="analysis_categories",
        )
        return [
            stock.code for stock in STOCKS if stock.category in selected_categories
        ]

    return st.multiselect(
        "分析する銘柄",
        options=[stock.code for stock in STOCKS],
        default=list(FEATURED_CODES),
        format_func=lambda code: STOCK_BY_CODE[code].label,
        placeholder="会社名または証券コードで検索",
        key="analysis_codes",
    )


def render_results(payload: dict[str, object], current_signature: tuple[object, ...]) -> None:
    results = payload["results"]
    details = payload["details"]
    failures = payload["failures"]
    period_label = str(payload["period_label"])
    signature = payload["signature"]

    if signature != current_signature:
        st.info("分析条件が変更されています。現在は前回の分析結果を表示しています。更新するには再度分析してください。")

    st.markdown('<div class="section-kicker">Overview</div>', unsafe_allow_html=True)
    st.subheader("分析サマリー")

    correlations = [float(result["相関係数"]) for result in results]
    best = results[0]
    strong_count = sum(value >= 0.40 for value in correlations)
    start_date = min(pd.Timestamp(result["開始日"]) for result in results)
    end_date = max(pd.Timestamp(result["終了日"]) for result in results)

    metrics_1 = st.columns(2)
    metrics_1[0].metric("分析できた銘柄", f"{len(results)}社")
    metrics_1[1].metric(
        "最高相関",
        f"{float(best['相関係数']):.3f}",
        delta=str(best["会社名"]),
        delta_color="off",
    )

    metrics_2 = st.columns(2)
    metrics_2[0].metric("平均相関", f"{sum(correlations) / len(correlations):.3f}")
    metrics_2[1].metric("相関0.40以上", f"{strong_count}社")

    st.caption(
        f"分析期間: {period_label}　｜　比較日: {start_date:%Y-%m-%d}〜{end_date:%Y-%m-%d}　｜　"
        f"更新: {payload['generated_at']}　｜　前日のSOX → 当日の日本株"
    )

    result_tabs = st.tabs(["ランキング", "銘柄詳細", "取得状況"])

    with result_tabs[0]:
        summary = build_summary_dataframe(results)

        filter_cols = st.columns([1.4, 1])
        keyword = filter_cols[0].text_input(
            "結果を検索",
            placeholder="会社名・コード・分野・関連領域",
            key="result_keyword",
        )
        categories = filter_cols[1].multiselect(
            "結果の分野",
            options=list(CATEGORIES),
            default=[],
            key="result_categories",
            placeholder="すべて",
        )

        filtered = summary.copy()
        if categories:
            filtered = filtered[filtered["分野"].isin(categories)]

        normalized_keyword = keyword.strip().lower()
        if normalized_keyword:
            searchable = (
                filtered["会社名"].astype(str)
                + " "
                + filtered["コード"].astype(str)
                + " "
                + filtered["分野"].astype(str)
                + " "
                + filtered["関連領域"].astype(str)
            ).str.lower()
            filtered = filtered[searchable.str.contains(normalized_keyword, regex=False)]

        st.caption(f"{len(filtered)}銘柄を表示中")
        render_summary_table(filtered)

        chart_source = filtered.head(20).set_index("会社名")[["期間相関"]]
        if not chart_source.empty:
            st.markdown("#### 相関上位20銘柄")
            st.bar_chart(chart_source, height=360)

        st.download_button(
            "ランキングをCSV保存",
            data=summary.to_csv(index=False).encode("utf-8-sig"),
            file_name="sox_correlation_ranking.csv",
            mime="text/csv",
            width="stretch",
        )

    with result_tabs[1]:
        result_by_code = {str(result["コード"]): result for result in results}
        detail_codes = list(result_by_code.keys())
        selected_detail_code = st.selectbox(
            "詳細を表示する銘柄",
            options=detail_codes,
            format_func=lambda code: STOCK_BY_CODE[code].label,
            key="detail_code",
        )
        render_stock_detail(
            result_by_code[selected_detail_code],
            details[selected_detail_code],
        )

    with result_tabs[2]:
        success_rate = len(results) / (len(results) + len(failures)) * 100
        st.metric("取得成功率", f"{success_rate:.1f}%")

        if failures:
            st.warning(
                "一部の銘柄は価格データ不足、上場期間の短さ、Yahoo Finance側の応答などにより分析できませんでした。"
            )
            failure_df = pd.DataFrame({"取得できなかった銘柄": failures})
            st.dataframe(failure_df, width="stretch", hide_index=True)
        else:
            st.success("選択したすべての銘柄を分析できました。")


if "analysis_payload" not in st.session_state:
    st.session_state.analysis_payload = None


st.markdown(
    f"""
    <div class="hero">
      <div class="hero-badge">JAPAN SEMICONDUCTOR × PHILADELPHIA SOX</div>
      <h1>SOX連動度ダッシュボード</h1>
      <p>
        前日のSOX指数リターンと当日の日本株リターンを比較し、
        {len(STOCKS)}銘柄から複数社をまとめてランキング。
        期間相関と20日ローリング相関をスマートフォンでも見やすく確認できます。
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

main_tab, universe_tab = st.tabs(
    ["📊 相関分析", f"🏢 登録銘柄一覧（{len(STOCKS)}）"]
)

with main_tab:
    with st.container(border=True):
        st.markdown(
            '<div class="section-kicker">Analysis settings</div>',
            unsafe_allow_html=True,
        )
        st.subheader("分析条件")

        control_cols = st.columns(2)
        period_label = control_cols[0].segmented_control(
            "分析期間",
            options=list(PERIOD_OPTIONS.keys()),
            default="3か月",
            selection_mode="single",
            width="stretch",
            key="period_label",
        )
        selection_mode = control_cols[1].selectbox(
            "銘柄の選び方",
            options=["注目20銘柄", "分野から選ぶ", "個別に選ぶ", "全銘柄"],
            index=0,
            key="selection_mode",
        )

        selected_codes = selected_codes_from_ui(str(selection_mode))
        selected_codes = list(dict.fromkeys(selected_codes))

        category_counts = pd.Series(
            [STOCK_BY_CODE[code].category for code in selected_codes],
            dtype="object",
        ).value_counts()

        category_text = " / ".join(
            f"{category} {count}社" for category, count in category_counts.items()
        )

        st.markdown(
            f"""
            <div class="selection-summary">
              <span class="selection-pill">{len(selected_codes)}銘柄を選択</span>
              <span>{html.escape(category_text) if category_text else "銘柄を選択してください"}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        action_cols = st.columns([3, 1])
        analyze_button = action_cols[0].button(
            "選択銘柄をまとめて分析",
            type="primary",
            icon=":material/analytics:",
            width="stretch",
        )
        refresh_button = action_cols[1].button(
            "キャッシュ更新",
            icon=":material/refresh:",
            width="stretch",
            help="最新データを取り直したいときに使用します。",
        )

        if refresh_button:
            st.cache_data.clear()
            st.session_state.analysis_payload = None
            st.toast("キャッシュを削除しました。再度分析してください。")
            st.rerun()

    signature = (str(period_label), tuple(selected_codes))

    if analyze_button:
        if not selected_codes:
            st.warning("分析する銘柄を1社以上選択してください。")
        else:
            try:
                selected_stocks = [STOCK_BY_CODE[code] for code in selected_codes]
                period_code = PERIOD_OPTIONS[str(period_label)]
                progress_bar = st.progress(0)
                progress_text = st.empty()

                def update_progress(done: int, total: int, message: str) -> None:
                    progress_bar.progress(min(done / total, 1.0))
                    progress_text.caption(message)

                results, details, failures = analyze_stocks(
                    selected_stocks,
                    period_code,
                    progress_callback=update_progress,
                )

                progress_bar.progress(1.0)
                progress_text.success("分析が完了しました")

                generated_at = datetime.now(ZoneInfo("Asia/Tokyo")).strftime(
                    "%Y-%m-%d %H:%M"
                )
                st.session_state.analysis_payload = {
                    "results": results,
                    "details": details,
                    "failures": failures,
                    "period_label": period_label,
                    "selected_codes": selected_codes,
                    "signature": signature,
                    "generated_at": generated_at,
                }
                st.toast(f"{len(results)}銘柄の分析が完了しました。")
            except AppError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error("予期しないエラーが発生しました。時間を置いて再度お試しください。")
                with st.expander("技術情報"):
                    st.code(f"{type(exc).__name__}: {exc}")

    payload = st.session_state.analysis_payload
    if payload:
        st.divider()
        render_results(payload, signature)
    else:
        st.markdown('<div class="section-kicker">How it works</div>', unsafe_allow_html=True)
        st.subheader("使い方")
        guide_1 = st.columns(2)
        guide_1[0].info("**1. 期間を選択**\n\n1か月・3か月・6か月・1年から選べます。")
        guide_1[1].info("**2. 銘柄を選択**\n\n注目銘柄、分野、個別、全銘柄から選べます。")
        guide_2 = st.columns(2)
        guide_2[0].info("**3. 一括分析**\n\n相関ランキングを検索・絞り込みできます。")
        guide_2[1].info("**4. 詳細確認**\n\n銘柄を切り替えて20日データと相関推移を確認できます。")

with universe_tab:
    render_universe_table()

st.caption(
    "相関は因果関係や将来の値動きを保証しません。データはYahoo Finance経由で取得するため、"
    "遅延・欠損・仕様変更が起こる場合があります。"
)

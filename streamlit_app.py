from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import streamlit as st
import yfinance as yf

SOX_TICKER = "^SOX"
MIN_OBSERVATIONS = 8
ROLLING_WINDOW = 20
ROLLING_MIN_PERIODS = 5
DETAIL_ROWS = 20
CACHE_TTL_SECONDS = 60 * 60


class AppError(Exception):
    """画面に安全に表示できるアプリ用エラー。"""


@dataclass(frozen=True)
class StockInfo:
    code: str
    name: str
    category: str
    description: str

    @property
    def ticker(self) -> str:
        return f"{self.code}.T"

    @property
    def label(self) -> str:
        return f"{self.name}（{self.code}）｜{self.category}"


# 「半導体関連」の厳密な指数構成銘柄ではなく、日常比較用の主要銘柄リスト。
STOCKS: tuple[StockInfo, ...] = (
    StockInfo("8035", "東京エレクトロン", "製造装置", "前工程を中心とする半導体製造装置"),
    StockInfo("6857", "アドバンテスト", "検査・計測", "半導体テスト装置"),
    StockInfo("6920", "レーザーテック", "検査・計測", "マスク・ウェハー検査装置"),
    StockInfo("6146", "ディスコ", "製造装置", "切断・研削・研磨装置"),
    StockInfo("7735", "SCREENホールディングス", "製造装置", "洗浄・塗布現像装置"),
    StockInfo("6315", "TOWA", "製造装置", "半導体モールディング装置"),
    StockInfo("6266", "タツモ", "製造装置", "塗布・搬送などの製造装置"),
    StockInfo("6871", "日本マイクロニクス", "検査・計測", "プローブカード・検査機器"),
    StockInfo("6525", "KOKUSAI ELECTRIC", "製造装置", "成膜・熱処理装置"),
    StockInfo("7729", "東京精密", "検査・計測", "ウェハープロービング・精密計測"),
    StockInfo("6323", "ローツェ", "搬送・周辺", "ウェハー搬送ロボット"),
    StockInfo("6723", "ルネサスエレクトロニクス", "半導体デバイス", "車載・産業向けMCU／SoC"),
    StockInfo("6526", "ソシオネクスト", "半導体デバイス", "カスタムSoC"),
    StockInfo("6963", "ローム", "半導体デバイス", "パワー・アナログ半導体"),
    StockInfo("3436", "SUMCO", "材料・ウェハー", "シリコンウェハー"),
    StockInfo("4063", "信越化学工業", "材料・ウェハー", "シリコンウェハー・半導体材料"),
    StockInfo("4186", "東京応化工業", "材料・ウェハー", "フォトレジストなどの材料"),
)

STOCK_BY_CODE = {stock.code: stock for stock in STOCKS}
MAJOR_CODES = ("8035", "6857", "6920", "6146", "7735", "6723", "6526", "3436")

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
        --app-bg: #f6f8fc;
        --card-border: rgba(15, 23, 42, 0.09);
        --muted: #64748b;
      }

      .stApp { background: var(--app-bg); }

      .block-container {
        max-width: 1180px;
        padding-top: 1.1rem;
        padding-right: 1.2rem;
        padding-left: 1.2rem;
        padding-bottom: 4rem;
      }

      .hero {
        padding: 1.55rem 1.6rem;
        border-radius: 22px;
        color: white;
        background:
          radial-gradient(circle at 88% 12%, rgba(255,255,255,.22), transparent 28%),
          linear-gradient(135deg, #0f172a 0%, #1d4ed8 58%, #06b6d4 100%);
        box-shadow: 0 18px 50px rgba(30, 64, 175, .20);
        margin-bottom: 1.2rem;
      }

      .hero h1 {
        font-size: clamp(1.65rem, 4vw, 2.45rem);
        line-height: 1.15;
        margin: 0 0 .55rem 0;
        letter-spacing: -.03em;
      }

      .hero p {
        margin: 0;
        max-width: 760px;
        color: rgba(255,255,255,.88);
        font-size: 1rem;
        line-height: 1.7;
      }

      .hero-badge {
        display: inline-flex;
        padding: .3rem .65rem;
        border-radius: 999px;
        margin-bottom: .8rem;
        background: rgba(255,255,255,.16);
        border: 1px solid rgba(255,255,255,.23);
        font-size: .78rem;
        font-weight: 700;
      }

      div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(255,255,255,.88);
        border-color: var(--card-border) !important;
        border-radius: 18px;
        box-shadow: 0 8px 30px rgba(15, 23, 42, .055);
      }

      div[data-testid="stMetric"] {
        background: rgba(255,255,255,.9);
        border: 1px solid var(--card-border);
        padding: .95rem 1rem;
        border-radius: 16px;
        box-shadow: 0 5px 18px rgba(15, 23, 42, .045);
      }

      div[data-testid="stMetricLabel"] { color: var(--muted); }

      div[data-testid="stButton"] button,
      div[data-testid="stFormSubmitButton"] button {
        min-height: 50px;
        border-radius: 13px;
        font-size: 1rem;
        font-weight: 750;
      }

      div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
        min-height: 50px;
        border-radius: 13px;
      }

      div[data-testid="stDataFrame"] {
        border-radius: 14px;
        overflow: hidden;
      }

      .section-kicker {
        color: #2563eb;
        font-size: .78rem;
        font-weight: 800;
        letter-spacing: .08em;
        text-transform: uppercase;
        margin-bottom: .2rem;
      }

      .stock-note {
        color: var(--muted);
        font-size: .88rem;
        line-height: 1.55;
      }

      @media (max-width: 640px) {
        .block-container {
          padding-top: .65rem;
          padding-right: .75rem;
          padding-left: .75rem;
        }
        .hero {
          border-radius: 18px;
          padding: 1.25rem 1.05rem;
        }
        .hero p { font-size: .92rem; }
        div[data-testid="stMetricValue"] { font-size: 1.45rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def download_market_data(tickers: tuple[str, ...], period: str) -> pd.DataFrame:
    """複数銘柄とSOXを一括取得する。"""
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
            timeout=30,
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
    """yfinanceの複数銘柄DataFrameから指定銘柄の終値を取り出す。"""
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
    日米の土日・祝日の違いもmerge_asofで吸収する。
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


def analyze_stocks(
    selected_stocks: Iterable[StockInfo],
    period: str,
) -> tuple[list[dict[str, object]], dict[str, pd.DataFrame], list[str]]:
    selected = list(selected_stocks)
    tickers = tuple(dict.fromkeys([SOX_TICKER, *[stock.ticker for stock in selected]]))
    market_data = download_market_data(tickers, period)

    try:
        sox_close = extract_close(market_data, SOX_TICKER)
    except AppError as exc:
        raise AppError("SOX指数のデータを取得できませんでした。") from exc

    results: list[dict[str, object]] = []
    details: dict[str, pd.DataFrame] = {}
    failures: list[str] = []

    for stock in selected:
        try:
            japanese_close = extract_close(market_data, stock.ticker)
            correlation, aligned = calculate_lagged_correlation(japanese_close, sox_close)
            latest_return = float(aligned["日本株リターン"].iloc[-1])
            latest_rolling = aligned[f"{ROLLING_WINDOW}日ローリング相関"].iloc[-1]

            results.append(
                {
                    "会社名": stock.name,
                    "コード": stock.code,
                    "分野": stock.category,
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

    if not results:
        raise AppError("選択した銘柄の分析結果を作成できませんでした。")

    results.sort(key=lambda item: float(item["相関係数"]), reverse=True)
    return results, details, failures


def render_summary_table(results: list[dict[str, object]]) -> None:
    rows = []
    for rank, result in enumerate(results, start=1):
        rows.append(
            {
                "順位": rank,
                "会社名": result["会社名"],
                "コード": result["コード"],
                "分野": result["分野"],
                "期間相関": result["相関係数"],
                "最新20日相関": result["最新20日相関"],
                "判定": result["判定"],
                "最新騰落率": float(result["最新騰落率"]) * 100,
                "観測日数": result["観測日数"],
            }
        )

    summary = pd.DataFrame(rows)
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
            "期間相関": st.column_config.NumberColumn(
                "期間相関", help="選択期間全体のピアソン相関係数", format="%.3f"
            ),
            "最新20日相関": st.column_config.NumberColumn(
                "最新20日相関", help="直近20観測日のローリング相関", format="%.3f"
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


def render_stock_details(
    results: list[dict[str, object]],
    details: dict[str, pd.DataFrame],
) -> None:
    st.markdown('<div class="section-kicker">Company details</div>', unsafe_allow_html=True)
    st.subheader("銘柄別の詳細")
    st.caption(
        "「20日相関」は、各日を終点として最大20観測日から計算したローリング相関です。"
        "1日だけでは相関を計算できないため、日ごとの変化はこの方法で表示します。"
    )

    for result in results:
        code = str(result["コード"])
        stock = STOCK_BY_CODE[code]
        correlation = float(result["相関係数"])

        with st.expander(
            f"{stock.name}（{code}）｜相関 {correlation:.3f}｜{result['判定']}",
            expanded=False,
        ):
            st.markdown(
                f'<div class="stock-note"><b>{stock.category}</b>　{stock.description}</div>',
                unsafe_allow_html=True,
            )

            metric_cols = st.columns(3)
            metric_cols[0].metric("期間相関", f"{correlation:.3f}")
            latest_rolling = result["最新20日相関"]
            metric_cols[1].metric(
                "最新20日相関",
                f"{float(latest_rolling):.3f}" if latest_rolling is not None else "—",
            )
            metric_cols[2].metric(
                "最新騰落率", f"{float(result['最新騰落率']) * 100:+.2f}%"
            )

            aligned = details[code]
            chart = aligned.tail(DETAIL_ROWS)[
                ["日本株リターン", "前日SOXリターン"]
            ].copy()
            chart.columns = [f"{stock.name}", "前日SOX"]
            chart *= 100
            st.line_chart(chart, height=230)

            st.markdown(f"**直近{DETAIL_ROWS}日分の対応データ**")
            render_detail_table(aligned)


st.markdown(
    """
    <div class="hero">
      <div class="hero-badge">JAPAN SEMICONDUCTOR × PHILADELPHIA SOX</div>
      <h1>SOX連動度ダッシュボード</h1>
      <p>
        前日のSOX指数リターンと、当日の日本の半導体関連株リターンを比較。
        複数銘柄をまとめてランキングし、期間相関と20日ローリング相関を確認できます。
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.container(border=True):
    st.markdown('<div class="section-kicker">Analysis settings</div>', unsafe_allow_html=True)
    st.subheader("分析条件")

    period_label = st.segmented_control(
        "分析期間",
        options=list(PERIOD_OPTIONS.keys()),
        default="3か月",
        selection_mode="single",
        width="stretch",
    )

    selection_mode = st.segmented_control(
        "銘柄の選び方",
        options=["主要8銘柄", f"全{len(STOCKS)}銘柄", "選んで比較"],
        default=f"全{len(STOCKS)}銘柄",
        selection_mode="single",
        width="stretch",
    )

    if selection_mode == "主要8銘柄":
        selected_codes = list(MAJOR_CODES)
        st.caption("流動性と知名度を考慮した主要8銘柄を分析します。")
    elif selection_mode == f"全{len(STOCKS)}銘柄":
        selected_codes = [stock.code for stock in STOCKS]
        st.caption(f"アプリに登録した主要半導体関連{len(STOCKS)}銘柄を一括分析します。")
    else:
        selected_codes = st.multiselect(
            "分析する銘柄",
            options=[stock.code for stock in STOCKS],
            default=list(MAJOR_CODES),
            format_func=lambda code: STOCK_BY_CODE[code].label,
            placeholder="会社名を選択",
        )

    category_counts = pd.Series(
        [STOCK_BY_CODE[code].category for code in selected_codes]
    ).value_counts()
    if not category_counts.empty:
        category_text = " / ".join(
            f"{category} {count}社" for category, count in category_counts.items()
        )
        st.caption(f"選択中: {len(selected_codes)}社　｜　{category_text}")

    analyze_button = st.button(
        "選択銘柄をまとめて分析",
        type="primary",
        icon=":material/analytics:",
        width="stretch",
    )

if analyze_button:
    if not selected_codes:
        st.warning("分析する銘柄を1社以上選択してください。")
    else:
        try:
            selected_stocks = [STOCK_BY_CODE[code] for code in selected_codes]
            period_code = PERIOD_OPTIONS[str(period_label)]

            with st.status("市場データを取得して分析しています…", expanded=True) as status:
                st.write("SOX指数と日本株の日足終値を一括取得中")
                results, details, failures = analyze_stocks(selected_stocks, period_code)
                st.write("前日SOXと当日日本株を日付対応し、相関係数を計算中")
                status.update(label="分析が完了しました", state="complete", expanded=False)

            st.markdown('<div class="section-kicker">Overview</div>', unsafe_allow_html=True)
            st.subheader("分析サマリー")

            correlations = [float(result["相関係数"]) for result in results]
            best = results[0]
            strong_count = sum(value >= 0.40 for value in correlations)
            start_date = min(pd.Timestamp(result["開始日"]) for result in results)
            end_date = max(pd.Timestamp(result["終了日"]) for result in results)

            metric_cols = st.columns(4)
            metric_cols[0].metric("分析銘柄", f"{len(results)}社")
            metric_cols[1].metric(
                "最高相関",
                f"{float(best['相関係数']):.3f}",
                delta=str(best["会社名"]),
                delta_color="off",
            )
            metric_cols[2].metric("平均相関", f"{sum(correlations) / len(correlations):.3f}")
            metric_cols[3].metric("0.40以上", f"{strong_count}社")

            st.caption(
                f"分析期間: {period_label}　｜　比較日: {start_date:%Y-%m-%d}〜{end_date:%Y-%m-%d}　｜　"
                "前日のSOX → 当日の日本株"
            )

            render_summary_table(results)

            if failures:
                with st.expander(f"取得できなかった銘柄（{len(failures)}件）"):
                    for failure in failures:
                        st.write(f"- {failure}")

            render_stock_details(results, details)

            st.info(
                "相関は因果関係や将来の値動きを保証しません。銘柄一覧は日常比較用の主要例であり、"
                "半導体関連銘柄を網羅するものではありません。"
            )

        except AppError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(
                "予期しないエラーが発生しました。時間を置いて再度お試しください。"
            )
            with st.expander("技術情報"):
                st.code(f"{type(exc).__name__}: {exc}")
else:
    st.markdown('<div class="section-kicker">How it works</div>', unsafe_allow_html=True)
    st.subheader("使い方")
    instruction_cols = st.columns(3)
    instruction_cols[0].info("**1. 期間を選択**\n\n1か月・3か月・6か月・1年から選べます。")
    instruction_cols[1].info("**2. 銘柄を選択**\n\n主要銘柄、全銘柄、個別選択に対応しています。")
    instruction_cols[2].info("**3. 一括分析**\n\n相関ランキングと銘柄別20日データを表示します。")

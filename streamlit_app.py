from __future__ import annotations

import re
import unicodedata

import pandas as pd
import streamlit as st
import yfinance as yf

SOX_TICKER = "^SOX"
MIN_OBSERVATIONS = 10
CACHE_TTL_SECONDS = 60 * 60


class AppError(Exception):
    """画面に安全に表示できるアプリ用エラー。"""


st.set_page_config(
    page_title="SOX連動度チェッカー",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# iPhoneでも入力・ボタンを押しやすくするための最小限のCSS
st.markdown(
    """
    <style>
      .block-container {
        max-width: 700px;
        padding-top: 1.1rem;
        padding-right: 1rem;
        padding-left: 1rem;
        padding-bottom: 3rem;
      }
      div[data-testid="stTextInput"] input {
        min-height: 48px;
        font-size: 18px;
      }
      div[data-testid="stFormSubmitButton"] button {
        min-height: 52px;
        font-size: 18px;
        font-weight: 700;
        border-radius: 12px;
      }
      div[data-testid="stMetric"] {
        padding: 0.9rem 1rem;
        border-radius: 14px;
      }
      @media (max-width: 480px) {
        h1 { font-size: 1.65rem !important; }
        h2 { font-size: 1.25rem !important; }
        .block-container { padding-top: 0.7rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def normalize_japanese_ticker(raw_code: str) -> str:
    """4文字の日本株コードをYahoo Finance形式（例: 8035.T）に変換する。"""
    code = unicodedata.normalize("NFKC", raw_code).strip().upper()

    if re.fullmatch(r"[0-9A-Z]{4}", code):
        return f"{code}.T"

    if re.fullmatch(r"[0-9A-Z]{4}\.T", code):
        return code

    raise AppError(
        "証券コードは4文字で入力してください。例: 8035 または 8035.T"
    )


def extract_close(data: pd.DataFrame, ticker: str) -> pd.Series:
    """yfinanceの列形式が変わってもClose列を取り出せるようにする。"""
    if data is None or data.empty:
        raise AppError(
            f"{ticker} の価格データを取得できませんでした。"
            "コード、通信状況、Yahoo Finance側の一時的な制限をご確認ください。"
        )

    if isinstance(data.columns, pd.MultiIndex):
        close_columns = [
            column
            for column in data.columns
            if any(str(level) == "Close" for level in column)
        ]
        if not close_columns:
            raise AppError(f"{ticker} の終値（Close）列が見つかりませんでした。")
        close = data[close_columns[0]]
    else:
        if "Close" not in data.columns:
            raise AppError(f"{ticker} の終値（Close）列が見つかりませんでした。")
        close = data["Close"]

    close = pd.to_numeric(close, errors="coerce").dropna()
    if close.empty:
        raise AppError(f"{ticker} の有効な終値データがありません。")

    # 日足のラベルをタイムゾーンなしの「取引日」に統一する。
    index = pd.DatetimeIndex(close.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    close.index = index.normalize()

    close = close[~close.index.duplicated(keep="last")].sort_index()
    close.name = ticker
    return close


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def download_close(ticker: str) -> pd.Series:
    """直近3ヶ月の日足終値を取得する。"""
    try:
        data = yf.download(
            ticker,
            period="3mo",
            interval="1d",
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=False,
            ignore_tz=True,
            timeout=20,
            multi_level_index=False,
        )
    except Exception as exc:
        raise AppError(
            f"{ticker} のデータ取得中にエラーが発生しました。"
            "少し時間を置いて再度お試しください。"
        ) from exc

    return extract_close(data, ticker)


def calculate_lagged_correlation(
    japanese_close: pd.Series,
    sox_close: pd.Series,
) -> tuple[float, pd.DataFrame]:
    """
    前日のSOXリターンと当日の日本株リターンをそろえ、
    ピアソン相関係数を計算する。
    """
    japanese_return = japanese_close.pct_change(fill_method=None).rename(
        "日本株リターン"
    )
    sox_return = sox_close.pct_change(fill_method=None).rename("SOXリターン")

    if japanese_return.dropna().empty or sox_return.dropna().empty:
        raise AppError("リターンを計算するための価格データが不足しています。")

    # 土日・日米の祝日差に対応するため、SOXをカレンダー日付へ展開する。
    calendar = pd.date_range(
        start=min(japanese_return.index.min(), sox_return.index.min()),
        end=max(japanese_return.index.max(), sox_return.index.max()),
        freq="D",
    )

    # 休場日は直近のSOX取引日のリターンを引き継ぎ、その後1日shiftする。
    # 例: 月曜の日本株には、通常は前週金曜のSOXリターンが入る。
    sox_calendar_return = sox_return.reindex(calendar).ffill()
    previous_sox_return = sox_calendar_return.shift(1).rename("前日SOXリターン")

    # どのSOX取引日の値を使ったか、確認用に保持する。
    sox_source_date = pd.Series(sox_return.index, index=sox_return.index)
    previous_sox_date = (
        sox_source_date.reindex(calendar)
        .ffill()
        .shift(1)
        .rename("SOX取引日")
    )

    aligned = pd.concat(
        [japanese_return, previous_sox_return, previous_sox_date],
        axis=1,
        join="inner",
    ).dropna(subset=["日本株リターン", "前日SOXリターン"])

    if len(aligned) < MIN_OBSERVATIONS:
        raise AppError(
            f"有効な比較日が {len(aligned)} 日しかありません。"
            f"最低 {MIN_OBSERVATIONS} 日必要です。"
        )

    correlation = aligned["日本株リターン"].corr(
        aligned["前日SOXリターン"], method="pearson"
    )

    if pd.isna(correlation):
        raise AppError(
            "相関係数を計算できませんでした。値動きが一定、またはデータ不足の可能性があります。"
        )

    return float(correlation), aligned


def describe_correlation(value: float) -> str:
    """相関係数の読み方を簡易表示する。境界はあくまで目安。"""
    if value >= 0.70:
        return "強い正の相関"
    if value >= 0.40:
        return "中程度の正の相関"
    if value >= 0.20:
        return "弱い正の相関"
    if value > -0.20:
        return "線形の相関はほぼ見られない"
    if value > -0.40:
        return "弱い負の相関"
    if value > -0.70:
        return "中程度の負の相関"
    return "強い負の相関"


def render_detail_table(aligned: pd.DataFrame) -> None:
    """直近の対応データをスマホ向けに表示する。"""
    detail = aligned.tail(10).copy()
    detail.index.name = "日本株取引日"
    detail["日本株リターン"] *= 100
    detail["前日SOXリターン"] *= 100
    detail["SOX取引日"] = pd.to_datetime(detail["SOX取引日"]).dt.strftime(
        "%Y-%m-%d"
    )

    st.dataframe(
        detail,
        width="stretch",
        hide_index=False,
        column_config={
            "日本株リターン": st.column_config.NumberColumn(
                "日本株騰落率", format="%.2f%%"
            ),
            "前日SOXリターン": st.column_config.NumberColumn(
                "前日SOX騰落率", format="%.2f%%"
            ),
            "SOX取引日": st.column_config.TextColumn("対応SOX日"),
        },
    )


st.title("📈 SOX連動度チェッカー")
st.write(
    "前日のフィラデルフィア半導体株指数（SOX）の騰落率と、"
    "当日の日本株の騰落率の相関を直近3ヶ月で計算します。"
)

with st.form("correlation_form"):
    raw_code = st.text_input(
        "日本株の証券コード",
        value="8035",
        placeholder="例: 8035",
        help="4桁コード、またはYahoo Finance形式の8035.Tを入力できます。",
        max_chars=6,
    )
    submitted = st.form_submit_button(
        "相関を計算",
        type="primary",
        icon=":material/calculate:",
        width="stretch",
    )

if submitted:
    try:
        japanese_ticker = normalize_japanese_ticker(raw_code)

        with st.spinner("株価データを取得して計算しています…"):
            japanese_close = download_close(japanese_ticker)
            sox_close = download_close(SOX_TICKER)
            correlation, aligned_data = calculate_lagged_correlation(
                japanese_close,
                sox_close,
            )

        st.subheader("分析結果")
        st.metric(
            "前日SOX → 当日日本株の相関係数",
            f"{correlation:.3f}",
            border=True,
        )
        st.info(f"判定の目安: **{describe_correlation(correlation)}**")

        period_start = aligned_data.index.min().strftime("%Y-%m-%d")
        period_end = aligned_data.index.max().strftime("%Y-%m-%d")
        st.caption(
            f"銘柄: {japanese_ticker} / 有効観測数: {len(aligned_data)}日 / "
            f"比較期間: {period_start}〜{period_end}"
        )

        with st.expander("直近10日分の対応データを見る"):
            render_detail_table(aligned_data)

        st.warning(
            "相関は因果関係や将来の値動きを保証しません。"
            "Yahoo Financeのデータは遅延・欠損・仕様変更が起こる場合があります。"
        )

    except AppError as exc:
        st.error(str(exc))
    except Exception:
        st.error(
            "予期しないエラーが発生しました。入力コードを確認し、"
            "時間を置いて再度お試しください。"
        )

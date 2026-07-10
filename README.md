# SOX連動度ダッシュボード

前日のフィラデルフィア半導体株指数（SOX）のリターンと、当日の日本の半導体関連株リターンの相関をまとめて比較するStreamlitアプリです。

## 主な機能

- 1か月・3か月・6か月・1年から分析期間を選択
- 主要8銘柄、登録全銘柄、任意選択による複数銘柄の一括比較
- 会社名、証券コード、分野、期間相関、最新20日ローリング相関を一覧表示
- 各銘柄について直近20観測日の騰落率とローリング相関を表示
- 日米の土日・祝日差を考慮し、前日のSOXと当日の日本株を対応
- iPhoneを含むスマートフォン向けレスポンシブUI

## ローカル実行

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## ファイル

- `streamlit_app.py`: アプリ本体
- `requirements.txt`: Python依存ライブラリ

## 注意

相関は因果関係や将来の値動きを保証しません。銘柄一覧は日常比較用の主要例であり、半導体関連銘柄を網羅するものではありません。

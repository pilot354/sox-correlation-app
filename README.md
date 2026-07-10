# SOX連動度チェッカー

前日のSOX指数リターンと当日の日本株リターンの、直近3ヶ月のピアソン相関係数を計算するStreamlitアプリです。

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

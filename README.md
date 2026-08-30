# maslow-toggl-meisai

マズロー案件のToggl実績を集計してPDF明細を作るスクリプト。Claude Codeのクラウドルーティン(毎月1日AM3時JST)から実行される。

## 実行方法

```
pip install -r requirements.txt
TOGGL_API_TOKEN=xxxx python3 toggl_maslow_meisai.py <year> <month> <output.pdf>
```

- `TOGGL_API_TOKEN`: Toggl Track APIトークン(未設定時はWindowsローカルのTOKEN_PATHファイルにフォールバック)
- `TOGGL_MEISAI_FONT_REGULAR` / `TOGGL_MEISAI_FONT_BOLD`: PDFに使うCJKフォント(TTF/TTC)のパス。未指定ならWindowsのMeiryoパスにフォールバックするので、Linux環境では明示的に指定する(例: Noto Sans CJK JP)。

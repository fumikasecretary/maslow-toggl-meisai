# -*- coding: utf-8 -*-
"""
マズロー請求用 Toggl明細PDF生成スクリプト

使い方:
    python toggl_maslow_meisai.py 2026 7 output.pdf

- Toggl API (project: マズロー) から指定年月の実績を取得
- タグなしエントリは「事務」扱い
- タグ別の合計・総合計を計算
- 日付・時間帯・区分・時間の一覧表をPDFに出力(複数ページ対応)
- 標準出力にJSON summaryを出す(区分別合計・総合計、Push通知や後続処理用)

トークンは環境変数 TOGGL_API_TOKEN があればそれを使う。無ければ
ローカルのTOKEN_PATHファイルを読む(元のWindows環境での実行互換用)。

CJKフォントは環境変数 TOGGL_MEISAI_FONT_REGULAR / TOGGL_MEISAI_FONT_BOLD
で指定可能(クラウド実行時にNoto Sans CJKなどを指定する想定)。未指定なら
Windows標準のMeiryoパスにフォールバックする。
"""
import os
import sys
import json
import calendar
from datetime import datetime, timedelta, timezone

import urllib.request
import base64

TOKEN_PATH = r"I:\その他のパソコン\マイ ノートパソコン\1.FUMIKA\1.個人事業\code\TogglAPI.txt"
DEFAULT_FONT_REGULAR = r"C:\Windows\Fonts\meiryo.ttc"
DEFAULT_FONT_BOLD = r"C:\Windows\Fonts\meiryob.ttc"
PROJECT_NAME = "マズロー"
DEFAULT_TAG = "事務"
JST = timezone(timedelta(hours=9))

WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


def load_token():
    env_token = os.environ.get("TOGGL_API_TOKEN")
    if env_token:
        return env_token.strip()
    with open(TOKEN_PATH, encoding="utf-8") as f:
        return f.read().strip()


def api_get(path, token, params=None):
    url = f"https://api.track.toggl.com/api/v9{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url)
    auth = base64.b64encode(f"{token}:api_token".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_month_entries(token, year, month):
    # 月境界のズレを避けるため前後1日広めに取得し、あとでJST日付でフィルタする
    first = datetime(year, month, 1) - timedelta(days=1)
    last_day = calendar.monthrange(year, month)[1]
    last = datetime(year, month, last_day) + timedelta(days=1)
    entries = api_get(
        "/me/time_entries",
        token,
        {
            "start_date": first.strftime("%Y-%m-%d"),
            "end_date": last.strftime("%Y-%m-%d"),
        },
    )

    projects = api_get(f"/workspaces/{entries[0]['workspace_id']}/projects", token) if entries else []
    project_ids = {p["id"] for p in projects if p["name"] == PROJECT_NAME}

    rows = []
    for e in entries:
        if e.get("duration", 0) < 0:
            continue  # 実行中のタイマーはスキップ
        if project_ids and e.get("project_id") not in project_ids:
            continue
        start_utc = datetime.fromisoformat(e["start"].replace("Z", "+00:00"))
        start_jst = start_utc.astimezone(JST)
        stop_utc = datetime.fromisoformat(e["stop"].replace("Z", "+00:00"))
        stop_jst = stop_utc.astimezone(JST)
        if not (year == start_jst.year and month == start_jst.month):
            continue
        tags = e.get("tags") or []
        tag = tags[0] if tags else DEFAULT_TAG
        rows.append({
            "date": start_jst.date(),
            "start": start_jst,
            "stop": stop_jst,
            "duration": e["duration"],
            "tag": tag,
        })

    rows.sort(key=lambda r: r["start"])
    return rows


def fmt_hms(seconds):
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def build_summary(rows):
    from collections import defaultdict
    sums = defaultdict(int)
    total = 0
    for r in rows:
        sums[r["tag"]] += r["duration"]
        total += r["duration"]
    return sums, total


def render_pdf(rows, sums, total, year, month, out_path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_regular = os.environ.get("TOGGL_MEISAI_FONT_REGULAR", DEFAULT_FONT_REGULAR)
    font_bold = os.environ.get("TOGGL_MEISAI_FONT_BOLD", DEFAULT_FONT_BOLD)

    pdfmetrics.registerFont(TTFont("Meiryo", font_regular, subfontIndex=0))
    pdfmetrics.registerFont(TTFont("MeiryoB", font_bold, subfontIndex=0))

    title_style = ParagraphStyle("title", fontName="MeiryoB", fontSize=16, leading=20)
    normal_style = ParagraphStyle("normal", fontName="Meiryo", fontSize=10, leading=14)

    doc = SimpleDocTemplate(out_path, pagesize=A4,
                             topMargin=18 * mm, bottomMargin=18 * mm,
                             leftMargin=18 * mm, rightMargin=18 * mm)
    elems = []
    elems.append(Paragraph(f"マズロー 作業明細　{year}年{month}月分", title_style))
    elems.append(Spacer(1, 8 * mm))

    header = ["日付", "時間帯", "区分", "時間"]
    data = [header]
    for r in rows:
        wd = WEEKDAY_JP[r["start"].weekday()]
        date_str = f"{r['date'].month}/{r['date'].day}({wd})"
        time_str = f"{r['start'].strftime('%H:%M')}-{r['stop'].strftime('%H:%M')}"
        data.append([date_str, time_str, r["tag"], fmt_hms(r["duration"])])

    table = Table(data, colWidths=[35 * mm, 40 * mm, 30 * mm, 30 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Meiryo"),
        ("FONTNAME", (0, 0), (-1, 0), "MeiryoB"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dddddd")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
    ]))
    elems.append(table)
    elems.append(Spacer(1, 10 * mm))

    summary_lines = [f"{tag}　合計 {fmt_hms(sec)}（{sec/3600:.2f}時間）" for tag, sec in sums.items()]
    summary_lines.append(f"総合計　{fmt_hms(total)}（{total/3600:.2f}時間）")
    for line in summary_lines:
        elems.append(Paragraph(line, normal_style))

    doc.build(elems)


def main():
    year = int(sys.argv[1])
    month = int(sys.argv[2])
    out_path = sys.argv[3] if len(sys.argv) > 3 else f"{year}{month:02d}_maslowmeisai.pdf"

    token = load_token()
    rows = fetch_month_entries(token, year, month)
    sums, total = build_summary(rows)
    render_pdf(rows, sums, total, year, month, out_path)

    summary = {
        "year": year,
        "month": month,
        "by_tag": {tag: round(sec / 3600, 2) for tag, sec in sums.items()},
        "total_hours": round(total / 3600, 2),
        "entry_count": len(rows),
        "pdf_path": out_path,
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

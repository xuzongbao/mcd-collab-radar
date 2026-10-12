#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦麦联名雷达 · 联名抢购攻略卡渲染器
把「联名情报表 + 价梯表 + 渠道策略」渲染成一张可截图分享的小红书风 HTML 卡片。

用法:
    python3 render_collab_card.py --input plan.json --output demo/out/collab-card.html
    python3 render_collab_card.py --demo          # 用内置示例数据渲染

特点:
    - 纯标准库，零第三方依赖
    - 输出自包含 HTML（内联 CSS，无外链字体/CDN），可离线打开截图
    - 卡片宽度适配手机截图（约 420px）
"""
import argparse
import html
import json
import sys
from pathlib import Path

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: #FDF2E9;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  display: flex; justify-content: center; padding: 28px 12px;
}
.card {
  width: 420px; background: #FFFBF5; border-radius: 28px; overflow: hidden;
  box-shadow: 0 12px 40px rgba(230, 100, 60, 0.16);
  border: 1px solid rgba(230, 120, 80, 0.14);
}
.hero {
  background: linear-gradient(135deg, #FFD9C7 0%, #FFC2AE 45%, #FFB39C 100%);
  padding: 26px 24px 22px; position: relative;
}
.hero::after {
  content: ""; position: absolute; right: -30px; top: -30px; width: 130px; height: 130px;
  border-radius: 50%; background: rgba(255, 255, 255, 0.28);
}
.hero .kicker { font-size: 12px; color: #B0522E; letter-spacing: 2px; font-weight: 600; }
.hero h1 { font-size: 25px; color: #8C3A1E; margin-top: 6px; font-weight: 800; letter-spacing: 1px; }
.hero .slogan { font-size: 12px; color: #A85B36; margin-top: 8px; font-weight: 600; }
.chips { display: flex; gap: 8px; padding: 16px 20px 4px; flex-wrap: wrap; }
.chip {
  background: #FFF1E8; border: 1px solid #FFD9C4; color: #B0522E;
  font-size: 12px; font-weight: 600; padding: 6px 12px; border-radius: 999px;
}
.section-title {
  font-size: 14px; font-weight: 800; color: #8C3A1E;
  padding: 16px 20px 8px; display: flex; align-items: center; gap: 6px;
}
.window {
  margin: 0 16px 10px; background: linear-gradient(135deg, #FFF3E0, #FFE3D0);
  border-radius: 16px; padding: 12px 14px; display: flex; align-items: center; gap: 12px;
}
.w-icon {
  width: 42px; height: 42px; border-radius: 14px; flex-shrink: 0;
  background: linear-gradient(135deg, #FF8A65, #F4511E);
  display: flex; align-items: center; justify-content: center; font-size: 18px;
}
.w-body { flex: 1; min-width: 0; }
.w-item { font-size: 13px; color: #4A2C1D; font-weight: 700; }
.w-time { font-size: 11px; color: #B08872; margin-top: 3px; }
.w-cd { text-align: right; flex-shrink: 0; }
.w-cd .cd { font-size: 12px; font-weight: 800; color: #D84315; }
.w-cd .adv { font-size: 10px; color: #C9A48F; margin-top: 2px; }
.merch {
  margin: 0 16px 10px; background: #FFFFFF; border-radius: 16px; padding: 12px 14px;
  border: 1px solid #FFE8DC;
}
.m-row { display: flex; justify-content: space-between; align-items: baseline; padding: 7px 0; }
.m-row + .m-row { border-top: 1px dashed #FFE0D0; }
.m-left .name { font-size: 13px; color: #4A2C1D; font-weight: 700; }
.m-left .mech { font-size: 11px; color: #B08872; margin-top: 2px; }
.m-right { text-align: right; }
.m-right .price { font-size: 15px; font-weight: 800; color: #F4511E; }
.m-right .tag { font-size: 10px; color: #fff; background: #F4511E; border-radius: 6px; padding: 1px 6px; margin-left: 4px; }
.tips {
  margin: 6px 16px 4px; background: #FFF8F2; border: 1px solid #FFE4D6;
  border-radius: 16px; padding: 12px 16px;
}
.tip { font-size: 12px; color: #7A4A30; line-height: 1.9; }
.tip::before { content: "🎯 "; }
.footer { padding: 14px 20px 20px; text-align: center; }
.footer .pb { font-size: 11px; color: #8C3A1E; font-weight: 700; line-height: 1.8; }
.footer .src { font-size: 10px; color: #C9A48F; margin-top: 8px; line-height: 1.6; }
"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def render(plan: dict) -> str:
    collab = esc(plan.get("collab", "麦当劳限定联名"))
    nickname = esc(plan.get("nickname", "雷达用户"))
    today = esc(plan.get("today", ""))
    windows = plan.get("windows", [])
    merch = plan.get("merch", [])
    tips = plan.get("channel_tips", [])
    playbook = plan.get("playbook", [])
    repo = esc(plan.get("repo", "github.com/xuzongbao/mcd-collab-radar"))

    chips = [f'<span class="chip">👤 {nickname}</span>']
    if today:
        chips.append(f'<span class="chip">🗓 {today}</span>')

    w_rows = []
    for w in windows:
        w_rows.append(f"""
      <div class="window">
        <div class="w-icon">⏰</div>
        <div class="w-body">
          <div class="w-item">{esc(w.get('item', ''))}</div>
          <div class="w-time">{esc(w.get('time', ''))} · {esc(w.get('advance', ''))}</div>
        </div>
        <div class="w-cd">
          <div class="cd">{esc(w.get('countdown', ''))}</div>
          <div class="adv">倒计时</div>
        </div>
      </div>""")

    m_rows = []
    for m in merch:
        tag = '<span class="tag">最优</span>' if m.get("best") else ""
        m_rows.append(f"""
      <div class="m-row">
        <div class="m-left">
          <div class="name">{esc(m.get('item', ''))}</div>
          <div class="mech">{esc(m.get('mechanism', ''))}</div>
        </div>
        <div class="m-right"><span class="price">{esc(m.get('best_price', '—'))}</span>{tag}</div>
      </div>""")

    tip_html = "".join(f'<div class="tip">{esc(t)}</div>' for t in tips)
    pb_html = "".join(f'<div class="tip">{esc(p)}</div>' for p in playbook)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>联名抢购攻略卡 · {collab}</title>
<style>{CSS}</style>
</head>
<body>
  <div class="card">
    <div class="hero">
      <div class="kicker">MCD COLLAB RADAR</div>
      <h1>📡 麦麦联名雷达</h1>
      <div class="slogan">联名可以冲，账要先算清</div>
    </div>
    <div class="chips">
      {''.join(chips)}
      <span class="chip">🤝 {collab}</span>
    </div>
    <div class="section-title">⏰ 冲浪窗口</div>
    {''.join(w_rows)}
    <div class="section-title">💰 价梯（到手价）</div>
    <div class="merch">{''.join(m_rows)}</div>
    <div class="section-title">📍 渠道策略</div>
    <div class="tips">{tip_html}</div>
    <div class="section-title">📌 攻略要点</div>
    <div class="tips">{pb_html}</div>
    <div class="footer">
      <div class="pb">由「麦麦联名雷达」生成 · 基于麦当劳中国官方 MCP 能力<br>
      非麦当劳官方产品 · 周边为消费品，不建议囤积炒作</div>
      <div class="src">价格与活动以官方渠道实时信息为准 · 项目地址 {repo} · 欢迎 Star ⭐</div>
    </div>
  </div>
</body>
</html>"""


DEMO_PLAN = {
    "collab": "麦当劳 × PEACEMINUSONE",
    "nickname": "薯条爱好者",
    "today": "2026-10-12",
    "repo": "github.com/xuzongbao/mcd-collab-radar",
    "windows": [
        {"item": "联名徽章（一套三枚）", "time": "10/15 10:45 开售", "advance": "10/15 10:40 积分抢先购", "countdown": "2 天 11 小时"},
        {"item": "限定主题丝巾", "time": "10/22 10:45 开售", "advance": "10/22 10:40 积分抢先购", "countdown": "9 天 11 小时"},
    ],
    "merch": [
        {"item": "联名徽章（一套三枚）", "mechanism": "任意消费 +39.9", "best_price": "¥61.8", "best": True},
        {"item": "限定主题丝巾", "mechanism": "任意消费 +39.9", "best_price": "¥61.8", "best": True},
        {"item": "复古棒球帽", "mechanism": "任意消费 +39.9", "best_price": "¥61.8", "best": False},
        {"item": "随单小卡（3 款随机）", "mechanism": "购买联名套餐随单得", "best_price": "¥0", "best": False},
    ],
    "channel_tips": [
        "首发日避开核心商圈大店（痛店排队久、售罄快）",
        "优先查就近 3-5 家非热门门店，货量通常更充足",
        "APP 内先确认库存再出发，部分周边仅线上有售",
    ],
    "playbook": [
        "定闹钟：开售前 5 分钟进 APP，积分用户 10:40 抢先购",
        "提前领好券再下单，麦金卡随单再减 5 元",
        "周边是消费品，喜欢再冲，别为凑单点多一份",
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser(description="渲染麦麦联名攻略卡")
    ap.add_argument("--input", help="计划 JSON 文件路径")
    ap.add_argument("--output", help="输出 HTML 路径（默认 demo/out/collab-card.html）")
    ap.add_argument("--demo", action="store_true", help="使用内置示例数据")
    args = ap.parse_args()

    if args.demo:
        plan = DEMO_PLAN
    elif args.input:
        plan = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        print("错误：需要 --input 或 --demo", file=sys.stderr)
        return 1

    out = Path(args.output or "demo/out/collab-card.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(plan), encoding="utf-8")
    print(f"✅ 联名攻略卡已生成: {out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

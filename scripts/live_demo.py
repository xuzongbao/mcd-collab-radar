#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦麦联名雷达 · 实盘演示编排器（live_demo.py）

一条命令跑完「扫雷达 → 算三本账 → 出攻略卡」全流程，全部数据来自麦当劳中国
官方 MCP（mcd-mcp）实时返回，用于：

  1. 联名开售当天（如 GD x PEACEMINUSONE 徽章 10/15 10:45）现场实跑演示
  2. 验证 SKILL.md 工作流在真实环境下成立
  3. 产出可审计的原始返回（out/raw/*.json）+ 攻略卡 + 演示报告

用法（实盘，需 Token）:
    export MCD_MCP_TOKEN="你的Token"
    python3 scripts/live_demo.py                          # 默认南京新街口
    python3 scripts/live_demo.py --city 上海市 --keyword 人民广场
    python3 scripts/live_demo.py --store 1990346         # 指定主门店
    python3 scripts/live_demo.py --wait-until 10:40      # 等到 10:40 再跑（抢积分抢先购）
    python3 scripts/live_demo.py --wait-until 10:45 --no-card

用法（离线回放，无需 Token）:
    python3 scripts/live_demo.py --dry-run

设计原则:
    - 纯 Python 标准库，零第三方依赖
    - 所有价格必须由 calculate-price 实算，禁止用菜单价冒充实算价
    - 每一步失败不中断整体（降级继续），并在报告中如实标注
    - Token 只从环境变量 / 命令行读取，绝不写入任何产物文件
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

MCP_URL = "https://mcp.mcd.cn"
REPO_LINE = "github.com/xuzongbao/mcd-collab-radar"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

# 联名活动识别关键词（不绑定单次联名，未来新联名自动纳入）
COLLAB_KEYWORDS = ("PEACEMINUSONE", "G-DRAGON", "权志龙", "联名", "周边", "限定")
MERCH_HINTS = (
    ("徽章", "联名徽章"),
    ("丝巾", "限定丝巾"),
    ("棒球帽", "联名棒球帽"),
    ("帽子", "联名帽子"),
    ("小卡", "随单小卡"),
    ("挂件", "联名挂件"),
    ("T恤", "联名T恤"),
)


# ---------------------------------------------------------------- 基础工具

def log(msg=""):
    print(msg, flush=True)


def rule(title=""):
    log("")
    log("=" * 74)
    if title:
        log("  " + title)
        log("=" * 74)


def fmt_money(fen) -> str:
    """分 -> '¥12.30'"""
    try:
        return "¥%.2f" % (float(fen) / 100.0)
    except (TypeError, ValueError):
        return "—"


def fmt_countdown(delta: dt.timedelta) -> str:
    total = int(delta.total_seconds())
    if total <= 0:
        return "已开售"
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days > 0:
        return "%d 天 %d 小时" % (days, hours)
    if hours > 0:
        return "%d 小时 %d 分" % (hours, minutes)
    return "%d 分钟" % minutes


def parse_server_dt(text: str):
    """从 '2026-10-13 20:21:07' 或 ISO 串解析 datetime。"""
    if not text:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})", text)
    if not m:
        return None
    y, mo, d, h, mi, s = (int(x) for x in m.groups())
    return dt.datetime(y, mo, d, h, mi, s)


def extract_json(text: str):
    """mcd-mcp 的 tools/call 返回 Markdown 描述 + 末尾 JSON；抽取 JSON 部分。"""
    if not text:
        return None
    idx = text.find('{"success"')
    if idx < 0:
        return None
    try:
        return json.loads(text[idx:])
    except json.JSONDecodeError:
        # 尾部可能混有说明文字，尝试逐字符收敛
        for end in range(len(text), idx, -1):
            try:
                return json.loads(text[idx:end])
            except json.JSONDecodeError:
                continue
    return None


# ---------------------------------------------------------------- MCP 客户端

class McpClient:
    """最小可用的 mcd-mcp Streamable HTTP 客户端（标准库实现）。"""

    def __init__(self, token: str, url: str = MCP_URL, verbose=True):
        self.token = token
        self.url = url
        self.verbose = verbose
        self.session = None
        self.server_info = {}
        self.calls = []          # [(tool, ok, note)]
        self._id = 0

    def _rpc(self, method, params):
        self._id += 1
        body = json.dumps({
            "jsonrpc": "2.0", "id": self._id, "method": method, "params": params,
        }).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        req.add_header("Authorization", "Bearer " + self.token)
        if self.session:
            req.add_header("mcp-session-id", self.session)
        with urllib.request.urlopen(req, timeout=90) as resp:
            if not self.session:
                self.session = resp.headers.get("mcp-session-id")
            raw = resp.read().decode("utf-8", "replace")
        if raw.lstrip().startswith("{"):
            return json.loads(raw)
        for line in raw.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        raise ValueError("无法解析 MCP 响应: " + raw[:200])

    def connect(self):
        r = self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcd-collab-radar-live-demo", "version": "1.0.0"},
        })
        self.server_info = r.get("result", {}).get("serverInfo", {})
        try:
            self._rpc("notifications/initialized", {})
        except Exception:
            pass  # 部分服务端不强制要求
        return self.server_info

    def call(self, tool, arguments=None, retries=2):
        """返回 (text, parsed_json_or_None)。失败返回 (None, None) 并记录。"""
        last_err = None
        for attempt in range(retries + 1):
            try:
                r = self._rpc("tools/call", {"name": tool, "arguments": arguments or {}})
                result = r.get("result", {})
                if result.get("isError"):
                    last_err = "工具返回 isError"
                    time.sleep(0.6)
                    continue
                texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
                text = "\n".join(texts)
                self.calls.append((tool, True, ""))
                time.sleep(0.25)  # 温和调用，远离 600 次/分钟限流
                return text, extract_json(text)
            except urllib.error.HTTPError as e:
                last_err = "HTTP %s" % e.code
                if e.code in (401, 403):
                    break
                time.sleep(0.8)
            except Exception as e:  # 网络抖动等
                last_err = "%s: %s" % (type(e).__name__, e)
                time.sleep(0.8)
        self.calls.append((tool, False, last_err or "未知错误"))
        if self.verbose:
            log("    ⚠️  %s 调用失败（%s），已降级跳过" % (tool, last_err))
        return None, None


# ---------------------------------------------------------------- 离线回放

class FixtureStore:
    """--dry-run：从 demo/fixtures/raw/ 读取已录制的真实返回。"""

    def __init__(self, fixtures_dir: Path):
        self.dir = fixtures_dir / "raw"
        self.calls = []
        self.server_info = {"name": "mcd-mcp", "version": "1.0.0（回放）"}

    def call(self, tool, arguments=None, retries=0):
        name = tool
        if tool == "calculate-price":
            code = (arguments or {}).get("items", [{}])[0].get("productCode", "x")
            name = "calculate-price_%s" % code
        path = self.dir / ("%s.json" % name)
        if not path.exists():
            self.calls.append((tool, False, "缺少回放文件 %s" % path.name))
            log("    ⚠️  离线回放缺少 %s，该步骤降级" % path.name)
            return None, None
        data = json.loads(path.read_text(encoding="utf-8"))
        # 兼容两种保存格式：完整 tools/call 响应 / 纯 text
        if isinstance(data, dict) and "result" in data:
            text = "\n".join(c.get("text", "") for c in data["result"].get("content", [])
                             if c.get("type") == "text")
        else:
            text = data.get("text", "")
        self.calls.append((tool, True, "fixture"))
        return text, extract_json(text)


# ---------------------------------------------------------------- 活动解析

def parse_campaign(text: str):
    """把 campaign-calendar 的 Markdown 解析成 [{date, title, content, image}]。"""
    if not text:
        return []
    marks = list(re.finditer(r"####\s*(\d{4}年\d{1,2}月\d{1,2}日)", text))
    activities = []
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[start:end]
        for blk in re.split(r"(?=-)\s+\*\*活动标题\*\*：", body):
            mt = re.search(r"\*\*活动标题\*\*：(.+)", blk)
            if not mt:
                continue
            mc = re.search(r"\*\*活动内容介绍\*\*：(.+?)(?=\*\*活动图片介绍\*\*|\Z)", blk, re.S)
            content = " ".join(mc.group(1).split()) if mc else ""
            mi = re.search(r'<img src="([^"]+)"', blk)
            activities.append({
                "date": m.group(1),
                "title": mt.group(1).strip(),
                "content": content,
                "image": mi.group(1) if mi else "",
            })
    return activities


def merch_name_of(title: str, content: str) -> str:
    """识别周边名称：先看标题（最可靠），再看正文。
    注意：丝巾文案里会出现「叠搭联名棒球帽&徽章」，若先扫正文会误判。"""
    name = ""
    for kw, n in MERCH_HINTS:
        if kw in title:
            name = n
            break
    if not name:
        for kw, n in MERCH_HINTS:
            if kw in content:
                name = n
                break
    # 补充规格信息，如「一套三枚」
    m = re.search(r"一套([一二三四五六七八九十\d]+枚)", content)
    if m and "套" not in name:
        name = "%s（一套%s）" % (name, m.group(1))
    return name


def parse_merch_events(activities):
    """从活动中抽取联名周边事件：开售时刻 / 积分抢先购 / 换购机制。"""
    events, seen = [], set()
    for a in activities:
        blob = a["title"] + " " + a["content"]
        if not any(k in blob for k in COLLAB_KEYWORDS):
            continue
        name = merch_name_of(a["title"], a["content"])
        sale = re.search(r"(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})\s*开售", blob)
        advance = re.search(r"积分抢先购\s*(\d{1,2}):(\d{2})\s*开抢", blob)
        add_price = re.search(r"加\s*(\d+(?:\.\d+)?)\s*元", blob)
        if not sale:
            continue
        key = (name, sale.group(0))
        if key in seen:
            continue
        seen.add(key)
        year = dt.date.today().year
        try:
            sale_dt = dt.datetime(year, int(sale.group(1)), int(sale.group(2)),
                                  int(sale.group(3)), int(sale.group(4)))
        except ValueError:
            continue
        adv_dt = None
        if advance:
            adv_dt = sale_dt.replace(hour=int(advance.group(1)), minute=int(advance.group(2)))
        events.append({
            "name": name or a["title"].strip(),
            "title": a["title"].strip(),
            "desc": a["content"],
            "sale_dt": sale_dt,
            "advance_dt": adv_dt,
            "add_price": float(add_price.group(1)) if add_price else None,
            "date_label": a["date"],
        })
    events.sort(key=lambda e: e["sale_dt"])
    return events


# ---------------------------------------------------------------- 菜单分析

def parse_menu(text: str):
    """query-meals -> [(code, name, price_yuan)]，按价格升序。"""
    if not text:
        return []
    j = extract_json(text)
    if not j or not j.get("data"):
        return []
    meals = j["data"].get("meals", {}) or {}
    items = []
    for code, v in meals.items():
        try:
            price = float(v.get("currentPrice") or 0)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        items.append((code, v.get("name", ""), price))
    items.sort(key=lambda x: (x[2], x[1]))
    return items


def pick_paths(items, feed_name_hint="龙焰"):
    """从菜单挑出凑单候选：极限下限 / 稳妥凑单 / 小食凑单 / 饱腹路径。"""
    if not items:
        return []
    is_addon = lambda n: ("酱" in n) or ("配料" in n)
    normal = [i for i in items if not is_addon(i[1])]
    picks = []

    # 极限下限：全场最便宜（可能是蘸酱类加购项，需 APP 确认能否作为换购消费）
    if items:
        picks.append(("极限下限", items[0], "全场最低价；加购类需 APP 确认可作换购消费"))
    # 稳妥凑单：最便宜的非加购类
    if normal:
        picks.append(("稳妥凑单", normal[0], "可单独下单的餐品，已实算"))
    # 小食凑单：次便宜的非加购类
    if len(normal) > 1:
        picks.append(("小食凑单", normal[1], "菜单现价，已实算"))
    # 饱腹路径：优先联名三件套，否则最便宜三件套
    feed = [i for i in items if feed_name_hint in i[1] and "三件套" in i[1]]
    if not feed:
        feed = [i for i in items if "三件套" in i[1]]
    if feed:
        picks.append(("饱腹路径", feed[0], "联名新品三件套，已实算"))
    return picks


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(
        description="麦麦联名雷达 · 实盘演示编排器（数据全部来自麦当劳中国官方 MCP）")
    ap.add_argument("--token", default=os.environ.get("MCD_MCP_TOKEN", ""),
                    help="MCP Token（也可用环境变量 MCD_MCP_TOKEN）")
    ap.add_argument("--dry-run", action="store_true",
                    help="离线回放 demo/fixtures/raw/ 中录制的真实返回，无需 Token")
    ap.add_argument("--fixtures", default=str(PROJECT_DIR / "demo" / "fixtures"),
                    help="离线回放数据目录")
    ap.add_argument("--out", default=str(PROJECT_DIR / "demo" / "out"), help="输出目录")
    ap.add_argument("--city", default="南京市", help="门店检索城市")
    ap.add_argument("--keyword", default="新街口", help="门店检索关键词（商圈/地名）")
    ap.add_argument("--store", default="", help="指定主门店 storeCode（默认取检索结果中最近的一家）")
    ap.add_argument("--nickname", default="GD 追更人", help="卡片上的昵称")
    ap.add_argument("--wait-until", default="", metavar="HH:MM",
                    help="等到本地该时刻再开始跑（如 10:40 抢积分抢先购窗口）")
    ap.add_argument("--no-card", action="store_true", help="只出报告，不渲染攻略卡")
    ap.add_argument("--feed-hint", default="龙焰", help="饱腹路径的联名新品关键词")
    args = ap.parse_args()

    out_dir = Path(args.out)
    raw_dir = out_dir / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    # ---- 等待窗口 ----
    if args.wait_until:
        try:
            hh, mm = (int(x) for x in args.wait_until.split(":"))
        except ValueError:
            log("❌ --wait-until 格式应为 HH:MM"); return 2
        now = dt.datetime.now()
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target < now:
            target += dt.timedelta(days=1)
        log("⏳ 等待至 %s 起跑（还剩 %s）…" % (args.wait_until, fmt_countdown(target - now)))
        while True:
            remain = target - dt.datetime.now()
            if remain.total_seconds() <= 0:
                break
            time.sleep(min(20, max(1, remain.total_seconds())))

    # ---- 连接 ----
    if args.dry_run:
        mcp = FixtureStore(Path(args.fixtures))
        mode = "离线回放（demo/fixtures/raw/）"
        rule("麦麦联名雷达 · 实盘演示（离线回放模式）")
    else:
        if not args.token:
            log("❌ 未提供 Token：请设置环境变量 MCD_MCP_TOKEN 或使用 --token，"
                "或加 --dry-run 离线回放")
            return 2
        rule("麦麦联名雷达 · 实盘演示（真实 MCP 调用）")
        mcp = McpClient(args.token)
        try:
            info = mcp.connect()
        except Exception as e:
            log("❌ MCP 握手失败：%s" % e)
            log("   请检查网络与 Token（401=Token 失效，429=触发限流）")
            return 1
        mode = "实盘（真实 Token）"
    log("  模式：%s" % mode)
    log("  服务端：%s v%s" % (mcp.server_info.get("name", "mcd-mcp"),
                             mcp.server_info.get("version", "?")))
    report = {
        "mode": mode,
        "started_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "server": mcp.server_info,
        "steps": [],
    }

    def step(title):
        rule(title)

    def save_raw(name, text):
        if text is None:
            return
        (raw_dir / ("%s.json" % name)).write_text(
            json.dumps({"tool": name, "text": text}, ensure_ascii=False, indent=2),
            encoding="utf-8")

    # ==================================================== 1. 服务器时间
    step("① 服务器时间（now-time-info）")
    text, j = mcp.call("now-time-info")
    save_raw("now-time-info", text)
    server_now = None
    if j and j.get("data"):
        server_now = parse_server_dt(j["data"].get("datetime") or j["data"].get("formatted"))
        log("  服务器时间：%s（%s）" % (j["data"].get("formatted"), j["data"].get("timezone")))
        report["server_time"] = j["data"].get("formatted")
    if not server_now:
        server_now = dt.datetime.now()
        log("  ⚠️ 未能获取服务器时间，回退本地时间 %s" % server_now.strftime("%F %T"))
    log("  本地时间：  %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # ==================================================== 2. 活动雷达
    step("② 活动雷达（campaign-calendar）")
    text, _ = mcp.call("campaign-calendar")
    save_raw("campaign-calendar", text)
    activities = parse_campaign(text)
    events = parse_merch_events(activities)
    log("  日历活动 %d 条，识别到联名周边事件 %d 个" % (len(activities), len(events)))
    for e in events:
        cd_adv = fmt_countdown(e["advance_dt"] - server_now) if e["advance_dt"] else "—"
        cd_sale = fmt_countdown(e["sale_dt"] - server_now)
        log("  • %-10s 开售 %s（抢先购 %s）%s" % (
            e["name"], e["sale_dt"].strftime("%m-%d %H:%M"),
            e["advance_dt"].strftime("%H:%M") if e["advance_dt"] else "—",
            "｜倒计时 " + cd_sale if cd_sale != "已开售" else "｜已开售"))
        log("    机制：任意餐品消费 + %.1f 元换购｜%s" % (e["add_price"] or 39.9, e["desc"][:60]))
    report["events"] = [{
        "name": e["name"], "sale": e["sale_dt"].strftime("%Y-%m-%d %H:%M"),
        "advance": e["advance_dt"].strftime("%Y-%m-%d %H:%M") if e["advance_dt"] else "",
        "add_price": e["add_price"], "desc": e["desc"], "countdown": fmt_countdown(e["sale_dt"] - server_now),
    } for e in events]

    # ==================================================== 3. 积分账户
    step("③ 积分账户（query-my-account）")
    text, j = mcp.call("query-my-account")
    save_raw("query-my-account", text)
    points = None
    if j and j.get("data"):
        points = j["data"].get("availablePoint")
        log("  可用积分：%s（累计 %s，本月将过期 %s）" % (
            points, j["data"].get("accumulativePoint"), j["data"].get("currentMouthExpirePoint")))
        report["points"] = points
    else:
        log("  ⚠️ 未获取到积分信息")

    # ==================================================== 4. 积分商城核对
    step("④ 积分商城核对（mall-points-products）")
    text, j = mcp.call("mall-points-products")
    save_raw("mall-points-products", text)
    mall_hits = []
    other_collab = 0
    mall_total = 0
    if j and isinstance(j.get("data"), list):
        mall_total = len(j["data"])
        for p in j["data"]:
            name = p.get("spuName", "")
            # 只认本次联名的周边关键词；其它联名商品仅计数，不点名（避免提及无关品牌）
            if any(k in name for k in ("徽章", "丝巾", "棒球帽", "PEACEMINUSONE", "G-DRAGON")):
                mall_hits.append(name)
            elif "联名" in name:
                other_collab += 1
    if mall_hits:
        log("  ⚠️ 积分商城中出现本次联名周边：%s" % "、".join(mall_hits[:5]))
        report["mall_conclusion"] = "联名周边在积分商城有兑换项，需重新评估积分路径"
    else:
        log("  ✅ 在架商品 %d 个，其中无本次联名周边（另有 %d 个其它联名类商品）"
            % (mall_total, other_collab))
        log("  → 结论：机制是「任意餐品消费 + %.1f 元换购」，优化目标是把凑单餐品压到最便宜，而非攒积分"
            % (events[0]["add_price"] if events and events[0]["add_price"] else 39.9))
        report["mall_conclusion"] = ("联名周边不在积分商城兑换列表（在架 %d 个商品），机制为任意消费换购"
                                     % mall_total)

    # ==================================================== 5. 门店雷达
    step("⑤ 渠道账 · 门店雷达（query-nearby-stores）")
    text, j = mcp.call("query-nearby-stores",
                       {"beType": 1, "searchType": 2, "city": args.city, "keyword": args.keyword})
    save_raw("query-nearby-stores", text)
    stores = []
    if j and isinstance(j.get("data"), list):
        for s in j["data"]:
            try:
                dist = float(s.get("distance") or 0)
            except (TypeError, ValueError):
                dist = 0.0
            stores.append({
                "code": s.get("storeCode", ""), "name": s.get("storeName", ""),
                "address": s.get("address", ""), "distance": dist,
                "open": s.get("businessStartTime", ""), "close": s.get("businessEndTime", ""),
                "h24": (s.get("businessStartTime") == "00:00" and s.get("businessEndTime") == "23:59"),
                "status": s.get("businessStatus"),
            })
        stores.sort(key=lambda s: s["distance"])
        for s in stores[:6]:
            log("  %s %-22s %4.0fm  %s-%s%s" % (
                "🕑" if s["h24"] else "  ", s["name"], s["distance"], s["open"], s["close"],
                "" if s["status"] else "（休息中）"))
        log("  共 %d 家门店，主门店默认取最近的一家" % len(stores))
        report["stores"] = stores
    else:
        log("  ⚠️ 门店检索失败，渠道账降级")

    primary = None
    if stores:
        primary = next((s for s in stores if s["code"] == args.store), stores[0])
    elif args.store:
        primary = {"code": args.store, "name": "指定门店", "address": "", "distance": 0,
                   "open": "", "close": "", "h24": False, "status": True}
    if not primary:
        log("  ❌ 无可用门店，价梯账无法实算（菜单与算价都依赖门店编码）")
        report["fatal"] = "无可用门店"
        return finish(report, mcp, args, out_dir, raw_dir, None)

    log("  主门店：%s %s（%s，%s）" % (primary["code"], primary["name"],
                                     primary["address"], "24 小时" if primary["h24"] else
                                     "%s-%s" % (primary["open"], primary["close"])))

    # ==================================================== 6. 菜单
    step("⑥ 价梯账 · 菜单（query-meals）")
    text, j = mcp.call("query-meals",
                       {"storeCode": primary["code"], "orderType": 1, "beType": 1})
    save_raw("query-meals", text)
    items = parse_menu(text)
    log("  在售餐品 %d 个，最便宜的 5 个：" % len(items))
    for code, name, price in items[:5]:
        log("    ¥%-6.1f %-18s (code=%s)" % (price, name, code))
    paths = pick_paths(items, args.feed_hint)
    if not paths:
        log("  ❌ 菜单解析失败，价梯账降级")
        report["menu_items"] = 0

    # ==================================================== 7. 实算价格
    step("⑦ 价梯账 · 实算（calculate-price）")
    ladder = []
    add_price = (events[0]["add_price"] if events and events[0]["add_price"] else 39.9)
    for label, (code, name, price), note in paths:
        text, j = mcp.call("calculate-price",
                           {"beType": 1, "orderType": 1, "storeCode": primary["code"],
                            "items": [{"productCode": code, "quantity": 1}]})
        save_raw("calculate-price_%s" % code, text)
        verified = False
        if j and j.get("data"):
            fen = j["data"].get("price")
            if fen is not None:
                price = float(fen) / 100.0
                verified = True
        total = round(price + add_price, 2)
        ladder.append({
            "path": label, "food": name, "food_price": "¥%.2f" % price,
            "total": "¥%.2f" % total, "code": code,
            "note": note + ("｜已实算" if verified else "｜菜单价（实算未返回）"),
            "verified": verified,
        })
        log("  %-6s %-18s %-8s + %.1f = %-8s %s" % (
            label, name, "¥%.2f" % price, add_price, "¥%.2f" % total,
            "✅实算" if verified else "⚠️菜单价"))
    report["ladder"] = ladder

    # ==================================================== 8. 券况
    step("⑧ 券况（query-store-coupons / available-coupons）")
    text, j = mcp.call("query-store-coupons",
                       {"storeCode": primary["code"], "beType": 1, "orderType": 1})
    save_raw("query-store-coupons", text)
    store_coupons = []
    if j and isinstance(j.get("data"), list):
        store_coupons = j["data"]
        log("  门店券 %d 张" % len(store_coupons))
        for c in store_coupons[:5]:
            log("    • %s" % c.get("title", ""))
    else:
        log("  该门店当前无可用门店券")

    text, _ = mcp.call("available-coupons")
    save_raw("available-coupons", text)
    claimable = []
    if text:
        for m in re.finditer(r"优惠券标题：([^\\\n]+)", text):
            claimable.append(m.group(1).strip())
        claimable = [c for c in claimable if c]
        log("  麦麦省可领券 %d 张：%s" % (len(claimable), "、".join(claimable[:6]) +
                                         ("…" if len(claimable) > 6 else "")))
    report["coupons"] = {"store": len(store_coupons), "claimable": claimable[:10]}

    # ==================================================== 9. 生成产物
    plan = build_plan(args, server_now, events, ladder, stores, primary, points,
                      store_coupons, claimable, mcp, mode)
    return finish(report, mcp, args, out_dir, raw_dir, plan)


def build_plan(args, server_now, events, ladder, stores, primary, points,
               store_coupons, claimable, mcp, mode="实盘（真实 Token）"):
    """把真实数据组装成攻略卡渲染输入（与 render_collab_card.py 的 plan 格式一致）。"""
    add_price = (events[0]["add_price"] if events and events[0]["add_price"] else 39.9)
    is_fixture = mode.startswith("离线回放")
    collab = "麦当劳限定联名"
    for e in events:
        if "PEACEMINUSONE" in (e["title"] + e["desc"]):
            collab = "麦当劳 × PEACEMINUSONE"
            break

    windows = []
    for e in events[:3]:
        cd = fmt_countdown(e["sale_dt"] - server_now)
        windows.append({
            "item": e["name"],
            "time": e["sale_dt"].strftime("%m/%d %H:%M") + (" 已开售" if cd == "已开售" else " 开售"),
            "advance": (e["advance_dt"].strftime("%m/%d %H:%M") + " 积分抢先购") if e["advance_dt"] else "无抢先购",
            "countdown": cd if cd != "已开售" else "进行中",
        })

    # 每条周边的到手价：用「稳妥凑单」路径（可单独下单、已实算）作为标价依据
    safe = next((l for l in ladder if l["path"] == "稳妥凑单"), None)
    floor = next((l for l in ladder if l["path"] == "极限下限"), None)
    merch = []
    for e in events[:3]:
        basis = safe or floor
        merch.append({
            "item": e["name"],
            "mechanism": "%s %s + 换购 %.1f" % (
                basis["food"], basis["food_price"], add_price) if basis else "任意消费 + %.1f" % add_price,
            "best_price": ("¥%.2f" % (float(basis["food_price"][1:]) + add_price)) if basis else "—",
            "best": True,
        })
    if not any("小卡" in m["item"] for m in merch):
        merch.append({"item": "随单小卡（3 款随机）", "mechanism": "购买联名套餐随单得",
                      "best_price": "¥0", "best": False})

    # 渠道策略
    tips = []
    if stores:
        near = stores[0]
        tips.append("%s 为检索中心最近门店（%dm）：属核心商圈，首发日排队久、售罄快，建议错峰"
                    % (near["name"], round(near["distance"])))
        h24 = [s for s in stores if s["h24"]][:2]
        if h24:
            tips.append("就近 24 小时备选：%s" % "、".join(
                "%s %dm" % (s["name"], round(s["distance"])) for s in h24))
        tips.append("APP 内先确认库存再出发；到店 %s-%s 营业" % (primary["open"], primary["close"]))
    if points:
        tips.append("积分余额 %s，可留意 APP 积分抢先购窗口" % points)
    if not tips:
        tips = ["首发日避开核心商圈大店（痛店排队久、售罄快）",
                "优先查就近 3-5 家非热门门店，货量通常更充足"]

    # 攻略要点：锁定下一场未开售的周边
    playbook = []
    upcoming = [e for e in events if e["sale_dt"] > server_now]
    if upcoming:
        nxt = upcoming[0]
        playbook.append("定闹钟：%s 积分抢先购开抢，%s 全面开售" % (
            nxt["advance_dt"].strftime("%m/%d %H:%M") if nxt["advance_dt"] else "—",
            nxt["sale_dt"].strftime("%H:%M")))
    if safe:
        playbook.append("提前把「%s」加好购物车（%s），开售瞬间一键结算" % (safe["food"], safe["food_price"]))
    if claimable:
        playbook.append("下单前先领券：麦麦省当前可领 %d 张" % len(claimable))
    playbook.append("周边是消费品，喜欢再冲，别为凑单点多一份")

    return {
        "collab": collab,
        "nickname": args.nickname,
        "today": server_now.strftime("%Y-%m-%d"),
        "repo": REPO_LINE,
        "data_source": "麦当劳中国官方 MCP（mcd-mcp）%s · 门店：%s %s · %s · 本次演示调用 %d 个工具"
                       % ("录制数据回放" if is_fixture else "实时返回",
                          primary["name"], primary["code"],
                          server_now.strftime("%Y-%m-%d %H:%M"), len(mcp.calls)),
        "windows": windows,
        "merch": merch,
        "price_ladder": [{"path": l["path"], "food": l["food"], "food_price": l["food_price"],
                          "total": l["total"], "note": l["note"]} for l in ladder],
        "channel_tips": tips,
        "playbook": playbook,
    }


def finish(report, mcp, args, out_dir, raw_dir, plan):
    """输出报告 + 攻略卡，打印总结。"""
    ok_calls = [c for c in mcp.calls if c[1]]
    report["calls"] = [{"tool": t, "ok": ok, "note": n} for t, ok, n in mcp.calls]

    # ---- 攻略卡 ----
    card_path = None
    if plan and not args.no_card:
        plan_path = out_dir / "plan.json"
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        card_path = out_dir / "collab-card.html"
        try:
            sys.path.insert(0, str(SCRIPT_DIR))
            import render_collab_card
            card_path.write_text(render_collab_card.render(plan), encoding="utf-8")
            log("")
            log("  🎴 攻略卡已生成：%s" % card_path)
        except Exception as e:
            log("  ⚠️ 攻略卡渲染失败：%s" % e)
            card_path = None

    # ---- 报告 ----
    report_path = out_dir / "live-report.md"
    report_path.write_text(render_report(report, plan), encoding="utf-8")

    rule("演示总结")
    log("  调用工具：%d 次（成功 %d，降级 %d）" % (
        len(mcp.calls), len(ok_calls), len(mcp.calls) - len(ok_calls)))
    for t, ok, note in mcp.calls:
        log("    %s %s%s" % ("✅" if ok else "⚠️ ", t, "" if ok else "（%s）" % note))
    log("  产物目录：%s" % out_dir)
    log("    - live-report.md      演示报告（含全部结论与原始数据索引）")
    log("    - raw/*.json          每次工具调用的原始返回（可审计）")
    if plan:
        log("    - plan.json           攻略卡渲染输入")
    if card_path:
        log("    - collab-card.html    联名攻略卡（浏览器打开即可截图）")
    log("")
    log("  ⚠️ 合规提示：非麦当劳官方产品；周边为消费品，不建议囤积炒作；")
    log("     价格与活动以官方渠道实时信息为准。")
    log("=" * 74)
    return 0


def render_report(report, plan):
    L = []
    A = L.append
    A("# 麦麦联名雷达 · 实盘演示报告")
    A("")
    A("- 运行模式：**%s**" % report.get("mode"))
    A("- 运行时间：%s" % report.get("started_at"))
    A("- 服务端：%s v%s" % (report.get("server", {}).get("name", "mcd-mcp"),
                            report.get("server", {}).get("version", "?")))
    if report.get("server_time"):
        A("- 服务器时间：%s" % report["server_time"])
    A("- 工具调用：%d 次" % len(report.get("calls", [])))
    A("")
    A("> 本报告由 `scripts/live_demo.py` 自动生成，全部数据来自麦当劳中国官方 MCP（mcd-mcp）实时返回。")
    A("> 非麦当劳官方产品；周边为消费品，不建议囤积炒作；价格与活动以官方渠道实时信息为准。")
    A("")

    A("## 一、工具调用清单")
    A("")
    A("| 工具 | 结果 | 备注 |")
    A("|---|---|---|")
    for c in report.get("calls", []):
        A("| `%s` | %s | %s |" % (c["tool"], "✅ 成功" if c["ok"] else "⚠️ 降级", c["note"] or ""))
    A("")

    events = report.get("events", [])
    A("## 二、联名情报（冲浪窗口）")
    A("")
    if events:
        A("| 周边 | 开售时间 | 积分抢先购 | 换购机制 | 倒计时 |")
        A("|---|---|---|---|---|")
        for e in events:
            A("| %s | %s | %s | 任意消费 + %.1f 元 | %s |" % (
                e["name"], e["sale"], e["advance"] or "—", e["add_price"] or 39.9, e["countdown"]))
        A("")
        for e in events:
            A("- **%s**：%s" % (e["name"], e["desc"]))
        A("")
    else:
        A("当前日历未识别到联名周边活动（`campaign-calendar` 为活水源，新联名上线会自动纳入）。")
        A("")

    A("## 三、积分与商城核对")
    A("")
    if report.get("points"):
        A("- 可用积分：**%s**" % report["points"])
    A("- 结论：%s" % report.get("mall_conclusion", "未获取"))
    A("")

    ladder = report.get("ladder", [])
    A("## 四、价梯账（实算对比）")
    A("")
    if ladder:
        A("| 路径 | 凑单餐品 | 餐品价 | 换购 | 到手价 | 数据来源 |")
        A("|---|---|---|---|---|---|")
        for l in ladder:
            A("| %s | %s | %s | +%.1f | **%s** | %s |" % (
                l["path"], l["food"], l["food_price"], 39.9, l["total"], l["note"]))
        A("")
        best = min(ladder, key=lambda l: float(l["total"][1:]))
        A("**最优路径：%s（%s）**" % (best["path"], best["total"]))
        A("")
    else:
        A("价梯账未生成（菜单或算价调用失败）。")
        A("")

    stores = report.get("stores", [])
    A("## 五、渠道账（门店雷达）")
    A("")
    if stores:
        A("| 门店 | 距离 | 营业时间 | 备注 |")
        A("|---|---|---|---|")
        for s in stores[:8]:
            A("| %s（%s） | %dm | %s-%s | %s |" % (
                s["name"], s["code"], round(s["distance"]), s["open"], s["close"],
                "24 小时" if s["h24"] else ("" if s["status"] else "休息中")))
        A("")
    else:
        A("门店检索未返回数据。")
        A("")

    cp = report.get("coupons", {})
    A("## 六、券况")
    A("")
    A("- 门店可用券：%d 张" % cp.get("store", 0))
    if cp.get("claimable"):
        A("- 麦麦省可领：%s" % "、".join(cp["claimable"]))
    A("")

    if plan:
        A("## 七、攻略卡")
        A("")
        A("- 渲染输入：`demo/out/plan.json`")
        A("- 卡片产物：`demo/out/collab-card.html`（浏览器打开即可截图分享）")
        A("- 联名：%s" % plan.get("collab"))
        A("- 数据来源：%s" % plan.get("data_source"))
        A("")

    A("## 八、复现方式")
    A("")
    A("```bash")
    A("export MCD_MCP_TOKEN=\"你的Token\"")
    A("python3 scripts/live_demo.py --city 南京市 --keyword 新街口")
    A("python3 scripts/live_demo.py --dry-run   # 离线回放，无需 Token")
    A("```")
    A("")
    A("每次工具调用的原始返回都保存在 `demo/out/raw/*.json`，可逐条核对。")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())

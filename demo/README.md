# demo · 实盘演示

这个目录放「麦麦联名雷达」的**可复现实盘演示**：一条命令跑完「扫雷达 → 算三本账 → 出攻略卡」，全部数据来自麦当劳中国官方 MCP（mcd-mcp）实时返回。

## 快速开始

### 实盘模式（需要 MCP Token）

```bash
# 1. 设置 Token（仅从环境变量读取，绝不写入任何产物文件）
export MCD_MCP_TOKEN="你的MCP Token"

# 2. 跑演示（默认南京新街口）
python3 scripts/live_demo.py

# 3. 换个城市/商圈
python3 scripts/live_demo.py --city 上海市 --keyword 人民广场

# 4. 指定主门店
python3 scripts/live_demo.py --store 1990346
```

### 离线回放模式（无需 Token）

仓库内置了 `fixtures/raw/` 下录制的真实返回（账户 ID 已脱敏），评委和用户不申请 Token 也能完整体验：

```bash
python3 scripts/live_demo.py --dry-run
```

## 开售日现场演示

联名开售当天（如 GD × PEACEMINUSONE 徽章 **10/15 10:45**）可以定时起跑，抓第一手数据：

```bash
# 等到 10:40 积分抢先购窗口再跑
python3 scripts/live_demo.py --wait-until 10:40

# 等到 10:45 全面开售再跑，且只出报告不渲染卡片
python3 scripts/live_demo.py --wait-until 10:45 --no-card
```

## 命令行参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--token` | 环境变量 `MCD_MCP_TOKEN` | MCP Token（实盘模式必填） |
| `--dry-run` | — | 离线回放 `fixtures/raw/` 中的录制数据 |
| `--fixtures` | `demo/fixtures` | 回放数据目录 |
| `--out` | `demo/out` | 产物输出目录 |
| `--city` / `--keyword` | `南京市` / `新街口` | 门店检索范围 |
| `--store` | 检索结果中最近的一家 | 指定主门店 `storeCode` |
| `--nickname` | `GD 追更人` | 攻略卡上的昵称 |
| `--wait-until HH:MM` | — | 等到本地该时刻再起跑 |
| `--no-card` | — | 只出报告，不渲染攻略卡 |
| `--feed-hint` | `龙焰` | 饱腹路径的联名新品关键词 |

## 产物说明

每次运行会在 `demo/out/` 下生成：

```
demo/out/
├── live-report.md        # 演示报告：工具调用清单 / 联名情报 / 价梯实算 / 门店雷达 / 券况
├── plan.json             # 攻略卡渲染输入（与 render_collab_card.py 的 plan 格式一致）
├── collab-card.html      # 联名攻略卡（浏览器打开即可截图分享）
└── raw/                  # 每次工具调用的原始返回，可逐条核对
    ├── now-time-info.json
    ├── campaign-calendar.json
    ├── query-my-account.json
    ├── mall-points-products.json
    ├── query-nearby-stores.json
    ├── query-meals.json
    ├── calculate-price_<code>.json
    ├── query-store-coupons.json
    └── available-coupons.json
```

## 演示脚本做了什么

按 SKILL.md 的三步工作流编排，共调用 8 类工具：

| 步骤 | 工具 | 作用 |
|---|---|---|
| ① 服务器时间 | `now-time-info` | 校准时间，计算开售倒计时 |
| ② 活动雷达 | `campaign-calendar` | 解析联名周边弹次、开售时刻、积分抢先购、换购机制 |
| ③ 积分账户 | `query-my-account` | 可用积分余额 |
| ④ 商城核对 | `mall-points-products` | 验证周边是否在积分兑换列表（实测：不在） |
| ⑤ 门店雷达 | `query-nearby-stores` | 附近门店 + 距离 + 营业时间 + 痛店/冷店策略 |
| ⑥ 菜单 | `query-meals` | 找凑单下限（实测最便宜可下单项 ¥3 蘸酱 / ¥5 圆筒） |
| ⑦ 价格实算 | `calculate-price` ×4 | 四条路径逐条实算，禁止用菜单价冒充实算价 |
| ⑧ 券况 | `query-store-coupons` + `available-coupons` | 门店券与麦麦省可领券 |

## 设计原则

- **纯标准库零依赖**：只用 Python 3 标准库，克隆即可跑
- **价格必须实算**：每条价梯路径都调用 `calculate-price`，拿不到实算结果会明确标注「菜单价」
- **失败降级不中断**：单个工具失败只跳过该步并在报告里标注，不会让整个演示崩掉
- **Token 不进产物**：Token 只从环境变量/命令行读取，`raw/` 里保存的是 API 返回而非请求
- **温和调用**：每次调用间隔 250ms，远离 600 次/分钟的限流

## 更新回放数据

实盘跑完后想刷新 `fixtures/`：

```bash
python3 scripts/live_demo.py                # 先实跑一次，产出 demo/out/raw/
cp demo/out/raw/*.json demo/fixtures/raw/   # 复制为回放数据
```

> 复制前建议确认 `query-my-account.json` 里的账户 ID 已脱敏。

## 合规提示

- 本项目为非麦当劳官方产品，演示数据仅用于技术验证
- 周边为消费品，不建议囤积炒作
- 价格与活动信息以官方渠道实时信息为准

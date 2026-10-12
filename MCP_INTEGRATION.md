# MCP 接入说明 · MCP_INTEGRATION

本项目基于**麦当劳中国官方 MCP Server**（`mcd-mcp`）开发，以下说明实际使用的 Server、Tool、调用流程与业务价值。

## 一、MCP Server 信息

| 项 | 值 |
|---|---|
| Server 名称 | `mcd-mcp`（麦当劳中国官方远程托管） |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 鉴权方式 | `Authorization: Bearer <MCD_MCP_TOKEN>` |
| Token 申请 | https://open.mcd.cn/mcp （手机号登录 → 控制台 → 激活） |
| 限流 | 600 次/分钟（超限返回 429） |
| 官方仓库 | https://github.com/M-China/mcd-mcp-server |

脱敏配置见 [`mcp-config.example.json`](./mcp-config.example.json)（仅环境变量占位符，不含任何真实凭据）。

## 二、使用的 Tool 清单（共 15 个）

| # | Tool | 用途 | 调用时机（工作流步骤） |
|---|---|---|---|
| 1 | `now-time-info` | 校准当前时间，计算开售倒计时 | 第 1 步 扫雷达 |
| 2 | `campaign-calendar` | 当月营销活动日历（联名/限定/上新/开售时刻） | 第 1 步 扫雷达（核心数据源） |
| 3 | `mall-points-products` | 麦麦商城周边商品（积分兑换/加购） | 第 1 步 扫雷达 |
| 4 | `mall-product-detail` | 周边商品详情（价格/有效期/说明） | 第 1 步 扫雷达 |
| 5 | `query-lottery-info` | 积分抽奖活动信息（联名配套抽奖） | 第 1 步 扫雷达 |
| 6 | `query-nearby-stores` | 按位置查附近麦当劳餐厅 | 第 2 步 账③ 渠道 |
| 7 | `query-meals` | 门店在售菜单（联名套餐/凑单餐品） | 第 2 步 账② 价梯 |
| 8 | `query-meal-detail` | 餐品详情：套餐组成、换配与特制选项 | 第 2 步 账② 价梯 |
| 9 | `calculate-price` | 按选购商品+优惠券计算应付金额 | 第 2 步 账② 价梯（所有价格必经此工具） |
| 10 | `query-store-coupons` | 当前门店可用优惠券 | 第 2 步 账②/账③ |
| 11 | `available-coupons` | 麦麦省可领取的优惠券列表 | 第 2 步 账② 价梯 |
| 12 | `auto-bind-coupons` | 一键领取当前全部可领优惠券 | 第 2 步 账② 价梯 |
| 13 | `query-my-account` | 积分账户余额（抵扣/抢先购能力评估） | 第 2 步 账② 价梯 |
| 14 | `query-my-prizes` | 抽奖奖品记录 | 复盘 |
| 15 | `order-list` | 历史订单（联名周边到手清单/花费复盘） | 复盘 |

## 三、调用流程

```
┌─────────────────────────────────────────────────────────────┐
│ 第1步 扫雷达（联名情报）                                      │
│   now-time-info ──────▶ 校准时间 / 倒计时                     │
│   campaign-calendar ──▶ 联名/限定/上新活动 + 开售时刻 ★核心    │
│   mall-points-products / mall-product-detail ▶ 商城周边        │
│   query-lottery-info ─▶ 配套抽奖活动                          │
├─────────────────────────────────────────────────────────────┤
│ 第2步 算三本账                                               │
│   账① 窗口：campaign-calendar 时间轴 + 倒计时 + 行动建议       │
│   账② 价梯：query-meals → query-meal-detail → calculate-price │
│            + query-store-coupons / available-coupons /        │
│              auto-bind-coupons + query-my-account（积分路径）  │
│   账③ 渠道：query-nearby-stores → 附近门店雷达 + 痛店/冷店策略  │
├─────────────────────────────────────────────────────────────┤
│ 第3步 出攻略卡                                               │
│   scripts/render_collab_card.py ──▶ 小红书风 HTML 攻略卡       │
├─────────────────────────────────────────────────────────────┤
│ 复盘（可选）                                                  │
│   order-list / query-my-prizes ──▶ 到手清单 + 花费复盘         │
└─────────────────────────────────────────────────────────────┘
```

典型一次完整规划（以"GD 联名徽章怎么买最划算"为例）：

```
now-time-info → campaign-calendar → mall-points-products →
query-nearby-stores → query-meals → query-meal-detail →
available-coupons → auto-bind-coupons → query-my-account →
calculate-price（换购路径 vs 加购路径 vs 麦金卡路径）→ render_collab_card.py
```

## 四、业务价值

| 价值点 | 说明 |
|---|---|
| **把信息差变成攻略** | 联名周边"抢破头 vs 没人买"并存的根源是信息差；雷达把官方的开售时刻、购买机制、附近门店一次性算清，让用户 3 秒做决策 |
| **价格路径透明可比** | 每条周边给出「换购/加购/麦金卡/积分」多路径实付对比，全部来自 `calculate-price` 实时计算，不靠经验拍脑袋 |
| **时间窗口不错过** | 自动提取开售与积分抢先购时刻并生成倒计时，把"刷到才知道"变成"定好闹钟" |
| **可持续适配** | 不绑定某一次联名——`campaign-calendar` 是活水源，新联名上线即自动纳入雷达 |
| **自传播闭环** | 攻略卡自带项目地址，用户截图分享即为项目带来 Star，形成"分享 → 使用 → Star"闭环 |

## 五、安全与合规

- 本项目**真实调用**麦当劳中国官方 MCP Server，未做任何中间层代理或数据篡改
- 配置文件仅使用环境变量占位符 `${MCD_MCP_TOKEN}`（见 `mcp-config.example.json`）
- 严格遵守 MCP 服务规则：限 600 次/分钟，错误码 401（Token 失效）/429（限流）均有降级处理
- 只规划官方渠道自用购买路径：不提供代抢、黄牛、二手交易建议，不构成投资建议
- 项目为参赛者独立开发的非官方作品，不构成麦当劳官方产品，不提及其他品牌

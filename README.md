# 📡 麦麦联名雷达 · mcd-collab-radar

> **联名可以冲，账要先算清。**
> 麦当劳限定联名的抢购参谋——把「窗口、价梯、渠道」三本账算明白，再甩你一张能晒的攻略卡。

当下最典型的场景：**麦当劳 × PEACEMINUSONE（G-DRAGON）联名**——韩式新品 + 周边多弹发售（小卡 → 徽章 → 丝巾）。输入你在追的联名，它还你一张结构化情报表 + 一张可截图分享的攻略卡。

🏷️ **麦当劳程序员创意开发大赛**参赛作品 · 基于麦当劳中国官方 MCP（mcd-mcp）开发 · 使用 WorkBuddy 辅助开发
⚠️ 本项目为参赛者独立开发的**非麦当劳官方产品**，输出仅供参考；周边为消费品，不建议囤积炒作。

---

## ✨ 解决什么问题

联名周边开售那天，小红书上一半人在喊"抢破头"，一半人在喊"没人买"——**信息差才是真正的成本**。麦麦联名雷达用 MCP 实时数据，把一次联名抢购拆成三个可执行的问题：

| 账本 | 回答什么问题 | 数据来自 |
|---|---|---|
| ⏰ **窗口** | 什么时候冲？开售/积分抢先购时刻、倒计时 | `campaign-calendar` 实时活动日历 |
| 💰 **价梯** | 怎么买最便宜？换购/加购/麦金卡/积分，哪条路径到手价最低 | `query-meals` + `calculate-price` + 券 + 积分 |
| 📍 **渠道** | 去哪买？附近门店雷达 + 痛店/冷店错位策略 | `query-nearby-stores` + 门店券对比 |

最后生成一张**小红书风攻略卡**，截图就能发——手慢的人，连攻略都是借来的。

## 👤 目标用户

- **追限定周边的粉丝/潮人**：K-pop 粉丝、潮玩收集者（当下：GD 联名三连弹）
- **羊毛党**：想用最低成本拿到周边的精明消费者
- **选择困难户**：面对"换购 or 加购、哪家店、要不要定闹钟"不想做功课的人

## 🚀 安装与使用

### 前置条件

1. 支持 MCP 的客户端（推荐 **WorkBuddy**，本项目即在其上开发）
2. 麦当劳中国 MCP Token：[https://open.mcd.cn/mcp](https://open.mcd.cn/mcp) → 手机号登录 → 控制台 → 激活 → 复制

### 第一步：配置麦当劳 MCP

复制 [`mcp-config.example.json`](./mcp-config.example.json)，把 `${MCD_MCP_TOKEN}` 替换为真实 Token（或用环境变量注入）：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer ${MCD_MCP_TOKEN}"
      }
    }
  }
}
```

### 第二步：加载 Skill

将本仓库的 `SKILL.md` 及 `references/`、`scripts/` 作为 Skill 加载到 WorkBuddy（或任何支持 Agent Skill 的客户端）。

### 第三步：开始对话

```
现在麦当劳有什么联名？周边都什么时候开售，怎么买最划算？
```

或：

```
我在追 GD 联名，帮我算算徽章和丝巾的最优购买路径，我在北京五道口
```

Skill 会自动完成：扫雷达 → 算三本账 → 出攻略卡。

## 📁 项目结构

```
mcd-collab-radar/
├── SKILL.md                        # Skill 主体：三步工作流（扫雷→算账→出卡）
├── references/
│   ├── workflow.md                 # 三步工作流详解与话术
│   ├── price-ladder.md             # 价梯计算规则（联名周边购买机制拆解）
│   └── collab-playbook.md          # 联名玩法与攻略卡内容规范
├── scripts/
│   └── render_collab_card.py       # 联名攻略卡渲染器（纯标准库零依赖）
├── demo/
│   └── sample-card.html            # 示例攻略卡（浏览器打开即可截图）
├── MCP_INTEGRATION.md              # MCP 接入说明（Server/Tool/流程/价值）
├── mcp-config.example.json         # 脱敏 MCP 配置示例（仅环境变量占位符）
├── CONTEST_DECLARATION.md          # 参赛声明（官方模板原文）
├── workbuddy.md                    # WorkBuddy 开发对话上下文
└── README.md
```

## 🧩 使用的麦当劳 MCP 工具

共 15 个：`campaign-calendar`、`now-time-info`、`mall-points-products`、`mall-product-detail`、`query-lottery-info`、`query-nearby-stores`、`query-meals`、`query-meal-detail`、`calculate-price`、`query-store-coupons`、`available-coupons`、`auto-bind-coupons`、`query-my-account`、`query-my-prizes`、`order-list`

详细调用流程与业务价值见 [MCP_INTEGRATION.md](./MCP_INTEGRATION.md)。

## 🔒 安全与边界

- **不代抢、不碰二手**：只规划本人在官方渠道的自用购买路径，不做任何投资/炒作建议
- 领券等写操作必须经用户明确确认；配置**仅用环境变量占位符**，仓库不含任何真实 Token
- 活动、价格、优惠一律以 MCP 实时返回为准，不编造
- 本项目为非麦当劳官方产品，不提及其他品牌

## 🏆 参赛信息

- **赛事**：麦当劳程序员创意开发大赛（1024 程序员节专项）
- **赛事仓库**：https://github.com/M-China/mcd-developer-innovation-challenge
- **开发工具**：WorkBuddy（官方合作伙伴），对话上下文见 [workbuddy.md](./workbuddy.md)

## 📄 License

MIT

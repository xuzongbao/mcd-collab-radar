# workbuddy.md · WorkBuddy 开发对话上下文

> 本文件记录「麦麦联名雷达」在**腾讯 WorkBuddy 智能体**中的真实开发过程，用于麦当劳程序员创意开发大赛 **WorkBuddy 专项奖励**联动。
> 项目确由 WorkBuddy 辅助开发：需求拆解、赛事规则研究、竞品分析、Skill 编排、渲染器编码、MCP 联调、文档撰写均在 WorkBuddy 对话中完成。

---

## 一、开发环境

| 项 | 内容 |
|---|---|
| 智能体平台 | 腾讯 WorkBuddy（Agent 模式） |
| 工作区 | `/Users/xuzongbao/WorkBuddy/麦当劳/` |
| 项目目录 | `mcd-collab-radar/` |
| MCP 客户端 | WorkBuddy 自定义连接器（Streamable HTTP + Bearer Token） |
| 开发周期 | 2026-10-11 ~ 2026-10-13（3 天） |
| 参赛者 GitHub | xuzongbao |

---

## 二、对话推进主线（真实时间线）

### Day 1（10-11）· MCP 对接

**用户**："我有一个麦当劳的 MCP，在 workbuddy 中怎么对接呢？"

- WorkBuddy 抓取官方仓库 `M-China/mcd-mcp-server`，确认接入方式：Streamable HTTP、`https://mcp.mcd.cn`、`Authorization: Bearer <Token>`
- 用户提供 Token，WorkBuddy 将其合并进 `~/.workbuddy/mcp.json`（保留原有 3 个 tokenbank 配置），JSON 校验通过
- 指导用户在连接器页面点"信任/启用"

### Day 2（10-12）· 连通性验证 + 赛事研究 + 首个方案

**用户**："好的"（要求验证连通性）

- WorkBuddy 直接发 MCP `initialize` 握手 → HTTP 200，`serverInfo: mcd-mcp v1.0.0`
- 拉取 `tools/list` → 返回 **35 个工具**，逐一解析并按场景分组（点餐/配送/门店/积分券/活动/商城/派对/抽奖/订单/营养/时间）

**用户**："我在参考 mcd 的一个小比赛……后续我们一起来完成。"

- WorkBuddy 抓取 `M-China/mcd-developer-innovation-challenge` 的 README、`activityGuidelines.md`、`CONTEST_DECLARATION.md`、`RANKING.md`
- 梳理出：赛程（报名截止 10-25 23:59，定榜 10-26）、必交 6 项文件、纯 Star 排名、前 100 入榜、WorkBuddy 专项 3000 积分
- 分析竞争态势：500+ 报名、入榜门槛约 5~15 Star、前三 183/142/110 Star；省钱/优惠券/热量/积分/运势/人格/图鉴/点单/账单赛道全部拥挤
- 提出差异化假设：开发者爱 Star 懂梗的项目 + 可分享物料 + 用户自有分发渠道

**首个方案：麦麦冲刺补给站**（学生冲刺场景）
- WorkBuddy 搭建完整仓库骨架：`SKILL.md` 四步工作流 + 3 份 references + 卡片渲染器 + 全套参赛文件
- 渲染器跑通，产出示例补给卡

### Day 3（10-13）· 热点转向 + 落地 + 发布

**用户**："不不不，我感觉这个方案有点不太行，现在的热点也不在考公、期末、考研、考证等，是否可以结合一些当前的热点进行场景化"

- WorkBuddy 双向取数：一边调 `mcp__mcd-mcp__campaign-calendar` 拿麦当劳官方**此刻在推的活动**，一边全网搜热点
- **挖到金矿**：麦当劳中国头号热点是 **G-DRAGON（权志龙）× PEACEMINUSONE 联名**——预售破亿、周边三连弹（小卡→徽章 10/15→丝巾 10/22，全在赛期内）
- 交叉验证热度：官方微博 1339 条评论、新加坡门店拉闸、小红书热帖 234 条评论吵"抢破头 vs 没人买"
- 从高热攻略文提炼出用户真痛点："**三本账**"——价梯（怎么买最便宜）、渠道（哪家店有货）、窗口（什么时候开售）
- 发现这三本账**恰好能全部用 MCP 工具算出来** → 数据驱动的真需求，而非硬编场景

**转向方案：麦麦联名雷达**
- 重构项目：保留仓库骨架/渲染器/参赛文件，重写 SKILL 与三份 references
- 三步工作流：**扫雷达 → 算三本账 → 出攻略卡**
- MCP 编排从 13 个工具扩展到 **15 个**，核心是 `campaign-calendar` 作为活水源（不绑死单次联名，未来新联名自动纳入）
- 攻略卡渲染器重写为联名版，跑通产出示例卡

**发布阶段**
- 用户完成 GitHub 授权后，WorkBuddy 推送全部代码至 `xuzongbao/mcd-collab-radar`（11 文件 / 969 行 / 45 KB）
- 校验 `CONTEST_DECLARATION.md` 与官方原文**逐字节一致**（1522 B，diff 无差异）

---

## 三、WorkBuddy 实际调用的麦当劳 MCP 工具

| 工具 | 调用时机 | 返回 |
|---|---|---|
| `initialize` | Day 2 连通性验证 | HTTP 200，`serverInfo: mcd-mcp v1.0.0` |
| `tools/list` | Day 2 工具盘点 | 35 个工具全量清单 |
| `campaign-calendar` | Day 3 热点挖掘 | 定位到 GD × PEACEMINUSONE 联名 + 周边三连弹日历 |

> 上述调用均通过 WorkBuddy 内置 MCP 连接器完成，非外部脚本代理。

---

## 四、关键决策记录

| 决策点 | 选择 | 理由 |
|---|---|---|
| 场景方向 | 从"学生冲刺补给站"转向"联名雷达" | 用户指出热点不匹配；`campaign-calendar` 实时数据证明联名是当下最大浪 |
| 是否绑死单次联名 | 不绑定，`campaign-calendar` 作活水源 | 赛事横跨 10-09~10-25，期间徽章/丝巾两个爆点，且未来联名可持续复用 |
| 价格数据来源 | 全部必经 `calculate-price`，禁止估算 | 攻略类项目公信力的根基 |
| 输出形态 | 小红书风 HTML 攻略卡 | 用户自有小红书渠道，卡片可自传播反哺 Star |
| 合规边界 | 不代抢/不碰二手/不做投资建议 | 赛事红线 + 周边属消费品，不建议囤积炒作 |

---

## 五、产出物清单

```
mcd-collab-radar/
├── SKILL.md                        # 三步工作流 + 三张单规则 + 合规硬约束 + 降级策略
├── references/
│   ├── workflow.md                 # 三步工作流详解与话术
│   ├── price-ladder.md             # 价梯计算规则（联名周边购买机制拆解）
│   └── collab-playbook.md          # 联名玩法与攻略卡内容规范
├── scripts/
│   └── render_collab_card.py       # 攻略卡渲染器（纯标准库零依赖）
├── demo/
│   └── sample-card.html            # 示例攻略卡
├── MCP_INTEGRATION.md              # 15 个 mcd-mcp 工具的调用流程与业务价值
├── mcp-config.example.json         # 脱敏配置（仅 ${MCD_MCP_TOKEN} 占位符）
├── CONTEST_DECLARATION.md          # 官方参赛声明原文（一字未改）
├── workbuddy.md                    # 本文件
└── README.md
```

---

## 六、合规自查

- [x] 仓库不含任何真实 Token / 密钥（`mcp-config.example.json` 仅环境变量占位符）
- [x] `CONTEST_DECLARATION.md` 为官方原文，未做任何修改
- [x] 项目为参赛者独立开发的**非麦当劳官方产品**，输出已标注
- [x] 未在项目任何位置提及、对比其他餐饮品牌
- [x] 不提供代抢、黄牛、二手交易建议，不构成投资建议
- [x] 项目原创，未盗用他人代码或麦当劳官方素材

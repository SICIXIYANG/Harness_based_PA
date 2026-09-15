---
name: polymarket-stops
description: 为 Polymarket 交易设置硬止损、追踪止损和组合止损，防止无原生止损功能导致的超额亏损，适用于已持仓但缺乏风控的场景。
---

### 适用场景
- Polymarket（及 Hyperliquid）上已有已成交仓位，但平台不支持 STOP/TRAILING_STOP 等原生风控指令；
- 已部署 polyclaw、Gina、@mvanhorn/polymarket 等仅负责下单的技能，需配套外部风控；
- 需统一执行日亏损上限、单仓最大敞口、组合清仓（flatten all）等策略性退出规则；
- 多代理协同环境，依赖 trust heartbeat 实现跨 Agent 风控状态同步。

### 标准流程
1. **安装与初始化**：运行 `clawhub install agent-guard`，进入 `skills/agent-guard/scripts` 目录执行 `npm install`，再用 `npx @hypelens/hypelens-agent-guard@0.1.18 setup --wallet 0x…` 绑定资助钱包；
2. **配置风控策略**：调用 `guard_set_policy` 或 `set_exit_rules` 设置硬止损百分比、追踪止损偏移、日亏损阈值、组合杀伤开关等参数；启用 `exits.dryRun:false` 切换至实盘执行模式；
3. **启动守护服务**：运行 `npx @hypelens/hypelens-agent-guard@0.1.18 watcher`（或 Docker Compose 启动），持续监听链上仓位与行情数据，自动触发退出逻辑，并通过 `guard_heartbeat` 输出可信状态供其他 Agent 读取。

### 注意事项
- 严禁用于下单/开仓环节——该技能仅作“事后风控”，开仓应使用 `polymarket-place` 或 `pm-desk`；
- 必须确保 `AGENT_GUARD_EXIT_PK` 和 `AGENT_GUARD_HL_PK` 环境变量正确配置，否则无法执行真实平仓；
- 启用 `AGENT_GUARD_EXIT_ON_BREACH=1` 后，首次触发风控将立即终止进程（exit 10），需配合 fail-closed 编排策略；
- 所有策略均基于链上清算数据与 Data API 的“chain-truth”，不依赖 LLM 决策，避免模型幻觉导致风控失效。
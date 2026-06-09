# AI 提示词与输出校验设计

本文档记录 AI 决策层的输入字段、提示词模板、输出 JSON 格式和校验规则。

## 1. AI 层职责

AI 层不直接替代数学优化器，也不允许只输出文字解释。它的职责是读取 SPO 候选组合、ETF 单体风险收益指标和风险偏好约束，生成低风险、中风险、高风险三档 ETF 权重建议，并说明配置理由。

所有 AI 输出必须由程序复核：

1. 权重和是否为 1；
2. 是否存在负权重；
3. 是否超过单只 ETF 权重上限；
4. 年化波动率是否满足风险档位约束；
5. 风险和收益指标是否可由数据重新计算；
6. 若校验失败，重新提示或回退到程序化优化器结果。

## 2. 输入字段

当前脚本会把完整提示词载荷输出到：

```text
outputs/tables/ai_prompt_payload.json
```

该文件包含 system prompt、user prompt 模板、结构化输入、目标 JSON schema 和已通过校验的参考输出，可直接作为后续接入外部大模型 API 的输入基础。

### 2.1 SPO 候选组合

来源：

```text
outputs/tables/spo_candidate_portfolios.csv
```

字段：

| 字段 | 含义 |
|---|---|
| `date` | 调仓日期 |
| `candidate_strategy` | 候选策略名称 |
| `expected_annual_return` | 候选组合预期年化收益 |
| `expected_annual_volatility` | 候选组合预期年化波动率 |
| `actual_future_return_21d` | 未来 21 日实际收益，用于回测评价 |
| `spo_weighted_decision_score` | 按权重加总的 SPO 决策分数 |
| `max_single_weight` | 候选组合最大单资产权重 |
| `dominant_etf` | 权重最高的 ETF |
| `turnover` | 相比上月的换手率 |
| `weights_json` | 候选组合权重 |

### 2.2 ETF 单体风险收益表

来源：

```text
outputs/tables/etf_risk_return_metrics.csv
```

字段：

| 字段 | 含义 |
|---|---|
| `ticker` | ETF 代码 |
| `expected_return_21d_pto` | PtO 模型预测未来 21 日收益 |
| `spo_decision_score` | SPO+ 决策分数 |
| `spo_predicted_rank` | SPO+ 预测排名 |
| `historical_annual_return` | 历史年化收益 |
| `annual_volatility` | 年化波动率 |
| `max_drawdown` | 最大回撤 |
| `sharpe` | 夏普比率 |
| `momentum_21d` | 近 21 日动量 |
| `momentum_60d` | 近 60 日动量 |
| `momentum_120d` | 近 120 日动量 |
| `downside_volatility` | 下行波动率 |

### 2.3 风险档位

| 档位 | 年化波动率上限 | 单只 ETF 权重上限 | 目标 |
|---|---:|---:|---|
| 低风险 | 10% | 35% | 风险可控前提下最大化收益 |
| 中风险 | 15% | 45% | 平衡收益和波动 |
| 高风险 | 22% | 60% | 接受更高波动以追求更高收益 |

## 3. 提示词模板

```text
你是投资组合优化助手。请基于以下结构化数据，为 6 只 ETF 生成低风险、中风险、高风险三档组合。

项目背景：
- 本项目是课程案例研究，不构成投资建议。
- 资产池为 SPY、QQQ、TLT、GLD、VNQ、DBC。
- 主算法采用 Smart Predict--then--Optimize, SPO。
- SPO 候选组合已经由程序生成，ETF 单体风险收益指标已经由程序计算。

决策目标：
- 每个风险档位都要在风险约束可控前提下最大化预期收益。
- 必须输出 ETF 权重、预期收益、预期波动、最大回撤风险说明和配置理由。
- 权重必须非负，权重和必须为 1。
- 不允许输出没有数据支撑的主观判断。

风险档位：
1. 低风险：年化波动率不超过 10%，单只 ETF 权重不超过 35%。
2. 中风险：年化波动率不超过 15%，单只 ETF 权重不超过 45%。
3. 高风险：年化波动率不超过 22%，单只 ETF 权重不超过 60%。

输入数据：
SPO 候选组合：
{{spo_candidate_portfolios}}

ETF 单体风险收益表：
{{etf_risk_return_metrics}}

当前市场特征摘要：
{{market_feature_summary}}

输出要求：
- 只能输出 JSON。
- JSON 必须符合给定 schema。
- 如果某个风险档位不可行，使用该档位下可行的最低风险组合，并在 risk_note 中说明。
```

## 4. 输出 JSON Schema

```json
{
  "generated_at_utc": "string",
  "decision_date": "YYYY-MM-DD",
  "ai_generation_mode": "string",
  "source_files": ["string"],
  "risk_profiles": [
    {
      "profile": "low_risk | medium_risk | high_risk",
      "profile_label": "低风险 | 中风险 | 高风险",
      "objective": "string",
      "constraints": {
        "annual_volatility_max": 0.1,
        "single_etf_weight_max": 0.35,
        "long_only": true,
        "weight_sum": 1.0
      },
      "weights": {
        "SPY": 0.0,
        "QQQ": 0.0,
        "TLT": 0.0,
        "GLD": 0.0,
        "VNQ": 0.0,
        "DBC": 0.0
      },
      "expected_annual_return": 0.0,
      "expected_annual_volatility": 0.0,
      "expected_sharpe": 0.0,
      "historical_risk_check": {
        "historical_annual_return": 0.0,
        "historical_annual_volatility": 0.0,
        "historical_sharpe": 0.0,
        "historical_max_drawdown": 0.0
      },
      "constraint_validation": {
        "weight_sum_ok": true,
        "long_only_ok": true,
        "single_etf_cap_ok": true,
        "volatility_cap_ok": true,
        "fallback_reason": "string"
      },
      "risk_note": "string",
      "allocation_reason": "string"
    }
  ],
  "validation_policy": "string",
  "disclaimer": "本项目仅用于课程案例研究，不构成任何投资建议。"
}
```

## 5. 程序化校验规则

校验逻辑在 `src/generate_ai_risk_profiles.py` 中实现。

| 校验项 | 规则 |
|---|---|
| 权重和 | `abs(sum(weights) - 1) <= 1e-6` |
| 非负权重 | `min(weights) >= 0` |
| 单只 ETF 上限 | 不超过该档位的 `single_etf_weight_max` |
| 年化波动率 | 使用调仓日前 252 个交易日协方差矩阵复算 |
| 回测收益 | 使用未来 21 日真实收益，只用于事后评估 |
| 交易成本 | 净收益按换手率扣除 `0.005` 比例成本 |
| 不可行处理 | 若某档位波动率约束不可完全满足，回退到该档位权重上限下的最低波动组合并记录 `fallback_to_minimum_volatility` |

校验结果输出到：

```text
outputs/tables/ai_risk_profile_validation.json
```

提示词载荷输出到：

```text
outputs/tables/ai_prompt_payload.json
```

校验汇总字段中，`ai_risk_constraints_all_met` 表示所有历史调仓月都完全满足波动率上限；`ai_risk_constraints_or_fallbacks_ok` 表示未完全满足的月份也已按规则回退并标注。

## 6. 当前实现说明

当前本地实现没有绑定外部大模型 API，因此采用“结构化提示词决策 + 程序化优化器兜底”的方式生成 JSON。这样做的原因是课程复现必须可重复运行：即使没有 API key，也能根据同一批 SPO 输出和风险约束得到同一批组合权重。

如果后续接入外部大模型，只需要替换 `src/generate_ai_risk_profiles.py` 中的决策生成部分；校验器和回退逻辑应保持不变。

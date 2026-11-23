"""内置规则引擎 AI 洞察。

不依赖任何外部大模型 / API Key，断网也能稳定产出针对当前数据集的
中文异常诊断与运营建议，面试演示零风险。
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


def _pct(part: float, total: float) -> float:
    return (part / total * 100.0) if total else 0.0


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _quality_insight(metrics: dict) -> Optional[dict]:
    repaired = int(metrics.get("repaired_count", 0))
    if repaired <= 0:
        return None

    missing_filled = int(metrics.get("missing_filled", 0))
    anomalies_fixed = int(metrics.get("anomalies_fixed", 0))
    format_normalized = int(metrics.get("format_normalized", 0))
    duplicate_removed = int(metrics.get("duplicate_removed", 0))
    remaining = int(metrics.get("remaining_issue_cells", 0))

    level = "critical" if anomalies_fixed >= 5 else "warning"
    return {
        "id": "quality",
        "level": level,
        "title": "数据质量诊断",
        "finding": (
            f"本次共处理 {repaired} 处数据问题：缺失填充 {missing_filled} 处、"
            f"异常修正 {anomalies_fixed} 处、格式标准化 {format_normalized} 处，"
            f"并移除 {duplicate_removed} 条完全重复记录；清洗后剩余问题单元格 {remaining} 个。"
        ),
        "suggestion": (
            "建议在数据接入层增加字段级校验（金额非负、在线时长上限、日期格式），"
            "并对因缺失被填充为 Unknown / UNKNOWN / 中位数的记录做二次复核，避免污染后续 BI 指标。"
        ),
        "metric": {"label": "累计修复", "value": f"{repaired} 处"},
    }


def _market_insight(dataframe: pd.DataFrame) -> dict:
    total_revenue = float(dataframe["iap_amount"].sum())
    grouped = (
        dataframe.groupby("country")
        .agg(
            players=("player_id", "size"),
            revenue=("iap_amount", "sum"),
            avg_session=("session_duration", "mean"),
        )
        .sort_values("revenue", ascending=False)
    )
    top_country = str(grouped.index[0]) if len(grouped) else "Unknown"
    top_players = int(grouped.iloc[0]["players"]) if len(grouped) else 0
    top_avg_session = float(grouped.iloc[0]["avg_session"]) if len(grouped) else 0.0

    if total_revenue > 0:
        top_revenue = float(grouped.iloc[0]["revenue"])
        share = _pct(top_revenue, total_revenue)
        concentration = "偏高" if share >= 55 else "相对分散"
        level = "critical" if share >= 65 else "opportunity"
        finding = (
            f"流水最高的市场为 {top_country}：{top_players} 名玩家贡献 {_money(top_revenue)}，"
            f"占样本总流水 {share:.1f}%，市场集中度{concentration}；"
            f"该市场人均在线 {top_avg_session:.0f} 分钟。"
        )
        suggestion = (
            f"建议围绕 {top_country} 做首充礼包与本地化活动的 A/B 测试，同时监控头部市场收入占比，"
            "提前孵化第二增长市场以分散单一市场波动风险。"
        )
        metric = {"label": "Top 市场流水占比", "value": f"{top_country} · {share:.1f}%"}
    else:
        level = "warning"
        finding = (
            f"当前 {len(dataframe)} 名样本玩家暂无内购流水，活跃度最高的市场为 {top_country}"
            f"（{top_players} 人，人均在线 {top_avg_session:.0f} 分钟）。"
        )
        suggestion = (
            "建议先上线低价首充礼包与限时新手活动验证付费意愿，再按国家拆分测试不同定价档位，"
            "同时补齐付费埋点以定位转化漏斗断点。"
        )
        metric = {"label": "样本总流水", "value": "$0.00"}

    return {
        "id": "market",
        "level": level,
        "title": "核心市场流水洞察",
        "finding": finding,
        "suggestion": suggestion,
        "metric": metric,
    }


def _payer_insight(dataframe: pd.DataFrame) -> dict:
    paying = dataframe[dataframe["iap_amount"] > 0]
    total_players = len(dataframe)
    if paying.empty:
        return {
            "id": "payer",
            "level": "critical",
            "title": "付费转化预警",
            "finding": f"本次 {total_players} 名样本玩家中付费玩家为 0，内购转化率 0.0%，暂无鲸鱼玩家沉淀。",
            "suggestion": "建议检查支付 SDK 与埋点是否正常上报，并上线 0.99 美元首充档位降低首付门槛，观察 7 日复购率。",
            "metric": {"label": "付费玩家", "value": "0 人"},
        }

    paying_revenue = float(paying["iap_amount"].sum())
    payer_ratio = _pct(len(paying), total_players)
    arppu = paying_revenue / len(paying)
    top_count = max(1, int(round(len(paying) * 0.2)))
    top_revenue = float(paying["iap_amount"].sort_values(ascending=False).head(top_count).sum())
    top_share = _pct(top_revenue, paying_revenue)
    level = "warning" if top_share >= 70 else "opportunity"

    finding = (
        f"付费玩家 {len(paying)} 人（占比 {payer_ratio:.1f}%），ARPPU 为 {_money(arppu)}；"
        f"金额最高的 Top {top_count} 名玩家贡献 {top_share:.1f}% 的付费流水，"
        f"鲸鱼依赖度{'偏高' if top_share >= 70 else '健康'}。"
    )
    suggestion = (
        "建议为高价值玩家设计专属礼包与客服通道稳住 ARPPU，同时用 6 元档限时礼包扩大中间层付费人数，"
        "降低对少数鲸鱼玩家的收入依赖。"
    )
    return {
        "id": "payer",
        "level": level,
        "title": "付费结构与鲸鱼玩家",
        "finding": finding,
        "suggestion": suggestion,
        "metric": {"label": f"Top {top_count} 玩家流水贡献", "value": f"{top_share:.1f}%"},
    }


def _engagement_insight(dataframe: pd.DataFrame) -> dict:
    low_level_share = _pct(int((dataframe["level_reached"] <= 10).sum()), len(dataframe))
    stuck_players = int(
        ((dataframe["level_reached"] <= 10) & (dataframe["session_duration"] >= 30)).sum()
    )
    os_stats = dataframe.groupby("device_os")["session_duration"].mean().sort_values()

    if len(os_stats) >= 2:
        weak_os = str(os_stats.index[0])
        strong_os = str(os_stats.index[-1])
        weak_value = float(os_stats.iloc[0])
        strong_value = float(os_stats.iloc[-1])
        finding = (
            f"新手玩家（等级≤10）占比 {low_level_share:.1f}%，其中 {stuck_players} 人单次在线超过 30 分钟"
            f"但等级仍停留在 10 级以内；{weak_os} 端平均在线 {weak_value:.0f} 分钟，"
            f"低于 {strong_os} 端的 {strong_value:.0f} 分钟。"
        )
        suggestion = (
            f"建议优先排查 {weak_os} 端的加载耗时与卡顿，并在等级 5 前后加入「首胜奖励 + 引导加速」，"
            "结合关卡漏斗埋点定位新手流失节点。"
        )
        metric = {
            "label": "端间在线时长差",
            "value": f"{abs(strong_value - weak_value):.0f} 分钟",
        }
    else:
        platform = str(os_stats.index[0]) if len(os_stats) else "单一"
        finding = (
            f"当前样本仅覆盖 {platform} 平台，新手玩家（等级≤10）占比 {low_level_share:.1f}%，"
            f"其中 {stuck_players} 人长时间停留低等级。"
        )
        suggestion = "建议补充双端数据对比，并在等级 5 前后加入首胜奖励与新手引导加速，降低前期流失。"
        metric = {"label": "低等级玩家占比", "value": f"{low_level_share:.1f}%"}

    return {
        "id": "engagement",
        "level": "warning" if stuck_players > 0 else "success",
        "title": "平台体验与新手引导",
        "finding": finding,
        "suggestion": suggestion,
        "metric": metric,
    }


def build_insights(dataframe: pd.DataFrame, metrics: dict) -> list[dict]:
    """始终返回 3 条洞察：数据质量（有修复时）+ 市场 + 付费 / 新手体验。"""

    candidates: list[Optional[dict]] = [
        _quality_insight(metrics),
        _market_insight(dataframe),
        _payer_insight(dataframe),
        _engagement_insight(dataframe),
    ]
    insights = [item for item in candidates if item is not None]
    return insights[:3]

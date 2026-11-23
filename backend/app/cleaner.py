"""Pandas 智能清洗引擎。

职责：
- 数据体检（缺失 / 重复 / 异常 / 格式问题），输出单元格级标记
- 智能清洗（中位数填充、去重、文本标准化、异常修正、日期标准化）
- 计算数据健康度与修复统计，并输出每一步耗时日志
"""

from __future__ import annotations

import math
import re
import statistics
import time
import warnings
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "player_id",
    "country",
    "device_os",
    "level_reached",
    "iap_amount",
    "session_duration",
    "last_login",
]

COLUMN_LABELS = {
    "player_id": "玩家 ID",
    "country": "国家",
    "device_os": "设备 OS",
    "level_reached": "等级",
    "iap_amount": "内购金额",
    "session_duration": "在线时长",
    "last_login": "最近登录",
}

NUMERIC_COLUMNS = ["level_reached", "iap_amount", "session_duration"]
TEXT_COLUMNS = ["player_id", "country", "device_os"]

DEVICE_OS_MAP = {
    "ios": "iOS",
    "android": "Android",
    "android os": "Android",
    "苹果": "iOS",
    "安卓": "Android",
}

MISSING_TOKENS = {"", "-", "--", "null", "none", "nan", "n/a", "na"}
STANDARD_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
DATE_OUTPUT_FORMAT = "%Y-%m-%d %H:%M"
FALLBACK_DATE = pd.Timestamp("2024-01-01 00:00")

# 业务合理区间：内购金额、在线时长（分钟）、等级
IAP_MAX = 499.99
SESSION_MAX_MINUTES = 720
LEVEL_MAX = 100


def is_missing(value: Any) -> bool:
    """统一判断 None / NaN / NaT / 空白字符串等缺失形态。"""

    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in MISSING_TOKENS
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(missing) if isinstance(missing, (bool, np.bool_)) else False


def to_number(value: Any) -> Optional[float]:
    """把 "$4.99"、"1,299"、" (12.5) " 等文本安全转成 float，失败返回 None。"""

    if is_missing(value):
        return None
    try:
        if isinstance(value, str):
            text = value.strip().replace(",", "")
            for symbol in ("$", "€", "£", "¥", "￥"):
                text = text.replace(symbol, "")
            text = text.replace(" ", "")
            # 会计格式负数：(12.5) → -12.5
            if text.startswith("(") and text.endswith(")"):
                text = f"-{text[1:-1]}"
            return float(text)
        return float(value)
    except (TypeError, ValueError):
        return None


def numeric_issue_reason(column: str, value: float) -> Optional[str]:
    """返回数值越界的中文原因；正常值返回 None。"""

    if column == "iap_amount":
        if value < 0:
            return "内购金额为负数（疑似退款符号录入错误）"
        if value > IAP_MAX:
            return f"内购金额超出合理区间（> {IAP_MAX}）"
    elif column == "session_duration":
        if value <= 0:
            return "在线时长小于等于 0 分钟"
        if value > SESSION_MAX_MINUTES:
            return "在线时长超出常识（> 720 分钟 / 12 小时）"
    elif column == "level_reached":
        if value < 1:
            return "等级小于 1"
        if value > LEVEL_MAX:
            return f"等级超出合理上限（> {LEVEL_MAX}）"
    return None


def safe_parse_dates(series: pd.Series) -> pd.Series:
    """兼容斜杠 / ISO / 日/月/年 等混合格式的日期解析。"""

    text = series.map(lambda value: None if is_missing(value) else str(value).strip())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return pd.to_datetime(text, errors="coerce", dayfirst=True, format="mixed")
        except (TypeError, ValueError):
            return pd.to_datetime(text, errors="coerce", dayfirst=True)


def reasonable_median(series: pd.Series, column: str) -> float:
    """只用「合理值」计算中位数，避免异常值污染填充基准。"""

    values = []
    for raw in series.dropna().tolist():
        number = to_number(raw)
        if number is None or numeric_issue_reason(column, number):
            continue
        values.append(number)
    return float(statistics.median(values)) if values else 0.0


def compute_health(issue_cells: int, total_cells: int) -> float:
    """数据健康度 = 100 - 问题单元格占比。"""

    if total_cells <= 0:
        return 100.0
    score = max(0.0, 100.0 - (issue_cells / total_cells) * 100.0)
    return round(score, 1)


def json_safe(value: Any) -> Any:
    """把 Pandas / Numpy 值转成可 JSON 序列化的值。"""

    if is_missing(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.strftime(DATE_OUTPUT_FORMAT)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) else number
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) else value
    return value if isinstance(value, str) else str(value)


def dataframe_to_rows(dataframe: pd.DataFrame) -> list[dict]:
    """按固定字段顺序输出 JSON 友好的行数据。"""

    rows: list[dict] = []
    for record in dataframe.to_dict(orient="records"):
        rows.append({column: json_safe(record.get(column)) for column in REQUIRED_COLUMNS})
    return rows


def profile_raw(dataframe: pd.DataFrame) -> dict:
    """对原始数据做体检，返回单元格级问题标记与完全重复行。"""

    flags: list[dict] = []
    duplicate_rows: list[int] = []

    if dataframe.empty:
        return {"flags": flags, "duplicate_rows": duplicate_rows}

    duplicate_mask = dataframe.duplicated(keep="first")
    for position in dataframe.index[duplicate_mask]:
        duplicate_rows.append(int(position))
        flags.append(
            {
                "row": int(position),
                "field": None,
                "type": "duplicate",
                "hint": "与前面的记录完全重复，将被去重",
            }
        )

    parsed_dates = safe_parse_dates(dataframe["last_login"])

    for position in dataframe.index:
        row = dataframe.loc[position]
        for column in REQUIRED_COLUMNS:
            value = row.get(column)
            label = COLUMN_LABELS[column]

            if is_missing(value):
                flags.append(
                    {
                        "row": int(position),
                        "field": column,
                        "type": "missing",
                        "hint": f"{label}缺失",
                    }
                )
                continue

            if column in NUMERIC_COLUMNS:
                number = to_number(value)
                if number is None:
                    flags.append(
                        {
                            "row": int(position),
                            "field": column,
                            "type": "anomaly",
                            "hint": f"{label}不是有效数值",
                        }
                    )
                    continue
                reason = numeric_issue_reason(column, number)
                if reason:
                    flags.append(
                        {
                            "row": int(position),
                            "field": column,
                            "type": "anomaly",
                            "hint": reason,
                        }
                    )
                continue

            if column == "country":
                text = str(value).strip()
                if text.upper() == "UNKNOWN":
                    continue
                if text != text.upper() or (isinstance(value, str) and value != value.strip()):
                    flags.append(
                        {
                            "row": int(position),
                            "field": column,
                            "type": "format",
                            "hint": "国家代码大小写 / 空格不规范",
                        }
                    )
            elif column == "device_os":
                text = str(value).strip()
                canonical = DEVICE_OS_MAP.get(text.lower())
                if canonical and text != canonical:
                    flags.append(
                        {
                            "row": int(position),
                            "field": column,
                            "type": "format",
                            "hint": "设备系统命名不统一",
                        }
                    )
            elif column == "last_login":
                parsed = parsed_dates.get(position)
                if pd.isna(parsed):
                    flags.append(
                        {
                            "row": int(position),
                            "field": column,
                            "type": "anomaly",
                            "hint": "登录时间无法解析",
                        }
                    )
                elif isinstance(value, str) and not STANDARD_DATE_PATTERN.match(value.strip()):
                    flags.append(
                        {
                            "row": int(position),
                            "field": column,
                            "type": "format",
                            "hint": "日期格式不统一（应为 YYYY-MM-DD HH:MM）",
                        }
                    )

    return {"flags": flags, "duplicate_rows": duplicate_rows}


def clean_dataframe(raw_dataframe: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """执行完整清洗流程，返回（清洗后的 DataFrame, 前端所需 payload）。"""

    run_started = time.perf_counter()
    logs: list[dict] = []

    def log(step: str, message: str, started: float, level: str = "info") -> None:
        logs.append(
            {
                "step": step,
                "message": message,
                "ms": round((time.perf_counter() - started) * 1000, 1),
                "level": level,
            }
        )

    profile = profile_raw(raw_dataframe)
    raw_total = int(len(raw_dataframe))
    total_cells = raw_total * len(REQUIRED_COLUMNS)
    raw_issue_cells = (
        len([flag for flag in profile["flags"] if flag["field"]])
        + len(profile["duplicate_rows"]) * len(REQUIRED_COLUMNS)
    )
    raw_health = compute_health(raw_issue_cells, total_cells)

    dataframe = raw_dataframe.reset_index(drop=True).copy()
    repairs: dict[tuple[int, str], dict] = {}

    def mark(position: int, field: str, hint: str, category: str) -> None:
        key = (int(position), field)
        if key not in repairs:
            repairs[key] = {
                "row": int(position),
                "field": field,
                "type": "repaired",
                "category": category,
                "hint": hint,
            }

    # 步骤 1：文本字段标准化
    started = time.perf_counter()
    text_changes = 0
    for column in TEXT_COLUMNS:
        for position in dataframe.index:
            value = dataframe.at[position, column]
            if is_missing(value):
                continue
            original = str(value)
            stripped = original.strip()
            if column == "country":
                replacement = stripped.upper()
                hint = "国家代码已统一为大写并去除空格"
            elif column == "device_os":
                replacement = DEVICE_OS_MAP.get(stripped.lower(), stripped)
                hint = "设备系统命名已统一"
            else:
                replacement = stripped
                hint = "已去除首尾空格"
            if replacement != original:
                dataframe.at[position, column] = replacement
                mark(position, column, hint, "format")
                text_changes += 1
    log(
        "文本标准化",
        f"扫描玩家 ID / 国家 / 设备字段，修复 {text_changes} 处空格或大小写问题",
        started,
        "success" if text_changes else "info",
    )

    # 步骤 2：数值类型校验
    started = time.perf_counter()
    invalid_numeric = 0
    for column in NUMERIC_COLUMNS:
        converted = pd.to_numeric(
            dataframe[column].map(lambda value: to_number(value)),
            errors="coerce",
        )
        for position in dataframe.index:
            if not is_missing(dataframe.at[position, column]) and pd.isna(converted.loc[position]):
                invalid_numeric += 1
                mark(position, column, "非数值内容无法识别，已按缺失值处理", "anomaly")
        dataframe[column] = converted
    log(
        "类型校验",
        f"数值列强制转换完成，识别 {invalid_numeric} 处非法数值",
        started,
        "success" if invalid_numeric else "info",
    )

    # 步骤 3：越界异常值修正
    started = time.perf_counter()
    anomaly_fixes = 0
    medians = {column: reasonable_median(dataframe[column], column) for column in NUMERIC_COLUMNS}
    for column in NUMERIC_COLUMNS:
        median = medians[column]
        for position in dataframe.index:
            value = dataframe.at[position, column]
            if pd.isna(value):
                continue
            number = float(value)
            reason = numeric_issue_reason(column, number)
            if not reason:
                continue
            if column == "iap_amount" and number < 0:
                replacement = round(abs(number), 2)
                hint = f"负数金额已取绝对值修正为 {replacement:.2f}（疑似退款符号错误）"
            else:
                if column in ("level_reached", "session_duration"):
                    replacement = max(1, int(round(median)))
                else:
                    replacement = round(median, 2)
                hint = f"{reason}，已按合理中位数修正为 {replacement}"
            dataframe.at[position, column] = replacement
            mark(position, column, hint, "anomaly")
            anomaly_fixes += 1
    log(
        "异常修正",
        f"按业务合理区间修正 {anomaly_fixes} 处越界数值（负数金额取绝对值）",
        started,
        "success" if anomaly_fixes else "info",
    )

    # 步骤 4：缺失值智能填充
    started = time.perf_counter()
    missing_filled_raw = 0
    for column in NUMERIC_COLUMNS:
        median = medians[column]
        if column in ("level_reached", "session_duration"):
            fill_value = max(1, int(round(median)))
        else:
            fill_value = round(median, 2)
        for position in dataframe.index:
            if pd.isna(dataframe.at[position, column]):
                dataframe.at[position, column] = fill_value
                mark(position, column, f"缺失值已按中位数填充为 {fill_value}", "missing")
                missing_filled_raw += 1
    for column in TEXT_COLUMNS:
        for position in dataframe.index:
            if is_missing(dataframe.at[position, column]):
                if column == "country":
                    replacement = "UNKNOWN"
                    hint = "缺失国家代码已填充为 UNKNOWN"
                else:
                    replacement = "Unknown"
                    hint = "缺失文本已填充为 Unknown"
                dataframe.at[position, column] = replacement
                mark(position, column, hint, "missing")
                missing_filled_raw += 1
    dataframe["level_reached"] = dataframe["level_reached"].round(0).astype(int)
    dataframe["session_duration"] = dataframe["session_duration"].round(0).astype(int)
    dataframe["iap_amount"] = dataframe["iap_amount"].round(2)
    log(
        "缺失填充",
        f"数值列按中位数、文本列按 Unknown（国家为 UNKNOWN）填充，共补全 {missing_filled_raw} 个缺失单元格",
        started,
        "success" if missing_filled_raw else "info",
    )

    # 步骤 5：日期标准化
    started = time.perf_counter()
    parsed_dates = safe_parse_dates(dataframe["last_login"])
    valid_dates = parsed_dates.dropna()
    if len(valid_dates):
        mode_values = valid_dates.dt.floor("min").mode()
        fallback_date = pd.Timestamp(mode_values.iloc[0]) if len(mode_values) else FALLBACK_DATE
    else:
        fallback_date = FALLBACK_DATE
    fallback_text = fallback_date.strftime(DATE_OUTPUT_FORMAT)
    date_fixes = 0
    for position in dataframe.index:
        original = dataframe.at[position, "last_login"]
        parsed = parsed_dates.get(position)
        if is_missing(original):
            replacement = fallback_text
            hint = "缺失登录时间已按众数日期填充"
            category = "missing"
        elif pd.isna(parsed):
            replacement = fallback_text
            hint = "无法解析的日期已按众数日期修正"
            category = "anomaly"
        else:
            replacement = parsed.strftime(DATE_OUTPUT_FORMAT)
            hint = "日期已统一为标准格式 YYYY-MM-DD HH:MM"
            category = "format"
        dataframe.at[position, "last_login"] = replacement
        should_mark = category != "format" or (
            not is_missing(original) and str(original).strip() != replacement
        )
        if should_mark:
            mark(position, "last_login", hint, category)
            date_fixes += 1
    log(
        "日期标准化",
        f"日期列混合格式统一为 YYYY-MM-DD HH:MM，共修复 {date_fixes} 处",
        started,
        "success" if date_fixes else "info",
    )

    # 步骤 6：完全重复行去重
    started = time.perf_counter()
    before_dedupe = len(dataframe)
    dataframe = dataframe.drop_duplicates(keep="first")
    duplicate_removed = before_dedupe - len(dataframe)
    kept_positions = list(dataframe.index)
    dataframe = dataframe.reset_index(drop=True)
    index_map = {old: new for new, old in enumerate(kept_positions)}
    log(
        "完全去重",
        f"移除 {duplicate_removed} 条完全重复记录，保留 {len(dataframe)} 条有效记录",
        started,
        "success" if duplicate_removed else "info",
    )

    # 步骤 7：修复结果复核 / 健康度评分
    started = time.perf_counter()
    clean_flags: list[dict] = []
    for (position, field), info in repairs.items():
        if position not in index_map:
            continue
        clean_flags.append({**info, "row": index_map[position]})
    clean_flags.sort(key=lambda flag: (flag["row"], REQUIRED_COLUMNS.index(flag["field"])))

    kept_repairs = [info for (position, _), info in repairs.items() if position in index_map]
    missing_filled = sum(1 for item in kept_repairs if item["category"] == "missing")
    anomalies_fixed = sum(1 for item in kept_repairs if item["category"] == "anomaly")
    format_normalized = sum(1 for item in kept_repairs if item["category"] == "format")
    repaired_count = len(kept_repairs) + duplicate_removed

    post_profile = profile_raw(dataframe)
    post_issue_cells = (
        len([flag for flag in post_profile["flags"] if flag["field"]])
        + len(post_profile["duplicate_rows"]) * len(REQUIRED_COLUMNS)
    )
    clean_health = compute_health(post_issue_cells, len(dataframe) * len(REQUIRED_COLUMNS))
    log(
        "健康度复核",
        f"复检剩余问题单元格 {post_issue_cells} 个，数据健康度 {clean_health} 分",
        started,
        "success" if post_issue_cells == 0 else "warn",
    )

    duration_ms = round((time.perf_counter() - run_started) * 1000, 1)
    metrics = {
        "raw_total": raw_total,
        "clean_total": int(len(dataframe)),
        "duplicate_removed": duplicate_removed,
        "missing_filled": missing_filled,
        "anomalies_fixed": anomalies_fixed,
        "format_normalized": format_normalized,
        "repaired_count": repaired_count,
        "raw_issue_cells": raw_issue_cells,
        "remaining_issue_cells": post_issue_cells,
        "raw_health": raw_health,
        "clean_health": clean_health,
        "health_delta": round(clean_health - raw_health, 1),
        "duration_ms": duration_ms,
    }
    logs.append(
        {
            "step": "完成",
            "message": (
                f"清洗完成：{raw_total} → {len(dataframe)} 条，健康度 "
                f"{raw_health} → {clean_health}，共处理 {repaired_count} 处问题"
            ),
            "ms": duration_ms,
            "level": "success",
        }
    )

    payload = {
        "rows": dataframe_to_rows(dataframe),
        "flags": clean_flags,
        "total": int(len(dataframe)),
        "columns": REQUIRED_COLUMNS,
        "metrics": metrics,
        "logs": logs,
        "duration_ms": duration_ms,
    }
    return dataframe, payload

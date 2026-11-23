"""SmartClean AI FastAPI 入口。

接口一览：
- GET  /api/health                  健康检查（前端启动探测）
- POST /api/generate-mock-data      生成 20 条演示脏数据
- POST /api/upload                  上传 CSV / XLSX 并按别名自动导入（兼容旧接口）
- POST /api/inspect-upload          上传预检：返回源列、样例与自动映射建议
- POST /api/confirm-upload          按人工确认的字段映射导入数据
- POST /api/clean-data              执行 Pandas 清洗 + 规则引擎洞察
- GET  /api/export/{dataset_id}     导出清洗后 CSV
"""

from __future__ import annotations

import io
import hashlib
import re
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .cleaner import (
    COLUMN_LABELS,
    REQUIRED_COLUMNS,
    clean_dataframe,
    compute_health,
    dataframe_to_rows,
    json_safe,
    profile_raw,
)
from .insights import build_insights
from .mock_data import generate_mock_dataframe

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
CACHE_LIMIT = 30
PENDING_UPLOAD_LIMIT = 12
PENDING_UPLOAD_TTL_SECONDS = 30 * 60
DEFAULT_MAPPING_VALUE = "__default__"
SAMPLE_PREVIEW_ROWS = 5

# 允许中文表头 / 常见运营后台字段名，降低真实文件接入成本
COLUMN_ALIASES = {
    "player_id": {
        "player_id", "playerid", "player", "uid", "user_id", "userid",
        "account_id", "accountid", "gamer_id", "gamerid", "玩家id", "玩家_id",
        "用户id", "用户_id", "账号id", "账号_id",
    },
    "country": {
        "country", "country_code", "countrycode", "nation", "region",
        "region_code", "geo", "国家", "地区", "国家代码", "国家_地区",
    },
    "device_os": {
        "device_os", "os", "device", "platform", "operating_system",
        "operatingsystem", "device_type", "设备", "系统", "操作系统", "平台",
    },
    "level_reached": {
        "level_reached", "level", "player_level", "current_level",
        "max_level", "等级", "玩家等级", "当前等级",
    },
    "iap_amount": {
        "iap_amount", "iap", "amount", "revenue", "pay_amount", "payment",
        "price", "spend", "total_spent", "purchase_amount", "purchase_revenue",
        "内购金额", "流水", "付费金额", "消费金额", "充值金额",
    },
    "session_duration": {
        "session_duration", "session", "duration", "online_time", "play_time",
        "playtime", "session_length", "session_minutes", "minutes_played",
        "在线时长", "游戏时长", "会话时长",
    },
    "last_login": {
        "last_login", "login_time", "last_login_time", "login", "last_active",
        "last_active_time", "last_seen", "last_seen_at", "login_date",
        "last_login_date", "最近登录", "登录时间", "最后登录", "最后活跃",
    },
}

# 缺字段时的表头建议（固定顺序，便于前端错误弹窗阅读）
COLUMN_ALIAS_HINTS = {
    "player_id": "player_id / user_id / uid / 玩家id",
    "country": "country / country_code / region / 国家",
    "device_os": "device_os / os / platform / operating_system / 操作系统",
    "level_reached": "level_reached / level / player_level / 等级",
    "iap_amount": "iap_amount / iap / revenue / amount / total_spent / 内购金额",
    "session_duration": "session_duration / session_length / play_time / 在线时长",
    "last_login": "last_login / login_time / last_active / 登录时间",
}


class CleanRequest(BaseModel):
    dataset_id: str


class ConfirmUploadRequest(BaseModel):
    pending_id: str
    mapping: dict[str, Optional[str]]


class DatasetCache:
    """线程安全的内存数据集缓存（演示场景，无需数据库）。"""

    def __init__(self, limit: int = CACHE_LIMIT) -> None:
        self._items: OrderedDict[str, dict] = OrderedDict()
        self._limit = limit
        self._lock = threading.Lock()

    def put(
        self,
        dataframe: pd.DataFrame,
        source: str,
        filename: Optional[str] = None,
        logs: Optional[list[dict]] = None,
    ) -> str:
        dataset_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._items[dataset_id] = {
                "dataframe": dataframe,
                "source": source,
                "filename": filename,
                "created_at": time.time(),
                "cleaned_dataframe": None,
                "clean_payload": None,
                "logs": logs or [],
            }
            while len(self._items) > self._limit:
                self._items.popitem(last=False)
        return dataset_id

    def get(self, dataset_id: str) -> Optional[dict]:
        with self._lock:
            dataset = self._items.get(dataset_id)
            if dataset is not None:
                self._items.move_to_end(dataset_id)
            return dataset

    def set_clean(self, dataset_id: str, dataframe: pd.DataFrame, payload: dict) -> None:
        with self._lock:
            dataset = self._items.get(dataset_id)
            if dataset is not None:
                dataset["cleaned_dataframe"] = dataframe
                dataset["clean_payload"] = payload
                self._items.move_to_end(dataset_id)

    def count(self) -> int:
        with self._lock:
            return len(self._items)


class PendingUploadCache:
    """保存「已解析但尚未确认字段映射」的上传文件（内存 + TTL）。"""

    def __init__(self, limit: int = PENDING_UPLOAD_LIMIT, ttl: int = PENDING_UPLOAD_TTL_SECONDS) -> None:
        self._items: OrderedDict[str, dict] = OrderedDict()
        self._limit = limit
        self._ttl = ttl
        self._lock = threading.Lock()

    def _prune_locked(self) -> None:
        now = time.time()
        expired = [key for key, item in self._items.items() if now - item["created_at"] > self._ttl]
        for key in expired:
            self._items.pop(key, None)

    def put(self, dataframe: pd.DataFrame, filename: str, parse_ms: float) -> str:
        pending_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._prune_locked()
            self._items[pending_id] = {
                "dataframe": dataframe,
                "filename": filename,
                "created_at": time.time(),
                "parse_ms": parse_ms,
            }
            while len(self._items) > self._limit:
                self._items.popitem(last=False)
        return pending_id

    def get(self, pending_id: str) -> Optional[dict]:
        with self._lock:
            self._prune_locked()
            pending = self._items.get(pending_id)
            if pending is not None:
                self._items.move_to_end(pending_id)
            return pending

    def pop(self, pending_id: str) -> Optional[dict]:
        with self._lock:
            return self._items.pop(pending_id, None)

    def count(self) -> int:
        with self._lock:
            self._prune_locked()
            return len(self._items)


cache = DatasetCache()
pending_cache = PendingUploadCache()
app = FastAPI(title="SmartClean AI API", version="1.0.0")

# Vite 代理已解决跨域，这里再兜底一层，保证直连 8000 端口也能调试
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _fuzzy_canonical_column(key: str) -> Optional[str]:
    """对未精确命中的表头做关键词兜底映射（如 total_revenue → iap_amount）。"""

    tokens = set(key.split("_"))

    def has(*words: str) -> bool:
        return all(word in tokens for word in words)

    if has("player", "id") or has("user", "id") or has("account", "id") or has("gamer", "id") or "uid" in tokens:
        return "player_id"
    if (
        has("last", "login")
        or has("last", "active")
        or has("last", "seen")
        or has("login", "time")
        or has("login", "date")
    ):
        return "last_login"
    if (
        has("session", "duration")
        or has("session", "length")
        or has("session", "minutes")
        or has("play", "time")
        or has("online", "time")
        or "duration" in tokens
    ):
        return "session_duration"
    if (
        "iap" in tokens
        or "revenue" in tokens
        or "spent" in tokens
        or "spend" in tokens
        or "payment" in tokens
        or "purchase" in tokens
        or "amount" in tokens
        or "price" in tokens
    ):
        return "iap_amount"
    if "level" in tokens:
        return "level_reached"
    if "country" in tokens or "region" in tokens or "nation" in tokens or "geo" in tokens:
        return "country"
    if (
        "platform" in tokens
        or "os" in tokens
        or has("operating", "system")
        or has("device", "type")
    ):
        return "device_os"
    return None


def _canonical_column(name: object) -> str:
    # 兼容 PlayerID / OperatingSystem 等驼峰表头，先拆成 Player_ID / Operating_System
    raw = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(name).strip())
    key = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", raw.lower()).strip("_")
    for canonical, aliases in COLUMN_ALIASES.items():
        if key in aliases:
            return canonical
    return _fuzzy_canonical_column(key) or key


def _ensure_unique_column_names(dataframe: pd.DataFrame) -> pd.DataFrame:
    """把表头统一成非空、唯一字符串，供映射下拉框稳定使用。"""

    names: list[str] = []
    seen: dict[str, int] = {}
    for index, column in enumerate(dataframe.columns):
        base = str(column).strip() or f"column_{index + 1}"
        if base in seen:
            seen[base] += 1
            base = f"{base}_{seen[base]}"
        else:
            seen[base] = 1
        names.append(base)
    dataframe = dataframe.copy()
    dataframe.columns = names
    return dataframe


def read_tabular_file(filename: str, content: bytes) -> pd.DataFrame:
    """读取 CSV（自动尝试编码与分隔符）或 XLSX，保留原始表头，不做字段校验。"""

    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        decoded: Optional[str] = None
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
            try:
                decoded = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            raise ValueError("无法识别 CSV 文件编码，请另存为 UTF-8 后重新上传")
        buffer = io.StringIO(decoded)
        try:
            dataframe = pd.read_csv(buffer, sep=None, engine="python")
        except (pd.errors.ParserError, ValueError):
            buffer.seek(0)
            dataframe = pd.read_csv(buffer)
    elif suffix == ".xlsx":
        try:
            dataframe = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        except Exception as exc:  # openpyxl 对损坏文件抛出的异常类型较多
            raise ValueError(f"Excel 解析失败，请确认文件未损坏：{exc}") from exc
    else:
        raise ValueError("仅支持 .csv 或 .xlsx 文件，请重新选择")

    dataframe = dataframe.dropna(how="all")
    if dataframe.empty:
        raise ValueError("文件中没有有效数据行")
    return _ensure_unique_column_names(dataframe)


def build_suggested_mapping(dataframe: pd.DataFrame) -> dict[str, Optional[str]]:
    """为 7 个标准字段自动推荐源列；同一源列不会被重复推荐。"""

    mapping: dict[str, Optional[str]] = {column: None for column in REQUIRED_COLUMNS}
    used_sources: set[str] = set()
    for target in REQUIRED_COLUMNS:
        for column in dataframe.columns:
            if column in used_sources:
                continue
            if _canonical_column(column) == target:
                mapping[target] = column
                used_sources.add(column)
                break
    return mapping


def _default_value_series(target: str, dataframe: pd.DataFrame) -> pd.Series:
    """当用户选择「使用默认值」时构造占位列。

    player_id 使用源行内容哈希，保证完全重复行得到相同 ID，不破坏后续去重。
    """

    index = dataframe.index
    count = len(index)
    if target == "player_id":
        identifiers = []
        for values in dataframe.itertuples(index=False, name=None):
            payload = "|".join("" if json_safe(value) is None else str(json_safe(value)) for value in values)
            digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8].upper()
            identifiers.append(f"AUTO-{digest}")
        return pd.Series(identifiers, index=index, dtype="object")
    if target in ("country", "device_os"):
        return pd.Series(["Unknown"] * count, index=index, dtype="object")
    if target == "level_reached":
        return pd.Series([1] * count, index=index, dtype="int64")
    if target == "iap_amount":
        return pd.Series([0.0] * count, index=index, dtype="float64")
    if target == "session_duration":
        return pd.Series([30] * count, index=index, dtype="int64")
    if target == "last_login":
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        return pd.Series([timestamp] * count, index=index, dtype="object")
    return pd.Series([None] * count, index=index, dtype="object")


def apply_column_mapping(
    dataframe: pd.DataFrame,
    mapping: dict[str, Optional[str]],
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """按用户确认的字段映射重建 7 列标准数据。"""

    unassigned = [target for target in REQUIRED_COLUMNS if not mapping.get(target)]
    if unassigned:
        labels = "、".join(f"{COLUMN_LABELS[target]}（{target}）" for target in unassigned)
        raise ValueError(f"以下字段尚未完成映射：{labels}。请选择源字段，或显式使用默认值。")

    result = pd.DataFrame(index=dataframe.index)
    used_sources: dict[str, str] = {}
    mapped_fields: list[str] = []
    default_fields: list[str] = []

    for target in REQUIRED_COLUMNS:
        source = mapping.get(target)
        if source == DEFAULT_MAPPING_VALUE:
            result[target] = _default_value_series(target, dataframe)
            default_fields.append(target)
            continue
        if source not in dataframe.columns:
            raise ValueError(f"源字段「{source}」不存在，请重新选择映射列")
        if source in used_sources:
            previous = COLUMN_LABELS[used_sources[source]]
            raise ValueError(f"源字段「{source}」已映射到「{previous}」，不能重复使用")
        used_sources[str(source)] = target
        result[target] = dataframe[source]
        mapped_fields.append(target)

    return result[REQUIRED_COLUMNS].reset_index(drop=True), mapped_fields, default_fields


def build_inspection_payload(pending_id: str, pending: dict) -> dict:
    """返回字段映射弹窗所需的数据：源列、样例、自动推荐映射、缺失字段。"""

    dataframe = pending["dataframe"]
    suggested = build_suggested_mapping(dataframe)
    missing = [target for target in REQUIRED_COLUMNS if not suggested[target]]

    source_columns = []
    for column in dataframe.columns:
        source_columns.append(
            {
                "name": str(column),
                "dtype": str(dataframe[column].dtype),
                "sample": [json_safe(value) for value in dataframe[column].head(3).tolist()],
            }
        )

    sample_rows = []
    for _, row in dataframe.head(SAMPLE_PREVIEW_ROWS).iterrows():
        sample_rows.append({str(column): json_safe(row[column]) for column in dataframe.columns})

    return {
        "pending_id": pending_id,
        "filename": pending["filename"],
        "total_rows": int(len(dataframe)),
        "source_columns": source_columns,
        "sample_rows": sample_rows,
        "sample_row_count": len(sample_rows),
        "suggested_mapping": suggested,
        "missing_fields": missing,
        "auto_mapped_count": len(REQUIRED_COLUMNS) - len(missing),
        "parse_ms": pending["parse_ms"],
    }


def normalize_upload_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """统一表头、校验必填字段，并只保留看板需要的 7 列。"""

    renamed = dataframe.rename(
        columns={column: _canonical_column(column) for column in dataframe.columns}
    )
    renamed = renamed.loc[:, ~renamed.columns.duplicated()]
    renamed = renamed.dropna(how="all")
    if renamed.empty:
        raise ValueError("文件中没有有效数据行")
    missing = [column for column in REQUIRED_COLUMNS if column not in renamed.columns]
    if missing:
        labels = "、".join(f"{COLUMN_LABELS[column]}（{column}）" for column in missing)
        hints = "；".join(f"{COLUMN_LABELS[column]} 可用 {COLUMN_ALIAS_HINTS[column]}" for column in missing)
        raise ValueError(
            f"文件缺少必填字段：{labels}。{hints}。"
            "请在 Excel / 文本编辑器中重命名表头后重新上传，或参考 sample_data/alias_headers_example.csv。"
        )
    return renamed[REQUIRED_COLUMNS].reset_index(drop=True)


def parse_upload(filename: str, content: bytes) -> pd.DataFrame:
    """兼容旧接口：读取文件并自动标准化表头。"""

    dataframe = read_tabular_file(filename, content)
    return normalize_upload_dataframe(dataframe)


def build_preview(dataset_id: str, dataset: dict) -> dict:
    """构造原始数据预览（含单元格级问题标记）。"""

    dataframe = dataset["dataframe"]
    profile = profile_raw(dataframe)
    total = int(len(dataframe))
    issue_cells = (
        len([flag for flag in profile["flags"] if flag["field"]])
        + len(profile["duplicate_rows"]) * len(REQUIRED_COLUMNS)
    )
    return {
        "dataset_id": dataset_id,
        "source": dataset["source"],
        "filename": dataset["filename"],
        "columns": REQUIRED_COLUMNS,
        "raw": {
            "rows": dataframe_to_rows(dataframe),
            "flags": profile["flags"],
            "duplicate_rows": profile["duplicate_rows"],
            "total": total,
            "issue_cells": issue_cells,
            "health": compute_health(issue_cells, total * len(REQUIRED_COLUMNS)),
        },
        "logs": dataset["logs"],
    }


async def _read_uploaded_file(file: UploadFile) -> tuple[str, bytes]:
    """统一处理上传文件大小、空文件和文件名安全。"""

    content = await file.read()
    filename = Path(file.filename or "upload.csv").name
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空，请重新选择")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="文件超过 10MB 限制，请拆分后再上传")
    return filename, content


@app.get("/")
def root() -> dict:
    return {
        "service": "SmartClean AI API",
        "docs": "/docs",
        "health": "/api/health",
        "inspect_upload": "/api/inspect-upload",
        "confirm_upload": "/api/confirm-upload",
    }


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "SmartClean AI",
        "datasets": cache.count(),
        "time": datetime.now().isoformat(timespec="seconds"),
    }


@app.post("/api/generate-mock-data")
def generate_mock_data() -> dict:
    started = time.perf_counter()
    dataframe = generate_mock_dataframe(20)
    elapsed = round((time.perf_counter() - started) * 1000, 1)
    logs = [
        {
            "step": "演示数据",
            "message": f"已生成 {len(dataframe)} 条海外休闲游戏运营日志（含缺失 / 重复 / 异常值）",
            "ms": elapsed,
            "level": "success",
        }
    ]
    dataset_id = cache.put(dataframe, source="mock", logs=logs)
    dataset = cache.get(dataset_id)
    if dataset is None:  # pragma: no cover - 正常流程不会触发
        raise HTTPException(status_code=500, detail="演示数据创建失败，请重试")
    return build_preview(dataset_id, dataset)


@app.post("/api/upload")
async def upload_dataset(file: UploadFile = File(...)) -> dict:
    filename, content = await _read_uploaded_file(file)

    started = time.perf_counter()
    try:
        dataframe = parse_upload(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    elapsed = round((time.perf_counter() - started) * 1000, 1)
    logs = [
        {
            "step": "文件解析",
            "message": f"读取 {filename} 成功，共 {len(dataframe)} 行 × {len(REQUIRED_COLUMNS)} 列",
            "ms": elapsed,
            "level": "success",
        }
    ]
    dataset_id = cache.put(dataframe, source="upload", filename=filename, logs=logs)
    dataset = cache.get(dataset_id)
    if dataset is None:  # pragma: no cover
        raise HTTPException(status_code=500, detail="文件数据创建失败，请重试")
    return build_preview(dataset_id, dataset)


@app.post("/api/inspect-upload")
async def inspect_upload_dataset(file: UploadFile = File(...)) -> dict:
    """解析文件但不导入，返回源表头、样例数据与自动映射建议。"""

    filename, content = await _read_uploaded_file(file)
    started = time.perf_counter()
    try:
        dataframe = read_tabular_file(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    elapsed = round((time.perf_counter() - started) * 1000, 1)
    pending_id = pending_cache.put(dataframe, filename, elapsed)
    pending = pending_cache.get(pending_id)
    if pending is None:  # pragma: no cover
        raise HTTPException(status_code=500, detail="上传预检失败，请重试")
    return build_inspection_payload(pending_id, pending)


@app.post("/api/confirm-upload")
def confirm_upload_dataset(payload: ConfirmUploadRequest) -> dict:
    """按用户确认的字段映射导入数据，并注册为可清洗的数据集。"""

    pending = pending_cache.get(payload.pending_id)
    if pending is None:
        raise HTTPException(
            status_code=404,
            detail="上传会话不存在或已过期（30 分钟），请重新选择文件",
        )

    started = time.perf_counter()
    try:
        dataframe, mapped_fields, default_fields = apply_column_mapping(
            pending["dataframe"], payload.mapping
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if dataframe.empty:
        raise HTTPException(status_code=400, detail="映射后的数据为空，请重新选择文件")

    elapsed = round((time.perf_counter() - started) * 1000, 1)
    source_count = len(pending["dataframe"].columns)
    mapping_parts = []
    for target in REQUIRED_COLUMNS:
        source = payload.mapping.get(target)
        if source == DEFAULT_MAPPING_VALUE:
            mapping_parts.append(f"{COLUMN_LABELS[target]}←默认值")
        else:
            mapping_parts.append(f"{COLUMN_LABELS[target]}←{source}")

    default_labels = "、".join(COLUMN_LABELS[target] for target in default_fields)
    mapping_message = f"已映射 {len(mapped_fields)} 个字段"
    if default_fields:
        mapping_message += f"，{len(default_fields)} 个字段使用默认值（{default_labels}）"

    logs = [
        {
            "step": "文件解析",
            "message": (
                f"读取 {pending['filename']} 成功，共 {len(pending['dataframe'])} 行 × {source_count} 列"
            ),
            "ms": pending["parse_ms"],
            "level": "success",
        },
        {
            "step": "字段映射",
            "message": mapping_message,
            "ms": elapsed,
            "level": "warn" if default_fields else "success",
        },
        {
            "step": "字段映射",
            "message": "映射关系：" + "；".join(mapping_parts),
            "ms": 0,
            "level": "info",
        },
    ]

    dataset_id = cache.put(
        dataframe,
        source="upload",
        filename=pending["filename"],
        logs=logs,
    )
    pending_cache.pop(payload.pending_id)
    dataset = cache.get(dataset_id)
    if dataset is None:  # pragma: no cover
        raise HTTPException(status_code=500, detail="文件数据创建失败，请重试")

    preview = build_preview(dataset_id, dataset)
    preview["mapping_summary"] = {
        "mapped_fields": mapped_fields,
        "default_fields": default_fields,
    }
    return preview


@app.post("/api/clean-data")
def clean_data(payload: CleanRequest) -> dict:
    dataset = cache.get(payload.dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在或已过期，请重新加载数据")
    if dataset["dataframe"].empty:
        raise HTTPException(status_code=400, detail="当前数据集为空，无法清洗")

    started = time.perf_counter()
    cleaned_dataframe, result = clean_dataframe(dataset["dataframe"])
    insights = build_insights(cleaned_dataframe, result["metrics"])
    elapsed = round((time.perf_counter() - started) * 1000, 1)

    result.update(
        {
            "dataset_id": payload.dataset_id,
            "source": dataset["source"],
            "filename": dataset["filename"],
            "insights": insights,
            "total_duration_ms": elapsed,
        }
    )
    cache.set_clean(payload.dataset_id, cleaned_dataframe, result)
    return result


@app.get("/api/export/{dataset_id}")
def export_cleaned_csv(dataset_id: str) -> StreamingResponse:
    dataset = cache.get(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在或已过期，请重新加载数据")
    cleaned = dataset.get("cleaned_dataframe")
    if cleaned is None:
        raise HTTPException(status_code=400, detail="请先执行 AI 清洗，再导出干净 CSV")

    csv_text = cleaned.to_csv(index=False, lineterminator="\n")
    content = ("\ufeff" + csv_text).encode("utf-8")  # BOM 兼容 Excel 中文
    filename = f"smartclean_cleaned_{datetime.now():%Y%m%d_%H%M%S}.csv"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

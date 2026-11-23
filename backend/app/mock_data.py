"""海外休闲游戏运营日志模拟脏数据生成器。

刻意注入的脏数据类型：
1. 缺失值（None / 空字符串）
2. 完全重复行（每次随机注入 2~5 条）
3. 国家代码大小写 / 首尾空格不一致
4. 负数内购金额、超常识在线时长、越界等级
5. 格式混乱的 last_login（斜杠、ISO、非法日期）
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from .cleaner import REQUIRED_COLUMNS

COUNTRIES = ["BR", "ID", "VN", "US", "PH", "TH"]
DEVICES = ["iOS", "Android"]
DEFAULT_LOGIN = "%Y-%m-%d %H:%M"

# 真实但不整齐的日期写法，用于演示日期标准化
MESSY_DATES = [
    " 2024/03/06 ",
    "07/03/2024 09:15",
    "2024-3-8 20:05",
    "invalid-date",
    "2024-03-09T18:40:00",
    "2024-03-10",
]


def _random_login(rng: random.Random) -> str:
    moment = datetime(2024, 3, 5, 10, 0) - timedelta(
        days=rng.randint(0, 6), hours=rng.randint(0, 12), minutes=rng.randint(0, 59)
    )
    return moment.strftime(DEFAULT_LOGIN)


def generate_mock_dataframe(n: int = 20, seed: Optional[int] = None) -> pd.DataFrame:
    """生成 n 条（默认 20 条）带脏数据的海外休闲游戏运营日志。

    每次会随机注入 2~5 条完全重复记录，因此 n=20 时清洗后的有效记录
    会在 15~18 条之间变化，让面试演示的指标更真实、不呆板。
    """

    if n <= 0:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    rng = random.Random(seed)
    # 随机注入 2~5 条完全重复行，同时保证至少生成 1 条唯一记录
    duplicate_count = min(rng.randint(2, 5), max(n - 1, 0))
    unique_count = max(n - duplicate_count, 1)
    used_ids: set[str] = set()
    rows: list[dict] = []

    def inject(index: int, field: str, value) -> None:
        """按索引安全注入脏值，兼容较小 n 的调用。"""

        if 0 <= index < len(rows):
            rows[index][field] = value

    for _ in range(unique_count):
        player_id = f"PLY-{rng.randint(10000, 99999)}"
        while player_id in used_ids:
            player_id = f"PLY-{rng.randint(10000, 99999)}"
        used_ids.add(player_id)

        # 约 40% 玩家有内购，保证付费洞察有数据可分析
        iap_amount = round(rng.uniform(0.99, 49.99), 2) if rng.random() < 0.4 else 0.0

        rows.append(
            {
                "player_id": player_id,
                "country": rng.choice(COUNTRIES),
                "device_os": rng.choice(DEVICES),
                "level_reached": rng.randint(1, 45),
                "iap_amount": iap_amount,
                "session_duration": rng.randint(4, 75),
                "last_login": _random_login(rng),
            }
        )

    # ---- 注入缺失值（数值 + 文本 + 日期）----
    inject(1, "country", None)
    inject(3, "iap_amount", None)
    inject(5, "session_duration", None)
    inject(8, "last_login", None)
    inject(8, "level_reached", None)
    inject(11, "device_os", "   ")

    # ---- 国家代码大小写 / 空格不统一 ----
    country_variants = [" br", "us ", "Id", " vn", "th", " ph"]
    for idx, variant in zip((0, 2, 4, 6, 9, 13), country_variants):
        inject(idx, "country", variant)

    # ---- 负数金额 / 超常识时长 / 越界等级 ----
    inject(2, "iap_amount", -4.99)
    inject(7, "iap_amount", -19.9)
    inject(4, "session_duration", 1440)
    inject(10, "session_duration", 960)
    inject(6, "level_reached", 120)
    inject(12, "level_reached", 0)

    # ---- 日期格式混乱 ----
    for idx, messy in zip((0, 3, 5, 7, 10, 12), MESSY_DATES):
        inject(idx, "last_login", messy)

    # ---- 完全重复行（随机 2~5 条）----
    duplicates = [rows[rng.randrange(len(rows))].copy() for _ in range(duplicate_count)]
    rows.extend(duplicates)
    rng.shuffle(rows)
    rows = rows[:n]

    df = pd.DataFrame(rows, columns=REQUIRED_COLUMNS)
    return df.reset_index(drop=True)

"""清洗幂等性回归测试。

确保「清洗 → 导出 CSV → 重新导入 → 再次清洗」不会产生额外修复，
并验证国家缺失占位值统一为 UNKNOWN。
"""

from __future__ import annotations

import io
import unittest

import pandas as pd

from app.cleaner import REQUIRED_COLUMNS, clean_dataframe


def build_dirty_dataframe() -> pd.DataFrame:
    rows = [
        {
            "player_id": "PLY-1001",
            "country": None,
            "device_os": "   ",
            "level_reached": 25,
            "iap_amount": None,
            "session_duration": 40,
            "last_login": None,
        },
        {
            "player_id": "PLY-1002",
            "country": " br ",
            "device_os": "ios",
            "level_reached": None,
            "iap_amount": -4.99,
            "session_duration": 1440,
            "last_login": "2024/03/06",
        },
        {
            "player_id": "PLY-1003",
            "country": "US",
            "device_os": "Android",
            "level_reached": 12,
            "iap_amount": 9.99,
            "session_duration": 30,
            "last_login": "invalid-date",
        },
    ]
    rows.append(dict(rows[1]))  # 完全重复行
    return pd.DataFrame(rows, columns=REQUIRED_COLUMNS)


class CleanIdempotencyTest(unittest.TestCase):
    def test_country_placeholder_is_uppercase(self) -> None:
        cleaned, payload = clean_dataframe(build_dirty_dataframe())

        countries = cleaned["country"].astype(str).tolist()
        self.assertIn("UNKNOWN", countries)
        self.assertNotIn("Unknown", countries)
        self.assertTrue(all(value == value.upper() for value in countries))
        self.assertTrue(
            any(flag["field"] == "country" and "UNKNOWN" in flag["hint"] for flag in payload["flags"])
        )

    def test_second_clean_has_no_repairs(self) -> None:
        cleaned, first = clean_dataframe(build_dirty_dataframe())
        self.assertGreater(first["metrics"]["repaired_count"], 0)

        cleaned_again, second = clean_dataframe(cleaned)
        metrics = second["metrics"]

        self.assertEqual(metrics["repaired_count"], 0)
        self.assertEqual(metrics["missing_filled"], 0)
        self.assertEqual(metrics["anomalies_fixed"], 0)
        self.assertEqual(metrics["format_normalized"], 0)
        self.assertEqual(metrics["duplicate_removed"], 0)
        self.assertEqual(metrics["remaining_issue_cells"], 0)
        self.assertEqual(metrics["clean_health"], 100.0)
        pd.testing.assert_frame_equal(
            cleaned.reset_index(drop=True),
            cleaned_again.reset_index(drop=True),
        )

    def test_csv_export_and_reimport_is_idempotent(self) -> None:
        cleaned, _ = clean_dataframe(build_dirty_dataframe())
        csv_buffer = io.StringIO(cleaned.to_csv(index=False))
        reimported = pd.read_csv(csv_buffer)

        cleaned_again, second = clean_dataframe(reimported)
        metrics = second["metrics"]

        self.assertEqual(metrics["repaired_count"], 0)
        self.assertEqual(metrics["remaining_issue_cells"], 0)
        self.assertEqual(metrics["clean_health"], 100.0)
        self.assertTrue(all(value == value.upper() for value in cleaned_again["country"].astype(str)))
        pd.testing.assert_frame_equal(
            cleaned.reset_index(drop=True),
            cleaned_again.reset_index(drop=True),
        )


if __name__ == "__main__":
    unittest.main()

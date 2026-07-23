from __future__ import annotations

import pandas as pd


def dataframe_to_csv_bytes(frame: pd.DataFrame) -> bytes:
    if frame is None or frame.empty:
        return b""
    return frame.to_csv(index=False).encode("utf-8")

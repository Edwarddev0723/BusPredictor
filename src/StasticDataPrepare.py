import pandas as pd
import argparse
"""
因為計算平均數、中位數、標準差的程式檔案較大，因此包裝成對應的類別方便存取
"""
from TimeStastic import RealTimeStastic

if __name__ == "__main__":
    """
    參數設定
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--routeid", type=int)
    parser.add_argument("--direction", type=int)
    parser.add_argument("--start_date", type=str, default="2025-08-01")
    parser.add_argument("--end_date", type=str, default="2025-10-31")
    opt = parser.parse_args()
    print(opt)

    ROUTEID, DIRECTION, START_DATE, END_DATE = opt.routeid, opt.direction, opt.start_date, opt.end_date

    """
    抓取路徑、時刻表、經緯度會需要起程站名稱，故先從每日行程表中抓取對應路線的起程站名稱
    """
    df = pd.read_csv("./Info/v_stg_ibus_dailytimetable.csv")
    query = (df["routeid"] == ROUTEID) & (df["direction"] == DIRECTION)
    DEPARTSTOP = df[query]["departurestopname_zh_tw"].unique()[0]

    """
    根據上方存取的資訊(路線編號、方向、起程站、開始以及結束日期)，抓取從星期一至星期日的資訊
    """
    for day in range(1, 8):
        RealTimeStastic(ROUTEID, DIRECTION, DEPARTSTOP, str(day), START_DATE, END_DATE).realTimeStastic()
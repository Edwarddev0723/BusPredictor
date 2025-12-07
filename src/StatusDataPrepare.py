import argparse
import os
import pandas as pd
from GetInfo import BusSechudleInfo, RouteRealTime
from Tool import FindClosestTime
from openpyxl import Workbook
from Tool import  GetCarID, isValid, GetGroundTruth, InitKmeansCenter, GetKmeans

if __name__ == "__main__":
    """
    針對路線、方向、星期幾去整理對應的GRU訓練集
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--routeid", type=int)
    parser.add_argument("--direction", type=int)
    parser.add_argument("--day", type=str)
    parser.add_argument("--start_date", type=str, default="2025-08-01")
    parser.add_argument("--end_date", type=str, default="2025-10-31")
    opt = parser.parse_args()
    print(opt)

    ROUTEID, DIRECTION, DAY, START_DATE, END_DATE = opt.routeid, opt.direction, opt.day, opt.start_date, opt.end_date

    StatusWB = Workbook()
    StatusWS = StatusWB.active
    StatusWS.append(["Index", "KmeansCenter1", "KmeansCenter2", "GroundTruth", "Status"])

    """
    這部分程式碼跟StatisticDataPrepare.py 檔案是一樣的，
    1. 先抓取起程站資訊
    2. 根據起程站點將時刻表以及路線資訊取出。
    3. 針對不同的星期，取出整理好的dict
    格式:
    {20251001: df1, 20251008: df2, ...}
    """
    df = pd.read_csv("./Info/v_stg_ibus_dailytimetable.csv")
    query = (df["routeid"] == ROUTEID) & (df["direction"] == DIRECTION)
    DEPARTSTOP = df[query]["departurestopname_zh_tw"].unique()[0]

    if int(DAY) <= 5: busSechudleInfo = BusSechudleInfo(ROUTEID, DIRECTION, "2025-07-25 00:00:00.000", DEPARTSTOP)
    else: busSechudleInfo = BusSechudleInfo(ROUTEID, DIRECTION, "2025-07-26 00:00:00.000", DEPARTSTOP)
    TimeTable = busSechudleInfo.GetTimeTable()
    RouteTable = busSechudleInfo.GetRouteInfo()

    RealTimeDFDict = RouteRealTime(ROUTEID, DIRECTION, DAY, START_DATE, END_DATE).GetRealTimeDF()

    """
    建立對應資料夾，用於後續的資料新增
    """
    if not os.path.exists(f"ststus_dataset/{ROUTEID}/{DIRECTION}"):
        os.makedirs(f"status_dataset/{ROUTEID}/{DIRECTION}")

    """
    初始化kmeans表格，避免重複讀取資料
    """
    KmeansGroup1, KmeansGroup2 = InitKmeansCenter(ROUTEID, DAY, DIRECTION)

    """
    開始進行資料整理, 迴圈順序為日期 ===> 時刻表 ===> 每一個站點
    """
    for DATE in RealTimeDFDict.keys():
        RealTimeDF = RealTimeDFDict[DATE]
        RealTimeDF["gpstime"] = pd.to_datetime(RealTimeDF["gpstime"]).dt.tz_localize(None)
        RealTimeDF["gpstime"] = RealTimeDF["gpstime"].dt.time

        for SechudleIndex, SechudleTime in enumerate(TimeTable[0:1]):
            carID = GetCarID(RealTimeDF, SechudleTime, ROUTEID, DIRECTION)
            if carID == -1: continue
            PreviousStopDepartTime = f"{SechudleTime}:00"

            for CurrentStop in range(1, len(RouteTable)):
                """
                看當前站有沒有離站時間
                1. 如果沒有則代表沒有辦法跟其他站點計算GroundTruth(進站-離站)，直接跳過迴圈
                """
                DepartQuery = (RealTimeDF["routeid"] == ROUTEID) & (RealTimeDF["direction"] == DIRECTION) & (RealTimeDF["stopsequence"] == CurrentStop) & (RealTimeDF["a2eventtype"] == 0) & (RealTimeDF["platenumb"] == carID)
                DepartResult = RealTimeDF[DepartQuery]["gpstime"].tolist()
                DepartResult = [str(time) for time in DepartResult]

                if not isValid(PreviousStopDepartTime, DepartResult, 1): DepartResult = []

                if len(DepartResult) != 0:
                    CurrentStopDepartTime = DepartResult[FindClosestTime(PreviousStopDepartTime, DepartResult)]
                    PreviousStopDepartTime = CurrentStopDepartTime
                else:
                    continue

                GroundTruth = GetGroundTruth(ROUTEID, DIRECTION, CurrentStop+1, carID, CurrentStopDepartTime, RealTimeDF)
                KmeansCenter1, KmeansCenter2 = GetKmeans(KmeansGroup1, KmeansGroup2, CurrentStop, CurrentStop+1, SechudleIndex)

                if abs(KmeansCenter1[0]-GroundTruth) < abs(KmeansCenter2[0]-GroundTruth):
                    StatusWS.append([f"{DATE}-第{SechudleIndex+1}班-第{CurrentStop}站", KmeansCenter1[0], KmeansCenter2[0], GroundTruth, 1])
                else:
                    StatusWS.append([f"{DATE}-第{SechudleIndex+1}班-第{CurrentStop}站", KmeansCenter1[0], KmeansCenter2[0], GroundTruth, 2])

        StatusWB.save(f"status_dataset/{ROUTEID}/{DIRECTION}/status_{ROUTEID}_{DIRECTION}_{DAY}.xlsx")
        print(f"{DATE} 儲存完成")
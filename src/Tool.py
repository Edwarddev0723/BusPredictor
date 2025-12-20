import pandas as pd
import numpy as np
import os
import googlemaps
from datetime import datetime
from openpyxl import Workbook, load_workbook
from PredictedStatus import predict_next_status
from GetInfo import BusSechudleInfo

"""
計算兩個時間的差距
"""
def CalDiffTime(time1, time2):
    t1 = datetime.strptime(time1, "%H:%M:%S")
    t2 = datetime.strptime(time2, "%H:%M:%S")

    if t1 <= t2: diff = t2 - t1
    else: diff = t1 - t2

    return diff.total_seconds()

"""
找出最近的時間
departTime: str
timeIntervalResult: list[str]
"""
def FindClosestTime(departTime, timeIntervalResult):
    diff = [CalDiffTime(departTime, time) for time in timeIntervalResult]
    return diff.index(min(diff))

"""
找出對應的車次編號
departTime: str
updateTimes: list[str]
"""
def FindCarIDIndex(departTime, updateTimes):
    diff = [CalDiffTime(departTime, updateTime) for updateTime in updateTimes]
    if len(diff) == 0:
        return -1
    else:
        return diff.index(min(diff))

"""
檢查搜尋結果中，是否存在目標時間
BaseTime: str
CheckedTimeList: list[str]

609 threshold ===> 1800s
100、90 threshold ===> 600s
"""
def checkLessThanThreshold(BaseTime, CheckedTimeList):
    result = [CalDiffTime(BaseTime, time)<600 for time in CheckedTimeList]
    """
    如果false數量等同於串列長度，代表所有東西都超出閥值，600===> 10分鐘
    """
    return result.count(False) == len(CheckedTimeList)

"""
判斷進站離站結果是否合法
609 ===> 1800s、4800s
100、90 ===> 600s、3600s
"""
def isValid(BaseTime, CheckedTimeList, ThresHold_Type):
    """
    這裡是要根據不同的情況去設置不同的閥值
    1. 如果是近程，例如判斷前一站跟當前站 ===> 600s
    2. 如果是遠程，最後一站跟當前站 ===> 3600s
    (數值部分都可以自己在調整看看)
    """
    if ThresHold_Type == 1:
        ThresHold = 600
    else:
        ThresHold = 3600

    for time in CheckedTimeList:
        if CalDiffTime(BaseTime, time) < ThresHold:
            return True

    return False

"""
初始化歷史行駛時間表
"""
def InitHistoryDriveTimeTable(ROUTEID, DAY, DIRECTION, DEPARTSTOP):
    stastic_driveTime = pd.read_excel(f"StatisticResult/{ROUTEID}/drivetime_result_{ROUTEID}_{DAY}_{DIRECTION}.xlsx")
    InitHistoryDriveTimeList = []

    """
    看缺值，如果真的有出現，就用google api 將數值補上
    """
    for index in range(len(stastic_driveTime)):
        certain_sechudle_driveTime = stastic_driveTime.iloc[index].to_list()[1:]
        Lon, Lat = BusSechudleInfo(ROUTEID, DIRECTION, "2025-07-25 00:00:00.000", DEPARTSTOP).GetLonLatInfo()

        for idx in range(len(certain_sechudle_driveTime)): 
            if np.isnan(certain_sechudle_driveTime[idx]):
                departStop = (Lat[idx-1], Lon[idx-1])
                destinationStop = (Lat[idx], Lon[idx])
                """
                下面的金耀之後要改成你的
                """
                gmaps = googlemaps.Client(key="")
                result = gmaps.distance_matrix(departStop, destinationStop, mode="driving", departure_time="now")
                duration = result['rows'][0]['elements'][0]['duration']['value']
                certain_sechudle_driveTime[idx] = duration 

        InitHistoryDriveTimeList.append(certain_sechudle_driveTime)

    return InitHistoryDriveTimeList

"""
取出對應的車次編號
"""
def GetCarID(RealTimeDF, SechudleTime,  ROUTEID, DIRECTION):
    carIDQuery = (RealTimeDF["routeid"] == ROUTEID) & (RealTimeDF["direction"] == DIRECTION) & (RealTimeDF["stopsequence"] == 1) & (RealTimeDF["a2eventtype"] == 0)
    carID_DF = RealTimeDF[carIDQuery]
    carIDIndex = FindCarIDIndex(f"{SechudleTime}:00", carID_DF["gpstime"].apply(str))
    """
    沒有對應的結果
    """
    if carIDIndex == -1: return -1
    carID = carID_DF.iloc[carIDIndex]["platenumb"]
    return carID

"""
取出歷史的統計行駛時間
"""
def GetStasticDriveTime(HistoryDriveTimeTable, CURRENTSTOP, AFTERSTOP, testSechudleIndex):
    certain_sechudle_driveTime = HistoryDriveTimeTable[testSechudleIndex]
    totalDriveTime_of_eachStop = certain_sechudle_driveTime[CURRENTSTOP: AFTERSTOP]

    return totalDriveTime_of_eachStop

"""
取出歷史的統計等待時間
"""
def GetHistoryStayTime(ROUTEID, DAY, DIRECTION, CurrentStopIndex, testSechudleIndex):
    stastic_stayTime = pd.read_excel(f"StatisticResult/{ROUTEID}/staytime_result_{ROUTEID}_{DAY}_{DIRECTION}.xlsx")
    history_stasticStayTime = stastic_stayTime.iloc[testSechudleIndex].to_list()[CurrentStopIndex]

    return history_stasticStayTime

"""
取出公車當前站的離站跟前一站的離站的差值
"""
def GetGroundTruth(ROUTEID, DIRECTION, AfterStop, carID, CurrentStopDepartTime, RealTimeDF):
    ArrivalQuery = (RealTimeDF["routeid"] == ROUTEID) & (RealTimeDF["direction"] == DIRECTION) & (RealTimeDF["stopsequence"] == AfterStop) & (RealTimeDF["a2eventtype"] == 1) & (RealTimeDF["platenumb"] == carID)
    ArrivalResult = RealTimeDF[ArrivalQuery]["gpstime"].tolist()
    ArrivalResult = [str(time) for time in ArrivalResult]

    if not isValid(CurrentStopDepartTime, ArrivalResult, 2): ArrivalResult = []

    if len(ArrivalResult) != 0:
        ArrivalTime = ArrivalResult[FindClosestTime(CurrentStopDepartTime, ArrivalResult)]
        return CalDiffTime(CurrentStopDepartTime, ArrivalTime)
    else:
        return 0

"""
取出公車當前(GroundTruth)以及歷史行駛時間的比例
"""
def GetRatio(ROUTEID, DIRECTION, CurrentStop, carID, CurrentStopDepartTime, RealTimeDF, testSechudleIndex, HistoryDriveTimeTable):
    """
    首先先取得前一站的離站時間以及當前站的到站時間，求前面一段的行駛時間(GroundTruth)。
    第一站: 則直接回傳比例1
    沒有近離站時間: 同樣回傳比例1
    """
    if CurrentStop == 1: return 1.0

    ArrivalQuery = (RealTimeDF["routeid"] == ROUTEID) & (RealTimeDF["direction"] == DIRECTION) & (RealTimeDF["stopsequence"] == CurrentStop) & (RealTimeDF["a2eventtype"] == 1) & (RealTimeDF["platenumb"] == carID)
    ArrivalResult = RealTimeDF[ArrivalQuery]["gpstime"].tolist()
    ArrivalResult = [str(time) for time in ArrivalResult]

    DepartQuery = (RealTimeDF["routeid"] == ROUTEID) & (RealTimeDF["direction"] == DIRECTION) & (RealTimeDF["stopsequence"] == CurrentStop-1) & (RealTimeDF["a2eventtype"] == 0) & (RealTimeDF["platenumb"] == carID)
    DepartResult = RealTimeDF[DepartQuery]["gpstime"].tolist()
    DepartResult = [str(time) for time in DepartResult]

    if not isValid(CurrentStopDepartTime, ArrivalResult, 2): ArrivalResult = []
    if not isValid(CurrentStopDepartTime, DepartResult, 2): DepartResult = []

    if len(ArrivalResult) != 0  and len(DepartResult) != 0:
        ArrivalTime = ArrivalResult[FindClosestTime(CurrentStopDepartTime, ArrivalResult)]
        DepartTime = DepartResult[FindClosestTime(CurrentStopDepartTime, DepartResult)]
        GroundTruth = CalDiffTime(DepartTime, ArrivalTime)
    else:
        return 1.0
    
    """
    再來要計算出歷史的行駛時間，可以直接查表
    """
    HistoryDriveTime = sum(GetStasticDriveTime(HistoryDriveTimeTable, CurrentStop-1, CurrentStop, testSechudleIndex))
    if HistoryDriveTime == 0 or GroundTruth == 0:
        return 1.0
    
    """
    回傳計算結果
    """
    return GroundTruth / HistoryDriveTime

"""
初始化一個kmeans二維串列
"""
def InitKmeansCenter(ROUTEID, DAY, DIRECTION):
    KmeansGroup1, KmeansGroup2 = [], []
    KmeansList = pd.read_excel(f"StatisticResult/{ROUTEID}/Kmeans_drivetime_result_{ROUTEID}_{DAY}_{DIRECTION}.xlsx")
    for index in range(len(KmeansList)):
        Sechudle_based_KmenasCenter = KmeansList.iloc[index].to_list()[1:]
        # 17.5, 22.3 ===> ['17.5', '22.3']
        Sechudle_based_KmenasCenter = list(map(lambda x: str(x).split(", "), Sechudle_based_KmenasCenter))
        Transposed_KmeansCenter = [list(x) for x in zip(*Sechudle_based_KmenasCenter)]
        kmeans1, kmeans2 = Transposed_KmeansCenter
        kmeans1 = list(map(float, kmeans1))
        kmeans2 = list(map(float, kmeans2))

        KmeansGroup1.append(kmeans1)
        KmeansGroup2.append(kmeans2)
    
    return KmeansGroup1, KmeansGroup2

"""
取出kmeans中心點
"""
def GetKmeans(KmeansGroup1, KmeansGroup2, CURRENTSTOP, AFTERSTOP, testSechudleIndex):
    Sechudle_based_Kmeans1 = KmeansGroup1[testSechudleIndex]
    totalKmeans1 = Sechudle_based_Kmeans1[CURRENTSTOP: AFTERSTOP]
    Sechudle_based_Kmeans2 = KmeansGroup2[testSechudleIndex]
    totalKmeans2 = Sechudle_based_Kmeans2[CURRENTSTOP: AFTERSTOP]

    return totalKmeans1, totalKmeans2

"""
根據IQR取的對應的範圍
"""
def GetIQR(ROUTEID, DAY, DIRECTION, CURRENTSTOP, AFTERSTOP, testSechudleIndex):
    DriveTimeIQR = pd.read_excel(f"StatisticResult/{ROUTEID}/Iqr_drivetime_result_{ROUTEID}_{DAY}_{DIRECTION}.xlsx")
    certain_sechudle_driveTime_iqr = DriveTimeIQR.iloc[testSechudleIndex].to_list()[1:]
    totalIQR = sum(certain_sechudle_driveTime_iqr[CURRENTSTOP: AFTERSTOP])

    DriveTimeMid = pd.read_excel(f"StatisticResult/{ROUTEID}/median_drivetime_result_{ROUTEID}_{DAY}_{DIRECTION}.xlsx")
    certain_sechudle_driveTime_mid = DriveTimeMid.iloc[testSechudleIndex].to_list()[1:]
    totalMid = sum(certain_sechudle_driveTime_mid[CURRENTSTOP: AFTERSTOP])

    return totalMid + 1.5 * totalIQR, totalMid - 1.5 * totalIQR

"""
預測接下來的狀態(屬於哪一群)
"""
def PredictedStatus(HDriveTime, KmeansCenter1, KmeansCenter2, BusStatus, Routeid, model, device, default, k):
    #建立一個結果串列
    PredictedResult = []
    # 先複製原先串列
    BusStatus_Copy = BusStatus.copy()
    # 根據KmeansCenter長度進行traversal
    for index in range(len(KmeansCenter1)):
        Predicted = predict_next_status(model, device, BusStatus_Copy, Routeid)

        if abs(KmeansCenter1[index] - KmeansCenter2[index]) >= k and Predicted == 3:
            if default == 1:
                PredictedResult.append(KmeansCenter1[index])
            elif default == 2:
                PredictedResult.append(KmeansCenter2[index])
            # 如果兩群相差過大，不可能預測3(代表沒差異)，這時候需要修正預測
            Predicted = default
            BusStatus_Copy.append(Predicted)
        
        elif abs(KmeansCenter1[index] - KmeansCenter2[index]) >= k and Predicted != 3:
            if Predicted == 1:
                PredictedResult.append(KmeansCenter1[index])
            else:
                PredictedResult.append(KmeansCenter2[index])
            BusStatus_Copy.append(Predicted)

        else:
            PredictedResult.append(HDriveTime[index])
            BusStatus_Copy.append(3)

    return PredictedResult

"""
將推論結果儲存到excel表中，之後再做簡報會比較方便一些...
"""
def StoredResult(ResultList1, ResultList2, ResultList3):
    if not os.path.exists("inference_acc.xlsx"):
        FileWB = Workbook()
        for index in range(1, 4):
            FileWS = FileWB.create_sheet(title=f"{index}")
        FileWB.save("inference_acc.xlsx")

    FileWB = load_workbook("inference_acc.xlsx")

    for index, ResultList in enumerate([ResultList1, ResultList2, ResultList3], start=1):
        if index == 3:
            total, correct_10, correct_20, correct_30, correct_60, correct_120, correct_300 = ResultList
        else:
            total, correct_10, correct_20, correct_30, correct_60, correct_120 = ResultList

        if total == 0: continue
        FileWS = FileWB[f"{index}"]
        Result_10 = f"{round(correct_10/ total, 4)}/ {correct_10}"
        Result_20 = f"{round((correct_20 / total) - (correct_10/ total), 4)}/ {correct_20 - correct_10}"
        Result_30 = f"{round((correct_30 / total) - (correct_20/ total), 4)}/ {correct_30 - correct_20}"
        Result_60 = f"{round((correct_60 / total) - (correct_30/ total), 4)}/ {correct_60 - correct_30}"
        Result_120 = f"{round((correct_120 / total) - (correct_60/ total), 4)}/ {correct_120 - correct_60}"

        if index ==3:
            Result_300 = f"{round((correct_300 / total) - (correct_120/ total), 4)}/ {correct_300 - correct_120}"
            Result_others = f"{round(1 - (correct_300/ total), 4)}/ {total - correct_300}"
            FileWS.append([total, Result_10, Result_20, Result_30, Result_60, Result_120, Result_300, Result_others])
        else:
            Result_others = f"{round(1 - (correct_120/ total), 4)}/ {total - correct_120}"
            FileWS.append([total, Result_10, Result_20, Result_30, Result_60, Result_120, Result_others])
        
    FileWB.save("inference_acc.xlsx")
    print("預測完成...")
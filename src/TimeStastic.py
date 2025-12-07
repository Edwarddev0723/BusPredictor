import pandas as pd
import numpy as np
import os
import warnings
from openpyxl import Workbook
from sklearn.cluster import KMeans
from sklearn.exceptions import ConvergenceWarning

"""
公車所需的資訊如路線圖、時程表、站點的順序都是分散在不同的檔案中的，因此在GetInfo.py有兩個類別，負責處理上述需求
BusSechudleInfo ===> 負責抓取對應的路線表以及時刻表
RouteRealTime ===> 負責將對應路線、方向的每一筆資料，按照不同的日期進行整理，下方會在補充資料格式
"""
from GetInfo import BusSechudleInfo, RouteRealTime
"""
程式所需的工具會存放在Tool.py這一個檔案
1. CalDiffTime ===> 計算兩個時間字串之間的差值
2. FindClosestTime ===> 不同的車次可能在不同的時間都會有行駛，因此要根據錨點抓取對應的時刻
3. FindCarIDIndex ===> 找出對應行駛的車次
"""
from Tool import CalDiffTime, FindClosestTime, FindCarIDIndex, checkLessThanThreshold

class RealTimeStastic():
    def __init__(self, routeid, direction, departStop, day, start_date, end_date):
        self.routeid = routeid
        self.direction = direction
        self.departStop = departStop
        self.day = day
        self.start_date = start_date
        self.end_date = end_date

    def nomalization(self, BusRecord):
        warnings.filterwarnings("ignore", category=ConvergenceWarning)

        if int(self.day) <= 5: busSechudleInfo = BusSechudleInfo(self.routeid, self.direction, "2025-07-25 00:00:00.000", self.departStop)
        else: busSechudleInfo = BusSechudleInfo(self.routeid, self.direction, "2025-07-26 00:00:00.000", self.departStop)
        TimeTable = busSechudleInfo.GetTimeTable()
        RouteTable = busSechudleInfo.GetRouteInfo()

        BusRecord = np.array(BusRecord)

        """8
        輸出表格，用來看哪一種方法比較好
        1. 計算Q1、Q2、Q3 ===> 計算IQR ===> 剔除離群值 ===> 計算平均數
        補充: 方法一後續有在接上kmeans，用來將剔除離群值後的資料分成兩群
        2. 剔除前後10個百分比 ===> 計算平均數
        3. 計算平均值 ===> 計算標準差 ===> 剔除離群值 ===> 計算平均數
        """
        OutputWB = Workbook()
        OutputWS = OutputWB.active
        OutputWS.append(["班次&站點", "原始串列", "原始串列(排序)", "方法一結果(串列)", "方法一平均", "Kmeas(第一群)", "Kmeans(第二群)", "兩群中心"])

        AvgResult, MidResult, IQRResult, KmeansResult = [], [], [], []

        for sechudle in range(len(TimeTable)):
            AvgRow, MidRow, IQRRow, KmeansRow = [], [], [], []

            for stop in range(len(RouteTable)):
                """
                取出不同日期但相同時段相同站的每一個數值，並將上述串列剃除nan值
                """
                Values = BusRecord[:, sechudle, stop]
                CleanValues = Values[~np.isnan(Values)]
                """
                檢查串列長度是否為0
                """
                if len(CleanValues) != 0:
                    # 方法一
                    SortedList = np.sort(CleanValues)
                    Q1 = np.percentile(SortedList, 25)
                    Q2 = np.median(SortedList)
                    Q3 = np.percentile(SortedList, 75)
                    IQR = Q3 - Q1
                    lowerBound, upperBound = Q2 - 1.5 * IQR, Q2 + 1.5 * IQR
                    MethodOneInterval = SortedList[(SortedList >= lowerBound) & (SortedList <= upperBound)]
                    MethodOneAvg = float(np.sum(MethodOneInterval) / len(MethodOneInterval))

                    # Kmeans 
                    ReshapedData = MethodOneInterval.reshape(-1, 1)
                    Q3_KM = np.percentile(MethodOneInterval, 75)
                    Q1_KM = np.percentile(MethodOneInterval, 25)
                    n_cluster = min(len(MethodOneInterval), 2)
                    
                    if n_cluster < 2:
                        FirstGroup = MethodOneInterval.tolist()
                        SecondGroup = []
                        Centers = [round(Q1_KM, 2), round(Q3_KM, 2)]
                    else:
                        initial_centers = np.array([[Q1_KM], [Q3_KM]])

                        kmeans = KMeans(n_clusters=n_cluster, init=initial_centers, n_init=1, random_state=0)
                        kmeans.fit(ReshapedData)
                        FirstGroup = MethodOneInterval[kmeans.labels_ == 0].tolist()
                        SecondGroup = MethodOneInterval[kmeans.labels_ == 1].tolist()
                        Centers = kmeans.cluster_centers_.flatten().tolist()
                        Centers = list(map(lambda x: round(x, 2), Centers))
                    
                    OrginalList = ", ".join(list(map(str, CleanValues.tolist())))
                    OrginalSortList = ", ".join(list(map(str, sorted(CleanValues.tolist()))))
                    MethodOneInterval = ", ".join(list(map(str, MethodOneInterval.tolist())))

                    FirstGroup = ", ".join(list(map(str, FirstGroup)))
                    SecondGroup = ", ".join(list(map(str, SecondGroup)))
                    Centers = ", ".join(list(map(str, Centers)))

                    OutputWS.append([f"第{sechudle+1}班_第{stop}站", 
                                     OrginalList, 
                                     OrginalSortList,
                                     MethodOneInterval, 
                                     round(MethodOneAvg, 2),
                                     FirstGroup,
                                     SecondGroup,
                                     Centers])

                    AvgRow.append(round(MethodOneAvg, 2))
                    MidRow.append(round(Q2, 2))
                    IQRRow.append(round(IQR, 2))
                    KmeansRow.append(Centers)
                else:
                    AvgRow.append(0)
                    MidRow.append(0)
                    IQRRow.append(0)
                    KmeansRow.append("0.0, 0.0")

            AvgResult.append(AvgRow)
            MidResult.append(MidRow)
            IQRResult.append(IQRRow)
            KmeansResult.append(KmeansRow)
        
        OutputWB.save(f"./StatisticResult/{self.routeid}/StasticOutput_{self.routeid}.xlsx")
        return np.array(AvgResult), np.array(MidResult), np.array(IQRResult), np.array(KmeansResult)

    def realTimeStastic(self):
        """
        平常日跟周末的行程表是不相同的，因此這裡要根據輸送進的星期去產生不同的資訊(時刻、路程)
        """
        if int(self.day) <= 5: busSechudleInfo = BusSechudleInfo(self.routeid, self.direction, "2025-07-25 00:00:00.000", self.departStop)
        else: busSechudleInfo = BusSechudleInfo(self.routeid, self.direction, "2025-07-26 00:00:00.000", self.departStop)

        timeTable = busSechudleInfo.GetTimeTable()
        routeTable = busSechudleInfo.GetRouteInfo()

        """
        這裡要根據不同的路線、方向、星期幾、開始跟結束日期，生成所需的df，以便後續整理
        資料格式:
        {date1: df1, date2: df2, ..., date(N): df(N)}
        """
        dateBasedDF_Dict_day = RouteRealTime(self.routeid, self.direction, self.day, self.start_date, self.end_date).GetRealTimeDF()

        """
        準備開始根據不同的日期，去整理對應的平均數、中位數、標準差等表格，所以先建置兩個串列(後續會變成三維)用於儲存
        """
        allDates_DriveTime, allDates_StayTime = [], []

        for date in dateBasedDF_Dict_day.keys():
            """
            routeBaseDF ===> 根據不同日期所取出的df
            不過因為A2資料中存放的時間資料不是我們想要的格式，所以先行將其轉時區以及變成"H:M:S"格式
            """
            routeBaseDF = dateBasedDF_Dict_day[date]
            routeBaseDF["gpstime"] = pd.to_datetime(routeBaseDF["gpstime"]).dt.tz_localize(None)
            routeBaseDF["gpstime"] = routeBaseDF["gpstime"].dt.time

            """
            現在要根據每一個不同的班次(05:15, 05:40, ..., 22:10)去抓取每站的進站離站時間，因此再另外建置兩個串列(目標二維)用於儲存
            """
            dayBasedSpentTime, dayBasedStayTime = [], []

            for timeIndex in range(len(timeTable)): 
                """
                後續防呆需要使用到的變數，如果之後資料變得更加充足之後，可以考慮將其刪除
                """
                flag = False
                recordIndex = 1

                try:
                    """
                    首先在開始抓資料之前，要先找出該班次的車牌號碼，用於之後的條件設置(才不會05:15的班次，結果抓成15:15的)
                    條件:
                    1. 路線
                    2. 方向
                    3. 初始站為第一站
                    4. 離站(A2EventType = 0)
                    不過滿足上述條件的其實每一班都有，因此需要應用到FindCarIDIndex這一個函式去找出哪一班次跟目前最近
                    """
                    carIDQuery = (routeBaseDF["routeid"] == self.routeid) & (routeBaseDF["direction"] == self.direction) & (routeBaseDF["stopsequence"] == 1) & (routeBaseDF["a2eventtype"] == 0)
                    carID_DF = routeBaseDF[carIDQuery]

                    sechudleTime = timeTable[timeIndex]
                    carIDIndex = FindCarIDIndex(f"{sechudleTime}:00", carID_DF["gpstime"].apply(str))
                    carID = carID_DF.iloc[carIDIndex]["platenumb"]
                    
                    """
                    接下來任務: 要在這一班次上，一直不斷的更新其一站的離站時間(錨點)，避免抓取的資料跑成其他班次的
                    所以在初始化階段，要先取出第一站的進站以及離站資料
                    另外下方的checkLessThanThreshold功能，主要是判斷當前目前抓出來的數值是否有我們想要的目標
                    就如同剛才所說的，相同車次可能在不同時間都有行駛，所以要根據出發的預訂時刻表(錨點)，找出對應的離站時間
                    """
                    arrivalTimeQuery = (routeBaseDF["routeid"] == self.routeid) & (routeBaseDF["direction"] == self.direction) & (routeBaseDF["stopsequence"] == 1) & (routeBaseDF["a2eventtype"] == 1) & (routeBaseDF["platenumb"] == carID)
                    arrivalTimeResult = routeBaseDF[arrivalTimeQuery]["gpstime"].tolist()
                    arrivalTimeResult = [str(time) for time in arrivalTimeResult]
                    arrivalTime = arrivalTimeResult[FindClosestTime(f"{sechudleTime}:00", arrivalTimeResult)]

                    departTimeQuery = (routeBaseDF["routeid"] == self.routeid) & (routeBaseDF["direction"] == self.direction) & (routeBaseDF["stopsequence"] == 1) & (routeBaseDF["a2eventtype"] == 0) & (routeBaseDF["platenumb"] == carID)
                    departTimeResult = routeBaseDF[departTimeQuery]["gpstime"].tolist()
                    departTimeResult = [str(time) for time in departTimeResult]

                    if checkLessThanThreshold(f"{sechudleTime}:00", departTimeResult): departTimeResult = []

                    if len(departTimeResult) != 0:
                        """
                        有資料 ===> 計算停站時間(StayTime)，第一站不計算行駛時間(預設0)，更新前一站的離站時間(錨點)
                        """
                        departTime = departTimeResult[FindClosestTime(f"{sechudleTime}:00", departTimeResult)]
                        spentList, stayList = [0], [CalDiffTime(departTime, arrivalTime)]
                        previous_DepartTime = departTime
                    else:
                        """
                        沒資料 ===> 等待時間設為0並將前一站離站時間(錨點)設為預訂時刻表
                        """
                        previous_DepartTime = f"{sechudleTime}:00"
                        spentList, stayList = [0], [0]

                    """
                    從第二站開始抓，抓到最後一站，步驟相同
                    """
                    for stopIndex in range(2, len(routeTable)+1):
                        arrivalTimeQuery = (routeBaseDF["routeid"] == self.routeid) & (routeBaseDF["direction"] == self.direction) & (routeBaseDF["stopsequence"] == stopIndex) & (routeBaseDF["a2eventtype"] == 1) & (routeBaseDF["platenumb"] == carID)
                        arrivalTimeResult = routeBaseDF[arrivalTimeQuery]["gpstime"].tolist()
                        arrivalTimeResult = [str(time) for time in arrivalTimeResult]

                        departTimeQuery = (routeBaseDF["routeid"] == self.routeid) & (routeBaseDF["direction"] == self.direction) & (routeBaseDF["stopsequence"] == stopIndex) & (routeBaseDF["a2eventtype"] == 0) & (routeBaseDF["platenumb"] == carID)
                        departTimeResult = routeBaseDF[departTimeQuery]["gpstime"].tolist()
                        departTimeResult = [str(time) for time in departTimeResult]

                        if checkLessThanThreshold(previous_DepartTime, departTimeResult): departTimeResult = []
                        if checkLessThanThreshold(previous_DepartTime, arrivalTimeResult): arrivalTimeResult = []

                        """
                        進佔跟離站不見的都依定會存在，所以要做剛剛提到的防呆
                        1. 同時有資料 ===> 正常計算行駛時間、等待時間
                        2. 兩個都沒有 ===> 行駛跟等待時間都以0替代
                        3. 沒有離站 ===> 正常計算行駛時間，等待時間以0替代
                        4. 沒有進站 ===> 以離站時間替代進站時間計算行駛時間，等待時間以0替代
                        """
                        if len(departTimeResult) != 0 and len(arrivalTimeResult) != 0:
                            departTime = departTimeResult[FindClosestTime(previous_DepartTime, departTimeResult)]
                            arrivalTime = arrivalTimeResult[FindClosestTime(previous_DepartTime, arrivalTimeResult)]

                            spentList.append(CalDiffTime(arrivalTime, previous_DepartTime) if not flag else CalDiffTime(arrivalTime, previous_DepartTime) / (stopIndex - recordIndex))
                            stayList.append(CalDiffTime(departTime, arrivalTime))
                            previous_DepartTime = departTime

                            flag = False
                            recordIndex = stopIndex

                        else:
                            if len(arrivalTimeResult) == 0 and len(departTimeResult) == 0:
                                spentList.append(np.nan)
                                stayList.append(0)
                                flag = True
                            elif len(departTimeResult) == 0:
                                arrivalTime = arrivalTimeResult[FindClosestTime(previous_DepartTime, arrivalTimeResult)]
                                spentList.append(CalDiffTime(arrivalTime, previous_DepartTime) if not flag else CalDiffTime(arrivalTime, previous_DepartTime) / (stopIndex - recordIndex))
                                stayList.append(0)
                                previous_DepartTime = arrivalTime
                                flag = False
                                recordIndex = stopIndex
                            elif len(arrivalTimeResult) == 0:
                                departTime = departTimeResult[FindClosestTime(previous_DepartTime, departTimeResult)]
                                spentList.append(CalDiffTime(departTime, previous_DepartTime) if not flag else CalDiffTime(arrivalTime, previous_DepartTime) / (stopIndex - recordIndex))
                                stayList.append(0)
                                previous_DepartTime = departTime
                                flag = False
                                recordIndex = stopIndex
                    """
                    完成一個班次的存取，將其加入到剛剛的二維串列中
                    """
                    dayBasedSpentTime.append(spentList)
                    dayBasedStayTime.append(stayList)

                except Exception as e:
                    """
                    還是有可能會都抓不到，所以沒有的話就直接補nan進去八...
                    """
                    dayBasedSpentTime.append([np.nan] * len(routeTable))
                    dayBasedStayTime.append([np.nan] * len(routeTable))
                    continue

            """
            將上述步驟處理完成的二維串列加入到三維串列中，用於後續的平均值、中位數、標準差計算
            """
            allDates_DriveTime.append(dayBasedSpentTime)
            allDates_StayTime.append(dayBasedStayTime)  


        AvgDriveTime, MidDriveTime, IqrDriveTime, KmeansDriveTime = self.nomalization(allDates_DriveTime)
        AvgStayTime, MidStayTime, IqrStayTime, KmeansStayTime = self.nomalization(allDates_StayTime)

        if not os.path.exists(f"StatisticResult/{self.routeid}"): os.makedirs(f"StatisticResult/{self.routeid}")

        result = pd.DataFrame(AvgDriveTime, columns=routeTable[:len(routeTable)])
        result.to_excel(f"StatisticResult/{self.routeid}/drivetime_result_{self.routeid}_{self.day}_{self.direction}.xlsx")

        result = pd.DataFrame(AvgStayTime, columns=routeTable[:len(routeTable)])
        result.to_excel(f"StatisticResult/{self.routeid}/staytime_result_{self.routeid}_{self.day}_{self.direction}.xlsx")

        result = pd.DataFrame(MidDriveTime, columns=routeTable[:len(routeTable)])
        result.to_excel(f"StatisticResult/{self.routeid}/median_drivetime_result_{self.routeid}_{self.day}_{self.direction}.xlsx")

        result = pd.DataFrame(MidStayTime, columns=routeTable[:len(routeTable)])
        result.to_excel(f"StatisticResult/{self.routeid}/median_staytime_result_{self.routeid}_{self.day}_{self.direction}.xlsx")

        result = pd.DataFrame(IqrDriveTime, columns=routeTable[:len(routeTable)])
        result.to_excel(f"StatisticResult/{self.routeid}/Iqr_drivetime_result_{self.routeid}_{self.day}_{self.direction}.xlsx")

        result = pd.DataFrame(IqrStayTime, columns=routeTable[:len(routeTable)])
        result.to_excel(f"StatisticResult/{self.routeid}/Iqr_staytime_result_{self.routeid}_{self.day}_{self.direction}.xlsx")

        result = pd.DataFrame(KmeansDriveTime, columns=routeTable[:len(routeTable)])
        result.to_excel(f"StatisticResult/{self.routeid}/Kmeans_drivetime_result_{self.routeid}_{self.day}_{self.direction}.xlsx")

        result = pd.DataFrame(KmeansStayTime, columns=routeTable[:len(routeTable)])
        result.to_excel(f"StatisticResult/{self.routeid}/Kmeans_staytime_result_{self.routeid}_{self.day}_{self.direction}.xlsx")
        
        print("Successfully store to ./result...")
import pandas as pd
from datetime import datetime

"""
輸入:
1. 路線
2. 方向
3. 回報日期(其實不用管他, 因為用7-25, 7-26就可以取出所有的數值了)
4. 起程站

輸出:
1. 時刻表(GetTimeTable)
2. 行經站點(GetRouteInfo)
3. 經緯度資訊(GetLonLatInfo)
"""
class BusSechudleInfo():
    def __init__(self, routeid, direction, reportDate, departureStop):
        self.routeid = routeid
        self.direction = direction
        self.reportDate = reportDate
        self.departureStop = departureStop

    def GetTimeTable(self):
        df = pd.read_csv("./Info/v_stg_ibus_dailytimetable.csv")
        Tablequery = (df["routeid"] == self.routeid) & (df["reportdate"] == self.reportDate) & (df["departurestopname_zh_tw"] == self.departureStop) & (df["direction"] == self.direction)
        TimeTable = df[Tablequery].reset_index(drop=False)["scheduletime"].tolist()
        TimeTable.sort()

        return TimeTable

    def GetRouteInfo(self):
        """
        輸入:
        1. 站牌編號(排序好了)
        2. 站牌名稱(沒有排序)
        
        輸出:
        1. 排序好的站牌名稱
        """
        df = pd.read_csv("./Info/v_stg_tdx_stop2stopdistanceofroute.csv")
        routeQuery = (df["routeid"] == self.routeid) & (df["direction"] == self.direction)
        routeTable = df[routeQuery].reset_index(drop=False)["tostopid"]

        df = pd.read_csv("./Info/v_stg_tdx_stop.csv")
        stopInfoQuery = (df["routeid"] == self.routeid) & (df["direction"] == self.direction)
        stopInfo = df[stopInfoQuery].reset_index(drop=False)[["stopid", "stopname_zh_tw"]]

        routeTable = pd.merge(routeTable, stopInfo, left_on="tostopid", right_on="stopid", how="left")["stopname_zh_tw"].to_list()

        return routeTable
    
    def GetLonLatInfo(self):
        """
        輸入:
        1. 站牌編號(排序好了)
        2. 站牌名稱(沒有排序)
        
        輸出:
        1. 根據站牌排序的經緯度資料
        """
        df = pd.read_csv("./Info/v_stg_tdx_stop2stopdistanceofroute.csv")
        routeQuery = (df["routeid"] == self.routeid) & (df["direction"] == self.direction)
        routeTable = df[routeQuery].reset_index(drop=False)["tostopid"]

        df = pd.read_csv("./Info/v_stg_tdx_stop.csv")
        stopInfoQuery = (df["routeid"] == self.routeid) & (df["direction"] == self.direction)
        stopInfo = df[stopInfoQuery].reset_index(drop=False)[["stopid", "positionlon", "positionlat"]]

        LonLatTable = pd.merge(routeTable, stopInfo, left_on="tostopid", right_on="stopid", how="left")
        LonTable = LonLatTable["positionlon"].tolist()
        LatTable = LonLatTable["positionlat"].to_list()

        return LonTable, LatTable  

"""
根據輸入資訊(路線、方向、日期範圍)，整理每一天的的公車資訊
"""
class RouteRealTime():
    def __init__(self, routeid, direction, day, start_date, end_date):
        self.routeid = routeid
        self.direction = direction
        self.day = day
        self.start_date = start_date
        self.end_date = end_date

    def GetRealTimeDF(self):
        """
        先根據開始日以及結束日，產生這之間所有的日期
        不過pd所產生的格式跟實際檔案的格式是不一樣的，所以需要針對字串進行處理
        """
        allDate = pd.date_range(start=self.start_date, end=self.end_date, freq="D")
        allDate = allDate.strftime("%Y-%m-%d").to_list()
        
        """
        建置一個dict，用於儲存每天(星期一~星期日)各自擁有的日期
        格式:
        {1: [20251001, 25251008, ..., ], 
        2: [20251002, 20251010, ...], ...}
        """
        daybased_Dict = {str(i):[] for i in range(1, 8)}

        for date in allDate:
            day = datetime.strptime(date, "%Y-%m-%d").weekday() + 1
            daybased_Dict[str(day)].append(date)

        print("Integrating DF...")

        """
        建置另外一個dict, 用於儲存每一個經過整理的df
        格式:
        {20251001: df1, 
        20251008: df2, ...}
        """
        dateBasedDF_Dict_day = {}

        """
        new version
        """
        # 如過要換新資料的話，應該要先整合8-10月的所有內容
        StartMonth = self.start_date.split("-")[1]
        EndMonth = self.end_date.split("-")[1]

        InitDF = pd.read_csv(f"A2/v_stg_tdx_realtimenearstop_pt1m_2025{StartMonth}.csv")
        query = (InitDF["routeid"] == self.routeid) & (InitDF["direction"] == self.direction)
        RouteBaseDF = InitDF[query].dropna(subset=["platenumb"]).reset_index(drop=True)

        for month in range(int(StartMonth)+1, int(EndMonth)+1):
            AfterDF = pd.read_csv(f"A2/v_stg_tdx_realtimenearstop_pt1m_2025{str(month).zfill(2)}.csv")
            query = (AfterDF["routeid"] == self.routeid) & (AfterDF["direction"] == self.direction)
            AfterDF = AfterDF[query].dropna(subset=["platenumb"]).reset_index(drop=True)

            RouteBaseDF = pd.concat([RouteBaseDF, AfterDF], ignore_index=True)

        RouteBaseDF["__time"] = RouteBaseDF["__time"].apply(lambda x: x.split(" ")[0])

        # 然後根據(日期、routeid、direction)去將對應的資料抓取對應的df並進行回傳
        for date in daybased_Dict[self.day]:
            query = (RouteBaseDF["__time"] == date)
            dateBasedDF_Dict_day[date] = RouteBaseDF[query].reset_index(drop=True)
            print(f"Date {date} finish...")
        
        print("ALL file finish...")

        return dateBasedDF_Dict_day
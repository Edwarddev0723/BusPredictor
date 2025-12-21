import argparse
import os
import pandas as pd
from datetime import datetime
from openpyxl import Workbook
from Tool import StoredResult

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--routeid", type=int)
    parser.add_argument("--direction", type=int)
    parser.add_argument("--start_date", type=str, default="2025-08-01")
    parser.add_argument("--end_date", type=str, default="2025-10-31")
    parser.add_argument("--day", type=str)
    parser.add_argument("--mode", type=str)

    opt = parser.parse_args()
    print(opt)

    ROUTEID, DIRECTION,  START_DATE, END_DATE, DAY, MODE = opt.routeid, opt.direction, opt.start_date, opt.end_date, opt.day, opt.mode
    total_1, correct_10_1, correct_20_1, correct_30_1, correct_60_1, correct_120_1 = 0, 0, 0, 0, 0, 0
    total_2, correct_10_2, correct_20_2, correct_30_2, correct_60_2, correct_120_2 = 0, 0, 0, 0, 0, 0
    total_3, correct_10_3, correct_20_3, correct_30_3, correct_60_3, correct_120_3, correct_300_3 = 0, 0, 0, 0, 0, 0, 0

    """
    建置對應的存放路經，方便後續檔案存放
    """
    if not os.path.exists(f"inference_result/{ROUTEID}/{DIRECTION}/{MODE}/"):
        os.makedirs(f"inference_result/{ROUTEID}/{DIRECTION}/{MODE}/")

    """
    根據每一站去進行預測
    """
    sheets = pd.ExcelFile(f"training_dataset/{ROUTEID}/{DIRECTION}/dataset_{DAY}.xlsx").sheet_names

    """
    根據給定的日去整理對應的日期
    """
    allDate = pd.date_range(start=START_DATE, end=END_DATE, freq="D")
    allDate = allDate.strftime("%Y-%m-%d").to_list()
    DateOfDay = []
    for date in allDate:
        day = datetime.strptime(date, "%Y-%m-%d").weekday() + 1
        if str(day) == DAY:
            DateOfDay.append(date)
    
    for TEST_DATE in DateOfDay:
        print(f"正在預測 {TEST_DATE} 資料...")
        """
        初始化一個Excel檔案，用來存放結果
        """
        ResultWB = Workbook()

        for sheet in sheets[1:]:
            """
            初始化一個excel檔案，用於進行資料新增
            """
            ResultWS = ResultWB.create_sheet(title=sheet)
            ResultWS.append(["Date", "SechudeleIndex", "h_driveTime", "Ratio", "h_stayTime", "c_stayTime", "GroundTruth", "Predicted"])
            ResultWS.column_dimensions["A"].width = 20
            ResultWS.column_dimensions["B"].width = 20
            ResultWS.column_dimensions["C"].width = 20
            ResultWS.column_dimensions["D"].width = 20
            ResultWS.column_dimensions["E"].width = 20
            ResultWS.column_dimensions["F"].width = 20
            ResultWS.column_dimensions["G"].width = 20
            ResultWS.column_dimensions["H"].width = 20

            for PredictedType in ["-1", "-2", "-other"]:
                """
                抓取對應參數
                """
                ParameterDF = pd.read_excel(f"./training_result/{ROUTEID}/{DIRECTION}/{MODE}/parameters_{DAY}.xlsx")
                Query = (ParameterDF["stop"].str.contains(sheet)) & (ParameterDF["stop"].str.contains(PredictedType))
                ParameterDF = ParameterDF[Query]
                if len(ParameterDF) == 0:
                    continue

                DatasetDF = pd.read_excel(f"training_dataset/{ROUTEID}/{DIRECTION}/dataset_{DAY}.xlsx", sheet_name=sheet)
                Query = (DatasetDF["Date"] == TEST_DATE) & (DatasetDF["SechudeleIndex"].str.contains(PredictedType))
                DatasetDF = DatasetDF[Query]

                """
                根據不同模式進行預測
                """
                for index in range(len(DatasetDF)):
                    Data = DatasetDF.iloc[index]
                    kmeans1, kmeans2, HStayTime, CStayTime, Ratio, HDriveTime, GroundTruth = Data["kmeans1"], Data["kmeans2"], Data["h_stayTime"], Data["c_stayTime"], Data["Ratio"], Data["PredictedDriveTime"], Data["GroundTruth"]
                    
                    if MODE == "a":
                        Predicted = HDriveTime + ParameterDF["alpha"] * HStayTime + (1-ParameterDF["alpha"]) * CStayTime
                    elif MODE == "ac":
                        Predicted = HDriveTime + ParameterDF["alpha"] * HStayTime + (1-ParameterDF["alpha"]) * CStayTime + ParameterDF["constant"]
                    elif MODE == "ar":
                        Predicted = HDriveTime * Ratio + ParameterDF["alpha"] * HStayTime + (1-ParameterDF["alpha"]) * CStayTime
                    elif MODE == "acr":
                        Predicted = HDriveTime * Ratio + ParameterDF["alpha"] * HStayTime + (1-ParameterDF["alpha"]) * CStayTime + ParameterDF["constant"]
                    elif MODE == "c":
                        Predicted = HDriveTime + CStayTime + ParameterDF["constant"]
                    elif MODE == "cr":
                        Predicted = HDriveTime * Ratio + CStayTime + ParameterDF["constant"]
                    elif MODE == "r":
                        Predicted = HDriveTime * Ratio + CStayTime
                    
                    if MODE != "r": Predicted = Predicted.values[0]

                    """
                    計算指標
                    """
                    if GroundTruth != 0 and HDriveTime != 0:
                        if PredictedType == "-1":
                            total_1 += 1
                            if abs(Predicted - GroundTruth) <= 10:
                                correct_10_1 += 1
                            if abs(Predicted - GroundTruth) <= 20:
                                correct_20_1 += 1
                            if abs(Predicted - GroundTruth) <= 30:
                                correct_30_1 += 1
                            if abs(Predicted - GroundTruth) <= 60:
                                correct_60_1 += 1
                            if abs(Predicted - GroundTruth) <= 120:
                                correct_120_1 += 1

                        elif PredictedType == "-2":
                            total_2 += 1
                            if abs(Predicted - GroundTruth) <= 10:
                                correct_10_2 += 1
                            if abs(Predicted - GroundTruth) <= 20:
                                correct_20_2 += 1
                            if abs(Predicted - GroundTruth) <= 30:
                                correct_30_2 += 1
                            if abs(Predicted - GroundTruth) <= 60:
                                correct_60_2 += 1
                            if abs(Predicted - GroundTruth) <= 120:
                                correct_120_2 += 1

                        elif PredictedType == "-other":
                            total_3 += 1
                            if abs(Predicted - GroundTruth) <= 10:
                                correct_10_3 += 1
                            if abs(Predicted - GroundTruth) <= 20:
                                correct_20_3 += 1
                            if abs(Predicted - GroundTruth) <= 30:
                                correct_30_3 += 1
                            if abs(Predicted - GroundTruth) <= 60:
                                correct_60_3 += 1
                            if abs(Predicted - GroundTruth) <= 120:
                                correct_120_3 += 1
                            if abs(Predicted - GroundTruth) <= 300:
                                correct_300_3 += 1

                    ResultWS.append([TEST_DATE, f"{sheet}{PredictedType}", HDriveTime, Ratio, HStayTime, CStayTime, GroundTruth, Predicted])

        ResultWB.save(f"inference_result/{ROUTEID}/{DIRECTION}/{MODE}/result_{TEST_DATE}.xlsx")
        print(f"{TEST_DATE} 預測完成")

    StoredResult([total_1, correct_10_1, correct_20_1, correct_30_1, correct_60_1, correct_120_1], 
                [total_2, correct_10_2, correct_20_2, correct_30_2, correct_60_2, correct_120_2], 
                [total_3, correct_10_3, correct_20_3, correct_30_3, correct_60_3, correct_120_3, correct_300_3],
                routeid=ROUTEID, direction=DIRECTION, day=DAY, mode=MODE)
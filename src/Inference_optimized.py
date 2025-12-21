import argparse
import os
import pandas as pd
from datetime import datetime
from openpyxl import Workbook
from Tool import StoredResult

"""
優化版 Inference.py
- 一次讀取資料，推論所有模式
- 減少重複的 Excel I/O
"""

MODES = ["a", "c", "r", "ac", "ar", "cr", "acr"]

def predict(mode, h_drive, ratio, h_stay, c_stay, alpha, constant):
    """根據模式計算預測值"""
    if mode == "a":
        return h_drive + alpha * h_stay + (1 - alpha) * c_stay
    elif mode == "ac":
        return h_drive + alpha * h_stay + (1 - alpha) * c_stay + constant
    elif mode == "ar":
        return h_drive * ratio + alpha * h_stay + (1 - alpha) * c_stay
    elif mode == "acr":
        return h_drive * ratio + alpha * h_stay + (1 - alpha) * c_stay + constant
    elif mode == "c":
        return h_drive + c_stay + constant
    elif mode == "cr":
        return h_drive * ratio + c_stay + constant
    elif mode == "r":
        return h_drive * ratio + c_stay
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--routeid", type=int, required=True)
    parser.add_argument("--direction", type=int, required=True)
    parser.add_argument("--start_date", type=str, default="2025-08-01")
    parser.add_argument("--end_date", type=str, default="2025-10-31")
    parser.add_argument("--day", type=str, required=True)
    parser.add_argument("--modes", type=str, default="all", help="推論模式，用逗號分隔或 'all'")
    opt = parser.parse_args()
    print(opt)

    ROUTEID, DIRECTION, START_DATE, END_DATE, DAY = opt.routeid, opt.direction, opt.start_date, opt.end_date, opt.day
    
    # 決定要推論的模式
    if opt.modes == "all":
        modes_to_run = MODES
    else:
        modes_to_run = opt.modes.split(",")
    
    # 初始化統計變數 (每個模式獨立)
    stats = {mode: {
        "total_1": 0, "correct_10_1": 0, "correct_20_1": 0, "correct_30_1": 0, "correct_60_1": 0, "correct_120_1": 0,
        "total_2": 0, "correct_10_2": 0, "correct_20_2": 0, "correct_30_2": 0, "correct_60_2": 0, "correct_120_2": 0,
        "total_3": 0, "correct_10_3": 0, "correct_20_3": 0, "correct_30_3": 0, "correct_60_3": 0, "correct_120_3": 0, "correct_300_3": 0
    } for mode in modes_to_run}
    
    # 建立輸出資料夾
    for mode in modes_to_run:
        os.makedirs(f"inference_result/{ROUTEID}/{DIRECTION}/{mode}/", exist_ok=True)
    
    # 一次讀取訓練資料集
    print("載入資料...")
    dataset_path = f"training_dataset/{ROUTEID}/{DIRECTION}/dataset_{DAY}.xlsx"
    xl = pd.ExcelFile(dataset_path)
    sheets = xl.sheet_names[1:]
    
    all_data = {}
    for sheet in sheets:
        all_data[sheet] = pd.read_excel(xl, sheet_name=sheet)
    
    # 一次讀取所有模式的參數
    print("載入訓練參數...")
    parameters = {}
    for mode in modes_to_run:
        param_path = f"./training_result/{ROUTEID}/{DIRECTION}/{mode}/parameters_{DAY}.xlsx"
        if os.path.exists(param_path):
            parameters[mode] = pd.read_excel(param_path)
        else:
            print(f"  警告: 找不到 {param_path}")
            parameters[mode] = None
    
    # 整理日期
    all_dates = pd.date_range(start=START_DATE, end=END_DATE, freq="D")
    all_dates = all_dates.strftime("%Y-%m-%d").to_list()
    dates_of_day = [d for d in all_dates if str(datetime.strptime(d, "%Y-%m-%d").weekday() + 1) == DAY]
    
    print(f"共 {len(dates_of_day)} 天需要推論")
    
    # 為每個模式準備結果 workbook
    result_wbs = {mode: {} for mode in modes_to_run}
    
    for test_date in dates_of_day:
        print(f"處理 {test_date}...")
        
        # 初始化每個模式的 workbook
        for mode in modes_to_run:
            result_wbs[mode][test_date] = Workbook()
        
        for sheet in sheets:
            dataset = all_data[sheet]
            date_data = dataset[dataset["Date"] == test_date]
            
            if len(date_data) == 0:
                continue
            
            # 為每個模式建立 worksheet
            for mode in modes_to_run:
                ws = result_wbs[mode][test_date].create_sheet(title=sheet)
                ws.append(["Date", "SechudeleIndex", "h_driveTime", "Ratio", "h_stayTime", "c_stayTime", "GroundTruth", "Predicted"])
            
            for pred_type in ["-1", "-2", "-other"]:
                type_data = date_data[date_data["SechudeleIndex"].str.contains(pred_type)]
                
                if len(type_data) == 0:
                    continue
                
                for mode in modes_to_run:
                    if parameters[mode] is None:
                        continue
                    
                    # 取得參數
                    param_query = (parameters[mode]["stop"].str.contains(sheet)) & \
                                  (parameters[mode]["stop"].str.contains(pred_type))
                    param_df = parameters[mode][param_query]
                    
                    if len(param_df) == 0:
                        continue
                    
                    alpha = param_df["alpha"].values[0]
                    constant = param_df["constant"].values[0]
                    
                    ws = result_wbs[mode][test_date][sheet]
                    s = stats[mode]
                    
                    for _, row in type_data.iterrows():
                        h_drive = row["PredictedDriveTime"]
                        ratio = row["Ratio"]
                        h_stay = row["h_stayTime"]
                        c_stay = row["c_stayTime"]
                        gt = row["GroundTruth"]
                        
                        predicted = predict(mode, h_drive, ratio, h_stay, c_stay, alpha, constant)
                        
                        ws.append([test_date, f"{sheet}{pred_type}", h_drive, ratio, h_stay, c_stay, gt, predicted])
                        
                        # 統計
                        if gt != 0 and h_drive != 0:
                            diff = abs(predicted - gt)
                            
                            if pred_type == "-1":
                                s["total_1"] += 1
                                if diff <= 10: s["correct_10_1"] += 1
                                if diff <= 20: s["correct_20_1"] += 1
                                if diff <= 30: s["correct_30_1"] += 1
                                if diff <= 60: s["correct_60_1"] += 1
                                if diff <= 120: s["correct_120_1"] += 1
                            elif pred_type == "-2":
                                s["total_2"] += 1
                                if diff <= 10: s["correct_10_2"] += 1
                                if diff <= 20: s["correct_20_2"] += 1
                                if diff <= 30: s["correct_30_2"] += 1
                                if diff <= 60: s["correct_60_2"] += 1
                                if diff <= 120: s["correct_120_2"] += 1
                            else:
                                s["total_3"] += 1
                                if diff <= 10: s["correct_10_3"] += 1
                                if diff <= 20: s["correct_20_3"] += 1
                                if diff <= 30: s["correct_30_3"] += 1
                                if diff <= 60: s["correct_60_3"] += 1
                                if diff <= 120: s["correct_120_3"] += 1
                                if diff <= 300: s["correct_300_3"] += 1
        
        # 儲存每天的結果
        for mode in modes_to_run:
            result_wbs[mode][test_date].save(f"inference_result/{ROUTEID}/{DIRECTION}/{mode}/result_{test_date}.xlsx")
    
    # 儲存統計結果
    print("\n儲存統計結果...")
    for mode in modes_to_run:
        s = stats[mode]
        StoredResult(
            [s["total_1"], s["correct_10_1"], s["correct_20_1"], s["correct_30_1"], s["correct_60_1"], s["correct_120_1"]],
            [s["total_2"], s["correct_10_2"], s["correct_20_2"], s["correct_30_2"], s["correct_60_2"], s["correct_120_2"]],
            [s["total_3"], s["correct_10_3"], s["correct_20_3"], s["correct_30_3"], s["correct_60_3"], s["correct_120_3"], s["correct_300_3"]],
            routeid=ROUTEID, direction=DIRECTION, day=DAY, mode=mode
        )
    
    print("\n✓ 所有模式推論完成！")

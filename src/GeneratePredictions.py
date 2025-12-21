import argparse
import os
import pandas as pd
from openpyxl import load_workbook

"""
產生 predictions.xlsx 中缺少的班次預設值
根據 GRUModel 資料夾中已有的模型檔案來產生對應的班次資料
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--routeid", type=int, required=True)
    parser.add_argument("--direction", type=int, required=True)
    parser.add_argument("--day", type=str, required=True, help="星期幾 (1-7)")
    parser.add_argument("--default_cluster", type=int, default=1, help="預設 Cluster 值 (1 或 2)")
    opt = parser.parse_args()
    print(opt)

    ROUTEID = opt.routeid
    DIRECTION = opt.direction
    DAY = opt.day
    DEFAULT_CLUSTER = opt.default_cluster

    # 星期對應表
    DAY_MAPPING = {
        "1": "星期一", "2": "星期二", "3": "星期三",
        "4": "星期四", "5": "星期五", "6": "星期六", "7": "星期日"
    }

    # 檢查 GRUModel 資料夾
    model_dir = f"./GRUModel/{ROUTEID}/{DAY}"
    if not os.path.exists(model_dir):
        print(f"錯誤: 找不到模型資料夾 {model_dir}")
        exit(1)

    # 從模型檔案名稱取得班次數量
    model_files = [f for f in os.listdir(model_dir) if f.endswith('.pth') and f"_{DIRECTION}_" in f]
    
    if len(model_files) == 0:
        print(f"錯誤: 在 {model_dir} 中找不到方向 {DIRECTION} 的模型檔案")
        exit(1)

    # 解析班次編號
    schedule_indices = []
    for f in model_files:
        # 格式: gru_100_0_星期四_第10班.pth
        try:
            idx = int(f.split("第")[1].split("班")[0])
            schedule_indices.append(idx)
        except:
            continue
    
    schedule_indices.sort()
    print(f"找到 {len(schedule_indices)} 個班次: {schedule_indices}")

    # 讀取現有的 predictions.xlsx
    predictions_file = "predictions.xlsx"
    if os.path.exists(predictions_file):
        existing_df = pd.read_excel(predictions_file)
        print(f"現有資料筆數: {len(existing_df)}")
    else:
        existing_df = pd.DataFrame(columns=["班次", "Cluster"])
        print("建立新的 predictions.xlsx")

    # 產生新的班次資料
    new_records = []
    for idx in schedule_indices:
        schedule_name = f"{ROUTEID}_{DIRECTION}_{DAY}_第{idx}班"
        
        # 檢查是否已存在
        if schedule_name in existing_df["班次"].values:
            print(f"  跳過 (已存在): {schedule_name}")
            continue
        
        new_records.append({"班次": schedule_name, "Cluster": DEFAULT_CLUSTER})
        print(f"  新增: {schedule_name}")

    if len(new_records) == 0:
        print("沒有需要新增的班次資料")
    else:
        # 合併並儲存
        new_df = pd.DataFrame(new_records)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        combined_df.to_excel(predictions_file, index=False)
        print(f"\n成功新增 {len(new_records)} 筆班次資料到 {predictions_file}")
        print(f"總資料筆數: {len(combined_df)}")

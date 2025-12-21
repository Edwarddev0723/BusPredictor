import torch
import argparse
import os
import pandas as pd
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
from openpyxl import Workbook
from Model import WeightedModel

"""
優化版 Train.py
- 一次讀取資料，訓練所有模式
- 減少重複的 Excel I/O
"""

MODES = ["a", "c", "r", "ac", "ar", "cr", "acr"]

def train_single_mode(mode, sheet, training_type, dataset, device, epoch):
    """訓練單一模式"""
    if mode == "r":
        return 0.0, 0.0
    
    query = (dataset["GroundTruth"] != 0) & (dataset["PredictedDriveTime"] != 0) & \
            (dataset["SechudeleIndex"].str.contains(training_type))
    filtered = dataset[query]
    
    if len(filtered) == 0:
        return None, None
    
    # 準備資料
    drive_time = torch.tensor(filtered["PredictedDriveTime"].to_list(), dtype=torch.float32)
    ratio = torch.tensor(filtered["Ratio"].tolist(), dtype=torch.float32)
    history_stay = torch.tensor(filtered["h_stayTime"].tolist(), dtype=torch.float32)
    current_stay = torch.tensor(filtered["c_stayTime"].tolist(), dtype=torch.float32)
    ground_truth = torch.tensor(filtered["GroundTruth"].tolist(), dtype=torch.float32)
    
    training_dataset = TensorDataset(ratio, history_stay, current_stay, drive_time, ground_truth)
    dataloader = DataLoader(training_dataset, batch_size=1000, shuffle=True)
    
    # 訓練
    model = WeightedModel(mode, device).to(device)
    optimizer = optim.Adam(model.parameters(), lr=1e-2)
    criterion = nn.MSELoss()
    
    history = {"Loss": [], "Alpha": [], "Constant": []}
    
    for ep in range(epoch):
        total_loss = 0.0
        for batch in dataloader:
            r, h_stay, c_stay, h_drive, gt = [x.to(device) for x in batch]
            
            optimizer.zero_grad()
            y_pred, alpha, constant = model(h_drive, r, h_stay, c_stay)
            loss = criterion(y_pred, gt)
            loss.backward()
            optimizer.step()
        
        total_loss += loss.item()
        history["Loss"].append(total_loss)
        history["Alpha"].append(alpha.item())
        history["Constant"].append(constant.item())
    
    best_idx = history["Loss"].index(min(history["Loss"]))
    return round(history["Alpha"][best_idx], 4), round(history["Constant"][best_idx], 4)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--routeid", type=int, required=True)
    parser.add_argument("--direction", type=int, required=True)
    parser.add_argument("--epoch", type=int, default=300)
    parser.add_argument("--day", type=str, required=True)
    parser.add_argument("--modes", type=str, default="all", help="訓練模式，用逗號分隔或 'all'")
    opt = parser.parse_args()
    print(opt)

    ROUTEID, DIRECTION, EPOCH, DAY = opt.routeid, opt.direction, opt.epoch, opt.day
    
    # 決定要訓練的模式
    if opt.modes == "all":
        modes_to_train = MODES
    else:
        modes_to_train = opt.modes.split(",")
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用裝置: {device}")
    
    # 一次讀取所有資料
    print("載入訓練資料...")
    excel_path = f"training_dataset/{ROUTEID}/{DIRECTION}/dataset_{DAY}.xlsx"
    xl = pd.ExcelFile(excel_path)
    sheets = xl.sheet_names[1:]  # 跳過第一個空白 sheet
    
    # 預先載入所有 sheet 的資料
    all_data = {}
    for sheet in sheets:
        all_data[sheet] = pd.read_excel(xl, sheet_name=sheet)
    print(f"載入完成，共 {len(sheets)} 個站點")
    
    # 為每個模式建立結果字典
    results = {mode: [] for mode in modes_to_train}
    
    # 訓練所有模式
    total_tasks = len(sheets) * 3 * len(modes_to_train)  # 站點 * 類型 * 模式
    current_task = 0
    
    for sheet in sheets:
        dataset = all_data[sheet]
        
        for training_type in ["-1", "-2", "-other"]:
            for mode in modes_to_train:
                current_task += 1
                
                alpha, constant = train_single_mode(mode, sheet, training_type, dataset, device, EPOCH)
                
                if alpha is not None:
                    results[mode].append([f"{sheet}{training_type}", alpha, constant])
                else:
                    results[mode].append([f"{sheet}{training_type}", 0.0, 0.0])
                
                # 進度顯示 (每 10% 顯示一次)
                if current_task % max(1, total_tasks // 10) == 0:
                    print(f"進度: {current_task}/{total_tasks} ({current_task*100//total_tasks}%)")
    
    # 儲存結果
    print("\n儲存訓練結果...")
    for mode in modes_to_train:
        output_dir = f"training_result/{ROUTEID}/{DIRECTION}/{mode}/"
        os.makedirs(output_dir, exist_ok=True)
        
        wb = Workbook()
        ws = wb.active
        ws.append(["stop", "alpha", "constant"])
        
        for row in results[mode]:
            ws.append(row)
        
        wb.save(f"{output_dir}/parameters_{DAY}.xlsx")
        print(f"  已儲存: {output_dir}/parameters_{DAY}.xlsx")
    
    print("\n✓ 所有模式訓練完成！")

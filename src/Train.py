import torch
import random
import argparse
import os
import pandas as pd
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
from openpyxl import Workbook
from Model import WeightedModel
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--routeid", type=int)
    parser.add_argument("--direction", type=int)
    parser.add_argument("--epoch", type=int, default=300)
    parser.add_argument("--day", type=str)
    """
    訓練參數，可以去調整當前要訓練的方式
    1. a ===> 單純用alpha去調和
    2. ar ===> 用aplha調和等待時間，再將行駛時間乘上ratio
    3. ac ===> 用aplha、constant 去調和最終結果
    4. acr ===> 將三種因素都考慮進去
    5. c ===> 單純用constant去調整
    6. cr ===> 用constant去調整，並將行駛時間乘上ratio
    7. r ===> 單純將行駛時間乘上ratio
    """
    parser.add_argument("--mode", type=str)
    opt = parser.parse_args()
    print(opt)

    ROUTEID, DIRECTION, EPOCH, MODE, DAY = opt.routeid, opt.direction, opt.epoch, opt.mode, opt.day

    """
    建置對應的存放路經，方便後續檔案存放
    """
    if not os.path.exists(f"training_result/{ROUTEID}/{DIRECTION}/{MODE}/"):
        os.makedirs(f"training_result/{ROUTEID}/{DIRECTION}/{MODE}/")

    """
    建構一個表格，後續訓練完成之後，能夠將對應的參數結果存放進檔案中
    """
    FileWB = Workbook()
    FileWS = FileWB.active
    FileWS.append(["stop", "alpha", "constant"])

    """
    訓練階段: 
    每一個站點都會有自己的三組參數(預測下站、預測下下站、預測其他站)
    """
    sheets = pd.ExcelFile(f"training_dataset/{ROUTEID}/{DIRECTION}/dataset_{DAY}.xlsx").sheet_names

    for sheet in sheets[1:]:
        for TrainingType in ["-1", "-2", "-other"]:
            """
            r模式不能訓練，所以直接以0替代alpha以及constant
            """
            if MODE == "r":
                FileWS.append([sheet+TrainingType, 0.0, 0.0])
                continue

            """
            讀取資料，如果訓練集中沒有對應的資料可以使用，則直接跳過
            """
            Dataset = pd.read_excel(f"training_dataset/{ROUTEID}/{DIRECTION}/dataset_{DAY}.xlsx", sheet_name=sheet)
            Query = (Dataset["GroundTruth"] != 0) & (Dataset["PredictedDriveTime"] != 0) & (Dataset["SechudeleIndex"].str.contains(TrainingType))
            Dataset = Dataset[Query]

            if len(Dataset) == 0: continue

            """
            讀取對應資料到串列中
            """
            drive_time = torch.tensor(Dataset["PredictedDriveTime"].to_list(), dtype=torch.float32)
            Ratio = torch.tensor(Dataset["Ratio"].tolist(), dtype=torch.float32)
            HistoryStayTime = torch.tensor(Dataset["h_stayTime"].tolist(), dtype=torch.float32)
            CurrentStayTime = torch.tensor(Dataset["c_stayTime"].tolist(), dtype=torch.float32)
            GroundTruth = torch.tensor(Dataset["GroundTruth"].tolist(), dtype=torch.float32)

            """
            封裝資料
            """
            TrainingDataset = TensorDataset(Ratio, HistoryStayTime, CurrentStayTime, drive_time, GroundTruth)
            dataloader = DataLoader(TrainingDataset, batch_size=1000, shuffle=True)

            """
            開始訓練
            """
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model = WeightedModel(MODE, device).to(device)
            History = {"Loss":[], "Alpha":[], "Constant":[]}
            optimizer = optim.Adam(model.parameters(), lr=1e-2)
            criterion = nn.MSELoss()

            print(f"\n{sheet}{TrainingType} Start Training...")

            for epoch in range(EPOCH):
                TotalLoss = 0.0
                for batch in dataloader:
                    ratio, h_stay, curr_stay, h_drive, gt = [x.to(device) for x in batch]

                    optimizer.zero_grad()
                    y_pred, alpha, constant = model(h_drive, ratio, h_stay, curr_stay)
                    loss = criterion(y_pred, gt)
                    loss.backward()
                    optimizer.step()

                TotalLoss += loss.item()
                History["Loss"].append(TotalLoss)
                History["Alpha"].append(alpha.item())
                History["Constant"].append(constant.item())

                if epoch % 1000 == 0: print(f"Epoch {epoch+1}/{EPOCH}, Loss: {TotalLoss:.6f}, Alpha: {alpha.item():.4f}, Constant: {constant.item():.4f}")

            print(f"\n=== {sheet}{TrainingType} final Parameter ===")
            Index = History["Loss"].index(min(History["Loss"]))
            print(f"Loss: {History['Loss'][Index]:.6f}, Alpha: {History['Alpha'][Index]:.4f}, Constant: {History['Constant'][Index]:.4f} \n")
            FileWS.append([sheet+TrainingType, round(History['Alpha'][Index], 4), round(History['Constant'][Index], 4)])

    FileWB.save(f"training_result/{ROUTEID}/{DIRECTION}/{MODE}/parameters_{DAY}.xlsx")
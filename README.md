## 系統架構
img/bus.png
## 目錄結構

```
.
├─ A2/                         # 公車當前的即時到站資料
├─ Info/                       # 路線、站序、經緯度、時刻表等靜態資料
│   ├─ v_stg_ibus_dailytimetable.csv
│   ├─ v_stg_tdx_stop2stopdistanceofroute.csv
│   └─ v_stg_tdx_stop.csv
|
├─ StatisticResult/            # 歷史統計結果輸出（由 StatisticDataPrepare 產生）
├─ status_dataset/             # 狀態資料集 (用來訓練GRU模型)
├─ training_dataset/           # 訓練資料集（由 TrainingDataPrepare 產生）
├─ training_result/            # 站點參數（由 Train 產生）
├─ inference_result/           # 推論逐站輸出（由 inference 產生）
├─ GRUModel/                   # GRU模型
|
├─ GetInfo.py                  
├─ TimeStastic.py              
├─ StasticDataPrepare.py
├─ StatusDataPrepare.py
├─ TrainingDataPrepare.py      
├─ Model.py                    
├─ Train.py                    
├─ Inference.py                
├─ Tool.py
├─ PredictedStatus.py
└─ predictions.xlsx            # 預設狀態表 (如預測錯誤則會根據此表作為預設值)    
```

- **A2/**：公車當前的即時到站資訊資料夾。  
- **Info/**：存放公車**路線、經緯度、時刻表**等靜態資料。
- **GRUModel/**：存放訓練完成的狀態預測模型

---

## 安裝與環境

- Python 3.9+
- 主要套件：`pandas`, `numpy`, `openpyxl`, `torch`, `argparse`

---

## 資料流程一覽

### Step 1 — 歷史統計（StatisticDataPrepare）

**目的**：針對一段日期內，計算每個**班次**（如 05:15 … 22:20）在**每一站**的：
- 行駛時間/停站時間的**平均**、**中位數**、**標準差**，並剔除離群值（以中位數±3σ）。  
- 結果輸出到 `StatisticResult/<routeid>/` 之多個 Excel：`drivetime_result_*.xlsx`、`median_*`、`std_*` 等。

**指令**：
```bash
python StasticDataPrepare.py --routeid --direction --start_date --end_date 
```
參數說明：
- `--routeid`：公車路線 ID  
- `--direction`：去程/返程（0/1）  
- `--start_date`、`--end_date`：統計區間（YYYY-MM-DD）

---

### Step 2 — 生成路線狀態表 (StatusDataPrepare)

**目的**：生成路線上每一站點的狀態表，以供GRU模型進行訓練。
```
["Index", "KmeansCenter1", "KmeansCenter2", "GroundTruth", "Status"]
```
- `Index`：欄位索引，由日期、班次、站點組成。
- `KmeansCenter1`：第一群行駛時間
- `KmeansCenter2`：第二群行駛時間
- `GroundTruth`：以**離站-到站**計算之真值（超過 ±3σ 會被濾除
- `Status`：該站點屬於兩群中哪一群(1 ==> 第一群, 2 ==> 第二群)
- 不同的星期會各自輸出一個檔案

**指令**：
```bash
python StatusDataPrepare.py --routeid --direction --day --start_date --end_date
```
參數說明：
- `--routeid`：公車路線 ID  
- `--direction`：去程/返程（0/1）
- `--day`：星期（1=週一 … 7=週日)
- `--start_date`、`--end_date`：統計區間（YYYY-MM-DD）

---

### Step 3 — 訓練資料整理（TrainingDataPrepare）

**目的**：生成模型訓練所需之逐站樣本，欄位如下：
```
["Date", "SechudeleIndex", "h_driveTime", "Ratio", "h_stayTime", "c_stayTime", "GroundTruth"]
```
- `h_driveTime`：歷史統計的行駛時間
- `Ratio`：當前區段真實行駛時間與歷史行駛時間比值
- `R_gt` / `R_ht`：分別代表 Ground Truth 與歷史時間
- `h_stayTime` / `c_stayTime`：歷史/當前等待時間
- `std` / `avg`：對應區段的歷史標準差 / 平均（也提供 3σ 範圍篩選）
- `GroundTruth`：以**離站-到站**計算之真值（超過 ±3σ 會被濾除）  
- 每個路線方向會輸出一個 Excel，多個工作表（第1站…第N站）。

**指令**：
```bash
python TrainingDataPrepare.py --routeid --direction --day --start_date --end_date
```
參數說明：
- `--routeid`：公車路線 ID  
- `--direction`：去程/返程（0/1）  
- `--day`：星期（1=週一 … 7=週日）
- `--start_date`、`--end_date`：統計區間（YYYY-MM-DD）

---

### Step 4 — 站點參數化模型訓練（Train）

**模型**：`WeightedModel(mode)`  
- 以一個可學參數 **α（alpha）** 與常數 **c（constant）**，對**歷史行駛**、**歷史等待**、**當前等待**、以及（選配）**Ratio** 進行線性加權，輸出預測時間。  
- 七種模式：
  - `a`：`drive + α * stay_history + (1-α) * stay_current`
  - `c`：`drive + stay_current + c`
  - `r`：`drive * r + stay_current`
  - `ac`：`drive + α * stay_history + (1-α) * stay_current + constant`
  - `ar`：`drive * ratio + α * stay_history + (1-α) * stay_current`
  - `cr`：`drive * r + stay_current + c`
  - `acr`：`drive * ratio + α * stay_history + (1-α) * stay_current + constant`  

**訓練流程**：
- 逐**站別**訓練，並依預測距離分成三種 TrainingType：`-1`（下一站）、`-2`（下下站）、`-other`（更遠站點彙整）。  
- 使用 MSELoss 最小化預測與 GroundTruth 的誤差；每站會紀錄歷史 `Loss/Alpha/Constant` 序列，並挑選 **最小 Loss** 時刻的參數作為該站最終參數。  
- 所有站點參數彙整為 `training_result/<route>/<direction>/<mode>/parameters_<day>.xlsx`。

**指令**：
```bash
python Train.py --routeid --direction --epoch --day --mode
```
參數說明：
- `--routeid`：公車路線 ID  
- `--direction`：去程/返程（0/1） 
- `--epoch`：訓練圈數  
- `--day`：指定要針對哪一天（週幾）的資料訓練  
- `--mode`：`a | c | r | ac | ar | cr | acr  `（詳見上方）

---

### Step 5 — 推論與評估（Inference）

**目的**：讀取訓練資料集與訓練完成的參數檔，對指定日期 `--test_date` 產生逐站預測並計算誤差分佈。  
- 逐站輸出至 `inference_result/<route>/<direction>/<mode>/result.xlsx`。  
- 同時計算三類距離（`-1`, `-2`, `-other`）在不同誤差門檻下的**區間正確率**：`≤10s`、`≤20s`、`≤30s`、`≤60s`、`≤120s`、`>120s`，並以 `Tool.StoredResult` 追加到 `inference_acc.xlsx` 方便統計展示。

**指令**：
```bash
python Inference.py --routeid --direction --day --mode acr --start_date --end_date
```
參數說明：
- `--routeid`：公車路線 ID  
- `--direction`：去程/返程（0/1）
- `--day`：測試的星期（需與訓練/統計對齊）
- `--mode`：`a | ac | ar | acr`
- `--start_date`、`--end_date`：統計區間（YYYY-MM-DD）

---

## 補充事項

- **班次與車次對齊**：以第一站離站時間作為錨點，透過最近時刻匹配與車牌過濾，避免混入其他班次資料。必要時對「無進站/無離站」等缺漏情境做防呆處理。  
- **資料清洗**：以中位數±3σ做離群值濾除，統計時對缺值以 0 補或交由推後處理；在產生訓練樣本時，再以 3σ 範圍檢查 GroundTruth 合理性。  
- **距離分群**：依「距離當前站的站數」分為 `-1 / -2 / -other`，在訓練與推論皆使用相同規則，便於分群評估。  
- **工具方法**：時間差 `CalDiffTime`、最近時刻 `FindClosestTime`、車次定位 `FindCarIDIndex`、誤差統計彙整 `StoredResult` 等集中於 `Tool.py`。  
- **資料彙整**：跨日、跨檔案的 A2 來源會自動串接（pt1m_YYYYMMDD_1…4），若缺檔則忽略該分段。

---

## 重現步驟

1) **統計**（輸出 `StatisticResult/`）
```bash
python StasticDataPrepare.py --routeid 100 --direction 0 --start_date 2025-09-23 --end_date 2025-10-29
```
2) **狀態彙整**（輸出 `Status_dataset/`）
```bash
python StatusDataPrepare.py --routeid 100 --direction 0 --start_date 2025-09-23 --end_date 2025-10-29
```
3) **訓練集整理**（輸出 `training_dataset/`）
```bash
python TrainingDataPrepare.py --routeid 100 --direction 0 --day 3 --start_date 2025-09-23 --end_date 2025-10-29
```
4) **訓練**（輸出 `training_result/`）
```bash
python Train.py --routeid 100 --direction 0 --epoch 300 --day 3 --mode acr
```
5) **推論 + 評估**（輸出 `inference_result/` 與 `inference_acc.xlsx`）
```bash
python Inference.py --routeid 100 --direction 0 --day 3 --mode acr --start_date 2025-09-23 --end_date 2025-10-29
```

---

## 參考檔案（主要程式）

- `GetInfo.py`：班表/站序/經緯度與日期區間 A2 整併。  
- `TimeStastic.py`：統計流程與輸出。  
- `StasticDataPrepare.py`：批次統計入口。  
- `TrainingDataPrepare.py`：訓練資料彙整。
- `PredictedStatus.py`：GRU模型預測結果。
- `StatusDataPrepare.py`：狀態檔案彙整。
- `Model.py`：七種加權模式。  
- `Train.py`：逐站訓練與最佳參數輸出。  
- `Inference.py`：逐站推論與誤差區間評估。  
- `Tool.py`：時間處理與結果彙整工具。

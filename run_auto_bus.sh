#!/bin/bash

# ================= 設定區 =================
# 設定日期區間
START_DATE="2025-08-01"
END_DATE="2025-10-31"

# 設定要跑的星期 (例如: 4=週四, 5=週五)
DAYS=(4 5)

# 設定要跑的路線與方向
# 格式: "路線ID 方向"
TARGETS=(
    "100 0"
    "100 1"
    "90 0"
    "90 1"
    "609 0"
    "609 1"
)

# 訓練參數
EPOCH=300

# ================= 程式邏輯區 =================

# 0. 安全檢查與備份
if [ ! -f "src/Tool.py" ]; then
    echo "錯誤: 找不到 src/Tool.py，請確認腳本位於專案根目錄。"
    exit 1
fi

echo "正在建立 Tool.py 的版本備份..."
cp src/Tool.py src/Tool.py.original

# 1. 製作一般版 Tool.py (100, 90路用)
# 確保是原始設定: 600s / 3600s
cp src/Tool.py.original src/Tool_normal.py

# 2. 製作 609特規版 Tool.py
# 使用 sed 指令修改參數
# 修改 checkLessThanThreshold 中的 <600 為 <1800
# 修改 isValid 中的 ThresHold = 600 為 1800
# 修改 isValid 中的 ThresHold = 3600 為 4800
cp src/Tool.py.original src/Tool_609.py
sed -i 's/<600/<1800/g' src/Tool_609.py
sed -i 's/ThresHold = 600/ThresHold = 1800/g' src/Tool_609.py
sed -i 's/ThresHold = 3600/ThresHold = 4800/g' src/Tool_609.py

echo "Tool.py 版本製作完成。"

# 3. 開始迴圈執行任務
for target in "${TARGETS[@]}"; do
    set -- $target
    ROUTE=$1
    DIR=$2

    echo "=========================================="
    echo "準備執行: 路線 $ROUTE / 方向 $DIR"
    echo "=========================================="

    # 4. 根據路線切換 Tool.py
    if [ "$ROUTE" == "609" ]; then
        echo ">> 偵測到 609 路，切換至 [特規長距離參數] (1800s/4800s)..."
        cp src/Tool_609.py src/Tool.py
    else
        echo ">> 偵測到一般路線，切換至 [標準參數] (600s/3600s)..."
        cp src/Tool_normal.py src/Tool.py
    fi

    # 5. 執行 Python 流程
    # Step A: 歷史統計 (StasticDataPrepare)
    echo "[1/4] 執行歷史統計..."
    python src/StasticDataPrepare.py --routeid $ROUTE --direction $DIR --start_date $START_DATE --end_date $END_DATE

    for DAY in "${DAYS[@]}"; do
        echo "    處理星期 $DAY 資料中..."
        
        # Step B: 狀態資料彙整 (StatusDataPrepare)
        echo "    [2/4] 建立狀態資料 (GRU)..."
        python src/StatusDataPrepare.py --routeid $ROUTE --direction $DIR --day $DAY --start_date $START_DATE --end_date $END_DATE

        # Step C: 訓練資料準備 (TrainingDataPrepare)
        # 註: TrainingDataPrepare.py 內部已有 K值的判斷邏輯 (K=30 for 609)，無需外部修改
        echo "    [3/4] 準備訓練資料 (耗時步驟)..."
        python src/TrainingDataPrepare.py --routeid $ROUTE --direction $DIR --day $DAY --start_date $START_DATE --end_date $END_DATE

        # Step D: Pipeline (Train + Inference)
        echo "    [4/4] 執行訓練與推論 Pipeline..."
        python src/pipeline.py --routeid $ROUTE --direction $DIR --epoch $EPOCH --day $DAY --start_date $START_DATE --end_date $END_DATE
    done
done

# 6. 執行結束，還原檔案
echo "=========================================="
echo "所有任務完成，正在還原 Tool.py..."
cp src/Tool.py.original src/Tool.py
rm src/Tool.py.original src/Tool_normal.py src/Tool_609.py
echo "還原完成。"
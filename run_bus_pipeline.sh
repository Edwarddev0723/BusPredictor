#!/bin/bash
# =============================================================================
# 公車資料前處理、訓練準備、模型訓練及推論 自動化腳本
# =============================================================================
# 使用方式:
#   ./run_bus_pipeline.sh --routeid <路線ID> --direction <方向> [選項]
#
# 範例:
#   ./run_bus_pipeline.sh --routeid 100 --direction 0
#   ./run_bus_pipeline.sh --routeid 609 --direction 0  # 會自動調整閥值
#
# =============================================================================

set -e  # 遇到錯誤立即停止

# 預設參數
ROUTEID=""
DIRECTION=""
START_DATE="2025-08-01"
END_DATE="2025-10-31"
EPOCH=300
DAYS="4 5"  # 預設跑星期四和星期五

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 解析參數
while [[ $# -gt 0 ]]; do
    case $1 in
        --routeid)
            ROUTEID="$2"
            shift 2
            ;;
        --direction)
            DIRECTION="$2"
            shift 2
            ;;
        --start_date)
            START_DATE="$2"
            shift 2
            ;;
        --end_date)
            END_DATE="$2"
            shift 2
            ;;
        --epoch)
            EPOCH="$2"
            shift 2
            ;;
        --days)
            DAYS="$2"
            shift 2
            ;;
        -h|--help)
            echo "使用方式: $0 --routeid <路線ID> --direction <方向> [選項]"
            echo ""
            echo "必要參數:"
            echo "  --routeid      路線編號 (例如: 100, 90, 609)"
            echo "  --direction    方向 (0 或 1)"
            echo ""
            echo "選項:"
            echo "  --start_date   開始日期 (預設: 2025-08-01)"
            echo "  --end_date     結束日期 (預設: 2025-10-31)"
            echo "  --epoch        訓練週期數 (預設: 300)"
            echo "  --days         要處理的星期 (預設: \"4 5\" 代表星期四和星期五)"
            echo ""
            echo "⚠️  609 路公車注意事項:"
            echo "  609 路（哈佛快線）站距遠大於一般路線，腳本會自動提示需要修改的閥值參數"
            exit 0
            ;;
        *)
            echo -e "${RED}未知參數: $1${NC}"
            exit 1
            ;;
    esac
done

# 檢查必要參數
if [ -z "$ROUTEID" ] || [ -z "$DIRECTION" ]; then
    echo -e "${RED}錯誤: 必須提供 --routeid 和 --direction 參數${NC}"
    echo "使用 --help 查看說明"
    exit 1
fi

echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}     公車預測系統 - 自動化處理腳本${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""
echo -e "路線編號: ${GREEN}$ROUTEID${NC}"
echo -e "方向: ${GREEN}$DIRECTION${NC}"
echo -e "日期範圍: ${GREEN}$START_DATE ~ $END_DATE${NC}"
echo -e "處理星期: ${GREEN}$DAYS${NC}"
echo -e "訓練週期: ${GREEN}$EPOCH${NC}"
echo ""

# =============================================================================
# ⚠️ 609 路公車關鍵修改說明
# =============================================================================
if [ "$ROUTEID" == "609" ]; then
    echo -e "${YELLOW}=============================================${NC}"
    echo -e "${YELLOW}⚠️  609 路公車 (哈佛快線) 閥值修改提醒${NC}"
    echo -e "${YELLOW}=============================================${NC}"
    echo ""
    echo -e "${RED}重要: 609 路站距遠大於一般路線，必須修改 src/Tool.py 中的閥值！${NC}"
    echo ""
    echo "請手動修改以下參數:"
    echo ""
    echo -e "${YELLOW}1. isValid 函式 (約第 65-75 行):${NC}"
    echo "   - 100、90 路: ThresHold_Type == 1 時為 600s, Type == 2 時為 3600s"
    echo -e "   - ${RED}609 路: 近程改為 1800s (30分鐘), 遠程改為 4800s${NC}"
    echo ""
    echo "   修改前:"
    echo "       if ThresHold_Type == 1:"
    echo "           ThresHold = 600"
    echo "       else:"
    echo "           ThresHold = 3600"
    echo ""
    echo "   修改後 (609 路):"
    echo "       if ThresHold_Type == 1:"
    echo "           ThresHold = 1800  # 609 路: 30分鐘"
    echo "       else:"
    echo "           ThresHold = 4800  # 609 路: 80分鐘"
    echo ""
    echo -e "${YELLOW}2. checkLessThanThreshold 函式 (約第 50-58 行):${NC}"
    echo "   - 100、90 路: 固定值 600"
    echo -e "   - ${RED}609 路: 改為 1800${NC}"
    echo ""
    echo "   修改前:"
    echo "       result = [CalDiffTime(BaseTime, time)<600 for time in CheckedTimeList]"
    echo ""
    echo "   修改後 (609 路):"
    echo "       result = [CalDiffTime(BaseTime, time)<1800 for time in CheckedTimeList]"
    echo ""
    echo -e "${YELLOW}=============================================${NC}"
    echo ""
    read -p "確認已修改閥值後，按 Enter 繼續執行，或按 Ctrl+C 取消..."
    echo ""
fi

# =============================================================================
# 步驟 1: 資料前處理 (StasticDataPrepare)
# =============================================================================
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}步驟 1/5: 資料前處理 (統計資料準備)${NC}"
echo -e "${GREEN}=============================================${NC}"

python src/StasticDataPrepare.py \
    --routeid $ROUTEID \
    --direction $DIRECTION \
    --start_date $START_DATE \
    --end_date $END_DATE

echo -e "${GREEN}✓ 資料前處理完成${NC}"
echo ""

# =============================================================================
# 步驟 2: 產生 predictions.xlsx 中缺少的班次資料
# =============================================================================
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}步驟 2/5: 產生 predictions.xlsx 班次資料${NC}"
echo -e "${GREEN}=============================================${NC}"

for DAY in $DAYS; do
    echo -e "產生星期 ${YELLOW}$DAY${NC} 的班次資料..."
    python src/GeneratePredictions.py \
        --routeid $ROUTEID \
        --direction $DIRECTION \
        --day $DAY \
        --default_cluster 1
done

echo -e "${GREEN}✓ predictions.xlsx 更新完成${NC}"
echo ""

# =============================================================================
# 步驟 3-5: 針對每個星期執行訓練資料準備、模型訓練、推論
# =============================================================================
for DAY in $DAYS; do
    echo -e "${BLUE}=============================================${NC}"
    echo -e "${BLUE}處理星期 $DAY${NC}"
    echo -e "${BLUE}=============================================${NC}"
    
    # 步驟 3: 訓練資料準備 (使用優化版本)
    echo -e "${GREEN}步驟 3/5: 訓練資料準備 (星期 $DAY) - 優化版${NC}"
    python src/TrainingDataPrepare_optimized.py \
        --routeid $ROUTEID \
        --direction $DIRECTION \
        --day $DAY \
        --start_date $START_DATE \
        --end_date $END_DATE
    echo -e "${GREEN}✓ 訓練資料準備完成 (星期 $DAY)${NC}"
    echo ""

    # 步驟 4: 模型訓練 (所有模式)
    echo -e "${GREEN}步驟 4/5: 模型訓練 (星期 $DAY)${NC}"
    for MODE in a c r ac ar cr acr; do
        echo -e "  訓練模式: ${YELLOW}$MODE${NC}"
        python src/Train.py \
            --routeid $ROUTEID \
            --direction $DIRECTION \
            --epoch $EPOCH \
            --day $DAY \
            --mode $MODE
    done
    echo -e "${GREEN}✓ 模型訓練完成 (星期 $DAY)${NC}"
    echo ""

    # 步驟 5: 推論
    echo -e "${GREEN}步驟 5/5: 推論 (星期 $DAY)${NC}"
    for MODE in a c r ac ar cr acr; do
        echo -e "  推論模式: ${YELLOW}$MODE${NC}"
        python src/Inference.py \
            --routeid $ROUTEID \
            --direction $DIRECTION \
            --start_date $START_DATE \
            --end_date $END_DATE \
            --day $DAY \
            --mode $MODE
    done
    echo -e "${GREEN}✓ 推論完成 (星期 $DAY)${NC}"
    echo ""
done

# =============================================================================
# 完成
# =============================================================================
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}🎉 所有處理完成！${NC}"
echo -e "${GREEN}=============================================${NC}"
echo ""
echo "輸出結果位置:"
echo "  - 統計結果: StatisticResult/$ROUTEID/"
echo "  - 訓練資料: training_dataset/$ROUTEID/$DIRECTION/"
echo "  - 訓練參數: training_result/$ROUTEID/$DIRECTION/"
echo "  - 推論結果: inference_result/$ROUTEID/$DIRECTION/"
echo "  - 準確度統計: inference_acc.xlsx"

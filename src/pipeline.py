import os
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--routeid", type=int)
    parser.add_argument("--direction", type=int)
    parser.add_argument("--epoch", type=int, default=300)
    parser.add_argument("--day", type=str)
    parser.add_argument("--start_date", type=str, default="2025-08-01")
    parser.add_argument("--end_date", type=str, default="2025-10-31")
    opt = parser.parse_args()

    ROUTEID, DIRECTION, EPOCH, DAY, START_DATE, END_DATE = opt.routeid, opt.direction, opt.epoch, opt.day, opt.start_date, opt.end_date

    os.system(f"python Train.py --routeid {ROUTEID} --direction {DIRECTION} --epoch {EPOCH} --day {DAY} --mode a")
    os.system(f"python Train.py --routeid {ROUTEID} --direction {DIRECTION} --epoch {EPOCH} --day {DAY} --mode c")
    os.system(f"python Train.py --routeid {ROUTEID} --direction {DIRECTION} --epoch {EPOCH} --day {DAY} --mode r")
    os.system(f"python Train.py --routeid {ROUTEID} --direction {DIRECTION} --epoch {EPOCH} --day {DAY} --mode ac")
    os.system(f"python Train.py --routeid {ROUTEID} --direction {DIRECTION} --epoch {EPOCH} --day {DAY} --mode ar")
    os.system(f"python Train.py --routeid {ROUTEID} --direction {DIRECTION} --epoch {EPOCH} --day {DAY} --mode cr")
    os.system(f"python Train.py --routeid {ROUTEID} --direction {DIRECTION} --epoch {EPOCH} --day {DAY} --mode acr")

    print("------------------------------------------")
    print("所有模式訓練完成...")
    print("------------------------------------------")

    os.system(f"python Inference.py --routeid {ROUTEID} --direction {DIRECTION} --start_date {START_DATE} --end_date {END_DATE} --day {DAY} --mode a")
    os.system(f"python Inference.py --routeid {ROUTEID} --direction {DIRECTION} --start_date {START_DATE} --end_date {END_DATE} --day {DAY} --mode c")
    os.system(f"python Inference.py --routeid {ROUTEID} --direction {DIRECTION} --start_date {START_DATE} --end_date {END_DATE} --day {DAY} --mode r")
    os.system(f"python Inference.py --routeid {ROUTEID} --direction {DIRECTION} --start_date {START_DATE} --end_date {END_DATE} --day {DAY} --mode ac")
    os.system(f"python Inference.py --routeid {ROUTEID} --direction {DIRECTION} --start_date {START_DATE} --end_date {END_DATE} --day {DAY} --mode ar")
    os.system(f"python Inference.py --routeid {ROUTEID} --direction {DIRECTION} --start_date {START_DATE} --end_date {END_DATE} --day {DAY} --mode cr")
    os.system(f"python Inference.py --routeid {ROUTEID} --direction {DIRECTION} --start_date {START_DATE} --end_date {END_DATE} --day {DAY} --mode acr")

    print("------------------------------------------")
    print("推理完成所有模式...")
    print("------------------------------------------")


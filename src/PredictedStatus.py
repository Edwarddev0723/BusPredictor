import torch
import torch.nn as nn
import numpy as np

"""
超參數
"""
HIDDEN_SIZE = 256
NUM_LAYERS = 3
SequenceMapping = {100: 42, 90: 27, 609: 4}

"""
GRU模型
"""
class GRUModel(nn.Module):
    def __init__(self, input_size=1, hidden_size=HIDDEN_SIZE, num_layers=NUM_LAYERS, output_size=3):
        super(GRUModel, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.gru = nn.GRU(input_size, hidden_size, num_layers, batch_first=True, dropout=0.3)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        out, _ = self.gru(x, h0)
        out = self.fc(out[:, -1, :])
        return out

"""
將資料進行映射(1 ===> 0, 2 ===> 1, 3 ===> 2)以及填充-1
"""
def preprocess_input(status_sequence, target_length):
    mapped_seq = [x-1 for x in status_sequence]

    current_len = len(mapped_seq)
    if current_len < target_length:
        padding_needed = target_length - current_len
        padding = [-1] * padding_needed
        final_seq = padding + mapped_seq
    else:
        final_seq = mapped_seq[-target_length:]

    tensor_input = torch.tensor(final_seq, dtype=torch.float32).unsqueeze(0).unsqueeze(-1)
    
    return tensor_input
    
def GetModel(Routeid, Direction, DAY, SechudleIndex):
    Dict = {"1": "星期一", "2": "星期二", "3": "星期三", "4": "星期四", "5": "星期五", "6": "星期六", "7": "星期日"}
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = GRUModel().to(device)
    MODEL_PATH = f"./GRUModel/{Routeid}/{DAY}/gru_{Routeid}_{Direction}_{Dict[DAY]}_第{SechudleIndex}班.pth"
    model.load_state_dict(torch.load(MODEL_PATH, map_location=device))

    return model, device

def predict_next_status(model, device, input_sequence, Routeid):
    model.eval()
    SEQUENCE_LENGTH = SequenceMapping[Routeid]

    with torch.no_grad():
        X = preprocess_input(input_sequence, SEQUENCE_LENGTH).to(device)
        outputs = model(X) 
        
        _, predicted_idx = torch.max(outputs.data, 1)
        prediction = predicted_idx.item()
        
        final_result = prediction + 1
        
        return final_result

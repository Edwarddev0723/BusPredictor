import torch
import torch.nn as nn

class WeightedModel(nn.Module):
    def __init__(self, mode, device):
        super().__init__()
        self.mode = mode
        self.device = device

        if self.mode == "a" or self.mode == "ar":
            self.aplha_raw = nn.Parameter(torch.tensor(0.0, device=self.device))
        elif self.mode == "ac" or self.mode == "acr":
            self.aplha_raw = nn.Parameter(torch.tensor(0.0, device=self.device))
            self.constant_raw = nn.Parameter(torch.tensor(0.0, device=self.device))
        elif self.mode == "c" or self.mode == "cr":
            self.constant_raw = nn.Parameter(torch.tensor(0.0, device=self.device))

    def forward(self, drive_time, ratio, stay_history, current_stay):
        """
        根據不同情況去forward不同的結果
        """
        if self.mode == "a":
            alpha = torch.sigmoid(self.aplha_raw)
            constant = torch.tensor(0.0, device=self.device)
            y_pred = drive_time + alpha * stay_history + (1-alpha) * current_stay
        
        elif self.mode == "ar":
            alpha = torch.sigmoid(self.aplha_raw)
            constant = torch.tensor(0.0, device=self.device)
            y_pred = drive_time * ratio + alpha * stay_history + (1-alpha) * current_stay
        
        elif self.mode == "ac":
            alpha = torch.sigmoid(self.aplha_raw)
            constant = self.constant_raw
            y_pred = drive_time + alpha * stay_history + (1-alpha) * current_stay + constant
        
        elif self.mode == "acr":
            alpha = torch.sigmoid(self.aplha_raw)
            constant = self.constant_raw
            y_pred = drive_time * ratio + alpha * stay_history + (1-alpha) * current_stay + constant

        elif self.mode == "c":
            alpha = torch.tensor(0.0, device=self.device)
            constant = self.constant_raw
            y_pred = drive_time + current_stay + constant

        elif self.mode == "cr":
            alpha = torch.tensor(0.0, device=self.device)
            constant = self.constant_raw
            y_pred = drive_time * ratio + current_stay + constant

        return y_pred, alpha, constant
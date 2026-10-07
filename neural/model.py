"""A small untrained MLP; parameters are learned only from our public data."""
import torch
from torch import nn
from neural.dataset import encoding


class ValueNetwork(nn.Module):
    def __init__(self):
        super().__init__()
        self.layers = nn.Sequential(nn.Linear(64, 128), nn.ReLU(), nn.Linear(128, 64),
                                    nn.ReLU(), nn.Linear(64, 1), nn.Tanh())

    def forward(self, x):
        return self.layers(x).squeeze(-1)


class NeuralEvaluator:
    def __init__(self, checkpoint='neural/checkpoint.pt'):
        torch.set_num_threads(1)
        state = torch.load(checkpoint, map_location='cpu', weights_only=True)
        self.model = ValueNetwork()
        self.model.load_state_dict(state['state_dict'])
        self.model.eval()

    def __call__(self, board, player):
        with torch.inference_mode():
            value = self.model(torch.tensor(encoding(board), dtype=torch.float32)).item()
        return value * board.turn * player

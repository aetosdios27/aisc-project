import argparse
import csv
import json
import random
from pathlib import Path
import torch
from torch import nn
from neural.model import ValueNetwork
from experiments.tournament import digest, provenance


def load_split(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    return torch.tensor([r['x'] for r in rows], dtype=torch.float32), torch.tensor([r['y'] for r in rows], dtype=torch.float32)


def metrics(model, x, y):
    with torch.inference_mode():
        pred = model(x)
        correlation = torch.corrcoef(torch.stack((pred, y)))[0, 1].item() if pred.std() > 0 and y.std() > 0 else None
        return {'mse': ((pred - y) ** 2).mean().item(), 'mae': (pred - y).abs().mean().item(),
                'correlation': correlation, 'outcome_accuracy': ((pred > 0.33).int() - (pred < -0.33).int() == y).float().mean().item()}


def train(epochs=20, batch_size=128, learning_rate=0.001, seed=810):
    if epochs < 1 or batch_size < 1 or learning_rate <= 0:
        raise ValueError('Positive epochs, batch size and learning rate required')
    random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    directory = Path('data/processed')
    manifest = json.loads((directory / 'manifest.json').read_text())
    for split, expected in manifest['processed_sha256'].items():
        if digest(directory / f'{split}.jsonl') != expected:
            raise ValueError(f'Changed {split} data; preprocess again')
    x, y = load_split(directory / 'train.jsonl')
    vx, vy = load_split(directory / 'validation.jsonl')
    model, loss = ValueNetwork(), nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    history, best_loss, best_epoch = [], float('inf'), None
    for epoch in range(epochs):
        model.train()
        order = torch.randperm(len(x))
        total = 0.0
        for indices in order.split(batch_size):
            optimizer.zero_grad()
            batch_loss = loss(model(x[indices]), y[indices])
            batch_loss.backward()
            optimizer.step()
            total += batch_loss.item() * len(indices)
        model.eval()
        validation = metrics(model, vx, vy)
        row = {'epoch': epoch + 1, 'training_loss': total / len(x), 'validation_loss': validation['mse']}
        history.append(row)
        if validation['mse'] < best_loss:
            best_loss, best_epoch = validation['mse'], epoch + 1
            torch.save({'state_dict': model.state_dict(), 'seed': seed, 'epoch': best_epoch,
                        'dataset_sha256': manifest['raw_sha256']}, 'neural/checkpoint.pt')
        print(f"Epoch {epoch + 1}: train={row['training_loss']:.4f}, validation={row['validation_loss']:.4f}", flush=True)
    saved = torch.load('neural/checkpoint.pt', weights_only=True)
    model.load_state_dict(saved['state_dict'])
    tx, ty = load_split(directory / 'test.jsonl')
    mean_baseline = y.mean().expand_as(ty)
    result = {'config': {'epochs': epochs, 'batch_size': batch_size, 'learning_rate': learning_rate, 'seed': seed,
                         'architecture': [64, 128, 64, 1], 'parameters': sum(p.numel() for p in model.parameters()),
                         'optimizer': 'Adam', 'loss': 'mean squared error', 'torch': torch.__version__},
              'provenance': provenance(), 'dataset': manifest, 'history': history, 'best_epoch': best_epoch,
              'validation': metrics(model, vx, vy), 'test': metrics(model, tx, ty),
              'test_mean_baseline_mse': ((mean_baseline - ty) ** 2).mean().item(),
              'checkpoint_sha256': digest('neural/checkpoint.pt')}
    Path('experiments/results/neural.json').write_text(json.dumps(result, indent=2))
    with Path('experiments/results/neural.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=('epoch', 'training_loss', 'validation_loss'))
        writer.writeheader()
        writer.writerows(history)
    print(json.dumps({'best_epoch': best_epoch, 'test': result['test']}), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--epochs', type=int, default=20)
    parser.add_argument('--seed', type=int, default=810)
    args = parser.parse_args()
    train(args.epochs, seed=args.seed)

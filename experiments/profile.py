"""Measure bottlenecks before considering algorithm-preserving optimization."""
import cProfile
import io
import pstats
from pathlib import Path
from engine.search import search
from experiments.tournament import opening


def profile():
    profiler = cProfile.Profile()
    positions = [opening(931 + i, 12 + i * 5)[0] for i in range(6)]
    profiler.enable()
    for position in positions:
        search(position, 3, ordering='position')
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(25)
    Path('experiments/results/profile.txt').write_text('Six seeded positions, depth 3, manual Alpha-Beta, positional ordering.\nProfiler timings include instrumentation overhead.\n\n' + stream.getvalue())
    print(stream.getvalue())


if __name__ == '__main__':
    profile()

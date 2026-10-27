"""Legacy-named entry for shared, manifest-driven source inspection."""
from pathlib import Path
import argparse
import runpy
import sys

if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    sys.argv[1:] = ['source']
    runpy.run_path(str(Path(__file__).with_name('inspect_xlsx.py')), run_name='__main__')

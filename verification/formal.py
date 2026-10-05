#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare or run source-to-Yosys/ABC synthesis equivalence on GitHub Actions.

--prepare is metadata-only. Actual Yosys execution is restricted to a Linux
GitHub runner. This is generic synthesis equivalence, not physical-netlist CEC.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/'build/formal'
TOP = 'tt_um_jogjohgoeg_hardwired'


def script(top):
    files = f'src/{top}.v' if top != TOP else 'src/project.v src/cell_279.v src/dot32_t.v'
    out = f'build/formal/{top}'
    # Save source after process lowering; synth applies ABC to the other copy.
    steps = [f'read_verilog {files}', f'hierarchy -check -top {top}', 'proc', 'flatten',
             'opt_clean', 'check -assert', f'write_rtlil {out}.source.il',
             f'design -save source', f'synth -top {top} -flatten', 'check -assert',
             f'write_verilog -noattr {out}.synth.v', f'design -save synthesized',
             'design -reset', f'design -copy-from source -as gold {top}',
             f'design -copy-from synthesized -as gate {top}',
             'equiv_make gold gate equiv', 'hierarchy -top equiv', 'equiv_simple']
    if top == TOP:
        steps.append('equiv_induct -seq 4')
    steps += ['equiv_status -assert']
    if top == TOP:
        # Induction alone assumes synchronized state. Prove reset establishes it.
        steps += ['design -reset', f'design -copy-from source -as gold {top}',
                  f'design -copy-from synthesized -as gate {top}',
                  'miter -equiv -flatten gold gate reset_miter',
                  'hierarchy -top reset_miter', 'opt_clean',
                  'sat -verify -seq 2 -set-def-inputs -set-at 1 in_rst_n 0 '
                  '-prove trigger 0 -prove-skip 1 -timeout 120 -show-inputs -show-outputs']
    return '\n'.join(steps)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    args = parser.parse_args()
    BUILD.mkdir(parents=True,exist_ok=True)
    modules = ['cell_279','dot32_t',TOP]
    for top in modules:
        (BUILD/f'{top}.ys').write_text(script(top))
    if args.prepare:
        print('Prepared Yosys scripts only; no synthesis or SAT was run')
        return
    if platform.system()!='Linux' or os.environ.get('GITHUB_ACTIONS')!='true':
        raise SystemExit('Run synthesis/formal only in GitHub Actions; use --prepare locally')
    results = {}
    for top in modules:
        subprocess.run(['yosys','-Q','-T','-l',str(BUILD/f'{top}.log'),'-s',str(BUILD/f'{top}.ys')],
                       cwd=ROOT,check=True,timeout=900)
        results[top] = 'proved'
    # A deliberately wrong circuit must be rejected by the same formal engine.
    (BUILD/'negative.v').write_text('module gold(input a, output y); assign y=a; endmodule\n'
                                  'module gate(input a, output y); assign y=~a; endmodule\n')
    neg = subprocess.run(['yosys','-Q','-T','-p',
        'read_verilog build/formal/negative.v; equiv_make gold gate equiv; hierarchy -top equiv; '
        'equiv_simple; equiv_status -assert'],cwd=ROOT,capture_output=True,text=True,timeout=60)
    (BUILD/'negative.log').write_text(neg.stdout+neg.stderr)
    assert neg.returncode!=0 and 'unproven' in (neg.stdout+neg.stderr).lower(), 'negative control was not rejected'
    receipt = {'scope':'source RTL vs generic Yosys/ABC synthesized netlist, plus wrapper reset base case',
               'results':results,'negative_control':'rejected',
               'yosys':subprocess.check_output(['yosys','-V'],text=True).strip(),
               'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in [*sorted((ROOT/'src').glob('*.v')),Path(__file__).resolve()]}}
    (BUILD/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    main()

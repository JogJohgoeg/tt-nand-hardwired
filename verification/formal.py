#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""ABC port CEC and complete wrapper state-transition equivalence, Actions only.

--prepare writes scripts without running EDA. This proves generic synthesis,
not the routed SKY130 netlist. See verification/FORMAL.md for the proof boundary.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/formal'
TOP = 'tt_um_jogjohgoeg_hardwired'
MODULES = ('cell_279', 'dot32_t', TOP)
STATE = {'in_sr': 320, 'out_sr': 32, 'out_count': 6}


def definedness_command(outputs):
    # If ANY output can be X with binary inputs, the constraints have a model
    # and the deliberately false property fails. UNSAT proves all outputs defined.
    return ('sat -verify -enable_undef -set-def-inputs '
            f"-set-any-undef {','.join(outputs)} -prove 1'b0 1'b1 -timeout 60")


def script(top):
    files = f'src/{top}.v' if top != TOP else 'src/project.v src/cell_279.v src/dot32_t.v'
    out = f'build/formal/{top}'
    steps = [f'read_verilog {files}', f'hierarchy -check -top {top}',
             'proc', 'flatten', 'opt_clean', 'check -assert', 'design -save source']
    for side in ('gold', 'gate'):
        steps += ['design -load source']
        if side == 'gold':
            # Lower RTL operators to gates without invoking ABC on the source.
            steps += ['techmap', 'opt -fast']
        else:
            steps += [f'synth -top {top} -flatten', 'check -assert',
                      f'write_verilog -noattr {out}.synth.v']
        steps += ['dffunmap', 'opt_clean', 'check -assert',
                  f'write_json {out}.{side}.state.json']
        if top == TOP:
            # Only the three named registers become state boundaries. Hide other
            # internal aliases so expose cannot make extra unconstrained inputs.
            steps += ['select -set state w:in_sr w:out_sr w:out_count',
                      'rename -hide w:* @state %d', 'select *',
                      'expose -dff -evert-dff', 'opt_clean', 'check -assert']
        if top == TOP:
            # proc lowering may leave X on a mux branch masked by a later mux.
            # Prove it cannot escape to ANY observable/next-state/clock output
            # before choosing a binary representation for ABC's BLIF format.
            outputs = [n for n, (d, _) in expected_ports(top).items() if d == 'output']
            steps += [f'write_json {out}.{side}.undef.json', definedness_command(outputs)]
            # One active reset edge establishes identical zero state even when
            # the two implementations start from unrelated arbitrary states.
            steps += ['sat -verify -set-def-inputs -set rst_n 0 '
                      '-prove in_sr.d 0 -prove out_sr.d 0 -prove out_count.d 0 '
                      '-timeout 60', 'setundef -zero', 'opt_clean', 'check -assert']
        steps += [f'write_json {out}.{side}.json', f'write_blif {out}.{side}.blif']
    return '\n'.join(steps) + '\n'


def expected_ports(top):
    if top != TOP:
        ni, no = (15, 2) if top == 'cell_279' else (320, 32)
        return {'din': ('input', ni), 'dout': ('output', no)}
    ports = {name: ('input', 8) for name in ('ui_in', 'uio_in')}
    ports.update({name: ('input', 1) for name in ('clk', 'ena', 'rst_n')})
    ports.update({name: ('output', 8) for name in ('uo_out', 'uio_out', 'uio_oe')})
    for name, width in STATE.items():
        ports.update({name+'.q': ('input', width), name+'.d': ('output', width),
                      name+'.c': ('output', 1)})
    return ports


def validate_model(top, side):
    prefix = BUILD / f'{top}.{side}'
    before = json.loads(Path(str(prefix)+'.state.json').read_text())['modules'][top]
    flops = [c for c in before['cells'].values() if c['type'] == '$_DFF_P_']
    if top == TOP:
        state_bits = [b for name in STATE for b in before['netnames'][name]['bits']]
        assert len(flops) == len(state_bits) == len(set(state_bits)) == 358
        assert {c['connections']['Q'][0] for c in flops} == set(state_bits)
        assert all(c['connections']['C'] == before['ports']['clk']['bits'] for c in flops)
    else:
        assert not flops, 'combinational core unexpectedly has state'
    after = json.loads(Path(str(prefix)+'.json').read_text())['modules'][top]
    ports = {n: (p['direction'], len(p['bits'])) for n, p in after['ports'].items()}
    assert ports == expected_ports(top), f'unexpected proof interface: {ports}'
    blif = Path(str(prefix)+'.blif').read_text()
    # No latches, black boxes, EXDC, or unspecified values may be silently cut.
    allowed = {'.model', '.inputs', '.outputs', '.names', '.end'}
    assert all(line.split()[0] in allowed for line in blif.splitlines() if line.startswith('.'))
    assert all('$undef' not in line for line in blif.splitlines()
               if line.strip() != '.names $undef'), 'undefined signal in proof model'
    return {'state_bits': len(flops), 'inputs': sum(w for d, w in ports.values() if d == 'input'),
            'outputs': sum(w for d, w in ports.values() if d == 'output')}


def invert_output(blif, output):
    """Flip one actual result/state bit, preserving the entire proof interface."""
    lines = blif.splitlines()
    assert any(output in line.split()[1:] for line in lines if line.startswith('.outputs '))
    assert '__negative_value' not in blif
    result = []
    for line in lines:
        if line == '.end':
            result += [f'.names __negative_value {output}', '0 1']
        if not line.startswith(('.outputs ', '#')):
            line = ' '.join('__negative_value' if token == output else token for token in line.split())
        result.append(line)
    return '\n'.join(result) + '\n'


def cec_result(returncode, output):
    if returncode != 0 or re.search(r'(?i)error:|undecided|timed out|miter computation has failed', output):
        return 'error'
    different = bool(re.search(r'(?m)^Networks are NOT EQUIVALENT(?:[. ]|$)', output))
    equivalent = bool(re.search(r'(?m)^Networks are equivalent(?:[. ]|$)', output))
    return ('equivalent' if equivalent else 'different') if equivalent != different else 'error'


def sat_verify_result(returncode, output):
    """Recognize only an explicit -verify verdict, never a generic tool failure.

    Some Yosys builds exit with the fatal proof diagnostic before the captured
    stream contains the preceding 'model found: FAIL!' banner (8e139cf runner).
    """
    fatal = 'ERROR: Called with -verify and proof did fail!'
    errors = re.findall(r'(?m)^ERROR:.*$', output)
    if re.search(r'(?i)TIMEOUT!|proof did time out|solver timed out|solver interrupted', output):
        return 'error'
    passed = 'no model found: SUCCESS!' in output
    failed = 'model found: FAIL!' in output or fatal in errors
    if returncode == 0 and passed and not failed and not errors:
        return 'proved'
    if returncode == 1 and failed and not passed and all(e == fatal for e in errors):
        return 'counterexample'
    return 'error'


def cec(abc, gold, gate, log):
    start = time.monotonic()
    command = [abc, '-c', f'cec -T 120 {gold.relative_to(ROOT)} {gate.relative_to(ROOT)}']
    with log.open('w') as stream:
        # ABC cec returns 0 even for a counterexample: its verdict is mandatory.
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=150)
    output = log.read_text()
    print(output, flush=True)
    verdict = cec_result(result.returncode, output)
    return {'verdict': verdict, 'seconds': round(time.monotonic()-start, 3)}


def check_definedness_controls():
    # One output is always defined. The other leaks X only in the negative:
    # this also catches accidentally requiring ALL outputs to be undefined.
    (BUILD/'undef_controls.v').write_text(
        "module masked(input s, a, output good, bad);\n"
        "wire branch = s ? 1'bx : a;\n"
        "assign good = a; assign bad = s ? a : branch; endmodule\n"
        "module leaking(input s, a, output good, bad);\n"
        "assign good = a; assign bad = s ? 1'bx : a; endmodule\n")
    results = {}
    for top in ('masked', 'leaking'):
        ys = BUILD/f'undef_{top}.ys'
        ys.write_text(f'read_verilog build/formal/undef_controls.v\nhierarchy -top {top}\n'
                      'proc\ntechmap\nopt_clean\n'+definedness_command(['good', 'bad'])+'\n')
        result = subprocess.run(['yosys', '-Q', '-T', '-s', str(ys)], cwd=ROOT,
                                capture_output=True, text=True, timeout=75)
        output = result.stdout + result.stderr
        (BUILD/f'undef_{top}.log').write_text(output)
        verdict = sat_verify_result(result.returncode, output)
        expected = 'proved' if top == 'masked' else 'counterexample'
        assert verdict == expected, f'{top}: rc={result.returncode}, verdict={verdict}\n{output}'
        results[top] = {'returncode': result.returncode, 'verdict': verdict,
                        'log_sha256': hashlib.sha256(output.encode()).hexdigest()}
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--module', choices=MODULES)
    args = parser.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)
    modules = [args.module] if args.module else MODULES
    for top in modules:
        (BUILD/f'{top}.ys').write_text(script(top))
    if args.prepare:
        print('Prepared Yosys scripts only; no synthesis, ABC or SAT was run')
        return
    if platform.system() != 'Linux' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('Run synthesis/formal only in GitHub Actions; use --prepare locally')
    abc = shutil.which('yosys-abc') or shutil.which('berkeley-abc')
    assert abc, 'ABC executable missing'
    for top in modules:
        receipt_path = BUILD/f'{top}.receipt.json'
        receipt_path.unlink(missing_ok=True)
        undef_controls = check_definedness_controls() if top == TOP else None
        subprocess.run(['yosys', '-Q', '-T', '-l', str(BUILD/f'{top}.log'),
                        '-s', str(BUILD/f'{top}.ys')], cwd=ROOT, check=True, timeout=300)
        models = {side: validate_model(top, side) for side in ('gold', 'gate')}
        gold, gate = (BUILD/f'{top}.{side}.blif' for side in ('gold', 'gate'))
        proof = cec(abc, gold, gate, BUILD/f'{top}.cec.log')
        assert proof['verdict'] == 'equivalent', proof
        negative = BUILD/f'{top}.negative.blif'
        bit = 'in_sr.d[0]' if top == TOP else 'dout[0]'
        negative.write_text(invert_output(gate.read_text(), bit))
        reject = cec(abc, gold, negative, BUILD/f'{top}.negative.log')
        assert reject['verdict'] == 'different', 'actual-output negative control was not rejected'
        receipt = {'scope': 'source vs generic Yosys/ABC synthesis; all ports and all next-state bits',
                   'module': top, 'models': models, 'proof': proof, 'negative_control': reject,
                   'definedness': 'all 385 outputs defined on both sides before setundef -zero' if top == TOP else 'strict BLIF check',
                   'definedness_controls': undef_controls,
                   'reset_base_case': 'both sides proved zero after one reset edge' if top == TOP else None,
                   'yosys': subprocess.check_output(['yosys', '-V'], text=True).strip(),
                   'abc_executable': abc,
                   'files': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in [*sorted((ROOT/'src').glob('*.v')), Path(__file__).resolve(),
                                       BUILD/f'{top}.ys', gold, gate, BUILD/f'{top}.synth.v',
                                       *([BUILD/f'{top}.{s}.undef.json' for s in ('gold', 'gate')]
                                         if top == TOP else [])]}}
        receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')


if __name__ == '__main__':
    main()

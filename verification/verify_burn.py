# SPDX-License-Identifier: MIT
#!/usr/bin/env python3
"""Read the actual burn JSON, then compare every DOT L1 sample to golden.py.

No RPC or transaction is executed. case_dot(20), the README's L1 multiplier,
uses a fresh seed 21; this is a standalone DOT run, not the old multi-component
run's advanced RNG state. Validation batches contain at most 256 inputs.
"""
import ast
import hashlib
import types
import numpy as np
import json
import sys
import time
from pathlib import Path

from reference import HERE, Netlist, bits, word, sha


def main():
    started = time.monotonic()
    artifact = HERE/'burn/dot32_t_xlayer.json'
    burn = json.loads(artifact.read_text())
    assert burn['nl_hex'].startswith('0x')
    raw = bytes.fromhex(burn['nl_hex'][2:])
    assert hashlib.sha256(raw).hexdigest() == burn['sha256']
    net = Netlist.decode(raw, burn['nIn'], burn['nOut'])
    assert (net.n_in, net.n_out, len(net.records), net.n_state) == (320,32,3829,0)
    assert burn['nNand'] == len(net.records) and burn['nLatch'] == 0
    assert len(raw) == 7*3829 and all(op==0 for op,_,_ in net.records)
    kit = HERE/'upstream'
    # Execute only the original pure DOT generator and its packing helper.
    source = ast.parse((kit/'l1.py').read_text())
    selected = [node for node in source.body if isinstance(node,ast.FunctionDef)
                and node.name in ('words1','case_dot')]
    assert {node.name for node in selected} == {'words1','case_dot'}
    ns = {'np':np,'U64':np.uint64,'rng':np.random.default_rng(21)}
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(kit/'l1.py'),'exec'),ns)
    l1 = types.SimpleNamespace(case_dot=ns['case_dot'],np=np)
    multiplier = int(sys.argv[1]) if len(sys.argv)>1 else 20
    case = l1.case_dot(multiplier)
    del case['cell']
    n = len(case['ref'])
    assert n == 50000*multiplier+16
    vector_hash = hashlib.sha256()
    input_hash = hashlib.sha256()
    output_hash = hashlib.sha256()
    for start in range(0,n,256):
        inputs, expected = [], []
        for cd, y in zip(case['calldata'][start:start+256],case['ref'][start:start+256]):
            packed = cd.tobytes()
            x = int.from_bytes(packed[:32],'big') | (int.from_bytes(packed[32:],'big')<<256)
            y = int(y)
            inp, out = x.to_bytes(40,'little'), y.to_bytes(4,'little')
            vector_hash.update(inp+out); input_hash.update(inp); output_hash.update(out)
            inputs.append(bits(x,320)); expected.append(y)
        actual = [word(out) for state,out in net.step_simd([b'']*len(inputs),inputs)]
        assert actual==expected, f'L1 mismatch in batch starting {start}'
        if start % (256*200) == 0:
            print(f'L1 DOT32_T: {min(start+256,n)}/{n}, mismatches=0',flush=True)
    refs = next(node.value for node in ast.parse((kit/'l2.py').read_text()).body
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REFS' for t in node.targets))
    l2_components = [ast.literal_eval(k) for k in refs.keys]
    assert 'DOT32_T' not in l2_components, 'L2 scope changed: add DOT validation'
    # Flip one output bit: demonstrate that the comparison detects it.
    assert actual != [actual[0]^1,*actual[1:]]
    report = {
        'artifact':'dot32_t_xlayer.json','artifact_sha256':sha(artifact),
        'netlist_sha256':burn['sha256'],'bytes':len(raw),'nIn':320,'nOut':32,'nNand':3829,'nLatch':0,
        'target':{'chain':'X Layer','chain_id':196,'tape_id':245,
                  'circuit_contract':'0xA93E807fAB41431827EBBa57443Fb687a95E2AA3',
                  'method':'tapeout(bytes,uint32,uint32)','transactions':0},
        'l1':{'generator':'21nandkit/l1.py:case_dot','multiplier':multiplier,'seed':21,
              'rng_scope':'fresh standalone DOT run (not historical multi-component RNG state)',
              'numpy':l1.np.__version__,'cases':n,'output_bits_compared':32*n,'mismatches':0,
              'batch_max':256,'vectors_sha256':vector_hash.hexdigest(),
              'hash_encoding':'concatenate input as 40-byte LE then output as 4-byte LE for each row',
              'inputs_sha256':input_hash.hexdigest(),'outputs_sha256':output_hash.hexdigest()},
        'l2':{'status':'not_applicable','components':l2_components,
              'reason':'21nandkit L2 covers FMUL_BF16 only; no DOT32_T L2 vector set exists'},
        'negative_control':'one-bit output error detected',
        'files':{'verify_burn.py':sha(HERE/'verify_burn.py'),'reference.py':sha(HERE/'reference.py'),
                 'golden.py':sha(HERE/'golden.py'),'21nandkit/l1.py':sha(kit/'l1.py'),
                 '21nandkit/l2.py':sha(kit/'l2.py')},
        'scope':'local golden vs all generated L1 vectors; no onchain or post-synthesis equivalence claim',
        'seconds':round(time.monotonic()-started,3)}
    output = HERE.parent/'build/burn-verification.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {n} complete L1 vectors, {32*n} output bits, zero mismatches; L2 not applicable',flush=True)


if __name__=='__main__':
    main()

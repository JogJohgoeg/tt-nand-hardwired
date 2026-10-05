# SPDX-License-Identifier: MIT
"""Independent TapeOut golden model and pinned 21nandkit L1 vectors."""
import hashlib
import json
import random
from pathlib import Path
from gen_verilog import HERE, Netlist, sources

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def bits(value, width):
    return bytes((value >> i) & 1 for i in range(width))

def word(value):
    return sum(b << i for i, b in enumerate(value))

def dot_reference(value):
    total = 0
    for j in range(32):
        q = (value >> (8*j)) & 255
        if q & 128:
            q -= 256
        code = (value >> (256+2*j)) & 3
        total += q * (0, 1, -1, 0)[code]
    return total & 0xffffffff

def golden_outputs(source, values):
    net = Netlist.decode(bytes.fromhex(source['netlist_hex']), source['n_in'], source['n_out'])
    # Bounded SIMD batches; never allocate a dense truth table for the 320-bit domain.
    out = []
    for start in range(0, len(values), 256):
        xs = [bits(x, net.n_in) for x in values[start:start+256]]
        out.extend(word(y) for _, y in net.step_simd([b''] * len(xs), xs))
    return out

def vectors():
    src = sources()
    v279 = list(range(1 << src['cell_279']['n_in']))
    out279 = golden_outputs(src['cell_279'], v279)
    l1 = json.loads((HERE / 'l1_vectors.json').read_text())
    dot = [int(row['input_hex'], 16) for row in l1['rows']]
    expected = [int(row['output_hex'], 16) for row in l1['rows']]
    assert [dot_reference(v) for v in dot] == expected, 'frozen L1 reference mismatch'
    # Each lane, all four weight codes, signed boundaries and byte/bit walking.
    for j in range(32):
        for q in [0, 1, 127, 128, 129, 255] + [1 << k for k in range(1, 7)]:
            for code in range(4):
                dot.append((q << (8*j)) | (code << (256+2*j)))
    rng = random.Random(20261005)
    dot.extend(rng.getrandbits(320) for _ in range(2048))
    expected = [dot_reference(v) for v in dot]
    actual = golden_outputs(src['dot32_t'], dot)
    assert actual == expected, 'DOT32_T golden disagrees with signed integer semantics'
    return {'cell_279': list(zip(v279, out279)), 'dot32_t': list(zip(dot, expected))}

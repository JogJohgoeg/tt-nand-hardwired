#!/usr/bin/env python3
"""L2 穷举：输入不超过 32 位的组件（首批里只有 FMUL_BF16），全部 2^32 个输入在本地链 EVM 里逐个执行。
每 2^20 个输入一个区间，EVM 端（EXH.yul）与参考端用同一公式算两个 64 位校验和，对不上的区间再逐条取回定位。
每个并行进程用自己的本地链。远程：sh remote.sh m149 sh run_l2.sh FMUL_BF16 16 [区间数，默认全部 4096]"""
import json
import sys
import time
from multiprocessing import Pool

import numpy as np

import l1

U64 = np.uint64
GOLD = U64(0x9E3779B97F4A7C15)
SPAN = 1 << 20
BASE_PORT = 8611


def ref_fmul_bf16(x):
    with np.errstate(all='ignore'):
        return l1.canon(l1.as_f32((x & U64(0xFFFF)) << U64(16)) * l1.as_f32((x >> U64(16)) << U64(16)))


REFS = {'FMUL_BF16': ref_fmul_bf16}


def ref_sums(name, start):
    x = np.arange(start, start + SPAN, dtype=U64)
    out = REFS[name](x)
    return int((out * (x + U64(1))).sum(dtype=U64)), int((out * (x * GOLD)).sum(dtype=U64))


def evm_sums(name, start):
    head = int(l1.ADDR[name], 16).to_bytes(32, 'big') + start.to_bytes(32, 'big') + SPAN.to_bytes(32, 'big')
    res = bytes.fromhex(l1.rpc('eth_call', [{'to': l1.ADDR['EXH'], 'data': '0x' + head.hex(), 'gas': hex(90_000_000_000)}, 'latest'])[2:])
    return int.from_bytes(res[:32], 'big'), int.from_bytes(res[32:64], 'big')


def locate(name, start, limit=5):
    """区间内逐条取回（普通批量调用器），列出前几个不一致"""
    x = np.arange(start, start + SPAN, dtype=U64)
    got, _, _ = l1.evm_run(name, l1.words1(x))
    ref = REFS[name](x)
    idx = np.nonzero((got & U64(0xFFFFFFFF)) != ref)[0]
    return int(len(idx)), [{'input': hex(int(x[i])), 'got': hex(int(got[i])), 'ref': hex(int(ref[i]))} for i in idx[:limit]]


def worker(args):
    name, k, starts = args
    l1.RPC = f'http://127.0.0.1:{BASE_PORT + k}'
    for n, info in l1.BC.items():
        l1.rpc('anvil_setCode', [l1.ADDR[n], '0x' + info['runtime']])
    bad = []
    for s in starts:
        if ref_sums(name, s) != evm_sums(name, s):
            bad.append({'start': hex(s), **dict(zip(('mismatches', 'examples'), locate(name, s)))})
    return len(starts), bad


def negctl(name):
    """负对照：参考输出里改一位，校验和必须对不上"""
    l1.RPC = f'http://127.0.0.1:{BASE_PORT}'
    for n, info in l1.BC.items():
        l1.rpc('anvil_setCode', [l1.ADDR[n], '0x' + info['runtime']])
    x = np.arange(0, SPAN, dtype=U64)
    out = REFS[name](x)
    out[12345] ^= U64(1)
    tampered = int((out * (x + U64(1))).sum(dtype=U64)), int((out * (x * GOLD)).sum(dtype=U64))
    caught = tampered != evm_sums(name, 0) and ref_sums(name, 0) == evm_sums(name, 0)
    print(('PASS ' if caught else 'FAIL ') + json.dumps({'negctl': name, 'flipped_bit_detected': caught}), flush=True)
    sys.exit(0 if caught else 1)


if __name__ == '__main__':
    if sys.argv[2] == 'negctl':
        negctl(sys.argv[1])
    name, par = sys.argv[1], int(sys.argv[2])
    n_ranges = int(sys.argv[3]) if len(sys.argv) > 3 else (1 << 32) // SPAN
    starts = [i * SPAN for i in range(n_ranges)]
    t0 = time.time()
    with Pool(par) as pool:
        res = pool.map(worker, [(name, k, starts[k::par]) for k in range(par)])
    bad = [b for _, lst in res for b in lst]
    summary = {'component': name, 'inputs': n_ranges * SPAN, 'ranges': n_ranges, 'bad_ranges': len(bad),
               'mismatches': sum(b['mismatches'] for b in bad), 'examples': bad[:3], 'seconds': round(time.time() - t0, 1)}
    print(('PASS ' if not bad else 'FAIL ') + json.dumps(summary, ensure_ascii=False), flush=True)
    sys.exit(0 if not bad else 1)

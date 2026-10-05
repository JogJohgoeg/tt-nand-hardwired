#!/usr/bin/env python3
"""21nandkit L1 对拍：组件字节码在本地链 EVM 里执行，与独立参考实现、门电路大脑单元逐位对比，并记录每次调用的 gas。
远程运行（本机不跑大规模验证）：tools/remote/rrun --host m149 -- sh run_l1.sh [倍率，默认 1]
参考实现：fp32 加乘用 numpy float32（硬件 IEEE、保留非规格数）；ISCALE32 用 80 位 long double 算精确积再舍入到 fp32。"""
import json
import os
import sys
import time
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, '..', 'hashport', 'gate_src')
sys.path.insert(0, os.path.join(GATE, 'cells'))
from nandlib import evaluate, pack_bits, unpack_bits  # noqa: E402

RPC = os.environ.get('RPC', 'http://127.0.0.1:8601')
BC = json.load(open(os.path.join(HERE, 'bytecode.json')))
ADDR = {name: '0x' + format(0x21a0 + i, '040x') for i, name in enumerate(sorted(BC))}
rng = np.random.default_rng(21)
U64 = np.uint64


def rpc(method, params):
    req = urllib.request.Request(RPC, data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode(),
                                 headers={'content-type': 'application/json'})
    j = json.loads(urllib.request.urlopen(req, timeout=3600).read())
    if 'error' in j:
        raise RuntimeError(f'{method}: {json.dumps(j["error"])[:300]}')
    return j['result']


def words1(v):
    """每条输入一个字：v（≤ 64 位）放在字的最低 8 字节，大端。"""
    b = np.zeros((len(v), 32), np.uint8)
    b[:, 24:] = np.frombuffer(np.asarray(v, U64).astype('>u8').tobytes(), np.uint8).reshape(-1, 8)
    return b


def evm_run(name, calldata, batch=8192):
    """calldata：[N, 32·w] 字节。返回 (输出低 64 位, 平均 gas/次, 最大 gas/次)。"""
    n_all, nb = calldata.shape
    outs, gsum, gmax = [], 0, 0
    for i in range(0, n_all, batch):
        chunk = calldata[i:i + batch]
        n = chunk.shape[0]
        head = int(ADDR[name], 16).to_bytes(32, 'big') + n.to_bytes(32, 'big') + (nb // 32).to_bytes(32, 'big')
        res = bytes.fromhex(rpc('eth_call', [{'to': ADDR['HARNESS'], 'data': '0x' + (head + chunk.tobytes()).hex(),
                                              'gas': hex(20_000_000_000)}, 'latest'])[2:])
        gsum += int.from_bytes(res[:32], 'big')
        gmax = max(gmax, int.from_bytes(res[32:64], 'big'))
        outs.append(np.frombuffer(res[64:], dtype='>u8').reshape(n, 4)[:, 3].astype(U64))
    return np.concatenate(outs), gsum / n_all, gmax


def cell_eval(cell, fields, chunk=1 << 17):
    """门电路大脑单元位切片求值。fields：按输入位序的 [(值数组, 位数)]。"""
    meta = json.load(open(os.path.join(GATE, 'overlay', 'cells', f'{cell}.json')))
    net = open(os.path.join(GATE, 'overlay', 'cells', f'{cell}.bin'), 'rb').read()
    n_all = len(fields[0][0])
    res = []
    for i in range(0, n_all, chunk):
        part = [(np.asarray(v[i:i + chunk], U64), nb) for v, nb in fields]
        n = len(part[0][0])
        pad = (-n) % 64
        inp = np.concatenate([pack_bits(np.pad(v, (0, pad)), nb) for v, nb in part], axis=0)
        assert inp.shape[0] == meta['n_in'], (cell, inp.shape, meta['n_in'])
        res.append(unpack_bits(evaluate(net, meta['n_in'], meta['n_out'], inp))[:n])
    return np.concatenate(res)


def canon(f32):
    """float32 数组 → 位型，NaN 统一为 0x7fc00000"""
    return np.where(np.isnan(f32), np.uint32(0x7fc00000), f32.view(np.uint32)).astype(U64)


def as_f32(bits):
    return np.asarray(bits, U64).astype(np.uint32).view(np.float32)


F32_SPECIAL = [0x00000000, 0x00000001, 0x007FFFFF, 0x00800000, 0x00800001, 0x00400000, 0x3F800000, 0x3F800001, 0x3F7FFFFF,
               0x3EFFFFFF, 0x4B000000, 0x33800000, 0x40490FDB, 0x7F7FFFFE, 0x7F7FFFFF, 0x7F800000, 0x7FC00000, 0x7FA00000]
F32_SPECIAL = np.array(F32_SPECIAL + [x | 0x80000000 for x in F32_SPECIAL], U64)
BF_SPECIAL = [0x0000, 0x0001, 0x0040, 0x007F, 0x0080, 0x0081, 0x3F80, 0x3F81, 0x3FFF, 0x4000, 0x7F7F, 0x7F80, 0x7FC0, 0x7F81]
BF_SPECIAL = np.array(BF_SPECIAL + [x | 0x8000 for x in BF_SPECIAL], U64)


def f32_with_exp(e, n):
    """给定（数组）指数的随机 fp32：随机符号与尾数"""
    return ((rng.integers(0, 2, n, dtype=U64) << U64(31)) | (np.asarray(e, U64) << U64(23)) | rng.integers(0, 1 << 23, n, dtype=U64))


def bf_with_exp(e, n):
    return ((rng.integers(0, 2, n, dtype=U64) << U64(15)) | (np.asarray(e, U64) << U64(7)) | rng.integers(0, 1 << 7, n, dtype=U64))


def grid(s1, s2):
    return np.repeat(s1, len(s2)), np.tile(s2, len(s1))


# ---------------- 各组件：生成样本、参考实现、门电路单元 ----------------

def case_fadd(k):
    n = 60000 * k
    parts = [(rng.integers(0, 2 ** 32, n, dtype=U64), rng.integers(0, 2 ** 32, n, dtype=U64))]          # 均匀随机位型
    ea = rng.integers(1, 255, n)
    a = f32_with_exp(ea, n)
    parts.append((a, f32_with_exp(np.clip(ea + rng.integers(-30, 31, n), 0, 254), n)))              # 指数相近：对齐与舍入
    d = rng.integers(-64, 65, n).astype(np.int64)
    parts.append((a, (a ^ U64(0x80000000)).astype(np.int64).__add__(d).astype(U64) & U64(0xFFFFFFFF)))   # 近乎抵消
    parts.append((f32_with_exp(rng.integers(0, 3, n), n), f32_with_exp(rng.integers(0, 3, n), n)))  # 非规格数附近
    e_hi = rng.integers(250, 255, n)
    parts.append((f32_with_exp(e_hi, n) & U64(0x7FFFFFFF), f32_with_exp(e_hi, n) & U64(0x7FFFFFFF)))  # 溢出附近
    parts.append(grid(F32_SPECIAL, F32_SPECIAL))
    a = np.concatenate([p[0] for p in parts]); b = np.concatenate([p[1] for p in parts])
    with np.errstate(all='ignore'):
        ref = canon(as_f32(a) + as_f32(b))
    return {'calldata': words1(a | (b << U64(32))), 'ref': ref,
            'cell': ('add', [(a, 32), (b, 32)], np.ones(len(a), bool)), 'mask': 0xFFFFFFFF}


def case_fmul_bf16(k):
    n = 60000 * k
    parts = [(rng.integers(0, 2 ** 16, n, dtype=U64), rng.integers(0, 2 ** 16, n, dtype=U64))]
    parts.append((bf_with_exp(rng.integers(0, 71, n), n), bf_with_exp(rng.integers(0, 71, n), n)))        # 下溢、非规格结果
    parts.append((bf_with_exp(rng.integers(40, 90, n), n), bf_with_exp(rng.integers(0, 60, n), n)))       # 结果跨越规格/非规格边界
    parts.append((bf_with_exp(rng.integers(190, 255, n), n), bf_with_exp(rng.integers(190, 255, n), n)))  # 溢出附近
    parts.append((bf_with_exp(rng.integers(100, 155, n), n), bf_with_exp(rng.integers(100, 155, n), n)))  # 常规量级
    parts.append(grid(BF_SPECIAL, BF_SPECIAL))
    a = np.concatenate([p[0] for p in parts]); b = np.concatenate([p[1] for p in parts])
    with np.errstate(all='ignore'):
        ref = canon(as_f32(a << U64(16)) * as_f32(b << U64(16)))
    return {'calldata': words1(a | (b << U64(16))), 'ref': ref,
            'cell': ('mul_bb', [(a << U64(16), 32), (b << U64(16), 32)], np.ones(len(a), bool)), 'mask': 0xFFFFFFFF}


def case_iscale(k):
    assert np.finfo(np.longdouble).nmant >= 63, '需要 80 位 long double（x86_64）才能精确算 int32 × fp32'
    n = 60000 * k
    parts = [(rng.integers(0, 2 ** 32, n, dtype=U64), rng.integers(0, 2 ** 32, n, dtype=U64))]
    small = (rng.integers(-4096, 4097, n).astype(np.int64) & 0xFFFFFFFF).astype(U64)
    bfb = bf_with_exp(rng.integers(1, 255, n), n) << U64(16)
    parts.append((small, bfb))                                                                           # 门电路大脑的定义域
    big = (rng.integers(-2 ** 31, 2 ** 31, n).astype(np.int64) & 0xFFFFFFFF).astype(U64)
    parts.append((big, f32_with_exp(rng.integers(1, 255, n), n)))                                        # 55 位乘积的舍入
    parts.append((big, f32_with_exp(rng.integers(0, 3, n), n)))                                          # 非规格结果
    parts.append((big, f32_with_exp(rng.integers(200, 255, n), n)))                                      # 溢出附近
    ints = [0, 1, 2, 3, 4095, 4096, 16777215, 16777216, 16777217, 2 ** 31 - 1]
    ints = np.array([x & 0xFFFFFFFF for x in ints + [-x for x in ints] + [-2 ** 31]], U64)
    parts.append(grid(ints, F32_SPECIAL))
    a = np.concatenate([p[0] for p in parts]); b = np.concatenate([p[1] for p in parts])
    ai = a.astype(np.uint32).view(np.int32)
    with np.errstate(all='ignore'):
        ref = canon((ai.astype(np.longdouble) * as_f32(b).astype(np.longdouble)).astype(np.float32))
    eb = (b >> U64(23)) & U64(0xFF)
    er = (ref >> U64(23)) & U64(0xFF)
    dom = (np.abs(ai.astype(np.int64)) <= 4096) & ((b & U64(0xFFFF)) == 0) & (eb >= 1) & (eb <= 254) & (er >= 1) & (er <= 254)
    return {'calldata': words1(a | (b << U64(32))), 'ref': ref,
            'cell': ('scale_exact', [(a, 32), (b, 32)], dom), 'mask': 0xFFFFFFFF}


def case_quant(k):
    n = 60000 * k
    parts = [(rng.integers(0, 2 ** 16, n, dtype=U64), rng.integers(0, 2 ** 32, n, dtype=U64))]
    parts.append((bf_with_exp(rng.integers(119, 136, n), n), f32_with_exp(rng.integers(123, 132, n), n)))   # 结果落在 ±2^12 内
    parts.append((bf_with_exp(rng.integers(126, 134, n), n), f32_with_exp(rng.integers(125, 130, n), n)))   # 结果多在 ±128 附近
    odd = np.arange(-255, 256, 2, dtype=np.float32)                                                          # 平局：(2k+1) × 0.5
    xb = (odd.view(np.uint32) >> np.uint32(16)).astype(U64)
    parts.append(grid(xb, np.array([0x3F000000, 0xBF000000], U64)))
    parts.append(grid(BF_SPECIAL, F32_SPECIAL))
    x = np.concatenate([p[0] for p in parts]); s = np.concatenate([p[1] for p in parts])
    with np.errstate(all='ignore'):
        y = (as_f32(x << U64(16)) * as_f32(s)).astype(np.float32)
        q = np.clip(np.rint(y), -128, 127)
    q = np.where(np.isnan(y), 127, q).astype(np.int64)
    return {'calldata': words1(x | (s << U64(16))), 'ref': (q & 0xFF).astype(U64),
            'cell': ('quant_s8', [(x, 16), (s, 32)], np.ones(len(x), bool)), 'mask': 0xFF}


def case_dot(k):
    n = 40000 * k
    qb = rng.integers(0, 256, (n, 32), dtype=np.uint8)
    code = rng.integers(0, 2 ** 63, n, dtype=U64) | (rng.integers(0, 2, n, dtype=U64) << U64(63))
    m = n // 4                                                                                            # 权重只取 ±1
    c12 = np.zeros(m, U64)
    for j in range(32):
        c12 |= (rng.integers(1, 3, m, dtype=U64) << U64(2 * j))
    ext_q = np.array([[0x80] * 32, [0x7F] * 32, [0xFF] * 32, [0x01] * 32], np.uint8)
    ext_c = np.array([int('01' * 32, 2), int('10' * 32, 2), int('11' * 32, 2), 0], U64)
    eq, ec = np.repeat(ext_q, len(ext_c), axis=0), np.tile(ext_c, len(ext_q))
    qb = np.concatenate([qb, qb[:m], eq]); code = np.concatenate([code, c12, ec])
    qs = qb.view(np.int8).astype(np.int64)
    c = (code[:, None] >> (U64(2) * np.arange(32, dtype=U64))) & U64(3)
    ref = ((qs * np.where(c == 1, 1, np.where(c == 2, -1, 0))).sum(1) & 0xFFFFFFFF).astype(U64)
    cd = np.concatenate([qb[:, ::-1], words1(code)], axis=1)                                             # 第 j 路在字的位 8j
    lanes = [(qb[:, j].astype(U64), 8) for j in range(32)]
    return {'calldata': cd, 'ref': ref, 'cell': ('ternary32', lanes + [(code, 64)], np.ones(len(code), bool)), 'mask': 0xFFFFFFFF}


CASES = {'FADD32': case_fadd, 'FMUL_BF16': case_fmul_bf16, 'ISCALE32': case_iscale, 'QUANT_S8': case_quant, 'DOT32_T': case_dot}

if __name__ == '__main__':
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    for name, info in BC.items():
        rpc('anvil_setCode', [ADDR[name], '0x' + info['runtime']])
    summary, ok_all = {}, True
    for name, make in CASES.items():
        t0 = time.time()
        c = make(k)
        got, gavg, gmax = evm_run(name, c['calldata'])
        got &= U64(c['mask'])
        bad_ref = int((got != c['ref']).sum())
        cell, fields, dom = c['cell']
        cv = cell_eval(cell, fields)
        bad_cell = int((got[dom] != cv[dom]).sum())
        r = {'cases': int(len(got)), 'mismatch_vs_ref': bad_ref, 'cell': cell, 'cell_compared': int(dom.sum()),
             'mismatch_vs_cell': bad_cell, 'gas_avg': round(gavg, 1), 'gas_max': gmax,
             'bytes': BC[name]['bytes'], 'yul_lines': BC[name]['yul_lines'], 'seconds': round(time.time() - t0, 1)}
        if bad_ref:
            i = int(np.nonzero(got != c['ref'])[0][0])
            r['first_ref_mismatch'] = {'calldata': c['calldata'][i].tobytes().hex(), 'got': hex(int(got[i])), 'ref': hex(int(c['ref'][i]))}
        if bad_cell:
            i = int(np.nonzero(dom & (got != cv))[0][0])
            r['first_cell_mismatch'] = {'calldata': c['calldata'][i].tobytes().hex(), 'got': hex(int(got[i])), 'cell': hex(int(cv[i]))}
        ok_all &= bad_ref == 0 and bad_cell == 0
        summary[name] = r
        print(('PASS ' if bad_ref == 0 and bad_cell == 0 else 'FAIL ') + name, json.dumps(r, ensure_ascii=False), flush=True)
    print(json.dumps(summary, ensure_ascii=False))
    sys.exit(0 if ok_all else 1)

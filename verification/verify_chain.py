#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Standalone canonical eth_call replay. Standard library only; never writes on chain."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import urllib.request

from reference import sources, vectors, sha

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    'cell_279': {'chain_id':56,'cpu':'0x6Fb4089e7Cbaa9660Fd11056274Cbd8117EE5B38','cid':279,
                 'rpcs':['https://bsc-dataseed.binance.org','https://bsc-rpc.publicnode.com']},
    'dot32_t': {'chain_id':196,'cpu':'0xA93E807fAB41431827EBBa57443Fb687a95E2AA3','cid':3,
                'rpcs':['https://rpc.xlayer.tech','https://xlayerrpc.okx.com']},
}
SELECTORS = {'info':'084d60f1','netlist':'3fc4be56','eval':'934d06ea','step':'e8281a1a'}


def encode(args):
    head,tail = [],b''
    for value in args:
        if isinstance(value,int):head.append(value.to_bytes(32,'big'))
        else:
            head.append((32*len(args)+len(tail)).to_bytes(32,'big'))
            tail += len(value).to_bytes(32,'big')+value+bytes(-len(value)%32)
    return b''.join(head)+tail


def dynamic(raw,index=0):
    assert len(raw)>=32*(index+1),'short ABI head'
    off = int.from_bytes(raw[32*index:32*(index+1)],'big')
    assert off%32==0 and off+32<=len(raw),'bad ABI offset'
    size = int.from_bytes(raw[off:off+32],'big')
    assert off+32+size<=len(raw),'truncated ABI data'
    return raw[off+32:off+32+size]


def rpc(profile,method,params):
    assert method in {'eth_chainId','eth_blockNumber','eth_getBlockByNumber','eth_getCode','eth_call'}
    payload = json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}).encode()
    errors = []
    for url in profile['rpcs']:
        try:
            request = urllib.request.Request(url,data=payload,headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(request,timeout=40) as response:reply = json.load(response)
            if 'result' not in reply:raise RuntimeError(reply.get('error','missing result'))
            return reply['result']
        except Exception as error:errors.append(str(error))
    raise RuntimeError('Public RPCs failed: '+'; '.join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core',choices=PROFILES,default='dot32_t')
    parser.add_argument('--block',type=int)
    parser.add_argument('--plan',action='store_true',help='write expected vectors without network calls')
    args = parser.parse_args()
    profile = PROFILES[args.core]
    source = sources()[args.core]
    all_rows = vectors()[args.core]
    if args.core=='cell_279':
        rng = random.Random(279)
        indices = sorted(set([0,8,32767]+[1<<j for j in range(15)]+rng.sample(range(32768),32)))
    else:
        rng = random.Random(245)
        indices = sorted(set(list(range(512,528))+[0,255,256,511,528,len(all_rows)-1]+
                             rng.sample(range(528,len(all_rows)),64)))
    rows = [{'vector_index':i,'input_int':str(all_rows[i][0]),'output_int':all_rows[i][1]} for i in indices]
    output = ROOT/'build/chain'
    output.mkdir(parents=True,exist_ok=True)
    (output/f'{args.core}.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows))
    for row in rows:
        packed = int(row['input_int']).to_bytes((source['n_in']+7)//8,'little')
        assert dynamic(encode([profile['cid'],packed]),1)==packed
    if args.plan:
        print(f'PASS: {args.core}, {len(rows)} vectors, no network calls')
        return
    assert int(rpc(profile,'eth_chainId',[]),16)==profile['chain_id'],'wrong chain'
    tag = hex(args.block) if args.block is not None else rpc(profile,'eth_blockNumber',[])
    block = rpc(profile,'eth_getBlockByNumber',[tag,False])
    code = bytes.fromhex(rpc(profile,'eth_getCode',[profile['cpu'],tag])[2:])
    assert code,'missing contract code'
    def call(kind,values):
        data = '0x'+SELECTORS[kind]+encode(values).hex()
        return bytes.fromhex(rpc(profile,'eth_call',[{'to':profile['cpu'],'data':data,'gas':hex(40_000_000)},tag])[2:])
    info = call('info',[profile['cid']])
    assert [int.from_bytes(info[i:i+32],'big') for i in range(0,len(info),32)]==[
        source['n_in'],source['n_out'],0,source['n_nand']]
    raw = dynamic(call('netlist',[profile['cid']]))
    assert raw.hex()==source['netlist_hex'],'published bytes differ from pinned RTL source'
    result = {'core':args.core,'chain_id':profile['chain_id'],'cpu':profile['cpu'],'cid':profile['cid'],
              'block':int(tag,16),'block_hash':block['hash'],'timestamp':int(block['timestamp'],16),
              'netlist_sha256':hashlib.sha256(raw).hexdigest(),'cpu_code_sha256':hashlib.sha256(code).hexdigest(),
              'transactions':0,'state_overrides':False,'checks':[],
              'files':{str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__).resolve(),
                       ROOT/'verification/reference.py',ROOT/'verification/sources.json',ROOT/'verification/golden.py']}}
    for i,row in enumerate(rows):
        packed = int(row['input_int']).to_bytes((source['n_in']+7)//8,'little')
        expected = row['output_int'].to_bytes((source['n_out']+7)//8,'little')
        ev = call('eval',[profile['cid'],packed]); st = call('step',[profile['cid'],b'',packed])
        assert dynamic(ev)==dynamic(st,1)==expected and dynamic(st)==b'',row
        result['checks'].append(dict(row,eval_return=ev.hex(),step_return=st.hex()))
        if (i+1)%16==0:print(f'{i+1}/{len(rows)} canonical pairs match',flush=True)
    assert rpc(profile,'eth_getBlockByNumber',[tag,False])['hash']==block['hash'],'block changed'
    (output/f'{args.core}_receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {len(rows)} canonical eval/step pairs, exact source bytes, zero transactions')


if __name__=='__main__':
    main()

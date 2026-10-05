#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exhaustive #279 and 4,112 DOT vectors; strict Icarus return-code checks."""
import json
from pathlib import Path
import re
import subprocess

from reference import vectors, sources, sha

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/'build/cores'
TB = '''`timescale 1ns/1ps
module tb;
reg [@NI@:0] din;
wire [@NO@:0] dout;
reg [@NO@:0] expected;
reg [4095:0] path, extra;
integer fd, n, r, count;
@NAME@ dut(.din(din),.dout(dout));
initial begin
  if (!$value$plusargs("STIM=%s",path) || !$value$plusargs("COUNT=%d",count) || count<=0)
    $fatal(1,"TB_FAIL arguments");
  fd=$fopen(path,"r");
  if (fd==0) $fatal(1,"TB_FAIL missing stimulus");
  for (n=0;n<count;n=n+1) begin
    r=$fscanf(fd,"%h %h",din,expected);
    if (r!=2) $fatal(1,"TB_FAIL truncated vector");
    #1;
    if (dout!==expected) $fatal(1,"TB_FAIL mismatch vector=%0d",n);
  end
  r=$fscanf(fd,"%s",extra);
  if (r>0 || !$feof(fd)) $fatal(1,"TB_FAIL extra data");
  $fclose(fd);
  $display("TB_PASS vectors=%0d",count);
  $finish;
end
endmodule
'''


def main():
    BUILD.mkdir(parents=True,exist_ok=True)
    result = {}
    for name, rows in vectors().items():
        s = sources()[name]
        tb = BUILD/f'{name}.v'
        tb.write_text(TB.replace('@NI@',str(s['n_in']-1)).replace('@NO@',str(s['n_out']-1)).replace('@NAME@',name))
        stim = BUILD/f'{name}.txt'
        stim.write_text(''.join(f'{x:x} {y:x}\n' for x,y in rows))
        exe = BUILD/f'{name}.vvp'
        subprocess.run(['iverilog','-g2012','-s','tb','-o',str(exe),str(ROOT/'src'/f'{name}.v'),str(tb)],check=True)
        got = subprocess.run(['vvp',str(exe),f'+STIM={stim}',f'+COUNT={len(rows)}'],capture_output=True,text=True,timeout=60)
        (BUILD/f'{name}.log').write_text(got.stdout+got.stderr)
        assert got.returncode==0 and re.search(rf'^TB_PASS vectors={len(rows)}$',got.stdout,re.M),got.stdout+got.stderr
        print(got.stdout.strip())
        controls = {'flipped':f'{rows[0][0]:x} {rows[0][1]^1:x}\n','empty':''}
        for label,text in controls.items():
            bad = BUILD/f'{name}_{label}.txt'; bad.write_text(text)
            neg = subprocess.run(['vvp',str(exe),f'+STIM={bad}','+COUNT=1'],capture_output=True,text=True,timeout=30)
            (BUILD/f'{name}_{label}.log').write_text(neg.stdout+neg.stderr)
            assert neg.returncode!=0 and 'TB_FAIL' in neg.stdout,'negative control undetected'
        result[name] = {'vectors':len(rows),'mismatches':0,'negative_controls':list(controls),
                        'netlist_sha256':s['sha256'],'rtl_sha256':sha(ROOT/'src'/f'{name}.v'),
                        'stim_sha256':sha(stim)}
    (BUILD/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()

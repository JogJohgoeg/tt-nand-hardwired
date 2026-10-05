# SPDX-License-Identifier: MIT
"""Port-only tests also run against the physical-flow gate-level netlist."""
import json
import sys
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'verification'))
from reference import vectors


@cocotb.test()
async def serial_protocol(dut):
    dut.clk.value = 0
    dut.rst_n.value = 0
    dut.ena.value = 0
    dut.ui_in.value = 0xff
    dut.uio_in.value = 0xa5

    async def edge(ui, ena=1, reset=1):
        dut.clk.value = 0
        dut.ui_in.value = ui
        dut.ena.value = ena
        dut.rst_n.value = reset
        await Timer(50, unit='ns')
        dut.clk.value = 1
        await Timer(50, unit='ns')
        dut.clk.value = 0

    def check(core, active, bit=0):
        expected = (core << 2) | (active << 1) | bit
        assert int(dut.uo_out.value) == expected, (int(dut.uo_out.value), expected)
        assert int(dut.uio_oe.value) == 0
        assert int(dut.uio_out.value) == 0

    await edge(0xff, ena=0, reset=0)
    check(1,0)
    v = vectors()
    receipt = json.loads((Path(__file__).resolve().parents[1]/'verification/evidence/chain.json').read_text())
    c279 = [v['cell_279'][row['vector_index']] for row in receipt['canonical_279']]
    # The exact L1 boundary rows plus random, per-lane and all-code cases.
    dot_indices = sorted(set([0,255,256,511]+list(range(512,528))+
                             list(range(528,len(v['dot32_t']),61))))
    dot = [v['dot32_t'][i] for i in dot_indices]
    rows = []
    for i in range(max(len(c279),len(dot))):
        if i < len(c279): rows.append((0,15,2,*c279[i]))
        if i < len(dot): rows.append((1,320,32,*dot[i]))
    for n,(core,ni,no,x,y) in enumerate(rows):
        base = core << 3
        for k in range(ni-1,-1,-1):
            if k == ni//2:
                await edge(base|0x17)       # CS_n pauses RUN and SHIFT
                check(core,0)
                await edge(base|0x15,ena=0) # ena pauses RUN and SHIFT
                check(core,0)
            await edge(base|4|((x>>k)&1))
        check(core,0)
        await edge(base|0x14)  # RUN priority over SHIFT
        check(core,1,(y>>(no-1))&1)
        await edge(base|0x10)  # replace an unread response
        for k in range(no-1,-1,-1):
            bit = (y>>k)&1
            check(core,1,bit)
            if k == no-1:
                await edge(base|0x17)
                check(core,1,bit)
                await edge(base|0x15,ena=0)
                check(core,1,bit)
                await edge(base^8) # live core echo, latched response
                check(core^1,1,bit)
                await edge(base)
            await edge(base|4)
        check(core,0)
        if n % 17 == 0:
            await edge(base|0x10)
            await edge(0xff,ena=0,reset=0) # reset wins over all controls
            check(1,0)
    dut._log.info('PASS: %d serial vectors, including all %d canonical chain samples',len(rows),len(c279))

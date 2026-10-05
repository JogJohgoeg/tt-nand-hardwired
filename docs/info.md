<!-- Protocol specification: CC0-1.0. -->
## How it works

This project converts two pinned TapeOut NAND netlists into ordinary standard-cell logic. Every source NAND record produces exactly one Verilog NAND primitive before synthesis. The compiler and source hashes are in `verification/`.

| Core | Input bits | Output bits | Source NANDs | Function |
|---|---:|---:|---:|---|
| 0 | 15 | 2 | 21 | TapeOut circuit #279, a combinational controller |
| 1 | 320 | 32 | 3,829 | DOT32_T, a signed 32-lane ternary dot product |

DOT32_T takes 32 signed 8-bit activations and 32 two-bit weight codes. For lane `j`, activation bits are `8*j +: 8` and the code is at `256 + 2*j +: 2`. Codes `00`, `01`, `10`, `11` mean `0`, `+1`, `-1`, `0`. The output is the sum modulo 2^32, interpreted as a signed two's-complement result. The weights arrive as input data. This first chip contains an arithmetic building block and a small fixed controller, not a complete language model or a mask-ROM weight store.

Circuit #279 was checked against the published BSC CPU 732 netlist and canonical `eval`/`step` calls. The user published DOT32_T as **#3@2.245** on X Layer. Independent verification matched its raw bytes and all 86 canonical eval/step pairs at block 72440910; see `verification/evidence/xlayer_dot32_cid3.json`. See `verification/evidence/chain.json` for the exact block and source bytes.

The current layout uses **2x2 tiles** and a **100 ns / 10 MHz clock constraint**. Actions bd1876b passed GDS, precheck and gate simulation, with positive setup/hold margins. The first 1x2 run failed at 107.137% utilization. These are flow results, not silicon measurements; see the report for area, timing, remaining slew counts and the additional tile cost.

## How to test

Use the normal Tiny Tapeout `clk`, `rst_n` and design selection (`ena`) pins. `rst_n` is an active-low **synchronous** reset: hold it low over at least one rising clock edge. Reset clears both shift registers and the response counter, including when `ena=0` or `CS_n=1`.

| Pin | Meaning |
|---|---|
| `ui[0]` | DIN |
| `ui[1]` | CS_n: low selects the interface |
| `ui[2]` | SHIFT: shift on the rising clock edge |
| `ui[3]` | CORE: 0 selects #279, 1 selects DOT32_T |
| `ui[4]` | RUN: capture the selected combinational result |
| `ui[7:5]` | Ignored |
| `uo[0]` | DOUT: next unread bit, zero when no response remains |
| `uo[1]` | RESPONSE: unread bits remain; this is not a computation timer |
| `uo[2]` | Live CORE echo, even during reset or deselection |
| `uo[7:3]` | Zero |
| `uio[*]` | Inputs, output enable zero; input values ignored |

1. With RESPONSE low, set CORE and CS_n=0. Keep RUN=0 and SHIFT=1. Present the input **most significant bit first**, one bit per rising edge: 15 bits for #279 or 320 bits for DOT32_T.
2. Set SHIFT=0 and RUN=1 for one rising edge. Set RUN back to zero. RESPONSE is now high and DOUT contains the output's most significant bit.
3. Sample DOUT **before** each SHIFT rising edge. Clock SHIFT exactly 2 times for #279 or 32 times for DOT32_T. The last edge clears RESPONSE and DOUT.
4. The next SHIFT loads a new input bit. Load a complete input frame before RUN. Incomplete frames deliberately retain older input bits; there is no frame-length detector.

CS_n=1 or ena=0 pauses all registers. With both RUN and SHIFT high, RUN wins. RUN replaces an unread response. Changing CORE alone changes only the echo and future RUN selection; it does not alter a captured response. The two cores share the input shift register. RUN does not clear it, so repeating RUN repeats the same calculation.

Example: DOT32_T with only lane 0 activation `-128` (byte `0x80`) and code `10` has packed input `(2 << 256) | 128` and output `0x00000080` (+128). Shift all 320 bits of that integer, bit 319 first. A transaction needs 353 clock edges: 320 load, one RUN, 32 read. At the 10 MHz target this is 35.3 microseconds without idle cycles; it is a protocol calculation, not measured throughput.

`test/test.py` checks the ports against the independent Python golden model, including all 49 #279 chain samples, DOT L1/boundary/random samples, pause, reset and priority. This also passed in the official gate-level workflow. `verification/test_cores.py` separately checks all 32,768 #279 inputs and 4,112 DOT inputs. The local full-wrapper Verilator regression covered all 36,880 transactions; receipts are included. Actions bd1876b proved both cores equivalent to generic Yosys/ABC synthesis and rejected actual-output flips. Wrapper reset proofs passed; its full equivalence check awaits the internal-X export fix described in `verification/FORMAL.md`.

## External hardware

A Tiny Tapeout demo board and a host that can drive synchronous GPIO are sufficient. Keep DIN and control signals stable around each rising edge. Use the demo board's supported logic levels. No external RAM, model storage or analog components are required.

## 中文说明

本项目把 #279 的 21 条 NAND 记录和 DOT32_T 的 3,829 条 NAND 记录机械转换为门级 RTL。DOT 是三值点积单元，激活与权重均从引脚输入；首片尚未包含完整语言模型或固化模型权重。#279 已对 BSC 链上电路逐位抽查；DOT 已由用户在 X Layer 发布为 #3@2.245，独立 86 组 eval/step 逐位通过，原始网表哈希一致。

串口按高位先行：空闲时装入 15/320 位，RUN 一拍，随后在 SHIFT 上升沿之前读取 2/32 位。低有效同步复位优先级最高；CS_n 高或 ena 低保持寄存器；RUN 优先于 SHIFT，可覆盖未读响应。`uo[1]` 表示仍有输出位未读，`uo[2]` 始终回显当前 CORE 输入。4 tile（增加 €140）已通过 GDS/precheck/门级仿真，100 ns 下 setup/hold 裕量为正；两核心 CEC 已通过，wrapper 等价待修复后验证。未做付费提交。

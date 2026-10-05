# Synthesis equivalence

The first Actions run (`e50f2e1`) proved cell_279. For DOT32_T, `equiv_simple`
printed success for all 32 output bits but then stalled on an internal `w41xx`
correspondence until the 900-second process limit. Output successes depended on
internal equivalence cut points; they do **not** establish the complete proof.
The original failed run remains evidence, not a pass.

The replacement uses ABC `cec -T 120` on the complete combinational interfaces.
ABC performs structural hashing, functional reduction and SAT; internal Verilog
wire names are not proof obligations. Gold is process-lowered and gate-lowered
source without ABC. Gate is the result of `synth -flatten`, including ABC.
Both exports must contain only combinational BLIF truth tables, with exact input
and output widths, no black boxes, no EXDC assumptions and no undefined drivers.

For the wrapper, both full cores remain in the flattened design. After unmapping
synchronous reset and enable into multiplexers, the script checks that exactly
358 positive-edge flops are driven by `clk`, covering `in_sr`, `out_sr` and
`out_count`. Yosys `expose -dff -evert-dff` turns these registers into matched
current-state inputs and next-state/clock outputs. All other internal names are
hidden first; the script rejects additional or missing ports and any remaining
sequential cells. ABC then proves every output and every next-state bit for
**all inputs and all shared current states**, including unreachable states.
Separate Yosys SAT checks prove that each implementation sets all 358 next-state
bits to zero when `rst_n=0`, irrespective of its previous state, `ena` or CS_n.
Thus one reset edge establishes equal state, and the transition proof preserves
equivalence for every following clock. This is an induction argument, not a
finite two-clock simulation. It assumes the documented common synchronous clock
and initial reset; it does not claim unrelated power-up states are identical.

Each of the three modules runs in its own Actions matrix job. Yosys has a
300-second process cap (each reset SAT query also has a 60-second limit); each
ABC call has a 120-second internal limit and 150-second process cap. Timeouts,
missing verdicts and inconsistent verdicts fail the job. ABC's exit status alone
is insufficient: it also returns zero for counterexamples. Every positive proof
must be followed by rejection of the **actual synthesized design** with one
output bit inverted (a next-state bit for the wrapper). Receipts bind the source,
script, synthesized Verilog and both BLIFs to SHA-256 values.

This establishes generic Yosys/ABC synthesis equivalence when the job passes.
It does not establish formal equivalence of the final routed SKY130 netlist;
the official GDS flow and its gate-level port regression remain separate checks.
The replacement is prepared locally; only an actual Actions result counts as a
formal pass. No local synthesis or solver run is permitted for this project.

```sh
# Local Python only:
python verification/formal.py --prepare
python -m unittest discover -s verification -p test_formal.py
# Executed only by the Linux GitHub runner:
python verification/formal.py --module dot32_t
```

Primary implementation references: [Yosys expose](https://github.com/YosysHQ/yosys/blob/yosys-0.33/passes/sat/expose.cc),
[Yosys expose regression](https://github.com/YosysHQ/yosys/blob/yosys-0.33/tests/sat/expose_dff.ys),
[DFF unmapping](https://github.com/YosysHQ/yosys/blob/yosys-0.33/passes/techmap/dffunmap.cc),
[ABC cec command](https://github.com/berkeley-abc/abc/blob/master/src/base/abci/abc.c),
and [ABC CEC/verdict implementation](https://github.com/berkeley-abc/abc/blob/master/src/base/abci/abcVerify.c).

中文：新方法比较两颗核心的全部端口，以及完整顶层的全部输出和 358 个下一状态位。
只有状态寄存器作为归纳边界，算术核心没有黑盒化。复位基例与任意状态下的一步转换
共同覆盖复位后的任意长执行。每项有时限，并用实际综合输出翻位作为负对照。
本机只生成脚本和测试解析器；Actions 通过前不宣称形式证明成功。

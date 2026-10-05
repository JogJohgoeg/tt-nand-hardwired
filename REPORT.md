# H2 validation report / 首片验证报告

2026-10-05: **8e139cf passes test, docs, both core CEC jobs, 2x2 GDS, precheck, routed gate simulation and viewer.** Wrapper CEC remains pending: Yosys correctly rejected the leaking-X negative control, but the harness required a missing FAIL banner and stopped before the wrapper proof. Its verdict parser is fixed locally and needs another Actions run. Area/timing numbers below retain their original bd1876b artifact provenance. No physical silicon or full-language-model performance is claimed.

8e139cf 的 test/docs、两颗核心 CEC、gds/precheck/gl_test/viewer 全过。wrapper 的泄漏X负对照已被Yosys拒绝，误报来自脚本要求未输出的FAIL横幅；已补精确判词和实际日志回归，不放宽SAT/CEC条件，新证明仍待Actions。4 tile 较原计划增加 €140，正式费用需用户决定。DOT 权重仍从输入提供，首片还不包含完整模型或权重 ROM。

| Evidence | Coverage | Result |
|---|---|---|
| Core gate simulation | #279 all 32,768 inputs, DOT32_T 4,112 samples; Icarus and Verilator | Zero mismatches |
| Original serial wrapper | Verilator all 36,880 transactions; Icarus 49 #279 + 94 DOT | Pass |
| This template's serial ports | Icarus/cocotb 49 #279 + 79 DOT, reset/pause/priority checks | Pass |
| Negative controls | 20 invalid core stimuli, wrapper flips/empty vectors, old broken wrapper | Rejected |
| BSC #279 | Canonical eval and step for the same 49 vectors | Pass at block 125879482 |
| Final DOT burn JSON | Original L1 case_dot(20), fresh DOT RNG seed 21; 1,000,016 samples, 32,000,512 output bits | Zero mismatches |
| X Layer DOT #3@2.245 | Same 86 vectors, both canonical eval and step; exact netlist bytes | Pass at block 72440910 |
| DOT L2 | Upstream L2 contains FMUL_BF16 only | Not applicable |
| Yosys/ABC core CEC | All inputs; actual-output flip negative controls | bd1876b: #279 pass in 0.032 s; DOT pass in 0.716 s |
| Wrapper formal | 358 state bits, both reset base cases | Reset pass; CEC blocked by internal-X export guard; fix pending |
| SKY130 physical flow | Official ttsky26d GDS / 15 prechecks / 128 port transactions | bd1876b: all three design jobs pass |

Raw source SHA-256 values are `f35baa03be7f9eefba33d778e0ff5b6e1430ccbb7b5b4a9daa81695b186c26c0` (#279, 21 NAND) and `b1507f55d3bd80bbc55f9e06dc656d81e049138827c97ec7fe640d7bfa2ce0b7` (DOT32_T, 3,829 NAND). Both contain zero latches. The wrapper adds 358 declared state bits. The core counts describe the pre-synthesis source records, not physical standard-cell counts.

[Local receipts](verification/evidence/) bind results to file hashes. The archived `simulation.json` and `wrapper.json` were produced in the parent H2 workspace; their source names are local to that workspace. `cores-local.json`, `cocotb-local.xml` and `local-files.json` bind this standalone repository's actual files and renamed top. The original wrapper bug and harness failures were preserved in the parent audit: wrong serial shift direction and an ineffective testbench reset. The current regression detects the old wrapper. Full Icarus serial testing hit a 240 s cap; the full serial dataset passes on Verilator and the explicitly counted Icarus subset passes.

[Chain receipt](verification/evidence/chain.json): BSC CPU 732 at `0x6Fb4089e7Cbaa9660Fd11056274Cbd8117EE5B38`, block hash `0xb6c853eaca577dc6800ef5e57226a579ed13712f6bba689783eaf2051428a27e`. The exact #279 raw bytes and raw eval/step returns are retained. This is not DOT chain evidence. Per the user's decision, DOT targets X Layer #245 at `0xA93E807fAB41431827EBBa57443Fb687a95E2AA3`; the user published circuit **#3@2.245**. Independent [canonical verification](verification/evidence/xlayer_dot32_cid3.json) passed all 86 eval/step pairs at block **72440910**, hash `0xeb6ff9611314755b572a4a1a77de55fd2572759db001f798a858a5c54e3404a5`. Published raw bytes match the source and burn JSON exactly.

[Burn JSON and proof](verification/burn/) contain the complete unsigned netlist payload and its local L1 proof. The standalone verification command is `python verification/verify_burn.py 20` with the NumPy version pinned in `verification/requirements.txt` (Python 3.11 recommended); it reopens the JSON and runs the original upstream DOT generator in bounded batches. It uses a fresh seed 21, not the historical multi-component run's advanced RNG stream. New receipts are written to `build/`. The existing million-sample receipt remains unchanged.

本地逐位证据、负对照和文件哈希均已保留。#279 已核对原始链上网表及同批 eval/step。DOT 已发布为 #3@2.245，独立 86 组链上 eval/step 逐位通过；最终 JSON 对 L1 全百万向量通过，但这不等于全部 2^320 输入的形式证明；现有 L2 没有 DOT 项目。泛用综合的 CEC 也不等于最终布线网表的形式签核，后者另有官方 GL 有限向量测试。

The [official schedule](https://tinytapeout.com/chips/) lists **TTSKY26d closing 2026-11-30**, estimated shipping **2027-06-09**. The [calculator](https://app.tinytapeout.com/calculator?shuttle=chipfoundry&tiles=2&pcbs=1) and its [public pricing module](https://app.tinytapeout.com/_build/assets/invoice-WoZjomWD.js), checked 2026-10-05, give €70/tile. Two tiles cost €140; one standard €300 kit plus €15 shipping makes €455, or €255 with the limited €100 individual kit. Discount eligibility, inventory, taxes and final checkout are unconfirmed. [Pricing snapshot](verification/evidence/pricing.json). No order has been submitted.

当前候选四 tile €280；加普通开发板与列明的运费 €595，有个人优惠时 €395，相比原两 tile 均增加 €140。最终费用取决于实际尺寸、优惠与结算；本项目未付费提交。

## First Actions failure and candidate selection / 首轮失败与尺寸选型

The [first GDS run](https://github.com/JogJohgoeg/tt-nand-hardwired/actions/runs/37326566724) mapped **2,863 cells / 31,137.363 µm²**, including **358 sequential cells / 7,614.803 µm² (24.46%)**. The 1x2 core provides 34,255.354 µm², with 1,178.630 µm² fixed cells. GPL adds 4,299.990 µm² for pin density, giving `(31,137.363 + 4,299.990) / (34,255.354 - 1,178.630) = 107.137%`. Raising the 60% placement-density target cannot fix an effective utilization above 100%. Synthesis already used `AREA_0`. ABC printed “The network is combinational” while handling an extracted cone; the mapped top still contains all 358 sequential cells. The fatal flow error was GPL-0301; that failed run produced no routed timing result. [Evidence and original-log hashes](verification/evidence/ci_e50f2e1.json).

| Option | Area basis | Tile fee | Change from 2 tiles | Decision |
|---|---|---:|---:|---|
| Keep 1x2 and reduce area | Measured 107.137%; approximately 44% reduction of adjusted movable area to reach 60% | €140 | €0 | Requires substantial optimization; no fitting result |
| **2x2 candidate** | Die 334.88 × 225.76 µm; initial utilization estimate 50.6%, now **54.8262% measured by flow** | **€280** | **+€140** | GDS/precheck/GL pass at bd1876b; paid submission requires user decision |
| 3x2 reserve | More capacity; no physical run | €420 | +€280 | Not selected; consider only if 2x2 fails |

The 2x2 estimate uses the [official DEF](https://github.com/TinyTapeout/tt-support-tools/blob/main/tech/sky130A/def/tt_block_2x2_pg.def), unchanged margins, unchanged logic/pin-adjust area and fixed-cell area scaled with core area. It excludes new CTS/routing buffers and is not a fit guarantee. A 2x2 run keeps the exact source NANDs, serial protocol and 100 ns clock target. Removing only the 32-bit output register would not provide the roughly 44% target reduction; all sequential cells together account for only 24.46% of mapped area, and all 320 input bits must be retained for the published combinational core. Further mapping or wrapper changes require new equivalence evidence. No unmeasured area-saving claim is used to justify two tiles.

选型：先用 2x2 验证能否完整布通，保持源网表与接口不变。1x2 当前连 100% 都超过，60% 目标所需缩减约 44%；默认已做 AREA_0，不能把调高密度当作修复。2x2 的约 50.6% 仅为面积估算，必须通过实际 GDS、precheck、GL 与时序检查。4 tile 的额外 €140 已交用户决定，CI 配置不代表下单。

The [failed formal run](https://github.com/JogJohgoeg/tt-nand-hardwired/actions/runs/37326566770) reported all DOT `dout` bits successful before stalling on internal wire obligations. Those successes depended on unproven cut points, so DOT was unproven in that revision. The replacement uses ABC CEC over ports and, for the complete wrapper, all 358 next-state bits plus clock outputs, with separate reset proofs. It does not black-box the arithmetic cores. Independent matrix jobs have explicit process limits and reject a flipped bit in each actual synthesized design. [Proof method and limits](verification/FORMAL.md). The later core proofs are recorded below; wrapper CEC remains pending.

## bd1876b measured results / 第二轮实测

The [formal run](https://github.com/JogJohgoeg/tt-nand-hardwired/actions/runs/37331447451) establishes full generic synthesis equivalence for both cores. The previous DOT timeout is resolved: its CEC took 0.716 s and its output-flip counterexample 0.064 s. [Core receipts and logs](verification/evidence/formal_bd1876b/). The wrapper's two reset checks passed, but 76 source-side mux branches contained X. Its prepared fix first proves that all **385 external/next-state/clock output bits are defined for arbitrary binary inputs and state**, then permits internal X normalization for ABC. The exported-BLIF guard is retained, with masked-X and observable-X controls. Wrapper CEC remains unproved until the new Actions job passes.

The [physical run](https://github.com/JogJohgoeg/tt-nand-hardwired/actions/runs/37331447516) passed GDS, all 15 Tiny Tapeout prechecks and the port-level gate simulation (128 transactions inside one cocotb test). Artifact source/config hashes match the current design. [Raw metrics, precheck, gate-test XML and artifact manifest](verification/evidence/physical_bd1876b/).

| Metric | bd1876b result |
|---|---:|
| Tile count / die | 4 / 334.88 × 225.76 µm |
| Core area | 72,564.6 µm² |
| Standard-cell area, excluding fillers | 39,784.4 µm² |
| Standard-cell utilization | 54.8262% |
| Clock constraint | 100 ns / 10 MHz |
| Worst setup slack, all reported corners | +58.283776 ns |
| Worst hold slack, all reported corners | +0.107796 ns |
| Setup / hold total negative slack | 0 / 0 ns |
| Route DRC / Magic DRC / LVS errors | 0 / 0 / 0 |
| Max-cap violations | 0 |
| Max-slew violation metric | **226**, worst reported corner `max_ss_100C_1v60` |

The flow's total instance area includes fillers and equals the core area; it is **not** the logic area. Added timing/clock buffers account for much of the increase over the 31,137 µm² synthesis area. Setup and hold meet the supplied constraints; the reported slew violations remain visible and no zero-violation or silicon-frequency claim is made. The GDS SHA-256 is `b909b61df0b70735cd87b2cfea0dc683b41ac737d2250a1baa337a210030a1b0`.

2x2 已实际布通并通过提交前检查和门级仿真。面积采用排除 filler 的标准单元指标，不能把填满 core 的总 instance area 当作逻辑面积。100 ns 约束下 setup/hold 无负裕量，但保留原始 max-slew 计数 226，不写成所有电气指标零违规。初次 Viewer 的 Pages 部署返回 404；后续同提交运行已成功。此项不改变设计验证结果，也没有付费提交。

| Related work | Comparison |
|---|---|
| [Taalas HC1](https://taalas.com/products/) | Vendor's complete Llama 3.1 8B hardwired demonstrator, 6 nm and 815 mm². Its advertised 17k tokens/s/user is not comparable to our serial arithmetic prototype. |
| [Ankhdjet](https://arxiv.org/abs/2608.26206) | Open ternary checkpoint-to-via-mask compiler on SKY130; paper reports signoff and a TTSKY26c demonstrator submission. Relevant to future fixed-weight storage. |
| [tiny-asic 1.58-bit matrix multiply](https://github.com/rejunity/tiny-asic-1_58bit-matrix-mul) | Open ternary arithmetic with streamed packed weights and simulation-based performance. Our first milestone emphasizes byte-pinned source netlists and canonical chain checks. |

三者分别对应完整模型硬化、开源掩膜 ROM 编译、三值算术。首片当前验证门网表到芯片 RTL 的可核对链路，不以不同工艺与规模的 token/s 或能耗作直接比较。三值的信息量约 1.585 位；本接口实际使用每权重两位。

The standalone public replay script was also run against block 72440910: all 86 eval/step pairs match byte-for-byte with the parent-workspace receipt. [Standalone replay evidence](verification/evidence/standalone_dot32_chain.json). Its offline #279 plan was checked to select exactly the 49 BSC receipt inputs.

## Later physical-workflow receipt / 后续物理流程回执

[Run 37334330241](https://github.com/JogJohgoeg/tt-nand-hardwired/actions/runs/37334330241), at the same bd1876b commit, reports **gds, precheck, gl_test and viewer all successful**. [Read-only status receipt](verification/evidence/gds_rerun_bd1876b.json). The measured area/timing table above remains sourced from run 37331447516 artifacts. This update does not establish the still-pending wrapper CEC or a paid submission.

同提交的后续物理工作流四项均成功，含可选 viewer；不据此推断设置由谁改变。上文面积/时序仍绑定初次成功物理 job 的原始 artifact；wrapper 新证明仍待 Actions。


## 8e139cf control-verdict fix

[Formal run 37353300366](https://github.com/JogJohgoeg/tt-nand-hardwired/actions/runs/37353300366) passed both cores again. The leaking-X fixture produced `ERROR: Called with -verify and proof did fail!`; the old parser incorrectly also required `model found: FAIL!`. The replacement recognizes explicit counterexamples with exit code 1 and rejects timeouts, signals, generic errors and contradictory verdicts. Four local parser tests include the actual runner log. The SAT query and all 385 output/state/clock obligations are unchanged; full wrapper proof remains pending. [Run receipts](verification/evidence/ci_8e139cf.json). [GDS run 37353300337](https://github.com/JogJohgoeg/tt-nand-hardwired/actions/runs/37353300337) passes gds/precheck/gl_test/viewer; its status does not replace the earlier measured area/timing artifacts.

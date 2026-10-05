# H2 validation report / 首片验证报告

2026-10-05: the local RTL and interface checks pass. Formal, GDS, precheck and routed gate simulation await GitHub Actions results. The requested configuration is **1x2 tiles at 10 MHz**, not an achieved area or timing result. No physical silicon or full-language-model performance is claimed.

本地 RTL 与接口验证已通过。2 tile、10 MHz 为待验证配置；形式等价、GDS、precheck 和布线后仿真等待 Actions。DOT 权重从输入提供，首片还不包含完整模型或权重 ROM。

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
| Yosys/ABC CEC | Both cores and wrapper, reset base case and negative control | Prepared, pending Actions |
| SKY130 physical flow | Official ttsky26d GDS / precheck / gate simulation | Pending Actions |

Raw source SHA-256 values are `f35baa03be7f9eefba33d778e0ff5b6e1430ccbb7b5b4a9daa81695b186c26c0` (#279, 21 NAND) and `b1507f55d3bd80bbc55f9e06dc656d81e049138827c97ec7fe640d7bfa2ce0b7` (DOT32_T, 3,829 NAND). Both contain zero latches. The wrapper adds 358 declared state bits. The core counts describe the pre-synthesis source records, not physical standard-cell counts.

[Local receipts](verification/evidence/) bind results to file hashes. The archived `simulation.json` and `wrapper.json` were produced in the parent H2 workspace; their source names are local to that workspace. `cores-local.json`, `cocotb-local.xml` and `local-files.json` bind this standalone repository's actual files and renamed top. The original wrapper bug and harness failures were preserved in the parent audit: wrong serial shift direction and an ineffective testbench reset. The current regression detects the old wrapper. Full Icarus serial testing hit a 240 s cap; the full serial dataset passes on Verilator and the explicitly counted Icarus subset passes.

[Chain receipt](verification/evidence/chain.json): BSC CPU 732 at `0x6Fb4089e7Cbaa9660Fd11056274Cbd8117EE5B38`, block hash `0xb6c853eaca577dc6800ef5e57226a579ed13712f6bba689783eaf2051428a27e`. The exact #279 raw bytes and raw eval/step returns are retained. This is not DOT chain evidence. Per the user's decision, DOT targets X Layer #245 at `0xA93E807fAB41431827EBBa57443Fb687a95E2AA3`; the user published circuit **#3@2.245**. Independent [canonical verification](verification/evidence/xlayer_dot32_cid3.json) passed all 86 eval/step pairs at block **72440910**, hash `0xeb6ff9611314755b572a4a1a77de55fd2572759db001f798a858a5c54e3404a5`. Published raw bytes match the source and burn JSON exactly.

[Burn JSON and proof](verification/burn/) contain the complete unsigned netlist payload and its local L1 proof. The standalone verification command is `python verification/verify_burn.py 20` with the NumPy version pinned in `verification/requirements.txt` (Python 3.11 recommended); it reopens the JSON and runs the original upstream DOT generator in bounded batches. It uses a fresh seed 21, not the historical multi-component run's advanced RNG stream. New receipts are written to `build/`. The existing million-sample receipt remains unchanged.

本地逐位证据、负对照和文件哈希均已保留。#279 已核对原始链上网表及同批 eval/step。DOT 已发布为 #3@2.245，独立 86 组链上 eval/step 逐位通过；最终 JSON 对 L1 全百万向量通过，但这不等于全部 2^320 输入的形式证明；现有 L2 没有 DOT 项目。泛用综合的 CEC 也不等于最终布线网表的形式签核，后者另有官方 GL 有限向量测试。

The [official schedule](https://tinytapeout.com/chips/) lists **TTSKY26d closing 2026-11-30**, estimated shipping **2027-06-09**. The [calculator](https://app.tinytapeout.com/calculator?shuttle=chipfoundry&tiles=2&pcbs=1) and its [public pricing module](https://app.tinytapeout.com/_build/assets/invoice-WoZjomWD.js), checked 2026-10-05, give €70/tile. Two tiles cost €140; one standard €300 kit plus €15 shipping makes €455, or €255 with the limited €100 individual kit. Discount eligibility, inventory, taxes and final checkout are unconfirmed. [Pricing snapshot](verification/evidence/pricing.json). No order has been submitted.

当前报价两 tile €140；加普通开发板与列明的运费 €455，有个人优惠时 €255。最终费用取决于实际尺寸、优惠与结算；本项目未付费提交。

| Related work | Comparison |
|---|---|
| [Taalas HC1](https://taalas.com/products/) | Vendor's complete Llama 3.1 8B hardwired demonstrator, 6 nm and 815 mm². Its advertised 17k tokens/s/user is not comparable to our serial arithmetic prototype. |
| [Ankhdjet](https://arxiv.org/abs/2608.26206) | Open ternary checkpoint-to-via-mask compiler on SKY130; paper reports signoff and a TTSKY26c demonstrator submission. Relevant to future fixed-weight storage. |
| [tiny-asic 1.58-bit matrix multiply](https://github.com/rejunity/tiny-asic-1_58bit-matrix-mul) | Open ternary arithmetic with streamed packed weights and simulation-based performance. Our first milestone emphasizes byte-pinned source netlists and canonical chain checks. |

三者分别对应完整模型硬化、开源掩膜 ROM 编译、三值算术。首片当前验证门网表到芯片 RTL 的可核对链路，不以不同工艺与规模的 token/s 或能耗作直接比较。三值的信息量约 1.585 位；本接口实际使用每权重两位。

The standalone public replay script was also run against block 72440910: all 86 eval/step pairs match byte-for-byte with the parent-workspace receipt. [Standalone replay evidence](verification/evidence/standalone_dot32_chain.json). Its offline #279 plan was checked to select exactly the 49 BSC receipt inputs.

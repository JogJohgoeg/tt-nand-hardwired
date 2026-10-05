# DOT32_T X Layer #245 flow input

`dot32_t_xlayer.json` is the requested transaction input artifact. It contains 26,803 raw bytes, 3,829 NAND records, 320 inputs, 32 outputs and no latches. Each NAND record is opcode 0, then two unsigned 24-bit big-endian wire IDs. Output bits are the last 32 wire values. `sha256` hashes the raw decoded bytes, not the JSON text or the `0x` prefix:

`b1507f55d3bd80bbc55f9e06dc656d81e049138827c97ec7fe640d7bfa2ce0b7`

Target supplied by the user: X Layer (chain 196), TapeID #245, circuit contract `0xA93E807fAB41431827EBBa57443Fb687a95E2AA3`, method `tapeout(bytes,uint32,uint32)`. Claude handles transaction simulation, minting, signature UI and publication. This package performed zero transactions and does not claim publication.

`verification.json` records successful decoding of this exact JSON followed by all **1,000,016** samples from the original `21nandkit/l1.py:case_dot(20)` generator (fresh standalone NumPy RNG seed 21), comparing **32,000,512** output bits to `golden.py`, with zero mismatches. It includes the artifact, source and vector hashes, NumPy version and negative control. This reproduces the published L1 multiplier; its fresh DOT RNG stream differs from the historical multi-component run's advanced stream. Batches contain at most 256 vectors. L2 is **not applicable**: the existing `21nandkit/l2.py` has only FMUL_BF16, no DOT32_T vectors. No L2 pass is claimed.

Reproduce from this standalone repository (NumPy required; fresh receipt is written under build/):

```sh
python3 -m pip install -r verification/requirements.txt
python3 verification/verify_burn.py 20
```

For lane j, signed int8 q occupies input bits 8j..8j+7; the weight code occupies 256+2j..257+2j. Codes 00/01/10/11 mean 0/+1/-1/0. The output is sum(q*w) modulo 2^32.

本文件可直接交给 Claude 构建流片调用。最终 JSON 内的网表已重新解码，对全部 1,000,016 个 L1 样本逐位通过；现有 L2 不含 DOT，不冒充通过。授权的链上操作仍由 Claude 执行；发布后补芯片与链上电路的等价证据。

Publication update (2026-10-05): the user published this exact netlist as **#3@2.245**. Independent canonical verification passed 86 eval/step pairs at X Layer block **72440910**, hash `0xeb6ff9611314755b572a4a1a77de55fd2572759db001f798a858a5c54e3404a5`. See `../evidence/xlayer_dot32_cid3.json`. The original million-vector receipt remains a local-validation record, with zero transactions by this verifier.

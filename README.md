# Auditable NAND hard logic on Tiny Tapeout

A SKY130 Tiny Tapeout candidate containing circuit #279 (21 NANDs) and DOT32_T (3,829 NANDs), generated mechanically from pinned TapeOut gate records. DOT weights are runtime inputs; this is a first arithmetic demonstrator, not a complete hardwired LLM.

The [datasheet](docs/info.md) specifies the serial protocol. [Verification evidence](verification/evidence/) records local tests and both cores’ canonical chain checks. Actions **bd1876b** passed both core CEC jobs and **2x2 GDS, precheck and gate simulation**; wrapper formal remains pending. The [report](REPORT.md) includes measured area/timing, the internal-X proof fix and the **+€140 tile-fee** comparison.

```sh
python verification/gen_verilog.py --check
python verification/test_cores.py
python -m pip install -r test/requirements.txt
cd test
make
python -m cocotb_tools.check_results results.xml
```

These commands run Python and small gate simulations only. Yosys/ABC synthesis and formal checks run in [GitHub Actions](.github/workflows/formal.yaml); the [proof method](verification/FORMAL.md) covers all ports, wrapper state transitions and reset. The official `ttsky26d` actions produce GDS, precheck and gate-level simulation. A local metadata-only preview is `python verification/formal.py --prepare`. No local synthesis is required.

Generated cores must be changed by changing the source records and regenerating them. All new code is MIT ([LICENSE-MIT](LICENSE-MIT)); the inherited Tiny Tapeout template remains Apache-2.0 ([LICENSE](LICENSE)). The protocol specification is CC0-1.0 ([LICENSE-SPEC](LICENSE-SPEC)).

Read-only chain replay (standard library; public RPC access required):

```sh
python verification/verify_chain.py --core cell_279
python verification/verify_chain.py --core dot32_t --block 72440910
```

The published DOT circuit is #3@2.245. These scripts make only canonical `eth_call`/metadata requests, with no state overrides or transactions.

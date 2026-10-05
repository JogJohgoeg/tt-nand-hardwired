# SPDX-License-Identifier: MIT
"""Test false-pass handling without running Yosys, ABC, synthesis or SAT."""
import unittest
from pathlib import Path

from formal import cec_result, invert_output, sat_verify_result


class FormalHarnessTest(unittest.TestCase):
    def test_yosys_verify_counterexample_formats_and_errors(self):
        fatal = 'ERROR: Called with -verify and proof did fail!'
        passed = 'SAT proof finished - no model found: SUCCESS!'
        failed = 'SAT proof finished - model found: FAIL!'
        self.assertEqual(sat_verify_result(0, passed), 'proved')
        for message in (fatal, failed, failed+'\n'+fatal):
            self.assertEqual(sat_verify_result(1, message), 'counterexample')
        for code, message in ((0, fatal), (-9, fatal), (1, ''), (1, passed),
                              (1, 'ERROR: No such command: sat'),
                              (1, 'ERROR: Called with -verify and proof did time out!'),
                              (1, fatal+'\nInterrupted SAT solver: TIMEOUT!'),
                              (1, fatal+'\nERROR: cannot read input'), (1, passed+'\n'+fatal)):
            with self.subTest(code=code, message=message):
                self.assertEqual(sat_verify_result(code, message), 'error')

    def test_actual_8e139cf_negative_log(self):
        fixture = Path(__file__).parent/'evidence/formal_8e139cf/undef_leaking.log'
        output = fixture.read_text()
        self.assertNotIn('model found: FAIL!', output)
        self.assertEqual(sat_verify_result(1, output), 'counterexample')

    def test_abc_zero_exit_is_not_a_proof(self):
        for text in ('', 'ABC command line: cec gold.blif gate.blif',
                     'Networks are undecided (SAT solver timed out).',
                     'Miter computation has failed.',
                     'Networks are equivalent.\nError: bad network',
                     'Networks are equivalent.\nNetworks are NOT EQUIVALENT.'):
            with self.subTest(text=text):
                self.assertEqual(cec_result(0, text), 'error')
        self.assertEqual(cec_result(1, 'Networks are equivalent.'), 'error')
        self.assertEqual(cec_result(0, 'Networks are equivalent after fraiging.\n'), 'equivalent')
        # ABC reports this counterexample with exit code zero and the word failed.
        self.assertEqual(cec_result(0, 'Networks are NOT EQUIVALENT after SAT.\n'
                                   'Verification failed for at least 1 output: y\n'), 'different')

    def test_flip_keeps_interface_and_other_output_logic(self):
        source = '.model test\n.inputs a\n.outputs y z\n.names a y\n1 1\n.names y z\n1 1\n.end\n'
        changed = invert_output(source, 'y')
        self.assertEqual(changed, '.model test\n.inputs a\n.outputs y z\n'
                         '.names a __negative_value\n1 1\n.names __negative_value z\n1 1\n'
                         '.names __negative_value y\n0 1\n.end\n')
        with self.assertRaises(AssertionError):
            invert_output(source, 'missing_output')


if __name__ == '__main__':
    unittest.main()

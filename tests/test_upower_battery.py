from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from controller_battery import parse_upower, read_battery, read_upower

PATH = '/org/freedesktop/UPower/devices/gaming_input_dev_F9_7C_A2_6D_17_58'
INFO = 'model: Stadia26X8-1758\nserial: F9:7C:A2:6D:17:58\npercentage: 99%\n'


class UPowerTests(unittest.TestCase):
    def test_actual_controller_format_reports_percent_without_voltage(self):
        data = parse_upower(INFO)
        self.assertEqual(data['percent'], 99)
        self.assertIsNone(data['voltage'])

    def test_voltage_only_when_available_and_positive(self):
        self.assertEqual(parse_upower(INFO + 'voltage: 3.75 V\n')['voltage'], 3.75)
        self.assertIsNone(parse_upower(INFO + 'voltage: 0 V\n')['voltage'])
        self.assertIsNone(parse_upower('percentage: 999%\n')['percent'])

    def test_coarse_levels_do_not_claim_exact_percent(self):
        result = parse_upower('percentage: 50%\nbattery-level: low\n')
        self.assertIsNone(result['percent'])
        self.assertEqual(result['status'], 'Low')

    def test_matches_only_connected_controller_address(self):
        other = '/org/freedesktop/UPower/devices/gaming_input_dev_AA_BB_CC_DD_EE_FF'
        with patch('controller_battery.subprocess.run', side_effect=[Mock(stdout=other + '\n' + PATH), Mock(stdout=INFO)]) as run:
            self.assertEqual(read_upower('F9:7C:A2:6D:17:58', 'Stadia')['percent'], 99)
            self.assertEqual(run.call_args.args[0], ['upower', '-i', PATH])

    def test_falls_back_when_sysfs_has_no_controller_data(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch('controller_battery.read_upower', return_value=parse_upower(INFO)):
            result = read_battery('F9:7C:A2:6D:17:58', 'Stadia', Path(directory))
            self.assertEqual(result['percent'], 99)
            self.assertIsNone(result['voltage'])

    def test_absent_service_or_utility_is_optional(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired('upower', 1)):
            with patch('controller_battery.subprocess.run', side_effect=error):
                self.assertIsNone(read_upower('F9:7C:A2:6D:17:58', 'Stadia'))

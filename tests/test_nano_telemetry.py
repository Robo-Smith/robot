import unittest
from unittest.mock import Mock
from nano_telemetry import NanoTelemetry


class TelemetryTests(unittest.TestCase):
    def test_partial_and_multiple_frames(self):
        telemetry = NanoTelemetry()
        telemetry.feed(b'T120,1000,0,20,0,500', now=10)
        self.assertFalse(telemetry.snapshot(now=10)['available'])
        telemetry.feed(b',-250,0,9000\nT40,900,0,10,0,250,250,0,9200\n', now=10)
        data = telemetry.snapshot(now=10)
        self.assertEqual(data['distance_cm'], 40)
        self.assertEqual(data['applied_outputs'], [.25, .25, 0])
        self.assertEqual(data['tof_state'], 'slow')

    def test_same_distance_thresholds_as_firmware(self):
        for distance, expected in ((19, 'stop'), (20, 'slow'), (100, 'slow'), (101, 'clear')):
            telemetry = NanoTelemetry()
            telemetry.feed(f'T{distance},1000,0,0,0,0,0,0,1\n'.encode(), now=1)
            self.assertEqual(telemetry.snapshot(now=1)['tof_state'], expected)

    def test_sensor_quality_and_packet_staleness_are_distinct(self):
        telemetry = NanoTelemetry()
        telemetry.feed(b'T100,10,0,0,0,0,0,0,1\n', now=1)
        self.assertEqual(telemetry.snapshot(now=1)['tof_state'], 'unreliable')
        telemetry.feed(b'T100,1000,600,0,0,0,0,0,1\n', now=1)
        self.assertEqual(telemetry.snapshot(now=1)['tof_state'], 'sensor_stale')
        self.assertEqual(telemetry.snapshot(now=3)['tof_state'], 'stale')
        self.assertFalse(telemetry.snapshot(now=3)['sensor_valid'])

    def test_oversize_and_malformed_lines_do_not_replace_valid_reading(self):
        telemetry = NanoTelemetry()
        telemetry.feed(b'T20,1000,0,0,0,0,0,0,1\n', now=1)
        telemetry.feed(b'X' * 200 + b'T1,1000,0,0,0,0,0,0,1\n', now=2)
        for bad in (b'Tx,1\n', b'T20,1000,0,0,2,0,0,0,1\n', b'T20,1000,0,0,0,1001,0,0,1\n'):
            telemetry.feed(bad, now=2)
        self.assertEqual(telemetry.snapshot(now=1)['distance_cm'], 20)
        self.assertEqual(telemetry.received, 1)
        telemetry.feed(b'T15,1000,0,600,1,0,0,0,2\n', now=3)
        self.assertTrue(telemetry.snapshot(now=3)['watchdog'])

    def test_serial_reads_are_bounded_and_do_not_wait_for_line(self):
        telemetry = NanoTelemetry()
        serial = Mock(in_waiting=2000)
        serial.read.return_value = b'boot message\n'
        telemetry.read(serial)
        serial.read.assert_called_once_with(512)
        serial.in_waiting = 0
        serial.read.reset_mock()
        telemetry.read(serial)
        serial.read.assert_not_called()

    def test_old_firmware_is_explicitly_unavailable(self):
        self.assertFalse(NanoTelemetry().snapshot()['fresh'])

    def test_worst_case_frame_fits_avr_transmit_buffer(self):
        line = b'T65535,65535,65535,65535,1,-1000,-1000,-1000,4294967295\n'
        self.assertLessEqual(len(line), 63)
        telemetry = NanoTelemetry()
        telemetry.feed(line, now=1)
        self.assertTrue(telemetry.snapshot(now=1)['available'])

    def test_sonar_frames_are_independent_of_tof_packets(self):
        telemetry = NanoTelemetry()
        telemetry.feed(b'S120,45,0,10\n', now=1)
        data = telemetry.snapshot(now=1.1)
        self.assertFalse(data['available'])
        self.assertEqual(data['sonar']['left']['distance_cm'], 120)
        self.assertEqual(data['sonar']['right']['distance_cm'], 45)
        self.assertEqual(data['sonar']['left']['state'], 'ok')
        self.assertEqual(telemetry.snapshot(now=1.7)['sonar']['left']['state'], 'stale')

    def test_no_echo_is_not_zero_distance(self):
        telemetry = NanoTelemetry()
        telemetry.feed(b'S0,200,0,0\n', now=1)
        sonar = telemetry.snapshot(now=1)['sonar']
        self.assertIsNone(sonar['left']['distance_cm'])
        self.assertEqual(sonar['left']['state'], 'no_echo')
        self.assertEqual(sonar['right']['distance_cm'], 200)

    def test_bad_sonar_frames_do_not_refresh_good_readings(self):
        telemetry = NanoTelemetry()
        telemetry.feed(b'S12,34,0,0\n', now=1)
        for line in (b'S201,20,0,0\n', b'S12,20,-1,0\n', b'S12,20,0\n', b'Sx,20,0,0\n'):
            telemetry.feed(line, now=2)
        self.assertEqual(telemetry.sonar_received, 1)
        self.assertEqual(telemetry.snapshot(now=1)['sonar']['left']['distance_cm'], 12)

    def test_partial_sonar_and_tof_frames_can_be_interleaved(self):
        telemetry = NanoTelemetry()
        telemetry.feed(b'S12,', now=1)
        telemetry.feed(b'34,0,0\nT120,1000,0,0,0,500,500,0,100\n', now=1)
        data = telemetry.snapshot(now=1)
        self.assertEqual(data['distance_cm'], 120)
        self.assertEqual(data['sonar']['right']['distance_cm'], 34)
        self.assertLess(len(b'S200,200,65535,65535\n'), 63)

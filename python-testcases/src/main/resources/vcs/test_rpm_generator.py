"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     September 2015
@author:    Zlatko Masek, Boyan Mihovski
@summary:   Unittests
"""
import unittest
import mock
from rpm_generator import (generate_rpm,
                           generate_rpms)


class TestRpmGenerator(unittest.TestCase):
    """
    Test suite for rpm_generator function.
    """

    def setUp(self):
        self.story = 9600
        self.package_count = 1
        self.script = 'test-lsb-9600-1'

    @mock.patch('rpm_generator.generate_rpm')
    def test_generate_rpms(self, _generate_rpm):
        """ Procedure:
            1. Generate a rpm package by story id
            ---------
            Verification:
            2. Verify no errors occurred
        """
        generate_rpms(story=self.story, package_count=self.package_count)
        _generate_rpm.assert_called_with(str(self.story), self.package_count)

    @mock.patch('os.chmod')
    @mock.patch('os.stat')
    @mock.patch('subprocess.Popen')
    @mock.patch('os.remove')
    @mock.patch('shutil.rmtree')
    @mock.patch('glob.glob')
    def test_generate_rpm(self, _glob, _rmtree, _remove,
                          _popen, _stat, _chmod):
        """
        Procedure:
            1. Generate a rpm package by story id
            ---------
            Verification:
            2. Verify no errors occurred
            3. Verify generate rpm is called once.
            3. Verify correct permissions are applied.
            3. Verify build temp files are removed.
        """
        _stat.return_value = mock.Mock(st_mode=0)
        process = mock.MagicMock()
        process.communicate.return_value = 'stdout', 'stderr'
        process.returncode = 0
        _popen.return_value = process
        mocked_open = mock.mock_open()
        with mock.patch('__builtin__.open', mocked_open, create=True):
            generate_rpm(str(self.story), self.package_count)
        _stat.assert_called_once_with(self.script)
        _chmod.assert_called_once_with(self.script, 73)
        self.assertEqual(mocked_open.call_count, 2)
        _rmtree.assert_called_once_with('build')
        self.assertEqual(_glob.call_count, 2)
        self.assertEqual(_remove.call_count, 3)

if __name__ == '__main__':
    unittest.main()

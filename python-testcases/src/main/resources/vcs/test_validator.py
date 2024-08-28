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
import codecs
from generate import (_extract_invalid_options,
                      _validate_key_input,
                      _serialize_options,
                      _tokenize_params,
                      _validate_input,
                      _get_fragment,
                      _generate_item_data,
                      generate_json,
                      _write_json,
                      validate_fixtures,
                      apply_item_changes,
                      apply_options_changes,
                      load_fixtures)
from os import path
from jsonschema import ValidationError


class TestValidation(unittest.TestCase):
    """
    Test suite for test validation function.
    """

    def test_extract_invalid_options(self):
        """ Procedure:
            1. Specify with invalid values.
            ---------
            Verification:
            2. Verify only valid values are returned.
        """
        input_values = 'prop="value" asd 123 "" = prop2=value2 prop3="value3"'
        result = _extract_invalid_options(input_values)
        self.assertEqual(['asd', '123', '""', '=', 'prop2=value2'], result)

    def test_validate_key_input_positive_vcso(self):
        """ Procedure:
            1. Specify valid values for vcso.
            ---------
            Verification:
            2. Verify no wrong values are returned.
        """
        self.assertEqual({},
                         _validate_key_input(
            'offline_timeout="401" online_timeout="401"',
            {'offline_timeout': int, 'online_timeout': int}
        )
        )

    def test_validate_key_input_positive_ao(self):
        """ Procedure:
            1. Specify valid values for ao.
            ---------
            Verification:
            2. Verify no wrong values are returned.
        """
        def validate_commands(string):
            """ Procedure:
                1. Specify valid values for start stop commands.
                ---------
                Verification:
                2. Verify no value error is returned.
            """
            app_path, _, command = string.split()

            if (not path.isabs(app_path) or
                    command not in ('start', 'stop')):
                raise ValueError

        self.assertEqual({}, _validate_key_input(
            'name="something" stop_command="/sbin/service test-lsb- stop"',
            {'name': lambda x: None, 'stop_command': validate_commands},
        ))

    def test_validate_key_input_false_ao(self):
        """ Procedure:
            1. Specify invalid values for ao.
            ---------
            Verification:
            2. Verify only wrong values are returned.
        """
        def validate_commands(string):
            """
            Validate app commands.
            """
            app_path, _, command = string.split()

            if (not path.isabs(app_path) or
                    command not in ('start', 'stop')):
                raise ValueError

        self.assertEqual({'invalid_values': ['stop_command']},
                         _validate_key_input(
            'name="something" stop_command="/sbin/service test-lsb- stp"',
            {'name': lambda x: None, 'stop_command': validate_commands},
        ))

    @mock.patch('sys.exit')
    def test_validate_input_positive(self, _exit):
        """ Procedure:
            1. Specify valid values for vcs_options, app_options, hsc_options.
            ---------
            Verification:
            2. Verify only wrong values are returned.
        """
        vcs_options = 'offline_timeout="180"'
        app_options = ''
        hsc_options = ''
        vip_options = ''
        _validate_input(vcs_options, app_options, hsc_options, vip_options)
        self.assertFalse(_exit.called)

    @mock.patch('sys.exit')
    def test_validate_input_negative(self, _exit):
        """ Procedure:
            1. Specify invalid values for vcs_options,
            app_options, hsc_options.
            ---------
            Verification:
            2. Verify only wrong values are returned.
        """
        vcs_options = 'some_timeout="180"'
        app_options = ''
        hsc_options = ''
        vip_options = ''
        _validate_input(vcs_options, app_options, hsc_options, vip_options)
        _exit.assert_any_call(1)
        self.assertTrue(_exit.called)


class TestGenerator(unittest.TestCase):
    """ Procedure:
        1. Specify invalid values for vcs_options,
        app_options, hsc_options.
        ---------
        Verification:
        2. Verify only wrong values are returned.
    """

    def setUp(self):
        self.story = '9600'
        self.number = 1
        self.length = 1
        self.options = 'opt1="val1" opt2="2"'
        self.dummy_dict = {'opt1': 'val1', 'opt2': 2}

    def test_serialize_options(self):
        """ Procedure:
            1. Specify valid options and
            serialize them.
            ---------
            Verification:
            2. Verify the output.
        """
        options = {'opt1': 'val1', 'opt2': 2}
        serialized = _serialize_options(options)
        self.assertEqual(serialized, 'opt1="val1" opt2="2"')

    def test_tokenize_params(self):
        """ Procedure:
            1. Specify valid options and
            tokenize them.
            ---------
            Verification:
            2. Verify the output.
        """
        input_values = 'opt1="val1" opt2="2"'
        result = _tokenize_params(input_values)
        self.assertEqual(result, {'opt1': 'val1', 'opt2': '2'})

    def test_get_fragment_service(self):
        """ Procedure:
            1. Specify 'service' item.
            ---------
            Verification:
            2. Verify the output.
        """
        name = 'service'
        fragment = _get_fragment(name)
        self.assertEqual(fragment, 'APP')

    def test_get_fragment_service_config(self):
        """ Procedure:
            1. Specify 'ha-service-config' item.
            ---------
            Verification:
            2. Verify the output.
        """
        name = 'ha-service-config'
        fragment = _get_fragment(name)
        self.assertEqual(fragment, 'HSC')

    def test_get_fragment_vcs(self):
        """ Procedure:
            1. Specify 'vcs-clustered-service' item.
            ---------
            Verification:
            2. Verify the output.
        """
        name = 'vcs-clustered-service'
        fragment = _get_fragment(name)
        self.assertEqual(fragment, 'CS')

    def test_get_fragment_vip(self):
        """ Procedure:
            1. Specify 'vip' item.
            ---------
            Verification:
            2. Verify the output.
        """
        name = 'vip'
        fragment = _get_fragment(name)
        self.assertEqual(fragment, 'VIP')

    @mock.patch('generate.generate_rpm')
    def test_generate_item_data_vcs(self, _generate_rpm):
        """ Procedure:
            1. Specify item data vcs generate prerequisites and generate it.
            ---------
            Verification:
            2. Verify the output.
        """
        name = 'vcs-clustered-service'
        items = _generate_item_data(
            name, self.story, self.length, self.options, False)
        expected_items = [
            {
                'id': 'CS_9600_1',
                'vpath': '/services/CS_9600_1',
                'options': {
                    'active': '1',
                    'standby': '0',
                    'name': 'CS_9600_1',
                    'opt1': 'val1',
                    'opt2': '2'
                },
                'options_string': 'active="1" standby="0" opt1="val1" '
                'name="CS_9600_1" opt2="2"',
                'add_to_cleanup': False,
            }
        ]
        self.assertEqual(items, expected_items)

    @mock.patch('generate.generate_rpm')
    def test_generate_item_data_service(self, _generate_rpm):
        """ Procedure:
            1. Specify item data service generate prerequisites and
                generate it.
            ---------
            Verification:
            2. Verify the output.
        """
        name = 'service'
        items = _generate_item_data(
            name, self.story, self.length, self.options, False)
        expected_items = [
            {
                'package_id': 'EXTR-lsbwrapper-9600-1',
                'package_vpath': '/software/items/EXTR-lsbwrapper-9600-1',
                'package_destination': '/software/services/APP_9600_1/packages'
                '/EXTR-lsbwrapper-9600-1',
                'id': 'APP_9600_1',
                'vpath': '/software/services/APP_9600_1',
                'destination': '/services/CS_9600_1/applications/APP_9600_1',
                'parent': 'CS_9600_1',
                'options': {
                    'service_name': 'test-lsb-9600-1',
                    'opt1': 'val1',
                    'opt2': '2'
                },
                'options_string': 'service_name="test-lsb-9600-1" opt1="val1"'
                ' opt2="2"',
                'add_to_cleanup': False,
            }
        ]
        self.assertEqual(items, expected_items)

    @mock.patch('generate.generate_rpm')
    def test_generate_item_vip_service(self, _generate_rpm):
        """ Procedure:
            1. Specify item data service generate prerequisites and
                generate it.
            ---------
            Verification:
            2. Verify the output.
        """
        name = 'vip'
        items = _generate_item_data(
            name, self.story, self.length, self.options, False)
        expected_items = [
            {
                'id': 'VIP_9600_1',
                'vpath': '/services/CS_9600_1/'
                'ipaddresses/ip_VIP_9600_1',
                'options': {
                    'opt1': 'val1',
                    'opt2': '2'
                },
                'options_string': 'opt1="val1"'
                ' opt2="2"',
                'add_to_cleanup': False,
            }
        ]
        self.assertEqual(items, expected_items)

    @mock.patch('generate.generate_rpm')
    def test_generate_item_data_service_config(self, _generate_rpm):
        """ Procedure:
            1. Specify item data service_config generate prerequisites and
                generate it.
            ---------
            Verification:
            2. Verify the output.
        """
        name = 'ha-service-config'
        items = _generate_item_data(
            name, self.story, self.length, self.options, False)
        expected_items = [
            {
                'id': 'HSC_9600_1',
                'vpath': '/services/CS_9600_1/ha_configs/HSC_9600_1',
                'options': {
                    'opt1': 'val1',
                    'opt2': '2'
                },
                'options_string': 'opt1="val1" opt2="2"',
                'parent': 'CS_9600_1',
                'add_to_cleanup': False,
            }
        ]
        self.assertEqual(items, expected_items)

    @mock.patch('generate.generate_rpm')
    def test_generate_item_data_service_config_multi(self, _generate_rpm):
        """ Procedure:
            1. Specify items data service_config generate prerequisites and
                generate it.
            ---------
            Verification:
            2. Verify the output.
        """
        name = 'ha-service-config'
        items = _generate_item_data(name, self.story, 2, self.options, False)
        expected_items = [
            {
                'id': 'HSC_9600_1',
                'vpath': '/services/CS_9600_1/ha_configs/HSC_9600_1',
                'options': {
                    'opt1': 'val1',
                    'opt2': '2',
                    'service_id': 'APP_9600_1',
                },
                'options_string': 'service_id="APP_9600_1" opt1="val1" '
                'opt2="2"',
                'parent': 'CS_9600_1',
                'add_to_cleanup': False,
            },
            {
                'id': 'HSC_9600_2',
                'vpath': '/services/CS_9600_1/ha_configs/HSC_9600_2',
                'options': {
                    'opt1': 'val1',
                    'opt2': '2',
                    'service_id': 'APP_9600_2',
                },
                'options_string': 'service_id="APP_9600_2" opt1="val1" '
                'opt2="2"',
                'parent': 'CS_9600_1',
                'add_to_cleanup': False,
            }
        ]
        self.assertEqual(items, expected_items)

    @mock.patch('json.dumps')
    @mock.patch('sys.exit')
    def test_write_json_negative(self, _exit, _dumps):
        """ Procedure:
            1. Specify wrong json values.
            ---------
            Verification:
            2. Verify the output.
        """
        _dumps.side_effect = ValueError
        with mock.patch.object(codecs, 'open', mock.mock_open()):
            _write_json('9600', self.dummy_dict)
        self.assertRaises(ValueError, _dumps)
        _exit.assert_any_call(1)

    @mock.patch('json.dumps')
    @mock.patch('sys.exit')
    def test_write_json_positive(self, _exit, _dumps):
        """ Procedure:
            1. Specify correct json values.
            ---------
            Verification:
            2. Verify the output.
        """
        with mock.patch.object(codecs, 'open', mock.mock_open()):
            _write_json('9600', self.dummy_dict)
        _dumps.assert_any_call(self.dummy_dict)
        self.assertFalse(_exit.called)

    @mock.patch('generate.generate_rpm')
    @mock.patch('codecs.open')
    @mock.patch('generate._write_json')
    def test_generate_json(self, __write_json, _open, _generate_rpm):
        """ Procedure:
            1. Specify full set of correct json values.
            ---------
            Verification:
            2. Verify the output.
        """
        story = 9600
        vcs_length = 1
        app_length = 1
        hsc_length = 1
        vip_length = 1
        vcs_options = 'offline_timeout="401" online_timeout="401"'
        app_options = ('service_name="something" stop_command="/bin/true"'
                       ' status_command="/sbin/service test-lsb- status" '
                       'start_command="/sbin/service test-lsb- start"')
        hsc_options = 'clean_timeout="700"'
        vip_options = 'network_name="traffic1" ipaddress="172.17.100.83"'
        generate_json(story=story, vcs_length=vcs_length,
                      app_length=app_length, hsc_length=hsc_length,
                      vip_length=vip_length, vcs_options=vcs_options,
                      app_options=app_options, hsc_options=hsc_options,
                      vip_options=vip_options)
        self.assertTrue(__write_json.called)


class TestHelperMethods(unittest.TestCase):
    """
    Test suite for validator helper functions.
    """

    def setUp(self):
        self.fixtures = {
            "litp_default_values":
            {
                "vcs-clustered-service":
                {
                    "online_timeout": "300",
                    "offline_timeout": "300"
                },

                "service":
                {
                    "cleanup_command": "/bin/true"
                },

                "ha-service-config":
                {
                    "clean_timeout": "60",
                    "fault_on_monitor_timeouts": "4",
                    "tolerance_limit": "0"
                },
                "vip": {
                    "ipaddress": "172.17.100.83",
                    "network_name": "traffic1",
                },
            },

            "service":
            [
                {
                    "package_vpath": "/software/items/EXTR-lsbwrapper-9600-1",
                    "parent": "CS_9600_1",
                    "options_string": "service_name=\"test-lsb-9600-1\"",
                    "destination":
                        "/services/CS_9600_1/applications/APP_9600_1",
                    "id": "APP_9600_1",
                    "package_id": "EXTR-lsbwrapper-9600-1",
                    "package_destination": "/software/services/APP_9600_1/\
                        packages/EXTR-lsbwrapper-9600-1",
                    "add_to_cleanup": False,
                    "options":
                    {
                        "service_name": "test-lsb-9600-1"
                    },
                    "vpath": "/software/services/APP_9600_1"
                }
            ],

            "ha-service-config":
            [
                {
                    "parent": "CS_9600_1",
                    "add_to_cleanup": False,
                    "id": "HSC_9600_1",
                    "options_string": "service_id=\"APP_9600_1\" \
                        fault_on_monitor_timeouts=\"280\" \
                        tolerance_limit=\"300\"",
                    "options":
                    {
                        "service_id": "APP_9600_1",
                        "fault_on_monitor_timeouts": "280",
                        "tolerance_limit": "300"
                    },

                    "vpath": "/services/CS_9600_1/ha_configs/HSC_9600_1"
                }
            ],

            "vip":
            [
                {
                    "options_string": "vip_id=\"VIP_9600_1\"",
                    "add_to_cleanup": True,
                    "options":
                    {
                     "vip_id": "VIP_5168_1"
                    },

                    "vpath": "/services/CS_9600_1/ipaddresses/ip_VIP_9600_1",
                    "id": "VIP_9600_1"

                }
             ],

            "vcs-clustered-service":
            [
                {
                    "options_string": "active=\"1\" standby=\"0\"\
                         name=\"CS_9600_1\" online_timeout=\"180\"",
                    "add_to_cleanup": False,
                    "options":
                    {
                        "active": "1",
                        "standby": "0",
                        "name": "CS_9600_1",
                        "online_timeout": "180"
                    },

                    "vpath": "/services/CS_9600_1",
                    "id": "CS_9600_1"
                }
            ],

            "packages":
            [
                "EXTR-lsbwrapper-9600-1-1.0-1.noarch.rpm",
            ],

            "options":
            {
                "story": "9600",
                "hsc_length": 1,
                "vcs_length": 1,
                "app_length": 1,
                "vip_length": 1
            }
        }

    def test_load_fixtures(self):
        """ Procedure:
            1. Specify load_fixtures prerequisites.
            ---------
            Verification:
            2. Verify the output.
        """
        fixtures = load_fixtures(
            9600, '/deployments/d1/clusters/c1', ['n1'], self.fixtures)
        self.assertEqual(fixtures['service'][0]['destination'],
                         '/deployments/d1/clusters/c1/services/CS_9600_1/'
                         'applications/APP_9600_1')
        self.assertEqual(fixtures['vcs-clustered-service'][0]
                         ['options']['node_list'], 'n1')
        self.assertEqual(fixtures['vcs-clustered-service'][0]['vpath'],
                         '/deployments/d1/clusters/c1/services/CS_9600_1')
        self.assertEqual(fixtures['ha-service-config'][0]['vpath'],
                         '/deployments/d1/clusters/c1/services/CS_9600_1/'
                         'ha_configs/HSC_9600_1')
        self.assertEqual(fixtures['vip'][0]['vpath'],
                         '/deployments/d1/clusters/c1/services/CS_9600_1/'
                         'ipaddresses/ip_VIP_9600_1')

    def test_validate_fixtures(self):
        """ Procedure:
            1. Specify load_fixtures prerequisites and validate them.
            ---------
            Verification:
            2. Verify the output.
        """
        self.assertEqual(validate_fixtures(self.fixtures), None)

    def test_validate_fixtures_fail(self):
        """ Procedure:
            1. Specify validate_fixtures without args.
            ---------
            Verification:
            2. Verify the output.
        """
        self.assertRaises(ValidationError, validate_fixtures, '')

    def test_apply_options_changes(self):
        """ Procedure:
            1. Update fixtures data options.
            ---------
            Verification:
            2. Verify the output.
        """
        self.assertFalse('stop_command' in self.fixtures['service'][0]
                         ['options'])
        apply_options_changes(
            self.fixtures, 'service', 0, {'stop_command': '/bin/true'})
        self.assertTrue('stop_command' in self.fixtures['service'][0]
                        ['options'])

    def test_apply_item_changes(self):
        """ Procedure:
            1. Update fixtures data items.
            ---------
            Verification:
            2. Verify the output.
        """
        self.assertFalse(self.fixtures['service'][0]['add_to_cleanup'])
        apply_item_changes(
            self.fixtures, 'service', 0, {'add_to_cleanup': True})
        self.assertTrue(self.fixtures['service'][0]['add_to_cleanup'])

if __name__ == '__main__':
    unittest.main()

#! /usr/bin/python
"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     September 2015
@author:    Zlatko Masek, Boyan Mihovski
@summary:   Integration tests test data generator for testing VCS scenarios
            Agile: LITPCDS-10172
"""
import codecs
import json
import jsonschema
import sys
import optparse
import re
import logging
from collections import defaultdict
from schemas import FIXTURES_SCHEMA
from rpm_generator import generate_rpm

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

PARSER = optparse.OptionParser()
PARSER.add_option('--s', action='store', dest='story', type='int',
                  help='The number of the story. e.g. 9600')

PARSER.add_option('--a', action='store', dest='app_length', type='int',
                  default=0, help='The number of service items that will get '
                  'generated. '
                  'e.g. --a 3')
PARSER.add_option('--ao', action='store', dest='app_options', type='str',
                  default='', help='A string of options that are added to the'
                  ' service '
                  'items. e.g. --ao \'start_command="/bin/true" stop_command="'
                  '/bin/true"\'')

PARSER.add_option('--vcs', action='store', dest='vcs_length', type='int',
                  default=0, help='The number of vcs-clustered-service items '
                  'that will get '
                  'generated. e.g. --vcs 1')
PARSER.add_option('--vcso', action='store', dest='vcs_options', type='str',
                  default='', help='A string of options that are added to the '
                  'vcs-clustered-service items. e.g. --vcso '
                  '\'online_timeout="120" offline_timeout="120"\'')

PARSER.add_option('--hsc', action='store', dest='hsc_length', type='int',
                  default=0, help='The number of ha-service-config items that '
                  'will get '
                  'generated. e.g. --hsc 1. If using more than one service, '
                  'this number has to '
                  'match it. e.g. --a 3 --hsc 3')
PARSER.add_option('--hsco', action='store', dest='hsc_options', type='str',
                  default='', help='A string of options that are added to the '
                  'ha-service-config items. e.g. --hsco '
                  '\'restart_limit="2" startup_retry_limit="2"\'')

PARSER.add_option('--atc', action='store_true', dest='add_to_cleanup',
                  default=False, help='If used, the items are marked as add_'
                  'to_cleanup.')

PARSER.add_option('--vip', action='store', dest='vip_length', type='int',
                  default=0, help='The number of vip items '
                  'that will get generated. e.g. --vip 1')
PARSER.add_option('--vipo', action='store', dest='vip_options', type='str',
                  default='', help='A string of options that are added to the '
                  'vip items. e.g. --vipo \'ipaddress="192.168.1.1"\'')

PARSER.add_option('--trig', action='store', dest='vcs_trigger', type='int',
                  default=0, help='The number of trigger items '
                  'that will get generated. example --trig 1')
PARSER.add_option('--trigo', action='store', dest='trigger_options', type='str',
                  default='nofailover', help='A string option thats added to a'
                  'trigger item. example --trigo \'trigger_type="nofailover"\'')
PARSER.add_option('--version', action='store', dest='version', type='str',
                  default='1.0')

DEBUG = False

KEY_VALUE_REGEX = r'(\w+)="([\w/\-. ]+?)"'

VCS_PROPS = {
    'offline_timeout': lambda x: None,
    'online_timeout': lambda x: None,
    'active': lambda x: None,
    'standby': lambda x: None,
    'dependency_list': lambda x: None,
    'name': lambda x: None,
    'node_list': lambda x: None,
}

SERVICE_PROPS = {
    'cleanup_command': lambda x: None,
    'start_command': lambda x: None,
    'status_command': lambda x: None,
    'stop_command': lambda x: None,
    'service_name': lambda x: None,
}

HA_CONFIG_PROPS = {
    'status_interval': lambda x: None,
    'status_timeout': lambda x: None,
    'clean_timeout': lambda x: None,
    'dependency_list': lambda x: None,
    'fault_on_monitor_timeouts': lambda x: None,
    'restart_limit': lambda x: None,
    'service_id': lambda x: None,
    'startup_retry_limit': lambda x: None,
    'tolerance_limit': lambda x: None,
}

VIP_PROPS = {
    'ipaddress': lambda x: None,
    'network_name': lambda x: None,
}

TRIGGER_PROPS = {
    'trigger_type': lambda x: None
}


def _extract_invalid_options(input_value):
    """
    Return a list of invalid values in the input string if they are not
    matching the key="value" format.
    """
    key_value_regex = re.compile(KEY_VALUE_REGEX)
    invalid_options = key_value_regex.sub('', input_value).strip()
    return re.split(' +', invalid_options) if invalid_options else []


def _validate_key_input(input_values, validator_functions):
    """
    Validate if a generic input matches with what we request
    e.g. input_values: offline_timeout="401" online_timeout="401"
    """
    problems = defaultdict(list)
    invalid_options = _extract_invalid_options(input_values)
    if invalid_options:
        problems['invalid_options'] = invalid_options

    regex = re.compile(KEY_VALUE_REGEX)
    for param, value in regex.findall(input_values):
        try:
            validator_functions[param](value)
        except (ValueError, KeyError):
            problems['invalid_values'].append(param)

    return problems


def _serialize_options(options):
    """
    Return key-value pairs in the options dictionary as a space separated
    string in the key="value" format.
    """
    result = ['{0}="{1}"'.format(key, value) for key, value in options.items()]
    return ' '.join(result)


def _tokenize_params(input_values):
    """
    Split the input values that are in a string format into corresponding
    dictionary.
    """
    result = {}
    regex = re.compile(KEY_VALUE_REGEX)
    for left, right in regex.findall(input_values):
        result[left] = right
    return result


def _validate_input(vcs_options, app_options, hsc_options, vip_options,
                    trigger_options):
    """
    Validate incoming options with the defined properties for them. Otherwise
    exit the program.
    """
    arguments = (vcs_options, app_options, hsc_options, vip_options,
                 trigger_options)
    # only the following properties are allowed and will be validated against
    props = (VCS_PROPS, SERVICE_PROPS, HA_CONFIG_PROPS, VIP_PROPS,
             TRIGGER_PROPS)
    options_invalid = []
    for options, validators in zip(arguments, props):
        # validate the specific option with the validator for it
        invalid = _validate_key_input(options, validators)
        options_invalid.append(invalid)
        if invalid:
            logging.error('Invalid input for: ' + options)
            logging.error(invalid)
    if any(options_invalid):
        sys.exit(1)


def _get_fragment(name):
    """
    Return the fragment for the specified item.
    """
    if name == 'vcs-clustered-service':
        return 'CS'
    elif name == 'service':
        return 'APP'
    elif name == 'ha-service-config':
        return 'HSC'
    elif name == 'vip':
        return 'VIP'
    elif name == 'vcs_trigger':
        return 'TRIG'


def _generate_item_data(name, story, length, options, version, valid_rpm,
                        add_to_cleanup, overwrite_rpm):
    """
    Return the items with their corresponding properties and values.
    """
    # set the default options for the item types
    fragment = _get_fragment(name)

    items = []
    for cs_num in xrange(1, length + 1):
        item = {}
        # construct basic attributes
        item['options'] = {}
        item['id'] = '{0}_{1}_{2}'.format(fragment, story, cs_num)
        item['add_to_cleanup'] = add_to_cleanup

        if fragment == 'CS':
            item['vpath'] = '/services/' + item['id']
            item['options']['name'] = item['id']
            item['options']['active'] = '1'
            item['options']['standby'] = '0'
        elif fragment == 'APP':
            item['vpath'] = '/software/services/{0}'.format(item['id'])
            item['destination'] = \
                '/services/CS_{0}_1/applications/{1}'.format(story, item['id'])
            item[
                'package_id'] = 'EXTR-lsbwrapper-{0}-{1}'.format(story, cs_num)
            item['package_vpath'] = \
                '/software/items/{0}'.format(item['package_id'])
            item['package_destination'] = \
                '/software/services/{0}/packages/{1}'.format(
                item['id'], item['package_id'])
            item['parent'] = 'CS_{0}_1'.format(story)
            if valid_rpm == 1:
                item['options'][
                    'service_name'] = 'test-lsb-{0}-{1}'.format(story, cs_num)
            elif valid_rpm == 2:
                item['options'][
                    'service_name'] = 'test-lsb-ping-{0}-{1}'.format(
                        story, cs_num)
            elif valid_rpm == 3:
                item['options'][
                    'service_name'] = 'test-lsb-fail-{0}-{1}'.format(
                        story, cs_num)
                item['package_id'] = 'EXTR-lsbwrapper-fail-{0}-{1}'.format(
                    story, cs_num)
            elif valid_rpm == 4:
                item['options'][
                    'service_name'] = 'test-lsb-http-{0}-{1}'.format(
                        story, cs_num)
                item['package_id'] = 'EXTR-lsbwrapper-http-{0}-{1}'.format(
                    story, cs_num)
            elif valid_rpm == 5:
                item['options'][
                    'service_name'] = 'test-lsb-off-del-{0}-{1}'.format(
                        story, cs_num)
                item['package_id'] = 'EXTR-lsbwrapper-delay-{0}-{1}'.format(
                    story, cs_num)
            generate_rpm(story, cs_num, version, valid_rpm, overwrite_rpm)
        elif fragment == 'HSC':
            item['vpath'] = \
                '/services/CS_{0}_1/ha_configs/{1}'.format(story, item['id'])
            item['parent'] = 'CS_{0}_1'.format(story)
            if length > 1:
                item['options']['service_id'] = 'APP_{0}_{1}'.format(
                    story, cs_num)
        elif fragment == 'VIP':
            item['vpath'] = \
                '/services/CS_{0}_1/ipaddresses/ip_{1}'.format(story,
                                                               item['id'])
            if length > 1:
                item['options']['vip_id'] = '{0}'.format(item['id'])
        elif fragment == 'TRIG':
            item['vpath'] = \
                '/services/CS_{0}_1/triggers/{1}'\
                    .format(story, item['id'])
            if length > 1:
                item['vpath'] = \
                '/services/CS_{0}_{1}/triggers/{2}'\
                    .format(story, cs_num, item['id'])
            item['options']['trigger_type'] = 'nofailover'
        item['options'].update(_tokenize_params(options))
        item['options_string'] = _serialize_options(item['options'])
        items.append(item)
    return items


def _expand_dict(name, data, story, length, options, version, valid_rpm,
                add_to_cleanup, overwrite_rpm):
    """
    Expand the data dictionary with items generated from the provided options.
    """
    if length:
        data[name] = _generate_item_data(name, story, length, options,
                                         version, valid_rpm, add_to_cleanup,
                                         overwrite_rpm)


def generate_json(story, vcs_length=0, app_length=0, hsc_length=0,
                  vip_length=0, vcs_options='', app_options='', hsc_options='',
                  vip_options='', vcs_trigger=0, trigger_options='',
                  version='1.0', valid_rpm=1, add_to_cleanup=False,
                  to_file=True, overwrite_rpm=False):
    """
    Generate data dictionary for JSON output.
    """
    if app_length > 1 and app_length != hsc_length:
        sys.exit('Number of services and configs is not equal.')

    # make sure that the arguments for the options are ok, Note currently by
    # default only one trigger type is allowed with current behaviour from
    # Sprint 16.7
    _validate_input(vcs_options, app_options, hsc_options, vip_options,
                    trigger_options)

    # build a data dictionary for JSON
    data = {
        'options': {
            'story': story,
            'vcs_length': vcs_length,
            'app_length': app_length,
            'hsc_length': hsc_length,
            'vip_length': vip_length,
            'trigger_length': vcs_trigger
        },
        'litp_default_values': {
            'vcs-clustered-service': {
                'offline_timeout': '300',
                'online_timeout': '300',
            },
            'service': {
                'cleanup_command': '/bin/true',
            },
            'ha-service-config': {
                'clean_timeout': '60',
                'fault_on_monitor_timeouts': '4',
                'tolerance_limit': '0',
            },
            'vip': {
                'ipaddress': '172.17.100.83',
                'network_name': 'traffic1',
            },
            'vcs_trigger': {
                'trigger_type': 'nofailover'
            }
        },
    }
    props = (
        ('vcs-clustered-service', vcs_length, vcs_options),
        ('service', app_length, app_options),
        ('ha-service-config', hsc_length, hsc_options),
        ('vip', vip_length, vip_options),
        ('vcs_trigger', vcs_trigger, trigger_options)
    )
    for triple in props:
        # we can rely on the data dict being mutable here
        _expand_dict(triple[0], data, story, triple[1], triple[2],
                     version, valid_rpm, add_to_cleanup, overwrite_rpm)
    data['packages'] = [s['package_id'] + '-{0}-1.noarch.rpm'.format(version)
                        for s in data['service']]

    # write the JSON to a file
    if to_file:
        _write_json(story, data)
    else:
        return data


def _write_json(story, data):
    """
    Write the data dictionary to story number + data.json in the same folder.
    E.g. 9600data.json
    """
    if DEBUG:
        import pprint
        pprint.pprint(data)
    else:
        with codecs.open(story + 'data.json', 'w', 'utf-8') as json_file:
            try:
                data_string = json.dumps(data)
            except ValueError:
                logging.error('Invalid JSON.', exc_info=True)
                sys.exit(1)
            else:
                try:
                    json_file.write(data_string)
                except OSError:
                    logging.error('Error writing the data to file.',
                                  exc_info=True)
                    sys.exit(1)


def load_fixtures(story, prefix, nodes_urls, input_data=None):
    """
    Load the fixtures with the specified parameters from the running test case.
    The fixtures can be passed as an input_data dictionary or they will be
    loaded from a file on the drive.
    """
    fixtures = input_data
    if input_data is None:
        with open(story + 'data.json') as json_file:
            fixtures = json.loads(json_file.read())

    for vcs in fixtures['vcs-clustered-service']:
        number_of_nodes = int(vcs['options']['active']) + int(
            vcs['options']['standby'])
        if number_of_nodes > len(nodes_urls):
            sys.exit('Number of available nodes is less than specified in'
                     ' fixtures.')
        node_list = [node_url.split('/')[-1]
                     for node_url in nodes_urls[:number_of_nodes]]
        vcs['options'].update({
            'node_list': ','.join(node_list)
        })
        vcs['options_string'] = _serialize_options(vcs['options'])
        vcs['vpath'] = prefix + vcs['vpath']
    for service in fixtures['service']:
        service['destination'] = prefix + service['destination']
    for hsc in fixtures['ha-service-config']:
        hsc['vpath'] = prefix + hsc['vpath']
    for ip in fixtures.get('vip', []):
        ip['vpath'] = prefix + ip['vpath']
    if fixtures.has_key('vcs_trigger'):
        for triggers in fixtures['vcs_trigger']:
            triggers['vpath'] = prefix + triggers['vpath']
    return fixtures


def apply_options_changes(fixtures, item_type, index,
                          options, overwrite=False):
    """
    Accepts:
        fixtures (dict): it is mutated in place with new options
        item_type (str): a type that is changed in the fixtures. e.g. service
        index (int): a zero-based index of the item in the item_type list
        options (dict): an options dictionary of custom properties
        overwrite (boolean): if set to true, the options are overwritten
            instead of updated
    The function mutates the specified options in fixtures in place with the
    new values.
    """
    if overwrite:
        fixtures[item_type][index]['options'] = options
    else:
        fixtures[item_type][index]['options'].update(options)
    fixtures[item_type][index]['options_string'] = _serialize_options(
        fixtures[item_type][index]['options']
    )


def apply_item_changes(fixtures, item_type, index, properties):
    """
    Accepts:
        fixtures (dict): it is mutated in place with new options
        item_type (str): a type that is changed in the fixtures. e.g. service
        index (int): a zero-based index of the item in the item_type list
        properties (dict): a dictionary of custom properties
    The function mutates the specified items in fixtures in place with the new
    values.
    """
    fixtures[item_type][index].update(properties)


def validate_fixtures(fixtures):
    """
    Validates the fixtures against the specific schema. Otherwise raises a
    ValueError. jsonschema package is used for this.
    """
    jsonschema.validate(fixtures, FIXTURES_SCHEMA)

if __name__ == '__main__':
    if DEBUG:
        PARSER_OPTIONS = PARSER.parse_args(['--s', '9600',
                                            '--a', '1',
                                            '--vcs', '1',
                                            '--hsc', '1',
                                            '--vip', '1',
                                            '--vipo', '',
                                            '--vcso', 'offline_timeout="401"'
                                            ' online_'
                                            'timeout="401"', '--ao', 'service'
                                            '_name="'
                                            'something" stop_command="/bin/tru'
                                            'e" sta'
                                            'tus_command="/sbin/service test'
                                            '-lsb-9600'
                                            ' status" start_command="/sbin/ser'
                                            'vice t'
                                            'est-lsb-9600 start"',
                                            '--hsco',
                                            'clean_timeout="700"'])[0]
    else:
        PARSER_OPTIONS = PARSER.parse_args()[0]
    OPTS = vars(PARSER_OPTIONS)
    try:
        generate_json(story=str(OPTS['story']),
                      vcs_length=OPTS.get('vcs_length', 0),
                      app_length=OPTS.get('app_length', 0),
                      hsc_length=OPTS.get('hsc_length', 0),
                      vip_length=OPTS.get('vip_length', 0),
                      vcs_options=OPTS.get('vcs_options', ''),
                      app_options=OPTS.get('app_options', ''),
                      hsc_options=OPTS.get('hsc_options', ''),
                      vip_options=OPTS.get('vip_options', ''),
                      version=OPTS.get('version', '1.0'),
                      valid_rpm=OPTS.get('valid_rpm', 1),
                      add_to_cleanup=OPTS.get('add_to_cleanup', False))
    except KeyError:
        sys.exit('--s parameter is mandatory.')

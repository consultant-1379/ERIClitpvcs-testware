"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     September 2015
@author:    Zlatko Masek, Boyan Mihovski, Ciaran Reilly
@summary:   Integration tests test data generator for testing VCS scenarios
            Agile: LITPCDS-10172
"""
import glob
import optparse
import os
import shutil
import subprocess
import sys
import jinja2
import logging
import re

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

DEBUG = True

PARSER = optparse.OptionParser()
PARSER.add_option('--s', action='store', dest='story', type='int')
PARSER.add_option(
    '--c', action='store', dest='package_count', type='int', default=1)
PARSER.add_option('--p', action='store_true', dest='valid_rpm')
PARSER.add_option('--n', action='store_false', dest='invalid_rpm')
PARSER.add_option('--v', action='store', dest='version')

# In this case, we will load templates off the filesystem.
# This means we must construct a FileSystemLoader object.
#
# The search path can be used to make finding templates by
#   relative paths much easier.  In this case, we are using
#   absolute paths and thus set it to the filesystem root.

TEMPLATELOADER = None
if os.path.dirname(__file__) == '':
    TEMPLATELOADER = jinja2.FileSystemLoader(
        searchpath=os.path.dirname(
            os.path.abspath(__file__)
        ) + "/rpm-template"
    )
else:
    TEMPLATELOADER = jinja2.FileSystemLoader(
        searchpath=os.path.dirname(__file__) + "/rpm-template"
    )

# TEMPLATELOADER = jinja2.FileSystemLoader(
#    searchpath=os.path.dirname(__file__) + "/rpm-template")

# An environment provides the data necessary to read and
#   parse our templates.  We pass in the loader object here.
TEMPLATEENV = jinja2.Environment(loader=TEMPLATELOADER)

# This constant string specifies the template file we will use.
TEMPLATE_SETUP = "setup.jinja"
TEMPLATE_SCRIPT = "test-lsb-"
TEMPLATE_SCRIPT_PING = "test-lsb-ping-"
TEMPLATE_SCRIPT_FAULT = "test-lsb-fail-"
TEMPLATE_SCRIPT_FAULT_STABLE = "test-lsb-fail-fixed-"
TEMPLATE_SCRIP_HTTP = "test-lsb-http-"
TEMPLATE_SCRIP_DELAY = "test-lsb-off-del-"
TEMPLATE_SERVICE_UNIT = "test_service_unit.service"

# Read the template file using the environment object.
# This also constructs our Template object.
TEMPLATESETUP = TEMPLATEENV.get_template(TEMPLATE_SETUP)
TEMPLATESCRIPT = TEMPLATEENV.get_template(TEMPLATE_SCRIPT)
TEMPLATESERVICEUNIT = TEMPLATEENV.get_template(TEMPLATE_SERVICE_UNIT)
TEMPLATESCRIPTPING = TEMPLATEENV.get_template(TEMPLATE_SCRIPT_PING)
TEMPLATESCRIPTFAULT = TEMPLATEENV.get_template(TEMPLATE_SCRIPT_FAULT)
TEMPLATESCRIPHTTP = TEMPLATEENV.get_template(TEMPLATE_SCRIP_HTTP)
TEMPLATESCRIPTDELAY = TEMPLATEENV.get_template(TEMPLATE_SCRIP_DELAY)
TEMPLATESCRIPTFAULTFIXED = TEMPLATEENV.get_template(
    TEMPLATE_SCRIPT_FAULT_STABLE)

PACKAGE_NAME = 'EXTR-lsbwrapper-{0}-{1}'
PACKAGE_NAME_FAIL = 'EXTR-lsbwrapper-fail-{0}-{1}'
PACKAGE_NAME_HTTP = 'EXTR-lsbwrapper-http-{0}-{1}'
PACKAGE_NAME_DELAY = 'EXTR-lsbwrapper-delay-{0}-{1}'
SERVICE_UNIT = "test-lsb-{0}-{1}.service"


def _get_exec_path():
    """
    Function that returns the absolute path to the executable.
    """

    if os.path.dirname(__file__) == '':
        return os.path.dirname(os.path.abspath(__file__))
    else:
        return os.path.dirname(__file__)


def generate_rpm(story, number, version='1.0', valid_rpm=1,
                 overwrite_rpm=False):
    """
    Function to create a dummy rpm content files based on provided
        story and counter numbers.

    Args:
          story (str): Story number.

          number (int): Count on generated rpms.
          version (str): Version number of the RPM being generated

          valid_rpm (int): Determines the type of RPM for testing to be
          generated

          overwrite_rpm (bool): Determines whether a faulty/bad RPM will be
          overwritten with a more stable one
    """
    templatescript = None
    rpm_out = _get_exec_path() + '/rpm-out/'

    # Setup service_unit file
    template_vars = {'name': PACKAGE_NAME.format(story, number),
                     'version': version}

    if valid_rpm == 1:
        template_vars = {'name': PACKAGE_NAME.format(story, number),
                         'version': version}
        template_vars['script'] = 'test-lsb-{0}-{1}'.format(story, number)
        templatescript = TEMPLATESCRIPT
        template_vars['service_unit'] = SERVICE_UNIT.format(story, number)
    elif valid_rpm == 2:
        template_vars = {'name': PACKAGE_NAME.format(story, number),
                         'version': version}
        template_vars['script'] = 'test-lsb-ping-{0}-{1}'.format(story,
                                                                 number)
        templatescript = TEMPLATESCRIPTPING
        template_vars['service_unit'] = "test-lsb-ping-{0}-{1}.service".format(story, number)
    elif valid_rpm == 3:
        template_vars = {'name': PACKAGE_NAME_FAIL.format(story, number),
                         'version': version}
        template_vars['script'] = 'test-lsb-fail-{0}-{1}'.format(story,
                                                                 number)
        if overwrite_rpm:
            templatescript = TEMPLATESCRIPTFAULTFIXED
        else:
            templatescript = TEMPLATESCRIPTFAULT
        template_vars['service_unit'] = "test-lsb-fail-{0}-{1}.service".format(story, number)
    elif valid_rpm == 4:
        template_vars = {'name': PACKAGE_NAME_HTTP.format(story, number),
                         'version': version}
        template_vars['script'] = 'test-lsb-http-{0}-{1}'.format(story,
                                                                 number)
        templatescript = TEMPLATESCRIPHTTP
        template_vars['service_unit'] = "test-lsb-http-{0}-{1}.service".format(story, number)
    elif valid_rpm == 5:
        template_vars = {'name': PACKAGE_NAME_DELAY.format(story, number),
                         'version': version}
        template_vars['script'] = \
            'test-lsb-off-del-{0}-{1}'.format(story, number)
        templatescript = TEMPLATESCRIPTDELAY
        template_vars['service_unit'] = "test-lsb-off-del-{0}-{1}.service".format(story, number)

    templateservice = TEMPLATESERVICEUNIT
    with open(rpm_out + template_vars['service_unit'], 'w') as rpm_script:
        rpm_script.write(templateservice.render(template_vars))

    with open(rpm_out + "setup.py", 'w') as setup_file:
        setup_file.write(TEMPLATESETUP.render(template_vars))
    with open(rpm_out + template_vars['script'], 'w') as rpm_script:
        rpm_script.write(templatescript.render(template_vars))
    os.chdir(rpm_out)

    stat_rpm_script = os.stat(template_vars['script'])
    stat_rpm_service= os.stat(template_vars['service_unit'])
    os.chmod(template_vars['script'], stat_rpm_script.st_mode | 0111)
    os.chmod(template_vars['service_unit'], stat_rpm_service.st_mode | 0111)
    sub_proc_rpm = subprocess.Popen('python setup.py bdist_rpm --no-autoreq',
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    shell=True)
    out, err = sub_proc_rpm.communicate()
    rc, _, _ = sub_proc_rpm.returncode, out.strip(), err.strip()
    # if it exited successfuly
    if rc == 0:
        logging.debug(out)
        os.remove(template_vars['script'])
        os.remove(template_vars['service_unit'])
        os.remove('setup.py')
        os.remove('MANIFEST')
        shutil.rmtree('build')
        tars = glob.glob('dist/*.tar.gz')
        for tar in tars:
            os.remove(tar)
        srcs = glob.glob('dist/*.src.rpm')
        for src in srcs:
            os.remove(src)
        os.chdir('..')
    else:
        logging.error(err)


def generate_rpms(**kwargs):
    """
    Function to create a dummy rpms based on
        provided story and counter numbers.
    """

    def exec_generate(start, end, story, version, valid_rpm):
        """
        Internal function to call generate_rpm() function after the external
        function checks how many packages are required. Only used when the
        script is executed directly as a binary, not imported.
        """

        for number in xrange(start, end):
            generate_rpm(story, number, version, valid_rpm)

    story = str(kwargs['story'])
    package_count = kwargs.get('package_count')
    version = kwargs.get('version')
    valid_rpm = kwargs.get('valid_rpm')

    if valid_rpm == 1 or valid_rpm == 2:
        rpm_path = _get_exec_path() + '/rpm-out/dist/' + \
                   PACKAGE_NAME.format(story, '*')
    elif valid_rpm == 3:
        rpm_path = _get_exec_path() + '/rpm-out/dist/' + \
                   PACKAGE_NAME_FAIL.format(story, '*')
    elif valid_rpm == 4:
        rpm_path = _get_exec_path() + '/rpm-out/dist/' + \
                   PACKAGE_NAME_HTTP.format(story, '*')
    elif valid_rpm == 5:
        rpm_path = _get_exec_path() + '/rpm-out/dist/' + \
                   PACKAGE_NAME_DELAY.format(story, '*')
    existing_rpms = glob.glob(rpm_path)
    if existing_rpms:
        if package_count > len(existing_rpms):
            package_count = package_count - len(existing_rpms)
            exec_generate(
                len(existing_rpms) + 1, package_count + 1, story, version,
                valid_rpm
            )
        else:
            package_count = package_count + len(existing_rpms)
            exec_generate(
                len(existing_rpms) + 1, package_count + 1, story, version,
                valid_rpm
            )
            # Specify any input variables to the template as a dictionary.
    else:
        exec_generate(1, package_count + 1, story, version, valid_rpm)


if __name__ == '__main__':
    DEBUG = False
    if DEBUG:
        OPTIONS = PARSER.parse_args(['--s', '9600',
                                     '--c', '8',
                                     '--v', '1.0'
                                            '--p'])[0]
    else:
        # ./rpm_generator.py --s 9600 --c 1
        REGEX = re.compile(r'\d{1,2}\.\d{1,2}(\.\d{1,2})?$')
        OPTIONS = PARSER.parse_args()[0]
        if not OPTIONS.story:
            # package count is default 1 so never empty - no need to check
            raise Exception('Missing arguments')
        if OPTIONS.valid_rpm == None and OPTIONS.invalid_rpm == None:
            raise Exception('RPM must specify as negative || positive')
        if OPTIONS.valid_rpm != None and OPTIONS.invalid_rpm != None:
            raise Exception('RPM must specify as negative || positive')
        if OPTIONS.version != None:
            if not REGEX.match(OPTIONS.version):
                raise Exception('RPM version regex no match value')
        if OPTIONS.invalid_rpm != None:
            OPTIONS.valid_rpm = OPTIONS.invalid_rpm
            OPTIONS.invalid_rpm = None
    OPTS = vars(OPTIONS)
    generate_rpms(
        story=OPTS['story'], package_count=OPTS['package_count'],
        valid_rpm=OPTS['valid_rpm'], version=OPTS['version']
    )

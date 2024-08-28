"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     June 2015
@author:    Boyan Mihovski
@summary:   Integration
            Agile: STORY-9600
"""

import os
from litp_generic_test import GenericTest, attr
import test_constants
from vcs_utils import VCSUtils
from generate import load_fixtures, generate_json, apply_item_changes, \
    apply_options_changes
import re
from litp_cli_utils import CLIUtils

STORY = '9600'


class Story9600(GenericTest):
    """
    LITPCDS-9600:
    The following VCS Resource Attributes should be made tunable via the LITP
    model (all should be optional LITP properties):
        FaultOnMonitorTimeouts
        ToleranceLimit
        CleanTimeout
    I should be able to reconfigure each of the following VCS attributes via
    the LITP model:
        FaultOnMonitorTimeouts
        ToleranceLimit
        CleanTimeout
        OfflineTimeout
        OnlineTimeout
    I should be able to reconfigure the cleanup_command which will then modify
    the VCS Resource "Clean" attribute.
    If the optional properties are not specified then their respective default
    values should be used see property mapping below.
    A plan should not contain any node locking when updating any of
    these parameters.
    Generator command:
    python generate.py --s 9600 --a 2 --vcs 2 --hsc 2 \
    --vcso 'online_timeout="180"' \
    --hsco 'fault_on_monitor_timeouts="280" tolerance_limit="300"'
    """

    def setUp(self):
        """
        Description:
            Runs before every single test
        Actions:
            Determine
                management server,
                primary vcs node(first node in array
                                 returned from test framework)
                list of all managed nodes
        Results:
            Class variables that are required to execute tests
        """
        # 1. Call super class setup
        super(Story9600, self).setUp()
        # specify test data constants
        self.fault_on_mon = '600'
        self.tolerance_limit = '900'
        self.clean_timeout = '700'
        self.online_timeout = '600'
        self.offline_timeout = '900'
        self.cleanup_command = '/bin/touch /tmp/test-lsb.cleanup'
        self.management_server = self.get_management_node_filename()
        self.vcs = VCSUtils()
        self.cli = CLIUtils()

        # Location where RPMs to be used are stored
        self.rpm_src_dir = (os.path.dirname(
            os.path.realpath(__file__)) + '/rpm-out/dist/')

        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.management_server,
                                         '/deployments', 'vcs-cluster')[-1]
        self.cluster_id = self.vcs_cluster_url.split('/')[-1]

        nodes_urls = self.find(self.management_server,
                               self.vcs_cluster_url,
                               'node')

        _json = generate_json(to_file=False, story=STORY,
                              vcs_length=2,
                              app_length=2,
                              hsc_length=2,
                              vcs_options='online_timeout="180"',
                              hsc_options='fault_on_monitor_timeouts="280"'
                              'tolerance_limit="300"',
                              add_to_cleanup=False)
        self.fixtures = load_fixtures(
            STORY, self.vcs_cluster_url, nodes_urls, input_data=_json)
        apply_item_changes(self.fixtures, 'service', 1,
                           {'parent': "CS_9600_2",
                            'destination': self.vcs_cluster_url +
                            '/services/CS_9600_2/applications/APP_9600_2'})
        apply_item_changes(self.fixtures, 'ha-service-config', 1,
                           {'parent': "CS_9600_2"})
        apply_options_changes(
            self.fixtures, 'ha-service-config', 1, {
                'clean_timeout': '700', 'service_id': 'APP_9600_2'},
            overwrite=True)
        apply_item_changes(self.fixtures, 'ha-service-config', 1,
                           {'vpath': self.vcs_cluster_url +
                            '/services/CS_9600_2/ha_configs/HSC_9600_2'})
        apply_options_changes(
            self.fixtures,
            'vcs-clustered-service', 1, {'active': '1', 'standby': '0',
                                         'offline_timeout': '401',
                                         'name': 'CS_9600_2',
                                         'node_list': 'n1'},
            overwrite=True)

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story9600, self).tearDown()

    @attr('all', 'revert', 'story9600',
          'story9600_tc01', 'cdb_priority1')
    def test_01_p_cs_deploy_and_set_props(self):
        """
        @tms_id: litpcds_9600_tc01
        @tms_requirements_id: LITPCDS-9600
        @tms_title: cluster service deploy and set props
        @tms_description: To ensure that it is possible to specify, and deploy,
        a vcs-clustered-service with present "tolerance_limit" and
        "fault_on_monitor_timeouts" properties in "ha-service-config".
        @tms_test_steps:
        @step: Create 2 vcs-clustered-service
        @result: 2 vcs-clustered-service items created
        @step: Create 2 service items
        @result: service items created
        @step: Create 2 package items
        @result: package items created
        @step: inherit packages and services onto cluster
        @result: items inherited
        @step: Create ha-service-config item with fault_on_monitor_timeouts
        and tolerance_limit props set
        @result: item created
        @step: Create ha-service-config item with clean_timeout prop set
        @result: item created
        @step: Create and run plan
        @result: Plan executes successfully
        @result: applied properties from VCS app are correct
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # Steps 1, 2, 3
        # take node data from the model
        node_url = self.find(self.management_server, '/deployments', 'node')
        # Target node with installed vcs.
        node_to_exe = self.get_node_filename_from_url(self.management_server,
                                                      node_url[0])
        app_name = self.fixtures['service'][0]['id']
        # set cs conf dep path
        cs_url = self.get_cs_conf_url(self.management_server,
                                      self.fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.apply_cs_and_apps_sg(
                self.management_server, self.fixtures, self.rpm_src_dir)
            # This section of the test sets up the model and creates the plan
            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE, 5)
        # Step 4
        # checking test data agains vcs app configuration
        resource_id = \
            self.vcs.generate_application_resource_name(self.fixtures
                                                        ['service'][0]
                                                        ['parent'],
                                                        self.cluster_id,
                                                        app_name)
        fault_on_mon_timeouts_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'FaultOnMonitorTimeouts')

        # checking fault_on_monitor_timeouts value vcs app
        stdout, _, _ = \
            self.run_command(node_to_exe, fault_on_mon_timeouts_res_cmd,
                             su_root=True, default_asserts=True)
        self.assertEqual(self.fixtures['ha-service-config']
                         [0]['options']['fault_on_monitor_timeouts'],
                         stdout[0])
        # checking tolerance_limit value vcs app
        tolerance_limit_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'ToleranceLimit')
        stdout, _, _ = self.run_command(node_to_exe, tolerance_limit_res_cmd,
                                        su_root=True, default_asserts=True)
        self.assertEqual(self.fixtures['ha-service-config']
                         [0]['options']['tolerance_limit'],
                         stdout[0])
        # checking clean_timeout value vcs app
        clean_timeout_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'CleanTimeout')
        stdout, _, _ = self.run_command(node_to_exe, clean_timeout_res_cmd,
                                        su_root=True, default_asserts=True)
        self.assertEqual(self.fixtures['litp_default_values']
                         ['ha-service-config']['clean_timeout'], stdout[0])

    @attr('all', 'non-revert', 'story9600', 'story9600_tc02')
    def test_02_p_cs_update_create_props(self):
        """
        @tms_id: litpcds_9600_tc02
        @tms_requirements_id: LITPCDS-9600
        @tms_title: update ha-service-config item properties
        @tms_description:
        To ensure that it is possible to update previously applied
        "tolerance_limit", "fault_on_monitor_timeouts" and "clean_timeout"
        properties in "ha-service-config" in previously created
        vcs-clustered-service.
        @tms_test_steps:
        @step: update ha-service-config item with tolerance_limit
        fault_on_monitor_timeouts properties and create
        clean_timeout" property
        @result: item updated
        @step: Create and run plan
        @result: Plan executes successfully
        @result: applied properties from VCS app are correct
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # set local test data
        ha_conf_props = 'fault_on_monitor_timeouts={0} tolerance_limit={1} ' \
            'clean_timeout={2}'. \
            format(self.fault_on_mon, self.tolerance_limit, self.clean_timeout)
        # set cs conf dep path
        cs_url = self.get_cs_conf_url(self.management_server,
                                      self.fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.apply_cs_and_apps_sg(
                self.management_server, self.fixtures, self.rpm_src_dir)
            # This section of the test sets up the model and creates the plan
            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE, 5)
            cs_url = self.get_cs_conf_url(self.management_server,
                                          self.fixtures['service']
                                          [0]['parent'],
                                          self.vcs_cluster_url)
        # Steps 1, 2, 3
        # update ha values
        ha_conf_url = self.find(self.management_server, cs_url,
                                'ha-service-config')[0]
        self.execute_cli_update_cmd(self.management_server,
                                    ha_conf_url, ha_conf_props)
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 5)
        # Step 4
        # Show_plan output
        plan_stdout, _, _ = \
            self.execute_cli_showplan_cmd(self.management_server)
        parsed_plan = self.cli.parse_plan_output(plan_stdout)

        # Check if parased plan contains a lock node
        listtocheck = []
        for _, plan_value in parsed_plan.items():
            for _, desc_value in plan_value.items():
                listtocheck.append(desc_value['DESC'][-1])
        listtocompare = (', '.join(listtocheck))

        self.assertFalse(re.search('Lock VCS on node',
                                   listtocompare),
                         'Plan contains a nodelock, it should not')
        # Step 5
        # take node data from the model
        node_url = self.find(self.management_server, '/deployments', 'node')
        # Target node with installed vcs.
        node_to_exe = self.get_node_filename_from_url(self.management_server,
                                                      node_url[0])
        app_name = self.fixtures['service'][0]['id']
        # checking test data agains vcs app configuration
        resource_id = \
            self.vcs.generate_application_resource_name(self.fixtures
                                                        ['service']
                                                        [0]['parent'],
                                                        self.cluster_id,
                                                        app_name)
        fault_on_mon_timeouts_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'FaultOnMonitorTimeouts')

        # checking fault_on_monitor_timeouts value vcs app
        stdout, _, _ = \
            self.run_command(node_to_exe, fault_on_mon_timeouts_res_cmd,
                             su_root=True, default_asserts=True)
        self.assertEqual(self.fault_on_mon, stdout[0])
        # checking tolerance_limit value vcs app
        tolerance_limit_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'ToleranceLimit')
        stdout, _, _ = \
            self.run_command(node_to_exe, tolerance_limit_res_cmd,
                             su_root=True, default_asserts=True)
        self.assertEqual(self.tolerance_limit, stdout[0])
        # checking clean_timeout value vcs app
        clean_timeout_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'CleanTimeout')
        stdout, _, _ = self.run_command(node_to_exe, clean_timeout_res_cmd,
                                        su_root=True, default_asserts=True)
        self.assertEqual(self.clean_timeout, stdout[0])

    @attr('all', 'non-revert', 'story9600', 'story9600_tc03')
    def test_03_p_cs_rm_toler_limit_fault_on_mon_clean_timeout(self):
        """
        @tms_id: litpcds_9600_tc03
        @tms_requirements_id: LITPCDS-9600
        @tms_title: delete ha-service-config item properties
        @tms_description:
        To ensure that it is deleting already applied properties
        "tolerance_limit" and "fault_on_monitor_timeouts" using
        the litp update command.
        @tms_test_steps:
        @step: delete ha-service-config item properties: tolerance_limit
        fault_on_monitor_timeouts and clean_timeout
        @result: item updated
        @step: Create and run plan
        @result: plan does not contain a node lock task
        @result: Plan executes successfully
        @result: applied properties from VCS app are correct
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # set local test data
        ha_conf_props = 'fault_on_monitor_timeouts ' \
            'tolerance_limit clean_timeout'
        # set cs conf dep path
        cs_url = self.get_cs_conf_url(self.management_server,
                                      self.fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.apply_cs_and_apps_sg(
                self.management_server, self.fixtures, self.rpm_src_dir)
            # This section of the test sets up the model and creates the plan
            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE, 5)
            cs_url = self.get_cs_conf_url(self.management_server,
                                          self.fixtures['service']
                                          [0]['parent'],
                                          self.vcs_cluster_url)
        # Steps 1, 2, 3
        # Update the model
        ha_conf_url = self.find(self.management_server, cs_url,
                                'ha-service-config')[0]
        self.execute_cli_update_cmd(self.management_server,
                                    ha_conf_url, ha_conf_props,
                                    action_del=True)
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 5)
        # Step 4
        # Show_plan output
        plan_stdout, _, _ = \
            self.execute_cli_showplan_cmd(self.management_server)
        parsed_plan = self.cli.parse_plan_output(plan_stdout)

        # Check if parased plan contains a lock node
        listtocheck = []
        for _, plan_value in parsed_plan.items():
            for _, desc_value in plan_value.items():
                listtocheck.append(desc_value['DESC'][-1])
        listtocompare = (', '.join(listtocheck))

        self.assertFalse(re.search('Lock VCS on node',
                                   listtocompare),
                         'Plan contains a nodelock, it should not')
        # Step 5
        # take node data from the model
        node_url = self.find(self.management_server, '/deployments', 'node')
        # Target node with installed vcs.
        node_to_exe = self.get_node_filename_from_url(self.management_server,
                                                      node_url[0])
        app_name = self.fixtures['service'][0]['id']
        # checking test data agains vcs app configuration
        resource_id = \
            self.vcs.generate_application_resource_name(self.fixtures
                                                        ['service']
                                                        [0]['parent'],
                                                        self.cluster_id,
                                                        app_name)
        fault_on_mon_timeours_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'FaultOnMonitorTimeouts')

        # checking fault_on_monitor_timeouts value vcs app
        stdout, _, _ = \
            self.run_command(node_to_exe, fault_on_mon_timeours_res_cmd,
                             su_root=True, default_asserts=True)
        self.assertEqual(self.fixtures['litp_default_values']
                         ['ha-service-config']['fault_on_monitor_timeouts'],
                         stdout[0])
        # checking tolerance_limit value vcs app
        tolerance_limit_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'ToleranceLimit')
        stdout, _, _ = self.run_command(node_to_exe, tolerance_limit_res_cmd,
                                        su_root=True, default_asserts=True)
        self.assertEqual(self.fixtures['litp_default_values']
                         ['ha-service-config']['tolerance_limit'],
                         stdout[0])
        # checking clean_timeout value vcs app
        clean_timeout_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'CleanTimeout')
        stdout, _, _ = self.run_command(node_to_exe, clean_timeout_res_cmd,
                                        su_root=True, default_asserts=True)
        self.assertEqual(self.fixtures['litp_default_values']
                         ['ha-service-config']['clean_timeout'],
                         stdout[0])

    @attr('all', 'non-revert', 'story9600', 'story9600_tc04')
    def test_04_p_cs_deploy_default_values(self):
        """
        @tms_id: litpcds_9600_tc04
        @tms_requirements_id: LITPCDS-9600
        @tms_title: cluster service default values
        @tms_description:
        To ensure that it is possible to specify, and deploy,
        a vcs-clustered-service without present "tolerance_limit" and
        "fault_on_monitor_timeouts" properties in "ha-service-config".
        @tms_test_steps:
        @step: execute "hares -value" with FaultOnMonitorTimeouts
        @result: command executes successfully
        @step: execute "hares -value" with ToleranceLimit
        @result: command executes successfully
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # Steps 1, 2, 3
        # take node data from the model
        node_url = self.find(self.management_server, '/deployments', 'node')
        # Test one when offline timeout is default
        node_to_exe = self.get_node_filename_from_url(self.management_server,
                                                      node_url[0])
        app_name = self.fixtures['service'][1]['id']
        # set cs conf dep path
        cs_url = self.get_cs_conf_url(self.management_server,
                                      self.fixtures['service'][1]['parent'],
                                      self.vcs_cluster_url)
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.apply_cs_and_apps_sg(
                self.management_server, self.fixtures, self.rpm_src_dir)
            # This section of the test sets up the model and creates the plan
            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE, 5)
        # Step 4
        # checking test data agains vcs app configuration
        resource_id = \
            self.vcs.generate_application_resource_name(self.fixtures
                                                        ['service']
                                                        [1]['parent'],
                                                        self.cluster_id,
                                                        app_name)
        fault_on_mon_timeours_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'FaultOnMonitorTimeouts')

        # checking fault_on_monitor_timeouts value vcs app
        stdout, _, _ = \
            self.run_command(node_to_exe, fault_on_mon_timeours_res_cmd,
                             su_root=True, default_asserts=True)
        self.assertEqual(self.fixtures['litp_default_values']
                         ['ha-service-config']['fault_on_monitor_timeouts'],
                         stdout[0])
        # checking tolerance_limit value vcs app
        tolerance_limit_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'ToleranceLimit')
        stdout, _, _ = self.run_command(node_to_exe, tolerance_limit_res_cmd,
                                        su_root=True, default_asserts=True)
        self.assertEqual(self.fixtures['litp_default_values']
                         ['ha-service-config']['tolerance_limit'],
                         stdout[0])

    @attr('all', 'non-revert', 'story9600', 'story9600_tc07')
    def test_07_p_cs_update_online_offline_timeout(self):
        """
        @tms_id: litpcds_9600_tc07
        @tms_requirements_id: LITPCDS-9600
        @tms_title: update online and offline timeout properties of
        vcs-clustered-service
        @tms_description:
        o ensure that it is possible to update previously applied
        "online_timeout" and "offline_timeout", in previously created
        vcs-clustered-service.
        @tms_test_steps:
        @step: update vcs-clustered-service item with offline_timeout and
        online_timeout properties
        @result: item updated
        @step: create and run plan
        @result: no lock task for node in plan
        @result: plan executes successfully
        @result: applied properties from VCS app are correct
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # set cs conf dep path
        cs_url = self.get_cs_conf_url(self.management_server,
                                      self.fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.apply_cs_and_apps_sg(
                self.management_server, self.fixtures, self.rpm_src_dir)
            # This section of the test sets up the model and creates the plan
            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE, 5)
        # Steps 1, 2, 3
        # set local test data
        vcs_conf_props = 'online_timeout={0} offline_timeout={1} '. \
            format(self.online_timeout, self.offline_timeout)
        # Update with the values
        self.execute_cli_update_cmd(self.management_server,
                                    cs_url, vcs_conf_props)
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 5)
        # Step 4
        # Show_plan output
        plan_stdout, _, _ = \
            self.execute_cli_showplan_cmd(self.management_server)
        parsed_plan = self.cli.parse_plan_output(plan_stdout)

        # Check if parased plan contains a lock node
        listtocheck = []
        for _, plan_value in parsed_plan.items():
            for _, desc_value in plan_value.items():
                listtocheck.append(desc_value['DESC'][-1])
        listtocompare = (', '.join(listtocheck))

        self.assertFalse(re.search('Lock VCS on node',
                                   listtocompare),
                         'Plan contains a nodelock, it should not')
        # Step 5
        # take node data from the model
        node_url = self.find(self.management_server, '/deployments', 'node')
        # Get online timeout, offline timeout values from the model
        node_to_exe = self.get_node_filename_from_url(self.management_server,
                                                      node_url[0])
        app_name = self.fixtures['service'][0]['id']
        # checking test data agains vcs app configuration
        resource_id = \
            self.vcs.generate_application_resource_name(self.fixtures
                                                        ['service']
                                                        [0]['parent'],
                                                        self.cluster_id,
                                                        app_name)
        online_timeout_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'OnlineTimeout')

        # checkinging online timeout value vcs app
        stdout, _, _ = self.run_command(node_to_exe, online_timeout_res_cmd,
                                        su_root=True, default_asserts=True)
        self.assertEqual(self.online_timeout, stdout[0])
        # checkinging offline timeout value vcs app
        offline_timeout_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'OfflineTimeout')
        stdout, _, _ = self.run_command(node_to_exe, offline_timeout_res_cmd,
                                        su_root=True, default_asserts=True)
        self.assertEqual(self.offline_timeout, stdout[0])

    @attr('all', 'non-revert', 'story9600', 'story9600_tc08')
    def test_08_p_cs_remove_online_offline_timeout(self):
        """
        @tms_id: litpcds_9600_tc08
        @tms_requirements_id: LITPCDS-9600
        @tms_title: remove online and offline timeout properties of
        vcs-clustered-service
        @tms_description:
        o ensure that it is possible to update previously applied
        "online_timeout" and "offline_timeout", in previously created
        vcs-clustered-service.
        @tms_test_steps:
        @step: remove vcs-clustered-service item with offline_timeout and
        online_timeout properties
        @result: item updated
        @step: create and run plan
        @result: plan executes successfully
        @result: applied properties from VCS app are correct and default to 300
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # set cs conf dep path
        cs_url = self.get_cs_conf_url(self.management_server,
                                      self.fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.apply_cs_and_apps_sg(
                self.management_server, self.fixtures, self.rpm_src_dir)
            # This section of the test sets up the model and creates the plan
            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE, 5)
        # Steps 1, 2, 3
        # set local test data
        vcs_conf_props = 'online_timeout offline_timeout'
        # Update with the values
        self.execute_cli_update_cmd(self.management_server,
                                    cs_url, vcs_conf_props,
                                    action_del=True)
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 5)

        # Step 4
        # take node data from the model
        node_url = self.find(self.management_server, '/deployments', 'node')
        # Get online timeout, offline timeout values from the model
        node_to_exe = self.get_node_filename_from_url(self.management_server,
                                                      node_url[0])
        app_name = self.fixtures['service'][0]['id']
        # checking test data agains vcs app configuration
        resource_id = \
            self.vcs.generate_application_resource_name(self.fixtures
                                                        ['service']
                                                        [0]['parent'],
                                                        self.cluster_id,
                                                        app_name)
        online_timeout_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'OnlineTimeout')

        # checking online_timeout value vcs app
        stdout, _, _ = self.run_command(node_to_exe, online_timeout_res_cmd,
                                        su_root=True, default_asserts=True)
        self.assertEqual(self.fixtures['litp_default_values']
                         ['vcs-clustered-service']
                         ['online_timeout'], stdout[0])
        # checking offline_timeout value vcs app
        offline_timeout_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'OfflineTimeout')
        stdout, _, _ = self.run_command(node_to_exe, offline_timeout_res_cmd,
                                        su_root=True, default_asserts=True)
        self.assertEqual(self.fixtures['litp_default_values']
                         ['vcs-clustered-service']
                         ['offline_timeout'], stdout[0])

    @attr('all', 'non-revert', 'story9600', 'story9600_tc09')
    def test_09_p_cs_update_cleanup_command_service(self):
        """
        @tms_id: litpcds_9600_tc09
        @tms_requirements_id: LITPCDS-9600
        @tms_title: update cleanup_command property of service item
        @tms_description:
        To ensure that it is possible to update previously applied
        "cleanup_command", in previously created "vcs-clustered-service" and
        "vm_service" type item.
        @tms_test_steps:
        @step: update service item cleanup_command property
        @result: item updated
        @step: create and run plan
        @result: no lock task for node
        @result: plan executes successfully
        @result: applied properties from VCS app are correct and default to 300
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # Execute initial plan creation if test data if is not applied already
        cs_url = self.get_cs_conf_url(self.management_server,
                                      self.fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.apply_cs_and_apps_sg(
                self.management_server, self.fixtures, self.rpm_src_dir)
            # This section of the test sets up the model and creates the plan
            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE, 5)
        # Steps 1, 2, 3
        # set local test data
        app_conf_url = '{0}{1}'.format('/software/services/',
                                       self.fixtures['service'][0]['id'])
        app_conf_props = 'cleanup_command="{0}"'. \
            format(self.cleanup_command)
        self.execute_cli_update_cmd(self.management_server,
                                    app_conf_url, app_conf_props)
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 5)
        # Step 4
        # Show_plan output
        plan_stdout, _, _ = \
            self.execute_cli_showplan_cmd(self.management_server)
        parsed_plan = self.cli.parse_plan_output(plan_stdout)

        # Check if parased plan contains a lock node
        listtocheck = []
        for _, plan_value in parsed_plan.items():
            for _, desc_value in plan_value.items():
                listtocheck.append(desc_value['DESC'][-1])
        listtocompare = (', '.join(listtocheck))

        self.assertFalse(re.search('Lock VCS on node',
                                   listtocompare),
                         'Plan contains a nodelock, it should not')
        # Step 5
        # take node data from the model
        node_url = self.find(self.management_server, '/deployments', 'node')
        # Target node with installed vcs.
        node_to_exe = self.get_node_filename_from_url(self.management_server,
                                                      node_url[0])
        app_name = self.fixtures['service'][0]['id']
        # checking test data agains vcs app configuration
        resource_id = \
            self.vcs.generate_application_resource_name(self.fixtures
                                                        ['service']
                                                        [0]['parent'],
                                                        self.cluster_id,
                                                        app_name)
        cleanup_cmd_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'CleanProgram')
        # checking cleanup command value vcs app
        stdout, _, _ = self.run_command(node_to_exe, cleanup_cmd_res_cmd,
                                        su_root=True, default_asserts=True)
        self.assertEqual(self.cleanup_command, stdout[0])

    @attr('all', 'non-revert', 'story9600', 'story9600_tc10')
    def test_10_p_cs_remove_cleanup_command_service(self):
        """
        @tms_id: litpcds_9600_tc10
        @tms_requirements_id: LITPCDS-9600
        @tms_title: remove cleanup_command property of service item
        @tms_description:
         To ensure that it is possible to remove previously applied
        "cleanup_command", in previously created "vcs-clustered-service"
        and "service" type item when the services are two and second has
        default value for "cleanup_command".
        @tms_test_steps:
        @step: remove service item cleanup_command property
        @result: item updated
        @step: create and run plan
        @result: plan executes successfully
        @result: applied properties from VCS app are correct and default to 300
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # Execute initial plan creation if test data if is not applied already
        cs_url = self.get_cs_conf_url(self.management_server,
                                      self.fixtures['service'][1]['parent'],
                                      self.vcs_cluster_url)
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.apply_cs_and_apps_sg(
                self.management_server, self.fixtures, self.rpm_src_dir)
            # This section of the test sets up the model and creates the plan
            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE, 5)
        # Steps 1, 2, 3
        # set local test data
        app_def_conf_url = '{0}{1}'.format('/software/services/',
                                           self.fixtures['service'][1]['id'])
        app_conf_url = '{0}{1}'.format('/software/services/',
                                       self.fixtures['service'][0]['id'])
        app_conf_props = 'cleanup_command'
        self.execute_cli_update_cmd(self.management_server, app_def_conf_url,
                                    app_conf_props, action_del=True)
        self.execute_cli_update_cmd(self.management_server, app_conf_url,
                                    app_conf_props, action_del=True)
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 5)
        # Step 4
        # take node data from the model
        node_url = self.find(self.management_server, '/deployments', 'node')
        # Target node with installed vcs.
        node_to_exe = self.get_node_filename_from_url(self.management_server,
                                                      node_url[1])
        app_name = self.fixtures['service'][0]['id']
        app_name_def = self.fixtures['service'][1]['id']
        # checking test data agains vcs app configuration
        resource_id = \
            self.vcs.generate_application_resource_name(self.fixtures
                                                        ['service']
                                                        [0]['parent'],
                                                        self.cluster_id,
                                                        app_name)
        resource_id_def = \
            self.vcs.generate_application_resource_name(self.fixtures
                                                        ['service']
                                                        [1]['parent'],
                                                        self.cluster_id,
                                                        app_name_def)
        vcs_cleanup_cmd_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'CleanProgram')
        # checking cleanup command value vcs app
        stdout, _, _ = self.run_command(node_to_exe, vcs_cleanup_cmd_res_cmd,
                                        su_root=True, default_asserts=True)
        self.assertEqual(self.fixtures['litp_default_values']
                         ['service']['cleanup_command'], stdout[0])
        vcs_cleanup_cmd_res_cmd_def = self.vcs.get_hares_resource_attr(
            resource_id_def, 'CleanProgram')
        # checking cleanup command default value vcs app
        stdout, _, _ = \
            self.run_command(node_to_exe, vcs_cleanup_cmd_res_cmd_def,
                             su_root=True, default_asserts=True)
        self.assertEqual(self.fixtures['litp_default_values']
                         ['service']['cleanup_command'], stdout[0])

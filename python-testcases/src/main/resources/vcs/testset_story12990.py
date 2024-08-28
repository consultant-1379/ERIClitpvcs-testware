"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     Feb 2016
@author:    Ciaran Reilly
@summary:   Integration Tests
            Agile: Blocker Bug Validation-12990
"""

import os
from litp_generic_test import GenericTest, attr
from vcs_utils import VCSUtils
from generate import load_fixtures, generate_json, apply_options_changes
from test_constants import PLAN_TASKS_RUNNING, PLAN_STOPPED

STORY = '12990'


class Blocker12990(GenericTest):
    """
    Blocker-12990:
    Stop_plan leaves is_locked property of node in incorrect state

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
        super(Blocker12990, self).setUp()
        self.management_server = self.get_management_node_filename()
        self.vcs = VCSUtils()
        # Location where RPMs to be used are stored
        self.rpm_src_dir = (os.path.dirname(
            os.path.realpath(__file__)) + '/rpm-out/dist/')

        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.management_server,
                                         '/deployments', 'vcs-cluster')[-1]
        self.cluster_id = self.vcs_cluster_url.split('/')[-1]

        self.nodes_urls = self.find(self.management_server,
                                    self.vcs_cluster_url,
                                    'node')

        self.node_ids = [node.split('/')[-1] for node in self.nodes_urls]

        self.node_1 = self.get_node_filename_from_url(self.management_server,
                                                      self.nodes_urls[0])

        _json = generate_json(to_file=False, story=STORY,
                              vcs_length=1,
                              app_length=1,
                              hsc_length=1,
                              add_to_cleanup=True)

        self.fixtures = load_fixtures(
            STORY, self.vcs_cluster_url, self.nodes_urls, input_data=_json)

        apply_options_changes(
            self.fixtures,
            'vcs-clustered-service', 0, {'active': '1', 'standby': '1',
                                         'name': 'CS_12990_1',
                                         'node_list': '{0}'.format
                                         (','.join(self.node_ids)),
                                         'online_timeout': '600'},
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
        super(Blocker12990, self).tearDown()

    @attr('all', 'revert', 'Blocker12990', 'Blocker12990_tc01')
    def test_01_check_is_locked_property(self):
        """
        @tms_id: litpcds_12990_tc01
        @tms_requirements_id: LITPCDS-3993
        @tms_title: Check node locking
        @tms_description: Test to validate that the 'is_locked'
        property is set to True after a plan stops
        @tms_test_steps:
          @step:  Create CS if not already created
          @result: model updated as expected
          @step: Wait for node 1 locking task to run
          @result: plan reaches locking task
          @step: run stop_plan command
          @result: plan goes to stopped state
          @step: check is_locked property on node1
          @result: is_locked property is set to true
        @tms_test_precondition: None
        @tms_execution_type: Automated
        """
        node_url = '/deployments/d1/clusters/c1/nodes/n1'
        task_desc = 'Lock VCS on node "node1"'
        cs_url = self.get_cs_conf_url(self.management_server,
                                      self.fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)
        # STEP 1
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.apply_cs_and_apps_sg(
                self.management_server, self.fixtures, self.rpm_src_dir)
            # This section of the test sets up the model and creates the plan

            self.execute_cli_createplan_cmd(self.management_server)
            self.execute_cli_runplan_cmd(self.management_server)

            # STEP 2
            self.assertTrue(self.wait_for_task_state(self.management_server,
                                                     task_desc,
                                                     PLAN_TASKS_RUNNING,
                                                     False),
                            'node 1 is locking')
            # STEP 3
            self.execute_cli_stopplan_cmd(self.management_server)

            # STEP 4
            self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                     PLAN_STOPPED))

            # STEP 5
            vpath = self.find(self.management_server, '/deployments', 'node')

            self.assertEqual(vpath[0], node_url)

            node_prop = self.get_props_from_url(self.management_server,
                                                vpath[0],
                                                filter_prop='is_locked')

            self.assertEqual(node_prop, 'true')

            self.execute_cli_removeplan_cmd(self.management_server)

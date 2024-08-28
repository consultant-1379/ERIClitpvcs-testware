"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     May 2017
@author:    Alex Kabargin
@summary:   Integration Tests
            Task TORF-186598
"""

import os
from litp_generic_test import GenericTest, attr
from vcs_utils import VCSUtils
from generate import load_fixtures, generate_json, apply_options_changes
from test_constants import PLAN_COMPLETE


STORY = '186598'
ONLINE_STATE = '|ONLINE|'


class Story186598(GenericTest):
    """
    TORF-186598:
    Check that PL Service group comes back online after node reboot
    Following fix for TORF-177064

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
        super(Story186598, self).setUp()
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
        self.node_exe = []
        for node in self.nodes_urls:
            self.node_exe.append(
                self.get_node_filename_from_url(self.management_server, node))

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story186598, self).tearDown()

    def baseline(self, vcs_len, app_len, hsc_len, vips_len=0, cleanup=False,
                 vcs_trig=0, valid_rpm=1, story=STORY):
        """
        Description:
            Runs if no suitable CS group is found with every test case to set
            up litp model with vcs/app and ha service parameters
        Parameters:
            vcs_len: (int) Number of VCS CS
            app_len: (int) Number of applications
            hsc_len: (int) Number of HA Service Configs
            vips_len: (int) Number of VIPs required
            valid_rpm: (int) Number relates to Stable/ Unstable version of RPM
            vcs_trig: (int) Number of vcs-triggers to generate
            cleanup: (bool) Remove the service during the cleanup tasks
        Actions:
            Declares fixtures dictionary for litp model generation
        Returns:
            fixtures dictionary
        """

        _json = generate_json(to_file=False, story=story,
                              vcs_length=vcs_len,
                              app_length=app_len,
                              hsc_length=hsc_len,
                              vip_length=vips_len,
                              vcs_trigger=vcs_trig,
                              valid_rpm=valid_rpm,
                              add_to_cleanup=cleanup)

        return load_fixtures(story, self.vcs_cluster_url,
                             self.nodes_urls, input_data=_json)

    def create_service(self, fixtures, active, standby, nodes):
        """
        Method to create a clustered service

        :param fixtures: fixtures dictionary
        :param active: (int) Number of active nodes
        :param standby: (int) Number of standby nodes
        :param nodes: (str) Nodes on which run the clustered service
        """
        cs_1_name = fixtures['service'][0]['parent']
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '{0}'.format(active), 'standby': '{0}'.format(standby),
             'name': '{0}'.format(cs_1_name), 'node_list': '{0}'.
             format(nodes)}, overwrite=True)

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

    @attr('all', 'story186598', 'story186598_tc01', 'non-revert', 'kgb-other')
    def test_01_p_check_cs_after_reboot(self):
        """
        @tms_id: torf_186598_tc01
        @tms_requirements_id: LITPCDS-9490
        @tms_title: Check the parallel service after reboot
        @tms_description: Test to validate that the parallel service group
        comes back online after node reboot
        NOTE: This verifies task TORF-186598
        @tms_test_steps:
          @step:  Create parallel CS on 2 nodes
          @result: model updated as expected
          @step: Reboot one of the nodes (node1)
          @result: Node is rebooted
          @step: Check the service group is back online
          @result: PL SG is back online
        @tms_test_precondition: None
        @tms_execution_type: Automated
        """
        timeout_mins = 90
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1,
                                 story=STORY, cleanup=True)
        self.create_service(fixtures, 2, 0, 'n1,n2')
        cs_1_name = fixtures['service'][0]['parent']

        # STEP 1
        # Execute initial plan creation
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))
        self.wait_for_vcs_service_group_online(self.node_exe[0], cs_1_name, 2)

        # STEP 2
        # Reboot the node1
        self.poweroff_peer_node(self.management_server,
                                self.node_exe[0])
        self.poweron_peer_node(self.management_server,
                               self.node_exe[0],
                               poweron_timeout_mins=15)
        # STEP 3
        # Check the service group is online on both nodes
        self.wait_for_vcs_service_group_online(self.node_exe[0], cs_1_name, 2)

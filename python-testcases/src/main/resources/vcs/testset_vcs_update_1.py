"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     November 2016
@author:    Ciaran Reilly
@summary:   Update Deployment script for VCS CS used in both CDB and KGB.
            Agile:
"""

import os
from litp_generic_test import GenericTest, attr
import test_constants
from litp_cli_utils import CLIUtils
from vcs_utils import VCSUtils
from test_constants import PLAN_TASKS_SUCCESS


class Vcsupdate(GenericTest):
    """
    XML Script that will update vcs-clustered-services from a previously
    deployed XML script from testset_vcs_deploy. These updates are based off
    older user stories deemed suitable for this optimization script
    """

    def setUp(self):
        """
        Description:
            Runs before every single test
        Actions:
            1. Call the super class setup method
            2. Set up variables used in the tests
        Results:
            The super class prints out diagnostics and variables
            common to all tests are available.
        """
        super(Vcsupdate, self).setUp()

        self.ms_node = self.get_management_node_filename()
        self.cliutils = CLIUtils()
        self.vcsutils = VCSUtils()

        self.rpm_src_dir = \
            os.path.dirname(os.path.realpath(__file__)) + \
            "/test_lsb_rpms/"

        self.xml_dir = os.path.dirname(os.path.realpath(__file__)) + '/'

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            1. Perform Test Cleanup
            2. Call superclass teardown
        Results:
            Items used in the test are cleaned up and the
            super class prints out end test diagnostics
        """
        super(Vcsupdate, self).tearDown()

    def _apd_test_5167_tc1(self):
        """
        APD test coverage from test case 1 from story 5167
        :return: Nothing
        """
        phase_18_success = ('Update VCS service group "Grp_CS_c1_CS4" to add '
                            'dependencies')
        self.assertTrue(self.wait_for_task_state(self.ms_node,
                                                 phase_18_success,
                                                 PLAN_TASKS_SUCCESS,
                                                 False),
                        'CS is not updated'
                        )
        self.restart_litpd_service(self.ms_node)
        self.execute_cli_createplan_cmd(self.ms_node)
        self.execute_cli_showplan_cmd(self.ms_node)
        self.execute_cli_runplan_cmd(self.ms_node)

    def _apd_test_13411_tc7(self):
        """
        APD test coverage from test case 7 from story 13411
        :return: Nothing
        """
        phase_3_success = ('Configure nofailover trigger on node "node1"')
        self.assertTrue(self.wait_for_task_state(self.ms_node,
                                                 phase_3_success,
                                                 PLAN_TASKS_SUCCESS,
                                                 False),
                        'CS Trigger not configured successfully'
                        )
        self.restart_litpd_service(self.ms_node)
        self.execute_cli_createplan_cmd(self.ms_node)
        self.execute_cli_showplan_cmd(self.ms_node)
        self.execute_cli_runplan_cmd(self.ms_node)

    @attr('all', 'non-revert', 'update_service_groups_tc01')
    def test_update_service_groups_tc01(self):
        """
        @tms_id: test_update_service_groups_tc01
        @tms_requirements_id: LITPCDS-11241, LITPCDS-5167, LITPCDS-13411,
        LITPCDS-5172, LITPCDS-5168, LITPCDS-8968

        @tms_title: Update 7 CS based off stories listed
        @tms_description: Initial deployment of 8 vcs cluster services
        including Failover, Parallel 1 node, and Parallel 2 node, all with
        varying configurations.
        NOTE: This verifies task TORF-155104

        @tms_test_steps:
            @step: Load updated_service_groups.xml using --merge option
            @result: service groupus are successfully merged into LITP model
            @step: Create and run plan
            @result: Plan is created and completes successfully

        @tms_test_precondition: A 2 node LITP cluster is installed, and
        test_deploy_service_groups_tc01.
        @tms_execution_type: Automated
        """
        # Copy XML files to MS for test execution
        xml_list = ['updated_service_groups.xml']

        filelist = []
        for xmls in xml_list:
            filelist.append(self.get_filelist_dict(self.xml_dir + xmls,
                                                   "/home/litp-admin/"))

        self.copy_filelist_to(self.ms_node, filelist, add_to_cleanup=False)

        plan_timeout_mins = 30

        filepath1 = '/home/litp-admin/updated_service_groups.xml'

        # Current assumption is that only 1 VCS cluster will exist
        vcs_cluster_url = self.find(self.ms_node,
                                    "/deployments", "vcs-cluster")[-1]
        self.execute_cli_load_cmd(self.ms_node,
                                  vcs_cluster_url,
                                  filepath1,
                                  '--merge')

        self.execute_cli_createplan_cmd(self.ms_node)
        self.execute_cli_showplan_cmd(self.ms_node)
        self.execute_cli_runplan_cmd(self.ms_node)

        # test_07_p_default_behaviour_and_idpempotency Phase 7 of initial plan
        self._apd_test_13411_tc7()

        # test_01_p_add_one_node_deps_idemp Phase 18 of initial plan
        self._apd_test_5167_tc1()

        self.assertTrue(self.wait_for_plan_state(
            self.ms_node,
            test_constants.PLAN_COMPLETE,
            plan_timeout_mins
        ))

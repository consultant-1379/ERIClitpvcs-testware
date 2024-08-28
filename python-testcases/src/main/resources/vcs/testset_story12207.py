"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     Jan 2016
@author:    David Gibbons
@summary:   Agile: LITPCDS-12207
"""
import re

import test_constants
from litp_generic_test import GenericTest, attr

TEST_02_NUMBER_THREADS = "27"
TEST_03_NUMBER_THREADS = "14"
VCS_DEFAULT_NUMBER_THREADS = "10"


class Story12207(GenericTest):
    """
    LITPCDS-12207:
    As a LITP User I want to configure the VCS Application Agent NumThreads
    Attribute so that I can tune my VCS cluster effectively
    """

    def setUp(self):
        """
        Description:
            Runs before every single test
        Results:
            Class variables that are required to execute tests
        """
        super(Story12207, self).setUp()
        self.management_server = self.get_management_node_filename()
        self.list_managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.list_managed_nodes[0]
        self.secondary_node = self.list_managed_nodes[1]
        self.vcs_cluster_url = self.find(self.management_server,
                                    "/deployments", "vcs-cluster")[-1]

    def tearDown(self):
        super(Story12207, self).tearDown()

    def _get_application_num_threads(self, node):
        """
        Gets the number of threads set for the VCS application by parsing the
            output of the 'hatype -display Application -attribute NumThreads'
            command
        Args:
            node: (string) The node on which to run the command
        Returns:
            app_number_threads: (string) The number of threads
        """
        cmd = '/opt/VRTS/bin/hatype -display Application -attribute NumThreads'
        stdout, _, _ = self.run_command(node, cmd, su_root=True,
                                        default_asserts=True)

        # Example: "Application  NumThreads             1"
        app_number_threads_regex = \
            r"^(Application)\s+(NumThreads)\s+(?P<num_threads>\d+)$"

        re_match = re.match(app_number_threads_regex, stdout[1])
        re_dict = re_match.groupdict()

        return re_dict["num_threads"]

    @attr('all', 'non-revert', 'story12207', 'story12207_tc02')
    def test_02_p_update_valid_app_agent_num_threads(self):
        """
        @tms_id: litpcds_12207_tc02
        @tms_requirements_id: LITPCDS-12207
        @tms_title: update VCS Application NumThreads
        @tms_description:
        Check VCS Application NumThreads was updated after
        running the plan
        @tms_test_steps:
        @step: Update the vcs-cluster with the property "app_agent_num_threads"
        and a value of 27
        @result: item updated
        @step: create and run plan
        @result: plan executes successfully
        @result: Application attribute is set to 27
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        self.execute_cli_update_cmd(self.management_server,
            self.vcs_cluster_url,
            "app_agent_num_threads={0}".format(TEST_02_NUMBER_THREADS))

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)
        self.assertTrue(self.wait_for_plan_state(
            self.management_server,
            test_constants.PLAN_COMPLETE
        ))

        number_threads = self._get_application_num_threads(self.primary_node)
        self.assertEqual(TEST_02_NUMBER_THREADS, number_threads)

        number_threads = self._get_application_num_threads(self.secondary_node)
        self.assertEqual(TEST_02_NUMBER_THREADS, number_threads)

    @attr('all', 'non-revert', 'story12207', 'story12207_tc03')
    def test_03_p_update_remove_valid_app_agent_num_threads(self):
        """
        @tms_id: litpcds_12207_tc03
        @tms_requirements_id: LITPCDS-12207
        @tms_title: remove VCS Application NumThreads prop
        @tms_description:
        Check "app_agent_num_threads" property value was not changed if the
        value was set previously. Note that the default VCS value
        should not be re-set
        @tms_test_steps:
        @step: Update the vcs-cluster with the property "app_agent_num_threads"
        and a value of 27
        @result: item updated
        @step: create plan
        @result: no tasks generated
        @step: Update the "app_agent_num_threads" to 14
        @result: item updated
        @step: create and run plan
        @result: plan completes successfully
        @step: run hatype -display
        @result: the Application attribute is set to 14
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        self.execute_cli_update_cmd(self.management_server,
            self.vcs_cluster_url,
            "app_agent_num_threads",
            action_del=True)

        self.execute_cli_createplan_cmd(self.management_server,
            expect_positive=False)

        number_threads = self._get_application_num_threads(self.primary_node)
        self.assertEqual(TEST_02_NUMBER_THREADS, number_threads)

        number_threads = self._get_application_num_threads(self.secondary_node)
        self.assertEqual(TEST_02_NUMBER_THREADS, number_threads)

        self.execute_cli_update_cmd(self.management_server,
            self.vcs_cluster_url,
            "app_agent_num_threads={0}".format(TEST_03_NUMBER_THREADS))

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)
        self.assertTrue(self.wait_for_plan_state(
            self.management_server,
            test_constants.PLAN_COMPLETE
        ))

        number_threads = self._get_application_num_threads(self.primary_node)
        self.assertEqual(TEST_03_NUMBER_THREADS, number_threads)

        number_threads = self._get_application_num_threads(self.secondary_node)
        self.assertEqual(TEST_03_NUMBER_THREADS, number_threads)

    @attr('all', 'non-revert', 'story12207', 'story12207_tc04')
    def test_04_p_default_app_agent_num_threads(self):
        """
        @tms_id: litpcds_12207_tc04
        @tms_requirements_id: LITPCDS-12207
        @tms_title: default app agent num_threads
        @tms_description:
        Check app_agent_num_threads property is absent from item. Note this
        should also ensure that the default VCS-generated value is used
        on the cluster
        @tms_test_steps:
        @step: Ensure that the property app_agent_num_threads is not set on
        cluster in litp model
        @result: property not set
        @step: execute hatype -display
        @result: the default VCS number of threads (10) is used
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        output = self.get_props_from_url(self.management_server,
            self.vcs_cluster_url)
        self.assertEqual("app_agent_num_threads" in output, False)
        number_threads = self._get_application_num_threads(self.primary_node)
        self.assertEqual(VCS_DEFAULT_NUMBER_THREADS, number_threads)

        # 2nd node should be the same (as cluster-wide), but check to be sure
        number_threads = self._get_application_num_threads(self.secondary_node)
        self.assertEqual(VCS_DEFAULT_NUMBER_THREADS, number_threads)

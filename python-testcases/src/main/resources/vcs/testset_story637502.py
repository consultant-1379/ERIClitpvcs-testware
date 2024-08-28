"""
COPYRIGHT Ericsson 2023
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     February 2023
@author:    Karen Flannery
@summary:   Integration Test for TORF-637502
"""

from test_constants import PLAN_COMPLETE
from litp_generic_test import GenericTest, attr


class Story637502(GenericTest):
    """
    TORF-637502:
        Description:
            As a LITP Engineer, I want to be able to remove
             a cluster if nodes in that cluster are
             unreachable
    """

    def setUp(self):
        """
        Executed at the start of each test.
        """
        super(Story637502, self).setUp()
        self.ms_node = self.get_management_node_filename()
        self.peer_nodes = self.get_managed_node_filenames()
        self.vcs_cluster2_url = self.find(self.ms_node, '/deployments',
                                    'cluster', False)[0] + '/c2'
        self.timeout_mins = 90

    def tearDown(self):
        """
        Description:
            Runs after every single test
        """
        super(Story637502, self).tearDown()

    def create_c2_with_3_nodes(self):
        """
        Description:
            This Method creates c2 cluster with 3
            nodes (n1,n2,n3)

        Actions:
            1. Create second cluster (c2)
            2. Expand cluster with 3 nodes
        """

        vcs_cluster_props = 'cluster_type=sfha cluster_id=2 ' \
                            'low_prio_net=mgmt llt_nets=hb1,hb2 ' \
                            'cs_initial_online=on app_agent_num_threads=2'

        self.log("info", "#1: Create second cluster (c2)")
        self.execute_cli_create_cmd(self.ms_node, self.vcs_cluster2_url,
                                    'vcs-cluster',
                                    vcs_cluster_props,
                                    add_to_cleanup=False)

        self.log("info", "#2: Expand second cluster (c2) with 3 "
                         "nodes (n1,n2,n3)")
        self.execute_expand_script(self.ms_node, 'expand_cloud_c2_mn2.sh',
                                   cluster_filename='192.168.0.42_4node.sh')
        self.execute_expand_script(self.ms_node, 'expand_cloud_c2_mn3.sh',
                                   cluster_filename='192.168.0.42_4node.sh')
        self.execute_expand_script(self.ms_node, 'expand_cloud_c2_mn4.sh',
                                   cluster_filename='192.168.0.42_4node.sh')

        self.run_and_check_plan(self.ms_node, PLAN_COMPLETE,
                                self.timeout_mins, add_to_cleanup=False)

    def get_c2_systems(self):
        """
        Description:
            This Method returns the systems for c2
        Actions:
            Get a list of systems for c2
        Returns (List):
            List of systems for c2
        """
        c2_systems_list = []
        c2_systems = self.find(self.ms_node,
                        self.vcs_cluster2_url, 'reference-to-blade')

        for system in c2_systems:
            c2_systems_list.append(self.deref_inherited_path(
                self.ms_node, system))

        return c2_systems_list

    @attr('all', 'non-revert', 'expansion',
          'Story637502', 'story637502_tc01')
    def test_01_p_rm_cluster_nodes_unreachable(self):
        """
        @tms_id: torf_637502_tc01
        @tms_requirements_id: TORF-637502
        @tms_title: Remove cluster from deployed system
            when all nodes in the cluster are unreachable
        @tms_description:
        Test to verify that a cluster can be removed when
            all nodes in that cluster are unreachable
        @tms_test_steps:
            @step: Create second cluster (c2) and expand
                to contain 3 nodes
            @result: c2 is created and expanded to contain
                3 nodes
            @step: Power off nodes in c2
            @result: All nodes in c2 are powered off
            @step: Remove infrastructure items from
                deployment
            @result: Infrastructure items are marked for
                removal in the deployment
            @step: Remove c2 cluster from deployment
            @result: C2 cluster items are marked for
                removal in the deployment
            @step: Create/Run plan
            @result: Plan is created, run to completion
                and is successful.
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """

        self.log("info", "#1. Create c2 with 3 nodes n2, n3, n4")
        self.create_c2_with_3_nodes()

        self.log("info", "#2. Power off nodes in c2")
        for node in self.peer_nodes[1:]:
            self.poweroff_peer_node(self.ms_node, node)

        self.log('info', '#3. Remove infrastructure items from the model')
        for system in self.get_c2_systems():
            self.execute_cli_remove_cmd(self.ms_node, system,
                                        add_to_cleanup=False)

        self.log('info', '#4. Remove a cluster from the model')
        self.execute_cli_remove_cmd(self.ms_node,
                                    self.vcs_cluster2_url,
                                    add_to_cleanup=False)

        self.log('info', '#5. Create/Run Plan')
        self.run_and_check_plan(self.ms_node, PLAN_COMPLETE,
                                self.timeout_mins, add_to_cleanup=False)

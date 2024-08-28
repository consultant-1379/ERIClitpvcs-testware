"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     August 2019
@author:    Declan Wheeler
@summary:   Integration Tests
            Agile: STORY-360173
"""
from vcs_utils import VCSUtils
from test_constants import PLAN_COMPLETE, CHKCONFIG_PATH, MCO_EXECUTABLE
from litp_generic_test import GenericTest, attr


class Story360173(GenericTest):
    """
    TORF-360173:
        Description:
            As a LITP user, I want the ability to remove a cluster so
            that I can trial new features and restore my system to its
            pre-existing state
    """

    def setUp(self):
        """
        Executed at the start of each test.
        """
        super(Story360173, self).setUp()
        self.management_server = self.get_management_node_filename()
        self.vcs = VCSUtils()
        self.vcs_cluster2_url = self.find(self.management_server,
                                          '/deployments', 'vcs-cluster')[0]
        self.cluster2_systems = self.find(self.management_server,
                            self.vcs_cluster2_url, 'reference-to-blade')
        self.blades = self.find(self.management_server,
                                '/infrastructure', 'blade')
        self.cluster2_nodes = self.find(self.management_server,
                                        self.vcs_cluster2_url, "node")
        self.disabled_services_list = ["vcs", "puppet", "mcollective"]
        self.timeout_mins = 90
        self.node_for_removal_list = []
        self.systems_for_removal_list = []
        self.init_path = "/etc/init.d/"
        self.ping = "ping"

        # Nodes for removal
        self.log('info', 'Getting a list of nodes for removal')
        for node in self.cluster2_nodes:
            hostname = \
                self.get_props_from_url(
                    self.management_server,
                    node,
                    "hostname")
            self.node_for_removal_list.append(hostname)

        # Systems for removal
        self.log('info', 'Getting a list of systems for removal')
        for system in self.cluster2_systems:
            system_name = self.deref_inherited_path(
                self.management_server, system)
            self.systems_for_removal_list.append(system_name)

        # Change default passwords on nodes for removal
        self.log('info', 'Changing default passwords on '
                         'nodes for removal')
        for node in self.node_for_removal_list:
            self.set_pws_new_node(self.management_server, node)

    def tearDown(self):
        """
        Description:
            Runs after every single test
        """
        super(Story360173, self).tearDown()

    def get_chkconfig_status(self, node, service):
        """
        Returns the return code from running chkconfig for a
        service on a node.

        Args: node (str): Node to run the chkconfig command on.

              service (str): Service to run the chkconfig command on.

        Returns:
            rc (int). The "/sbin/chkconfig <service_name>" return code.
        """
        rc = self.run_command(
            node, "{0} {1}".format(CHKCONFIG_PATH, service), su_root=True)[2]
        return rc

    def get_service_rc(self, node, service):
        """
        Returns the return code for the state of a service on a node.

        Args: node (str): Node to run the status command on.

              service (str): Service to run the status command on.

        Returns:
            rc (int). The "/etc/init.d/<service_name> status" return code.
        """
        rc = self.run_command(
            node, "{0}{1} status".format(
                self.init_path, service), su_root=True)[2]
        return rc

    def get_vcs_state(self, node):
        """
        Returns the return code for the VCS command for
        finding the state of a system.

        Args: node (str): Node to run the hasys command on.

        Returns:
            rc (int). The "hasys -state" command return code.
        """
        rc = self.run_command(
            node, self.vcs.get_hasys_state_cmd(), su_root=True)[2]
        return rc

    @attr('all', 'non-revert', 'expansion',
          'story360173', 'story360173_tc01')
    def test_01_p_rm_cluster(self):
        """
        @tms_id: torf_360173_tc01
        @tms_requirements_id: TORF-360173
        @tms_title: Remove cluster from deployed system
        @tms_description:
        Test to verify that a user can remove a cluster
        @tms_test_steps:
            @step: Remove cluster from the deployment
            @result: The cluster is marked for removal in the deployment
            @step: Remove cluster from infrastructure
            @result: Infrastructure items are marked for removal in the,
            deployment
            @step: Create/ Run plan
            @result: Plan is created, run to completion and is successful.
            @step: Assert VCS, MCO and Puppet are stopped and disabled,
            on the removed cluster
            @result: VCS, MCO and Puppet report nothing about the,
            removed cluster
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """

        # Step 1. Remove cluster from the model
        self.log('info', 'Remove a cluster from the model')
        self.execute_cli_remove_cmd(self.management_server,
                                    self.vcs_cluster2_url,
                                    add_to_cleanup=False)

        # Step 2. Remove infrastructure items from the model
        self.log('info', 'Remove infrastructure items from the model')
        for system in self.systems_for_removal_list:
            self.execute_cli_remove_cmd(self.management_server, system,
                                        add_to_cleanup=False)

        # Step 3. Create/Run Plan
        self.log('info', 'Create/Run Plan')
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE,
                                self.timeout_mins, add_to_cleanup=False)

        # Step 4. Ensure VCS, MCO and Puppet are stopped and disabled
        self.log('info', 'Ensure VCS, MCO and Puppet are stopped and disabled')
        mco_ping = self.run_command(
            self.management_server, "{0} {1}".format(
                MCO_EXECUTABLE, self.ping))

        for node in self.node_for_removal_list:
            rc = self.get_vcs_state(node)
            self.assertNotEqual(0, rc, "RC is equal to 0, "
                                       "not the expected value")
            for service in self.disabled_services_list:
                rc = self.get_chkconfig_status(node, service)
                self.assertNotEqual(0, rc, "RC is equal to 0, "
                                           "not the expected value")
                rc = self.get_service_rc(node, service)
                self.assertNotEqual(0, rc, "RC is equal to 0, "
                                           "not the expected value")
            self.assertTrue(node not in mco_ping, "{0} appears "
                                                  "in mco ping".format(node))

"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     July 2014
@author:    Philip Daly
@summary:   As a LITP User when I add, or remove, a NIC to a node in the LITP
            model I want the change to be reflected in the VCS NIC Service
            Group so that my VCS configuration is consistent with my LITP model
            Agile: STORY LITPCDS-5158 and LITPCDS-5179
"""
from litp_generic_test import GenericTest, attr
from litp_cli_utils import CLIUtils
from redhat_cmd_utils import RHCmdUtils
from vcs_utils import VCSUtils
import test_constants
from networking_utils import NetworkingUtils


class Story5178Story5179(GenericTest):
    """
    As a LITP User when I add, or remove, a NIC to a node in the LITP
    model I want the change to be reflected in the VCS NIC Service
    Group so that my VCS configuration is consistent with my LITP model
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
        super(Story5178Story5179, self).setUp()

        self.cli = CLIUtils()
        self.rh_os = RHCmdUtils()
        self.management_server = self.get_management_node_filename()
        self.list_managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.list_managed_nodes[0]
        self.secondary_node = self.list_managed_nodes[1]
        self.vcs = VCSUtils()
        self.net_utils = NetworkingUtils()
        self.list_managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.list_managed_nodes[0]
        self.primary_node_url = self.get_node_url_from_filename(
        self.management_server, self.primary_node)
        self.secondary_node_url = self.get_node_url_from_filename(
        self.management_server, self.secondary_node)
        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.management_server,
                                    "/deployments", "vcs-cluster")[-1]

        self.cluster_id = ""
        self.cluster_id = self.vcs_cluster_url.split("/")[-1]

        # This has to be hardcoded for now, as there is no way to search
        # the model for only traffic networks
        self.traffic_networks = ["traffic1", "traffic2"]

        # NETWORK DIRECTORY
        self.network_cfg_files_dir = test_constants.NETWORK_SCRIPTS_DIR + "/*"
        # INITIAL DECLARATION OF PROPERTIES. AMENDED WITH ACTUAL VALUES LATER
        # IN TEST EXECUTION.
        self.props_dict = None
        self.nics_urls = None
        self.ci_nic_config_dict = None
        self.node_urls = None
        self.nic_col_url = None
        self.node_collection_url = None

    def tearDown(self):
        """
        Description:
            Runs after every single test
            This function just calls the super classdd function
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story5178Story5179, self).tearDown()

    def nic_group_present_on_node(self, hagrp_list_output, device_name,
                                  node_hostname):
        """
        Checks whether a NIC group for the supplied node hostname exists in
        the provided vcs console output
        Args:
            hagrp_list_output (list): Output from the vcs console.

            device_name (str): Name of the nic.

            node_hostname (str): Hostname of the node

        Returns:
            bool. Indicating whether the vcs NIC group was found for that
                  hostname.
        """
        nic_grp_name = \
        self.generate_nic_group_name(self.cluster_id,
                                     device_name)

        nic_found_in_vcs = False
        for line in hagrp_list_output:
            if nic_grp_name in line and node_hostname in line:
                nic_found_in_vcs = True
                break
        return nic_found_in_vcs

    @staticmethod
    def generate_nic_group_name(cluster_id, nic_name):
        """
        Returns the unique NIC group name given the
        cluster name and nic name as input

        Args:
            cluster_id (str): Name of cluster item as defined in the model.

            nic name (str): Name of the nic.

        Returns:
            str. Unique name of the NIC proxy resource as defined in the model
        """
        return "Grp_NIC_" + cluster_id + "_" + nic_name

    def get_hagrp_list_cmd(self):
        """
        Returns the hagrp list command for listing the groups on a system.

        Returns:
        str. The command to list the groups on a system .
        """
        cmd = self.vcs.get_hagrp_cmd("-list")

        return cmd

    def retrieve_model_networking_config(self):
        """
        Function to retrieve the NIC configuration details.
        """
        # GATHER THE NIC CONFIGURATION CURRENTLY DEFINED, THIS IS TO ENSURE
        # THAT THE EXACT CONFIGURATION MAY BE RESTORED AT THE END OF THE TESTS
        # COMPILE A LIST OF ALL THE NODES UNDER THE VCS CLUSTER
        self.node_collection_url = \
        self.find(self.management_server, self.vcs_cluster_url,
                  "node", rtn_type_children=False)[0]

        self.node_urls = \
        self.find(self.management_server, self.node_collection_url,
                  "node")
        self.nic_col_url = {}
        self.ci_nic_config_dict = {}
        for node_url in self.node_urls:
            self.ci_nic_config_dict[node_url] = {}
            self.nic_col_url[node_url] = ""
            self.nic_col_url[node_url] = \
            self.find(self.management_server, node_url,
                      "collection-of-network-interface")[0]

            self.nics_urls = \
            self.find(self.management_server, self.nic_col_url[node_url],
                      "eth")
            for nic_url in self.nics_urls:
                self.props_dict = \
                self.get_props_from_url(self.management_server, nic_url)
                self.ci_nic_config_dict[node_url][nic_url] = self.props_dict

    def create_nic(self, props_dict, url):
        """
        Function to create a NIC on the supplied url with the properties in the
        supplied dictionary.
        """
        props = ""
        for prop in props_dict.keys():
            props = \
            props + " {0}={1}".format(prop, props_dict[prop])
        self.execute_cli_create_cmd(self.management_server, url, 'eth', props,
                                    add_to_cleanup=False)

    @attr('all', 'revert')
    def test_01_p_add_then_remove_single_nic_single_node_node1(self):
        """
        @tms_id: litpcds_5178_5179_tc1
        @tms_requirements_id: LITPCDS-5179, LITPCDS-5178
        @tms_title: add then remove single nic single node node1
        @tms_description:
         To ensure that it is possible to add a single NIC to the
         node1 node in the cluster, and also possible to subsequently remove
         that NIC from the node node1 in the cluster.
        @tms_test_steps:
        @step: create network item
        @result: item created
        @step: create eth item on node1
        @result: item created
        @step: create and run plan
        @result: plan executes successfully
        @step: remove network item
        @result: item set to forremoval
        @step: remove eth item on node1
        @result: item set to forremoval
        @step: create and run plan
        @result: plan executes successfully
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # RETRIEVE THE CURRENT C.I. NIC CONFIGURATION
        self.retrieve_model_networking_config()
        # GET THE FREE NICS ON THE NODE - SELECT THE FIRST FOUND FOR THE TEST
        free_nic_list = \
        self.get_free_nics_on_node(self.management_server,
                                   self.primary_node_url)
        self.assertNotEqual([], free_nic_list)

        free_nic_details_dict = free_nic_list[0]
        node_nic_collection_url = self.nic_col_url[self.primary_node_url]
        nic_url = node_nic_collection_url + '/5178_test_nic'
        nic_props = {}
        nic_props['macaddress'] = free_nic_details_dict['MAC']
        nic_props['device_name'] = free_nic_details_dict['NAME']
        nic_props['ipaddress'] = "172.16.101.4"
        nic_props['network_name'] = "test_traffic"
        network_files_dir = test_constants.NETWORK_SCRIPTS_DIR + '/'
        network_file = 'ifcfg-{0}'.format(nic_props['device_name'])
        try:
            # COPY THE IFCFG FILE THAT SHALL BE OVERWRITTEN BY PUPPET
            returnc = self.cp_file_on_node(self.primary_node,
                                 network_files_dir + network_file,
                                 '/tmp/' + network_file,
                                 su_root=True, add_to_cleanup=False)
            self.assertEqual(True, returnc)

            # CREATE A NETWORK FOR THE TEST
            network_coll_url = \
            self.find(self.management_server, '/',
                      "collection-of-network")
            network_url = \
            network_coll_url[0] + '/{0}'.format(nic_props['network_name'])
            network_props = \
            "subnet=172.16.101.0/24 litp_management=false name=test_traffic"
            self.execute_cli_create_cmd(self.management_server, network_url,
                                        'network', network_props,
                                        add_to_cleanup=False)
            # EXECUTE THE NIC CREATION COMMAND AGAINST THE NIC UNDER TEST
            self.create_nic(nic_props, nic_url)

            # EXECUTE THE PLAN TO REMOVE THE NIC FROM THE NODE
            self.execute_cli_createplan_cmd(self.management_server)
            self.execute_cli_runplan_cmd(self.management_server)
            plan_timeout_mins = 20
            self.assertTrue(self.wait_for_plan_state(
                self.management_server,
                test_constants.PLAN_COMPLETE,
                plan_timeout_mins
            ))

            # CHECK THE HAGRP TO ENSURE THAT THE GROUP HAS BEEN
            # CREATED FOR THE NODE.
            hagrp_list_cmd = self.get_hagrp_list_cmd()
            stdout, stderr, returnc = \
            self.run_command(self.primary_node, hagrp_list_cmd, su_root=True)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)

            # GET NIC VCS GROUP NAME AND NODE HOSTNAME TO QUERY AGAINST THE VCS
            # CONSOLE TO ENSURE THE ITEM HAS BEEN REMOVED
            node_hostname = \
            self.get_props_from_url(self.management_server,
                                    self.primary_node_url,
                                    'hostname')
            nic_found_in_vcs = \
            self.nic_group_present_on_node(stdout,
                                           nic_props['device_name'],
                                           node_hostname)
            self.assertEqual(True, nic_found_in_vcs)
        finally:
            # EXECUTE THE CLI REMOVE COMMAND AGAINST THE NETWORL
            self.execute_cli_remove_cmd(self.management_server,
                                        network_url,
                                        add_to_cleanup=False)
            # EXECUTE THE NIC REMOVAL COMMAND AGAINST THE NIC UNDER TEST
            self.execute_cli_remove_cmd(self.management_server,
                                        nic_url,
                                        add_to_cleanup=False)

            # EXECUTE THE PLAN TO REMOVE THE NIC FROM THE NODE
            self.execute_cli_createplan_cmd(self.management_server)
            self.execute_cli_runplan_cmd(self.management_server)
            plan_timeout_mins = 20
            self.assertTrue(self.wait_for_plan_state(
                self.management_server,
                test_constants.PLAN_COMPLETE,
                plan_timeout_mins
            ))

            # CHECK THE HAGRP TO ENSURE THAT THE GROUP IS NO LONGER REGISTERED
            # AGAINST THAT NODE
            hagrp_list_cmd = self.get_hagrp_list_cmd()
            stdout, stderr, returnc = \
            self.run_command(self.primary_node, hagrp_list_cmd, su_root=True)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)

            # GET NIC VCS GROUP NAME AND NODE HOSTNAME TO QUERY AGAINST THE VCS
            # CONSOLE TO ENSURE THE ITEM HAS BEEN REMOVED
            node_hostname = \
            self.get_props_from_url(self.management_server,
                                    self.primary_node_url,
                                    'hostname')
            nic_found_in_vcs = \
            self.nic_group_present_on_node(stdout,
                                           nic_props['device_name'],
                                           node_hostname)
            self.assertEqual(False, nic_found_in_vcs)

            # USE IFCONFIG TO BRING THE INTERFACE DOWN
            ifcfg_cmd = \
            self.net_utils.get_ifconfig_cmd(nic_props['device_name']) + ' down'
            self.run_command(self.primary_node, ifcfg_cmd, su_root=True)
            # MOVE THE IFCFG FILE BACKUP BACK TO ITS ORIGINAL LOCATION
            self.mv_file_on_node(self.primary_node,
                                 '/tmp/' + network_file,
                                 network_files_dir + network_file,
                                 mv_args='-f', su_root=True,
                                 add_to_cleanup=False)
            # ISSUE THE IP ADD DEL CMD TO REMOVE THE IP ADDRESS FROM THE NIC
            clear_ip_cmd = \
            self.net_utils.get_clear_ip_cmd(nic_props['ipaddress'] + '/24',
                                            nic_props['device_name'])
            stdout, stderr, returnc = \
            self.run_command(self.primary_node, clear_ip_cmd, su_root=True)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertEqual([], stdout)

###############################################################################
# THE FOLLOWING TESTS RE COMMENTED OUT AS THEY CURRENTLY CANNOT BE EXECUTED
# IN C.I. DUE TO VALIDATION PREVENTING THE REMOVAL OF NIC'S WHICH HAVE
# INHERITED A ROUTE. THIS VALIDATION MAY BE REMOVED IN THE FUTURE WHICH
# WOULD ALLOW THESE TESTS TO BE EXECUTED ONCE AGAIN AND WOULD GIVE GREATER
# TEST COVERAGE AS THIS TEST IS EXECUTED PRIOR TO C-S DEPLOYMENT, WHICH
# PROVES THAT C-S'S CAN BE SUCCESSFULLY DEPLOYED UPON NIC'S ADDED TO AN
# EXISTING VCS CLUSTER DEPLOYMENT.
###############################################################################

    #@attr('pre-reg', 'revert')
    def future_02_p_remove_then_readd_single_nic_single_node_node1(self):
        """
        Description:
            To ensure that it is possible to remove a single NIC from the
            node1 node in the cluster, and also possible to add a single NIC
            to the node node1 in the cluster.
        Actions:
            1. Specify that NIC traffic1 is to be removed from node1.
            2. Ensure the NIC is removed on node node1 successfully.
            3. Ensure that the NIC group for traffic1 on node1 no longer
               exists in the vcs console.
            4. Specify a NIC as traffic1 in the litp deployment description
               and have node1 inherit it.
            5. Ensure that the NIC group is registered in the vcs console
               for node node1.
        Result:
            1. The NIC is removed successfully from the node and the NIC
               group no longer exists in the vcs console.
            2. The NIC is added successfully to the node and the NIC
               group is created in the vcs console.
        """
        # RETRIEVE THE CURRENT C.I. NIC CONFIGURATION
        self.retrieve_model_networking_config()

        # RETRIEVE INFORMATION RELEVANT TO TRAFFIC1 NIC ON NODE1
        nic_urls = self.ci_nic_config_dict[self.primary_node_url].keys()
        nic_1_traffic_1_url = ""
        for nic_url in nic_urls:
            nic_props = \
            self.ci_nic_config_dict[self.primary_node_url][nic_url]
            if nic_props['network_name'] == 'traffic1':
                nic_1_props = nic_props
                nic_name = nic_props['device_name']
                nic_1_traffic_1_url = nic_url
                break

        try:
            # EXECUTE THE NIC REMOVAL COMMAND AGAINST THE NIC UNDER TEST
            self.execute_cli_remove_cmd(self.management_server,
                                        nic_1_traffic_1_url,
                                        add_to_cleanup=False)

            # EXECUTE THE PLAN TO REMOVE THE NIC FROM THE NODE
            self.execute_cli_createplan_cmd(self.management_server)
            self.execute_cli_runplan_cmd(self.management_server)
            plan_timeout_mins = 20
            self.assertTrue(self.wait_for_plan_state(
                self.management_server,
                test_constants.PLAN_COMPLETE,
                plan_timeout_mins
            ))

            # CHECK THE HAGRP TO ENSURE THAT THE GROUP IS NO LONGER REGISTERED
            # AGAINST THAT NODE
            hagrp_list_cmd = self.get_hagrp_list_cmd()
            stdout, stderr, returnc = \
            self.run_command(self.primary_node, hagrp_list_cmd, su_root=True)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)

            # GET NIC VCS GROUP NAME AND NODE HOSTNAME TO QUERY AGAINST THE
            # VCS CONSOLE TO ENSURE THE ITEM HAS BEEN REMOVED
            node_hostname = \
            self.get_props_from_url(self.management_server,
                                    self.primary_node_url,
                                    'hostname')
            nic_found_in_vcs = \
            self.nic_group_present_on_node(stdout,
                                           nic_name,
                                           node_hostname)
            self.assertEqual(False, nic_found_in_vcs)
        finally:
            # EXECUTE THE NIC CREATION COMMAND AGAINST THE NIC UNDER TEST
            self.create_nic(nic_1_props, nic_1_traffic_1_url)

            # EXECUTE THE PLAN TO REMOVE THE NIC FROM THE NODE
            self.execute_cli_createplan_cmd(self.management_server)
            self.execute_cli_runplan_cmd(self.management_server)
            plan_timeout_mins = 20
            self.assertTrue(self.wait_for_plan_state(
                self.management_server,
                test_constants.PLAN_COMPLETE,
                plan_timeout_mins
            ))

            # CHECK THE HAGRP TO ENSURE THAT THE GROUP HAS BEEN
            # CREATED FOR THE NODE.
            hagrp_list_cmd = self.get_hagrp_list_cmd()
            stdout, stderr, returnc = \
            self.run_command(self.primary_node, hagrp_list_cmd, su_root=True)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)

            # GET NIC VCS GROUP NAME AND NODE HOSTNAME TO QUERY AGAINST THE
            # VCS CONSOLE TO ENSURE THE ITEM HAS BEEN REMOVED
            node_hostname = \
            self.get_props_from_url(self.management_server,
                                    self.primary_node_url,
                                    'hostname')
            nic_found_in_vcs = \
            self.nic_group_present_on_node(stdout,
                                           nic_name,
                                           node_hostname)
            self.assertEqual(True, nic_found_in_vcs)

    #@attr('pre-reg', 'revert')
    def future_03_p_remove_then_readd_multiple_nic_single_node_node2(self):
        """
        Description:
            To ensure that it is possible to remove multiple NICs from the
            node node1 in the cluster and that it is possible to add multiple
            NICs to the node node1 in the cluster.
        Actions:
            1. Specify that the two NICs, traffic1 and traffic2, are to be
               removed from node2.
            2. Ensure the NICs are removed from node node1 successfully.
            3. Ensure that the NIC groups for traffic1 and traffic2 on node2
               no longer exist in the vcs console.
            4. Specify two NICs, as traffic1 and traffic2, in the litp
               deployment description and have node1 inherit them.
            5. Ensure the NICs are removed from node node1 successfully.
            6. Ensure that the NIC groups are registered in the vcs console
               for node node1.
        Result:
            1. The NICs are removed successfully from the node and the NIC
               groups no longer exist in the vcs console.
            2. The NICs are added successfully to the node and the NIC
               groups now exist in the vcs console.
        """
        # RETRIEVE THE CURRENT C.I. NIC CONFIGURATION
        self.retrieve_model_networking_config()
        # ASCERTAIN THE URL FOR TRAFFIC 1 NIC ON NODE 1
        nic_urls = self.ci_nic_config_dict[self.secondary_node_url].keys()
        nic_1_traffic_1_url = ""
        nic_1_traffic_2_url = ""
        for nic_url in nic_urls:
            nic_props = \
            self.ci_nic_config_dict[self.secondary_node_url][nic_url]
            if nic_props['network_name'] == 'traffic1':
                nic_1_props = nic_props
                traffic_1_nic_name = nic_props['device_name']
                nic_1_traffic_1_url = nic_url
            elif nic_props['network_name'] == 'traffic2':
                nic_2_props = nic_props
                traffic_2_nic_name = nic_props['device_name']
                nic_1_traffic_2_url = nic_url

        try:
            # EXECUTE THE NIC REMOVAL COMMAND AGAINST THE NIC UNDER TEST
            self.execute_cli_remove_cmd(self.management_server,
                                        nic_1_traffic_1_url,
                                        add_to_cleanup=False)
            self.execute_cli_remove_cmd(self.management_server,
                                        nic_1_traffic_2_url,
                                        add_to_cleanup=False)
            # EXECUTE THE PLAN TO REMOVE THE NIC FROM THE NODE
            self.execute_cli_createplan_cmd(self.management_server)
            self.execute_cli_runplan_cmd(self.management_server)
            plan_timeout_mins = 20
            self.assertTrue(self.wait_for_plan_state(
                self.management_server,
                test_constants.PLAN_COMPLETE,
                plan_timeout_mins
            ))

            # CHECK THE HAGRP TO ENSURE THAT THE GROUP IS NO LONGER REGISTERED
            # AGAINST THAT NODE
            hagrp_list_cmd = self.get_hagrp_list_cmd()
            stdout, stderr, returnc = \
            self.run_command(self.primary_node, hagrp_list_cmd, su_root=True)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)

            # GET NIC VCS GROUP NAME AND NODE HOSTNAME TO QUERY AGAINST THE
            # VCS CONSOLE TO ENSURE THE ITEM HAS BEEN REMOVED
            node_hostname = \
            self.get_props_from_url(self.management_server,
                                    self.secondary_node_url, 'hostname')
            nic_found_in_vcs = \
            self.nic_group_present_on_node(stdout,
                                           traffic_1_nic_name,
                                           node_hostname)
            self.assertEqual(False, nic_found_in_vcs)

            nic_found_in_vcs = \
            self.nic_group_present_on_node(stdout,
                                           traffic_2_nic_name,
                                           node_hostname)
            self.assertEqual(False, nic_found_in_vcs)
        finally:
            # EXECUTE THE NIC CREATION COMMAND AGAINST THE NIC UNDER TEST
            self.create_nic(nic_1_props, nic_1_traffic_1_url)
            self.create_nic(nic_2_props, nic_1_traffic_2_url)

            # EXECUTE THE PLAN TO ADD THE NIC TO THE NODE
            self.execute_cli_createplan_cmd(self.management_server)
            self.execute_cli_runplan_cmd(self.management_server)
            plan_timeout_mins = 20
            self.assertTrue(self.wait_for_plan_state(
                self.management_server,
                test_constants.PLAN_COMPLETE,
                plan_timeout_mins
            ))

            # CHECK THE HAGRP TO ENSURE THAT THE GROUP HAS BEEN
            # CREATED FOR THE NODE.
            hagrp_list_cmd = self.get_hagrp_list_cmd()
            stdout, stderr, returnc = \
            self.run_command(self.secondary_node, hagrp_list_cmd,
                             su_root=True)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)

            # GET NIC VCS GROUP NAME AND NODE HOSTNAME TO QUERY AGAINST THE
            # VCS CONSOLE TO ENSURE THE ITEM HAS BEEN REMOVED
            node_hostname = \
            self.get_props_from_url(self.management_server,
                                    self.secondary_node_url, 'hostname')
            nic_found_in_vcs = \
            self.nic_group_present_on_node(stdout,
                                           traffic_1_nic_name,
                                           node_hostname)
            self.assertEqual(True, nic_found_in_vcs)

            nic_found_in_vcs = \
            self.nic_group_present_on_node(stdout,
                                           traffic_2_nic_name,
                                           node_hostname)
            self.assertEqual(True, nic_found_in_vcs)

    #@attr('pre-reg', 'revert')
    def future_04_p_remove_readd_single_nic_multiple_node_node1_node2(self):
        """
        Description:
            To ensure that it is possible to remove a single NIC from both
            the node1 and node2 nodes in the cluster and that it is possible
            to add a single NIC to the node1 and node2 nodes in the cluster.
        Actions:
            1. Specify that the NIC traffic2 is to be removed from both
               node1 and node2.
            2. Ensure the NICs are removed from node node1 successfully.
            3. Ensure that the NIC group for traffic2 on node1 and node2 no
               longer exists in the vcs console.
            4. Specify a NIC as traffic2 in the litp deployment description
               and have node1 and node2 inherit it.
            5. Ensure the NICs are removed from node node1 successfully.
            6. Ensure that the NIC group is registered in the vcs console for
               both specified nodes.
        Result:
            1. The NICs are removed successfully from the nodes and the NIC
               groups no longer exist in the vcs console.
            2. The NICs are added successfully to the nodes and the NIC
               groups are created in the vcs console.
        """
        # RETRIEVE THE CURRENT C.I. NIC CONFIGURATION
        self.retrieve_model_networking_config()
        nic_urls = self.ci_nic_config_dict[self.primary_node_url].keys()
        nic_1_traffic_2_url = ""
        for nic_url in nic_urls:
            nic_props = \
            self.ci_nic_config_dict[self.primary_node_url][nic_url]
            if nic_props['network_name'] == 'traffic2':
                nic_1_props = nic_props
                nic_1_traffic_2_nic_name = nic_props['device_name']
                nic_1_traffic_2_url = nic_url

        nic_urls = self.ci_nic_config_dict[self.secondary_node_url].keys()
        nic_2_traffic_2_url = ""
        for nic_url in nic_urls:
            nic_props = \
            self.ci_nic_config_dict[self.secondary_node_url][nic_url]
            if nic_props['network_name'] == 'traffic2':
                nic_2_props = nic_props
                nic_2_traffic_2_nic_name = nic_props['device_name']
                nic_2_traffic_2_url = nic_url

        try:
            # EXECUTE THE NIC REMOVAL COMMAND AGAINST THE NIC UNDER TEST
            self.execute_cli_remove_cmd(self.management_server,
                                        nic_1_traffic_2_url,
                                        add_to_cleanup=False)
            self.execute_cli_remove_cmd(self.management_server,
                                        nic_2_traffic_2_url,
                                        add_to_cleanup=False)
            # EXECUTE THE PLAN TO REMOVE THE NIC FROM THE NODE
            self.execute_cli_createplan_cmd(self.management_server)
            self.execute_cli_runplan_cmd(self.management_server)
            plan_timeout_mins = 20
            self.assertTrue(self.wait_for_plan_state(
                self.management_server,
                test_constants.PLAN_COMPLETE,
                plan_timeout_mins
            ))

            # CHECK THE HAGRP TO ENSURE THAT THE GROUP IS NO LONGER REGISTERED
            # AGAINST THAT NODE
            hagrp_list_cmd = self.get_hagrp_list_cmd()
            stdout, stderr, returnc = \
            self.run_command(self.primary_node, hagrp_list_cmd, su_root=True)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)

            # GET NIC VCS GROUP NAME AND NODE HOSTNAME TO QUERY AGAINST THE
            # VCS CONSOLE TO ENSURE THE ITEM HAS BEEN REMOVED
            node_hostname = \
            self.get_props_from_url(self.management_server,
                                    self.primary_node_url,
                                    'hostname')
            nic_found_in_vcs = \
            self.nic_group_present_on_node(stdout,
                                           nic_1_traffic_2_nic_name,
                                           node_hostname)
            self.assertEqual(False, nic_found_in_vcs)

            nic_found_in_vcs = \
            self.nic_group_present_on_node(stdout,
                                           nic_2_traffic_2_nic_name,
                                           node_hostname)
            self.assertEqual(False, nic_found_in_vcs)
        finally:
            # EXECUTE THE NIC CREATION COMMAND AGAINST THE NIC UNDER TEST
            self.create_nic(nic_1_props, nic_1_traffic_2_url)
            self.create_nic(nic_2_props, nic_2_traffic_2_url)

            # EXECUTE THE PLAN TO ADD THE NIC To THE NODE
            self.execute_cli_createplan_cmd(self.management_server)
            self.execute_cli_runplan_cmd(self.management_server)
            plan_timeout_mins = 20
            self.assertTrue(self.wait_for_plan_state(
                self.management_server,
                test_constants.PLAN_COMPLETE,
                plan_timeout_mins
            ))

            # CHECK THE HAGRP TO ENSURE THAT THE GROUP HAS BEEN
            # CREATED FOR THE NODE.
            hagrp_list_cmd = self.get_hagrp_list_cmd()
            stdout, stderr, returnc = \
            self.run_command(self.primary_node, hagrp_list_cmd, su_root=True)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)

            # GET NIC VCS GROUP NAME AND NODE HOSTNAME TO QUERY AGAINST THE
            # VCS CONSOLE TO ENSURE THE ITEM HAS BEEN ADDED
            node_hostname = \
            self.get_props_from_url(self.management_server,
                                    self.primary_node_url,
                                    'hostname')
            nic_found_in_vcs = \
            self.nic_group_present_on_node(stdout,
                                           nic_1_traffic_2_nic_name,
                                           node_hostname)
            self.assertEqual(True, nic_found_in_vcs)

            nic_found_in_vcs = \
            self.nic_group_present_on_node(stdout,
                                           nic_2_traffic_2_nic_name,
                                           node_hostname)
            self.assertEqual(True, nic_found_in_vcs)

"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     July 2014
@author:    Damian Usher
@summary:   Integration tests for As a LITP User I want my VCS managed
            application packages upgraded so that I can keep my software
            up to date.
            Agile: STORY LITPCDS-3994
"""
from litp_generic_test import GenericTest, attr
from litp_cli_utils import CLIUtils
from redhat_cmd_utils import RHCmdUtils
from vcs_utils import VCSUtils
import test_constants
import os
import re


class Story3994(GenericTest):
    """
    Integration tests for As a LITP User I want my VCS managed
    application packages upgraded so that I can keep my software
    up to date.
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
        super(Story3994, self).setUp()

        self.cli = CLIUtils()
        self.rh_os = RHCmdUtils()
        self.management_server = self.get_management_node_filename()
        self.list_managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.list_managed_nodes[0]

        self.vcs = VCSUtils()
        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.management_server,
                                    "/deployments", "vcs-cluster")[-1]

        self.cluster_name = self.vcs_cluster_url.split("/")[-1]
        self.rpm_src_dir = os.path.dirname(os.path.realpath(__file__)) + \
                           "/test_lsb_rpms/"

        # This has to be hardcoded for now, as there is no way to search
        # the model for only traffic networks
        self.traffic_networks = ["traffic1", "traffic2"]

        # Get urls of all nodes in the vcs-cluster
        self.vcs_nodes_urls = self.find(
            self.management_server,
            self.vcs_cluster_url,
            "node"
        )

        # Get hostnames of all nodes in the vcs-cluster
        self.managed_nodes_hostnames = []
        for node in self.vcs_nodes_urls:
            self.managed_nodes_hostnames.append(str(
                self.get_props_from_url(
                    self.management_server,
                    node,
                    filter_prop="hostname")))

        # Get urls of all clustered services
        self.cs_urls = self.find(self.management_server,
            self.vcs_cluster_url, "vcs-clustered-service")

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
        super(Story3994, self).tearDown()

    def check_node_lock_or_unlock_task_sequence(self, task_regex,
        node_hostname, unlock=False):
        """
        Description:
             Function to check that a node Lock/Unlock is sequenced
             Prior/Following the specified task.
        Args:
            task_regex (str):    Pattern of the specified task
            node_hostname (str): Hostname of the node that will be checked
                                 for locking/unlocking
            unlock (bool): Boolean indicating whether the task being searched
                           for is a node unlock. Defaults to node lock.
        Returns:
            bool. Indicates whether the node lock/unlock was found as expected.
        """

        plan_stdout, _, _ = \
            self.execute_cli_showplan_cmd(self.management_server)
        parsed_plan = self.cli.parse_plan_output(plan_stdout)

        subtasks = []

        # Gather all subtasks in a flat array
        for task in parsed_plan.values():
            for subtask in task.values():
                subtasks.append(subtask['DESC'][1].strip())

        # Find the specified task
        task_idx = None
        for idx, desc in enumerate(subtasks):
            if re.match(task_regex, desc):
                task_idx = idx
                break

        # Make sure the task was found
        self.assertNotEqual(None, task_idx)

        if not unlock:
            #
            # Ensure LOCK
            #
            # Loop from the specified task to the beginning and
            # make sure it gets locked at some point
            for idx in reversed(range(0, task_idx)):
                desc = subtasks[idx]
                if desc.lower() == \
                    ('Lock VCS on node "{0}"'.format(node_hostname)).lower():
                    return True
                elif desc.lower() == \
                    ('Unlock VCS on node "{0}"'.format(node_hostname)).lower():
                    return False
            return False

        else:
            #
            # Ensure UNLOCK
            #
            # Loop from the specified task to the end and
            # make sure it gets unlocked at some point
            for idx in range(task_idx + 1, len(subtasks)):
                desc = subtasks[idx]
                if desc.lower() == \
                    ('Lock VCS on node "{0}"'.format(node_hostname)).lower():
                    return False
                elif desc.lower() == \
                    ('Unlock VCS on node "{0}"'.format(node_hostname)).lower():
                    return True
            return False

    def compile_cs_active_node_dict(self, conf):
        """
        Function to compile a dictionary detailing the nodes on which each
        clustered service is active.
        Args:
            conf (dict): Expected model of clustered services
                           and associated IP addresses
        Return:
            dict. A dictionary detailing which clustered services are
                  online on each node.
        """
        cs_active_node_dict = {}
        ##############################################################
        # The hostname of the node is used as the system name in VCS #
        # This piece of code is just retrieving all the hostnames ####
        # for the managed nodes ######################################
        ##############################################################
        list_of_systems = []
        for node in self.find(self.management_server, self.vcs_cluster_url,
                              "node"):
            list_of_systems.append(str(
                self.get_props_from_url(
                    self.management_server,
                    node,
                    filter_prop="hostname")))

        # CYCLE THROUGH CLUSTERED SERVICES BASED ON THEIR VCS NAME ENTRY
        # AND COMPILE A DICTIONARY OF ALL THE NODES ON WHICH THEY ARE ACTIVE.
        for clustered_service in conf["app_per_cs"].keys():
            cs_name = \
            self.vcs.generate_clustered_service_name(clustered_service,
                                                 self.cluster_name)

            # GATHER ALL OF THE NODES ON WHICH THE CS IS ACTIVE
            cmd = self.vcs.get_hagrp_state_cmd() + cs_name
            stdout, stderr, rc = self.run_command(self.primary_node, cmd,
                                                  su_root=True)
            self.assertEqual(0, rc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)

            # ADD AN ENTRY TO THE COMPILATION DICT OF THE CS WITH ANY ACTIVE
            # NODES FOUND FOR IT
            cs_active_node_dict = \
                self.check_hostname_cs_online(list_of_systems,
                                              clustered_service,
                                              stdout,
                                              cs_active_node_dict)
        # At least one node must be returned
        self.assertNotEqual({}, cs_active_node_dict)

        return cs_active_node_dict

    @staticmethod
    def check_hostname_cs_online(hostnames, clustered_service,
                                 vcs_output, cs_active_node_dict):
        """
        Function to check whether a clustered service is active on the provided
        hostnames.

        Args:
            hostnames (list): List of host names of nodes to be checked against
            clustered_service (Str): Name of the clustered service as it
                                     appears in the conf dictionary.
            vcs_output (Str): The output from the VCS query issued against
                              the clustered service.
            cs_active_node_dict (dict): Lists of nodes on which each C-S is
                                        active.
        """
        cs_active_node_dict[clustered_service] = []
        for hostname in hostnames:
            for line in vcs_output:
                if hostname in line and "ONLINE" in line:
                    cs_active_node_dict[clustered_service].append(hostname)
        if cs_active_node_dict[clustered_service] == []:
            del cs_active_node_dict[clustered_service]
        return cs_active_node_dict

    def map_node_host_to_node_file(self):
        """
        Function to map the node hostnames to their respective filenames
        """
        node_mapping = {}
        for node in self.find(self.management_server, self.vcs_cluster_url,
                              "node"):
            node_filename = \
            self.get_node_filename_from_url(self.management_server, node)
            node_mapping[str(
                self.get_props_from_url(
                    self.management_server,
                    node,
                    filter_prop="hostname"))] = node_filename
        return node_mapping

    def check_plan_phases(self, updated_pkg_versions, node_hostnames):
        """
        Check the plan phases layout to ensure that a node lock occurs
        prior to the package installation and that a node unlock occurs
        following the package installation.
        """

        for pkg in updated_pkg_versions:
            for node_hostname in node_hostnames:
                find_task = 'Update package "{0}" on node "{1}"'.format(
                    pkg, node_hostname)
                print find_task

                lock_found = \
                    self.check_node_lock_or_unlock_task_sequence(
                        re.escape(find_task), node_hostname, unlock=False)
                self.assertEqual(True, lock_found)

                unlock_found = \
                    self.check_node_lock_or_unlock_task_sequence(
                        re.escape(find_task), node_hostname, unlock=True)
                self.assertEqual(True, unlock_found)

    def get_cs_url(self, cs_name):
        """
        Code to find the package under C-S declaration
        find all C-S declarations in the deployment description
        """

        # FROM THE LIST FOUND RETRIEVE THE URL OF THE C-S UNDER TEST
        length = len(cs_name)
        for url in self.cs_urls:
            if url[-length:] == cs_name:
                return url
        return None

    def get_cs_nodes(self, cs_node_list):
        """
        Find the filenames of the nodes on which the c-s is deployed
        """

        # FIND THE URLS OF THE NODES ON WHICH THE C-S IS DEPLOYED
        deployed_node_urls = []
        for cs_node in cs_node_list:
            length = len(cs_node)
            for node_url in self.vcs_nodes_urls:
                if node_url[-length:] == cs_node:
                    deployed_node_urls.append(node_url)
                    break

        node_filenames_list = []
        for node_url in deployed_node_urls:
            node_filenames_list.append(
                        self.get_node_filename_from_url(
                                        self.management_server, node_url))
        return node_filenames_list

    @attr('all', 'non-revert', 'kgb-other', 'story3994',
          'story3994_test_plan1')
    def test_01_pkg_upgrade_plan1(self):
        """
        @tms_id: litpcds_3994_tc0_plan
        @tms_requirements_id: LITPCDS-3994
        @tms_title: update package items version property
        @tms_description:
        This test generates and execute a plan which will
        update various cluster services.
        @tms_test_steps:
        @step: Copy RPMs to MS and import into REPO
        @result: rpms imported
        @step: update package items version property
        @result: items updated
        @step: create and run plan
        @result: plan executes successfully
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # ==================================================
        # It is assumed that any rpms required for this test
        # exist in a repo before the plan is executed
        # This section of the test sets this up
        # ===================================================
        # List of rpms required for this test
        list_of_lsb_rpms = [
            'EXTR-lsbwrapper2-2.1.0.rpm',
            'EXTR-lsbwrapper1-2.1.0.rpm',
            'EXTR-lsbwrapper4-2.1.0.rpm',
            'EXTR-lsbwrapper3-2.1.0.rpm',
            'EXTR-lsbwrapper23-2.1.0.rpm',
            'EXTR-lsbwrapper5-2.1.0.rpm',
            'EXTR-lsbwrapper6-2.1.0.rpm',
            'EXTR-lsbwrapper9-2.1.0.rpm',
            'EXTR-lsbwrapper10-2.1.0.rpm',
            'EXTR-lsbwrapper7-2.1.0.rpm',
            'EXTR-lsbwrapper8-2.1.0.rpm',
            'EXTR-lsbwrapper8-3.1.0.rpm',
            'EXTR-lsbwrapper28-2.1.0.rpm'
        ]

        # Copy RPMs to Management Server
        filelist = []
        for rpm in list_of_lsb_rpms:
            filelist.append(self.get_filelist_dict(self.rpm_src_dir + rpm,
                "/tmp/"))

        ret = self.copy_filelist_to(self.management_server, filelist,
                              add_to_cleanup=False, root_copy=True)
        self.assertTrue(ret)

        # Use LITP import to add to repo for each RPM
        for rpm in list_of_lsb_rpms:
            self.execute_cli_import_cmd(
                self.management_server,
                '/tmp/' + rpm,
                test_constants.PP_PKG_REPO_DIR)

        # ========================================================
        # This section will find all the items in the model that
        # are to be updated and make the changes
        # ========================================================

        # list of packages which will be be updated where the pkg
        # resides under the clustered-service and not the software item
        updated_pkg_versions = {'CS2': ['EXTR-lsbwrapper2'],
                                'CS1': ['EXTR-lsbwrapper1'],
                                'CS3': ['EXTR-lsbwrapper3',
                                        'EXTR-lsbwrapper23'],
                                'CS5': ['EXTR-lsbwrapper5'],
                                'CS9': ['EXTR-lsbwrapper9'],
                                'CS7': ['EXTR-lsbwrapper7'],
                                'CS8': ['EXTR-lsbwrapper8'],
                                'CS28': ['EXTR-lsbwrapper28'],
                                }

        # list of packages which will be be updated where the pkg
        # resides under the software item and not under the clustered-service
        updated_parent_pkg_versions = {'CS1': ['EXTR-lsbwrapper4'],
                                       'CS6': ['EXTR-lsbwrapper6'],
                                       'CS10': ['EXTR-lsbwrapper10']}

        list_of_cs_pkg_upgrade = ["CS2", "CS1", "CS3",
                                  "CS5", "CS6", "CS9",
                                  "CS10", "CS7", "CS8", "CS28"]

        # FIND THE software item URL
        soft_item_urls = self.find(self.management_server, '/software/',
                                  "collection-of-software-item")
        self.assertNotEqual(0, len(soft_item_urls))
        soft_item_url = soft_item_urls[0]

        # the version of the rpms being tested will all be version 2
        version_property = 'version=2.1.0-1'

        for cs_name in list_of_cs_pkg_upgrade:
            cs_url = self.get_cs_url(cs_name)
            # FIND THE PACKAGES COLLECTION URL BELOW THE C-S URL
            cs_pkgs_urls = self.find(self.management_server, cs_url,
                                     "software-item",
                                     rtn_type_children=False, find_refs=True)
            self.assertNotEqual(0, len(cs_pkgs_urls))
            cs_pkgs_url = cs_pkgs_urls[0]

            # COMPILE AND EXECUTE THE COMMAND TO UPDATE THE PACKAGE VERSION
            # PROPERTY OF THE VCS C-S UNDER TEST
            if cs_name in updated_pkg_versions:
                if cs_name == "CS8":
                    version_property = 'version=latest'

                for pkg in updated_pkg_versions[cs_name]:
                    url = cs_pkgs_url + '/' + pkg
                    cmd = self.cli.get_update_cmd(url, version_property)
                    stdout, stderr, returnc = \
                                  self.run_command(self.management_server, cmd)
                    self.assertEqual(0, returnc)
                    self.assertEqual([], stderr)
                    self.assertEqual([], stdout)

            if cs_name in updated_parent_pkg_versions:
                for pkg in updated_parent_pkg_versions[cs_name]:
                    url = soft_item_url + '/' + pkg
                    cmd = self.cli.get_update_cmd(url, version_property)
                    stdout, stderr, returnc = \
                                  self.run_command(self.management_server, cmd)
                    self.assertEqual(0, returnc)
                    self.assertEqual([], stderr)
                    self.assertEqual([], stdout)
        # ===================================================
        # This section will create the plan and verify that
        # upgrade of the rpms happens when the node is locked
        # ===================================================

        self.execute_cli_createplan_cmd(self.management_server)
        plan_stdout, _, _ = \
            self.execute_cli_showplan_cmd(self.management_server)

        parsed_plan = self.cli.parse_plan_output(plan_stdout)

        # Generate the expected description of the locking and unlocking tasks
        expected_task = {}
        for node in self.list_managed_nodes:
            url = self.get_node_url_from_filename(self.management_server, node)
            node_name = url.split('/')[-1]
            expected_task[node_name] = {'lock': [url,
                                                 'Lock VCS on node "' + \
                                                 node_name + '"'],
                              'unlock': [url, 'Unlock VCS on node ' + \
                                                node_name]}

        # 3 phases per node, lock, upgrade packages, unlock
        # 1st phase has to be lock, last phase has to be unlock
        # All these CS are either 2 node failover, 1 node parallel
        # or 2 node parallel
        # 2 nodes * 3 phases = 6 phases
        # implies 1st phase is lock of a node
        #         3rd phase is unlock of aid node
        #         4th phase is lock of other node
        #         6th phase is unlock of other node

        # First phase is unlock
        self.assertTrue(re.search('Lock VCS on node',
                                  parsed_plan[1][1]['DESC'][-1]))
        first_node_name = parsed_plan[1][1]['DESC'][0].split('/')[-1]
        # 3rd phase is corresponding unlock of phase 2
        self.assertTrue(expected_task[first_node_name]['unlock'],
                        parsed_plan[3][1]['DESC'])

        # 4th phase is unlock
        self.assertTrue(re.search('Unlock VCS on node',
                        parsed_plan[parsed_plan.keys()[-1]][1]['DESC'][-1]))
        second_node_name = parsed_plan[6][1]['DESC'][0].split('/')[-1]
        # 6th phase is corresponding unlock of phase 4
        self.assertTrue(expected_task[second_node_name]['unlock'],
                        parsed_plan[4][1]['DESC'])

        # =====================================================
        # Execute the plan
        # =====================================================

        plan_timeout_mins = 20
        # EXECUTE THE PLAN TO DEPLOY THE UPDATED PACKAGE
        self.execute_cli_runplan_cmd(self.management_server)

        # WAIT FOR THE PLAN TO COMPLETE - ENSURE THE PLAN COMPLETES
        # SUCCESSFULLY WITHIN THE SPECIFIED TIME BOX
        self.assertTrue(self.wait_for_plan_state(
            self.management_server,
            test_constants.PLAN_COMPLETE,
            plan_timeout_mins
        ))

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_01')
    def test_01_p_pkg_upgrade_2_node_failover(self):
        """
        @tms_id: litpcds_3994_tc1
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package upgrade on 2 node failover CS2
        @tms_description:
            This test will verify that package version can be incremented
            and the package will be successfully upgraded to the new version
            This test will verify the app under CS2 has being upgraded.
            pkg item exists under the clustered-service
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        # Generate configuration that was already deployed
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        # Define what clustered-serice is being tested and what version
        cs_name = 'CS2'
        updated_pkg_versions = {'EXTR-lsbwrapper2': {'version': '2.1.0-1'}}

        cs_url = self.get_cs_url(cs_name)

        # Determine from the model which nodes the clusteres-service is
        # deployed on
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = ['EXTR-lsbwrapper2-2.1.0-1']

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for updated_pkg in updated_pkg_versions:
            if updated_pkg[-length:] == cs_numeric:
                active_pkg = updated_pkg
        version = updated_pkg_versions[active_pkg]['version']
        major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            updated_service_name = \
                service_name + '-v0{0}'.format(major_version)

            remote_path = "/tmp/'{0}'".format(updated_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)
        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_02')
    def test_02_p_pkg_upgrade_2_node_failover(self):
        """
        @tms_id: litpcds_3994_tc2
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package upgrade on 2 node failover CS1
        @tms_description:
            This test will verify that package version can be incremented
            and the package will be successfully upgraded to the new version
            This test will verify the app under CS1 has being upgraded.
            pkg item exists under the clustered-service
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # Generate configuration that was already deployed
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        # Define what clustered-serice is being tested and what version
        cs_name = 'CS1'
        updated_pkg_versions_cs = {'EXTR-lsbwrapper1': {'version': '2.1.0-1'}}

        cs_url = self.get_cs_url(cs_name)

        soft_item_urls = self.find(self.management_server, '/software/',
                                  "collection-of-software-item")
        self.assertNotEqual(0, len(soft_item_urls))

        updated_pkg_versions_sw = {'EXTR-lsbwrapper4': {'version': '2.1.0-1'}}

        # Merges all packages being updated under CS and under software items
        updated_pkg_versions = dict(
            updated_pkg_versions_cs.items() +
            updated_pkg_versions_sw.items())

        # Determine from the model which nodes the clusteres-service is
        # deployed on
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for updated_pkg in updated_pkg_versions:
            if updated_pkg[-length:] == cs_numeric:
                active_pkg = updated_pkg
        version = updated_pkg_versions[active_pkg]['version']
        major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            updated_service_name = \
                service_name + '-v0{0}'.format(major_version)
            remote_path = "/tmp/'{0}'".format(updated_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_03')
    def test_03_p_pkg_upgrade_2_node_failover(self):
        """
        @tms_id: litpcds_3994_tc3
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package upgrade on 2 node failover CS1
        @tms_description:
            This test will verify that package version can be incremented
            and the package will be successfully upgraded to the new version
        @tms_test_steps:
        @step: import rpms
        @result: rpms imported
        @step: updated clustered-service items version property on CS1
        @result: items updated
        @step: create and run plan
        @result: item executes successfully
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        #######################################################################
        # ACT. 0 THIS SECTION OF THE TEST ACCOMPLISHES THE TEST PREREQUISITES
        #######################################################################

        # ==================================================
        # It is assumed that any rpms required for this test
        # exist in a repo before the plan is executed
        # This section of the test sets this up
        # ===================================================
        # List of rpms required for this test
        list_of_lsb_rpms = [
            "EXTR-lsbwrapper1-3.1.0.rpm",
            "EXTR-lsbwrapper4-3.1.0.rpm",
        ]

        # Copy RPMs to Management Server
        filelist = []
        for rpm in list_of_lsb_rpms:
            filelist.append(self.get_filelist_dict(self.rpm_src_dir + rpm,
                "/tmp/"))

        ret = self.copy_filelist_to(self.management_server, filelist,
                              add_to_cleanup=False, root_copy=True)
        self.assertTrue(ret)

        # Use LITP import to add to repo for each RPM
        for rpm in list_of_lsb_rpms:
            self.execute_cli_import_cmd(
                self.management_server,
                '/tmp/' + rpm,
                test_constants.PP_PKG_REPO_DIR)

        # RETRIEVE THE BASE CONFIGURATION DICTIONARY
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        #######################################################################
        # ACT. 1. THIS SECTION OF THE TEST UPDATES THE PREVIOUSLY DEPLOYED C-S
        #######################################################################

        # MAXIMUM TIME ALLOWED FOR A PLAN TO RUN TO COMPLETION PRIOR TO AN
        # EXCEPTION BEING RAISED AND THE TEST FAILING.
        plan_timeout_mins = 20

        # C-S UNDER TEST AND ITS UPDATED PROPERTY VALUES
        cs_name = 'CS1'
        updated_pkg_versions = {
            'EXTR-lsbwrapper1': {'version': '3.1.0-1'},
            'EXTR-lsbwrapper4': {'version': '3.1.0-1'},
        }

        cs_url = self.get_cs_url(cs_name)

        # FIND THE PACKAGES COLLECTION URL BELOW THE C-S URL
        cs_pkgs_urls = self.find(self.management_server, cs_url,
                                "software-item",
                                rtn_type_children=False, find_refs=True)
        self.assertNotEqual(0, len(cs_pkgs_urls))
        cs_pkgs_url = cs_pkgs_urls[0]

        # COMPILE AND EXECUTE THE COMMAND TO UPDATE THE PACKAGE VERSION
        # PROPERTY OF THE VCS C-S UNDER TEST
        for pkg in updated_pkg_versions.keys():
            url = cs_pkgs_url + '/' + pkg
            properties = \
                'version={0}'.format(updated_pkg_versions[pkg]['version'])
            cmd = \
                self.cli.get_update_cmd(url, properties)
            stdout, stderr, returnc = \
                self.run_command(self.management_server, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertEqual([], stdout)

        #######################################################################
        # ACT. 2. THIS SECTION CREATES THE UPDATED CONFIGURATION PLAN
        #######################################################################

        # CREATE A PLAN TO DEPLOY THE UPDATED PACKAGE OBJECT
        self.execute_cli_createplan_cmd(self.management_server)

        #######################################################################
        # ACT. 3. THIS SECTION CHECKS THE LAYOUT OF THE NODE LOCK/UNLOCK TASKS
        #######################################################################

        self.check_plan_phases(updated_pkg_versions,
            self.managed_nodes_hostnames)

        #######################################################################
        # ACT. 4. THIS SECTION DEPLOYS THE UPDATED C-S PKG CONFIGURATION
        #######################################################################

        # EXECUTE THE PLAN TO DEPLOY THE UPDATED PACKAGE
        self.execute_cli_runplan_cmd(self.management_server)

        # WAIT FOR THE PLAN TO COMPLETE - ENSURE THE PLAN COMPLETES
        # SUCCESSFULLY WITHIN THE SPECIFIED TIME BOX
        self.assertTrue(self.wait_for_plan_state(
            self.management_server,
            test_constants.PLAN_COMPLETE,
            plan_timeout_mins
        ))

        #######################################################################
        # ACT. 5. THIS SECTION CHECKS THAT THE UPDATED PACKAGE HAS BEEN
        # DEPLOYED TO THE NODES ASSIGNED TO THE C-S.
        #######################################################################

        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for updated_pkg in updated_pkg_versions:
            if updated_pkg[-length:] == cs_numeric:
                active_pkg = updated_pkg
        version = updated_pkg_versions[active_pkg]['version']
        major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            updated_service_name = \
                service_name + '-v0{0}'.format(major_version)
            remote_path = "/tmp/'{0}'".format(updated_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_04')
    def test_04_p_pkg_upgrade_2_node_failover(self):
        """
        @tms_id: litpcds_3994_tc4
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package upgrade on 2 node failover CS3
        @tms_description:
            This test will verify that package version can be incremented
            and the package will be successfully upgraded to the new version
            This test will verify the app under CS3 has being upgraded.
            pkg item exists under the clustered-service
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # Generate configuration that was already deployed
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        # Define what clustered-serice is being tested and what version
        cs_name = 'CS3'
        updated_pkg_versions = {
            'EXTR-lsbwrapper3': {'version': '2.1.0-1'},
            'EXTR-lsbwrapper23': {'version': '2.1.0-1'},
        }

        cs_url = self.get_cs_url(cs_name)

        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for updated_pkg in updated_pkg_versions:
            if updated_pkg[-length:] == cs_numeric:
                active_pkg = updated_pkg
        version = updated_pkg_versions[active_pkg]['version']
        major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            updated_service_name = \
                service_name + '-v0{0}'.format(major_version)
            remote_path = "/tmp/'{0}'".format(updated_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_05')
    def test_05_p_pkg_upgrade_2_node_parallel(self):
        """
        @tms_id: litpcds_3994_tc5
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package upgrade on 2 node parallel CS5
        @tms_description:
            This test will verify that package version can be incremented
            and the package will be successfully upgraded to the new version
            This test will verify the app under CS5 has being upgraded.
            pkg item exists under the clustered-service
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated

        """
        # RETRIEVE THE BASE CONFIGURATION DICTIONARY
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        # C-S UNDER TEST AND ITS UPDATED PROPERTY VALUES
        cs_name = 'CS5'
        updated_pkg_versions = {'EXTR-lsbwrapper5': {'version': '2.1.0-1'}}

        cs_url = self.get_cs_url(cs_name)

        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for updated_pkg in updated_pkg_versions:
            if updated_pkg[-length:] == cs_numeric:
                active_pkg = updated_pkg
        version = updated_pkg_versions[active_pkg]['version']
        major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            updated_service_name = \
                service_name + '-v0{0}'.format(major_version)
            remote_path = "/tmp/'{0}'".format(updated_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_06')
    def test_06_p_pkg_upgrade_2_node_parallel(self):
        """
        @tms_id: litpcds_3994_tc6
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package upgrade on 2 node parallel CS6
        @tms_description:
            This test will verify that package version can be incremented
            and the package will be successfully upgraded to the new version
            This test will verify the app under CS6 has being upgraded.
            pkg item exists under the clustered-service
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated

        """

        # RETRIEVE THE BASE CONFIGURATION DICTIONARY
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        # C-S UNDER TEST AND ITS UPDATED PROPERTY VALUES
        cs_name = 'CS6'

        updated_pkg_versions = {'EXTR-lsbwrapper6': {'version': '2.1.0-1'}}

        cs_url = self.get_cs_url(cs_name)

        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for updated_pkg in updated_pkg_versions:
            if updated_pkg[-length:] == cs_numeric:
                active_pkg = updated_pkg
        version = updated_pkg_versions[active_pkg]['version']
        major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            updated_service_name = \
                service_name + '-v0{0}'.format(major_version)
            remote_path = "/tmp/'{0}'".format(updated_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_07')
    def test_07_p_pkg_upgrade_1_node_parallel(self):
        """
        @tms_id: litpcds_3994_tc7
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package upgrade on 1 node parallel CS9
        @tms_description:
            This test will verify that package version can be incremented
            and the package will be successfully upgraded to the new version
            This test will verify the app under CS9 has being upgraded.
            pkg item exists under the clustered-service
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        # RETRIEVE THE BASE CONFIGURATION DICTIONARY
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        # C-S UNDER TEST AND ITS UPDATED PROPERTY VALUES
        cs_name = 'CS9'
        updated_pkg_versions = {'EXTR-lsbwrapper9': {'version': '2.1.0-1'}}

        cs_url = self.get_cs_url(cs_name)

        #######################################################################
        # ACT. 5. THIS SECTION CHECKS THAT THE UPDATED PACKAGE HAS BEEN
        # DEPLOYED TO THE NODES ASSIGNED TO THE C-S.
        #######################################################################

        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for updated_pkg in updated_pkg_versions:
            if updated_pkg[-length:] == cs_numeric:
                active_pkg = updated_pkg
        version = updated_pkg_versions[active_pkg]['version']
        major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            updated_service_name = \
                service_name + '-v0{0}'.format(major_version)
            remote_path = "/tmp/'{0}'".format(updated_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_08')
    def test_08_p_pkg_upgrade_1_node_parallel(self):
        """
        @tms_id: litpcds_3994_tc8
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package upgrade on 1 node parallel CS10
        @tms_description:
            This test will verify that package version can be incremented
            and the package will be successfully upgraded to the new version
            This test will verify the app under CS10 has being upgraded.
            pkg item exists under the clustered-service
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        # C-S UNDER TEST AND ITS UPDATED PROPERTY VALUES
        cs_name = 'CS10'

        updated_pkg_versions = {'EXTR-lsbwrapper10': {'version': '2.1.0-1'}}

        cs_url = self.get_cs_url(cs_name)

        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for updated_pkg in updated_pkg_versions:
            if updated_pkg[-length:] == cs_numeric:
                active_pkg = updated_pkg
        version = updated_pkg_versions[active_pkg]['version']
        major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            updated_service_name = \
                service_name + '-v0{0}'.format(major_version)
            remote_path = "/tmp/'{0}'".format(updated_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_10')
    def test_10_pkg_downgrade_plan1(self):
        """
        @tms_id: litpcds_3994_tc1_plan1_10
        @tms_requirements_id: LITPCDS-3994
        @tms_title: create and update package items version property
        @tms_description:
        This test generates and execute a plan which will
        update various cluster services.
        @tms_test_steps:
        @step: Copy RPMs to MS and import into REPO
        @result: rpms imported
        @step: update package items version property
        @result: items updated
        @step: create and run plan
        @result: plan executes successfully
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # ========================================================
        # This section will find all the items in the model that
        # are to be updated and make the changes
        # ========================================================

        # list of packages which will be be updated where the pkg
        # resides under the clustered-service and not the software item
        updated_pkg_versions = {'CS2': ['EXTR-lsbwrapper2'],
                                'CS1': ['EXTR-lsbwrapper1'],
                                'CS3': ['EXTR-lsbwrapper3',
                                        'EXTR-lsbwrapper23'],
                                'CS5': ['EXTR-lsbwrapper5'],
                                'CS9': ['EXTR-lsbwrapper9'],
                                }

        # list of packages which will be be updated where the pkg
        # resides under the software item and not under the clustered-service
        updated_parent_pkg_versions = {'CS1': ['EXTR-lsbwrapper4'],
                                       'CS6': ['EXTR-lsbwrapper6'],
                                       'CS10': ['EXTR-lsbwrapper10']}

        list_of_cs_pkg_upgrade = ["CS2", "CS1", "CS3",
                                  "CS5", "CS6", "CS9",
                                  "CS10"]

        # FIND THE software item URL
        soft_item_urls = self.find(self.management_server, '/software/',
                                  "collection-of-software-item")
        self.assertNotEqual(0, len(soft_item_urls))
        soft_item_url = soft_item_urls[0]

        # the version of the rpms being tested will all be version 2
        version_property = 'version=1.1.0-1'

        for cs_name in list_of_cs_pkg_upgrade:
            cs_url = self.get_cs_url(cs_name)
            # FIND THE PACKAGES COLLECTION URL BELOW THE C-S URL
            cs_pkgs_urls = self.find(self.management_server, cs_url,
                                     "software-item",
                                     rtn_type_children=False, find_refs=True)
            self.assertNotEqual(0, len(cs_pkgs_urls))
            cs_pkgs_url = cs_pkgs_urls[0]

            # COMPILE AND EXECUTE THE COMMAND TO UPDATE THE PACKAGE VERSION
            # PROPERTY OF THE VCS C-S UNDER TEST
            if cs_name in updated_pkg_versions:
                for pkg in updated_pkg_versions[cs_name]:
                    url = cs_pkgs_url + '/' + pkg
                    cmd = self.cli.get_update_cmd(url, version_property)
                    stdout, stderr, returnc = \
                                  self.run_command(self.management_server, cmd)
                    self.assertEqual(0, returnc)
                    self.assertEqual([], stderr)
                    self.assertEqual([], stdout)

            if cs_name in updated_parent_pkg_versions:
                for pkg in updated_parent_pkg_versions[cs_name]:
                    url = soft_item_url + '/' + pkg
                    cmd = self.cli.get_update_cmd(url, version_property)
                    stdout, stderr, returnc = \
                                  self.run_command(self.management_server, cmd)
                    self.assertEqual(0, returnc)
                    self.assertEqual([], stderr)
                    self.assertEqual([], stdout)

        # ===================================================
        # This section will create the plan and verify that
        # upgrade of the rpms happens when the node is locked
        # ===================================================

        self.execute_cli_createplan_cmd(self.management_server)
        plan_stdout, _, _ = \
            self.execute_cli_showplan_cmd(self.management_server)

        parsed_plan = self.cli.parse_plan_output(plan_stdout)

        # Generate the expected description of the locking and unlocking tasks
        expected_task = {}
        for node in self.list_managed_nodes:
            url = self.get_node_url_from_filename(self.management_server, node)
            node_name = url.split('/')[-1]
            expected_task[node_name] = {'lock': [url,
                                                 'Lock VCS on node "' + \
                                                 node_name + '"'],
                              'unlock': [url, 'Unlock VCS on node ' + \
                                                node_name]}

        # 3 phases per node, lock, upgrade packages, unlock
        # 1st phase has to be lock, last phase has to be unlock
        # All these CS are either 2 node failover, 1 node parallel
        # or 2 node parallel
        # 2 nodes * 3 phases = 6 phases
        # implies 1st phase is lock of a node
        #         3rd phase is unlock of aid node
        #         4th phase is lock of other node
        #         6th phase is unlock of other node

        # First phase is unlock
        self.assertTrue(re.search('Lock VCS on node',
                                  parsed_plan[1][1]['DESC'][-1]))
        first_node_name = parsed_plan[1][1]['DESC'][0].split('/')[-1]
        # 3rd phase is corresponding unlock of phase 2
        self.assertTrue(expected_task[first_node_name]['unlock'],
                        parsed_plan[3][1]['DESC'])

        # 4th phase is unlock
        self.assertTrue(re.search('Unlock VCS on node',
                        parsed_plan[parsed_plan.keys()[-1]][1]['DESC'][-1]))
        second_node_name = parsed_plan[6][1]['DESC'][0].split('/')[-1]
        # 6th phase is corresponding unlock of phase 4
        self.assertTrue(expected_task[second_node_name]['unlock'],
                        parsed_plan[4][1]['DESC'])

        # =====================================================
        # Execute the plan
        # =====================================================
        plan_timeout_mins = 20
        # EXECUTE THE PLAN TO DEPLOY THE UPDATED PACKAGE
        self.execute_cli_runplan_cmd(self.management_server)

        # WAIT FOR THE PLAN TO COMPLETE - ENSURE THE PLAN COMPLETES
        # SUCCESSFULLY WITHIN THE SPECIFIED TIME BOX
        self.assertTrue(self.wait_for_plan_state(
            self.management_server,
            test_constants.PLAN_COMPLETE,
            plan_timeout_mins
        ))

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_11')
    def test_11_p_pkg_downgrade_2_node_failover(self):
        """
        @tms_id: litpcds_3994_tc11
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package downgrade on 2 node failover CS2
        @tms_description:
            This test will verify that package version can be incremented
            and the package will be successfully upgraded to the new version
            This test will verify the app under CS2 has being upgraded.
            pkg item exists under the clustered-service
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        # RETRIEVE THE BASE CONFIGURATION DICTIONARY
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        # C-S UNDER TEST AND ITS UPDATED PROPERTY VALUES
        cs_name = 'CS2'
        original_pkg_versions = {'EXTR-lsbwrapper2': {'version': '2.1.0-1'}}
        updated_pkg_versions = {'EXTR-lsbwrapper2': {'version': '1.1.0-1'}}

        cs_url = self.get_cs_url(cs_name)

        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for original_pkg in original_pkg_versions:
            if original_pkg[-length:] == cs_numeric:
                active_pkg = original_pkg
        version = original_pkg_versions[active_pkg]['version']
        major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            old_service_name = \
                service_name + '-v0{0}'.format(major_version)
            remote_path = "/tmp/'{0}'".format(old_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_12')
    def test_12_p_pkg_downgrade_2_node_failover(self):
        """
        @tms_id: litpcds_3994_tc12
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package downgrade on 2 node failover CS1
        @tms_description:
            This test will verify that package version can be decremented
            and the package will be successfully downgraded to the old version
        @tms_test_steps:
        @step: updated clustered-service items version property on CS1
        @result: items updated
        @step: create and run plan
        @result: item executes successfully
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition:
            test_03_p_pkg_upgrade_2 node_failover and
            test_02_p_pkg_upgrade_2 node_failover
            have been executed successfully
        @tms_execution_type: Automated
        """

        #######################################################################
        # ACT. 0 THIS SECTION OF THE TEST ACCOMPLISHES THE TEST PREREQUISITES
        #######################################################################

        # RETRIEVE THE BASE CONFIGURATION DICTIONARY
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        #######################################################################
        # ACT. 1. THIS SECTION OF THE TEST UPDATES THE PREVIOUSLY DEPLOYED C-S
        #######################################################################

        # MAXIMUM TIME ALLOWED FOR A PLAN TO RUN TO COMPLETION PRIOR TO AN
        # EXCEPTION BEING RAISED AND THE TEST FAILING.
        plan_timeout_mins = 20

        # C-S UNDER TEST AND ITS UPDATED PROPERTY VALUES
        cs_name = 'CS1'
        original_pkg_versions = {
            'EXTR-lsbwrapper1': {'version': '3.1.0-1'},
            'EXTR-lsbwrapper4': {'version': '3.1.0-1'},
        }
        updated_pkg_versions = {
            'EXTR-lsbwrapper1': {'version': '2.1.0-1'},
            'EXTR-lsbwrapper4': {'version': '2.1.0-1'},
        }

        cs_url = self.get_cs_url(cs_name)

        # FIND THE PACKAGES COLLECTION URL BELOW THE C-S URL
        cs_pkgs_urls = self.find(self.management_server, cs_url,
                                "software-item",
                                rtn_type_children=False, find_refs=True)
        self.assertNotEqual(0, len(cs_pkgs_urls))
        cs_pkgs_url = cs_pkgs_urls[0]

        # COMPILE AND EXECUTE THE COMMAND TO UPDATE THE PACKAGE VERSION
        # PROPERTY OF THE VCS C-S UNDER TEST
        for pkg in updated_pkg_versions.keys():
            url = cs_pkgs_url + '/' + pkg
            properties = \
                'version={0}'.format(updated_pkg_versions[pkg]['version'])
            cmd = \
                self.cli.get_update_cmd(url, properties)
            stdout, stderr, returnc = \
                self.run_command(self.management_server, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertEqual([], stdout)

        #######################################################################
        # ACT. 2. THIS SECTION CREATES THE UPDATED CONFIGURATION PLAN
        #######################################################################

        # CREATE A PLAN TO DEPLOY THE UPDATED PACKAGE OBJECT
        self.execute_cli_createplan_cmd(self.management_server)

        #######################################################################
        # ACT. 3. THIS SECTION CHECKS THE LAYOUT OF THE NODE LOCK/UNLOCK TASKS
        #######################################################################

        self.check_plan_phases(updated_pkg_versions,
            self.managed_nodes_hostnames)

        #######################################################################
        # ACT. 4. THIS SECTION DEPLOYS THE UPDATED C-S PKG CONFIGURATION
        #######################################################################

        # EXECUTE THE PLAN TO DEPLOY THE UPDATED PACKAGE
        self.execute_cli_runplan_cmd(self.management_server)

        # WAIT FOR THE PLAN TO COMPLETE - ENSURE THE PLAN COMPLETES
        # SUCCESSFULLY WITHIN THE SPECIFIED TIME BOX
        self.assertTrue(self.wait_for_plan_state(
            self.management_server,
            test_constants.PLAN_COMPLETE,
            plan_timeout_mins
        ))
        #######################################################################
        # ACT. 5. THIS SECTION CHECKS THAT THE UPDATED PACKAGE HAS BEEN
        # DEPLOYED TO THE NODES ASSIGNED TO THE C-S.
        #######################################################################

        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for updated_pkg in updated_pkg_versions:
            if updated_pkg[-length:] == cs_numeric:
                active_pkg = updated_pkg
        version = updated_pkg_versions[active_pkg]['version']
        new_major_version = version.split('.')[0]

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for original_pkg in original_pkg_versions:
            if original_pkg[-length:] == cs_numeric:
                active_pkg = original_pkg
        version = original_pkg_versions[active_pkg]['version']
        old_major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            new_service_name = \
                service_name + '-v0{0}'.format(new_major_version)
            remote_path = "/tmp/'{0}'".format(new_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            old_service_name = \
                service_name + '-v0{0}'.format(old_major_version)
            remote_path = "/tmp/'{0}'".format(old_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_13')
    def test_13_p_pkg_downgrade_2_node_failover(self):
        """
        @tms_id: litpcds_3994_tc13
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package downgrade on 2 node failover CS1
        @tms_description:
            This test will verify that package version can be decremented
            and the package will be successfully upgraded to the new version
            This test will verify the app under CS1 has being upgraded.
            pkg item exists under the clustered-service
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated

        """
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        cs_name = 'CS1'
        original_pkg_versions = {
            'EXTR-lsbwrapper1': {'version': '2.1.0-1'},
            'EXTR-lsbwrapper4': {'version': '2.1.0-1'},
        }
        updated_pkg_versions = {
            'EXTR-lsbwrapper1': {'version': '1.1.0-1'},
            'EXTR-lsbwrapper4': {'version': '1.1.0-1'},
        }

        cs_url = self.get_cs_url(cs_name)

        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for original_pkg in original_pkg_versions:
            if original_pkg[-length:] == cs_numeric:
                active_pkg = original_pkg
        version = original_pkg_versions[active_pkg]['version']
        old_major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            old_service_name = \
                service_name + '-v0{0}'.format(old_major_version)
            remote_path = "/tmp/'{0}'".format(old_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_14')
    def test_14_p_pkg_downgrade_2_node_parallel(self):
        """
        @tms_id: litpcds_3994_tc14
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package downgrade on 2 node parallel CS5
        @tms_description:
            This test will verify that package version can be decremented
            and the package will be successfully upgraded to the new version
            This test will verify the app under CS5 has being upgraded.
            pkg item exists under the clustered-service
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        # RETRIEVE THE BASE CONFIGURATION DICTIONARY
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        # C-S UNDER TEST AND ITS UPDATED PROPERTY VALUES
        cs_name = 'CS5'
        original_pkg_versions = {
            'EXTR-lsbwrapper5': {'version': '2.1.0-1'},
        }
        updated_pkg_versions = {
            'EXTR-lsbwrapper5': {'version': '1.1.0-1'},
        }

        cs_url = self.get_cs_url(cs_name)

        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for original_pkg in original_pkg_versions:
            if original_pkg[-length:] == cs_numeric:
                active_pkg = original_pkg
        version = original_pkg_versions[active_pkg]['version']
        old_major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            old_service_name = \
                service_name + '-v0{0}'.format(old_major_version)
            remote_path = "/tmp/'{0}'".format(old_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_15')
    def test_15_p_pkg_downgrade_2_node_parallel(self):
        """
        @tms_id: litpcds_3994_tc15
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package downgrade on 2 node parallel CS6
        @tms_description:
            This test will verify that package version can be decremented
            and the package will be successfully upgraded to the new version
            This test will verify the app under CS6 has being upgraded.
            pkg item exists under the clustered-service
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        conf = self.vcs.generate_plan_conf(self.traffic_networks)
        cs_name = 'CS6'

        original_pkg_versions = {
            'EXTR-lsbwrapper6': {'version': '2.1.0-1'},
        }
        updated_pkg_versions = {
            'EXTR-lsbwrapper6': {'version': '1.1.0-1'},
        }

        cs_url = self.get_cs_url(cs_name)
        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for original_pkg in original_pkg_versions:
            if original_pkg[-length:] == cs_numeric:
                active_pkg = original_pkg
        version = original_pkg_versions[active_pkg]['version']
        old_major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            old_service_name = \
                service_name + '-v0{0}'.format(old_major_version)
            remote_path = "/tmp/'{0}'".format(old_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_16')
    def test_16_p_pkg_downgrade_1_node_parallel(self):
        """
        @tms_id: litpcds_3994_tc16
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package downgrade on 1 node parallel CS9
        @tms_description:
            This test will verify that package version can be decremented
            and the package will be successfully upgraded to the new version
            This test will verify the app under CS9 has being upgraded.
            pkg item exists under the clustered-service
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        cs_name = 'CS9'
        original_pkg_versions = {
            'EXTR-lsbwrapper9': {'version': '2.1.0-1'},
        }
        updated_pkg_versions = {
            'EXTR-lsbwrapper9': {'version': '1.1.0-1'},
        }

        cs_url = self.get_cs_url(cs_name)

        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for original_pkg in original_pkg_versions:
            if original_pkg[-length:] == cs_numeric:
                active_pkg = original_pkg
        version = original_pkg_versions[active_pkg]['version']
        old_major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            old_service_name = \
                service_name + '-v0{0}'.format(old_major_version)
            remote_path = "/tmp/'{0}'".format(old_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_17')
    def test_17_p_pkg_downgrade_1_node_parallel(self):
        """
        @tms_id: litpcds_3994_tc17
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package downgrade on 1 node parallel CS10
        @tms_description:
            This test will verify that package version can be decremented
            and the package will be successfully upgraded to the new version
            This test will verify the app under CS10 has being upgraded.
            pkg item exists under the clustered-service
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        cs_name = 'CS10'

        original_pkg_versions = {
            'EXTR-lsbwrapper10': {'version': '2.1.0-1'},
        }
        updated_pkg_versions = {
            'EXTR-lsbwrapper10': {'version': '1.1.0-1'},
        }

        cs_url = self.get_cs_url(cs_name)

        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for original_pkg in original_pkg_versions:
            if original_pkg[-length:] == cs_numeric:
                active_pkg = original_pkg
        version = original_pkg_versions[active_pkg]['version']
        old_major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            old_service_name = \
                service_name + '-v0{0}'.format(old_major_version)
            remote_path = "/tmp/'{0}'".format(old_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_18')
    def test_20_p_pkg_upgrade_2_node_parallel(self):
        """
        @tms_id: litpcds_3994_tc20
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package upgrade on 2 node parallel CS7
        @tms_description:
            This test will verify that package for CS7 has been upgraded
            despite no version been applied during original installation
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Upgraded package is installed on both nodes
        @result: Upgrade LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        # C-S UNDER TEST AND ITS UPDATED PROPERTY VALUES
        cs_name = 'CS7'
        updated_pkg_versions = {'EXTR-lsbwrapper7': {'version': '2.1.0-1'}}

        cs_url = self.get_cs_url(cs_name)

        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for updated_pkg in updated_pkg_versions:
            if updated_pkg[-length:] == cs_numeric:
                active_pkg = updated_pkg
        version = updated_pkg_versions[active_pkg]['version']
        major_version = version.split('.')[0]

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            old_service_name = \
                service_name + '-v0{0}'.format(major_version)
            remote_path = "/tmp/'{0}'".format(old_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

    @attr('all', 'non-revert', 'kgb-other', 'story3994', 'story3994_test_21')
    def test_21_p_pkg_upgrade_2_node_parallel(self):
        """
        @tms_id: litpcds_3994_tc21
        @tms_requirements_id: LITPCDS-3994
        @tms_title: verify package upgrade on 2 node parallel CS8
        @tms_description:
            This test will verify that package version can be decremented
            and the package will be successfully downgraded to the old version
        @tms_test_steps:
        @step: execute hagrp -state on service groups
        @result: correct information is returned
        @result: Downgraded package is installed on both nodes
        @result: Downgraded LSB service is running
        @result: Old LSB service is not running
        @tms_test_precondition:version is not defined in the clustered-service
        @tms_execution_type: Automated
        """

        conf = self.vcs.generate_plan_conf(self.traffic_networks)

        # C-S UNDER TEST AND ITS UPDATED PROPERTY VALUES
        cs_name = 'CS8'
        updated_pkg_versions = {'EXTR-lsbwrapper8': {'version': '3.1.0-1'}}

        cs_url = self.get_cs_url(cs_name)

        # ASCERTAIN ON WHICH NODES THE C-S IS DEPLOYED BY RETRIEVING THE
        # NODE_LIST PROPERTY VALUE OF THE C-S URL
        cs_node_list_str = self.get_props_from_url(self.management_server,
            cs_url, 'node_list')
        self.assertNotEqual(None, cs_node_list_str)
        cs_node_list = str(cs_node_list_str).split(',')
        node_filenames_list = self.get_cs_nodes(cs_node_list)

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)
        pkg_names.sort()

        # CHECK THAT THE UPDATED PACKAGE(S) (IS|ARE) INSTALLED ON THE NODES.
        for node_filename in node_filenames_list:
            cmd = self.rh_os.check_pkg_installed(pkg_names)
            stdout, stderr, returnc = \
            self.run_command(node_filename, cmd)
            self.assertEqual(0, returnc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            self.assertNotEqual(pkg_names, stdout.sort())

        #######################################################################
        # ACT. 6. THIS SECTION CHECKS THAT THE PID FILE OF THE UPDATED SERVICE
        # HAS BEEN DEPLOYED ON THE ACTIVE NODE, AND THAT THE PID FILE OF THE
        # PREVIOUS SERVICE HAS BEEN REMOVED.
        #######################################################################

        # ENSURE THAT THE UPDATED SERVICE HAS BEEN DEPLOYED - ACCOMPLISHED BY
        # CHECKING THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        # WILL NEED TO ASCERTAIN THE NODES ON WHICH THE SERVICE IS ACTIVE BY
        # QUERYING THE VCS CONSOLE. THEN MAPPING THE NODE HOSTNAME FOUND
        # IN THE VCS CONSOLE TO THE NODE CONNECTION FILENAMES.
        cs_active_node_dict = self.compile_cs_active_node_dict(conf)
        cs_active_node_list = cs_active_node_dict[cs_name]
        node_mapping_dict = self.map_node_host_to_node_file()

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            active_node_filenames.append(node_mapping_dict[cs_active_node])

        # FIND THE SERVICE NAME OF THE PREVIOUSLY DEPLOYED SERVICE
        # THE PID FILE IS THE SAME NAME
        application = conf['app_per_cs'][cs_name]
        service_name = conf["lsb_app_properties"][application]['service_name']

        # FIND OUT WHICH CS IS UNDER TEST SO AS TO ASCERTAIN THE PKG
        # THAT CONTAINS ITS LSB SERVICE
        cs_numeric = cs_name[2:]
        length = len(cs_numeric)
        active_pkg = ""
        for updated_pkg in updated_pkg_versions:
            if updated_pkg[-length:] == cs_numeric:
                active_pkg = updated_pkg
        version = updated_pkg_versions[active_pkg]['version']
        major_version = version.split('.')[0]

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            remote_path = "/tmp/'{0}'".format(service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertFalse(res)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        # CHECK THAT THE OLD  PID FILE HAS BEEN REMOVED TO /tmp
        for active_node in active_node_filenames:
            old_service_name = \
                service_name + '-v0{0}'.format(major_version)
            remote_path = "/tmp/'{0}'".format(old_service_name)
            res = self.remote_path_exists(active_node, remote_path)
            self.assertTrue(res)

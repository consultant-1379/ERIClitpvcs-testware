"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     September 2014
@author:    Danny McDonald
@summary:   Integration tests for testing VCS scenarios
            Agile:
"""

from litp_cli_utils import CLIUtils
from litp_generic_test import GenericTest, attr
from redhat_cmd_utils import RHCmdUtils
from vcs_utils import VCSUtils
import test_constants
import os
import re


class Story5768(GenericTest):
    """
    LITPCDS-5768
    As a LITP Developer I want to use the service-base item with the VCS plug
    in so that there is a consistent approach to managing LSB services
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
        super(Story5768, self).setUp()

        self.rh_os = RHCmdUtils()
        self.management_server = self.get_management_node_filename()
        self.list_managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.list_managed_nodes[0]

        self.primary_node_url = self.get_node_url_from_filename(
            self.management_server, self.primary_node)

        self.cli = CLIUtils()
        self.vcs = VCSUtils()
        self.traffic_networks = ["traffic1", "traffic2"]
        # Location where RPMs to be used are stored
        self.rpm_src_dir = \
            os.path.dirname(os.path.realpath(__file__)) + \
            "/test_lsb_rpms/"

        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.management_server,
                                    "/deployments", "vcs-cluster")[-1]
        self.cluster_name = self.vcs_cluster_url.split("/")[-1]

        # Repo where rpms will be installed
        self.repo_dir_3pp = test_constants.PP_PKG_REPO_DIR

        # Get urls of all nodes in the vcs-cluster
        self.vcs_nodes_urls = self.find(
            self.management_server,
            self.vcs_cluster_url,
            "node"
        )

        self.node_info = {}
        # get all filenames of nodes in the vcs cluster
        for node in self.vcs_nodes_urls:
            filename = self.get_node_filename_from_url(
                self.management_server,
                node)
            hostname = self.get_node_att(filename, "hostname")

            self.node_info[filename] = {'hostname': hostname,
                                        'url': node}

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story5768, self).tearDown()

    def copy_and_import_dummy_lsb(self, list_of_lsb_rpms):
        """
        Function to copy dummy lsb serviced to the node and add them
        to the repo using the litp import command

        Args:
            list_of_lsb_rpms (dict): List of rpms to be added to the
                                     3pp repo on the node
        """
        # Location where RPMs to be used are stored
        rpm_src_dir = \
            os.path.dirname(os.path.realpath(__file__)) + \
            "/test_lsb_rpms/"

        # Copy RPMs to Management Server
        filelist = []
        for rpm in list_of_lsb_rpms:
            filelist.append(self.get_filelist_dict(rpm_src_dir + rpm,
                                                   "/tmp/"))

        self.copy_filelist_to(self.management_server, filelist,
                              add_to_cleanup=False, root_copy=True)

        # Use LITP import to add to repo for each RPM
        for rpm in list_of_lsb_rpms:
            self.execute_cli_import_cmd(
                self.management_server,
                '/tmp/' + rpm,
                self.repo_dir_3pp)

    def execute_cluster_service_cli(self, conf, cs_name, cli_data):
        """
        Function to generate and execute the CLI which will create
        clustered-services

        Args:
            conf (dictionary): Configuration for clustered-service
            cs_name (str): clustered service name, key to conf dictionary
            cli_data (str): All the CLI data required to create the CS's
        """
        nr_of_nodes = int(conf['params_per_cs'][cs_name]['active']) + \
                          int(conf['params_per_cs'][cs_name]['standby'])

        node_vnames = []
        node_cnt = 0
        for node in self.node_info:
            node_url = self.node_info[node]['url']
            if node_cnt < nr_of_nodes:
                node_vnames.append(node_url.split('/')[-1])
                node_cnt = node_cnt + 1

        # Create Clustered-Service in the model
        cs_options = cli_data['cs']['options'] + \
                     " node_list='{0}'".format(",".join(node_vnames))
        self.execute_cli_create_cmd(self.management_server,
                                    cli_data['cs']['url'],
                                    cli_data['cs']['class_type'],
                                    cs_options,
                                    add_to_cleanup=False)

        # Create lsb apps in the model
        self.execute_cli_create_cmd(self.management_server,
                                    cli_data['apps']['url'],
                                    cli_data['apps']['class_type'],
                                    cli_data['apps']['options'],
                                    add_to_cleanup=False)

        # create inherit to the service
        self.execute_cli_inherit_cmd(self.management_server,
                                     cli_data['apps']['app_url_in_cluster'],
                                     cli_data['apps']['url'],
                                     add_to_cleanup=False)

        # Create all IPs associated with the lsb-app
        for ip_data in cli_data['ips']:
            self.execute_cli_create_cmd(self.management_server,
                                        ip_data['url'],
                                        ip_data['class_type'],
                                        ip_data['options'],
                                        add_to_cleanup=False)

        # Create all packages associated with lsb-app
        for pkg_data in cli_data['pkgs']:
            self.execute_cli_create_cmd(self.management_server,
                                        pkg_data['url'],
                                        pkg_data['class_type'],
                                        pkg_data['options'],
                                        add_to_cleanup=False)

        # Create pkgs under the lsb-app
        for pkg_link_data in cli_data['pkg_links']:
            self.execute_cli_inherit_cmd(self.management_server,
                                        pkg_link_data['child_url'],
                                        pkg_link_data['parent_url'],
                                        add_to_cleanup=False)

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
                self.check_hostname_cs_online(self.list_managed_nodes,
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

    def check_plan_phases(self, updated_pkg_versions, node_hostnames):
        """
        Check the plan phases layout to ensure that a node lock occurs
        prior to the package installation and that a node unlock occurs
        following the package installation.
        """

        for pkg in updated_pkg_versions.keys():
            for node_hostname in node_hostnames:
                find_task = 'Update package "{0}" on node "{1}"'.format(
                    pkg, node_hostname)

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

        # Get urls of all clustered services
        cs_urls = self.find(self.management_server,
            self.vcs_cluster_url, "vcs-clustered-service")

        # FROM THE LIST FOUND RETRIEVE THE URL OF THE C-S UNDER TEST
        length = len(cs_name)
        for url in cs_urls:
            if url[-length:] == cs_name:
                return url
        return None

    @attr('all', 'non-revert', 'kgb-other')
    def test_02_p_pkg_upgrade_2_node_parallel(self):
        """
        @tms_id: litpcds_5768_tc02
        @tms_requirements_id: LITPCDS-5768
        @tms_title: Verify successful package upgrade
        @tms_description: This test will verify that package version can be
        incremented and the package will be successfully upgraded to the new
        version
        @tms_test_steps:
        @step: Generate config dictionary
        @result: Dictionary created
        @step: Increment package version of package under CS28
        @result: Package version incremented
        @step: Compile list of updated package names for which to search on the
        nodes on which CS28 is deployed.
        @result: List compiled
        @step: Check that the updated package(s) are deployed on the active
        nodes.
        @result: The check completes with no errors output.
        @result: Above check is successful, service has been deployed under
        '/tmp'
        @step: Check that the previous service has been undeployed.
        @result: The service is not present under '/tmp'
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        # RETRIEVE THE BASE CONFIGURATION DICTIONARY
        conf = self.vcs.generate_plan_conf_service()

        cs_name = 'CS28'
        updated_pkg_versions = {'EXTR-lsbwrapper28': {'version': '2.1.0-1'}}

        #######################################################################
        # ACT. 5. THIS SECTION CHECKS THAT THE UPDATED PACKAGE HAS BEEN
        # DEPLOYED TO THE NODES ASSIGNED TO THE C-S.
        #######################################################################

        node_filenames_list = self.node_info.keys()

        # COMPILE A LIST OF THE UPDATED PACKAGE NAMES FOR WHICH TO SEARCH
        # ON THE NODES ON WHICH THE C-S IS DEPLOYED
        pkg_names = []
        for pkg in updated_pkg_versions.keys():
            pkg_name = \
            pkg + '-{0}'.format(updated_pkg_versions[pkg]['version'])
            pkg_names.append(pkg_name)

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

        # FIND THE CONNECTION FILENAMES OF THE NODES ON WHICH THE C-S IS ACTIVE
        active_node_filenames = []
        for cs_active_node in cs_active_node_list:
            for fname, node_info in self.node_info.iteritems():
                if node_info['hostname'] == cs_active_node:
                    active_node_filenames.append(fname)
                    break

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
            if updated_pkg[- length:] == cs_numeric:
                active_pkg = updated_pkg
        version = updated_pkg_versions[active_pkg]['version']
        major_version = version.split('.')[0]

        # CHECK THAT THE UPDATED PID FILE HAS BEEN DEPLOYED TO /tmp
        for active_node in active_node_filenames:
            updated_service_name = \
                service_name + '-v0{0}'.format(major_version)
            cmd = '[ -f /tmp/{0} ]'.format(updated_service_name)
            _, _, returnc = self.run_command(active_node, cmd)

            self.assertEqual(0, returnc)

        # ENSURE THAT THE PREVIOUS SERVICE HAS BEEN UNDEPLOYED - ACCOMPLISHED
        # BY CHECKING THAT THE PREVIOUS PID FILE HAS BEEN REMOVED FROM /tmp
        for active_node in active_node_filenames:
            cmd = '[ -f /tmp/{0} ]'.format(service_name)
            _, _, returnc = self.run_command(active_node, cmd)
            self.assertNotEqual(0, returnc)

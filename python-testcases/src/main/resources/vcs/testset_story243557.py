"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     March 2018
@author:    Paul Chambers
@summary:   Integration tests for testing VCS scenarios
            Agile: TORF-239618
"""

from litp_generic_test import GenericTest, attr
from redhat_cmd_utils import RHCmdUtils
from vcs_utils import VCSUtils
import test_constants
import os
import time


class Story243557(GenericTest):
    """
    TORF-243557
    LITP Fails when you try to Upgrade out if SG is in status Frozen.
    """

    def setUp(self):
        """
        Runs before every single test
        """
        # 1. Call super class setup
        super(Story243557, self).setUp()

        self.rh_os = RHCmdUtils()
        self.management_server = self.get_management_node_filename()
        self.list_managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.list_managed_nodes[0]
        self.primary_node_url = self.get_node_url_from_filename(
        self.management_server, self.primary_node)
        self.vcs = VCSUtils()
        self.traffic_networks = ["traffic1", "traffic2"]
        # Location where RPMs to be used are stored
        self.rpm_src_dir = \
            os.path.dirname(os.path.realpath(__file__)) + \
            "/test_lsb_rpms/"

        # Repo where rpms will be installed
        self.repo_dir_3pp = test_constants.PP_PKG_REPO_DIR
        self.vcs_cluster_url = self.find(self.management_server,
                                         "/deployments", "vcs-cluster")[-1]

    def tearDown(self):
        """
        Runs after every single test
        """
        super(Story243557, self).tearDown()

    def generate_execute_cs_cli(self, conf, vcs_cluster_url, cs_name,
                                app_class="lsb-runtime", node_ordering=False):
        """
        Description:
            This function will generate and execute the CLI to create
            a clustered services

        Args:
            conf (dict): configuration details for clustered-services

            vcs_cluster_url (str): Model url of vcs cluster item

            cs_name (str): clustered-service name

        Kwargs:
            app_class (str): class name of the application item.
                             lsb-runtime is the default value

            node_ordering (bool): Flag on whether to order the
                                  node list according to how they are
                                  defined in the config.
                                  Default value is False
        """
        # Get CLI commands
        cli_data = self.vcs.generate_cli_commands(vcs_cluster_url,
                                                     conf, cs_name,
                                                     app_class)

        nodes_urls = self.find(self.management_server,
                               vcs_cluster_url,
                               "node")
        node_cnt = 0
        node_vnames = []
        for node_url in nodes_urls:
            node_cnt += 1
            # Retrieve the nodes hostname - key used to link
            hostname = self.get_props_from_url(self.management_server,
                                               node_url,
                                               'hostname')
            self.assertNotEqual(None, hostname)

            nr_of_nodes = int(conf['params_per_cs'][cs_name]['active']) + \
                          int(conf['params_per_cs'][cs_name]['standby'])

            # Add the node to the cluster
            if node_cnt <= nr_of_nodes:
                node_vnames.append(node_url.split('/')[-1])

        if node_ordering:
            # order the node list according to how they are
            # define in the config
            node_vnames = self.vcs.order_node_list(node_vnames, conf, cs_name)
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

        # CREATE THE HA SERVICE CONFIG ITEM
        if len(cli_data['ha_service_config'].keys()) > 0:
            self.execute_cli_create_cmd(self.management_server,
                                cli_data['ha_service_config']['url'],
                                cli_data['ha_service_config']['class_type'],
                                cli_data['ha_service_config']['options'],
                                add_to_cleanup=False)

        # Create pkgs under the lsb-app
        for pkg_link_data in cli_data['pkg_links']:
            self.execute_cli_inherit_cmd(self.management_server,
                                         pkg_link_data['child_url'],
                                         pkg_link_data['parent_url'],
                                         add_to_cleanup=False)

        # create inherit to the service
        if app_class in ["service", "vm-service"]:
            self.execute_cli_inherit_cmd(self.management_server,
                                         cli_data['apps']
                                         ['app_url_in_cluster'],
                                         cli_data['apps']['url'],
                                         add_to_cleanup=False)

    @staticmethod
    def generate_plan_conf_service(traffic_networks):
        """
        Description:
            Returns a dictionary which defines the required VCS configuration.
            The configuration defined in this dictionary will be used to:

            1. Generate CLI commands to create a VCS configuration.

            2. Verify that the VCS configuration has been deployed correctly.

            3. Used as a baseline for other tests such as failover.

        Args:
            traffic_networks (list): List of the traffic networks.

        Returns:
            dict. Dictionary which defines VCS configuration.

        """

        conf = {}

        # ===================================================================
        # List of VCS clustered services names and associated run-time names.
        # Only 1 runtime per clustered service is currently allowed.
        # ===================================================================
        conf['app_per_cs'] = {
            'CS41': 'APP41',
            'CS42': 'APP42',
            'CS43': 'APP43',
            'CS44': 'APP44',
            'CS45': 'APP45',
        }

        # ======================================================
        # List of nodes defined per vcs-clustered-service.
        # Assumption is that at most a 2 node vcs-cluster exists
        # which allows either 1 or 2 node clustered-service.
        # ======================================================
        conf['nodes_per_cs'] = {
            'CS41': [1],
            'CS42': [1, 2],
            'CS43': [1],
            'CS44': [1, 2],
            'CS45': [1, 2],
        }

        # ================================
        # Parameters per clustered-service
        # ================================
        conf['params_per_cs'] = {
            'CS41': {'active': 1, 'standby': 0, 'online_timeout': 180},
            'CS42': {'active': 1, 'standby': 1, 'online_timeout': 180},
            'CS43': {'active': 1, 'standby': 0, 'online_timeout': 180},
            'CS44': {'active': 1, 'standby': 1, 'online_timeout': 180},
            'CS45': {'active': 2, 'standby': 0, 'online_timeout': 180},
        }

        # =========================================================
        # List of IP resources per run-time in a clustered service
        # =======================================================
        conf['ip_per_app'] = {
            'APP41': ['172.16.100.25'],
            'APP42': ['172.16.200.27'],
            'APP43': ['172.16.100.26'],
            'APP44': ['172.16.200.28'],
            'APP45': ['172.16.100.28',
                     '172.16.100.29',
                     '172.16.200.29',
                     '172.16.200.30'],
        }

        ######################################################
        # List of IP addresses and their associated networks #
        # as per                                             #
        #   https://confluence-oss.lmera.ericsson.se/        #
        #           display/ELITP/2.1.6+Test+Setup           #
        ######################################################
        nets = traffic_networks
        conf["network_per_ip"] = {
            '172.16.100.25': nets[0],
            '172.16.100.26': nets[0],
            '172.16.100.27': nets[0],
            '172.16.100.28': nets[0],
            '172.16.100.29': nets[0],
            '172.16.200.27': nets[1],
            '172.16.200.28': nets[1],
            '172.16.200.29': nets[1],
            '172.16.200.30': nets[1],
            '172.16.200.31': nets[1],
        }

        # ==============================================
        # List of packages that will exist per run-time
        # ==============================================
        conf["pkg_per_app"] = {
            "APP41": {'EXTR-lsbwrapper41': {'version': '1.1.0-1'}},
            "APP42": {'EXTR-lsbwrapper42': {'version': '1.1.0-1'}},
            "APP43": {'EXTR-lsbwrapper43': {'version': '1.1.0-1'}},
            "APP44": {'EXTR-lsbwrapper44': {'version': '1.1.0-1'}},
            "APP45": {'EXTR-lsbwrapper45': {'version': '1.1.0-1'}},
        }

        # ==================================
        # List of properties per lsb runtime
        # ==================================

        conf["lsb_app_properties"] = {
            "APP41": {
                'service_name': 'test-lsb-41',
                'start_command': '/usr/bin/systemctl start test-lsb-41',
                'stop_command': '/usr/bin/systemctl stop test-lsb-41',
                'status_command': '/usr/share/litp/vcs_lsb_status'\
                                    ' test-lsb-41 status',
                'cleanup_command': '/bin/touch /tmp/test-lsb-41.cleanup'},
            "APP42": {
                'service_name': 'test-lsb-42'},
            "APP43": {
                'service_name': 'test-lsb-43',
                'start_command': '/usr/bin/systemctl start test-lsb-43',
                'stop_command': '/usr/bin/systemctl stop test-lsb-43',
                'status_command': '/usr/share/litp/vcs_lsb_status'\
                                    ' test-lsb-43 status',
                'cleanup_command': '/bin/touch /tmp/test-lsb-43.cleanup'},
            "APP44": {
                'service_name': 'test-lsb-44',
                'start_command': '/usr/bin/systemctl start test-lsb-44',
                'stop_command': '/usr/bin/systemctl stop test-lsb-44',
                'status_command': '/usr/share/litp/vcs_lsb_status'\
                                    ' test-lsb-44 status',
                'cleanup_command': '/bin/touch /tmp/test-lsb-44.cleanup'},
            "APP45": {
                'service_name': 'test-lsb-45',
                'start_command': '/usr/bin/systemctl start test-lsb-45',
                'stop_command': '/usr/bin/systemctl stop test-lsb-45',
                'status_command': '/usr/share/litp/vcs_lsb_status'\
                                    ' test-lsb-45 status',
                'cleanup_command': '/bin/touch /tmp/test-lsb-45.cleanup'}
        }

        return conf

    def wait_for_hagrp_to_respond_to_queries(self, node, cs_group_name,
                                             attribute):
        """
        Description:
            Waits until the cluster services become responsive to queries.

        Args:
            node (str): Node on which to execute the command.

            cs_group_name (str): vcs group name of the cluster service.

            attribute (str): vcs group attribute which is being checked.
        """
        has_cmd = self.vcs.get_hagrp_attribute_cmd(cs_group_name, attribute)

        online = \
            self.wait_for_cmd(node, has_cmd,
                              expected_rc=0, su_root=True, timeout_mins=4)
        self.assertTrue(online, cs_group_name + " is not responsive ")

    def check_service_attribute(self, node, cs_group_name, attribute, state):
        """
        Description:
            To ensure the VCS service's attribute is set to a specified state.

        Args:
            node (str): Node on which to execute the command.

            cs_group_name (str): vcs group name of the cluster service.

            attribute (str): vcs group attribute which is being checked.

            state (str): Expected state of the attribute.

        """
        has_cmd = self.vcs.get_hagrp_attribute_cmd(cs_group_name, attribute)

        self.log("info", "hagrp -display " + str(attribute) + " command: "
                 + str(has_cmd))
        self.log("info", "looking for attribute state: " + str(state))

        current_value = 0
        counter = 0
        while str(current_value) != str(state) and counter < 60:
            self.log("info", "current_value: " + str(current_value) +
                     " state: " + str(state))
            stdout, _, _ = \
                self.run_command(node, has_cmd,
                                 su_root=True, default_asserts=True)
            self.assertNotEqual([], stdout)

            grep_result = ' '.join(stdout)
            current_value = grep_result.split()[-1]
            counter += 1
            time.sleep(10)

        self.assertEquals(str(current_value), str(state))
        self.log("info", "Current_value: " + str(current_value))
        self.log("info", "Found state: " + str(state))

    def issue_offline_command(self, cs_group_name, nodes):
        """
        Description:
            Function to execute the hagrp offline command
            on a vcs cluster service.

        Args:
            cs_group_name (str): vcs cluster service to offline.

            nodes (list): list of nodes to be offlined.
        """
        for node in nodes:
            cmd = self.vcs.get_hagrp_cs_offline_cmd(cs_group_name,
                                                node,
                                                propagate=False)
            self.issue_and_wait_for_offline(node, cmd, cs_group_name)

    def issue_online_command(self, cs_group_name, nodes):
        """
        Description:
            Function to execute the hagrp online command
            on a vcs cluster service.

        Args:
            cs_group_name (str): vcs cluster service to online.

            nodes (list): list of nodes to be onlined.
        """
        for node in nodes:
            cmd = self.vcs.get_hagrp_cs_online_cmd(cs_group_name,
                                                node,
                                                propagate=False)
            self.issue_and_wait_for_online(node, cmd, cs_group_name)

    def issue_and_wait_for_offline(self, node, cmd, cs_group_name):
        """
        Description:
            Function to execute the hagrp offline command
            on a vcs cluster service on a specified node
            and to wait for completion.

        Args:
            node (str): node on which the cluster service is
                        to be offlined.

            cmd (str): formatted hagrp offline command.

            cs_group_name (str): vcs cluster service to offline.
        """
        stdout, _, _ = \
            self.run_command(node, cmd,
                             su_root=True, default_asserts=True)
        self.assertEqual([], stdout)

        status = 'string'
        counter = 0
        # system needs some time to offline.
        while status != 'OFFLINE' and counter < 60:
            # check if OFFLINE
            has_cmb = self.vcs.get_hastatus_sum_cmd()
            cmd = "{0} | {1} {2} | {1} {3}".format(has_cmb,
                                                   self.rh_os.grep_path,
                                                   cs_group_name,
                                                   node)
            stdout, _, _ = \
                self.run_command(node, cmd,
                                 su_root=True, default_asserts=True)
            self.assertNotEqual([], stdout)
            grep_result = ' '.join(stdout)
            if 'ONLINE' not in grep_result and 'STOPPING' not in grep_result:
                if 'FAULTED' in grep_result:
                    status = 'FAULTED'
                    self.assertNotEqual(status, 'FAULTED')
                elif 'FROZEN' in grep_result:
                    status = 'FROZEN'
                    self.assertNotEqual(status, 'FROZEN')
                elif 'OFFLINE' in grep_result:
                    if 'OFFLINE|' not in grep_result:
                        status = 'OFFLINE'
            counter += 1
            time.sleep(10)
        self.assertEqual(status, 'OFFLINE')

    def issue_and_wait_for_online(self, node, cmd, cs_group_name):
        """
        Description:
            Function to execute the hagrp online command
            on a vcs cluster service on a specified node
            and to wait for completion.

        Args:
            node (str): node on which the cluster service is
                        to be onlined.

            cmd (str): formatted hagrp online command.

            cs_group_name (str): vcs cluster service to online.
        """
        stdout, _, _ = \
            self.run_command(node, cmd,
                             su_root=True, default_asserts=True)
        self.assertEqual([], stdout)

        status = 'string'
        counter = 0
        # system needs some time to online.
        while status != 'ONLINE' and counter < 60:
            # check if ONLINE
            has_cmb = self.vcs.get_hastatus_sum_cmd()
            cmd = "{0} | {1} {2} | {1} {3}".format(has_cmb,
                                                   self.rh_os.grep_path,
                                                   cs_group_name,
                                                   node)
            stdout, _, _ = \
                self.run_command(node, cmd,
                                 su_root=True, default_asserts=True)
            self.assertNotEqual([], stdout)
            grep_result = ' '.join(stdout)
            if 'OFFLINE' not in grep_result and 'STARTING' not in grep_result:
                if 'FAULTED' in grep_result:
                    status = 'FAULTED'
                    self.assertNotEqual(status, 'FAULTED')
                elif 'FROZEN' in grep_result:
                    status = 'FROZEN'
                    self.assertNotEqual(status, 'FROZEN')
                elif 'ONLINE' in grep_result:
                    if 'ONLINE|' not in grep_result:
                        status = 'ONLINE'
            counter += 1
            time.sleep(10)
        self.assertEqual(status, 'ONLINE')

    @attr('all', 'non-revert', 'Bug243557_tc01')
    def test_01_unlock_success_with_temporarily_frozen_group(self):
        """
        @tms_id: TORF-243557_tc01
        @tms_requirements_id: TORF-239618
        @tms_title: Ensure the locking and unlocking of a node while the VCS
                    service cluster is in a frozen state
        @tms_description:
            Test to verify that the locking, and subsequent unlocking, of
            a node is successful when a vcs cluster service on the group is
            in a frozen state.
        @tms_test_steps:
            @step: Copy required rpms to the MS and import them.
            @result: Files are imported successfully.
            @step: Create four vcs cluster services. Two should be a one-node
                    parallels, and two should be fail-over CSs
            @result: cluster services created
            @step: deploy cluster services
            @result: Cluster services successfully deployed
            @step: issue offline command for services
            @result: services offline
            @step: issue freeze command to service CS41 & CS42.
            @result: services are frozen.
            @step: issue haconf -make rw command and persistently freeze
                   CS43 & CS44
            @result: Command issued, and services persistently frozen.
            @step: Check the attributes of CS 41, 42, 43, and 44.
            @result: Attributes are as expected.
            @step: Reboot the nodes.
            @result: The nodes are rebooted.
            @step: Ensure the service's TFrozen attribute is set to 1.
            @result: service's TFrozen attribute is set to 1.
            @step: Ensure the service's Frozen attribute is set to 1.
            @result: service's Frozen attribute is set to 1.
            @step: Ensure the service's IntentOnline attribute is set to 2.
            @result: service's IntentOnline attribute is set to 2.
            @step: Create a vcs cluster service of type two node parallel.
            @result: two node parallel cluster service created
            @step: deploy cluster service
            @result: Cluster service successfully deployed
            @step: issue unfreeze command to service CS41 & CS42.
            @result: services are unfrozen.
            @step: issue haconf -make rw command and persistently unfreeze
                   CS43 & CS44
            @result: Command issued, and services persistently unfrozen.
            @step: issue online command for services
            @result: services online
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """

        self.log("info", "Step 0. Importing test RPMS to MS")
        # ==================================================
        # It is assumed that any rpms required for this test
        # exist in a repo before the plan is executed
        # This section of the test sets this up
        # ===================================================
        # List of rpms required for this test
        list_of_lsb_rpms = [
            "EXTR-lsbwrapper41-1.1.0.rpm",
            "EXTR-lsbwrapper42-1.1.0.rpm",
            "EXTR-lsbwrapper43-1.1.0.rpm",
            "EXTR-lsbwrapper44-1.1.0.rpm",
            "EXTR-lsbwrapper45-1.1.0.rpm"
        ]
        # Copy RPMs to Management Server
        filelist = []
        for rpm in list_of_lsb_rpms:
            filelist.append(self.get_filelist_dict(self.rpm_src_dir + rpm,
                                                   "/tmp/"))
        self.copy_filelist_to(self.management_server, filelist,
                              add_to_cleanup=False, root_copy=True)

        # Use LITP import to add to repo for each RPM
        for rpm in list_of_lsb_rpms:
            self.execute_cli_import_cmd(
                self.management_server,
                '/tmp/' + rpm,
                self.repo_dir_3pp)

        self.log("info", "Step 1. Creating VCS Service Clusters. Two of type "
                         "one node parallel, and two of type fail-over. ")
        # ===============================================================
        # This section of the test sets up the model and creates the plan
        # ===============================================================
        # Maximum duration of running plan
        plan_timeout_mins = 40

        # Generate configuration for the plan
        # This configuration will contain the configuration for all
        # clustered-services to be created but only CS1 will be used

        list_of_cs_names_service = ['CS41', 'CS42', 'CS43', 'CS44']
        configuration_service = \
            self.generate_plan_conf_service(self.traffic_networks)

        for cs_name in list_of_cs_names_service:
            self.generate_execute_cs_cli(configuration_service,
                                         self.vcs_cluster_url,
                                         cs_name,
                                         app_class="service")

        self.log("info", "Step 2. Deploying Service Clusters. ")
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE,
                                plan_timeout_mins)

        self.log("info", "Step 3. Issuing offline command on services. ")
        cluster_id = self.vcs_cluster_url.split("/")[-1]

        # VCS group name of clustered-service
        cs_group_names = [self.vcs.generate_clustered_service_name(cs_name,
                                                                   cluster_id)
                          for cs_name in list_of_cs_names_service]

        self.issue_offline_command(cs_group_names[0],
                                   [self.list_managed_nodes[0]])

        self.issue_offline_command(cs_group_names[1],
                                   self.list_managed_nodes)

        self.issue_offline_command(cs_group_names[2],
                                   [self.list_managed_nodes[0]])

        self.issue_offline_command(cs_group_names[3],
                                   self.list_managed_nodes)

        try:

            self.log("info", "Step 4. Issue freeze command to one of each "
                             "Cluster service type")
            cmd = self.vcs.get_hagrp_cs_freeze_cmd(cs_group_names[0],
                                                   self.list_managed_nodes[0],
                                                   persistent=False)

            self.run_command(self.list_managed_nodes[0], cmd,
                             su_root=True)

            cmd = self.vcs.get_hagrp_cs_freeze_cmd(cs_group_names[1],
                                                   self.list_managed_nodes[0],
                                                   persistent=False)

            self.run_command(self.list_managed_nodes[0], cmd,
                             su_root=True)

            self.log("info", "Step 5. Issue the command to allow changes to "
                             "the haconf file")
            cmd = self.vcs.get_haconf_cmd("-makerw")
            stdout, _, _ = \
                self.run_command(self.list_managed_nodes[0], cmd,
                                 su_root=True, default_asserts=True)
            self.assertEqual([], stdout)

            self.log("info", "Step 6. Issue the persistent freeze command to "
                             "the remaining cluster services. ")
            cmd = self.vcs.get_hagrp_cs_freeze_cmd(cs_group_names[2],
                                                   self.list_managed_nodes[0],
                                                   persistent=True)
            self.run_command(self.list_managed_nodes[0], cmd,
                             su_root=True)

            cmd = self.vcs.get_hagrp_cs_freeze_cmd(cs_group_names[3],
                                                   self.list_managed_nodes[0],
                                                   persistent=True)

            self.run_command(self.list_managed_nodes[0], cmd,
                             su_root=True)

            self.log("info", "Step 7. Reboot the nodes.  ")
            self.vcs_reboot_and_wait_for_system(self.management_server,
                                                self.list_managed_nodes[1],
                                                self.list_managed_nodes[0])
            self.vcs_reboot_and_wait_for_system(self.management_server,
                                                self.list_managed_nodes[0],
                                                self.list_managed_nodes[1])

            self.log("info", "Step 8. Check the state of the Cluster Services "
                             "attributes. ")
            self.wait_for_hagrp_to_respond_to_queries(
                                                    self.list_managed_nodes[0],
                                                    cs_group_names[0],
                                                    'TFrozen')

            self.check_service_attribute(self.list_managed_nodes[0],
                                         cs_group_names[0], 'TFrozen', 1)

            self.check_service_attribute(self.list_managed_nodes[0],
                                         cs_group_names[1], 'TFrozen', 1)

            self.check_service_attribute(self.list_managed_nodes[0],
                                         cs_group_names[2], 'Frozen', 1)

            self.check_service_attribute(self.list_managed_nodes[0],
                                         cs_group_names[3], 'Frozen', 1)

            for cd_group_no in cs_group_names:
                self.check_service_attribute(self.list_managed_nodes[0],
                                             cd_group_no, 'IntentOnline', 2)

            self.log("info", "Step 9. Create a Service Cluster of type: two "
                             "node parallel. ")
            two_node_parallel = 'CS45'
            self.generate_execute_cs_cli(configuration_service,
                                         self.vcs_cluster_url,
                                         two_node_parallel,
                                         app_class="service")

            self.log("info", "Step 10. Deploy the two node parallel Cluster "
                             "Service")
            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE,
                                    plan_timeout_mins)

            self.log("info", "Step 11. Ensure the deployment is successful. ")
            network_dev_map = self.get_node_network_devices(
                                                    self.management_server,
                                                    self.primary_node_url)
            cmd = self.vcs.get_hagrp_state_cmd()
            hagrp_output, _, _ = self.run_command(self.primary_node,
                    cmd, su_root=True, default_asserts=True)

            cmd = self.vcs.get_hares_state_cmd()
            hares_output, _, _ = self.run_command(self.primary_node,
                    cmd, su_root=True, default_asserts=True)

            list_of_cs_names_service = ['CS45']
            self.verify_deployments_by_node(list_of_cs_names_service,
                                            cluster_id,
                                            configuration_service,
                                            hagrp_output, hares_output,
                                            network_dev_map,
                                            self.list_managed_nodes)

        finally:
            self.log("info", "Begining cleanup of frozen and offline VCS "
                             "clusters")

            self.log("info", "Step 12. Issue the unfreeze command"
                             "to the frozen cluster services. ")
            cmd = self.vcs.get_hagrp_cs_unfreeze_cmd(cs_group_names[0],
                                                self.list_managed_nodes[0],
                                                persistent=False)
            self.run_command(self.list_managed_nodes[0], cmd,
                             su_root=True)
            self.check_service_attribute(self.list_managed_nodes[0],
                                         cs_group_names[0], 'TFrozen',
                                         0)

            cmd = self.vcs.get_hagrp_cs_unfreeze_cmd(cs_group_names[1],
                                                self.list_managed_nodes[0],
                                                persistent=False)

            self.run_command(self.list_managed_nodes[0], cmd,
                             su_root=True)
            self.check_service_attribute(self.list_managed_nodes[0],
                                         cs_group_names[1], 'TFrozen',
                                         0)

            self.log("info", "Step 13. Issue the command to allow changes to "
                             "the haconf file to unfreeze SC")
            cmd = self.vcs.get_haconf_cmd("-makerw")
            stdout, _, rc = \
                self.run_command(self.list_managed_nodes[0], cmd, su_root=True)
            if rc != 0:
                self.assertTrue("Cluster already writable" in stdout[0],
                                "Failed to set VCS to read-write mode")
            else:
                self.assertEqual([], stdout)

            self.log("info", "Step 14. Issue the persistent unfreeze command "
                             "to the frozen cluster services. ")
            cmd = self.vcs.get_hagrp_cs_unfreeze_cmd(cs_group_names[2],
                                                self.list_managed_nodes[0],
                                                persistent=True)
            self.run_command(self.list_managed_nodes[0], cmd,
                             su_root=True)
            self.check_service_attribute(self.list_managed_nodes[0],
                                         cs_group_names[2], 'Frozen',
                                         0)

            cmd = self.vcs.get_hagrp_cs_unfreeze_cmd(cs_group_names[3],
                                                self.list_managed_nodes[0],
                                                persistent=True)

            self.run_command(self.list_managed_nodes[0], cmd,
                             su_root=True)
            self.check_service_attribute(self.list_managed_nodes[0],
                                         cs_group_names[3], 'Frozen',
                                         0)

            for cs_group in cs_group_names:
                self.issue_online_command(cs_group,
                                      [self.list_managed_nodes[0]])

#!/usr/bin/env python
'''
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     Oct 2014
@author:    Jan Odvarko
@summary:   Agile: LITPCDS-6165
'''

from litp_generic_test import GenericTest, attr
from vcs_utils import VCSUtils
import test_constants
import time
import os
# Location where RPMs to be used are stored
RPM_SRC_DIR = os.path.dirname(os.path.realpath(__file__)) + '/test_lsb_rpms/'


class Story6165(GenericTest):
    '''
    As a LITP Developer I want to use the service item along with filesystem
    items with the VCS plug in so that there is a consistent approach to
    managing LSB services
    '''

    def setUp(self):
        """
        Description:
            Runs before every single test
        Actions:
            1. Call the super class setup method
            2. Set up variables used in the tests
        Results:
            The super class prints out diagnostics and variables
            are defined which are required in the tests.
        """
        super(Story6165, self).setUp()

        self.vcs = VCSUtils()

        self.ms1 = self.get_management_node_filename()
        self.managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.managed_nodes[0]

        self.node_urls = []
        self.node_vnames = []
        for node in self.managed_nodes:
            url = self.get_node_url_from_filename(self.ms1, node)
            self.node_urls.append(url)
            self.node_vnames.append(url.split("/")[-1])

        self.cluster_url = self.find(self.ms1, "/deployments",
                                     "vcs-cluster")[0]
        self.cluster_id = self.cluster_url.split("/")[-1]

        # Repo where rpms will be installed
        self.repo_dir_3pp = test_constants.PP_PKG_REPO_DIR

        # specify test data constants
        self.cs_num = '6165'
        self.cs_app = 'APP6165'
        self.lsb_rpm = 'EXTR-lsbwrapper6165-1.1.0.rpm'

        self.tmp_cs_id = "test_cs_story6165"

        self.tmp_app_id = "test_app_story6165"
        self.tmp_app_service = "test_service_story6165"

        self.fsys = [
            {"id": "fs6165", "url": None, "mount_path": None},
        ]

        # Generate names for the Mount and Disk Group resources
        self.res = {
            "mount": self.vcs.generate_mount_resource_name(
                self.cluster_id, self.cs_num, self.cs_app,
                self.fsys[0]["id"]),
            "diskgrp": self.vcs.generate_diskgrp_resource_name(
                self.cluster_id, self.cs_num, self.cs_app,
                self.fsys[0]["id"]),
        }

        # Generate CS group name
        self.cs_group_name = self.vcs.generate_clustered_service_name(
            self.cs_num, self.cluster_id)

        # define test data constants dict
        self.conf = {}

        # List of VCS clustered services names and associated run-time names
        self.conf['app_per_cs'] = {
            self.cs_num: self.cs_app
        }

        # List of nodes defined per vcs-clustered-service
        self.conf['nodes_per_cs'] = {
            self.cs_num: [1, 2]
        }

        # Parameters per clustered-service
        self.conf['params_per_cs'] = {
            self.cs_num: {'active': 1, 'standby': 1}
        }

        # List of ip resources per run-time in a clustered service
        self.conf['ip_per_app'] = {
            self.cs_app: []
        }

        # List of ip addresses and their associated networks
        self.conf['network_per_ip'] = {}

        # List of packages that will exist per run-time
        self.conf['pkg_per_app'] = {
            self.cs_app: {'EXTR-lsbwrapper6165': {}}
        }

        # List of properties per lsb runtime
        self.conf['lsb_app_properties'] = {
            self.cs_app: {'service_name': 'test-lsb-6165'}
        }

        # List of ha properties per CS
        self.conf['ha_service_config_properties'] = {
            self.cs_num: {}
        }

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            1. Call superclass teardown
        """
        super(Story6165, self).tearDown()

    def init_resource_info(self):
        """
        Find VxFS filesystems used in this testset
        """

        sp_url = self.get_vxvm_paths(self.ms1)[0]
        fs_urls = self.find(self.ms1, sp_url, "file-system")
        for fs_url in fs_urls:
            for fsys in self.fsys:
                if fs_url.endswith("/" + fsys["id"]):
                    fsys["url"] = fs_url
                    fsys["mount_path"] = self.excl_inherit_symbol(
                        self.execute_show_data_cmd(
                            self.ms1, fs_url, "mount_point")
                    )
                    break

    def create_cs_with_service(self, cs_id, cs_options, service_id,
                               service_options):
        """
        Creates a Clustered Service with a software item in it

        Args:
            cs_id (str):      ID of the Clustered Service
            cs_options (str): Options of the Clustered Service
            service_id (str):      ID of the service item
            service_options (str): Options of the service item
        Returns:
            (str) URL of the new CS
        """

        cs_url = self.cluster_url + "/services/" + cs_id
        cs_class = "vcs-clustered-service"
        self.execute_cli_create_cmd(self.ms1, cs_url, cs_class, cs_options)

        app_sw_url = "/software/services/" + service_id
        app_sw_class = "service"
        self.execute_cli_create_cmd(self.ms1, app_sw_url, app_sw_class,
                                    service_options)

        app_url = cs_url + "/applications/" + service_id
        app_options = ""
        self.execute_cli_inherit_cmd(self.ms1, app_url, app_sw_url,
                                     app_options)

        return cs_url

    def get_vxvm_paths(self, ms_node):
        """
        Returns paths for storage profile in the system filtered by the passed
        profile driver type.

        Args:
            ms_node (str): The node in use.
        Returns:
            (list) List of all storage profile paths of that type.
        """
        filtered_profiles = []

        storage_profiles = self.find(ms_node, "/deployments",
                                     "storage-profile", True)

        for path in storage_profiles:
            volume_driver = self.execute_show_data_cmd(ms_node,
                                                       path, "volume_driver")

            if self.excl_inherit_symbol(volume_driver).lower() == "vxvm":
                filtered_profiles.append(path)

        return filtered_profiles

    def get_res_state_per_node(self, node_filename, resource_name):
        """
        Return VCS resource state on the specified node

        @arg (str) node_filename  The node where to run the hares command
        @arg (str) resource_name  Name of the resource
        @ret (dict) Status of the given resource per node
        """
        cmd = self.vcs.get_hares_state_cmd() + resource_name
        stdout, stderr, rc = self.run_command(node_filename,
                                              cmd, su_root=True)
        self.assertEqual(0, rc)
        self.assertEqual([], stderr)

        return self.vcs.get_resource_state(stdout)

    @staticmethod
    def res_state_filter(res_state, state_filter):
        """
        Filters the dict of resource states per node and only leaves the nodes
        where the resource is in specified state

        @arg (dict) res_state    State of resources
        @arg (dict) state_filter Resource state to search for
        @ret (list) List of the nodes where the resource is in specified state
        """
        res_active_nodes = []
        for node, state in res_state.items():
            if state == state_filter:
                res_active_nodes.append(node)

        return res_active_nodes

    def switch_group_to_system(self, node_filename, group, system):
        """
        Switch group to a specified system

        @arg (str) node_filename  The node where to run the hares command
        @arg (str) group          Name of the group to switch
        @arg (str) system         Name of the system to switch to
        """
        cmd = "hagrp -switch '{0}' -to '{1}'".format(group, system)
        stdout, stderr, rc = self.run_command(
            node_filename, cmd, su_root=True)
        self.assertEqual(0, rc)
        self.assertEqual([], stdout)
        self.assertEqual([], stderr)

    def verify_filesystem_rw(self, node_filename, mountpoint):
        """
        Performs read/write operations on the specified mount point

        @arg (str) node_filename The node to check
        @arg (str) mountpoint    Mount point on the node
        """

        test_str = " ".join(100 * ["Lorem Ipsum dolor sit amet"])
        test_file = mountpoint.rstrip("/") + "/test_story6165.txt"

        # Write to a test file
        cmd = "/bin/echo '{0}' > '{1}'".format(test_str, test_file)
        stdout, stderr, rc = self.run_command(node_filename,
                                              cmd, su_root=True)
        self.assertEqual(0, rc)
        self.assertEqual([], stdout)
        self.assertEqual([], stderr)

        # Verify contents of the test file
        lines = self.get_file_contents(node_filename, test_file)
        self.assertEqual(test_str.rstrip(), "\n".join(lines).rstrip())

    def verify_mounts(self):
        """
        - Make sure the currently active Mount resource is mounted and
          that is readable and writable
        - Make sure the currently standby Mount resource is not mounted
        """

        # Mount resource should be ONLINE on one node and OFFLINE on the
        # other one
        res_state_per_node = self.get_res_state_per_node(
            self.primary_node, self.res["mount"])

        self.assertEqual(1, res_state_per_node.values().count("online"))
        self.assertEqual(1, res_state_per_node.values().count("offline"))

        for node_hostname, state in res_state_per_node.items():
            node_filename = \
                self.get_node_list_by_hostname(node_hostname)[0].filename
            is_fs_mounted = self.is_filesystem_mounted(
                node_filename, "/6165")
            self.assertTrue(state in ["online", "offline"])
            if state == "online":
                # Make sure the currently active Mount resource is mounted and
                # that is readable and writable
                self.assertTrue(is_fs_mounted)
                self.verify_filesystem_rw(node_filename,
                                          "/6165")
            elif state == "offline":
                # Make sure the currently standby Mount resource is not mounted
                self.assertFalse(is_fs_mounted)

    def create_strg_prof_file_sys(self):
        """
        Create storage profile, volume group, file-system and physical-device.
        """
        # Create storage profile
        storage_profile_url = '/infrastructure/storage/' \
                              'storage_profiles/storage_6165'
        prps = 'volume_driver=vxvm'
        self.execute_cli_create_cmd(self.ms1, storage_profile_url,
                                    'storage-profile', prps,
                                    add_to_cleanup=False)

        # Create volume group
        vg_name = 'vg_6165'
        vg_url = '{0}/volume_groups/{1}'.\
            format(storage_profile_url, vg_name)
        props = 'volume_group_name=\'{0}\''.format(vg_name)
        self.execute_cli_create_cmd(self.ms1,
                                    vg_url,
                                    "volume-group",
                                    props,
                                    add_to_cleanup=False)

        # Create file system
        fs_url = vg_url + '/file_systems/fs6165'
        props = 'type=\'vxfs\' mount_point=\'/6165\' size=100M snap_size=100'
        self.execute_cli_create_cmd(self.ms1,
                                    fs_url,
                                    'file-system', props,
                                    add_to_cleanup=False)

        # Add phisical devices
        new_device_url = vg_url + '/physical_devices/internal'
        props = 'device_name=\'hd3\''
        self.execute_cli_create_cmd(self.ms1,
                                    new_device_url,
                                    'physical-device', props,
                                    add_to_cleanup=False)

        # Inherit from created storage profile
        inherit_url = self.cluster_url + '/storage_profile/storage_6165'
        self.execute_cli_inherit_cmd(self.ms1, inherit_url,
                                     storage_profile_url,
                                     add_to_cleanup=False)
        # Inherit storage profile, vg and fs to CS
        cs_url = self.get_cs_conf_url(self.ms1,
                                      self.cs_num,
                                      self.cluster_url)
        inherit_url = cs_url + '/filesystems/fs6165'
        source_url = self.cluster_url + '/storage_profile/storage_6165' \
            '/volume_groups/vg_6165/file_systems/fs6165'
        self.execute_cli_inherit_cmd(self.ms1, inherit_url,
                                     source_url,
                                     add_to_cleanup=False)

    def generate_execute_cs_cli(self, conf, cs_name,
                                app_class='lsb-runtime'):
        """
        This function will generate and execute the CLI to create
        a clustered services

        Args:
            conf (dict): configuration details for clustered-services

            self.cluster_id (str): Model url of vcs cluster item

            cs_name (str): clustered-service name

            app_class (str): class name of the application item

        Returns: -
        """

        # Get CLI commands
        cli_data = self.vcs.generate_cli_commands(self.cluster_url,
                                                  conf, cs_name,
                                                  app_class)

        # This section of code will add the nodes to the CS
        # Find cluster node urls
        nodes_urls = self.find(self.ms1,
                               self.cluster_url,
                               'node')
        node_cnt = 0
        node_vnames = []
        num_of_nodes = int(conf['params_per_cs'][cs_name]['active']) + \
            int(conf['params_per_cs'][cs_name]['standby'])

        for node_url in nodes_urls:
            node_cnt += 1

            # Add the node to the cluster
            if node_cnt <= num_of_nodes:
                node_vnames.append(node_url.split('/')[-1])

        # Create Clustered-Service in the model
        cs_options = '{0} node_list="{1}"'.format(cli_data['cs']['options'],
                                                  ','.join(node_vnames))

        self.execute_cli_create_cmd(self.ms1,
                                    cli_data['cs']['url'],
                                    cli_data['cs']['class_type'],
                                    cs_options,
                                    add_to_cleanup=False)

        # Create lsb apps in the model
        self.execute_cli_create_cmd(self.ms1,
                                    cli_data['apps']['url'],
                                    cli_data['apps']['class_type'],
                                    cli_data['apps']['options'],
                                    add_to_cleanup=False)

        # Create all packages associated with lsb-app
        for pkg_data in cli_data['pkgs']:
            self.execute_cli_create_cmd(self.ms1,
                                        pkg_data['url'],
                                        pkg_data['class_type'],
                                        pkg_data['options'],
                                        add_to_cleanup=False)

        # CREATE THE HA SERVICE CONFIG ITEM
        if cli_data['ha_service_config']:
            self.execute_cli_create_cmd(self.ms1,
                                        cli_data['ha_service_config']['url'],
                                        cli_data['ha_service_config']
                                        ['class_type'],
                                        cli_data['ha_service_config']
                                        ['options'],
                                        add_to_cleanup=False)

        # Create pkgs under the lsb-app
        for pkg_link_data in cli_data['pkg_links']:
            self.execute_cli_inherit_cmd(self.ms1,
                                         pkg_link_data['child_url'],
                                         pkg_link_data['parent_url'],
                                         add_to_cleanup=False)

        # create inherit to the service
        if app_class in ['service', 'vm-service']:
            self.execute_cli_inherit_cmd(self.ms1,
                                         cli_data['apps']
                                         ['app_url_in_cluster'],
                                         cli_data['apps']['url'],
                                         add_to_cleanup=False)
        # Create storage profile, file system and needed inherit
        self.create_strg_prof_file_sys()

    def add_cs_and_apps(self):
        """
        Description:
            To ensure that it is possible to specify, and deploy,
            a vcs-clustered-services containing different values about
            fault_on_monitor_timeout tolerance_limit and clean_timeout.
            Below a vcs-clustered-service of configuration active=1 standby=1

            It will create a
                2 nodes ha mode = failover.
                CS 6165 - 1 app.

        Actions:
             1. Add dummy lsb-services to repo
             2. Executes CLI to create model
             3. Create and execute plan.

        Results:
            The plan runs successfully
        """
        # It is assumed that any rpms required for this test
        # exist in a repo before the plan is executed
        # This section of the test sets this up
        # Copy RPMs to Management Server
        self.copy_file_to(self.ms1,
                          RPM_SRC_DIR + self.lsb_rpm, '/tmp/',
                          root_copy=True,
                          add_to_cleanup=False)

        # Use LITP import to add to repo for each RPM
        self.execute_cli_import_cmd(
            self.ms1,
            '/tmp/' + self.lsb_rpm,
            self.repo_dir_3pp)
        # This section of the test sets up the model and creates the plan
        # Maximum duration of running plan
        plan_timeout_mins = 20

        # Generate configuration for the plan
        # This configuration will contain the configuration for all
        # clustered-services to be created
        self.generate_execute_cs_cli(self.conf, self.cs_num, 'service')
        # Create and execute plan
        self.execute_cli_createplan_cmd(self.ms1)
        self.execute_cli_runplan_cmd(self.ms1)

        self.assertTrue(self.wait_for_plan_state(
            self.ms1,
            test_constants.PLAN_COMPLETE,
            plan_timeout_mins
        ))

    @attr('all', 'non-revert', 'physical', 'story6165', 'story6165_tc01')
    def test_01_p_create_cs(self):
        """
        @tms_id: litpcds_6165_tc1
        @tms_requirements_id: LITPCDS-6165
        @tms_title: create vcs cluster service
        @tms_description:
        This test will a create clustered-service and inherit a filesystem
        in it
        @tms_test_steps:
        @step: Create a failover VCS CS (active=1, standby=1) with a
        filesystems collection in it
        @result: failover VCS CS created
        @step: inherit a VxFS filesystem onto filesystem collection
        @result: filesystem inherited
        @step: create and run plan
        @result: plan executes successfully
        @result: Mount and DiskGroup resources created
        @result: Mount and DiskGroup on only one node is ONLINE and OFFLINE on
        the other
        @result: currently active Mount resource is mounted
        @result: currently standby Mount resource is not mounted
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        cs_url = self.get_cs_conf_url(self.ms1,
                                      self.cs_num,
                                      self.cluster_url)
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.add_cs_and_apps()

        self.init_resource_info()

        nodes_urls = self.find(self.ms1, self.cluster_url, "node")

        # Output from hasys -state command
        cmd = self.vcs.get_hasys_state_cmd()
        hasys_output, _, _ = self.run_command(self.primary_node,
                                              cmd, su_root=True,
                                              default_asserts=True)
        self.assertTrue(self.vcs.verify_vcs_systems_ok(nodes_urls,
                                                       hasys_output))

    @attr('all', 'non-revert', 'physical', 'story6165', 'story6165_tc02')
    def test_02_p_hagrp_switch(self):
        """
        @tms_id: litpcds_6165_tc2
        @tms_requirements_id: LITPCDS-6165
        @tms_title: Mount and DiskGroup resource switch
        @tms_description:
        Test case to make sure the Mount and DiskGroup resource will
        successfully switch to the other node and then back to the original
        node
        @tms_test_steps:
        @step: execute "hagrp -switch" command to switch all CS resources to
        the OFFLINE node
        @result: command executes successfully
        @result: previously OFFLINE Node is now ONLINE and previously ONLINE
        Node is now OFFLINE
        @result: currently active Mount resource is mounted
        @result: currently standby Mount resource is not mounted
        @step: execute "hagrp -switch" command to switch all CS resources to
        the OFFLINE node
        @result: command executes successfully
        @result: previously OFFLINE Node is now ONLINE and previously ONLINE
        Node is now OFFLINE
        @result: currently active Mount resource is mounted
        @result: currently standby Mount resource is not mounted
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        cs_url = self.get_cs_conf_url(self.ms1,
                                      self.cs_num,
                                      self.cluster_url)
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.add_cs_and_apps()

        self.init_resource_info()

        poll_count = 12
        poll_interval_sec = 10

        # Mount resource should be ONLINE on one node and OFFLINE on the
        # other one
        res_state_per_node = self.get_res_state_per_node(
            self.primary_node, self.res["mount"])
        self.assertEqual(1, res_state_per_node.values().count("online"))
        self.assertEqual(1, res_state_per_node.values().count("offline"))

        # Group should be temporarily switched to the node where
        # the Mount was originally offline
        switch_group_to_node = self.res_state_filter(
            res_state_per_node, "offline")[0]

        # Group should be returned to the node where the App was
        # originally online
        return_group_to_node = self.res_state_filter(
            res_state_per_node, "online")[0]

        # Temporarily switch the group and its resources to the other node
        self.switch_group_to_system(self.primary_node,
                                    self.cs_group_name, switch_group_to_node)

        poll_no = 1
        while True:
            time.sleep(poll_interval_sec)

            # Did the resources switch to the other node?
            resources = [
                self.res["mount"],
                self.res["diskgrp"],
            ]

            resources_ok = True
            for resource in resources:
                # Each resource should be ONLINE on the node we are switching
                # to and OFFLINE on the other one
                res_state_per_node = self.get_res_state_per_node(
                    self.primary_node, resource)
                if "online" != res_state_per_node[switch_group_to_node]:
                    resources_ok = False
                    break

            if resources_ok:
                break
            else:
                self.assertTrue(poll_no < poll_count)
                poll_no += 1

        self.assertEqual(1, res_state_per_node.values().count("online"))
        self.assertEqual(1, res_state_per_node.values().count("offline"))

        # Verify if the FS is mounted as expected
        self.verify_mounts()

        # Switch the group and its resources back to the original node
        self.switch_group_to_system(self.primary_node,
                                    self.cs_group_name, return_group_to_node)

        poll_no = 1
        while True:
            time.sleep(poll_interval_sec)

            # Did the resources switch to the other node?
            resources = [
                self.res["mount"],
                self.res["diskgrp"],
            ]

            resources_ok = True
            for resource in resources:
                # Each resource should be ONLINE on the node we are switching
                # to and OFFLINE on the other one
                res_state_per_node = self.get_res_state_per_node(
                    self.primary_node, resource)
                if "online" != res_state_per_node[return_group_to_node]:
                    resources_ok = False
                    break

            if resources_ok:
                break
            else:
                self.assertTrue(poll_no < poll_count)
                poll_no += 1

        self.assertEqual(1, res_state_per_node.values().count("online"))
        self.assertEqual(1, res_state_per_node.values().count("offline"))

        # Verify if the FS is mounted as expected
        self.verify_mounts()

    @attr('all', 'non-revert', 'physical', 'story6165', 'story6165_tc13')
    def test_13_n_inherit_used_fs(self):
        """
        @tms_id: litpcds_6165_tc13
        @tms_requirements_id: LITPCDS-6165
        @tms_title: Mount and DiskGroup resource switch
        @tms_description:
        Test to verify that LITP plan will fail to create when a filesystem
        that is already effectively used in another CS is inherited in
        a newly created CS
        @tms_test_steps:
        @step:Create a failover VCS CS (active=1, standby=1) with a filesystems
        collection in it
        @result: failover VCS CS created
        @step: inherit the VCS CS onto filesystem
        @result: filesystem inherited
        @step: create plan
        @result: create plan fails
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        cs_url = self.get_cs_conf_url(self.ms1,
                                      self.cs_num,
                                      self.cluster_url)
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.add_cs_and_apps()

        self.init_resource_info()

        cs_options = \
            "active={0} standby={1} name='{2}' node_list='{3}'".format(
                1, 1, self.tmp_cs_id, ",".join(self.node_vnames[0:2]))
        app_options = "service_name='{0}'".format(self.tmp_app_service)
        cs_url = self.create_cs_with_service(self.tmp_cs_id, cs_options,
                                             self.tmp_app_id, app_options)

        fs_url = cs_url + "/filesystems/" + self.fsys[0]["id"]
        fs_options = ""
        self.execute_cli_inherit_cmd(self.ms1, fs_url, self.fsys[0]["url"],
                                     fs_options)

        self.execute_cli_createplan_cmd(self.ms1, expect_positive=False)

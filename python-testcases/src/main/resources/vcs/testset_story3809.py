#!/usr/bin/env python
'''
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     June 2014
@author:    Jan Odvarko
@summary:   Agile: STORY LITPCDS-3809
'''

from litp_generic_test import GenericTest, attr
from redhat_cmd_utils import RHCmdUtils
import os
import re
import time


class Story3809(GenericTest):
    '''
    As a HA application designer I want to manage Mounting movable VxVM block
    devices so that my application will failover when a fault is detected
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
        super(Story3809, self).setUp()

        self.rh_os = RHCmdUtils()

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
        self.rpm_src_dir = \
            os.path.dirname(os.path.realpath(__file__)) + \
            "/test_lsb_rpms/"

        self.cs_url = self.find_cs_with_filesystem("/deployments", "vxfs")
        self.cs_id = self.cs_url.split("/")[-1]
        self.cs_name = self.execute_show_data_cmd(self.ms1, self.cs_url,
            "name")
        self.app_id = self.get_cs_app(self.cs_url).split('/')[-1]

        sp_url = self.get_vxvm_paths(self.ms1)[0]
        self.fs_url = self.find(self.ms1, sp_url, "file-system")[0]
        self.fs_id = self.fs_url.split('/')[-1]
        self.mount_path = self.excl_inherit_symbol(self.execute_show_data_cmd(
            self.ms1, self.fs_url, "mount_point"))

        self.traffic_networks = ["traffic1", "traffic2"]

        fs_id = self.get_cs_filesystem(self.cs_url).split('/')[-1]
        self.res = {
            "app": self.gen_app_resource_name(
                   self.cluster_id, self.cs_name, self.app_id),
            "mount": self.gen_mount_resource_name(
                     self.cluster_id, self.cs_id, self.app_id, fs_id),
            "diskgrp": self.gen_diskgrp_resource_name(
                       self.cluster_id, self.cs_id, self.app_id, fs_id)
        }

        # Generate CS group name
        self.cs_group_name = self.gen_cs_group_name(
            self.cluster_id, self.cs_id)

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            1. Call superclass teardown
        """
        super(Story3809, self).tearDown()

    @staticmethod
    def gen_cs_group_name(cluster_item_id, cs_item_id):
        """
        Returns full name of CS Group based on the parameters passed
        """
        return "Grp_CS_{0}_{1}".format(cluster_item_id, cs_item_id)

    @staticmethod
    def gen_app_resource_name(cluster_item_id, cs_item_id, runtime_item_id):
        """
        Returns full name of App resource based on the parameters passed
        """
        return "Res_App_{0}_{1}_{2}".format(
            cluster_item_id, cs_item_id, runtime_item_id)

    @staticmethod
    def gen_mount_resource_name(cluster_item_id, cs_item_id, runtime_item_id,
                                filesystem_id):
        """
        Returns full name of Mount resource based on the parameters passed
        """
        return "Res_Mnt_{0}_{1}_{2}_{3}".format(
            cluster_item_id, cs_item_id, runtime_item_id, filesystem_id)

    @staticmethod
    def gen_diskgrp_resource_name(cluster_item_id, cs_item_id, runtime_item_id,
                                  filesystem_id):
        """
        Returns full name of Disk Group resource based on the parameters passed
        """
        return "Res_DG_{0}_{1}_{2}_{3}".format(
            cluster_item_id, cs_item_id, runtime_item_id, filesystem_id)

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

    def find_cs_with_filesystem(self, base_url, expected_fs_type=None):
        """
        First the first CS that contains the specified filesystem and returns
        its URL
        """
        clustered_services = self.find(self.ms1, base_url,
                                       "vcs-clustered-service", True)
        for cs_url in clustered_services:
            fs_url = self.get_cs_filesystem(cs_url)
            if fs_url:
                fs_type = self.excl_inherit_symbol(self.get_props_from_url(
                    self.ms1, fs_url, "type"))
                if expected_fs_type == None or \
                   fs_type.lower() == expected_fs_type.lower():
                    return cs_url
        return None

    def get_cs_filesystem(self, cs_url):
        """
        Returns URL of the filesystem under the specified clustered service
        """
        filesystems = self.find(self.ms1, cs_url, "file-system", True,
            assert_not_empty=False)

        if filesystems:
            return filesystems[0]
        return None

    def get_cs_app(self, cs_url):
        """
        Returns URL of the application under the specified clustered service
        (both "lsb-runtime" and "service" item types are supported)
        """
        services = self.find(self.ms1, cs_url, "service", True,
            assert_not_empty=False)

        # Backward compatibility
        lsb_runtimes = self.find(self.ms1, cs_url, "lsb-runtime", True,
            assert_not_empty=False)

        apps = services + lsb_runtimes
        if apps:
            return apps[0]
        return None

    def get_res_state_per_node(self, node_filename, resource_name):
        """
        @arg (str) node_filename  The node where to run the hares command
        @arg (str) resource_name  Name of the resource
        @ret (dict) Status of the given resource per node
        """
        cmd = self.vcs.get_hares_state_cmd() + resource_name
        stdout, stderr, rc = self.run_command(node_filename,
                                              cmd, su_root=True)
        self.assertEqual(0, rc)
        self.assertEqual([], stderr)

        res_state_per_node = {}
        for line in stdout[1:]:
            match = re.match(r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$", line)
            self.assertNotEqual(None, match)
            node = match.group(3)
            state = match.group(4)
            res_state_per_node[node] = state.lower()

        return res_state_per_node

    @staticmethod
    def res_state_filter(res_state, state_filter):
        """
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

    def is_filesystem_mounted(self, node_filename, mountpoint):
        """
        @arg (str) node_filename The node to check
        @arg (str) mountpoint    Mount point on the node
        @ret (bool) True if the mountpoint is mounted, otherwise False
        """
        cmd = "/bin/mount -l"
        stdout, stderr, rc = self.run_command(node_filename,
            cmd, su_root=True)
        self.assertEqual(0, rc)
        self.assertEqual([], stderr)

        # Sample output:
        # /dev/mapper/vg_root-vg_1_home on /home type ext4 (rw)

        search_str = " on {0} ".format(mountpoint.rstrip("/"))
        return search_str in "\n".join(stdout)

    def verify_filesystem_rw(self, node_filename, mountpoint):
        """
        @arg (str) node_filename The node to check
        @arg (str) mountpoint    Mount point on the node
        """

        test_str = " ".join(100 * ["Lorem Ipsum dolor sit amet"])
        test_file = mountpoint.rstrip("/") + "/test_story3809.txt"

        # Write to a test file
        cmd = "/bin/echo '{0}' > '{1}'".format(test_str, test_file)
        stdout, stderr, rc = self.run_command(node_filename,
                                              cmd, su_root=True)
        self.assertEqual(0, rc)
        self.assertEqual([], stdout)
        self.assertEqual([], stderr)

        # Verify contents of the test file
        cmd = "/bin/cat '{0}'".format(test_file)
        stdout, stderr, rc = self.run_command(node_filename,
            cmd, su_root=True)
        self.assertEqual(0, rc)
        self.assertEqual(test_str, " ".join(stdout))
        self.assertEqual([], stderr)

    def verify_mounts(self):
        """
        - Make sure the currently active Mount resource is mounted and
          that is readable and writable
        - Make sure the currently standby Mount resource is not mounted
        """

        # Mount resource should be ONLINE on one node and OFFLINE on the
        # other one
        res_state_per_node = self.get_res_state_per_node(
            self.primary_node,
            self.res["mount"])

        self.assertEqual(1, res_state_per_node.values().count("online"))
        self.assertEqual(1, res_state_per_node.values().count("offline"))

        for node_hostname, state in res_state_per_node.items():
            node_filename = \
                self.get_node_list_by_hostname(node_hostname)[0].filename
            is_fs_mounted = self.is_filesystem_mounted(
                    node_filename, self.mount_path)
            if state == "online":
                # Make sure the currently active Mount resource is mounted and
                # that is readable and writable
                self.assertTrue(is_fs_mounted)
                self.verify_filesystem_rw(node_filename, self.mount_path)
            elif state == "offline":
                # Make sure the currently standby Mount resource is not mounted
                self.assertFalse(is_fs_mounted)
            else:
                self.fail()

    @attr('all', 'non-revert', 'physical')
    def test_02_p_vcs_vxvm_verify_resources(self):
        """
        @tms_id: litpcds_3809_tc02
        @tms_requirements_id: LITPCDS-3809
        @tms_title: vcs vxvm verify resources
        @tms_description:
        Test case to make sure the status of Mount resources
        matches the availability model
        @tms_test_steps:
        @step: execute hares -state on each resource
        @result: the Disk Group resource, Volume resource and Mount
        resource are ONLINE on one of the nodes and OFFLINE on the other one
        @result: the currently active Mount resource is mounted and
        that is readable and writable
        @result: Make sure the currently standby Mount resource is not mounted
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """

        resources = [
            self.res["app"],
            self.res["diskgrp"],
        ]
        for resource in resources:
            # Each resource should be ONLINE on one node and OFFLINE on the
            # other one
            res_state_per_node = self.get_res_state_per_node(
                self.primary_node, resource)
            self.assertEqual(1, res_state_per_node.values().count("online"))
            self.assertEqual(1, res_state_per_node.values().count("offline"))

        self.verify_mounts()

    @attr('all', 'non-revert', 'physical')
    def test_03_p_vcs_vxvm_hagrp_switch(self):
        """
        @tms_id: litpcds_3809_tc03
        @tms_requirements_id: LITPCDS-3809
        @tms_title: vcs vxvm verify resources
        @tms_description:
        Test case to make sure the status of Mount resources
        matches the availability model
        @tms_test_steps:
        @step: Find which node has the lsb-wrapper resource in ONLINE state
        @result: node found
        @step: execute "hagrp -switch" command, switch all CS resources to the
        other node
        @result: the Mount and LSB application resources are now ONLINE
        on this node and OFFLINE on the other one
        @result: the currently active Mount resource is mounted and
        that is readable and writable
        @result: the currently standby Mount resource is not mounted
        @step: execute "hagrp -switch" command, switch all CS resources again,
        back to the original node
        @result:the Mount and LSB application resources are now ONLINE
        on this node and OFFLINE on the other one
        @result: the currently active Mount resource is mounted and
        that is readable and writable
        @result: the currently standby Mount resource is not mounted
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """

        poll_count = 12
        poll_interval_sec = 10

        # App resource should be ONLINE on one node and OFFLINE on the
        # other one
        res_state_per_node = self.get_res_state_per_node(
            self.primary_node, self.res["app"])
        self.assertEqual(1, res_state_per_node.values().count("online"))
        self.assertEqual(1, res_state_per_node.values().count("offline"))

        # Group should be temporarily switched to the node where
        # the App was originally offline
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
                self.res["app"],
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
            elif poll_no < poll_count:
                poll_no += 1
            else:
                self.fail()

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
                self.res["app"],
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
            elif poll_no < poll_count:
                poll_no += 1
            else:
                self.fail()

        self.assertEqual(1, res_state_per_node.values().count("online"))
        self.assertEqual(1, res_state_per_node.values().count("offline"))

        # Verify if the FS is mounted as expected
        self.verify_mounts()

    @attr('all', 'non-revert', 'physical')
    def test_07_n_vcs_inherit_non_vxfs_fs(self):
        """
        @tms_id: litpcds_3809_tc07
        @tms_requirements_id: LITPCDS-3809
        @tms_title: vcs inherit non vxfs filesystem
        @tms_description:
        Test to verify that LITP plan will fail to create when an
        LSB-runtime item contains a file-system of invalid type
        @tms_test_steps:
        @step: create vcs-clustered-service and lsb-runtime item
        @result: items created
        @step: Within the lsb-runtime item, inherit a file-system of different
        type than VxFS
        @result: item inherited
        @step: create plan
        @result: plan fails
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """

        app_id = "test_app_story3809"
        app_name = "test_app_story3809"
        app_service_name = "test_service_story3809"

        cs_id = "test_cs_story3809"
        cs_name = "test_cs_story3809"
        cs_url = self.cluster_url + "/services/" + cs_id
        cs_class = "vcs-clustered-service"
        cs_options = \
            "active={0} standby={1} name='{2}' node_list='{3}'".format(
                1, 1, cs_name, ",".join(self.node_vnames[0:2]))
        self.execute_cli_create_cmd(self.ms1, cs_url, cs_class, cs_options)

        app_url = cs_url + "/runtimes/" + app_id
        app_class = "lsb-runtime"
        app_options = "name='{0}' service_name='{1}'".format(
            app_name, app_service_name)
        self.execute_cli_create_cmd(self.ms1, app_url, app_class, app_options)

        fs_url = app_url + "/filesystems/" + self.fs_id
        fs_options = "mount_point='{0}' type='ext4'".format(self.mount_path)
        self.execute_cli_inherit_cmd(self.ms1, fs_url, self.fs_url, fs_options)

        self.execute_cli_createplan_cmd(self.ms1, expect_positive=False)

    @attr('all', 'non-revert', 'physical')
    def test_08_n_vcs_parallel_cs(self):
        """
        @tms_id: litpcds_3809_tc08
        @tms_requirements_id: LITPCDS-3809
        @tms_title: vcs parallel cluster service
        @tms_description:
        Test to verify that LITP plan will fail to create when the VxFS is
        used in a parallel CS
        @tms_test_steps:
        @step: Model a parallel VCS cluster service (active=2, standby=0)
        with a single lsb-runtime item containing an lsb-wrapper application
        @result:parallel VCS cluster service modelled
        @step: Add both nodes to the cluster service
        @result: nodes added to cluster service
        @step: Within the lsb-runtime item, inherit the existing VxFS
        file-system
        @result: file-system inherit
        @step: create plan
        @result: plan fails
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """

        app_id = "test_app_story3809"
        app_name = "test_app_story3809"
        app_service_name = "test_service_story3809"

        cs_id = "test_cs_story3809"
        cs_name = "test_cs_story3809"
        cs_url = self.cluster_url + "/services/" + cs_id
        cs_class = "vcs-clustered-service"
        cs_options = \
            "active={0} standby={1} name='{2}' node_list='{3}'".format(
                2, 0, cs_name, ",".join(self.node_vnames[0:2]))
        self.execute_cli_create_cmd(self.ms1, cs_url, cs_class, cs_options)

        app_url = cs_url + "/runtimes/" + app_id
        app_class = "lsb-runtime"
        app_options = "name='{0}' service_name='{1}'".format(
            app_name, app_service_name)
        self.execute_cli_create_cmd(self.ms1, app_url, app_class, app_options)

        fs_url = app_url + "/filesystems/" + self.fs_id
        fs_options = "mount_point='{0}' type='vxfs'".format(self.mount_path)
        self.execute_cli_inherit_cmd(self.ms1, fs_url, self.fs_url, fs_options)

        self.execute_cli_createplan_cmd(self.ms1, expect_positive=False)

    @attr('all', 'non-revert', 'physical')
    def test_09_n_vcs_1node_cs(self):
        """
        @tms_id: litpcds_3809_tc09
        @tms_requirements_id: LITPCDS-3809
        @tms_title: vcs 1 node cluster service
        @tms_description:
        Test to verify that LITP plan will fail to create when the VxFS is
        used in a parallel CS
        @tms_test_steps:
        @step:  Model a single-node VCS CS (active=1, standby=0) with a single
              lsb-runtime item containing an lsb-wrapper application
        @result:single-node VCS cluster service modelled
        @step: Add node1 to the cluster service
        @result: node added to cluster service
        @step: Within the lsb-runtime item, inherit the existing VxFS
        file-system
        @result: file-system inherit
        @step: create plan
        @result: plan fails
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """

        app_id = "test_app_story3809"
        app_name = "test_app_story3809"
        app_service_name = "test_service_story3809"

        cs_id = "test_cs_story3809"
        cs_name = "test_cs_story3809"
        cs_url = self.cluster_url + "/services/" + cs_id
        cs_class = "vcs-clustered-service"
        cs_options = \
            "active={0} standby={1} name='{2}' node_list='{3}'".format(
                1, 0, cs_name, ",".join(self.node_vnames[0:1]))
        self.execute_cli_create_cmd(self.ms1, cs_url, cs_class, cs_options)

        app_url = cs_url + "/runtimes/" + app_id
        app_class = "lsb-runtime"
        app_options = "name='{0}' service_name='{1}'".format(
            app_name, app_service_name)
        self.execute_cli_create_cmd(self.ms1, app_url, app_class, app_options)

        fs_url = app_url + "/filesystems/" + self.fs_id
        fs_options = "mount_point='{0}' type='vxfs'".format(self.mount_path)
        self.execute_cli_inherit_cmd(self.ms1, fs_url, self.fs_url, fs_options)

        self.execute_cli_createplan_cmd(self.ms1, expect_positive=False)

    @attr('all', 'non-revert', 'physical')
    def test_10_n_vcs_2cs_inherit_same_fs(self):
        """
        @tms_id: litpcds_3809_tc010
        @tms_requirements_id: LITPCDS-3809
        @tms_title: vcs 2 cluster services inherit same file system
        @tms_description:
        Test to verify that LITP plan will fail to create when the same
        VxFS is used in two different LSB runtime items
        @tms_test_steps:
        @step: Model two failover VCS CS (active=1, standby=1), each with
              a single lsb-runtime item containing an lsb-wrapper application
        @result:single-node VCS cluster service modelled
        @step: Add both nodes to the cluster service
        @result: node added to cluster service
        @step: Within the lsb-runtime item of each CS, inherit the existing
              VxFS file-system (the same file-system in both CS)
        @result: file-system inherited
        @step: create plan
        @result: plan fails
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """

        app_id = "test_app_story3809"
        app_name = "test_app_story3809"
        app_service_name = "test_service_story3809"

        cs_id = "test_cs_story3809"
        cs_name = "test_cs_story3809"
        cs_url = self.cluster_url + "/services/" + cs_id
        cs_class = "vcs-clustered-service"
        cs_options = \
            "active={0} standby={1} name='{2}' node_list='{3}'".format(
                1, 1, cs_name, ",".join(self.node_vnames[0:2]))
        self.execute_cli_create_cmd(self.ms1, cs_url, cs_class, cs_options)

        app_url = cs_url + "/runtimes/" + app_id
        app_class = "lsb-runtime"
        app_options = "name='{0}' service_name='{1}'".format(
            app_name, app_service_name)
        self.execute_cli_create_cmd(self.ms1, app_url, app_class, app_options)

        fs_url = app_url + "/filesystems/" + self.fs_id
        fs_options = "mount_point='{0}' type='vxfs'".format(self.mount_path)
        self.execute_cli_inherit_cmd(self.ms1, fs_url, self.fs_url, fs_options)

        self.execute_cli_createplan_cmd(self.ms1, expect_positive=False)

    @attr('all', 'non-revert', 'physical')
    def test_11_n_vcs_fs_inherited_twice(self):
        """
        @tms_id: litpcds_3809_tc011
        @tms_requirements_id: LITPCDS-3809
        @tms_title: vcs file system inherited twice
        @tms_description:
        Test to verify that LITP plan will fail to create when the same
            VxFS is inherited twice in the same LSB runtime item
        @tms_test_steps:
        @step: Model a failover VCS CS (active=1, standby=1) with a single
              lsb-runtime item containing an lsb-wrapper application
        @result: failover VCS cluster service modelled
        @step: Add both nodes to the cluster service
        @result: node added to cluster service
        @step: Within the lsb-runtime item, inherit two items pointing to the
              same file-system
        @result: file-system inherited
        @step: create plan
        @result: plan fails
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """

        app_id = "test_app_story3809"
        app_name = "test_app_story3809"
        app_service_name = "test_service_story3809"

        cs_id = "test_cs_story3809"
        cs_name = "test_cs_story3809"
        cs_url = self.cluster_url + "/services/" + cs_id
        cs_class = "vcs-clustered-service"
        cs_options = \
            "active={0} standby={1} name='{2}' node_list='{3}'".format(
                1, 1, cs_name, ",".join(self.node_vnames[0:2]))
        self.execute_cli_create_cmd(self.ms1, cs_url, cs_class, cs_options)

        app_url = cs_url + "/runtimes/" + app_id
        app_class = "lsb-runtime"
        app_options = "name='{0}' service_name='{1}'".format(
            app_name, app_service_name)
        self.execute_cli_create_cmd(self.ms1, app_url, app_class, app_options)

        fs_url_1 = app_url + "/filesystems/" + self.fs_id + "_1"
        fs_url_2 = app_url + "/filesystems/" + self.fs_id + "_2"
        fs_options = "mount_point='{0}' type='vxfs'".format(self.mount_path)
        self.execute_cli_inherit_cmd(self.ms1, fs_url_1,
            self.fs_url, fs_options)
        self.execute_cli_inherit_cmd(self.ms1, fs_url_2,
            self.fs_url, fs_options)

        self.execute_cli_createplan_cmd(self.ms1, expect_positive=False)

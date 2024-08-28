"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     February 2018
@author:    Donnchadh mac Suibhne
@summary:   Integration Tests
            Agile: TORF-107496
"""
from vcs_utils import VCSUtils
import test_constants
from litp_generic_test import GenericTest, attr
from redhat_cmd_utils import RHCmdUtils


class Story107496(GenericTest):
    """
    TORF-107496:
        As a LITP user I want to update VIPs in my VCS Service Group so that
        my application can use different IPs if required

    This testset relies on items created during testset_story5173, so it is
    required that that testset must be run first.

    """
    def setUp(self):
        """
        Runs before every single test
        """
        # 1. Call super class setup
        super(Story107496, self).setUp()

        self.ms_node = self.get_management_node_filename()
        self.peer_nodes = self.get_managed_node_filenames()

        self.vcs = VCSUtils()
        self.rh_os = RHCmdUtils()

        self.pl_sg_name = "CS_5173_1"
        self.fo_sg_name = "CS_5173_2"

        self.network_name = "net5173"
        self.network_path = self.find(self.ms_node, "/infrastructure",
                                    "collection-of-network")[0] + \
                                    "/{0}".format(self.network_name)

        self.services_path = self.find(self.ms_node, "/deployments",
                                    "collection-of-clustered-service")[0]
        nodes_collection_path = self.find(self.ms_node, "/deployments",
                                    "collection-of-node")[0]
        node_paths = self.find(self.ms_node, nodes_collection_path,
                                    'node')

        pl_sg_path = self.services_path + "/" + self.pl_sg_name
        fo_sg_path = self.services_path + "/" + self.fo_sg_name

        self.ipv4_vip_items = [
            pl_sg_path + "/ipaddresses/vip5173_4",
            pl_sg_path + "/ipaddresses/vip5173_1",
            pl_sg_path + "/ipaddresses/vip5173_3",
            pl_sg_path + "/ipaddresses/vip5173_2",
            fo_sg_path + "/ipaddresses/dup_vip",
            fo_sg_path + "/ipaddresses/fovip5173_2",
            fo_sg_path + "/ipaddresses/fovip5173_1"]

        self.ipv6_vip_items = [
            pl_sg_path + "/ipaddresses/6vip5173_4",
            pl_sg_path + "/ipaddresses/6vip5173_1",
            pl_sg_path + "/ipaddresses/6vip5173_2",
            pl_sg_path + "/ipaddresses/6vip5173_3",
            fo_sg_path + "/ipaddresses/fo6vip5173_2",
            fo_sg_path + "/ipaddresses/fo6vip5173_1"]

        self.ipv4_nic_items = [
            "/ms/network_interfaces/net4",
            node_paths[0] + "/network_interfaces/net9",
            node_paths[1] + "/network_interfaces/net9"]

        self.vip_item_list = self.find(self.ms_node, self.services_path, "vip")

        self.cluster_name = self.find(self.ms_node, "/deployments",
                                      "vcs-cluster")[0].split("/")[-1]

    def tearDown(self):
        """
        Runs after every single test
        """
        cmd = self.rh_os.get_service_running_cmd("litpd")
        _, _, rc = self.run_command(self.ms_node, cmd, su_root=True)
        if rc != 0:
            cmd = self.rh_os.get_systemctl_start_cmd("litpd")
            self.run_command(self.ms_node, cmd, su_root=True)

        super(Story107496, self).tearDown()

    def get_ip_resource(self, ip_address):
        """
        Description:
            Gets the name of the ip resource in vcs based on the given address
        Args:
            ip_address (string): The resource for this IP address will be
                                 returned
        Returns:
            str. The requested resource
        """
        cmd = (self.vcs.get_hares_resource_attribute("", "Address") +
               ' | {0} " {1}$"| {2} "s/ .*//"'.format(test_constants.GREP_PATH,
                                                      ip_address,
                                                      test_constants.SED_PATH))
        stdout, _, _ = self.run_command(self.peer_nodes[0],
                                        cmd,
                                        su_root=True,
                                        default_asserts=True)
        return stdout[0]

    def get_vcs_resources_for_vips(self, vip_item_list):
        """
        Description:
            Returns a list of VCS resource items which correspond to the
            passed in list of VIP model items
        Args:
            vip_item_list (list of strings): list of VIP model items
        Returns:
            list of strings. A list of VCS resource items which correspond to
            the passed in list of VIP model items
        """
        vip_resources = []
        for vip_item in vip_item_list:
            ip_value = self.execute_show_data_cmd(self.ms_node,
                                                vip_item,
                                                "ipaddress")
            # Remove CIDR prefix if any
            ip_value = ip_value.split("/")[0]

            vip_resources.append(self.get_ip_resource(ip_value))

        return vip_resources

    def assert_vcs_resources_use_correct_ips(self,
                                             vip_item_list,
                                             vip_resources):
        """
        Description:
            Asserts that the passed in list of resources are the resources
            used by the passed in list of VIP model items. The order of the
            lists must match.
        Args:
            vip_item_list (list of strings): List of vip model items to check
            vip_resources (list of strings): List of vcs resources to check
        """
        for i in range(0, len(vip_item_list)):
            ip_value = self.execute_show_data_cmd(self.ms_node,
                                                vip_item_list[i],
                                                "ipaddress")
            # Remove CIDR prefix if any
            ip_value = ip_value.split("/")[0]

            ip_resource = self.get_ip_resource(ip_value)
            self.assertEqual(vip_resources[i], ip_resource)

    @attr('all', 'non-revert', 'story107496', 'story107496_tc01')
    def test_01_p_move_vips_new_subnet_force_failed_plan_and_retry(self):
        """
        @tms_id: torf_107496_tc1
        @tms_requirements_id: TORF-107496
        @tms_title: Move VIPs to new subnet, force failed plan during node
        lock and retry
        @tms_description:
        Test to force a subnet and VIPs migration plan (using parallel and
        failover SGs, and IPv4 and IPv6 addresses) to fail while a node is
        locked, and to recreate and run plan and ensure it runs to completion.
        @tms_test_steps:
        @step: Check SGs online in correct numbers
        @result: SGs are online in correct numbers
        @step: Get IP resource names from vcs for error checking later
        @result: IP resource names are recorded in a list
        @step: Update subnet in LITP model
        @result: Updated successfuly
        @step: Update VIPs in LITP model
        @result: Updated successfuly
        @step: Update NICs in LITP model
        @result: Updated successfuly
        @step: Create and start a plan changing VIPs of an SG to different
        subnet
        @result: Plan starts
        @step: While one of the nodes is locked, restart the MS
        @result: Plan fails, MS reboots successfully
        @step: Recreate and run plan
        @result: Plan should succeed. The VIPs should be successfully assigned
        to the same VCS resources as before.
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        new_subnet = "10.10.23.0/24"

        new_ipv4_addresses = [
            "10.10.23.1",
            "10.10.23.2",
            "10.10.23.3",
            "10.10.23.4",
            "10.10.23.5",
            "10.10.23.6",
            "10.10.23.7",
            "10.10.23.8",
            "10.10.23.9",
            "10.10.23.10"]

        new_ipv6_addresses = [
            "2001:abbc:de::4201/64",
            "2001:abbc:de::4202/64",
            "2001:abbc:de::4203/64",
            "2001:abbc:de::4204/64",
            "2001:abbc:de::4205/64",
            "2001:abbc:de::4206/64"]

        self.log('info', "Check SG online in correct numbers")
        self.wait_for_vcs_service_group_online(self.peer_nodes[0],
                                               self.pl_sg_name,
                                               online_count=2)
        self.wait_for_vcs_service_group_online(self.peer_nodes[0],
                                               self.fo_sg_name,
                                               online_count=1)

        self.log('info', "Get ipv4 resource names from vcs")
        ipv4_resources = self.get_vcs_resources_for_vips(self.ipv4_vip_items)

        self.log('info', "Get ipv6 resource names from vcs")
        ipv6_resources = self.get_vcs_resources_for_vips(self.ipv6_vip_items)

        self.log('info', "Update ipv4 subnet")
        self.execute_cli_show_cmd(self.ms_node, self.network_path)
        self.execute_cli_update_cmd(self.ms_node, self.network_path,
                                    "subnet=" + new_subnet)

        self.log('info', "Update vips and nic ipv4s")
        ipv4_counter = 0
        for ipv4_item in self.ipv4_vip_items + self.ipv4_nic_items:
            self.execute_cli_show_cmd(self.ms_node, ipv4_item)
            self.execute_cli_update_cmd(self.ms_node,
                            ipv4_item,
                            "ipaddress=" + new_ipv4_addresses[ipv4_counter])
            ipv4_counter += 1

        self.log('info', "Update ipv6 vips")
        ipv6_counter = 0
        for ipv6_vip_item in self.ipv6_vip_items:
            self.execute_cli_show_cmd(self.ms_node, ipv6_vip_item)
            self.execute_cli_update_cmd(self.ms_node,
                            ipv6_vip_item,
                            "ipaddress=" + new_ipv6_addresses[ipv6_counter])
            ipv6_counter += 1

        self.log('info', "Start plan and wait for node lock")
        self.execute_cli_createplan_cmd(self.ms_node)
        self.execute_cli_runplan_cmd(self.ms_node)

        self.wait_for_task_state(self.ms_node,
                                 "Lock VCS on node .*",
                                 test_constants.PLAN_TASKS_SUCCESS,
                                 seconds_increment=1)

        self.log('info', "After node lock, wait for nic update task to start "
                         "running")
        self.wait_for_task_state(self.ms_node,
                                 'Update eth "eth9" on node "node2"',
                                 test_constants.PLAN_TASKS_RUNNING,
                                 ignore_variables=False,
                                 seconds_increment=1)

        self.log('info', "Reboot MS")
        cmd = "{0} -r now".format(test_constants.SHUTDOWN_PATH)
        self.run_command(self.ms_node, cmd, su_root=True)
        # Wait for MS to go uncontactable
        ms_shutdown_successful = self.wait_for_ping(
                                    self.get_node_att(self.ms_node, 'ipv4'),
                                    False,
                                    timeout_mins=8,
                                    retry_count=2)
        self.assertTrue(ms_shutdown_successful,
                        "MS shut down failed in given time")

        # Wait for MS to come back up
        self.wait_for_node_up(self.ms_node,
                              wait_for_litp=True,
                              timeout_mins=8)

        self.log('info', "Recreate and rerun plan successfully")
        self.run_and_check_plan(self.ms_node, test_constants.PLAN_COMPLETE, 20)

        self.log('info', "Check SG online in correct numbers")
        self.wait_for_vcs_service_group_online(self.peer_nodes[0],
                                               self.pl_sg_name,
                                               online_count=2)
        self.wait_for_vcs_service_group_online(self.peer_nodes[0],
                                               self.fo_sg_name,
                                               online_count=1)

        self.log('info', "Ensure new IPs correspond to same resources as old")
        self.assert_vcs_resources_use_correct_ips(self.ipv4_vip_items,
                                                  ipv4_resources)

        # Check ipv6 resources
        self.assert_vcs_resources_use_correct_ips(self.ipv6_vip_items,
                                                  ipv6_resources)

    @attr('all', 'non-revert', 'story107496', 'story107496_tc02')
    def test_02_p_reduce_subnet_when_vip_changes_not_needed(self):
        """
        @tms_id: torf_107496_tc02
        @tms_requirements_id: TORF-107496
        @tms_title: Reduce subnet when VIP changes not needed
        @tms_description:
        Test to reduce SG subnet with no VIP changes.
        @tms_test_steps:
        @step: Create a plan reducing the subnet of an SG which doesn't
        require VIP updates
        @result: Plan should succeed and VIPs on the subnet should continue
        being assigned to a VCS resource for the SG
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        new_subnet = "10.10.23.0/25"

        self.log('info', "Get list of VIPs in model that are on the correct "
                         "network")
        vip_item_list = [vip_item for vip_item in self.vip_item_list if
                         self.execute_show_data_cmd(self.ms_node, vip_item,
                                        "network_name") == self.network_name]

        self.log('info', "Get VIP resource names from vcs")
        vip_resources = self.get_vcs_resources_for_vips(vip_item_list)

        self.log('info', "Update subnet")
        self.execute_cli_show_cmd(self.ms_node, self.network_path)
        self.execute_cli_update_cmd(self.ms_node, self.network_path,
                                "subnet=" + new_subnet)

        self.log('info', "Apply the model changes")
        self.run_and_check_plan(self.ms_node, test_constants.PLAN_COMPLETE, 20)

        self.log('info', "Ensure VIPs on the subnet are still assigned to a"
                         " VCS resource for the SG")
        self.assert_vcs_resources_use_correct_ips(vip_item_list,
                                                  vip_resources)

    @attr('all', 'non-revert', 'story107496', 'story107496_tc04')
    def test_04_p_change_VIPs_different_subnet_with_frozen_SGs(self):
        """
        @tms_id: torf_107496_tc04
        @tms_requirements_id: TORF-107496
        @tms_title: Change VIPs different subnet with frozen SGs
        @tms_description:
        Test to migrate vips and SGs while one SG is persistently frozen and
        another is temporarily frozen
        @tms_test_steps:
        @step: Create a plan to change VIPs of two SGs to a different subnet
        @result: Plan is created
        @step: Freeze one SG persistently, and the other temporarily
        @result: SGs are frozen
        @step: Run plan
        @result: The plan should run to completion. The VIPs should be
        successfully assigned to the same VCS resources as before.
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        pl_sg_grp = self.vcs.generate_clustered_service_name(
                            self.pl_sg_name,
                            self.cluster_name)

        fo_sg_grp = self.vcs.generate_clustered_service_name(
                            self.fo_sg_name,
                            self.cluster_name)

        new_subnet = "10.10.23.128/25"

        new_ipv4_addresses = [
            "10.10.23.201",
            "10.10.23.202",
            "10.10.23.203",
            "10.10.23.204",
            "10.10.23.205",
            "10.10.23.206",
            "10.10.23.207",
            "10.10.23.208",
            "10.10.23.209",
            "10.10.23.210"]

        self.log('info', "Check SG online in correct numbers")
        self.wait_for_vcs_service_group_online(self.peer_nodes[0],
                                               self.pl_sg_name,
                                               online_count=2)
        self.wait_for_vcs_service_group_online(self.peer_nodes[0],
                                               self.fo_sg_name,
                                               online_count=1)

        self.log('info', "Get ipv4 resource names from vcs")
        ipv4_resources = self.get_vcs_resources_for_vips(self.ipv4_vip_items)

        self.log('info', "Update ipv4 subnet")
        self.execute_cli_show_cmd(self.ms_node, self.network_path)
        self.execute_cli_update_cmd(self.ms_node, self.network_path,
                                "subnet=" + new_subnet)

        self.log('info', "Update vips and nic ipv4s")
        ipv4_counter = 0
        for ipv4_item in self.ipv4_vip_items + self.ipv4_nic_items:
            self.execute_cli_show_cmd(self.ms_node, ipv4_item)
            self.execute_cli_update_cmd(self.ms_node,
                            ipv4_item,
                            "ipaddress=" + new_ipv4_addresses[ipv4_counter])
            ipv4_counter += 1

        self.log('info', "Set SGs offline")
        for service_group in [pl_sg_grp, fo_sg_grp]:
            cmd = self.vcs.get_hagrp_cmd("-offline {0} -any")\
                .format(service_group)
            self.run_command(self.peer_nodes[0], cmd, su_root=True,
                             default_asserts=True)

            # wait for SGs to go offline
            self.wait_for_vcs_service_group_offline(self.peer_nodes[0],
                                                    service_group,
                                                    offline_count=2)
            # make sure FAULTED is not in SG status
            hastatus_cmd = self.vcs.get_hastatus_sum_cmd() + \
                           '|{0} {1} |{2} {3}'.format(test_constants.GREP_PATH,
                                                      service_group,
                                                      test_constants.GREP_PATH,
                                                      'FAULTED')
            stdout, _, _ = self.run_command(self.peer_nodes[0],
                                            hastatus_cmd,
                                            su_root=True)
            self.assertTrue(stdout == [])

        self.log('info', "Freeze one SG persistently, " \
                            "and the other temporarily")
        cmd = self.vcs.get_hagrp_cmd("-freeze " + pl_sg_grp)
        self.run_command(self.peer_nodes[0], cmd, su_root=True,
                                            default_asserts=True)
        cmd = self.vcs.get_haconf_cmd("-makerw")
        self.run_command(self.peer_nodes[0], cmd, su_root=True)
        cmd = self.vcs.get_hagrp_cmd("-freeze " + fo_sg_grp + " -persistent")
        self.run_command(self.peer_nodes[0], cmd, su_root=True,
                                            default_asserts=True)

        self.log('info', "Create and run plan successfully")
        self.run_and_check_plan(self.ms_node, test_constants.PLAN_COMPLETE, 20)

        self.log('info', "Unfreeze SGs")
        cmd = self.vcs.get_hagrp_cmd("-unfreeze " + pl_sg_grp)
        self.run_command(self.peer_nodes[0], cmd, su_root=True,
                                            default_asserts=True)
        cmd = self.vcs.get_haconf_cmd("-makerw")
        self.run_command(self.peer_nodes[0], cmd, su_root=True)
        cmd = self.vcs.get_hagrp_cmd("-unfreeze " + fo_sg_grp + " -persistent")
        self.run_command(self.peer_nodes[0], cmd, su_root=True,
                                            default_asserts=True)

        self.log('info', "Bring SGs back online")
        for service_group in [pl_sg_grp, fo_sg_grp]:
            cmd = self.vcs.get_hagrp_cmd("-online {0} -any")\
                .format(service_group)
            self.run_command(self.peer_nodes[0], cmd, su_root=True,
                             default_asserts=True)

        self.log('info', "Check SG online in correct numbers")
        self.wait_for_vcs_service_group_online(self.peer_nodes[0],
                                               self.pl_sg_name,
                                               online_count=2)
        self.wait_for_vcs_service_group_online(self.peer_nodes[0],
                                               self.fo_sg_name,
                                               online_count=1)

        self.log('info', "Ensure new IPs correspond to same resources as old")
        self.assert_vcs_resources_use_correct_ips(self.ipv4_vip_items,
                                                  ipv4_resources)

    @attr('all', 'non-revert', 'story107496', 'story107496_tc05')
    def test_05_p_move_ipv4_vips_same_subnet_fo_pl(self):
        """
        @tms_id: torf_107496_tc5
        @tms_requirements_id: TORF-107496
        @tms_title: Move VIPs on the same subnet
        @tms_description:
        Move VIPs on the same subnet, using parallel and failover SGs
        @tms_test_steps:
        @step: Check SGs online in correct numbers
        @result: SGs are online in correct numbers
        @step: Get IP resource names from vcs for error checking later
        @result: IP resource names are recorded in a list
        @step: Update VIPs in LITP model
        @result: Updated successfuly
        @step: Create and run plan to apply changes
        @result: Plan completes successfully
        @step: Check SGs online in correct numbers
        @result: SGs are online in correct numbers
        @step: Check that new IPs use the same resources as the old IPs
        @result: New IPs use the same resources as the old IPs
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        new_ipv4_addresses = [
            "10.10.23.221",
            "10.10.23.222",
            "10.10.23.223",
            "10.10.23.224",
            "10.10.23.225",
            "10.10.23.226",
            "10.10.23.227",
            "10.10.23.228",
            "10.10.23.229",
            "10.10.23.230"]

        self.log('info', "Check SG online in correct numbers")
        self.wait_for_vcs_service_group_online(self.peer_nodes[0],
                                               self.pl_sg_name,
                                               online_count=2)
        self.wait_for_vcs_service_group_online(self.peer_nodes[0],
                                               self.fo_sg_name,
                                               online_count=1)

        self.log('info', "Get ipv4 resource names from vcs")
        ipv4_resources = self.get_vcs_resources_for_vips(self.ipv4_vip_items)

        self.log('info', "Update ipv4 vips")
        ipv4_counter = 0
        for ipv4_vip_item in self.ipv4_vip_items:
            self.execute_cli_show_cmd(self.ms_node, ipv4_vip_item)
            self.execute_cli_update_cmd(self.ms_node,
                               ipv4_vip_item,
                               "ipaddress=" + new_ipv4_addresses[ipv4_counter])
            ipv4_counter += 1

        self.log('info', "Create and run plan successfully")
        self.run_and_check_plan(self.ms_node, test_constants.PLAN_COMPLETE, 20)

        self.log('info', "Check SG online in correct numbers")
        self.wait_for_vcs_service_group_online(self.peer_nodes[0],
                                               self.pl_sg_name,
                                               online_count=2)
        self.wait_for_vcs_service_group_online(self.peer_nodes[0],
                                               self.fo_sg_name,
                                               online_count=1)

        self.log('info', "Ensure new IPs correspond to same resources as old")
        self.assert_vcs_resources_use_correct_ips(self.ipv4_vip_items,
                                                  ipv4_resources)

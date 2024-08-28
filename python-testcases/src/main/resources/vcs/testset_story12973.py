"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     Feb 2016
@author:    Ciaran Reilly
            James Maher
@summary:   Integration Tests
            Agile: STORY-12973
"""

import test_constants
from litp_generic_test import GenericTest, attr
from vcs_utils import VCSUtils
import re

STORY = '12973'


class Story12973(GenericTest):
    """
    LITPCDS-12973:
        As a LITP user I want to add IPs to the NetworkHosts attribute of a VCS
        NIC resource so that the NIC agent can monitor network connectivity
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
        super(Story12973, self).setUp()
        self.management_server = self.get_management_node_filename()
        self.vcs = VCSUtils()

        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.management_server,
                                         '/deployments', 'vcs-cluster')[-1]

        self.network_hosts_urls = self.find(self.management_server,
                                        '/deployments',
                                        'collection-of-vcs-network-host')

        self.net_hosts_urls = self.find(self.management_server,
                                        '/deployments', 'vcs-network-host')

        self.nodes_urls = self.find(self.management_server,
                                    self.vcs_cluster_url,
                                    'node')

        self.node_1 = self.get_node_filename_from_url(self.management_server,
                                                      self.nodes_urls[0])

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story12973, self).tearDown()

    def check_ip_is_on_node(self, res_name, net_host_ip):
        """
        Method that checks if a Network host IP address exists on a node

        """
        ip_chk = False
        res_dict = self.run_vcs_hares_display_command(self.node_1, res_name,
                                                      attribute='NetworkHosts')
        if net_host_ip in res_dict['NetworkHosts'][0]['VALUE']:
            ip_chk = True
        return ip_chk

    def arrange_model_items(self):
        """
        Method used to arrange the items in a model to a readable list
        ascending order
        """
        def atoi(text):
            """
            Method used to determine if a number exits in a string
            """
            return int(text) if text.isdigit() else text

        def natural_keys(text):
            """
            Method used to determine arrange network hosts in a more readable
            form
            """
            return [atoi(c) for c in re.split("(\\d+)", text.split('/')[-1])]

        return self.net_hosts_urls.sort(key=natural_keys)

    def _save_net_hosts_for_cleanup(self):
        """
        Method that saves the network hosts from the model to a dictionary for
        use as cleanup after the test passes
        :return: nethosts_dict: filled with network hosts configurations
        """
        nethosts_dict = {"NetHosts": [], "Options": []}

        for net_hosts in self.net_hosts_urls:
            nethosts_dict["NetHosts"].append(net_hosts)
            nethosts_dict["Options"].append(
                self.get_props_from_url(self.management_server, net_hosts))
        return nethosts_dict

    def _create_net_hosts(self, nh_dict):
        """
        Re-create all the removed network hosts from test case 4
        :param nh_dict: The network hosts dictionary with all of the models
         configuration i.e. ip addresses, network names, and urls
        :return: Nothing
        """

        net_hosts_urls = nh_dict['NetHosts']
        nh_ip_addrs = []
        net_names = []
        props = 'ip={0} network_name={1}'

        for addrs_and_names in nh_dict['Options']:
            nh_ip_addrs.append(addrs_and_names['ip'])
            net_names.append(addrs_and_names['network_name'])

        for urls, addrs, names in zip(net_hosts_urls, nh_ip_addrs, net_names):
            self.execute_cli_create_cmd(self.management_server, urls,
                                        'vcs-network-host',
                                        props.format(addrs, names),
                                        add_to_cleanup=False)

    @attr('all', 'non-revert', 'story12973', 'story12973_tc01')
    def test_01_p_add_remove_ip_ipv4(self):
        """
        @tms_id: litpcds_12973_tc01
        @tms_requirements_id: LITPCDS-12973
        @tms_title: VCS nic resource
        @tms_description: To ensure that a new IP address can be added
        to the NetworkHosts attribute of a VCS NIC resource and then removed
        @tms_test_steps:
          @step: Create 3 Network hosts in model
          @result: model is updated as expected
          @step: remove an existing network host
          @result: model is updated as expected
          @step: create and run the plan
          @result: plan execution begins
          @step: Run litpd restart
          @result: plan execution halts
          @step: run create and run plan
          @result: plan recreates and runs remaining tasks to completion
          @step: ensure new network hosts are added to node
          @result: node updated as expected
          @step: ensure removed network host is not present on node
          @result: network host not present on node
          @step: remove added network host and recreate host that was removed
          @result: model updated as expected
          @step: create and run the plan
          @result: plan runs to completion
          @step: validate network host and IP is removed from host and node
          @result: items removed as expected
          @step: validate original network hosts recreated.
          @result: network hosts recreated as expected
        @tms_test_precondition: None
        @tms_execution_type: Automated
        """

        network_names = ['/nh22', '/nh23', '/nh24']
        network_props = ['ip=172.16.200.24 network_name=traffic2',
                         'ip=172.16.200.26 network_name=traffic2',
                         'ip=172.16.101.32 network_name=mgmt']

        old_net_props = 'ip=172.16.200.131 network_name=traffic2'

        # Step 1: Create 3 Network hosts, already created in model
        # Step 2- Remove previously created network host in this case nh15
        # with traffic 2
        self.execute_cli_remove_cmd(self.management_server,
                                    self.network_hosts_urls[0] + '/nh15',
                                    add_to_cleanup=False)

        for name, props in zip(network_names, network_props):
            self.execute_cli_create_cmd(self.management_server,
                                        self.network_hosts_urls[0] + name,
                                        'vcs-network-host',
                                        props, add_to_cleanup=False)
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        phase_2_success = ('Reconfigure NIC resource "Res_NIC_c1_eth5"'
                            'on node "node1"')
        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                     phase_2_success,
                                                     test_constants.
                                                     PLAN_TASKS_SUCCESS,
                                                     False),
                            'CS is not updated'
                            )
        # Step 3
        # Idempotency test run litpd restart
        self.restart_litpd_service(self.management_server)

        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 10)

        # Step 4: Ensure network host gets created on ms with corresponding IP
        self.execute_cli_show_cmd(self.management_server,
                                  self.network_hosts_urls[0] +
                                  network_names[0])

        nh_ip = self.get_props_from_url(self.management_server,
                                        self.network_hosts_urls[0] +
                                        network_names[0],
                                        filter_prop='ip')
        self.assertEqual(nh_ip, '172.16.200.24')

        # Step 5: Ensure new IP is included on the node
        ip_chk = self.check_ip_is_on_node('Res_NIC_c1_eth5', '172.16.200.24')
        self.assertTrue(ip_chk)

        # Step 6: Ensure previously created network host is removed on ms
        # and node
        self.execute_cli_show_cmd(self.management_server,
                                  self.network_hosts_urls[0] + '/nh15',
                                  expect_positive=False)

        ip_chk = self.check_ip_is_on_node('Res_NIC_c1_eth5', '172.16.200.131')
        self.assertFalse(ip_chk)

        # Step 7: Remove created network hosts and re-create previously
        # removed network host
        for name in network_names:
            self.execute_cli_remove_cmd(self.management_server,
                                        self.network_hosts_urls[0] + name,
                                        add_to_cleanup=False)

        self.execute_cli_create_cmd(self.management_server,
                                    self.network_hosts_urls[0] + '/nh15',
                                    'vcs-network-host',
                                    old_net_props, add_to_cleanup=False)

        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 10)

        # Step 7: Validate network hosts get removed on ms
        self.execute_cli_show_cmd(self.management_server,
                                  self.network_hosts_urls[0] +
                                  network_names[0], expect_positive=False)

        # Step 8: Validate new IP is removed on the node
        ip_chk = self.check_ip_is_on_node('Res_NIC_c1_eth5', '172.16.200.24')
        self.assertFalse(ip_chk)

        # Step 10: Validate network host gets created again
        self.execute_cli_show_cmd(self.management_server,
                                  self.network_hosts_urls[0] + '/nh15')

    @attr('all', 'non-revert', 'story12973', 'story12973_tc04')
    def test_04_p_add_nic_no_networkHosts(self):
        """
        @tms_id: litpcds_12973_tc02
        @tms_requirements_id: LITPCDS-12973
        @tms_title: Check network hosts
        @tms_description: Test to ensure that a new IP address can be added to
        the NetworkHosts attribute of a VCS NIC when previously none were
        defined
        @tms_test_steps:
          @step:  Remove all network hosts from model
          @result: network hosts removed successfully
          @step: Check route gateway IP is not applied to node,
          it is now empty.
          @result: gateway IP is no longer on node
          @step: Add a new network host
          @result: host added and plan runs to success
          @step: Verify the newly added network host is added and replaces the
               empty network hosts
          @result: network host updated as expected
        @tms_test_precondition: None
        @tms_execution_type: Automated
        """
        network_props = 'ip=192.168.0.16 network_name=mgmt'

        # Step 1: Remove all network hosts
        # Network Hosts already exists in model
        # These functions are used for sorting the Network Hosts
        self.arrange_model_items()

        nethosts_dict = self._save_net_hosts_for_cleanup()

        for name in self.net_hosts_urls:
            self.execute_cli_remove_cmd(self.management_server, name)

        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 10)

        # Step 2: Check route gateway IP is no longer applied to node
        # Updated due to the introduction of LITPCDS-13258
        # Gateway no longer set when no network host exists
        gw_urls = self.find(self.management_server, '/infrastructure', 'route')

        gw_addr = self.get_props_from_url(self.management_server, gw_urls[1],
                                          filter_prop='gateway')
        self.assertEqual(gw_addr, '192.168.0.1')
        # Updated due to the introduction of LITPCDS-13258
        # Gateway no longer set when no network host exists
        gw_chk = self.check_ip_is_on_node('Res_NIC_c1_br0', '')
        self.assertTrue(gw_chk)

        # Step 3: Add a new network host
        self.execute_cli_create_cmd(self.management_server,
                                    self.net_hosts_urls[0].strip('nh1') +
                                    'nh10',
                                    'vcs-network-host',
                                    network_props,
                                    add_to_cleanup=False)

        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 10)

        # Step 4: Verify the newly added network host is added and replaces
        # the empty network hosts
        gw_chk = self.check_ip_is_on_node('Res_NIC_c1_br0', '192.168.0.16')
        self.assertTrue(gw_chk)

        # Clean up by adding the removed network hosts back to the model
        self._create_net_hosts(nethosts_dict)

        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 10)

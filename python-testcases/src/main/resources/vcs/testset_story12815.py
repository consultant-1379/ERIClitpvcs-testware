#!/usr/bin/env python
"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     Jan 2016
@author:    David Gibbons
@summary:   Agile: LITPCDS-12815
"""

import test_constants
from litp_generic_test import GenericTest, attr
from vcs_utils import VCSUtils


TEST_02_MACADDRESS_IF1 = 'AA:BB:CC:AA:BB:CC'
TEST_02_MACADDRESS_IF2 = 'AA:BB:CC:CC:BB:AA'
TEST_02_MACADDRESS_LOW = 'AA:BB:CC:CC:AA:BB'


class Story12815(GenericTest):
    """
    As a LITP User I want an update of the macaddress property to trigger a
    reconfigure of the /etc/llttab file so that I can replace a blade or
    network related hardware
    """

    def setUp(self):
        """
        Description:
            Runs before every single test
        """
        super(Story12815, self).setUp()
        self.vcs = VCSUtils()
        self.management_server = self.get_management_node_filename()
        self.managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.managed_nodes[0]
        self.secondary_node = self.managed_nodes[1]
        self.vcs_cluster_url = self.find(self.management_server,
                                         "/deployments", "vcs-cluster")[-1]
        self.node_urls = []
        for node in self.managed_nodes:
            url = self.get_node_url_from_filename(self.management_server, node)
            self.node_urls.append(url)
        self.llt_nets = str(self.get_props_from_url(self.management_server,
                                                    self.vcs_cluster_url,
                                                    'llt_nets')).split(",")
        self.low_prio_net = str(self.get_props_from_url(self.management_server,
                                                        self.vcs_cluster_url,
                                                        'low_prio_net'))

    def tearDown(self):
        """
        Description:
            Runs after every single test
        """
        super(Story12815, self).tearDown()

    def _get_llt_interfaces_and_devices(self, hostname):
        """
        A method to get a dictionary with the iface_url and the device name
        fof LLTs on the vcs-cluster
        :args: node_hsta (string) the URL of the node
        :return: dictionary with iface paths and devices. For example
        {'/deployments/d1/clusters/c1/nodes/n1/network_interfaces/if2': 'eth2',
         '/deployments/d1/clusters/c1/nodes/n1/network_interfaces/if3': 'eth3'}
        """
        node_url = None
        for url in self.node_urls:
            item_hostname = self.get_props_from_url(self.management_server,
                                                    url,
                                                    'hostname')
            if item_hostname == hostname:
                node_url = url
                break

        interfaces_and_devices = {}
        interface_urls = self.find_children_of_collect(
            self.management_server, node_url, 'network-interface')
        for interface_url in interface_urls:
            network_name = self.get_props_from_url(self.management_server,
                                                   interface_url,
                                                   'network_name')
            if network_name in self.llt_nets:
                device_name = self.get_props_from_url(
                    self.management_server, interface_url, 'device_name')
                interfaces_and_devices[interface_url] = device_name

        print 'interfaces_and_devices: {0}'.format(interfaces_and_devices)
        return interfaces_and_devices

    def _get_low_pri_interface_and_device(self, hostname):
        """
        A method to get a tuple with the iface_url and the device name
        for the low priority interface on the vcs-cluster for hostname
        :args: hostname (string) the hostname of the node
        :return: dictionary with iface paths and devices. For example
        ('/deployments/d1/clusters/c1/nodes/n1/network_interfaces/if0', 'eth0')
        """
        node_url = None
        for url in self.node_urls:
            item_hostname = self.get_props_from_url(self.management_server,
                                                    url,
                                                    'hostname')
            if item_hostname == hostname:
                node_url = url
                break

        interface_urls = self.find_children_of_collect(
            self.management_server, node_url, 'network-interface')
        for interface_url in interface_urls:
            network_name = self.get_props_from_url(self.management_server,
                                                   interface_url,
                                                   'network_name')

            if network_name == self.low_prio_net:
                macaddress = self.get_props_from_url(
                    self.management_server, interface_url, 'macaddress')

                if macaddress:
                    device_name = self.get_props_from_url(
                        self.management_server, interface_url,
                        'device_name')
                    print 'low prio: {0} {1}'.format(interface_url,
                                                     device_name)
                    return interface_url, device_name
                else:
                    # Must search for eth using bridge
                    item_type = self.execute_show_data_cmd(
                        self.management_server, interface_url, "type")
                    if item_type == "bridge":
                        bridge_device_name = self.get_props_from_url(
                            self.management_server, interface_url,
                            'device_name')

                        _interface_url = None
                        for _url in interface_urls:
                            _bridge = self.get_props_from_url(
                                self.management_server, _url, 'bridge')
                            if _bridge == bridge_device_name:
                                _interface_url = _url
                                break

                        device_name = self.get_props_from_url(
                            self.management_server, _interface_url,
                            'device_name')
                        print 'low prio: {0} {1}'.format(_interface_url,
                                                         device_name)
                        return _interface_url, device_name

    def run_ifconfig(self, device, initial_mac, node, su_timeout=False):
        """
        Runs ifconfig command with specified device and mac address on node.
        Args:
            device(str): Device name of eth item.
            initial_mac(str): MAC address
            node(str): Node to run ifconfig command on.
            su_timeout(boolean): Timeout for root commands to finish running.
                               Default value is False.
        """
        ifconfig = self.net.get_ifconfig_cmd()

        cmd = '{0} {1} hw ether {2}'.format(
            ifconfig, device, initial_mac)

        if su_timeout:
            self.run_command(node, cmd, su_root=True, default_asserts=True,
                             su_timeout_secs=300)

        self.run_command(node, cmd, su_root=True, default_asserts=True)

    def check_lltab_file(self, device, node, linkcmd):
        """
        Checks the /etc/lltab file for eth items on node.
        Args:
            device(str): Eth item
            node(str): Node to run command on.
            linkcmd(str): Command used to assert the /etc/lltab contents.
        """
        cmd = '/bin/cat {0} | grep {1}'.format(
            test_constants.LLTTAB_PATH, device)

        iface_output, _, _ = self.run_command(
            node, cmd, su_root=True, default_asserts=True)
        self.assertEqual(iface_output[0], linkcmd,
                         'The interface {0} is not present in {1} '
                         'file '.format(device, test_constants.LLTTAB_PATH))

    def retrieve_props(self, url):
        """
        Retrieves the mac address from the specified url.
        Args:
            url(str): The url of the eth item.
        Return: mac_address(str): mac address
        """
        mac_address = self.get_props_from_url(
            self.management_server, url, 'macaddress')

        return mac_address

    def update_mac_address(self, url, mac):
        """
        Updates the mac address on the specified url.
        Args:
            url(str): The url of the eth item.
            mac(str): The MAC address used to update the macaddress prop.
        """
        self.execute_cli_update_cmd(self.management_server, url,
                                    "macaddress={0}".format(mac))

    # @attr('pre-reg', 'non-revert', 'story12815', 'story12815_tc01')
    def obsolete_01_p_update_one_mac_address(self):
        """
        Testing of mac update in test_02_p_update_all_macs_on_one_node is
        sufficient coverage.
        #tms_id: litpcds_12815_tc1
        #tms_requirements_id: LITPCDS-12815
        #tms_title: update one mac address
        #tms_description:
        Update a MAC address on one of the nodes. Ensure that the new MAC
            address is in the /etc/llttab file. It should be the only entry
            in llttab that has changed
        #tms_test_steps:
        #step: update macaddress prop on eth item
        #result: item updated
        #step: create and run plan
        #result: plan is running
        #step: stop plan at phase 3
        #result: plan stops at phase 3
        #step: create and run plan
        #result: plan executes successfully
        #result: /etc/llttab on the node has been updated correctly
        #tms_test_precondition: NA
        #tms_execution_type: Automated
        """
        pass

    @attr('all', 'non-revert', 'story12815', 'story12815_tc02')
    def test_02_p_update_all_macs_on_one_node(self):
        """
        @tms_id: litpcds_12815_tc2
        @tms_requirements_id: LITPCDS-12815
        @tms_title: update all macs on one node
        @tms_description: Update all MAC addresses on one of the nodes -
                          secondary node. Ensure that the new MAC addresses
                          are in the /etc/llttab file. This test covers
                          test_01_p_update_one_mac_address.
        @tms_test_steps:
            @step: Update macaddress prop on eth items on secondary node.
            @result: Eth items updated.
            @step: Create and run plan.
            @result: Plan executes and runs to completion successfully.
            @step: Check that /etc/llttab has been updated.
            @result: /etc/llttab on the node has been updated correctly
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        self.log('info', '1. Get interfaces and devices.')
        interfaces_and_devices = self._get_llt_interfaces_and_devices(
            self.secondary_node)
        interface_url = interfaces_and_devices.keys()[0]
        device = interfaces_and_devices[interface_url]
        interface_url_2 = interfaces_and_devices.keys()[1]
        device_2 = interfaces_and_devices[interface_url_2]

        low_pri_iface_url, low_pri_device =\
            self._get_low_pri_interface_and_device(self.secondary_node)

        self.log('info', '2. Run ifconfig on the secondary node.')
        self.run_ifconfig(device, TEST_02_MACADDRESS_IF1,
                          self.secondary_node)
        self.run_ifconfig(device_2, TEST_02_MACADDRESS_IF2,
                          self.secondary_node)
        self.run_ifconfig(low_pri_device, TEST_02_MACADDRESS_LOW,
                          self.secondary_node, su_timeout=True)

        # Update the mac address of first interface
        self.log('info', '3. Update macaddress prop on eth items on one node.')
        if1_mac_address_initial = self.retrieve_props(interface_url)
        self.update_mac_address(interface_url, TEST_02_MACADDRESS_IF1)

        # Get and then update the mac address of second interface
        if2_mac_address_initial = self.retrieve_props(interface_url_2)
        self.update_mac_address(interface_url_2, TEST_02_MACADDRESS_IF2)

        if3_mac_address_initial = self.retrieve_props(low_pri_iface_url)
        self.update_mac_address(low_pri_iface_url, TEST_02_MACADDRESS_LOW)

        self.log('info', '4. Create and run plan.')
        self.run_and_check_plan(
            self.management_server, test_constants.PLAN_COMPLETE, 10)

        self.log('info', '5. Checking {0} has been updated.'.format(
            test_constants.LLTTAB_PATH))
        cmd = 'link {0} {0}-{1} - ether - -'.format(
            device, TEST_02_MACADDRESS_IF1)
        self.check_lltab_file(device, self.secondary_node, cmd)

        cmd = 'link {0} {0}-{1} - ether - -'.format(
            device_2, TEST_02_MACADDRESS_IF2)
        self.check_lltab_file(device_2, self.secondary_node, cmd)

        # If bridge then bridge is used in llttab, else use device and mac
        bridge_name = self.get_props_from_url(
            self.management_server, low_pri_iface_url, 'bridge')

        if bridge_name:
            linkcmd = 'link-lowpri {0} {0} - ether - -'.format(bridge_name)
            self.check_lltab_file(bridge_name, self.secondary_node, linkcmd)

        else:
            linkcmd = 'link-lowpri {0} {0}-{1} - ether - -'.format(
                low_pri_device, TEST_02_MACADDRESS_LOW)
            self.check_lltab_file(low_pri_device, self.secondary_node, linkcmd)

        # Cleanup
        # Note: If clean up is not done, then errors are expected when a reboot
        # is performed after this test. This is due to the mismatch between
        # the hardware MAC address and the manually updated MAC address

        self.log('info', '6. Performing cleanup.')
        self.run_ifconfig(device, if1_mac_address_initial,
                          self.secondary_node)
        self.update_mac_address(interface_url, if1_mac_address_initial)

        self.run_ifconfig(device_2, if2_mac_address_initial,
                          self.secondary_node)
        self.update_mac_address(interface_url_2, if2_mac_address_initial)

        self.run_ifconfig(low_pri_device, if3_mac_address_initial,
                          self.secondary_node, su_timeout=True)
        self.update_mac_address(low_pri_iface_url, if3_mac_address_initial)

        self.run_and_check_plan(
            self.management_server, test_constants.PLAN_COMPLETE, 10)

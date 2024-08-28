#!/usr/bin/env python
"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     Aug 2015
@author:    Stefan Ulian
@summary:   Agile: LITPCDS-10741
"""

import test_constants
from litp_generic_test import GenericTest, attr
from vcs_utils import VCSUtils


class Story10741(GenericTest):
    """
    As a LITP User I want to remove IP entries from the VCS NIC Resource
    NetworkHost attribute so that any network reconfiguration will not lead
    to NIC resource faults
    """

    def setUp(self):
        """
        Description:
            Runs before every single test
        """
        super(Story10741, self).setUp()
        self.vcs = VCSUtils()
        self.ms1 = self.get_management_node_filename()
        self.managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.managed_nodes[0]
        self.node_urls = []
        for node in self.managed_nodes:
            url = self.get_node_url_from_filename(self.ms1, node)
            self.node_urls.append(url)
        self.cluster_url = self.find(self.ms1, "/deployments",
                                     "vcs-cluster")[0]
        self.cluster_name = self.cluster_url.split("/")[-1]
        self.llt_nets = str(self.get_props_from_url(self.ms1,
                                                    self.cluster_url,
                                                    'llt_nets')).split(",")
        net_host_url = self.find(
            self.ms1, self.cluster_url,
            "collection-of-vcs-network-host")[0] + str('/')

        self.network_host_urls = self.find(self.ms1, net_host_url,
                                           "vcs-network-host")
        self.networks = self.find(self.ms1, "/infrastructure", "network")

    def tearDown(self):
        """
        Description:
            Runs after every single test
        """
        super(Story10741, self).tearDown()

    def get_res_state_per_node(self, node_filename, resource_name):
        """
        Description:
            Return VCS resource state on the specified node

        Args:
            node_filename(str): The node where to run the hares command
            resource_name(str): Name of the resource
        Return:
            (dict) Status of the given resource per node
        """
        cmd = self.vcs.get_hares_state_cmd() + resource_name
        hares_state, _, _ = self.run_command(node_filename, cmd, su_root=True,
                                             default_asserts=True)

        return self.vcs.get_resource_state(hares_state)

    def get_route_for_subnet(self, node_url, subnet):
        """
        Description:
            Find the matching route for this network.
            The following algorithm is limited to IPv4 with /24 netmask

        Args:
            node_url(str): URL of the node
            subnet(str): The subnet we test against
        Return:
            (str) The IP address of the network route or None if no matching
                   route was found
        """
        network_route = None
        routes = self.find(self.ms1, node_url, "route")
        for route_url in routes:
            gateway = str(self.get_props_from_url(self.ms1, route_url,
                                                  'gateway'))
            gateway_segments = gateway.split(".")

            # Remove the netmask part
            subnet_addr = subnet.split("/")[0]
            subnet_segments = subnet_addr.split(".")
            if subnet_segments[:-1] == gateway_segments[:-1]:
                network_route = gateway
                break
        return network_route

    def get_hosts_per_network(self):
        """
        Find network hosts for each of the networks present in the LITP Model
        Save them in hosts per network dictionary.
        """
        hosts_per_network = {}

        for host_url in self.network_host_urls:
            net_name = self.get_props_from_url(self.ms1, host_url,
                                               'network_name')
            ip_addr = str(self.get_props_from_url(self.ms1, host_url, 'ip'))

            if not net_name in hosts_per_network:
                hosts_per_network[net_name] = []
            hosts_per_network[net_name].append(ip_addr.upper())

        return hosts_per_network

    def verify_vcs_network_hosts(self):
        """
        Description:
            Utility method for checking if vcs-network-hosts defined
            in LITP Model matches VCS NIC "NetworkHosts" Attribute
            present on managed nodes.
        """
        # Find network hosts for each of the networks present in the LITP Model
        # Save them in hosts per network dictionary.
        hosts_per_network = self.get_hosts_per_network()

        # Verify vcs-network-hosts present in LITP Model matches VCS NIC
        # Resource"NetworkHosts" attribute present on the managed nodes.
        for node_url in self.node_urls:
            node_hostname = self.get_props_from_url(
                self.ms1, node_url, 'hostname')
            interfaces = self.find_children_of_collect(
                self.ms1, node_url, 'network-interface')

            # For each network interface, run hares -display command to list
            # the VCS network hosts and then compare them with the items
            # specified in the model
            for if_url in interfaces:
                network_name = self.get_props_from_url(self.ms1, if_url,
                                                       'network_name')
                # Skip LLT networks
                if network_name in self.llt_nets:
                    continue
                # Only network interfaces with associated network name have a
                # NIC Service Group
                if network_name:
                    dev_name = self.get_props_from_url(
                        self.ms1, if_url, 'device_name')
                    sys = node_hostname
                    res_name = self.vcs.generate_nic_resource_name(
                        self.cluster_name, dev_name)
                    # Ensure the NIC resource is in ONLINE state
                    res_state_per_node = self.get_res_state_per_node(
                        self.primary_node, res_name)
                    self.assertEqual("online", res_state_per_node[sys],
                                     "NIC resource is not in ONLINE state")
                    # Find the NetworkHosts of this node, as they are
                    # seen by VCS
                    cmd = self.vcs.get_hares_resource_attribute(
                        res_name, "NetworkHosts") + " -sys '{0}'".format(sys)
                    net_hosts, _, _ = self.run_command(self.primary_node, cmd,
                                                       su_root=True,
                                                       default_asserts=True)

                    params = net_hosts[1].split(None, 3)
                    out_hosts = params[3].upper().split()
                    if network_name in hosts_per_network:
                        # Compare if the network hosts of this node match
                        # the items specified in the model
                        self.assertEqual(
                            sorted(hosts_per_network[network_name]),
                            sorted(out_hosts), "Network hosts on node don't"
                                               "match those specified in "
                                               "the model.")
                    else:
                        # If no Network Hosts are defined for this network,
                        # find the default route
                        # Find URL of this network
                        network_url = None
                        for net_url in self.networks:
                            name = str(self.get_props_from_url(
                                self.ms1, net_url, 'name'))
                            if name == network_name:
                                network_url = net_url
                                break
                        self.assertNotEqual(None, network_url,
                                            "Default network_url not found.")
                        subnet = str(self.get_props_from_url(
                            self.ms1, network_url, 'subnet'))
                        network_route = self.get_route_for_subnet(node_url,
                                                                  subnet)
                        self.assertNotEqual(None, network_route,
                                            "Default network route not found.")
                        # Ensure the NetworkHosts attribute contains only the
                        # network route, which is the default behaviour when
                        # no network-host items are explicitly set
                        self.assertEqual([network_route], out_hosts,
                                         "Unexpected additional network"
                                         "host items found: {0}".format(
                                             out_hosts))

    # @attr('pre-reg', 'non-revert', 'story10741', 'story10741_tc01')
    def obsolete_01_p_remove_ipv4_vcs_network_hosts(self):
        """
        Test merged with "test_03_p_remove_network_and_vcs_network_hosts".
        #tms_id: litpcds_10741_tc1
        #tms_requirements_id: LITPCDS-10741
        #tms_title: remove ipv4 vcs network hosts
        #tms_description:
            This positive test is checking that LITP can successfully remove
            IPv4 vcs-network-hosts items related with mgmt, traffic and dhcp
            network interfaces.
        #tms_test_steps:
        #step:  Remove IPv4 vcs-network-hosts
        #result: items set to for removal state
        #step: create and run plan
        #result: plan executes successfully
        #result: vcs-network-hosts were removed from VCS NIC Resource
               "NetworkHosts" Attribute on both managed nodes.

        #tms_test_precondition:  VCS cluster with 2 nodes and the following
            Network Hosts layout:
            - management network (low priority network)
                * non-pingable private IPv4 address
                * pingable IPv4 address of MS
            - traffic1 network:
                * pingable IPv4 address of MS
                * non-pingable private IPv4 address
            - dhcp network:
                * non-pingable private IPv4 address
        #tms_execution_type: Automated
        """
        pass

    # @attr('pre-reg', 'non-revert', 'story10741', 'story10741_tc02')
    def obsolete_02_p_remove_ipv6_vcs_network_hosts(self):
        """
        Test merged with "test_03_p_remove_network_and_vcs_network_hosts".
        #tms_id: litpcds_10741_tc2
        #tms_requirements_id: LITPCDS-10741
        #tms_title: remove ipv6 vcs network hosts
        #tms_description:
           This positive test is checking that LITP can successfully remove
            IPv6 vcs-network-hosts items related with traffic network.
        #tms_test_steps:
        #step:  Remove IPv6 vcs-network-hosts
        #result: items set to for removal state
        #step: create and run plan
        #result: plan executes successfully
        #result: vcs-network-hosts were removed from VCS NIC Resource
               NetworkHosts Property.
        #tms_test_precondition:  VCS cluster with 2 nodes and the following
                Network Hosts layout:
                - traffic1 network:
                * non-pingable private IPv6 address
        #tms_execution_type: Automated
        """
        pass

    @attr('all', 'non-revert', 'story10741', 'story10741_tc03')
    def test_03_p_remove_network_and_vcs_network_hosts(self):
        """
        @tms_id: litpcds_10741_tc3
        @tms_requirements_id: LITPCDS-10741
        @tms_title: remove network and vcs network hosts
        @tms_description:
            This positive test is checking that LITP can successfully remove:
            1. IPv4 vcs-network-hosts items related with mgmt, traffic and dhcp
            network interfaces.
            2. IPv6 vcs-network-hosts items related with traffic network.
            3. A network interface and all related "vcs-network-hosts" items.
            This test covers litpcds_10741_tc1 and litpcds_10741_tc2.
        @tms_test_steps:
            @step:  Remove IPv4 vcs-network-hosts
            @result: Items set to for removal state
            @step:  Remove IPv6 vcs-network-hosts
            @result: Items set to for removal state
            @step: Remove IPv4 dhcp-network vcs-network-hosts.
            @result: Items set to for removal state
            @step: Remove dhcp-network NICs on both nodes.
            @result: Items set to for removal state
            @step: Create and run plan
            @result: Plan executes successfully
            @result: vcs-network-hosts were removed from VCS NIC Resource
               "NetworkHosts" Attribute on both managed nodes.
            @result: vcs-network-hosts were removed from VCS NIC Resource
                NetworkHosts Property.
            @result: vcs-network-hosts were removed from
                   VCS NIC Resource.
        @tms_test_precondition:  VCS cluster with 2 nodes and the following
            Network Hosts layout:
            - management network (low priority network)
                * non-pingable private IPv4 address
                * pingable IPv4 address of MS
            - traffic1 network:
                * pingable IPv4 address of MS
                * non-pingable private IPv4 address
                * non-pingable private IPv6 address
            - dhcp network:
                * non-pingable private IPv4 address
            - vcs-network-hosts that use dhcp-network IPs.
        @tms_execution_type: Automated
        """

        for host_url in self.network_host_urls:
            # Test01
            if host_url.split("/")[-1] in ['nh1', 'nh6', 'nh20']:
                self.execute_cli_remove_cmd(self.ms1, host_url,
                                            add_to_cleanup=False)
            # Test02
            if host_url.split("/")[-1] in ['nh3', 'nh5']:
                self.execute_cli_remove_cmd(self.ms1, host_url,
                                            add_to_cleanup=False)
            # Test03
            if host_url.split("/")[-1] in ['nh20', 'nh21']:
                self.execute_cli_remove_cmd(self.ms1, host_url,
                                            add_to_cleanup=False)

        self.log('info', 'Remove NIC interfaces on both nodes associated '
                         'with dhcp_network. Remove the bridge and its'
                         'associated NIC')
        for node_url in self.node_urls:
            subnets = self.find(self.ms1, node_url, 'dhcp-subnet')
            # Create a list with all dhcp subnet networks present under node
            list_of_dhcp_subnets = []
            for subnet_url in subnets:
                subnet_network = self.get_props_from_url(self.ms1, \
                                        subnet_url, 'network_name')
                list_of_dhcp_subnets.append(subnet_network)

            self.assertNotEqual([], list_of_dhcp_subnets,
                                "No dhcp subnet networks found")

            bridges = self.find(self.ms1, node_url, 'bridge')
            interfaces = self.find_children_of_collect(
                self.ms1, node_url, 'network-interface')
            for bridge_url in bridges:
                network_name = self.get_props_from_url(
                    self.ms1, bridge_url, 'network_name')
                if network_name in list_of_dhcp_subnets:
                    for if_url in interfaces:
                        bridge_name = self.get_props_from_url(
                            self.ms1, if_url, 'bridge')
                        if bridge_name == bridge_url.split("/")[-1]:
                            self.execute_cli_remove_cmd(self.ms1, if_url,
                                                        add_to_cleanup=False)
                    self.execute_cli_remove_cmd(self.ms1, bridge_url,
                                                add_to_cleanup=False)

            # Remove DHCP service associated dhcp_network on both nodes
            dhcp_service_url = self.find(self.ms1, node_url, 'dhcp-service')[0]
            self.execute_cli_remove_cmd(self.ms1, dhcp_service_url,
                                        add_to_cleanup=False)

        self.log('info', 'Execute the plan to remove the NIC and VCS Network '
                         'Hosts related from the both nodes')
        self.run_and_check_plan(self.ms1, test_constants.PLAN_COMPLETE,
                                plan_timeout_mins=10)

        self.log('info', 'Check the VCS Network Hosts were removed from the'
                         'LITP model and the MNs by comparing the existing '
                         'VCS Network Hosts items with VCS NIC "NetworkHosts"'
                         'attribute present on MNs.')
        self.verify_vcs_network_hosts()

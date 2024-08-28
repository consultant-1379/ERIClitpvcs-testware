"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     January 2017
@author:    James Langan
@summary:   Integration Tests
            Agile: STORY-159932
"""
import os
from vcs_utils import VCSUtils
from test_constants import PLAN_COMPLETE, PLAN_TASKS_RUNNING
from litp_generic_test import GenericTest, attr
from redhat_cmd_utils import RHCmdUtils
from generate import load_fixtures, generate_json, apply_options_changes, \
    apply_item_changes

STORY = '159932'


class Story159932(GenericTest):
    """
    TORF-159932:
        Description:
            As a LITP user I want to be able to modify subnet definition in
            the model and have the VCS Plugin act accordingly
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
        super(Story159932, self).setUp()

        self.management_server = self.get_management_node_filename()
        self.vcs = VCSUtils()
        # Location where RPMs to be used are stored
        self.rpm_src_dir = (os.path.dirname(
            os.path.realpath(__file__)) + '/rpm-out/dist/')

        self.vcs_cluster_url = self.find(self.management_server,
                                         '/deployments', 'vcs-cluster')[-1]
        self.cluster_id = self.vcs_cluster_url.split('/')[-1]
        self.nodes_urls = self.find(self.management_server,
                                    self.vcs_cluster_url,
                                    'node')
        self.node_ids = [node.split('/')[-1] for node in self.nodes_urls]
        self.node_exe = []
        self.rh_cmds = RHCmdUtils()

        for node in self.nodes_urls:
            self.node_exe.append(
                self.get_node_filename_from_url(self.management_server, node))

        self.list_of_cs_names = []
        self.nodes_to_expand = list()
        for nodes in ["node2", "node3", "node4"]:
            self.nodes_to_expand.append(nodes)

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story159932, self).tearDown()

    def baseline(self, vcs_len, app_len, hsc_len, vips_len=0, cleanup=False,
                 vcs_trig=0, story=STORY):
        """
        Description:
            Runs if no suitable CS group is found with every test case to set
            up litp model with vcs/app and ha service parameters
        Parameters:
            vcs_len: (int) Number of VCS CS
            app_len: (int) Number of applications
            hsc_len: (int) Number of HA Service Configs
            vips_len: (int) Number of VIPs required
            cleanup: (bool) Add
        Actions:
            Declares fixtures dictionary for litp model generation
        Returns:
            fixtures dictionary
        """

        _json = generate_json(to_file=True, story=story,
                              vcs_length=vcs_len,
                              app_length=app_len,
                              hsc_length=hsc_len,
                              vip_length=vips_len,
                              vcs_trigger=vcs_trig,
                              add_to_cleanup=cleanup)

        return load_fixtures(story, self.vcs_cluster_url,
                             self.nodes_urls, input_data=_json)

    def set_Passwords(self):
        """
        Method that sets the passwords for newly expanded nodes
        :return: Nothing
        """
        for node in self.nodes_to_expand:
            self.assertTrue(self.set_pws_new_node(self.management_server,
                                                  node),
                            "Failed to set password")

            # Sanity check to prove passwds have been set
            stdout, _, _ = self.run_command(node, 'hostname')

            self.assertEqual(stdout[0], node)

    def _four_node_expansion(self):
        """
        This Method is used to expand the LITP model using UTIL scripts
        supplied
        :return: Nothing
        """
        net_hosts_props = {'ip': '10.10.14.4',
                           'network_name': 'dhcp_network'}

        self.execute_expand_script(self.management_server,
                                   'expand_cloud_c1_mn2.sh',
                                    cluster_filename='192.168.0.42_4node.sh')
        self.execute_expand_script(self.management_server,
                                   'expand_cloud_c1_mn3.sh',
                                   cluster_filename='192.168.0.42_4node.sh')
        self.execute_expand_script(self.management_server,
                                   'expand_cloud_c1_mn4.sh',
                                   cluster_filename='192.168.0.42_4node.sh')

        self.execute_cli_create_cmd(self.management_server,
                                    self.vcs_cluster_url +
                                    '/network_hosts/nh21', 'vcs-network-host',
                                    props='ip={0} network_name={1}'
                                    .format(net_hosts_props['ip'],
                                            net_hosts_props['network_name']),
                                   add_to_cleanup=False)

        timeout_mins = 90
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE,
                                timeout_mins)

    def _is_model_expanded(self):
        """
        Method that checks if litp is expanded if not, execute node expansion,
        otherwise proceed with test
        :return:
        """
        nodes = ['n1', 'n2', 'n3', 'n4']
         # Check if model is expanded to 4 nodes if not proceed with test
        if sorted(nodes) != sorted(self.node_ids):
            self._four_node_expansion()
            # Set passwords of newly added nodes
            self.set_Passwords()

    def _remove_deployed_services(self):
        """
        Method to remove Service Groups 'CS_159932_1' and 'CS_159932_2'
        :return:
        """
        depl_srvs_url = self.vcs_cluster_url + '/services/'
        soft_srvs_url = '/software/services/'
        soft_items_url = '/software/items/'
        # Step 1 : Remove CS from model
        self.execute_cli_remove_cmd(self.management_server,
                            depl_srvs_url + 'CS_159932_1',
                            add_to_cleanup=False)
        self.execute_cli_remove_cmd(self.management_server,
                            depl_srvs_url + 'CS_159932_2',
                            add_to_cleanup=False)

        self.execute_cli_remove_cmd(self.management_server,
                                    soft_srvs_url + 'APP_159932_1',
                                    add_to_cleanup=False)
        self.execute_cli_remove_cmd(self.management_server,
                                    soft_srvs_url + 'APP_159932_2',
                                    add_to_cleanup=False)

        self.execute_cli_remove_cmd(self.management_server,
                                   soft_items_url + 'EXTR-lsbwrapper-159932-1',
                                   add_to_cleanup=False)
        self.execute_cli_remove_cmd(self.management_server,
                                   soft_items_url + 'EXTR-lsbwrapper-159932-2',
                                   add_to_cleanup=False)

        # Step 2: Create/ Run plan
        self.run_and_check_plan(self.management_server,
                                PLAN_COMPLETE,
                                plan_timeout_mins=15, add_to_cleanup=False)

    def _contract_traffic1_subnet(self):
        """
        Method that will contract the subnet of the traffic1 network from
        172.16.100.0/23 to 172.16.100.0/24.
        :return:
        """
        timeout_mins = 15
        updte_net_url = "/infrastructure/networking/networks/traffic1"

        self.execute_cli_update_cmd(self.management_server, updte_net_url,
                                        props="subnet=172.16.100.0/24")
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

    def _deploy_cs_in_model(self, parallel_sg1=True, vips=False):
        """
        Method that will deploy CS_159923_1 and CS_159932_2 Service Groups
        and create and run plan.
        NOTE: CS_159932_2 is configured as 2 node PL with no vips that is
        dependent on CS_159932_1.
        parallel_sg1: Control whether CS_159923_1 is Failover or 2 Node PL SG
        vips: Control whether CS_159923_1 has 4 vips (2ipv4 & 2ipv6) or no vips
        :return: Nothing
        """
        timeout_mins = 15
        self.log('info', 'Creating suitable Service groups for test case')
        vip_len = 0
        if vips:
            vip_len = 4
        fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2,
                                 vips_len=vip_len)

        vip_props = {'network_name': 'traffic1',
                     'ipaddress': ['172.16.100.190', '172.16.100.191']}

        vip6_props = {'network_name': 'traffic1',
                     'ipaddress': ['2001:abbc:de::5180/64',
                                   '2001:abbc:de::5181/64']}

        # Default CS_159932_1 as Failover SG
        active = '1'
        standby = '1'
        if parallel_sg1:
            active = '2'
            standby = '0'

        apply_options_changes(
                fixtures, 'vcs-clustered-service', 0,
                {'active': active, 'standby': standby, 'name': 'CS_159932_1',
                 'node_list': 'n1,n2'}, overwrite=True)
        if vips:
            apply_options_changes(
                fixtures, 'vip', 0, {
                'network_name': '{0}'.format(vip_props['network_name']),
                'ipaddress': '{0}'.format(vip_props['ipaddress'][0])},
                overwrite=True)
            apply_item_changes(
                fixtures, 'vip', 1, {
                'vpath': self.vcs_cluster_url +
                '/services/{0}/ipaddresses/ip2'.format('CS_159932_1')})
            apply_options_changes(
                fixtures, 'vip', 1, {
                'network_name': '{0}'.format(vip_props['network_name']),
                'ipaddress': '{0}'.format(vip_props['ipaddress'][1])},
                overwrite=True)
            apply_item_changes(
                fixtures, 'vip', 2, {
                'vpath': self.vcs_cluster_url +
                '/services/{0}/ipaddresses/ip3'.format('CS_159932_1')})
            apply_options_changes(
                fixtures, 'vip', 2, {
                'network_name': '{0}'.format(vip6_props['network_name']),
                'ipaddress': '{0}'.format(vip6_props['ipaddress'][0])},
                overwrite=True)
            apply_item_changes(
                fixtures, 'vip', 3, {
                'vpath': self.vcs_cluster_url +
                '/services/{0}/ipaddresses/ip4'.format('CS_159932_1')})
            apply_options_changes(
                fixtures, 'vip', 3, {
                'network_name': '{0}'.format(vip6_props['network_name']),
                'ipaddress': '{0}'.format(vip6_props['ipaddress'][1])},
                overwrite=True)
        apply_options_changes(
                fixtures, 'vcs-clustered-service', 1,
                {'active': '2', 'standby': '0', 'name': 'CS_159932_2',
                 'node_list': 'n1,n2',
                 'dependency_list': 'CS_159932_1'}, overwrite=True)
        apply_item_changes(
                fixtures, 'ha-service-config', 1,
                {'parent': "CS_159932_2",
                 'vpath': self.vcs_cluster_url + '/services/CS_159932_2/'
                                                 'ha_configs/HSC_159932_2'}
                )
        apply_item_changes(
                fixtures, 'service', 1,
                {'parent': "CS_159932_2",
                 'destination': self.vcs_cluster_url +
                                '/services/CS_159932_2/applications/'
                                'APP_159932_2'})

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

    def _perform_cleanup(self):
        """
        Method that restores model back to one node after expansion has
        succeeded
        """
        # If the expansion has succeeded we restore_snapshot to bring us
        # back to a one node state again. Note we set the poweroff_nodes value
        # as expanded nodes should be powered off before restoring back.
        self.execute_and_wait_restore_snapshot(
            self.management_server, poweroff_nodes=self.nodes_to_expand)

        # Create a new snapshot for the next test to have a restore_point
        self.execute_and_wait_createsnapshot(self.management_server,
                                             add_to_cleanup=False)

        # Reset Passwords for next test case
        self.assertTrue(self.set_pws_new_node(self.management_server,
                                              self.node_exe[0]),
                        'Passwords Not Set')

        # Sanity check to prove passwds have been set
        stdout, _, _ = self.run_command(self.node_exe[0], 'hostname')
        self.assertEqual('node1', stdout[0])

    def _verify_netmask(self, service_group, exp_netmask):
        """
        Method that verifies the NetMask has been updated correctly for
        the ipv4 based VCS IP Resources for VCS service group.
        Also verifies ipv6 based VCS IP Resources have not been updated.
        service_group: service group to examine
        exp_netmask: expected netmask. e.g. '255.255.254.0'.
        """
        sg_name = \
            self.vcs.generate_clustered_service_name(service_group,
                                                 self.cluster_id)
        cmd = self.vcs.get_hagrp_resource_list_cmd(sg_name)

        stdout = self.run_command(self.node_exe[0], cmd, su_root=True,
                                  default_asserts=True)

        ipv4_res_list = []
        ipv6_res_list = []
        for res in stdout[0]:
            if 'IP' in res:
                # Check if ipv4 or ipv6 IP Resource
                cmd = self.vcs.get_hares_cmd('-value {0} Address'
                                     .format(res))

                stdout = self.run_command(self.node_exe[0], cmd, su_root=True,
                                  default_asserts=True)
                if self.net.is_ipv4_address(stdout[0][0]):
                    ipv4_res_list.append(res)
                else:
                    ipv6_res_list.append(res)

        # Verify ipv4 based VCS IP Resources
        for res in ipv4_res_list:
            cmd = self.vcs.get_hares_cmd('-value {0} NetMask'
                                     .format(res))

            stdout = self.run_command(self.node_exe[0], cmd, su_root=True,
                                  default_asserts=True)
            self.assertEqual(stdout[0][0], exp_netmask)

        # Verify ipv6 based VCS IP Resources
        for res in ipv6_res_list:
            cmd = self.vcs.get_hares_cmd('-value {0} NetMask'
                                     .format(res))

            stdout = self.run_command(self.node_exe[0], cmd, su_root=True,
                                  default_asserts=True)

            # Assert NetMask is not set for ipv6 based VCS IP Resources
            self.assertEqual(stdout[0], [])

    @attr('all', 'expansion', 'story159932', 'story159932_tc01')
    def test_01_p_expand_subnet_during_2n_to_3n_add_vips(self):
        """
        @tms_id: torf_159932_tc01
        @tms_requirements_id: TORF-159932
        @tms_title: Expand subnet while adding a node to node list of PL SG
        and also adding an ipv4 based vip
        @tms_description:
        Test to verify that a user can update the subnet of a network when
        expanding vcs-clustered-service from 2 nodes to 3 nodes and adding an
        ipv4 based vips
        @tms_test_steps:
            @step: Create two Service Groups. CS_159932_1 and
            CS_159932_2 are both 2 node Parallel SG. CS_159932_1 with 2 vips.
            @result: Service Groups created successfully.
            @step: Expand the subnet of traffic1 network from /24 to /23, add
            an ipv4 vip to CS_159932_1, add n3 to node_list of CS_159932_1
            and create and run plan
            @result: Plan runs successfully expanding subnet, adding vip and
            adding CS_159932_1 to node3.
            @step: Remove the deployed Service Groups and create and run plan
            @result: Plan is run successfully removing Service Groups
            @step: Contract the subnet of traffic1 network for /23 to /24 and
            create and run plan
            @result: Plan runs successfully contracting traffic1 subnet
        @tms_test_precondition: N/A
        @tms_execution_type: Automated
        """
        timeout_mins = 90
        updte_net_url = "/infrastructure/networking/networks/traffic1"
        ipv4_addrs = ['172.16.101.12']
        ipv6_addrs = ['2001:abbc:de::5182/64']

        self.log('info', 'Checking if model is expanded already')
        self._is_model_expanded()

        self.log('info', 'Deploy services')
        self._deploy_cs_in_model(vips=True)

        vcs_pl1_sg = 'CS_159932_1'
        vcs_pl1_sg_url = self.vcs_cluster_url + '/services/{0}'\
            .format(vcs_pl1_sg)
        sg_ips_url = self.vcs_cluster_url + '/services/{0}/ipaddresses/'\
            .format(vcs_pl1_sg)

        # Verify NetMask before subnet expansion
        self._verify_netmask(vcs_pl1_sg, '255.255.255.0')

        self.log('info', 'Updating node list to add node 3')
        self.execute_cli_update_cmd(self.management_server, vcs_pl1_sg_url,
                                    props='active=3 standby=0 '
                                          'node_list=n1,n2,n3')

        # Step 1: Expand the subnet of network from /24 to /23
        self.execute_cli_update_cmd(self.management_server, updte_net_url,
                                        props="subnet=172.16.100.0/23")

        # Step 2: Add new ipv4 vip to SG
        sg_ips_url = self.vcs_cluster_url + '/services/{0}/ipaddresses/'\
            .format(vcs_pl1_sg)

        self.execute_cli_create_cmd(self.management_server,
                                    sg_ips_url + "ip5",
                                    "vip",
                                    props="ipaddress={0} network_name=traffic1"
                                        .format(ipv4_addrs[0]),
                                    add_to_cleanup=False)

        self.execute_cli_create_cmd(self.management_server,
                                    sg_ips_url + "ip6",
                                    "vip",
                                    props="ipaddress={0} network_name=traffic1"
                                        .format(ipv6_addrs[0]),
                                    add_to_cleanup=False)

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        # Verify NetMask has been updated after subnet expansion
        self._verify_netmask(vcs_pl1_sg, '255.255.254.0')

        # Cleanup section.
        # Remove Service Groups and create/run plan
        # Contract subnet and create/run plan
        # Need two separate plans to achieve cleanup.
        self._remove_deployed_services()
        self._contract_traffic1_subnet()

    @attr('all', 'expansion', 'story159932', 'story159932_tc02')
    def test_02_p_expand_subnet_add_2_vips_existing_expanded_subnet(self):
        """
        @tms_id: torf_159932_tc02
        @tms_requirements_id: TORF-159932
        @tms_title: Expand subnet while also adding ipv4 based vips to PL SG
        @tms_description:
        Test to verify that a user can expand the subnet of a network while
        adding two ipv4 based vips, one within original subnet and one within
        the expanded subnet to a 2 node Parallel vcs-clustered-service with
        no vips
        @tms_test_steps:
            @step: Create two Service Groups. CS_159932_1 and
            CS_159932_2 are both 2 node Parallel SGs with no vips.
            @result: Service Groups created successfully.
            @step: Expand the subnet of traffic1 network from /24 to /23, add
            two ipv4 vips to CS_159932_1 and create and run plan
            @result: Plan runs successfully expanding subnet and adding vips
            @step: Remove the deployed Service Groups and create and run plan
            @result: Plan is run successfully removing Service Groups
            @step: Contract the subnet of traffic1 network for /23 to /24 and
            create and run plan
            @result: Plan runs successfully contracting traffic1 subnet
        @tms_test_precondition: N/A
        @tms_execution_type: Automated
        """
        timeout_mins = 90
        updte_net_url = "/infrastructure/networking/networks/traffic1"
        ipv4_addrs = ['172.16.100.191', '172.16.101.11']
        ipv6_addrs = ['2001:abbc:de::5180/64', '2001:abbc:de::5181/64']

        self.log('info', 'Checking if model is expanded already')
        self._is_model_expanded()

        self.log('info', 'Deploy services')
        self._deploy_cs_in_model()

        vcs_pl1_sg = 'CS_159932_1'
        sg_ips_url = self.vcs_cluster_url + '/services/{0}/ipaddresses/'\
            .format(vcs_pl1_sg)

        # Step 1: Expand the subnet of network from /24 to /23
        self.execute_cli_update_cmd(self.management_server, updte_net_url,
                                        props="subnet=172.16.100.0/23")

        # Step 2a: Add 2 new ipv4 vips to SG
        sg_ips_url = self.vcs_cluster_url + '/services/{0}/ipaddresses/'\
            .format(vcs_pl1_sg)

        self.execute_cli_create_cmd(self.management_server,
                                    sg_ips_url + "ip1",
                                    "vip",
                                    props="ipaddress={0} network_name=traffic1"
                                    .format(ipv4_addrs[0]),
                                    add_to_cleanup=False)
        self.execute_cli_create_cmd(self.management_server,
                                    sg_ips_url + "ip2",
                                    "vip",
                                    props="ipaddress={0} network_name=traffic1"
                                        .format(ipv4_addrs[1]),
                                    add_to_cleanup=False)

        # Step 2b: Add 2 new ipv6 vips to SG
        self.execute_cli_create_cmd(self.management_server,
                                    sg_ips_url + "ip3",
                                    "vip",
                                    props="ipaddress={0} network_name=traffic1"
                                    .format(ipv6_addrs[0]),
                                    add_to_cleanup=False)
        self.execute_cli_create_cmd(self.management_server,
                                    sg_ips_url + "ip4",
                                    "vip",
                                    props="ipaddress={0} network_name=traffic1"
                                        .format(ipv6_addrs[1]),
                                    add_to_cleanup=False)

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        # Verify NetMask has been updated after subnet expansion
        self._verify_netmask(vcs_pl1_sg, '255.255.254.0')

        # Cleanup section.
        # Remove Service Groups and create/run plan
        # Contract subnet and create/run plan
        # Need two separate plans to achieve cleanup.
        self._remove_deployed_services()
        self._contract_traffic1_subnet()

    @attr('all', 'expansion', 'story159932', 'story159932_tc03')
    def test_03_p_expand_subnet_2vip_to_4vip_fail_rerun_plan(self):
        """
        @tms_id: torf_159932_tc03
        @tms_requirements_id: TORF-159932
        @tms_title: Expand subnet while also adding ipv4 based vips to PL SG
        which already has 2 vips the fail the plan using litpd restart and
        re-create/re-run plan again
        @tms_description:
        Test to verify that a user can expand the subnet of a network while
        adding two ipv4 based vips within original and expanded subnet to a 2
        node Parallel vcs-clustered-service which already has two ipv4 based
        vips when the initial plan fails when running Create IP resources task
        @tms_test_steps:
            @step: Create two Service Groups. CS_159932_1 and
            CS_159932_2 are both 2 node Parallel SG. CS_159932_1 with 2 vips.
            @result: Service Groups created successfully.
            @step: Expand the subnet of traffic1 network from /24 to /23 and
            add two more ipv4 vips to CS_159932_1 and create and run plan
            @result: Plan is running with tasks to expand subnet and add vips
            @step: Perform 'litpd restart' when Create IP Resources" Task is
            Running and then re-create/re-run plan again
            @result: Initial plan fails due to 'litpd restart' but second plan
            runs to completion successfully
            @step: Remove the deployed Service Groups and create and run plan
            @result: Plan is run successfully removing Service Groups
            @step: Contract the subnet of traffic1 network for /23 to /24 and
            create and run plan
            @result: Plan runs successfully contracting traffic1 subnet
        @tms_test_precondition: N/A
        @tms_execution_type: Automated
        """
        timeout_mins = 90
        updte_net_url = "/infrastructure/networking/networks/traffic1"
        ipv4_addrs = ['172.16.100.192', '172.16.101.11']
        ipv6_addrs = ['2001:abbc:de::5182/64', '2001:abbc:de::5183/64']
        task_desc = 'Create IP resources for VCS service group'

        self.log('info', 'Deploy services')
        #self._deploy_pl_cs_in_model()
        self._deploy_cs_in_model(vips=True)

        vcs_pl1_sg = 'CS_159932_1'
        sg_ips_url = self.vcs_cluster_url + '/services/{0}/ipaddresses/'\
            .format(vcs_pl1_sg)

        # Verify NetMask before subnet expansion
        self._verify_netmask(vcs_pl1_sg, '255.255.255.0')

        # Step 1: Expand the subnet of network from /24 to /23
        self.execute_cli_update_cmd(self.management_server, updte_net_url,
                                        props="subnet=172.16.100.0/23")

        # Step 2a: Add 2 new ipv4 vips to SG
        sg_ips_url = self.vcs_cluster_url + '/services/{0}/ipaddresses/'\
            .format(vcs_pl1_sg)

        self.execute_cli_create_cmd(self.management_server,
                                    sg_ips_url + "ip5",
                                    "vip",
                                    props="ipaddress={0} network_name=traffic1"
                                    .format(ipv4_addrs[0]),
                                    add_to_cleanup=False)
        self.execute_cli_create_cmd(self.management_server,
                                    sg_ips_url + "ip6",
                                    "vip",
                                    props="ipaddress={0} network_name=traffic1"
                                        .format(ipv4_addrs[1]),
                                    add_to_cleanup=False)

        # Step 2b: Add 2 new ipv6 vips to SG
        self.execute_cli_create_cmd(self.management_server,
                                    sg_ips_url + "ip7",
                                    "vip",
                                    props="ipaddress={0} network_name=traffic1"
                                        .format(ipv6_addrs[0]),
                                    add_to_cleanup=False)
        self.execute_cli_create_cmd(self.management_server,
                                    sg_ips_url + "ip8",
                                    "vip",
                                    props="ipaddress={0} network_name=traffic1"
                                        .format(ipv6_addrs[1]),
                                    add_to_cleanup=False)

        self.log('info', 'Create / Run plan')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Restart litpd at Create IP resources Task')
        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 task_desc,
                                                 PLAN_TASKS_RUNNING,
                                                 ignore_variables=False),
                        'Could not restart on Create IP Resource Task')
        self.restart_litpd_service(self.management_server)

        self.log('info', 'Create / Run plan again to completion')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        # Verify NetMask has been updated after subnet expansion
        self._verify_netmask(vcs_pl1_sg, '255.255.254.0')

        # Cleanup section.
        # Remove Service Groups and create/run plan
        # Contract subnet and create/run plan
        # Need two separate plans to achieve cleanup.
        self._remove_deployed_services()
        self._contract_traffic1_subnet()

    @attr('all', 'expansion', 'story159932', 'story159932_tc04')
    def test_04_p_expand_subnet_during_FO_to_PL_add_vips(self):
        """
        @tms_id: torf_159932_tc04
        @tms_requirements_id: TORF-159932
        @tms_title: Expand subnet while also converting SG from Failover to
        2 Node Parallel SG and adding two ipv4 based vips to the SG
        @tms_description:
        Test to verify that a user can update their Failover clustered services
        with ipv4 based vips to PL while expanding the subnet of a network and
        adding ipv4 based vips
        @tms_test_steps:
            @step: Create two Service Groups. CS_159932_1 is Failover SG with
            2 ipv4 based vips and CS_159932_2 is a 2 node Parallel SG.
            @result: Service Groups created successfully.
            @step: Expand the subnet of traffic1 network from /24 to /23 and
            add two more ipv4 vips and change Failover SG to Parallel SG and
            create and run plan
            @result: Plan runs successfully expanding subnet, adding vips and
            converting FO SG to PL SG.
            @step: Remove the deployed Service Groups and create and run plan
            @result: Plan is run successfully removing Service Groups
            @step: Contract the subnet of traffic1 network for /23 to /24 and
            create and run plan
            @result: Plan runs successfully contracting traffic1 subnet
        @tms_test_precondition: N/A
        @tms_execution_type: Automated
        """
        timeout_mins = 90
        updte_net_url = "/infrastructure/networking/networks/traffic1"
        ipv4_addrs = ['172.16.100.192', '172.16.101.11']
        ipv6_addrs = ['2001:abbc:de::5182/64', '2001:abbc:de::5183/64']

        # Step 1: Deploy 1 FO SG and 1 PL SG.
        # FO SG deployed with 2 ipv4 vips
        self._deploy_cs_in_model(parallel_sg1=False, vips=True)
        vcs_fo_sg = 'CS_159932_1'
        fo_sg_url = self.vcs_cluster_url + '/services/{0}'\
            .format(vcs_fo_sg)
        sg_ips_url = self.vcs_cluster_url + '/services/{0}/ipaddresses/'\
            .format(vcs_fo_sg)

        # Verify NetMask before subnet expansion
        self._verify_netmask(vcs_fo_sg, '255.255.255.0')

        # Step 2a: Expand the subnet of network from /24 to /23
        self.execute_cli_update_cmd(self.management_server, updte_net_url,
                                        props="subnet=172.16.100.0/23")

        # Step 2b: Add 2 new ipv4 vips to SG
        self.execute_cli_create_cmd(self.management_server,
                                    sg_ips_url + "ip5",
                                    "vip",
                                    props="ipaddress={0} network_name=traffic1"
                                        .format(ipv4_addrs[0]),
                                    add_to_cleanup=False)
        self.execute_cli_create_cmd(self.management_server,
                                    sg_ips_url + "ip6",
                                    "vip",
                                    props="ipaddress={0} network_name=traffic1"
                                        .format(ipv4_addrs[1]),
                                    add_to_cleanup=False)

        # Step 2c: Add 2 new ipv6 vips to SG
        self.execute_cli_create_cmd(self.management_server,
                                    sg_ips_url + "ip7",
                                    "vip",
                                    props="ipaddress={0} network_name=traffic1"
                                        .format(ipv6_addrs[0]),
                                    add_to_cleanup=False)
        self.execute_cli_create_cmd(self.management_server,
                                    sg_ips_url + "ip8",
                                    "vip",
                                    props="ipaddress={0} network_name=traffic1"
                                        .format(ipv6_addrs[1]),
                                    add_to_cleanup=False)

        # Step 2d: Update from Failover SG to Parallel
        self.execute_cli_update_cmd(self.management_server, fo_sg_url,
                               props="active=2 standby=0 node_list='n1,n2'")

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        # Verify NetMask has been updated after subnet expansion
        self._verify_netmask(vcs_fo_sg, '255.255.254.0')

        # Cleanup section.
        self._perform_cleanup()

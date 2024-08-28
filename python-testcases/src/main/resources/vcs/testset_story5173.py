"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     Feb 2016
@author:    Ciaran Reilly, James Maher, David Gibbons
@summary:   Integration Tests
            Agile: STORY-5173
"""

import os
import test_constants
from litp_generic_test import GenericTest, attr
from redhat_cmd_utils import RHCmdUtils
from vcs_utils import VCSUtils
from generate import load_fixtures, generate_json, apply_options_changes, \
    apply_item_changes

STORY = '5173'


class Story5173(GenericTest):
    """
    LITPCDS-5173:
    I can add a VIP containing an IPv4 address to an already created VCS
        Service Group
    I can add a VIP containing an IPv6 address to an already created VCS
        Service Group
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
        super(Story5173, self).setUp()
        self.management_server = self.get_management_node_filename()
        self.vcs = VCSUtils()
        self.rhcmd = RHCmdUtils()
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

        self.managed_nodes = self.get_managed_node_filenames()

        self.node_1 = self.get_node_filename_from_url(self.management_server,
                                                      self.nodes_urls[0])

        self.test01_ipv4_addr = ['10.10.22.226', '10.10.22.227',
                                 '10.10.22.228']
        self.test01_ipv6_addr = ['2001:abbc:de::5180/64',
                                 '2001:abbc:de::5181/64',
                                 '2001:abbc:de::5182/64']
        # Use MAC's from eth9 on peer nodes
        self.test01_macaddresses = ["00:50:56:00:01:08", "00:50:56:00:01:09"]
        self.test02_ipv4_addr = ['10.10.22.229', '10.10.22.230',
                                 '10.10.22.231']
        self.test02_ipv6_addr = ['2001:abbc:de::5183/64',
                                 '2001:abbc:de::5184/64',
                                 '2001:abbc:de::5185/64']
        self.test04_dup = "10.10.22.42"
        self.test04_free = "10.10.22.213"

    def baseline(self, vcs_len, app_len, hsc_len, cleanup=False,
                 valid_rpm=True):
        """
        Description:
            Runs initially with every test case to set up litp model
            with vcs/app and ha service parameters
        Parameters:
            vcs_len: (int) Number of VCS CS
            app_len: (int) Number of applications
            hsc_len: (int) Number of HA Service Configs
            cleanup: (bool) Add
        Actions:
            Declares fixtures dictionary for litp model generation
        Returns:
            fixtures dictionary
        """

        _json = generate_json(to_file=False, story=STORY,
                              vcs_length=vcs_len,
                              app_length=app_len,
                              hsc_length=hsc_len,
                              add_to_cleanup=cleanup,
                              valid_rpm=valid_rpm)

        return load_fixtures(
            STORY, self.vcs_cluster_url, self.nodes_urls, input_data=_json)

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story5173, self).tearDown()

    def _check_pings(self, ipv4_addresses, ipv6_addresses):
        """
        :param ipv4_addresses: List of ipv4 address to test ping
        :param ipv6_addresses: List of ipv6 address to test ping
        :return:
        """
        # Check that each new IP is created on either node1 or node2
        for i_p in ipv4_addresses:
            ping_command = "/bin/ping -c 1 {0}".format(i_p)
            self.run_command(self.node_1, ping_command, su_root=True,
                             default_asserts=True)
        for i_p in ipv6_addresses:
            ping_command = "/bin/ping6 -c 1 {0}".format(i_p.split('/')[0])
            self.run_command(self.node_1, ping_command, su_root=True,
                             default_asserts=True)

    def _check_ifconfig(self, ipv4_addresses, ipv6_addresses):
        """
        Method to check that all the ipaddresses appear in ifconfig on either
            node
        :param ipv4_addresses: List of ipv4 address to test ping
        :param ipv6_addresses: List of ipv6 address to test ping
        :return:
        """
        ifconfig_output = ''
        for node in self.managed_nodes:
            ifconfig_cmd = self.net.get_ifconfig_cmd()
            stdout, _, _ = self.run_command(node, ifconfig_cmd, su_root=True,
                                            default_asserts=True)
            ifconfig_output += ''.join(stdout)

        for i_p in ipv4_addresses + ipv6_addresses:
            self.assertTrue(i_p.split("/")[0] in ifconfig_output,
                            'IP "{0}" not found in ifconfig output '
                            '"{1}"'.format(i_p.split("/")[0], ifconfig_output))

    def _check_app_dependencies(self, cs_name, app_id, expected_result):
        """
        Method to check the application dependencies of a VCS Service Group
        :param app_id (str): The service application to be checked
                i.e. App_5173_1
               cs_name (str): Name of a clustered service i.e. CS_5173_1
               expected_result: State the service group applications are
                expected to be in
        :return:
        """
        app_name = self.vcs.generate_application_resource_name(cs_name,
                                                               self.cluster_id,
                                                               app_id)
        hares_dep_cmd = self.vcs.get_hares_cmd('-dep {0}'.format(app_name))
        stdout = self.run_command(self.node_1, hares_dep_cmd, su_root=True,
                                  default_asserts=True)

        self.assertEqual(stdout[0].sort(), expected_result.sort())

    @attr('all', 'non-revert', 'story5173', 'story5173_tc01')
    def test_01_p_add_vips_sg_no_vips_network_updated(self):
        """
        @tms_id: litpcds_5173_tc1
        @tms_requirements_id: LITPCDS-5173
        @tms_title:  Update a Service Group vips
        @tms_description:
        Update a Service Group with no vips applied. Add vips to test for
        both Failover and Parallel, and with ipv4 and ipv6. Update a
        network interface for the new vips
        @tms_test_steps:
        @step: Create service, clustered-service, package, ha-service-config,
        eth and network items
        @result: items created
        @step: update network items ip properties
        @result: items updated
        @step: create two new ipv4 vips and two new ipv6 items to
        fail over service group
        @result: items created
        @step: create a new ipv4 vips and a new ipv6 items to
        Parallel service group
        @result: items created
        @step: create and run plan
        @result: plan executes successfully
        @result: new vip is included on the vcs config
        @result: app resource in the service group depends on the
        new vips
        @step: ping ips
        @result: ips are pingable
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        net_url = "/infrastructure/networking/networks/net5173_init"
        net_props = "name=net5173_init subnet=10.10.111.0/24"
        updte_net_url = "/infrastructure/networking/networks/net5173"
        updte_net_props = "name=net5173 subnet=10.10.22.0/24"

        net_intfce_props = "device_name=eth9 network_name=net5173_init " \
                           "macaddress={0} ipaddress=10.10.111.2{1}"

        expected_result_cs_1 = ['#Group              Parent                 '
                                '         Child',
                                'Grp_CS_c1_CS_5173_1 '
                                'Res_App_c1_CS_5173_1_APP_5173_1 '
                                'Res_IP_c1_CS_5173_1_APP_5173_1_net5173_2',
                                'Grp_CS_c1_CS_5173_1 '
                                'Res_App_c1_CS_5173_1_APP_5173_1 '
                                'Res_IP_c1_CS_5173_1_APP_5173_1_net5173_1']

        expected_result_cs_2 = ['#Group              Parent                 '
                                '         Child',
                                'Grp_CS_c1_CS_5173_2 '
                                'Res_App_c1_CS_5173_2_APP_5173_2 '
                                'Res_IP_c1_CS_5173_2_APP_5173_2_net5173_2',
                                'Grp_CS_c1_CS_5173_2 '
                                'Res_App_c1_CS_5173_2_APP_5173_2 '
                                'Res_IP_c1_CS_5173_2_APP_5173_2_net5173_1']

        # Step 0: Create 2 vcs-clustered-services, a FO and a PL with the test
        #  RPM for 5173. Add a new network, and an interface on each node.
        # Add a 2nd new network.
        fixtures = self.baseline(2, 2, 2, False)

        cs_url = self.get_cs_conf_url(self.management_server,
                                      fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)
        if cs_url is None:
            apply_options_changes(
                fixtures,
                'vcs-clustered-service', 0, {'active': '2', 'standby': '0',
                                             'name': 'CS_5173_1',
                                             'node_list': '{0}'.format
                                             (','.join(self.node_ids))},
                overwrite=True)

            apply_options_changes(
                fixtures,
                'vcs-clustered-service', 1, {'active': '1', 'standby': '1',
                                             'name': 'CS_5173_2',
                                             'node_list': '{0}'.format
                                             (','.join(self.node_ids))},
                overwrite=True)

            apply_item_changes(fixtures, 'ha-service-config', 1,
                               {'vpath': self.vcs_cluster_url + '/services/'
                                                                'CS_5173_2/'
                                                                'ha_configs/'
                                                                'HSC_5173_2',
                                'parent': "CS_5173_2"})

            apply_item_changes(fixtures, 'service', 1,
                               {'parent': "CS_5173_2",
                                'destination': self.vcs_cluster_url +
                                '/services/CS_5173_2/applications/APP_5173_2'})

            list_of_cs_names = [fixtures['service'][0]['parent'],
                                fixtures['service'][1]['parent']]

            self.apply_cs_and_apps_sg(self.management_server,
                                      fixtures,
                                      self.rpm_src_dir)

            self.execute_cli_create_cmd(self.management_server, net_url,
                                        'network', net_props,
                                        add_to_cleanup=False)

            for index, node_url in enumerate(self.nodes_urls):
                self.execute_cli_create_cmd(self.management_server,
                                            node_url +
                                            "/network_interfaces/net9",
                                            "eth", net_intfce_props.format(
                                             self.test01_macaddresses[index],
                                             index),
                                            add_to_cleanup=False)

            self.execute_cli_create_cmd(self.management_server, updte_net_url,
                                        'network', updte_net_props,
                                        add_to_cleanup=False)

            self.execute_cli_create_cmd(self.management_server,
                                    "/ms/network_interfaces/net4",
                                    "eth",
                                    props="device_name=eth4 "
                                          "network_name=net5173 "
                                          "macaddress=00:50:56:00:01:02 "
                                          "ipaddress=10.10.22.42",
                                    add_to_cleanup=False)

            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE, 20)

        # Step 1: Update the interface on the nodes to use the 2nd network
        for index, node_url in enumerate(self.nodes_urls):
            self.execute_cli_update_cmd(self.management_server, node_url +
                                        "/network_interfaces/net9",
                                        props="network_name=net5173 "
                                              "ipaddress=10.10.22.2{0}".
                                        format(index))

        # Step 2: Add a new ipv4 vip and a new ipv6 vip to a FO service group
        pl_sg_ips_url = self.vcs_cluster_url + '/services/{0}/ipaddresses/'\
            .format(list_of_cs_names[0])

        self.execute_cli_create_cmd(self.management_server,
                                    pl_sg_ips_url + "vip5173_1",
                                    "vip",
                                    props="ipaddress={0} network_name=net5173"
                                    .format(self.test01_ipv4_addr[0]),
                                    add_to_cleanup=False)
        self.execute_cli_create_cmd(self.management_server,
                                    pl_sg_ips_url + "vip5173_2",
                                    "vip",
                                    props="ipaddress={0} network_name=net5173"
                                        .format(self.test01_ipv4_addr[1]),
                                    add_to_cleanup=False)

        self.execute_cli_create_cmd(self.management_server,
                                    pl_sg_ips_url + "6vip5173_1",
                                    "vip",
                                    props="ipaddress={0} network_name=net5173"
                                        .format(self.test01_ipv6_addr[0]),
                                    add_to_cleanup=False)
        self.execute_cli_create_cmd(self.management_server,
                                    pl_sg_ips_url + "6vip5173_2",
                                    "vip",
                                    props="ipaddress={0} network_name=net5173"
                                        .format(self.test01_ipv6_addr[1]),
                                    add_to_cleanup=False)

        # Step 3: Add a new ipv4 vip and a new ipv6 vip to a FO service group
        fo_sg_ips_url = self.vcs_cluster_url + '/services/{0}/ipaddresses/'\
            .format(list_of_cs_names[1])

        self.execute_cli_create_cmd(self.management_server,
                                    fo_sg_ips_url + "fovip5173_1",
                                    "vip",
                                    props="ipaddress={0} network_name=net5173"
                                        .format(self.test01_ipv4_addr[2]),
                                    add_to_cleanup=False)

        self.execute_cli_create_cmd(self.management_server,
                                    fo_sg_ips_url + "fo6vip5173_1",
                                    "vip",
                                    props="ipaddress={0} network_name=net5173"
                                        .format(self.test01_ipv6_addr[2]),
                                    add_to_cleanup=False)

        # Step 4: Create/ Run Plan
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 30)

        # Step 5: Check that the new vip is included on the vcs config on
        # the node
        self._check_ifconfig(self.test01_ipv4_addr, self.test01_ipv6_addr)

        # Step 6: Ping that ip address to ensure it is up
        self._check_pings(self.test01_ipv4_addr, self.test01_ipv6_addr)

        # Step 7: Check that the app resource in the service group depends on
        # the new vips
        self._check_app_dependencies(list_of_cs_names[0], 'APP_5173_1',
                                     expected_result_cs_1)
        self._check_app_dependencies(list_of_cs_names[1], 'APP_5173_2',
                                     expected_result_cs_2)

    @attr('all', 'non-revert', 'story5173', 'story5173_tc02')
    def test_02_p_add_vips_sg_applied_vips(self):
        """
        Description:
            Update a Service Group which has vips already applied. Test for
            both Failover and Parallel, and with ipv4 and ipv6

        Steps:
            1. Add a new ipv4 vip and a new ipv6 vip to a FO service group
            2. Add two new ipv4 vips and two new ipv6 to a Parallel service
                group
            3. Create/Run plan
            4. Check that the new vip is included on the vcs config on the node
            5. Ping that ip address to ensure it is up
            6. Check that the app resource in the service group depends on the
                new vips
        """

        expected_result_cs1 = ['#Group              Parent                  '
                               '        Child',
                               'Grp_CS_c1_CS_5173_1 '
                               'Res_App_c1_CS_5173_1_APP_5173_1 '
                               'Res_IP_c1_CS_5173_1_APP_5173_1_net5173_4',
                               'Grp_CS_c1_CS_5173_1 '
                               'Res_App_c1_CS_5173_1_APP_5173_1 '
                               'Res_IP_c1_CS_5173_1_APP_5173_1_net5173_3',
                               'Grp_CS_c1_CS_5173_1 '
                               'Res_App_c1_CS_5173_1_APP_5173_1 '
                               'Res_IP_c1_CS_5173_1_APP_5173_1_net5173_2',
                               'Grp_CS_c1_CS_5173_1 '
                               'Res_App_c1_CS_5173_1_APP_5173_1 '
                               'Res_IP_c1_CS_5173_1_APP_5173_1_net5173_1']
        expected_result_cs2 = ['#Group              Parent                  '
                               '        Child',
                               'Grp_CS_c1_CS_5173_2 '
                               'Res_App_c1_CS_5173_2_APP_5173_2 '
                               'Res_IP_c1_CS_5173_2_APP_5173_2_net5173_4',
                               'Grp_CS_c1_CS_5173_2 '
                               'Res_App_c1_CS_5173_2_APP_5173_2 '
                               'Res_IP_c1_CS_5173_2_APP_5173_2_net5173_3',
                               'Grp_CS_c1_CS_5173_2 '
                               'Res_App_c1_CS_5173_2_APP_5173_2 '
                               'Res_IP_c1_CS_5173_2_APP_5173_2_net5173_2',
                               'Grp_CS_c1_CS_5173_2 '
                               'Res_App_c1_CS_5173_2_APP_5173_2 '
                               'Res_IP_c1_CS_5173_2_APP_5173_2_net5173_1']

        # Step 1: Add a new ipv4 vip and a new ipv6 vip to a FO service group
        fo_sg_ips_url = "{0}/services/{1}/ipaddresses/".format(
            self.vcs_cluster_url, 'CS_5173_2')

        self.execute_cli_create_cmd(self.management_server,
                                    fo_sg_ips_url + "fovip5173_2",
                                    "vip",
                                    props="ipaddress={0} network_name=net5173"
                                        .format(self.test02_ipv4_addr[2]),
                                    add_to_cleanup=False)
        self.execute_cli_create_cmd(self.management_server,
                                    fo_sg_ips_url + "fo6vip5173_2",
                                    "vip",
                                    props="ipaddress={0} network_name=net5173"
                                        .format(self.test02_ipv6_addr[2]),
                                    add_to_cleanup=False)

        # Step 2: Add 2 ipv4 address and 2 ipv6 addresses to PL service group
        pl_sg_ips_url = "{0}/services/{1}/ipaddresses/".format(
            self.vcs_cluster_url, 'CS_5173_1')
        self.execute_cli_create_cmd(self.management_server,
                                    pl_sg_ips_url + "vip5173_3",
                                    "vip",
                                    props="ipaddress={0} network_name=net5173"
                                    .format(self.test02_ipv4_addr[0]),
                                    add_to_cleanup=False)
        self.execute_cli_create_cmd(self.management_server,
                                    pl_sg_ips_url + "vip5173_4",
                                    "vip",
                                    props="ipaddress={0} network_name=net5173"
                                        .format(self.test02_ipv4_addr[1]),
                                    add_to_cleanup=False)

        self.execute_cli_create_cmd(self.management_server,
                                    pl_sg_ips_url + "6vip5173_3",
                                    "vip",
                                    props="ipaddress={0} network_name=net5173"
                                        .format(self.test02_ipv6_addr[0]),
                                    add_to_cleanup=False)
        self.execute_cli_create_cmd(self.management_server,
                                    pl_sg_ips_url + "6vip5173_4",
                                    "vip",
                                    props="ipaddress={0} network_name=net5173"
                                        .format(self.test02_ipv6_addr[1]),
                                    add_to_cleanup=False)

        # Step 3: Create/ Run Plan
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 20)

        # Step 4: Check that the new vip is included on the vcs config on
        # the node
        self._check_ifconfig(self.test02_ipv4_addr, self.test02_ipv6_addr)

        # Step 5: Ping the new IP address to ensure it is up
        self._check_pings(self.test02_ipv4_addr, self.test02_ipv6_addr)

        # Step 6: Check that the app resource in the service group depends on
        # the new vips
        self._check_app_dependencies('CS_5173_1', 'APP_5173_1',
                                     expected_result_cs1)
        self._check_app_dependencies('CS_5173_2', 'APP_5173_2',
                                     expected_result_cs2)

    @attr('all', 'non-revert', 'story5173', 'story5173_tc08')
    def test_08_n_add_duplicate_vip_idempotency(self):
        """
        @tms_id: litpcds_5173_tc8
        @tms_requirements_id: LITPCDS-5173
        @tms_title: Add a vip that is a duplicate ip of one that exists
        @tms_description:
        Add a vip that is a duplicate ip of one that is already there.
        The online task should fail. When updated to a free IP address,
        the plan should succeed, and vip created
        @tms_test_steps:
        @step: Create vip item which has an IP which
        is a duplicate of the interface used on the MS
        @result: items created
        @step: create and run plan
        @result: plan fails
        @step: update vip ip to unique value
        @result: item updated
        @step: create and run plan
        @result: plan executes successfully
        @result: both service groups are online
        @result: app resource in the service group depends on the
        new vips
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        expected_result_cs2 = ['#Group              Parent                  '
                               '        Child',
                               'Grp_CS_c1_CS_5173_2 '
                               'Res_App_c1_CS_5173_2_APP_5173_2 '
                               'Res_IP_c1_CS_5173_2_APP_5173_2_net5173_5',
                               'Grp_CS_c1_CS_5173_2 '
                               'Res_App_c1_CS_5173_2_APP_5173_2 '
                               'Res_IP_c1_CS_5173_2_APP_5173_2_net5173_4',
                               'Grp_CS_c1_CS_5173_2 '
                               'Res_App_c1_CS_5173_2_APP_5173_2 '
                               'Res_IP_c1_CS_5173_2_APP_5173_2_net5173_3',
                               'Grp_CS_c1_CS_5173_2 '
                               'Res_App_c1_CS_5173_2_APP_5173_2 '
                               'Res_IP_c1_CS_5173_2_APP_5173_2_net5173_2',
                               'Grp_CS_c1_CS_5173_2 '
                               'Res_App_c1_CS_5173_2_APP_5173_2 '
                               'Res_IP_c1_CS_5173_2_APP_5173_2_net5173_1']

        # Step 1: Add a new ipv4 vip and a new ipv6 vip to a FO service group
        fo_sg_ips_url = "{0}/services/{1}/ipaddresses/".format(
            self.vcs_cluster_url, 'CS_5173_2')

        # Step 2: Create/ Run Plan
        # Step 3: Check that plan fails when onlining the group.
        self.execute_cli_create_cmd(self.management_server,
                                    fo_sg_ips_url + "dup_vip",
                                    "vip",
                                    props="ipaddress={0} network_name=net5173"
                                        .format(self.test04_dup),
                                    add_to_cleanup=False)
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)
        self.assertTrue(self.wait_for_plan_state(
            self.management_server,
            test_constants.PLAN_FAILED,
            20
        ))

        # Step 4: Update the ip to one that is not already used
        self.execute_cli_update_cmd(self.management_server,
                                    fo_sg_ips_url + "dup_vip",
                                    props="ipaddress={0}".format(
                                        self.test04_free))

        # Step 5: Create/ Run Plan
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 20,
                                add_to_cleanup=False)

        # Step 6: Make sure that both service groups are online, that the ip
        # resource has been created with correct IP
        self._check_ifconfig([self.test04_free], [])
        self._check_pings([self.test04_free], [])

        # Step 7: Check that the app resource in the service group depends on
        # the new vips
        self._check_app_dependencies('CS_5173_2', 'APP_5173_2',
                                     expected_result_cs2)

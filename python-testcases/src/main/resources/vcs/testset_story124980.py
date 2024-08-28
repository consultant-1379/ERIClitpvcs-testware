# pylint: disable=C0103
"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     August 2016
@author:    Ciaran Reilly, Philip McGrath
@summary:   Integration Tests
            Agile: STORY-124980, STORY-397061

"""
import os
from vcs_utils import VCSUtils
from test_constants import PLAN_COMPLETE, PLAN_TASKS_SUCCESS, \
    VCS_MAIN_CF_FILENAME
from litp_generic_test import GenericTest, attr
from redhat_cmd_utils import RHCmdUtils
from generate import load_fixtures, generate_json, apply_options_changes, \
    apply_item_changes

STORY = '124980'


class Story124980(GenericTest):
    """
    TORF-124980:
        Description:
            As a LITP User I want to migrate a VCS service group to new nodes
            so that i can optimize an expanded cluster
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
        super(Story124980, self).setUp()

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
        super(Story124980, self).tearDown()

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

    def _get_node_list_for_cs(self, cs_url):
        """
        Method to obtain the node list of a clustered service group before
        and after migration
        :param cs_url: (str) clustered service URL
        :return: node_list: (str) Service group Node list
        """
        node_list = self.get_props_from_url(self.management_server, cs_url,
                                            filter_prop='node_list')

        return node_list

    def _update_node_list(self, cs_url, new_node_list):
        """
        Method that will update the node list for a specified clustered service
        group

        Parameters:
            cs_url (str): Clustered service URL
            new_node_list (str): Node list that SG will be migrated to
        :return: Nothing
        """

        self.execute_cli_update_cmd(self.management_server, cs_url,
                                    props="node_list={0}".format
                                    (new_node_list))

    def _check_active_node(self, sg_name):
        """
        Method to check which node is ONLINE for any failover SG, the
        assumption is that at least one node will be ONLINE.

        :return: act_node (str): The active node for any failover SG.
                standby_node (str): The standby node for any failover SG
        """
        active_node = None
        standby_node = None
        for node in self.node_exe:
            node_check = '-state {0} -sys {1}'.format(sg_name,
                                                      '{0}'.format(node))
            sg_state_cmd = self.vcs.get_hagrp_cmd(node_check)
            sg_grp_state, _, _ = self.run_command(node, sg_state_cmd,
                                                  su_root=True)

            if sg_grp_state[0] == 'ONLINE':
                active_node = node
            elif sg_grp_state[0] == 'OFFLINE':
                standby_node = node
            else:
                continue

        self.assertNotEqual(active_node, None)
        self.assertNotEqual(standby_node, None)

        return active_node, standby_node

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
                                            net_hosts_props['network_name']))

        timeout_mins = 90
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE,
                                timeout_mins)

    def _check_cs_in_model_tc01(self):
        """
        Method that will check for existing service groups in the model for
        test case 1
        :return: vcs_fo_sg (str): FO SG URL
                 vcs_pl_sg (str): PL SG URL
        """
        vcs_fo_sg = self.get_matching_vcs_cs_in_model(
                self.management_server, apps=1, ha_srv_cfgs=1,
                cs_props_dict={'active': '1', 'standby': '1',
                               'node_list': 'n1,n2'})
        vcs_pl_sg = self.get_matching_vcs_cs_in_model(
                self.management_server, apps=1, ha_srv_cfgs=1,
                cs_props_dict={'active': '2', 'standby': '0',
                               'node_list': 'n1,n2'})
        if vcs_fo_sg == [] or vcs_pl_sg == []:
            self.log('info', 'Creating suitable Service groups for TC01')
            fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2)
            apply_options_changes(
                fixtures, 'vcs-clustered-service', 0,
                {'active': '1', 'standby': '1', 'name': 'CS_124980_1',
                 'node_list': 'n1,n2'}, overwrite=True)
            apply_options_changes(
                fixtures, 'vcs-clustered-service', 1,
                {'active': '2', 'standby': '0', 'name': 'CS_124980_2',
                 'node_list': 'n1,n2'}, overwrite=True)
            apply_item_changes(
                fixtures, 'ha-service-config', 1,
                {'parent': "CS_124980_2",
                 'vpath': self.vcs_cluster_url + '/services/CS_124980_2/'
                                                 'ha_configs/HSC_124980_2'}
                )
            apply_item_changes(fixtures, 'service', 1,
                               {'parent': "CS_124980_2",
                                'destination': self.vcs_cluster_url +
                                               '/services/CS_124980_2/'
                                               'applications/APP_124980_2'
                                 })
            self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                      self.rpm_src_dir)
            vcs_fo_sg = self.vcs_cluster_url + '/services/' + \
                        fixtures['service'][0]['parent']
            vcs_pl_sg = self.vcs_cluster_url + '/services/' + \
                        fixtures['service'][1]['parent']

            self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                    add_to_cleanup=False)
        else:
            vcs_fo_sg = vcs_fo_sg[-1]
            vcs_pl_sg = vcs_pl_sg[-1]

        return vcs_fo_sg, vcs_pl_sg

    def _check_cs_in_model_tc02(self):
        """
        Method that will check for existing service groups in the model for
        test case 2
        :return: vcs_fo_sg (str): FO SG URL
                 vcs_pl_sg (str): PL SG URL
        """
        vip_props = {'network_name': 'traffic1',
                     'ipaddress': ['172.16.100.10', '172.16.100.12']}
        vcs_fo_sg = self.get_matching_vcs_cs_in_model(
                self.management_server, apps=1, ha_srv_cfgs=1,
                cs_props_dict={'active': '1', 'standby': '1',
                               'node_list': 'n3,n4',
                               'name': 'CS_124980_1'})
        vcs_pl_sg = self.get_matching_vcs_cs_in_model(
                self.management_server, apps=1, ha_srv_cfgs=1,
                cs_props_dict={'active': '2', 'standby': '0',
                               'node_list': 'n3,n4',
                               'name': 'CS_124980_2'})
        if vcs_fo_sg == [] or vcs_pl_sg == []:
            self.log('info', 'Creating suitable Service groups for TC02')
            fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2,
                                     vips_len=2)
            apply_options_changes(
                fixtures, 'vcs-clustered-service', 0,
                {'active': '1', 'standby': '1', 'name': 'CS_124980_1',
                 'node_list': 'n3,n4',
                 'dependency_list': 'CS_124980_2'}, overwrite=True)
            apply_options_changes(
                fixtures, 'vcs-clustered-service', 1,
                {'active': '2', 'standby': '0', 'name': 'CS_124980_2',
                 'node_list': 'n3,n4'}, overwrite=True)
            apply_item_changes(
                fixtures, 'ha-service-config', 1,
                {'parent': "CS_124980_2",
                 'vpath': self.vcs_cluster_url + '/services/CS_124980_2/'
                                                 'ha_configs/HSC_124980_2'}
                )
            apply_item_changes(
                fixtures, 'service', 1,
                {'parent': "CS_124980_2",
                 'destination': self.vcs_cluster_url +
                                '/services/CS_124980_2/applications/'
                                'APP_124980_2'})
            apply_item_changes(
                fixtures, 'vip', 0, {'vpath': self.vcs_cluster_url +
                                              '/services/CS_124980_2/'
                                              'ipaddresses/VIP1'}
            )
            apply_options_changes(
                fixtures, 'vip', 0, {
                    'network_name': '{0}'.format(vip_props['network_name']),
                    'ipaddress': '{0}'.format(vip_props['ipaddress'][0])},
                overwrite=True)
            apply_item_changes(
                fixtures, 'vip', 1, {'vpath': self.vcs_cluster_url +
                                              '/services/CS_124980_2/'
                                              'ipaddresses/VIP2'}
            )
            apply_options_changes(
                fixtures, 'vip', 1, {
                    'network_name': '{0}'.format(vip_props['network_name']),
                     'ipaddress': '{0}'.format(vip_props['ipaddress'][1])},
                overwrite=True)

            self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                      self.rpm_src_dir)

            vcs_fo_sg = self.vcs_cluster_url + fixtures['service'][0]['parent']
            vcs_pl_sg = self.vcs_cluster_url + fixtures['service'][1]['parent']

            self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                    add_to_cleanup=False)
        else:
            vcs_fo_sg = vcs_fo_sg[-1]
            vcs_pl_sg = vcs_pl_sg[-1]

            self.execute_cli_update_cmd(self.management_server, vcs_fo_sg,
                                        props='dependency_list=CS_124980_2')
            self.execute_cli_create_cmd(
                self.management_server, vcs_pl_sg + '/ipaddresses/VIP1',
                'vip', props='network_name={0} ipaddress={1}'
                    .format(vip_props['network_name'],
                            vip_props['ipaddress'][0]), add_to_cleanup=False)
            self.execute_cli_create_cmd(
                self.management_server, vcs_pl_sg + '/ipaddresses/VIP2',
                'vip', props='network_name={0} ipaddress={1}'
                    .format(vip_props['network_name'],
                            vip_props['ipaddress'][1]), add_to_cleanup=False)
            self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                    add_to_cleanup=False)
        return vcs_fo_sg, vcs_pl_sg

    def _check_cs_in_model_tc05(self):
        """
        Method that will check for existing service groups in the model for
        test case 5
        :return: vcs_fo_sg (str): FO SG URL
        """
        vcs_fo_sg = self.get_matching_vcs_cs_in_model(
                self.management_server, apps=1, ha_srv_cfgs=1,
                cs_props_dict={'active': '1', 'standby': '1',
                               'node_list': 'n2,n1',
                               'name': 'CS_124980_1'})
        if vcs_fo_sg == []:
            self.log('info', 'Creating suitable Service groups for TC05')
            fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1,
                                     vcs_trig=1)
            apply_options_changes(
                fixtures, 'vcs-clustered-service', 0,
                {'active': '1', 'standby': '1', 'name': 'CS_124980_1',
                 'node_list': 'n2,n1'}, overwrite=True)
            apply_item_changes(
                fixtures, 'service', 0,
                {'parent': "CS_124980_1",
                 'destination': self.vcs_cluster_url +
                                '/services/CS_124980_1/applications/'
                                'APP_124980_1'})
            vcs_fo_sg = self.vcs_cluster_url + '/services/' + fixtures[
                'service'][0]['parent']

            self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                      self.rpm_src_dir)

            self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                    add_to_cleanup=False)
        else:
            vcs_fo_sg = vcs_fo_sg[-1]
            self.execute_cli_create_cmd(self.management_server, vcs_fo_sg +
                                        '/triggers/trig1', 'vcs-trigger',
                                        props='trigger_type=nofailover',
                                        add_to_cleanup=False)

            self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                    add_to_cleanup=False)
        return vcs_fo_sg

    def _check_cs_in_model_tc06(self):
        """
        Method that will check for existing service groups in the model for
        test case 6
        :return: vcs_pl_sg (str): PL SG URL
        """
        vcs_pl_sg = self.get_matching_vcs_cs_in_model(
            self.management_server, apps=1, ha_srv_cfgs=1,
            cs_props_dict={'active': '1', 'standby': '0',
                           'node_list': 'n4',
                           'name': 'CS_124980_3'})
        if vcs_pl_sg == []:
            self.log('info', 'Creating suitable Service groups for TC06')
            fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1)
            apply_options_changes(
                fixtures, 'vcs-clustered-service', 0,
                {'active': '1', 'standby': '0', 'name': 'CS_124980_3',
                 'node_list': 'n4'}, overwrite=True)

            self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                      self.rpm_src_dir)
            vcs_pl_sg = self.vcs_cluster_url + \
                          fixtures['service'][0]['parent']

            self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                    add_to_cleanup=False)
        else:
            vcs_pl_sg = vcs_pl_sg[-1]
        return vcs_pl_sg

    def _check_cs_in_model_tc07(self):
        """
        Method that will check for existing service groups in the model for
        test case 7
        :return: vcs_fo_sg (str): FO SG URL
        """
        vcs_pl_sg = self.get_matching_vcs_cs_in_model(
            self.management_server, apps=1, ha_srv_cfgs=1,
            cs_props_dict={'active': '1', 'standby': '1',
                           'node_list': 'n4,n3',
                           'name': 'CS_124980_1'})
        if vcs_pl_sg == []:
            self.log('info', 'Creating suitable Service groups for TC07')
            fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1)
            apply_options_changes(
                fixtures, 'vcs-clustered-service', 0,
                {'active': '1', 'standby': '1', 'name': 'CS_124980_1',
                 'node_list': 'n4,n3'}, overwrite=True)
            self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                      self.rpm_src_dir)
            vcs_pl_sg = self.vcs_cluster_url + \
                        fixtures['service'][0]['parent']

            self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                    add_to_cleanup=False)
        else:
            vcs_pl_sg = vcs_pl_sg[-1]
            self.execute_cli_remove_cmd(self.management_server, vcs_pl_sg +
                                        '/triggers/trig1')
        return vcs_pl_sg

    def _check_cs_in_model_tc08(self):
        """
        Method that will check for existing service groups in the model for
        test case 7
        :return: vcs_fo_sg (str): FO SG URL
        """
        vcs_pl_sg = self.get_matching_vcs_cs_in_model(
            self.management_server, apps=1, ha_srv_cfgs=1,
            cs_props_dict={'active': '1', 'standby': '0',
                           'node_list': 'n3',
                           'name': 'CS_124980_3'})
        if vcs_pl_sg == []:
            self.log('info', 'Creating suitable Service groups for TC08')
            fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1)
            apply_options_changes(
                fixtures, 'vcs-clustered-service', 0,
                {'active': '1', 'standby': '0', 'name': 'CS_124980_3',
                 'node_list': 'n3'}, overwrite=True)
            self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                      self.rpm_src_dir)
            vcs_pl_sg = \
                self.vcs_cluster_url + fixtures['service'][0]['parent']

            self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                    add_to_cleanup=False)
        else:
            vcs_pl_sg = vcs_pl_sg[-1]
        return vcs_pl_sg

    def _check_disk_based_fencing(self):
        """
        This Method will verify the disk based fencing configuration on a
        physical deployment.
        :return: Nothing
        """
        gabconfig_cmd = '/sbin/gabconfig -a'
        vxfenadm_cmd = 'vxfenadm -d'
        vxfenmode_dir = '/etc/vxfenmode'
        vxfentab_dir = '/etc/vxfentab'
        vx_running = 'node   {0} in state  8 (running)'

        # Verify fencing is correctly configured on nodes
        self.log('info', 'Verifying fencing is configured on nodes by '
                         'checking if Port b exists')
        for node in self.node_exe:
            gabconfig_output = self.run_command(node, gabconfig_cmd,
                                                su_root=True,
                                                default_asserts=True)
            self.assertTrue(self.is_text_in_list('Port b gen',
                                                 gabconfig_output[0]))

            # Verify fencing is running on nodes
            self.log('info', 'Checking fencing is running on nodes')
            vxfenadm_output = self.run_command(node, vxfenadm_cmd,
                                               su_root=True,
                                               default_asserts=True)[0]
            node_astric = [active_node for active_node in vxfenadm_output
                           if '*' in active_node][0]
            node_id = node_astric.split()[1]
            self.assertTrue(self.is_text_in_list(vx_running.format(node_id),
                                                 vxfenadm_output))

            # Verify fencing configuration on nodes corresponds to main.cf
            # configuration
            self.log('info', 'Verfiying node configurations match main.cf '
                             'configuration')
            cat_cmd = self.rh_cmds.get_cat_cmd(vxfenmode_dir)
            vxfenout = self.run_command(node, cat_cmd, su_root=True,
                                        default_asserts=True)[0]
            vxfenmode = [vx_mode for vx_mode in vxfenout if 'vxfen_mode' in
                         vx_mode][0].split('vxfen_mode=')[1].upper()

            grep_cmd = \
                self.rh_cmds.get_grep_file_cmd(filepath=VCS_MAIN_CF_FILENAME,
                                               grep_items=[vxfenmode])
            maincf_out = self.run_command(node, grep_cmd, su_root=True,
                                          default_asserts=True)[0]

            self.assertEqual("UseFence = {0}".format(vxfenmode),
                             maincf_out[0])

            # Verify fencing disk type on nodes
            self.log('info', 'Verfiy disk types on nodes')
            cat_cmd = self.rh_cmds.get_cat_cmd('/etc/vxfendg')
            vxtypeout = self.run_command(node, cat_cmd, su_root=True,
                                         default_asserts=True)[0]
            self.assertEqual(vxtypeout[0].split('vxfen')[0], '')

            # Verify the number of nodes seen in vxfentab with the litp model
            self.log('info', 'Verifying the co-ordinator disks on nodes '
                             'seen in vxfentab')
            grep_cmd = \
                self.rh_cmds.get_grep_file_cmd(filepath=vxfentab_dir,
                                               grep_items='/dev')
            numdisk = self.run_command(node, grep_cmd, su_root=True,
                                       default_asserts=True)[0]
            self.assertEqual(len(numdisk), 3)

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

    @attr('all', 'expansion', 'story124980', 'story124980_tc01')
    def test_01_p_update_cs_node_list_fo_and_pl(self):
        """
        @tms_id: torf_124980_tc01
        @tms_requirements_id: TORF-124980
        @tms_title: Update cs node with fo and pl
        @tms_description:
        Test to verify that a user can update their clustered service node
        list for both failover and parallel type of clustered services
        @tms_test_steps:
            @step: Check if suitable SG is already created if not, create 1
            FO and 1 PL type of SG
            @result: Suitable SGs are applied on litp model
            @step: Assert node list prior to SG migration
            @result: Node list differs from node migration i.e. node1, node2
            @step: Update CS groups node list attribute to migrate groups to
            different nodes
            @result: Node is in updated state on relevant CS groups
            @step: Create and run plan
            @result: plan creates and executes successfully
            @step: Assert Node list after migration
            @result: Node list is updated after plan
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        timeout_mins = 90

        self.log('info', 'Checking if model is expanded already')
        self._is_model_expanded()
        # Check if model has been expanded already
        # Check if there are suitable service groups existing in
        # the model if not create them
        self.log('info', 'Checking for suitable Service Groups')
        vcs_fo_sg, vcs_pl_sg = self._check_cs_in_model_tc01()

        list_of_cs_names = [vcs_fo_sg.split(self.vcs_cluster_url +
                                            '/services/')[1],
                            vcs_pl_sg.split(self.vcs_cluster_url +
                                            '/services/')[1]]

        self.log('info', 'Asserting node list prior to migration update')
        # Assert node list prior to migration
        for vcs_grp in [vcs_fo_sg, vcs_pl_sg]:
            node_list = self._get_node_list_for_cs(vcs_grp)
            self.assertEqual(node_list, 'n1,n2')
            self.log('info', 'Updating node list for migration')
            self._update_node_list(vcs_grp, 'n3,n4')

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Asserting CS is brought back online on other nodes')
        cs_grp_name = \
            self.vcs.generate_clustered_service_name(list_of_cs_names[0],
                                                     self.cluster_id)

        self.wait_for_vcs_service_group_online(self.node_exe[2], cs_grp_name,
                                               online_count=1,
                                               wait_time_mins=15)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Asserting node list after migration update')
        # Assert node list after migration to other nodes
        for vcs_grp in [vcs_fo_sg, vcs_pl_sg]:
            node_list = self._get_node_list_for_cs(vcs_grp)
            self.assertEqual(node_list, 'n3,n4')

    @attr('all', 'expansion', 'story124980', 'story124980_tc02')
    def test_02_p_migrate_cs_with_vips_and_dependencies(self):
        """
        @tms_id: torf_124980_tc02
        @tms_requirements_id: TORF-124980
        @tms_title: Update cs node vips and dependencies configured
        @tms_description:
        Test to verify that a user can update their clustered service node
        list when VIPS and dependencies are present
        @tms_test_steps:
            @step: Check if suitable SG is already created if not, create 2
            SGs with VIPs and dependencies present
            @result: Suitable SGs are applied on litp model
            @step: Assert node list prior to SG migration
            @result: Node list differs from node migration i.e. node1, node2
            @step: Update CS groups node list attribute to migrate groups to
            different nodes
            @result: Node is in updated state on relevant CS groups
            @step: Create and run plan
            @result: plan creates and executes successfully
            @step: Assert Node list after migration
            @result: Node list is updated after plan
            @step: Assert Dependencies and VIPs are maintained after migration
            @result: Dependencies and VIPs are migrated over to new nodes
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        timeout_mins = 90

        self.log('info', 'Checking if model is expanded already')
        self._is_model_expanded()

        # Check if model has been expanded already
        # Check if there are suitable service groups existing in
        # the model if not create them
        self.log('info', 'Checking for suitable Service Groups')
        vcs_fo_sg, vcs_pl_sg = self._check_cs_in_model_tc02()

        list_of_cs_names = [vcs_fo_sg.split(self.vcs_cluster_url +
                                            '/services/')[1],
                            vcs_pl_sg.split(self.vcs_cluster_url +
                                            '/services/')[1]]
        self.log('info', 'Asserting node list prior to migration update')
        # Assert node list prior to migration
        for vcs_grp in [vcs_fo_sg, vcs_pl_sg]:
            node_list = self._get_node_list_for_cs(vcs_grp)
            self.assertEqual(node_list, 'n3,n4')
            self.log('info', 'Updating node list for migration')
            self._update_node_list(vcs_grp, 'n2,n1')

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Asserting CS is brought back online on other nodes')
        cs_grp_name = \
            self.vcs.generate_clustered_service_name(list_of_cs_names[0],
                                                     self.cluster_id)

        self.wait_for_vcs_service_group_online(self.node_exe[1], cs_grp_name,
                                               online_count=1,
                                               wait_time_mins=15)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))
        self.log('info', 'Asserting node list after migration update')
        # Assert node list after migration to other nodes

        for vcs_grp in [vcs_fo_sg, vcs_pl_sg]:
            node_list = self._get_node_list_for_cs(vcs_grp)
            self.assertEqual(node_list, 'n2,n1')

        self.log('info', 'Assert Dependencies and VIPs are '
                         'maintained after migration')
        self.assertEqual(
            self.get_props_from_url(self.management_server, vcs_fo_sg,
                                    filter_prop='dependency_list'),
            list_of_cs_names[1], 'Dependencies are not correct')
        self.assertEqual(
            len(self.find_children_of_collect(self.management_server,
                                              vcs_pl_sg + '/ipaddresses/',
                                              'vip')), 2,
            'Number of VIPs are incorrect')

    @attr('all', 'expansion', 'story124980', 'story124980_tc03', 'story397061')
    def test_03_p_migrate_cs_that_is_offline_due_to_cs_initial_online(
            self):
        """
        The cs_initial_online property now prevents the generation
        of all Online tasks when set to off. See TORF-397061
        @tms_id: torf_124980_tc03
        @tms_requirements_id: TORF-124980, TORF 397061
        @tms_title: Update cs that is offline due to cs_intial_online
        @tms_description:
        Test to verify that a user can update their clustered service node
        list with a service group that is offline
        @tms_test_steps:
            @step: Create 1 SG with cs_initial_online = off
            @result: SG is created and offline
            @step: Assert node list prior to migration
            @result: Node list is equal to n1
            @step: Update CS group node list attribute to migrate groups to
            different nodes
            @result: CS has updated node list
            @step: Create and run plan
            @result: Plan is created and run
            @step: Assert node list after migration
            @result: Node list is updated after plan
            @step: Assert CS is offline after update and
            cs_initial_online = off
            @result: CS is offline
            @step: Reset cs_initial_online to on
            @result: cs_initial_online is on
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        self.log('info', 'Check if litp model is expanded')
        self._is_model_expanded()

        self.backup_path_props(self.management_server, self.vcs_cluster_url)

        self.log('info', 'Switching cs_initial_online=off')
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    'cs_initial_online=off')

        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1,
                                 story='124980_3')

        cs_url = \
            self.vcs_cluster_url + '/services/' + \
            fixtures['service'][0]['parent']
        cs_name = fixtures['service'][0]['parent']
        self.log('info', 'Checking if CS_124980_3 is created already')

        apply_options_changes(fixtures, 'vcs-clustered-service', 0,
                              {'active': '1', 'standby': '0',
                               'name': 'CS_124980_3',
                               'node_list': 'n1'},
                              overwrite=True)
        self.log('info', 'Creating SG that will be offline')
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                add_to_cleanup=False)

        self.log('info', 'Assert the Service group is OFFLINE')
        cs_grp_name = self.vcs.generate_clustered_service_name(cs_name,
                                                               self.cluster_id)
        haval_cmd = self.vcs.get_hagrp_value_cmd(cs_grp_name, 'State',
                                                 self.node_exe[0])
        actual_state, _, _ = self.run_command(self.node_exe[0], haval_cmd,
                                               su_root=True,
                                               default_asserts=True)
        self.assertEqual(actual_state[0], '|OFFLINE|')

        self.log('info', 'Checking node list is as expected')
        node_list = self._get_node_list_for_cs(cs_url)
        self.assertEqual(node_list, 'n1')

        self.log('info', 'Updating node list for migration')
        self._update_node_list(cs_url, 'n4')

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                add_to_cleanup=False)

        self.log('info', 'Ensure SG stays offline during migration')

        haval_cmd = self.vcs.get_hagrp_value_cmd(cs_grp_name, 'State',
                                                 self.node_exe[3])
        actual_state, _, _ = self.run_command(self.node_exe[0], haval_cmd,
                                               su_root=True)

        self.assertEqual(actual_state[0], '|OFFLINE|', 'Service group '
                                           'not OFFLINE on node')

        self.log('info', 'Asserting node list after migration')
        node_list = self._get_node_list_for_cs(cs_url)
        self.assertEqual(node_list, 'n4', 'Incorrect node in '
                                                   'the node list')

        self.log('info', 'Asserting cs_intial_online has not changed as part '
                         'of migration')
        self.assertEqual(
            self.get_props_from_url(self.management_server,
                                    self.vcs_cluster_url,
                                    filter_prop='cs_initial_online'), 'off',
            'CS_INITIAL_ONLINE incorrect')

        timeout_mins = 60
        self.log('info', 'Wait for Plan to complete')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins),
                                 'Plan finished in an unexpected state')

        self.log('info', 'Switching cs_initial_online=on')
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    'cs_initial_online=on')

    @attr('all', 'expansion', 'story124980', 'story124980_tc05')
    def test_05_p_migrate_cs_with_triggers(self):
        """
        @tms_id: torf_124980_tc05
        @tms_requirements_id: TORF-124980
        @tms_title: Update cs that has triggers configured
        @tms_description:
        Test to verify that a user can update their clustered service node
        list with a service group that has vcs-triggers configured.
        @tms_test_steps:
            @step: Check if suitable CS is available in model if not create
            one with a trigger
            @result: SG exists in model with a trigger configured
            @step: Assert Node list prior to migration
            @result: Node list is equal to n2,n1
            @step: Update CS group node list attribute to migrate groups to
            different nodes n4,n3
            @result: CS has updated node list
            @step: Create/ Run plan
            @result: Plan is created and run
            @step: Assert Node list after migration
            @result: Node list is updated after plan
            @step: Cause trigger FO by removing PID file
            @result: SG fails over to new migration node list
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        lsb_name = "test-lsb-124980-1"
        timeout_mins = 60
        self.log('info', 'Check if litp model is expanded')
        self._is_model_expanded()

        # Check if model has been expanded already
        # Check if there are suitable service groups existing in
        # the model if not create them
        self.log('info', 'Checking for suitable Service Groups')
        vcs_fo_sg = self._check_cs_in_model_tc05()

        list_of_cs_names = vcs_fo_sg.split(self.vcs_cluster_url +
                                           '/services/')[1]

        self.log('info', 'Checking node list is as expected')
        node_list = self._get_node_list_for_cs(vcs_fo_sg)
        self.assertEqual(node_list, 'n2,n1')

        self.log('info', 'Updating node list for migration')
        self._update_node_list(vcs_fo_sg, 'n4,n3')

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Asserting CS is brought back online on other nodes')
        cs_grp_name = \
            self.vcs.generate_clustered_service_name(list_of_cs_names,
                                                     self.cluster_id)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        active_node, standby_node = self._check_active_node(cs_grp_name)

        self.wait_for_vcs_service_group_online(active_node, cs_grp_name,
                                               online_count=1,
                                               wait_time_mins=15)

        self.log('info', 'Asserting node list after migration update')
        # Assert node list after migration to other nodes

        node_list = self._get_node_list_for_cs(vcs_fo_sg)
        self.assertEqual(node_list, 'n4,n3')

        self.log('info', 'Cause trigger FO by removing PID file')
        # Remove PID file from /tmp/ directory on primary node by running
        # systemctl stop command
        stop_lsb_cmd = self.rh_cmds.get_systemctl_stop_cmd(lsb_name)
        stdout = self.run_command(active_node, stop_lsb_cmd,
                                  su_root=True, default_asserts=True)[0]
        self.assertEqual([], stdout)
        hastatus_state = \
            self.vcs.get_hagrp_value_cmd(cs_grp_name, "State")
        self.log('info', 'Verify SG fails over to correct standby node')
        # Wait for SG to fail over to secondary node
        # Check SG on node1 is faulted
        self.assertTrue(self.wait_for_cmd(standby_node, hastatus_state,
                                          expected_rc=0,
                                          expected_stdout='|ONLINE|',
                                          timeout_mins=2, su_root=True),
                        'Service did not come up on correct node')

        self.log('info', 'Clear faulted service group on node4')
        ha_clear = self.vcs.get_hagrp_cs_clear_cmd(cs_grp_name, active_node)
        self.run_command(active_node, ha_clear, su_root=True,
                         default_asserts=True)

    @attr('all', 'expansion', 'story124980', 'story124980_tc06')
    def test_06_p_migrate_cs_during_expansion_contraction(self):
        """
        @tms_id: torf_124980_tc06
        @tms_requirements_id: TORF-124980
        @tms_title: Update cs that will expand and contract with migration
        @tms_description:
        Test to verify that a user can update their clustered service node
        list with both expansion/contraction taking place.
        @tms_test_steps:
            @step: Check if suitable CS is available in model if not create
            one parallel SG (1, one node PL)
            @result: SG is exists in model
            @step: Assert Node list prior to migration
            @result: Node list is equal to n4
            @step: Update CS group node list attribute to migrate groups to
            different nodes (1 node PL SG to n1,n2)
            @result: CS has updated node list
            @step: Create/ Run plan
            @result: Plan is created and run
            @result: Node list is updated after plan
            @step: Update CS group node list attribute to migrate groups to
            different nodes (2 node PL SG to n3)
            @result: CS has updated node list
            @step: Create/ Run plan
            @result: Plan is created and run
            @step: Assert Node list after migration
            @result: Node list is updated after plan
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        timeout_mins = 60
        self.log('info', 'Check if litp model is expanded')
        self._is_model_expanded()
        # Check if model has been expanded already
        # Check if there are suitable service groups existing in
        # the model if not create them
        self.log('info', 'Checking for suitable Service Groups')
        vcs_pl_sg = self._check_cs_in_model_tc06()

        list_of_cs_names = vcs_pl_sg.split(self.vcs_cluster_url +
                                           '/services/')[1]

        self.log('info', 'Checking node list is as expected')
        node_list = self._get_node_list_for_cs(vcs_pl_sg)
        self.assertEqual(node_list, 'n4')

        self.log('info', 'Updating node list for migration, with '
                         'Expansion')
        self.execute_cli_update_cmd(self.management_server, vcs_pl_sg,
                                    props='active=2 node_list=n1,n2')

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Asserting CS is brought back online on other nodes')
        cs_grp_name = \
            self.vcs.generate_clustered_service_name(list_of_cs_names,
                                                     self.cluster_id)

        self.log('info', 'Ensure SG comes online during migration')
        self.wait_for_vcs_service_group_online(self.node_exe[1], cs_grp_name,
                                               online_count=2,
                                               wait_time_mins=15)
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Asserting node list after migration update')
        # Assert node list after migration to other nodes
        node_list = self._get_node_list_for_cs(vcs_pl_sg)
        self.assertEqual(node_list, 'n1,n2')

        self.log('info', 'Updating node list for migration, with Contraction')
        self.execute_cli_update_cmd(self.management_server, vcs_pl_sg,
                                    props='active=1 node_list=n3')

        node_list = self._get_node_list_for_cs(vcs_pl_sg)
        self.assertEqual(node_list, 'n3')

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Ensure SG comes online during migration')
        self.wait_for_vcs_service_group_online(self.node_exe[2], cs_grp_name,
                                               online_count=1,
                                               wait_time_mins=5)
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Asserting node list after migration update')
        # Assert node list after migration to other nodes
        node_list = self._get_node_list_for_cs(vcs_pl_sg)
        self.assertEqual(node_list, 'n3')

    @attr('all', 'expansion', 'story124980', 'story124980_tc07')
    def test_07_p_migrate_during_fo_to_pl(self):
        """
        @tms_id: torf_124980_tc07
        @tms_requirements_id: TORF-124980
        @tms_title: Update cs that will go from fo to pl with migration
        @tms_description:
        Test to verify that a user can update their clustered service node
        list during fail over to parallel.
        @tms_test_steps:
            @step: Check if suitable CS is available in model (1 fo sg) if not
            create one
            @result: SG is exists in model
            @step: Assert Node list prior to migration
            @result: Node list is equal to n4,n3
            @step: Update CS group node list attribute to migrate to nodes
            making the active count = 2
            @result: CS has updated node list
            @step: Create/ Run plan
            @result: Plan is created and run
            @step: Assert Node list after migration
            @result: Node list is updated after plan
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        timeout_mins = 60
        self.log('info', 'Check if litp model is expanded')
        self._is_model_expanded()
        # Check if model has been expanded already
        # Check if there are suitable service groups existing in
        # the model if not create them
        self.log('info', 'Checking for suitable Service Groups')
        vcs_sg = self._check_cs_in_model_tc07()

        list_of_cs_names = vcs_sg.split(self.vcs_cluster_url +
                                        '/services/')[1]

        self.log('info', 'Checking node list is as expected')
        node_list = self._get_node_list_for_cs(vcs_sg)
        self.assertEqual(node_list, 'n4,n3')

        self.log('info', 'Updating node list for migration, with '
                         'Expansion')
        self.execute_cli_update_cmd(self.management_server, vcs_sg,
                                    props='active=2 standby=0 '
                                          'node_list=n1,n2')

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Asserting CS is brought back online on other nodes')
        cs_grp_name = \
            self.vcs.generate_clustered_service_name(list_of_cs_names,
                                                     self.cluster_id)

        self.wait_for_vcs_service_group_online(self.node_exe[0],
                                               cs_grp_name,
                                               online_count=2,
                                               wait_time_mins=15)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Asserting node list after migration update')
        # Assert node list after migration to other nodes
        node_list = self._get_node_list_for_cs(vcs_sg)
        self.assertEqual(node_list, 'n1,n2')

    @attr('all', 'expansion', 'story124980', 'story124980_tc08')
    def test_08_p_migrate_cs_during_apd(self):
        """
        @tms_id: torf_124980_tc08
        @tms_requirements_id: TORF-124980
        @tms_title: Test to verify CS can be migrated successfully during APD
        @tms_description:
        Test to verify that a user can update their clustered service
        successfully during an APD run
        @tms_test_steps:
            @step: Check if suitable CS is available in model (1 PL sg) if not
            create one
            @result: SG is exists in model
            @step: Assert Node list prior to migration
            @result: Node list is equal to n3
            @step: Update CS group node list attribute to migrate to nodes
            making the active count = 3 node_list=n2,n4,n1
            @result: CS has updated node list
            @step: Create/ Run plan
            @result: Plan is created and run
            @step: Run litpd restart prior to node lock and after service
            group is removed
            @result: LITPD deamon is restarted
            @step: Assert CS is fully re-installed and online after node
            lock phases
            @result: Sgs are online on different nodes after migration
            @step: Assert Node list after migration
            @result: Node list is updated after plan
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        task_descriptions = ['Remove VCS service group '
                             '"Grp_CS_c1_CS_124980_3_1"',
                             'Restore VCS service group '
                             '"Grp_CS_c1_CS_124980_3_1"']
        timeout_mins = 60
        self.log('info', 'Check if litp model is expanded')
        self._is_model_expanded()
        # Check if model has been expanded already
        # Check if there are suitable service groups existing in
        # the model if not create them
        self.log('info', 'Checking for suitable Service Groups')
        vcs_pl_sg = self._check_cs_in_model_tc08()

        list_of_cs_names = vcs_pl_sg.split(self.vcs_cluster_url +
                                           '/services/')[1]

        self.log('info', 'Checking node list is as expected')
        node_list = self._get_node_list_for_cs(vcs_pl_sg)
        self.assertEqual(node_list, 'n3')

        self.log('info', 'Updating node list for migration, with '
                         'Expansion')
        self.execute_cli_update_cmd(self.management_server, vcs_pl_sg,
                                    props='active=3 standby=0 '
                                          'node_list=n2,n4,n1')

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Asserting CS is removed prior to node lock')
        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 task_descriptions[0],
                                                 PLAN_TASKS_SUCCESS,
                                                 ignore_variables=False),
                        'Removal task was not run')

        self.log('info', 'Running litpd restart')
        self.restart_litpd_service(self.management_server)

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 task_descriptions[1],
                                                 PLAN_TASKS_SUCCESS,
                                                 ignore_variables=False),
                        'Service groups are being restored')

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Asserting CS is brought online on other nodes')
        cs_grp_name = \
            self.vcs.generate_clustered_service_name(list_of_cs_names,
                                                     self.cluster_id)
        haval_cmd = self.vcs.get_hagrp_value_cmd(cs_grp_name, 'State',
                                                 self.node_exe[3])
        stdout = self.run_command(self.node_exe[3], haval_cmd, su_root=True,
                         default_asserts=True)[0]
        self.assertEqual('|ONLINE|', stdout[0],
                         'Service group not ONLINE on correct nodes')

        self.log('info', 'Asserting node list after migration update')
        # Assert node list after migration to other nodes
        node_list = self._get_node_list_for_cs(vcs_pl_sg)
        self.assertEqual(node_list, 'n2,n4,n1')

    @attr('all', 'kgb-physical', 'story124980', 'story124980_tc12')
    def test_12_p_migrate_sg_with_fencing_configured(self):
        """
        @tms_id: TORF_124980_tc12
        @tms_requirements_id: TORF-124980
        @tms_title: Update sg node list on physical hardware
        @tms_description:
        Test to verify that a user can update their clustered service node
        list for both failover and parallel type of clustered services, with
        fencing configured on the cluster.
        @tms_test_steps:
            @step: Check for suitable SGs available in model (FO_vcs1, PL_vcs)
            @result: Suitable SGs are applied on litp model
            @step: Verify fencing is configured in model
            @result: Fencing configuration is asserted
            @step: Assert Node list prior to migration
            @result: Node list is equal to (FO_vcs1 = n2,n1/ PL_vcs = n1,n2)
            @step: Update CS groups node list attribute to migrate to nodes
            making node_list=n3,n4
            @result: CS has updated node list
            @step: Create/ Run plan
            @result: Plan is created and run
            @step: Assert Node list after migration
            @result: Node list is updated after plan
            @step: Assert fencing configuration is still running
            @result: Fencing is still running as expected
        @tms_test_precondition: PCDB 4 Node Expansion with fencing
        @tms_execution_type: Automated
        """
        timeout_mins = 60
        self.log('info', 'Check if litp model is expanded')
        self._is_model_expanded()
        # Check if model has been expanded already
        # Check if there are suitable service groups existing in
        # the model if not create them
        self.log('info', 'Check for suitable CS in model for migration')
        vcs_sgs = self.find_children_of_collect(self.management_server,
                                                self.vcs_cluster_url +
                                                '/services/',
                                                'clustered-service')
        for grps in vcs_sgs:
            if 'FO_SG_vm2' in grps:
                fo_sg = grps
            elif 'PL_SG_vm2' in grps:
                pl_sg = grps

        self.assertNotEqual(pl_sg, '', 'No Parallel Service groups found '
                                       'in model')
        self.assertNotEqual(fo_sg, '', 'No Fail-Over Service groups found '
                                       'in model')

        list_of_cs_names = [fo_sg.split(self.vcs_cluster_url +
                                            '/services/')[1],
                            pl_sg.split(self.vcs_cluster_url +
                                            '/services/')[1]]

        self.log('info', 'Check fencing configuration in model')
        self._check_disk_based_fencing()

        self.log('info', 'Assert node list is as expected')
        node_list = self._get_node_list_for_cs(fo_sg)
        self.assertEqual(node_list, 'n3,n1')
        node_list = self._get_node_list_for_cs(pl_sg)
        self.assertEqual(node_list, 'n2,n3')

        self.log('info', 'Update node list for service groups')
        for vcs_grp in [fo_sg, pl_sg]:
            self._update_node_list(vcs_grp, 'n3,n4')

        # Create/ Run plan
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Asserting CS is brought back online on other nodes')
        cs_grp_name = \
            self.vcs.generate_clustered_service_name(list_of_cs_names[0],
                                                     self.cluster_id)
        self.wait_for_vcs_service_group_online(self.node_exe[2], cs_grp_name,
                                               online_count=1,
                                               wait_time_mins=15)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Assert node list after SG migration')
        for vcs_grp in [fo_sg, pl_sg]:
            node_list = self._get_node_list_for_cs(vcs_grp)
            self.assertEqual(node_list, 'n3,n4',
                             'Node list in {0} SG is not as '
                             'expected'.format(vcs_grp))

        self.log('info', 'Check fencing is still running')
        self._check_disk_based_fencing()

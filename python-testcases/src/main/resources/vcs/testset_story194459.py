"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     July 2017
@author:    Stefan Ulian
@summary:   Integration Tests
            Agile: STORY-194459
"""
import os
from vcs_utils import VCSUtils
from test_constants import PLAN_COMPLETE, PLAN_TASKS_SUCCESS
from litp_generic_test import GenericTest, attr
from generate import load_fixtures, generate_json, apply_options_changes, \
    apply_item_changes

STORY = '194459'


class Story194459(GenericTest):
    """
    TORF-194459:
        Description:
            As a LITP User, I want the ability to migrate one node of a
            failover Service Group
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
        super(Story194459, self).setUp()

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

        for node in self.nodes_urls:
            self.node_exe.append(
                self.get_node_filename_from_url(self.management_server, node))

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story194459, self).tearDown()

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
        :return: vcs_fo1_sg (str): FO1 SG URL
                 vcs_fo2_sg (str): FO2 SG URL
        """
        self.log('info', 'Creating suitable Service groups for TC01')
        fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '1', 'standby': '1', 'name': 'CS_194459_1',
             'node_list': 'n1,n2'}, overwrite=True)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 1,
            {'active': '1', 'standby': '1', 'name': 'CS_194459_2',
             'node_list': 'n3,n4'}, overwrite=True)
        apply_item_changes(
            fixtures, 'ha-service-config', 1,
            {'parent': "CS_194459_2",
             'vpath': self.vcs_cluster_url + '/services/CS_194459_2/'
                                             'ha_configs/HSC_194459_2'}
            )
        apply_item_changes(fixtures, 'service', 1,
                           {'parent': "CS_194459_2",
                            'destination': self.vcs_cluster_url +
                                           '/services/CS_194459_2/'
                                           'applications/APP_194459_2'
                             })
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)
        vcs_fo1_sg = self.vcs_cluster_url + '/services/' + \
                    fixtures['service'][0]['parent']
        vcs_fo2_sg = self.vcs_cluster_url + '/services/' + \
                    fixtures['service'][1]['parent']

        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                add_to_cleanup=False)

        return vcs_fo1_sg, vcs_fo2_sg

    def _check_cs_in_model_tc02(self):
        """
        Method that will check for existing service groups in the model for
        test case 2
        :return: vcs_fo1_sg (str): FO SG URL
                 vcs_fo2_sg (str): FO SG URL
        """
        vip_props = {'network_name': 'traffic1',
                     'ipaddress': ['172.16.100.11', '172.16.100.13']}
        vcs_fo1_sg = self.get_matching_vcs_cs_in_model(
                self.management_server, apps=1, ha_srv_cfgs=1,
                cs_props_dict={'active': '1', 'standby': '1',
                               'node_list': 'n1,n3',
                               'name': 'CS_194459_1'})
        vcs_fo2_sg = self.get_matching_vcs_cs_in_model(
                self.management_server, apps=1, ha_srv_cfgs=1,
                cs_props_dict={'active': '1', 'standby': '1',
                               'node_list': 'n3,n2',
                               'name': 'CS_194459_2'})
        if vcs_fo1_sg == [] or vcs_fo2_sg == []:
            self.log('info', 'Creating suitable Service groups for TC02')
            fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2,
                                     vips_len=2)
            apply_options_changes(
                fixtures, 'vcs-clustered-service', 0,
                {'active': '1', 'standby': '1', 'name': 'CS_194459_1',
                 'node_list': 'n1,n3',
                 'dependency_list': 'CS_194459_2'}, overwrite=True)
            apply_options_changes(
                fixtures, 'vcs-clustered-service', 1,
                {'active': '1', 'standby': '1', 'name': 'CS_194459_2',
                 'node_list': 'n3,n2'}, overwrite=True)
            apply_item_changes(
                fixtures, 'ha-service-config', 1,
                {'parent': "CS_194459_2",
                 'vpath': self.vcs_cluster_url + '/services/CS_194459_2/'
                                                 'ha_configs/HSC_194459_2'}
                )
            apply_item_changes(
                fixtures, 'service', 1,
                {'parent': "CS_194459_2",
                 'destination': self.vcs_cluster_url +
                                '/services/CS_194459_2/applications/'
                                'APP_194459_2'})
            apply_item_changes(
                fixtures, 'vip', 0, {'vpath': self.vcs_cluster_url +
                                              '/services/CS_194459_2/'
                                              'ipaddresses/VIP1'}
            )
            apply_options_changes(
                fixtures, 'vip', 0, {
                    'network_name': '{0}'.format(vip_props['network_name']),
                    'ipaddress': '{0}'.format(vip_props['ipaddress'][0])},
                overwrite=True)
            apply_item_changes(
                fixtures, 'vip', 1, {'vpath': self.vcs_cluster_url +
                                              '/services/CS_194459_2/'
                                              'ipaddresses/VIP2'}
            )
            apply_options_changes(
                fixtures, 'vip', 1, {
                    'network_name': '{0}'.format(vip_props['network_name']),
                     'ipaddress': '{0}'.format(vip_props['ipaddress'][1])},
                overwrite=True)

            self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                      self.rpm_src_dir)

            vcs_fo1_sg = self.vcs_cluster_url + \
                fixtures['service'][0]['parent']
            vcs_fo2_sg = self.vcs_cluster_url + \
                fixtures['service'][1]['parent']

            self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                    add_to_cleanup=False)
        else:
            vcs_fo1_sg = vcs_fo1_sg[-1]
            vcs_fo2_sg = vcs_fo2_sg[-1]

            self.execute_cli_update_cmd(self.management_server, vcs_fo1_sg,
                                        props='dependency_list=CS_194459_2')
            self.execute_cli_create_cmd(
                self.management_server, vcs_fo2_sg + '/ipaddresses/VIP1',
                'vip', props='network_name={0} ipaddress={1}'
                    .format(vip_props['network_name'],
                            vip_props['ipaddress'][0]), add_to_cleanup=False)
            self.execute_cli_create_cmd(
                self.management_server, vcs_fo2_sg + '/ipaddresses/VIP2',
                'vip', props='network_name={0} ipaddress={1}'
                    .format(vip_props['network_name'],
                            vip_props['ipaddress'][1]), add_to_cleanup=False)
            self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                    add_to_cleanup=False)
        return vcs_fo1_sg, vcs_fo2_sg

    def _check_cs_in_model_tc04(self):
        """
        Method that will check for existing service groups in the model for
        test case 7
        :return: vcs_fo1_sg (str): FO SG URL
        """
        vcs_fo1_sg = self.get_matching_vcs_cs_in_model(
            self.management_server, apps=1, ha_srv_cfgs=1,
            cs_props_dict={'active': '1', 'standby': '1',
                           'node_list': 'n1,n4',
                           'name': 'CS_194459_1'})
        if vcs_fo1_sg == []:
            self.log('info', 'Creating suitable Service groups for TC04')
            fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1)
            apply_options_changes(
                fixtures, 'vcs-clustered-service', 0,
                {'active': '1', 'standby': '1', 'name': 'CS_194459_1',
                 'node_list': 'n1,n4'}, overwrite=True)
            self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                      self.rpm_src_dir)
            vcs_fo1_sg = \
                self.vcs_cluster_url + fixtures['service'][0]['parent']

            self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                    add_to_cleanup=False)
        else:
            vcs_fo1_sg = vcs_fo1_sg[-1]
        return vcs_fo1_sg

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

    @attr('all', 'expansion', 'Story194459', 'Story194459_tc01')
    def test_01_p_migrate_standby_node_multiple_fos(self):
        """
        @tms_id: torf_194459_tc01
        @tms_requirements_id: TORF-194459
        @tms_title: Update two fos css node list property by replacing the
                    standby node.
        @tms_description:
        Test to verify that a user can update the standby node of two failover
        clustered services.
        @tms_test_steps:
            @step: Ensure cs_initial_online is set to on
            @result: cs_initial_online is on
            @step: Check if CS_194459_1, CS_194459_2 FO SGs are already
            created if not create them.
            @result: CS_194459_1, CS_194459_2 FO SGs are applied on litp model
            @step: Assert node list prior to SG migration.
            CS_194459_1 is on  node1, node2.
            CS_194459_2 is on node3, node4.
            @result: Node list differs from node migration
            @step: Update CS groups node list attribute to migrate groups to
            different nodes by replacing only the standby node
            CS_194459_1 updated to node1, node3
            CS_194459_2 updated to node3, node2
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
        vcs_fo1_sg, vcs_fo2_sg = self._check_cs_in_model_tc01()

        list_of_cs_names = [vcs_fo1_sg.split(self.vcs_cluster_url +
                                            '/services/')[1],
                            vcs_fo2_sg.split(self.vcs_cluster_url +
                                            '/services/')[1]]

        vcs_prop = self.get_props_from_url(self.management_server,
                                           self.vcs_cluster_url,
                                           filter_prop='cs_initial_online')
        if vcs_prop == 'off':
            self.log('info', 'Switching cs_initial_online=on')
            self.execute_cli_update_cmd(self.management_server,
                                        self.vcs_cluster_url,
                                        'cs_initial_online=on')

        self.log('info', 'Asserting node list prior to migration update')
        # Assert node list prior to migration
        node_list = self._get_node_list_for_cs(vcs_fo1_sg)
        self.assertEqual(node_list, 'n1,n2')
        node_list = self._get_node_list_for_cs(vcs_fo2_sg)
        self.assertEqual(node_list, 'n3,n4')

        self.log('info', 'Updating node list for migration')
        self._update_node_list(vcs_fo1_sg, 'n1,n3')
        self._update_node_list(vcs_fo2_sg, 'n3,n2')

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

        # Assert node list after migration to other nodes
        self.log('info', 'Asserting node list after migration update')
        node_list = self._get_node_list_for_cs(vcs_fo1_sg)
        self.assertEqual(node_list, 'n1,n3')
        node_list = self._get_node_list_for_cs(vcs_fo2_sg)
        self.assertEqual(node_list, 'n3,n2')

    @attr('all', 'expansion', 'Story194459', 'Story194459_tc02')
    def test_02_p_migrate_standby_node_with_vips_and_dependencies(self):
        """
        @tms_id: torf_194459_tc02
        @tms_requirements_id: TORF-194459
        @tms_title: Update cs node vips and dependencies configured
        @tms_description:
        Test to verify that a user can update their clustered service standby
        node when VIPS and dependencies are present
        @tms_test_steps:
            @step: Check if CS_194459_1, CS_194459_2 are already created
            if not, create CS_194459_1, CS_194459_2 FO SGs with VIPs and
            dependencies present
            @result: CS_194459_1, CS_194459_2 FO SGs are applied on litp model
            @step: Assert node list prior to SG migration
            CS_194459_1 is on node1, node3
            CS_194459_2 is on node3, node2
            @result: Node list differs from node migration node list
            @step: Update CS groups node list attribute to migrate standby
            node to different node
            CS_194459_1 updated to node1, node4
            CS_194459_2 updated to node3, node1
            @result: Standby Node is in updated state on relevant CS groups
            @step: Create and run plan
            @result: plan creates and executes successfully
            @step: Assert Node list after migration
            @result: Node list is updated after plan
            @step: Assert Dependencies and VIPs are maintained after migration
            @result: Dependencies and VIPs are migrated over to new node
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
        vcs_fo1_sg, vcs_fo2_sg = self._check_cs_in_model_tc02()

        list_of_cs_names = [vcs_fo1_sg.split(self.vcs_cluster_url +
                                            '/services/')[1],
                            vcs_fo2_sg.split(self.vcs_cluster_url +
                                            '/services/')[1]]
        self.log('info', 'Asserting node list prior to migration update')

        # Assert node list prior to migration
        node_list = self._get_node_list_for_cs(vcs_fo1_sg)
        self.assertEqual(node_list, 'n1,n3')
        node_list = self._get_node_list_for_cs(vcs_fo2_sg)
        self.assertEqual(node_list, 'n3,n2')

        self.log('info', 'Updating node list for migration')
        self._update_node_list(vcs_fo1_sg, 'n1,n4')
        self._update_node_list(vcs_fo2_sg, 'n3,n1')

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
        node_list = self._get_node_list_for_cs(vcs_fo1_sg)
        self.assertEqual(node_list, 'n1,n4')
        node_list = self._get_node_list_for_cs(vcs_fo2_sg)
        self.assertEqual(node_list, 'n3,n1')

        self.log('info', 'Assert Dependencies and VIPs are '
                         'maintained after migration')
        self.assertEqual(
            self.get_props_from_url(self.management_server, vcs_fo1_sg,
                                    filter_prop='dependency_list'),
            list_of_cs_names[1], 'Dependencies are not correct')
        self.assertEqual(
            len(self.find_children_of_collect(self.management_server,
                                              vcs_fo2_sg + '/ipaddresses/',
                                              'vip')), 2,
            'Number of VIPs are incorrect')

    @attr('all', 'expansion', 'Story194459', 'Story194459_tc04')
    def test_04_p_migrate_standby_node_during_apd(self):
        """
        @tms_id: torf_194459_tc04
        @tms_requirements_id: TORF-194459
        @tms_title: Test to verify standby node can be migrated successfully
        during APD
        @tms_description:
        Test to verify that a user can update their clustered service
        successfully during an APD run
        @tms_test_steps:
            @step: Check if CS_194459_1 FO CS is available in model if not
            create it.
            @result: CS_194459_1 FO SGs exists in model
            @step: Assert Node list prior to migration
            @result: CS_194459_1 is on node1,node4
            @step: Update CS_194459_1 to migrate standby node to node2, node4
            @result: CS_194459_1 FO SG has updated node list
            @step: Create/ Run plan
            @result: Plan is created and run
            @step: Run litpd restart prior to node lock and after service
            group is removed
            @result: LITPD deamon is restarted
            @step: Assert CS is fully re-installed and online after node
            lock phases
            @result: SGs are online on different nodes after migration
            @step: Assert Node list after migration
            CS_194459_1 is on node2, node4
            @result: Node list is updated after plan
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        task_descriptions = ['Remove standby node "node1" from '
                             'clustered service "Grp_CS_c1_CS_194459_1"']

        timeout_mins = 60
        self.log('info', 'Check if litp model is expanded')
        self._is_model_expanded()
        # Check if model has been expanded already
        # Check if there are suitable service groups existing in
        # the model if not create them
        self.log('info', 'Checking for suitable Service Groups')
        vcs_fo1_sg = self._check_cs_in_model_tc04()

        list_of_cs_names = vcs_fo1_sg.split(self.vcs_cluster_url +
                                           '/services/')[1]

        self.log('info', 'Checking node list is as expected')
        node_list = self._get_node_list_for_cs(vcs_fo1_sg)

        self.assertEqual(node_list, 'n1,n4')

        self.log('info', 'Updating node list for migration')
        self.execute_cli_update_cmd(self.management_server, vcs_fo1_sg,
                                    props='active=1 standby=1 '
                                          'node_list=n2,n4')

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Asserting standby node is removed '
                         'prior to node lock')
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
        node_list = self._get_node_list_for_cs(vcs_fo1_sg)
        self.assertEqual(node_list, 'n2,n4')

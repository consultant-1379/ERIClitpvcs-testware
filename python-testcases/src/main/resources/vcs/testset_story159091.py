# pylint: disable=C0103
"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     November 2016
@author:    James Langan, Philip McGrath
@summary:   Integration Tests
            Agile: STORY-159091, STORY-397061
"""
import os
from vcs_utils import VCSUtils
from test_constants import PLAN_COMPLETE, PLAN_TASKS_SUCCESS, \
    PLAN_TASKS_RUNNING
from litp_generic_test import GenericTest, attr
from redhat_cmd_utils import RHCmdUtils
from generate import load_fixtures, generate_json, apply_options_changes, \
    apply_item_changes

STORY = '159091'


class Story159091(GenericTest):
    """
    TORF-159091:
        Description:
            As a LITP user, I want to update the node list of a service and
            not interrupt service on nodes which remain in the list
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
        super(Story159091, self).setUp()

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
        super(Story159091, self).tearDown()

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
        and after update
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

    def _deploy_cs_in_model(self):
        """
        Method that will deploy CS_159091_1 and CS_159091_2 which are
        used in subsequent test cases
        :return: Nothing
        """
        self.log('info', 'Creating suitable Service groups for TC01')
        fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2)
        apply_options_changes(
                fixtures, 'vcs-clustered-service', 0,
                {'active': '2', 'standby': '0', 'name': 'CS_159091_1',
                 'node_list': 'n1,n2'}, overwrite=True)

        self.log('info', 'Creating suitable Service groups for TC02')
        apply_options_changes(
                fixtures, 'vcs-clustered-service', 1,
                {'active': '2', 'standby': '0', 'name': 'CS_159091_2',
                 'node_list': 'n1,n2',
                 'dependency_list': 'CS_159091_1'}, overwrite=True)
        apply_item_changes(
                fixtures, 'ha-service-config', 1,
                {'parent': "CS_159091_2",
                 'vpath': self.vcs_cluster_url + '/services/CS_159091_2/'
                                                 'ha_configs/HSC_159091_2'}
                )
        apply_item_changes(
                fixtures, 'service', 1,
                {'parent': "CS_159091_2",
                 'destination': self.vcs_cluster_url +
                                '/services/CS_159091_2/applications/'
                                'APP_159091_2'})

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                    add_to_cleanup=False)

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
        stdout, _, _ = self.run_command(self.node_exe[0], 'hostname')
        self.assertEqual('node1', stdout[0])

    @attr('all', 'expansion', 'story159091', 'story159091_deploy')
    def test_deploy_159091_services_tc01(self):
        """
        @tms_id: test_deploy_159091_services_tc01
        @tms_requirements_id: TORF-159091
        @tms_title: Deploy two vcs-clustered-service for use in test cases
        @tms_description:
        Test to deploy two vcs-clustered-services which are later used in test
        cases to verify story TORF-159091
        @tms_test_steps:
            @step: Deploy two vcs-clustered-services
            @result: Success
        @tms_test_precondition: 4 node vcs-cluster deployed
        @tms_execution_type: Automated
        """
        self.log('info', 'Deploy services')
        self._deploy_cs_in_model()

    @attr('all', 'expansion', 'story159091', 'story159091_tc01')
    def test_01_p_add_and_remove_nodes_in_CS_node_list_for_PL(self):
        """
        @tms_id: torf_159091_tc01
        @tms_requirements_id: TORF-159091
        @tms_title: Update cs node list by adding removing and keeping nodes
        when there are dependencies between services
        @tms_description:
        Test to verify that a user can update a parallel vcs-clustered-service
        node_list by expanding and contracting the node_list in one plan
        @tms_test_steps:
            @step: Check if suitable SG is already created if not, create 1 PL
           type of SG
            @result: Suitable SGs are applied on litp model
            @step: Assert node list prior to SG node_list modification
            @result: Node list differs containing either 2 or 3 nodes
            @step: Update CS groups node list attribute to remove a subset of
            existing nodes and add new nodes, I.E. keep at least one original
            node in node_list.
            @result: Node is in updated state on relevant CS groups
            @step: Create and run plan
            @result: plan creates and executes successfully
            @step: Assert nodes removed from vcs-clustered-service node_list in
            LITP model are removed from VCS service group
            @result: Correct nodes are removed from VCS Service Group
            @step: Assert CS is unaffected on nodes which are in node_list
            property before and after update. CS should remain ONLINE
            @result: CS on unaffected node(s) remains ONLINE during plan
            and there is no Lock task in plan for unaffected node(s)
            @step: Assert CS is brought ONLINE on new nodes added to the
            node_list
            @result: CS is brought ONLINE on new node(s)
            @step: Assert Dependencies are all maintained
            @result: Dependencies are maintained after node_list update
        @tms_test_precondition: test_deploy_159091_services_tc01
        @tms_execution_type: Automated
        """
        timeout_mins = 90

        self.log('info', 'Checking if model is expanded already')
        self._is_model_expanded()

        # Get suitable service groups in model which have already
        # been deployed as a precondition
        self.log('info', 'Checking for suitable Service Groups')
        vcs_pl_group = self.get_matching_vcs_cs_in_model(
                self.management_server, apps=1, ha_srv_cfgs=1,
                vips_dict={'ipv4': '0', 'ipv6': '0'},
                cs_props_dict={'active': '2', 'standby': '0',
                               'node_list': 'n1,n2',
                               'name': 'CS_159091_1'})

        vcs_pl2_group = self.get_matching_vcs_cs_in_model(
                self.management_server, apps=1, ha_srv_cfgs=1,
                cs_props_dict={'active': '2', 'standby': '0',
                               'node_list': 'n1,n2',
                               'name': 'CS_159091_2'})

        self.assertTrue(len(vcs_pl_group) >= 0)
        self.assertTrue(len(vcs_pl2_group) >= 0)
        vcs_pl_sg = vcs_pl_group[0]
        vcs_pl2_sg = vcs_pl2_group[0]
        list_of_cs_names = [vcs_pl_sg.split(self.vcs_cluster_url +
                                            '/services/')[1],
                            vcs_pl2_sg.split(self.vcs_cluster_url +
                                            '/services/')[1]]

        self.log('info', 'Asserting node list prior to update')
        # Assert node list prior to update
        for vcs_grp in [vcs_pl_sg, vcs_pl2_sg]:
            node_list = self._get_node_list_for_cs(vcs_grp)
            self.assertEqual(node_list, 'n1,n2')

            self.log('info', 'Updating node list')
            self._update_node_list(vcs_grp, 'n1,n3,n4')
            self.execute_cli_update_cmd(self.management_server, vcs_grp,
                                    props='active=3')

        self.execute_cli_createplan_cmd(self.management_server)
        task_list = self.get_full_list_of_tasks(self.management_server)
        # Ensure node1 is not locked.
        self.assertFalse('Lock VCS on node "node1"' in task_list)

        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Asserting CS is brought back online on other nodes')
        cs_grp_name = \
            self.vcs.generate_clustered_service_name(list_of_cs_names[0],
                                                     self.cluster_id)

        self.wait_for_vcs_service_group_online(self.node_exe[0], cs_grp_name,
                                               online_count=3,
                                               wait_time_mins=15)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Asserting node list after update')
        for vcs_grp in [vcs_pl_sg, vcs_pl2_sg]:
            node_list = self._get_node_list_for_cs(vcs_grp)
            self.assertEqual(node_list, 'n1,n3,n4')

        self.log('info', 'Assert Dependencies are maintained')
        self.assertEqual(
            self.get_props_from_url(self.management_server, vcs_pl2_sg,
                                    filter_prop='dependency_list'),
            'CS_159091_1', 'Dependencies are not correct')

    @attr('all', 'expansion', 'story159091', 'story159091_tc03', 'story397061')
    def test_03_p_add_remove_nodes_CS_offline_cs_initial_online(self):
        """
        The cs_initial_online property now prevents the generation
        of all Online tasks when set to off. See TORF-397061
        @tms_id: torf_159091_tc03
        @tms_requirements_id: TORF-159091, TORF-397061
        @tms_title: Update cs node list by adding removing and keeping nodes
        @tms_description:
        Test to verify that a user can update a parallel vcs-clustered-service
        node_list by expanding and contracting the node_list in one plan
        @tms_test_steps:
            @step: Update cs_initial_online to off
            @result: cs_initial_online is off
            @step: Check if suitable SG is already created if not, create 1 PL
            type of SG
            @result: Suitable SGs are applied on litp model
            @step: Assert node list prior to SG node_list modification
            @result: Node list differs contains either 2 or 3 nodes
            @step: Update CS groups node list attribute to remove a subset of
            existing nodes and add new nodes, I.E. keep at least one original
            node in node_list.
            @result: Node is in updated state on relevant CS groups
            @step: Create and run plan
            @result: plan creates and executes successfully
            @step: Assert nodes removed from vcs-clustered-service node_list in
            LITP model are removed from VCS service group
            @result: Correct nodes are removed from VCS Service Group
            @step: Assert CS is unaffected on nodes which are in node_list
            property before and after update. CS should remain OFFLINE
            @result: CS on unaffected node(s) remains OFFLINE during plan
            @step: Assert CS is OFFLINE on new nodes added to the
            node_list
            @result: CS is OFFLINE on new node(s)
            @step: Reset cs_initial_online to on
            @result: cs_initial_online is on
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        self.log('info', 'Checking if model is expanded already')
        self._is_model_expanded()

        self.backup_path_props(self.management_server, self.vcs_cluster_url)

        self.log('info', 'Switching cs_initial_online=off')
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    'cs_initial_online=off')

        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1,
                                 story='159091_3')

        cs_url = \
            self.vcs_cluster_url + '/services/' + \
            fixtures['service'][0]['parent']
        cs_name = fixtures['service'][0]['parent']
        self.log('info', 'Checking if CS_159091_3 is created already')

        apply_options_changes(
                fixtures, 'vcs-clustered-service', 0,
                {'active': '2', 'standby': '0', 'name': 'CS_159091_3',
                 'node_list': 'n2,n3'}, overwrite=True)

        self.log('info', 'Creating SG that will be offline')
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                add_to_cleanup=False)

        self.log('info', 'Assert the Service group is OFFLINE')
        cs_grp_name = self.vcs.generate_clustered_service_name(cs_name,
                                                               self.cluster_id)
        haval_cmd = self.vcs.get_hagrp_value_cmd(cs_grp_name, 'State',
                                                 self.node_exe[1])
        self.run_command(self.node_exe[0], haval_cmd, su_root=True,
                         default_asserts=True)

        self.log('info', 'Checking node list is as expected')
        node_list = self._get_node_list_for_cs(cs_url)
        self.assertEqual(node_list, 'n2,n3', 'Incorrect nodes in '
                                            'the node list')

        self.log('info', 'Updating node list')
        self._update_node_list(cs_url, 'n1,n2,n4')
        self.execute_cli_update_cmd(self.management_server, cs_url,
                                    props='active=3')

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.run_and_check_plan(self.management_server,
                                PLAN_COMPLETE, 20)

        self.log('info', 'Ensure SG stays offline during during node_list '
                         'update')

        haval_cmd_n1 = self.vcs.get_hagrp_value_cmd(cs_grp_name, 'State',
                                                  self.node_exe[0])

        actual_state_n1, _, _ = self.run_command(self.node_exe[0],
                                                 haval_cmd_n1,
                                                 su_root=True,
                                                 default_asserts=True)

        self.assertEqual(actual_state_n1[0], '|OFFLINE|', 'Service group '
                                           'not OFFLINE on correct nodes')

        haval_cmd_n2 = self.vcs.get_hagrp_value_cmd(cs_grp_name, 'State',
                                                  self.node_exe[1])

        actual_state_n2, _, _ = self.run_command(self.node_exe[1],
                                                haval_cmd_n2,
                                                su_root=True,
                                                 default_asserts=True)

        self.assertEqual(actual_state_n2[0], '|OFFLINE|', 'Service group '
                                           'not OFFLINE on correct nodes')

        haval_cmd_n4 = self.vcs.get_hagrp_value_cmd(cs_grp_name, 'State',
                                                 self.node_exe[3])

        actual_state_n4, _, _ = self.run_command(self.node_exe[3],
                                                haval_cmd_n4,
                                                su_root=True,
                                                default_asserts=True)

        self.assertEqual(actual_state_n4[0], '|OFFLINE|', 'Service group '
                                           'not OFFLINE on correct nodes')

        self.log('info', 'Asserting node list after update')
        node_list = self._get_node_list_for_cs(cs_url)
        self.assertEqual(node_list, 'n1,n2,n4', 'Incorrect nodes in '
                                                   'the node list')

        self.log('info', 'Asserting cs_intial_online has not changed as part '
                         'of update')
        self.assertEqual(
            self.get_props_from_url(self.management_server,
                                    self.vcs_cluster_url,
                                    filter_prop='cs_initial_online'), 'off',
            'CS_INITIAL_ONLINE incorrect')

        self.log('info', 'Switching cs_initial_online=on')
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    'cs_initial_online=on')

    @attr('all', 'expansion', 'story159091', 'story159091_tc05')
    def test_05_p_add_remove_nodes_in_CS_during_APD(self):
        """
        @tms_id: torf_159091_tc05
        @tms_requirements_id: TORF-159091
        @tms_title: Update cs node list by adding removing and keeping nodes
        and restart litpd followed by new plan
        @tms_description:
        Test to verify that a user can update their SG node_list and after a
        litpd restart occurs create and run plan to completion.
        idempotency occurs
        @tms_test_steps:
            @step: Find already deployed and suitable SG in LITP model
            @result: Suitable SGs are applied on litp model
            @step: Assert node list prior to SG node_list modification
            @result: Node list differs contains either 2 or 3 nodes
            @step: Update CS groups node list attribute to remove a subset of
            existing nodes and add new nodes, I.E. keep at least one original
            node in node_list.
            @result: Node is in updated state on relevant CS groups
            @step: Create and run plan
            @result: plan is created and running
            @step: When plan is running task to Update VCS SG by removing
            node(s), perform a 'litpd restart'
            @result: litpd restart performed
            @step: Create and run plan again
            @result: plan creates and executes to completion successfully
            @step: Assert nodes removed from vcs-clustered-service node_list in
            LITP model are also removed from VCS service group
            @result: Correct nodes are removed from VCS Service Group
            @step: Assert CS is unaffected on nodes which are in node_list
            property before and after update. CS should remain ONLINE
            @result: CS on unaffected node(s) remains ONLINE during plan
            and there is no Lock task in plan for unaffected node(s)
            @step: Assert CS is brought ONLINE on new nodes added to the
            node_list
            @result: CS is brought ONLINE on new node(s)
        @tms_test_precondition: test_03
        @tms_execution_type: Automated
        """
        timeout_mins = 90
        task_descriptions = ['Update VCS service group '
                             '"Grp_CS_c1_CS_159091_3_1" to remove']

        self.log('info', 'Checking if model is expanded already')
        self._is_model_expanded()

        vcs_pl_group = self.get_matching_vcs_cs_in_model(
                self.management_server, apps=1, ha_srv_cfgs=1,
                cs_props_dict={'active': '3', 'standby': '0',
                               'node_list': 'n1,n2,n4',
                               'name': 'CS_159091_3'})

        self.assertTrue(len(vcs_pl_group) >= 0)
        vcs_pl_sg = vcs_pl_group[0]
        list_of_cs_names = vcs_pl_sg.split(self.vcs_cluster_url +
                                           '/services/')[1]

        self.log('info', 'Checking node list is as expected')
        node_list = self._get_node_list_for_cs(vcs_pl_sg)
        self.assertEqual(node_list, 'n1,n2,n4')

        self.log('info', 'Updating node list to remove 2 nodes,'
                         ' add 1 node and keep 1 node')
        self.execute_cli_update_cmd(self.management_server, vcs_pl_sg,
                                    props='active=2 standby=0 '
                                          'node_list=n4,n3')

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Asserting CS is removed')
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

        self.log('info', 'Asserting node list after update')
        node_list = self._get_node_list_for_cs(vcs_pl_sg)
        self.assertEqual(node_list, 'n4,n3')

    @attr('manual-test', 'story159091', 'story159091_tc06')
    def test_06_p_add_remove_nodes_robustness_APD(self):
        """
        @tms_id: torf_159091_tc06
        @tms_requirements_id: TORF-159091
        @tms_title: Update cs node list by adding removing and keeping nodes
        @tms_description:
        Test to verify APD robustness of TORF-159091
        NOTE: Never add this to a KGB/CDB. It takes hours to execute.
        @tms_test_steps:
            @step: Check if suitable SG is already created if not, create 1 PL
           type of SG
            @result: Suitable SGs are applied on litp model
            @step: Assert node list prior to SG node_list modification
            @result: Node list differs contains either 2 or 3 nodes
            @step: Update CS groups node list attribute to remove a subset of
            existing nodes and add new nodes, I.E. keep at least one original
            node in node_list.
            @result: Node is in updated state on relevant CS groups
            @step: Create and run plan
            @result: plan creates and executes successfully
            @step: Assert nodes removed from vcs-clustered-service node_list in
            LITP model are also removed from VCS service group
            @result: Correct nodes are removed from VCS Service Group
            @step: Assert CS is unaffected on nodes which are in node_list
            property before and after update. CS should remain ONLINE
            @result: CS on unaffected node(s) remains ONLINE during plan
            and there is no Lock task in plan for unaffected node(s)
            @step: Assert CS is brought ONLINE on new nodes added to the
            node_list
            @result: CS is brought ONLINE on new node(s)
        @tms_test_precondition: test_03
        @tms_execution_type: Automated.
        """
        timeout_mins = 90

        self.log('info', 'Checking if model is expanded already')
        self._is_model_expanded()

        vcs_pl_group = self.get_matching_vcs_cs_in_model(
                self.management_server, apps=1, ha_srv_cfgs=1,
                cs_props_dict={'active': '3', 'standby': '0',
                               'node_list': 'n1,n2,n4',
                               'name': 'CS_159091_3'})

        self.assertTrue(len(vcs_pl_group) >= 0)
        vcs_pl_sg = vcs_pl_group[0]
        list_of_cs_names = vcs_pl_sg.split(self.vcs_cluster_url +
                                           '/services/')[1]

        self.log('info', 'Checking node list is as expected')
        node_list = self._get_node_list_for_cs(vcs_pl_sg)
        self.assertEqual(node_list, 'n1,n2,n4')

        self.log('info', 'Updating node list to remove 2 nodes,'
                         ' add 1 node and keep 1 node')
        self.execute_cli_update_cmd(self.management_server, vcs_pl_sg,
                                    props='active=2 standby=0 '
                                          'node_list=n4,n3')

        self.execute_cli_createplan_cmd(self.management_server)
        task_list = self.get_full_list_of_tasks(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)
        self.perform_repeated_apd_runs(self.management_server,
                                       task_list,
                                       PLAN_TASKS_RUNNING)

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

        self.log('info', 'Asserting node list after update')
        node_list = self._get_node_list_for_cs(vcs_pl_sg)
        self.assertEqual(node_list, 'n4,n3')

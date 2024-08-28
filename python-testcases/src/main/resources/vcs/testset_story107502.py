"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     March 2017
@author:    Ciaran Reilly, Iacopo Isimbaldi, Gary O, Stefan Ulian,
            Alex Kabargin
@summary:   Integration Tests
            Agile: STORY-107502
"""

from generate import load_fixtures, generate_json, apply_options_changes, \
    apply_item_changes
from litp_generic_test import GenericTest, attr
from re import I as insensitive, match
from redhat_cmd_utils import RHCmdUtils
from rpm_generator import generate_rpm
from test_constants import PLAN_COMPLETE, PLAN_TASKS_SUCCESS, \
    PP_PKG_REPO_DIR, PLAN_FAILED
from vcs_utils import VCSUtils

import os

STORY = '107502'
RPM_DIR = os.path.dirname(os.path.realpath(__file__)) + '/rpm-out/dist/'
BAD_RPM = 'EXTR-lsbwrapper-fail-{0}-{1}-{2}-1.noarch.rpm'
OFFLINE_STATE = '|OFFLINE|'
FAULTED_STATE = '|OFFLINE|FAULTED|'
ONLINE_STATE = '|ONLINE|'
UNLOCK_TASK = 'Unlock VCS on node "{0}"'
LOCK_TASK = 'Lock VCS on node "{0}"'


class Story107502(GenericTest):
    """
    TORF-107502:
        Description:
            As a LITP User I want a node lock to proceed even if one or more
            of my Service Groups are OFFLINE and/or FAULTED so that my upgrade
            could possibly fix the underlying issue
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
        super(Story107502, self).setUp()

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

        self.loc_dir = os.path.dirname(os.path.realpath(__file__))

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story107502, self).tearDown()

        # Remove unused RPMs for next test case iteration
        self.run_command(self.management_server,
                         "rm -f {0}/EXTR-lsbwrapper-*".format(PP_PKG_REPO_DIR),
                         su_root=True)

    def baseline(self, vcs_len, app_len, hsc_len, vips_len=0, cleanup=False,
                 vcs_trig=0, valid_rpm=1, story=STORY):
        """
        Description:
            Runs if no suitable CS group is found with every test case to set
            up litp model with vcs/app and ha service parameters
        Parameters:
            vcs_len: (int) Number of VCS CS
            app_len: (int) Number of applications
            hsc_len: (int) Number of HA Service Configs
            vips_len: (int) Number of VIPs required
            valid_rpm: (int) Number relates to Stable/ Unstable version of RPM
            vcs_trig: (int) Number of vcs-triggers to generate
            cleanup: (bool) Remove the service during the cleanup tasks
        Actions:
            Declares fixtures dictionary for litp model generation
        Returns:
            fixtures dictionary
        """

        _json = generate_json(to_file=False, story=story,
                              vcs_length=vcs_len,
                              app_length=app_len,
                              hsc_length=hsc_len,
                              vip_length=vips_len,
                              vcs_trigger=vcs_trig,
                              valid_rpm=valid_rpm,
                              add_to_cleanup=cleanup)

        return load_fixtures(story, self.vcs_cluster_url,
                             self.nodes_urls, input_data=_json)

    def create_service(self, name, valid_rpm, active, standby, nodes,
                       cleanup=True):
        """
        Method to create a clustered service

        :param name: (str) Name of the clustered service
        :param valid_rpm: (int) Type of RPM used by the clustered service
        :param active: (int) Number of active nodes
        :param standby: (int) Number of standby nodes
        :param nodes: (str) Nodes on which run the clustered service
        :param cleanup: (boolean) Remove the service during the cleanup tasks
        :return: fixtures dictionary
        """
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1,
                                 valid_rpm=valid_rpm, story=name,
                                 cleanup=cleanup)

        apply_options_changes(fixtures, 'vcs-clustered-service', 0, {
            'active': '{0}'.format(active),
            'standby': '{0}'.format(standby),
            'name': 'CS_{0}_1'.format(name),
            'node_list': '{0}'.format(nodes)
        }, overwrite=True)

        apply_item_changes(fixtures, 'service', 0, {
            'parent': "CS_{0}_1".format(name),
            'destination': self.vcs_cluster_url +
                           '/services/CS_{0}_1/applications'.format(name) +
                           '/APP_{0}'.format(name)
        })

        return fixtures

    def _four_node_expansion(self):
        """
        Description:
            Method that will expand the litp model to have four running nodes
        Steps:
            1. Expand the cluster in the litp model to have 4 nodes if not
            already defined
        Return:
            Nothing
        """
        net_hosts_props_dhcp = {'ip': '10.10.14.4',
                                'network_name': 'dhcp_network'}
        net_hosts_props_mgmt = {'ip': '192.168.0.4',
                                'network_name': 'mgmt'}

        # Step 1: Expand the litp model to run on three nodes
        self.execute_expand_script(self.management_server,
                                   'expand_cloud_c1_mn2.sh',
                                   cluster_filename='192.168.0.42_4node.sh')
        self.execute_expand_script(self.management_server,
                                   'expand_cloud_c1_mn3.sh',
                                   cluster_filename='192.168.0.42_4node.sh')
        self.execute_expand_script(self.management_server,
                                   'expand_cloud_c1_mn4.sh',
                                   cluster_filename='192.168.0.42_4node.sh')

        self.execute_cli_create_cmd(
            self.management_server,
            self.vcs_cluster_url +
            '/network_hosts/nh21',
            'vcs-network-host',
            props='ip={0} network_name={1}'.format(
                net_hosts_props_dhcp['ip'],
                net_hosts_props_dhcp['network_name']),
            add_to_cleanup=False)

        self.execute_cli_create_cmd(
            self.management_server,
            self.vcs_cluster_url +
            '/network_hosts/nh22',
            'vcs-network-host',
            props='ip={0} network_name={1}'.format(
                net_hosts_props_mgmt['ip'],
                net_hosts_props_mgmt['network_name']),
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
        else:
            self.log('info', 'Model is already expanded')

    def set_Passwords(self):
        """
            Method that sets the passwords for newly expanded nodes
        :return: Nothing
        """
        for node in self.nodes_to_expand:
            self.assertTrue(self.set_pws_new_node(self.management_server,
                                                  node),
                            "Failed to set password")

        stdout, _, _ = self.run_command(self.nodes_to_expand[1], 'hostname')
        self.assertEqual(stdout[0], self.nodes_to_expand[1])

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

    def _update_vcs_cluster(self, switch='on'):
        """
        Description:
            Runs with nearly every test cases to update the cs_initial_online
            property to on/off depending on what phase in the TC
        Parameters:
            switch: used to turn cs_initial_online on /off
        Actions:
            Updates the vcs-cluster item
        Returns: None
        """
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    'cs_initial_online={0}'.format(switch))

    def _manually_attempt_bring_sg_online(self, sg_name, node):
        """
        Method to run 'hagrp -online sg_name -sys node' applied SGs in VCS
        :param sg_name: Name of SG
        :param node: Node to attempt ONLINING of SG on
        :return: Nothing
        """
        vcs_sg_name = self.vcs.generate_clustered_service_name(sg_name,
                                                               self.cluster_id)

        hagrp_online_cmd = self.vcs.get_hagrp_cs_online_cmd(vcs_sg_name, node)

        stdout = self.run_command(self.node_exe[0], hagrp_online_cmd,
                                  su_root=True, default_asserts=True)[0]
        self.assertNotEqual(stdout, [])

    def _assert_sg_in_stable_state(self, sg_name='', node=''):
        """
        Method to ensure SGs are in the assumed state during different stages
        of testing
        :param sg_name: (str) Name of SG
        :param node: (str) Node we wish to execute command on
        :return: sg_grp_state (list): State of SG across all nodes in cluster
        """
        vcs_sg_name = self.vcs.generate_clustered_service_name(sg_name,
                                                               self.cluster_id)

        node_check = '-state {0} -sys {1}'.format(vcs_sg_name, node)
        sg_state_cmd = self.vcs.get_hagrp_cmd(node_check)

        sg_grp_state = self.run_command(self.node_exe[0], sg_state_cmd,
                                        su_root=True, default_asserts=True)[0]

        return sg_grp_state

    def _update_critical_service_on_cluster(self, sg_name=''):
        """
        Description:
            Method used to update the critical service property on a vcs
            cluster
        Parameters:
            sg_name: Failover SG name specified as a critical_service on
            cluster level
        Actions:
            Updates the vcs-cluster item
        Returns: None
        """
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    'critical_service={0}'.format(sg_name))

    def _update_faulted_rpm_on_sg(self, number=1, version='2.0', story=STORY):
        """
        Method that will upgrade a Faulted RPM with a Stable RPM based on the
        SG that is passed into the method
        :param: number: (int) Used to determine which
        a faulted RPM package with
        :param: version: (str) Version of RPM that will be generated to install
        over bad RPM package
        :return: Nothing
        """
        # Generate Stable version of RPM, try catch needed due to SG
        # distinguishing between packages
        generate_rpm(story=story, number=number, version=version,
                     valid_rpm=3, overwrite_rpm=True)

        self.copy_file_to(self.management_server,
                          RPM_DIR + BAD_RPM.format(story, number, version),
                          '/tmp/', root_copy=True, add_to_cleanup=True)

        self.execute_cli_import_cmd(self.management_server, '/tmp/' +
                                    BAD_RPM.format(story, number, version),
                                    PP_PKG_REPO_DIR)

        self.execute_cli_update_cmd(self.management_server,
                                    '/software/items/EXTR-lsbwrapper-{0}-{1}'
                                    .format(story, number),
                                    props='version={0}-1'.format(version))

    def _stop_lsb_service(self, cs_name, node):
        """
        Method used to stop lsb service on a peer node
        :param cs_name: (str) SG name in litp
        :param node : (str) Node the lsb service will be stopped on
        :return: Nothing
        """
        app_url = self.find(self.management_server, self.vcs_cluster_url +
                            '/services/{0}/applications'.format(cs_name),
                            resource='service')[0]

        app_id = app_url.replace(self.vcs_cluster_url +
                                 '/services/{0}/applications/'
                                 .format(cs_name), "")

        lsb_name = self.get_props_from_url(self.management_server,
                                           '/software/services/{0}'
                                           .format(app_id),
                                           filter_prop='service_name')
        stop_lsb_cmd = self.rhc.get_systemctl_stop_cmd(lsb_name)
        stdout = self.run_command(node, stop_lsb_cmd,
                                  su_root=True, default_asserts=True)[0]
        self.assertEqual([], stdout)

    def _clear_faults_on_sgs_on_nodes(self, sg_name, node):
        """
        Method that issues hagrp -clear command in VCS
        :param sg_name: (str) SG name used to generate VCS SG name for command
        :param node: (str) Node that will have SG cleared on it
        :return: Nothing
        """
        vcs_sg_name = self.vcs.generate_clustered_service_name(sg_name,
                                                               self.cluster_id)

        hagrp_online_cmd = self.vcs.get_hagrp_cs_clear_cmd(vcs_sg_name, node)

        stdout = self.run_command(self.node_exe[0], hagrp_online_cmd,
                                  su_root=True, default_asserts=True)[0]
        self.assertEqual(stdout, [])

    def _setup_pre_condition_for_tcs(self, fixtures, active='1', standby='1',
                                     critical_flag=False):
        """
        Method to setup the pre-condition for TC1, TC4 and TC7
        :param: fixtures (dict): VCS Clustered Service configuration dictionary
        active (int): number of active nodes
        standby (int): number of standby nodes
        critical_flag (bool): flag defining the service is critical or not
        :return: Nothing
        """
        cs_1_name = fixtures['service'][0]['parent']
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '{0}'.format(active), 'standby': '{0}'.format(standby),
             'name': '{0}'.format(cs_1_name), 'node_list': 'n1,n2'},
            overwrite=True)

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)
        if critical_flag:
            self._update_critical_service_on_cluster(sg_name=cs_1_name)

    def _setup_sgs_pre_condition_for_tc2(self, fixtures, story, active,
                                         standby, node_list='n1,n2'):
        """
        Method to setup the pre-condition for TC2
        :param: fixtures (dict): VCS Clustered Service configuration dictionary
        :param: story (str) of current story plus relevence to SG created
        :param: active (int): number of active nodes
        :param: standby (int): number of standby nodes
        :param node_list (str) of nodes the CS G is online on
        :return: Nothing
        """
        apply_options_changes(fixtures, 'vcs-clustered-service', 0,
                              {'active': '{0}'.format(active),
                               'standby': '{0}'.format(standby),
                               'name': 'CS_{0}_1'.format(story),
                               'node_list': '{0}'.format(node_list)},
                              overwrite=True)
        apply_options_changes(fixtures, 'vcs-clustered-service', 1,
                              {'active': '{0}'.format(active),
                               'standby': '{0}'.format(standby),
                               'name': 'CS_{0}_2'.format(story),
                               'node_list': '{0}'.format(node_list)},
                              overwrite=True)
        apply_item_changes(
            fixtures, 'ha-service-config', 1,
            {'parent': "CS_{0}_2".format(STORY),
             'vpath':
                 self.vcs_cluster_url + '/services/CS_{0}_2/ha_configs/'
                                        'HSC_{0}_2'.format(story)})
        apply_item_changes(
            fixtures, 'service', 1,
            {'parent': "CS_{0}_2".format(story),
             'destination':
                 self.vcs_cluster_url + '/services/CS_{0}_2/applications'
                                        '/APP_{0}_2'.format(story)})

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

    def _setup_sgs_pre_condition_for_tc8(self, fixtures, story=STORY,
                                         node_list='n1'):
        """
        Method to setup the pre-condition for TC8
        :param: fixtures (dict): VCS Clustered Service configuration dictionary
        :param story (str) of current story plus relevance to SG created
        :param node_list (str) of nodes the CS G is online on
        :return: Nothing
        """
        apply_options_changes(fixtures, 'vcs-clustered-service', 0,
                              {'active': '1',
                               'standby': '0',
                               'name': 'CS_{0}_2'.format(story),
                               'node_list': '{0}'.format(node_list)},
                              overwrite=True)

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

    def _setup_sgs_pre_condition_for_tc9(self, fixtures, story=STORY,
                                         node_list='n1,n2'):
        """
        Method to setup the pre-condition for TC9
        :param: fixtures (dict): VCS Clustered Service configuration dictionary
        :param story (str) of current story plus relevance to SG created
        :param node_list (str) of nodes the CS G is online on
        :return: Nothing
        """
        apply_options_changes(fixtures, 'vcs-clustered-service', 0,
                              {'active': '2',
                               'standby': '0',
                               'name': 'CS_{0}_1'.format(story),
                               'node_list': '{0}'.format(node_list)},
                              overwrite=True)

        apply_options_changes(fixtures, 'vcs-clustered-service', 1,
                              {'active': '2',
                               'standby': '0',
                               'name': 'CS_{0}_2'.format(story),
                               'node_list': '{0}'.format(node_list)},
                              overwrite=True)
        apply_item_changes(
            fixtures, 'ha-service-config', 1,
            {'parent': "CS_{0}_2".format(STORY),
             'vpath':
                 self.vcs_cluster_url + '/services/CS_{0}_2/ha_configs/'
                                        'HSC_{1}_2'.format(story, story)})
        apply_item_changes(
            fixtures, 'service', 1,
            {'parent': "CS_{0}_2".format(story),
             'destination':
                 self.vcs_cluster_url + '/services/CS_{0}_2/applications'
                                        '/APP_{1}_2'.format(story, story)})

        apply_options_changes(fixtures, 'vcs-clustered-service', 2,
                              {'active': '1',
                               'standby': '1',
                               'name': 'CS_{0}_3'.format(story),
                               'node_list': '{0}'.format(node_list)},
                              overwrite=True)
        apply_item_changes(
            fixtures, 'ha-service-config', 2,
            {'parent': "CS_{0}_3".format(STORY),
             'vpath':
                 self.vcs_cluster_url + '/services/CS_{0}_3/ha_configs/'
                                        'HSC_{1}_3'.format(story, story)})
        apply_item_changes(
            fixtures, 'service', 2,
            {'parent': "CS_{0}_3".format(story),
             'destination':
                 self.vcs_cluster_url + '/services/CS_{0}_3/applications'
                                        '/APP_{1}_3'.format(story, story)})

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

    def _setup_pre_condition_for_tc13(self, fixtures, active='2', standby='0',
                                      initial_dependency_list=""
                                      ):
        """
        Method to setup the pre-condition for TC13
        :param: fixtures (dict): VCS Clustered Service configuration dictionary
        active (int): number of active nodes
        standby (int): number of standby nodes
        initial_dependency_list (str): comma separated list of dependent CSs
        :return: Nothing
        """
        cs_1_name = fixtures['service'][0]['parent']
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '{0}'.format(active), 'standby': '{0}'.format(standby),
             'name': '{0}'.format(cs_1_name), 'node_list': 'n1,n2',
             'initial_online_dependency_list': '{0}'
                 .format(initial_dependency_list)}, overwrite=True)

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

    def _setup_sgs_pre_condition_for_tc19(self, fault_fixtures,
                                          stable_fixtures,
                                          story_faul=STORY,
                                          story_stable=STORY):
        """
        Method to setup the pre-condition for TC19
        :param: fault_fixtures (dict): VCS Clustered Service
        configuration dictionary with faulted SGs
        :param: stable_fixtures (dict): VCS clustered services config
        dictionary with stable SG
        :param story_faul (str) of current story plus relevance to SG created
        :param story_stable (str) of current story plus relevance of SG
        created
        :return: Nothing
        """
        pl_sg2 = fault_fixtures['vcs-clustered-service'][1]['id']
        pl_sg3 = stable_fixtures['vcs-clustered-service'][0]['id']

        self.log('info', 'Test Case 12 Dependency list defined ')
        apply_options_changes(fault_fixtures, 'vcs-clustered-service', 0,
                              {'active': '2',
                               'standby': '0',
                               'name': 'CS_{0}_1'.format(story_faul),
                               'dependency_list': '{0},{1}'.format(pl_sg2,
                                                                   pl_sg3),
                               'node_list': 'n1,n2'},
                              overwrite=True)

        apply_options_changes(fault_fixtures, 'vcs-clustered-service', 1,
                              {'active': '2',
                               'standby': '0',
                               'name': 'CS_{0}_2'.format(story_faul),
                               'node_list': 'n1,n2'},
                              overwrite=True)
        apply_item_changes(
            fault_fixtures, 'ha-service-config', 1,
            {'parent': "CS_{0}_2".format(STORY),
             'vpath':
                 self.vcs_cluster_url + '/services/CS_{0}_2/ha_configs/'
                                        'HSC_{1}_2'.format(story_faul,
                                                           story_faul)})
        apply_item_changes(
            fault_fixtures, 'service', 1,
            {'parent': "CS_{0}_2".format(story_faul),
             'destination':
                 self.vcs_cluster_url + '/services/CS_{0}_2/applications'
                                        '/APP_{1}_2'.format(story_faul,
                                                            story_faul)})

        apply_options_changes(stable_fixtures, 'vcs-clustered-service', 0,
                              {'active': '2',
                               'standby': '0',
                               'name': 'CS_{0}_1'.format(story_stable),
                               'dependency_list': '{0}'.format(pl_sg2),
                               'node_list': 'n1,n2'},
                              overwrite=True)

        for fixtures in [fault_fixtures, stable_fixtures]:
            self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                      self.rpm_src_dir)

    def _setup_pre_condition_for_tc6(self, fixtures):
        """
        Method to setup the pre-condition for TC6
        :param: fixtures (dict): VCS Clustered Service configuration dictionary
        :return: Nothing
        """
        apply_options_changes(fixtures,
                              'vcs-clustered-service',
                              0,
                              {'active': '1', 'standby': '0',
                               'offline_timeout': '1',
                               'name': 'CS_107_2',
                               'node_list': 'n1'},
                              overwrite=True)

        # update default stop_command for lsb-service to cause offline failure
        service_options = fixtures['service'][0]['options_string']
        service_options += ' stop_command="/bin/true"'
        apply_item_changes(fixtures, 'service', 0,
                            {'options_string': service_options})

        # Apply CS and apps
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

    @attr('all', 'non-revert', 'story107502', 'story107502_tc01')
    def test_01_n_fnl_with_critical_serv(self):
        """
        @tms_id: torf_107502_tc01
        @tms_requirements_id: TORF-107502
        @tms_title: Faulted SG fixed with fnl feature
        @tms_description:
        test_01_n_fnl_with_critical_serv:
        If a SG is applied in the litp model and FAULTED through VCS, any
        subsequent plans that attempt to update/create items on the same nodes
        as the FAULTED SG, the lock task for the given SG should succeed,
        and the unlock task should fail (SG must be online with the
        critical_serv paramater)
        test_03_n_fnl_with_idemp_check_with_update:
        Test to verify if a user has an applied SG in litp that is FAULTED in
        VCS the fnl feature can be used to fix the SG issue during a
        litpd restart
        test_05_n_fnl_with_cs_intial_online:
        Test to verify that when a SG is created and applied using
        cs_intial_online property=off and a user wants to ONLINE the SG
        themselves in the future. If the SG becomes FAULTED in VCS the user
        can use the fnl feature to fix any issues
        @tms_test_steps:
            @step: Update cs_initial_online=off on vcs cluster
            @result: cs_initial_online=off on vcs cluster
            @step: Create faulted failover SG (on nodes n1,n2) in litp model
            using bad RPM package which is defined as a critical service
            on the cluster
            @result: Failover SG is defined in litp model
            @step: Create/ Run Plan and wait for plan to succeed
            @result: Plan is run to completion FO is now applied
            @step: Manually try ONLINE SG
            @result: SG1 becomes FAULTED
            @step: Update cs_initial_online = on
            @result: cs_initial_online is now on
            @step: Create new FO SG in model with stable package
            @result: New SG is defined in the litp model
            @step: Create/ Run plan
            @result: Plan is created and run
            @step: Ensure Lock task passes
            @result: Lock Task passes
            @step: Ensure plan fails unlock task on nodes
            @result: Unlock Fails due to ONLINING SG Fail
            @step: Update bad package for FAULTED SG to bring FO SG ONLINE
            @result: Stable package is generated and copied onto MS
            @step: Create/ Run plan again
            @result: Plan is created and run to completion
            @step: Ensure Lock task passes
            @result: Lock Task passes
            @step: run litpd restart
            @result: Plan is recreated and run to compltion
            @step: Ensure plan passes unlock task on nodes
            @result: Unlock Passes due to ONLINING SG Fail
        @tms_test_precondition: None
        @tms_execution_type: Automated
        """
        timeout_mins = 90
        self.log('info', 'Beginning Test Case 1')

        self.log('info', 'Step 1: Update cs_initial_online=off')
        self._update_vcs_cluster(switch='off')

        # Pre-condition for TC1
        self.log('info', 'Step 2: Create 1 FO SG with BAD RPM packages')
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1,
                                 story=STORY + 'crit', valid_rpm=3)

        cs_1_name = fixtures['service'][0]['parent']

        # Create SGs for TC1
        self._setup_pre_condition_for_tcs(fixtures, critical_flag=True)

        # Create/ Run plan until failure occurs
        self.log('info', 'Step 3: Create/ Run plan')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 3: Wait for plan to finish')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

        # Ensure SG is OFFLINE
        self.assertEqual('OFFLINE', self._assert_sg_in_stable_state(
            cs_1_name, 'node1')[0])

        self.log('info', 'Step 4: Manually attempt to ONLINE SG')
        self._manually_attempt_bring_sg_online(cs_1_name, node='node1')

        self.log('info', 'Ensure that SG1 is OFFLINE|FAULTED')
        cs_grp_name = self.vcs.generate_clustered_service_name(cs_1_name,
                                                               self.cluster_id)
        hastatus_state = self.vcs.get_hagrp_value_cmd(cs_grp_name, "State")
        self.assertTrue(self.wait_for_cmd(self.node_exe[0], hastatus_state,
                                          expected_rc=0,
                                          expected_stdout=FAULTED_STATE,
                                          timeout_mins=5, su_root=True),
                        'Service SG1 is not FAULTED')

        self.log('info', 'Step 5: Update cs_initial_online=on')
        self._update_vcs_cluster()

        self.log('info', 'Step 6: Create new FO SG in model with stable '
                         'package')
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1,
                                 story=STORY + 'stable', cleanup=True)

        self._setup_pre_condition_for_tcs(fixtures)

        # test_01_n_fnl_with_critical_serv
        # Normally we would assert the Unlock fails here but plan will add
        # additional 15 minutes execution time if this was to happen

        self.log('info', 'Step 10: Update bad package for FAULTED SG to bring '
                         'FO SG ONLINE')
        self._update_faulted_rpm_on_sg(story=STORY + 'crit')

        self.log('info', 'Step 11: Create/ Run plan again')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 14: Unlock Tasks pass in plan')
        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 UNLOCK_TASK.format('node1'),
                                                 PLAN_TASKS_SUCCESS,
                                                 ignore_variables=False))

        # End of TC 1 and 5
        self.log('info', 'Test cases 1, 3 and 5 are being run together')

        self.log('info', 'Step 13: Run litpd restart')
        self.restart_litpd_service(self.management_server)

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 15: Plan runs to completion')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

    @attr('all', 'expansion', 'story107502', 'story107502_tc02')
    def test_02_n_mult_faulted_sgs_irrlvnt_with_fnl_sgs_on_diff_nodes(self):
        """
        @tms_id: torf_107502_tc02
        @tms_requirements_id: TORF-107502
        @tms_title: Faulted SG fixed with fnl feature across multiple SGs
        @tms_description:
        test_02_n_mult_faulted_sgs_irrlvnt_with_fnl_sgs_on_diff_nodes:
        If a user has multiple parallel sgs that are faulted in VCS but
        applied in litp, and does not wish to fix them currently but wants to
        add more sgs to the model they can with fnl, and provided the sgs are
        on different nodes to the FAULTED sgs
        test_23_n_mult_sgs_faul_and_offline_throughout_clust_to_online_
        state_rm_pid:
        Test to verify that if a user has multiple applied SGs that are
        interrmitantly faulted between nodes in a cluster, along with OFFLINE
        SGs, the lock tasks in a litp plan will proceed and the unlock will
        pass due to the lock task bringing the Sgs all ONLINE.
        test_24_n_mult_sgs_fault_and_offline_throughout_clust_to_fault_
        state_bad_rpm:
        Test to verify that if a user has multiple applied SGs that are
        consistently faulted between nodes in a cluster, along with OFFLINE
        Sgs using bad RPMs, the lock tasks in a litp plan will proceed and
        the unlock will fail unless we fix the bad RPM with a stable version
        @tms_test_steps:
            @step: Update cs_initial_online=off on vcs cluster
            @result: cs_initial_online=off on vcs cluster
            @step: Create 4 Parallel SGs, 2 with stable RPMs and 2 with Bad
            RPM packages
            @result: 4 Parallel SGs are created in the litp model
            Create 4 Failover SGs, 2 with stable RPMs and 2 with Bad
            RPM packages
            @result: 4 Failover SGs are created in the litp model
            @step: Create/ Run Plan
            @result: Wait for plan to succeed
            @step: Ensure all SGs are OFFLINE
            @result: All SGs are OFFLINE
            @step: Manually attempt to ONLINE all SGs
            @result: All SGs are issued online commands
            @step: Ensure all relevant SGs become FAULTED
            @result: 2 PL and 2 FO SGs become FAULTED on both nodes
            @step: Remove PID files from n1 for all stable SGs
            @result: Wait for all SGs to become FAULTED on node1
            @step: Ensure Stable SGs are Still ONLINE on node2
            @result: Stable SGs are ONLINE on node2
            @step: Clear Faults through VCS on stable SGs node 1,
            for 1 PL and 1 FO SGs
            @result: SGs are OFFLINE on node n1
            @step: Update cs_initial_online=on
            @result: cs_initial_online is updated to on
            @step: Create 2 additional stable SGs on nodes 3 and 4
            @result: Additional SGs are defined in litp model regardless of
            FAULTED SGs
            @step: Update all Bad RPM Packages for FAULTED SGs
            @result: All bad RPM packages
            @step: Ensure all relevant SGs are ONLINE
            @result: All Sgs are ONLINE
        @tms_test_precondition: 4 Node cluster installed with litp
        @tms_execution_type: Automated
        """
        # Check if model has 4 nodes if not include expansion as part of CS
        # creation
        self._is_model_expanded()

        timeout_mins = 90
        self.log('info', 'Beginning Test Case 2')

        self.log('info', 'Step 1: Update cs_initial_online=off')
        self._update_vcs_cluster(switch='off')

        # Pre-condition for TC2, 23 and 24
        self.log('info', 'Step 2: Create 4 Parallel SGs, 2 with stable RPMs '
                         'and 2 with Bad RPM packages')
        faul_pl_fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2,
                                         valid_rpm=3, story=STORY + 'PL_Faul',
                                         cleanup=True)

        self._setup_sgs_pre_condition_for_tc2(faul_pl_fixtures,
                                              STORY + 'PL_Faul',
                                              active='2', standby='0')

        stable_pl_fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2,
                                           story=STORY + 'PL_stable',
                                           cleanup=True)

        self._setup_sgs_pre_condition_for_tc2(stable_pl_fixtures,
                                              STORY + 'PL_stable',
                                              active='2', standby='0')

        self.log('info', 'Step 2: Create 4 Failover SGs, 2 with stable RPMs '
                         'and 2 with Bad RPM packages')
        faul_fo_fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2,
                                         valid_rpm=3, story=STORY + 'FO_Faul',
                                         cleanup=True)

        self._setup_sgs_pre_condition_for_tc2(faul_fo_fixtures,
                                              STORY + 'FO_Faul',
                                              active='1', standby='1')

        stable_fo_fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2,
                                           story=STORY + 'FO_stable',
                                           cleanup=True)

        self._setup_sgs_pre_condition_for_tc2(stable_fo_fixtures,
                                              STORY + 'FO_stable',
                                              active='1', standby='1')

        self.log('info', 'Step 3: Create/ Run plan')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 4: Wait for plan to finish')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

        self.log('info', 'Step 5: Ensure all SGs are in OFFLINE state')
        # Ensure all SGs are OFFLINE
        for cs_name in [faul_pl_fixtures['service'][0]['parent'],
                        faul_pl_fixtures['service'][1]['parent'],
                        stable_pl_fixtures['service'][0]['parent'],
                        stable_pl_fixtures['service'][1]['parent'],
                        faul_fo_fixtures['service'][0]['parent'],
                        faul_fo_fixtures['service'][1]['parent'],
                        stable_fo_fixtures['service'][0]['parent'],
                        stable_fo_fixtures['service'][1]['parent']]:
            self.assertTrue(
                self.is_text_in_list('OFFLINE',
                                     self._assert_sg_in_stable_state(
                                         cs_name, 'node1')))

        self.log('info', 'Step 6: Manually attempt to ONLINE all SGs')
        for cs_name in [faul_pl_fixtures['service'][0]['parent'],
                        stable_pl_fixtures['service'][0]['parent'],
                        faul_fo_fixtures['service'][0]['parent'],
                        stable_fo_fixtures['service'][0]['parent']]:

            self.log('info', 'Step 6: Manually attempt to ONLINE SGs')
            self._manually_attempt_bring_sg_online(cs_name, node='node1')

            if 'PL' in cs_name:
                self._manually_attempt_bring_sg_online(cs_name, node='node2')

            cs_grp_name = \
                self.vcs.generate_clustered_service_name(cs_name,
                                                         self.cluster_id)
            hastatus_state = self.vcs.get_hagrp_value_cmd(cs_grp_name, "State")

            self.log('info', 'Step 7: Ensure all relevant SGs become FAULTED')
            if 'Faul' in cs_name:
                self.assertTrue(
                    self.wait_for_cmd(self.node_exe[0], hastatus_state,
                                      expected_rc=0,
                                      expected_stdout=FAULTED_STATE,
                                      timeout_mins=5, su_root=True),
                    'Service {0} is not FAULTED'.format(cs_name))

            self.log('info', 'Ensure all relevant SGs come ONLINE')
            if 'stable' in cs_name:
                self.assertTrue(
                    self.wait_for_cmd(self.node_exe[0], hastatus_state,
                                      expected_rc=0,
                                      expected_stdout=ONLINE_STATE,
                                      timeout_mins=5, su_root=True),
                    'Service {0} is not ONLINE'.format(cs_name))

                self.log('info', 'Step 8: Remove PID file from node1 causing '
                                 'SG to become FAULTED on n1')
                self._stop_lsb_service(cs_name, node=self.node_exe[0])

                self.log('info', 'Step 9: Wait for SGs on node 1 to become '
                                 'FAULTED')
                self.assertTrue(
                    self.wait_for_cmd(self.node_exe[0], hastatus_state,
                                      expected_rc=0,
                                      expected_stdout=FAULTED_STATE,
                                      timeout_mins=5, su_root=True),
                    'Service {0} is not FAULTED'.format(cs_name))

                self.log('info', 'Step 10: Wait for SGs on node 2 to come '
                                 'ONLINE')
                self.assertTrue(
                    self.wait_for_cmd(self.node_exe[1], hastatus_state,
                                      expected_rc=0,
                                      expected_stdout=ONLINE_STATE,
                                      timeout_mins=5, su_root=True),
                    'Service {0} is not ONLINE'.format(cs_name))

                self.log('info', 'Step 11: Clear the FAULTs on stable SGs'
                                 'on node n1')
                self._clear_faults_on_sgs_on_nodes(cs_name, 'node1')

                self.log('info', 'Step 12: Assert SG is now OFFLINE')
                self.assertEqual(
                    self._assert_sg_in_stable_state(cs_name, 'node1')[0],
                    'OFFLINE')

        self.log('info', 'Step 13: Update cs_initial_online=on')
        self._update_vcs_cluster()

        self.log('info', 'Step 14: Create additonal CS irrelevant of '
                         'FAULTED SGs')
        fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2, cleanup=True)

        self._setup_sgs_pre_condition_for_tc2(fixtures, STORY, active=2,
                                              standby=0, node_list='n3,n4')

        self.log('info', 'Step 15: Update all bad RPM packages previously '
                         'created')
        for faulted_rpms in [STORY + 'PL_Faul', STORY + 'FO_Faul']:
            self._update_faulted_rpm_on_sg(number=1, story=faulted_rpms)

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 16: Wait for plan to finish')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

        self.log('info', 'Step 17: Ensure relevant SGs come ONLINE')
        for cs_name in [faul_pl_fixtures['service'][0]['parent'],
                        stable_pl_fixtures['service'][0]['parent'],
                        faul_fo_fixtures['service'][0]['parent'],
                        stable_fo_fixtures['service'][0]['parent']]:
            self.assertEqual(self._assert_sg_in_stable_state(cs_name,
                                                             'node1')[0],
                             'ONLINE')
        self.assertEqual(self._assert_sg_in_stable_state(
            fixtures['service'][0]['parent'], 'node3')[0], 'ONLINE')

    @attr('all', 'revert', 'story107502', 'story107502_tc04')
    def test_04_n_fnl_with_vcs_triggers_used(self):
        """
        @tms_id: torf_107502_tc04
        @tms_requirements_id: TORF-107502
        @tms_title: FAULTED VCS SG fixed with fnl feature
        @tms_description:
        Test to verify if a user has an applied failover type SG defined in
        litp, configured with a "nofailover" type vcs-trigger, and the SG
        becomes FAULTED on both nodes. (Causing a 'ping-ping' state between
        two nodes due to the vcs-trigger configured), they can fix the
        problem with the new fnl feature in litp
        @tms_test_steps:
            @step: Create faulted failover SG in model using bad RPM
            @result: Failover SG is defined in the litp model
            @step: Configure nofailover vcs-trigger with failover SG
            @result: VCS-trigger is configured on failover SG in litp model
            @step: Update cs_initial_online=off on cluster level
            @result: cs_initial_online is off
            @step: Create/ Run plan
            @result: Wait for plan to successfully finish
            @step: Manually attempt to ONLINE faulted SG through hagrp commands
            @result: Wait for SG to become FAULTED and go into ping-pong state
            @step: Update cs_intial_online = on
            @result: cs_initial_online is updated back to on
            @step: Update bad RPM package on SG in attempt to bring it ONLINE
            @result: RPM Package is updated
            @step: Import and update package version in litp
            @result: Package is copied to MS and version is updated in model
            @step: Create/ Run plan again
            @result: Wait for plan to successfully finish
            @step: Ensure previously FAULTED SG is now ONLINE
            @result: SG should now be fully ONLINE
        @tms_test_precondition: None
        @tms_execution_type: Automated
        """
        timeout_mins = 90
        # Pre-condition for TC4
        self.log('info', 'Step 1: Create 1 FO SG with BAD RPM packages')
        self.log('info', 'Step 2: Create VCS nofailover Trigger')
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1, valid_rpm=3,
                                 vcs_trig=1, cleanup=True)

        self.log('info', 'Step 3: Update cs_initial_online=off')
        self._update_vcs_cluster(switch='off')

        cs_1_name = fixtures['service'][0]['parent']

        # Create SGs for TC4
        self._setup_pre_condition_for_tcs(fixtures)

        self.log('info', 'Step 4: Create/ Run plan')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 5: Wait for plan to finish')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

        self.log('info', 'Step 6: Manually attempt to ONLINE SG on node n1')
        self._manually_attempt_bring_sg_online(cs_1_name, 'node1')

        self.log('info', 'Step 7: Update cs_initial_online=on')
        self._update_vcs_cluster()

        cs_grp_name = self.vcs.generate_clustered_service_name(cs_1_name,
                                                               self.cluster_id)
        hastatus_state = self.vcs.get_hagrp_value_cmd(cs_grp_name, "State")

        self.log('info', 'Step 8: Ensure CS goes into OFFLINE|FAULTED and '
                         'tries ONLINE back on n1 after failing on both nodes')
        for node, state in zip([self.node_exe[0], self.node_exe[1]],
                               [FAULTED_STATE, '|OFFLINE|']):
            self.assertTrue(
                self.wait_for_cmd(node, hastatus_state,
                                  expected_rc=0,
                                  expected_stdout=state,
                                  timeout_mins=5, su_root=True,
                                  default_time=10),
                'Service {0} is not in proper state'.format(cs_1_name))

        self.assertTrue(
            self.wait_for_cmd(self.node_exe[0], hastatus_state,
                              expected_rc=0,
                              expected_stdout=FAULTED_STATE,
                              timeout_mins=5, su_root=True),
            'Service {0} is not in ping-pong state'.format(cs_1_name))

        self.log('info', 'Step 9: Import and Update Bad RPM package on SG')
        self._update_faulted_rpm_on_sg()

        self.log('info', 'Step 10: Create/ Run plan')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 11: Wait for plan to finish')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

        active_node, _ = self._check_active_node(cs_grp_name)
        self.log('info', 'Step 12: Ensure SG now comes ONLINE')
        self.assertEqual('ONLINE',
                         self._assert_sg_in_stable_state(cs_1_name,
                                                         active_node)[0],
                         'SG {0} did not come ONLINE'.format(cs_1_name))

    @attr('all', 'non-revert', 'story107502', 'story107502_tc_06')
    def test_06_n_fnl_sg_fails_to_stop_plan_fails(self):
        """
        @tms_id: torf_107502_tc06
        @tms_requirements_id: TORF-107502
        @tms_title: Faulted SG fixed with fnl feature across multiple SGs
        @tms_description:
        Test to verify that when an applied SG fails to be brought OFFLINE in
        a specific amount of time, the lock task in the plan will fail
        regardless of fnl feature.
        @tms_test_steps:
            @step: Create 1 Parallel type SG with 1 node and with
            offline_timeout=1 on node1
            @result: Parallel type SG is defined in the litp model with
            offline_timeout=1 on node1
            @step: Create/ Run plan
            @result: Ensure plan runs to completion
            @result: Parallel SG is ONLINE in VCS on node 1
            @step: Update cluster by adding a new SG
            @result: new parallel SG is defined in litp model
            @step: Create/ Run plan
            @result: Plan is created and run
            @result: lock task should fail due to offline timeout of previously
            added SG on node1.
        @tms_test_precondition: 2 Node cluster installed with litp
        @tms_execution_type: Automated
        """
        timeout_mins = 90
        self.log('info', 'Beginning Test Case 06')

        # Pre-condition for TC
        self.log('info', 'Pre-Step 1: Create 1 Parallel type SG with 1 node '
                         'and with offline_timeout=1')

        fixtures = self.baseline(vcs_len=1,
                                 app_len=1,
                                 hsc_len=1,
                                 valid_rpm=5,
                                 cleanup=False,
                                 story=STORY + 'stable_PL_delay')

        fixtures_2 = self.baseline(vcs_len=1,
                                   app_len=1,
                                   hsc_len=1,
                                   cleanup=True,
                                   story=STORY + 'stable_PL_1')

        cs_1_name = fixtures['service'][0]['parent']

        self._setup_pre_condition_for_tc6(fixtures)
        # Create/ Run plan until failure occurs
        self.log('info', 'Pre-Step 2: Create/ Run plan')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Pre-Step 3: Wait for plan to finish, '
                         'Check is PL SG ONLINE on n1')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

        self.assertTrue(self.is_text_in_list('ONLINE',
                                             self._assert_sg_in_stable_state(
                                                 cs_1_name, 'node1')))
        self.log("info", "Beginning Steps for test")
        self.log("info", "Step 1: Update cluster with single node PL SG on "
                         "node 'Node1'")
        # Create a 1 node PL service group on node1
        self._setup_sgs_pre_condition_for_tc8(fixtures_2,
                                              story=STORY + 'stable_PL_1')
        # Create/ Run plan until plan completes occurs
        self.log('info', 'Step 2: Create/ Run plan')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)
        self.log('info', 'Step 3: Wait for plan to fail, Due to lock task '
                         'failure')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_FAILED, timeout_mins),
                        msg="Plan did not fail in the allowed time")
        self.log("info", "Plan failed as expected , Test Passed")

    @attr('all', 'expansion', 'story107502', 'story107502_tc07')
    def test_07_n_deactivate_fault_critical_sg_with_fnl(self):
        """
        @tms_id: torf_107502_tc07
        @tms_requirements_id: TORF-107502
        @tms_title: Critically Faulted SG can be deactivated using fnl feature
        @tms_description:
        Test to verify that a user is able deactivate a FAULTED (applied) SG
        that is defined as a critical_service using the fnl feature
        @tms_test_steps:
            @step: Update cs_initial_online=off on vcs cluster
            @result: cs_initial_online=off on vcs cluster
            @step: Create a FO type SG with a bad RPM package on nodes 1 and 2
            @result: FO type SG is defined with bad RPM package
            @step: Update critical service to be equal to new FO SG
            @result: Critical service is now assigned
            @step: Create/ Run plan
            @result: Plan is created and run to completion
            @step: Manually attempt to ONLINE FO SG
            @result: FO SG becomes FAULTED in VCS
            @step: Ensure FO SG is now FAULTED
            @result: SG is Fully FAULTED on both nodes
            @step: Update cs_initial_online = on
            @result: cs_initial_online is updated back to on
            @step: Create new stable FO SG on nodes 3 and 4 that deactivates
            the FAULTED SG
            @result: New FO SG is defined in the litp model
            @step: Update critical_service property to point
            @result: New FO SG is now defined as the clusters critical service
            @step: Create/ Run plan again
            @result: Plan runs to completion
            @step: First FAULTED FO SG should now be removed from VCS
            @result: Previously FAULTED SG is removed from VCS
            @step: Old FO SG should have deactivated = true
            @result: Old FO SG has deactivated = true
            @step: New FO SG is fully ONLINE
            @result: New FO SG is fully ONLINE
        @tms_test_precondition: 4 Node cluster installed with litp
        @tms_execution_type: Automated
        """

        timeout_mins = 90
        # Check is model is already expanded to 4 nodes
        self._is_model_expanded()

        self.log('info', 'Step 1: Update cs_initial_online=off')
        self._update_vcs_cluster(switch='off')

        self.log('info', 'Step 2: Create new FO type SG with bad RPM')
        fault_fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1,
                                       valid_rpm=3, story=STORY + 'FO_Faul')

        fo_fault_cs_name = fault_fixtures['service'][0]['parent']
        self._setup_pre_condition_for_tcs(fault_fixtures)

        self.log('info', 'Step 3: Update critical service to be equal FO SG')
        self._update_critical_service_on_cluster(sg_name=fo_fault_cs_name)

        self.log('info', 'Step 4: Create/ Run plan')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 5: Wait for plan to finish')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

        self.log('info', 'Step 6: Manually attempt to ONLINE SG')
        self._manually_attempt_bring_sg_online(fo_fault_cs_name, 'node1')

        cs_grp_name = \
            self.vcs.generate_clustered_service_name(fo_fault_cs_name,
                                                     self.cluster_id)
        hastatus_state = self.vcs.get_hagrp_value_cmd(cs_grp_name, "State")

        self.log('info', 'Step 6: Ensure SG Becomes FAULTED')
        for node in [self.node_exe[0], self.node_exe[1]]:
            self.assertTrue(
                self.wait_for_cmd(node, hastatus_state, expected_rc=0,
                                  expected_stdout=FAULTED_STATE,
                                  timeout_mins=5, su_root=True),
                'Service {0} is not FAULTED'.format(fo_fault_cs_name))

        self.log('info', 'Step 7: Update cs_initial_online = on')
        self._update_vcs_cluster()

        self.log('info', 'Step 8: Create a stable FO SG that deactivates '
                         'the first Faulted SG')
        stable_fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1,
                                        story=STORY + 'FO_stable')

        fo_stable_cs_name = stable_fixtures['service'][0]['parent']
        apply_options_changes(
            stable_fixtures, 'vcs-clustered-service', 0,
            {'active': '1', 'standby': '1',
             'name': 'CS_{0}_1'.format(STORY + 'stable'),
             'node_list': 'n3,n4',
             'deactivates': '{0}'.format(fo_fault_cs_name)},
            overwrite=True)

        self.apply_cs_and_apps_sg(self.management_server, stable_fixtures,
                                  self.rpm_src_dir)

        self.log('info', 'Step 9: Update critical service to be equal FO SG')
        self._update_critical_service_on_cluster(sg_name=fo_stable_cs_name)

        self.log('info', 'Step 10: Create/ Run plan again')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 11: Wait for plan to finish')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

        self.log('info', 'Step 12: Ensure previously FAULTED SG is removed'
                         'from VCS')
        hagrp_list_cmd = self.vcs.get_hagrp_cmd('-list')
        stdout = self.run_command(self.node_exe[0], hagrp_list_cmd,
                                  su_root=True, default_asserts=True)[0]
        self.assertFalse(self.is_text_in_list(fo_fault_cs_name, stdout))

        self.log('info', 'Step 13: Ensure Old FO SG is deactivated=true in '
                         'litp model')
        self.assertEqual('true',
                         self.get_props_from_url(
                             self.management_server,
                             fault_fixtures['vcs-clustered-service'][0]
                             ['vpath'], filter_prop='deactivated'))

        self.log('info', 'Step 14: Ensure new SG is ONLINE')
        self.assertEqual('ONLINE',
                         self._assert_sg_in_stable_state(fo_stable_cs_name,
                                                         'node3')[0],
                         'SG {0} did not come ONLINE'.format(fo_stable_cs_name)
                         )

    @attr('all', 'revert', 'story107502', 'story107502_tc_08')
    def test_08_n_fnl_sg_online_on_non_faulted_node_as_priority(self):
        """
        @tms_id: torf_107502_tc08
        @tms_requirements_id: TORF-107502
        @tms_title: Faulted SG fixed with fnl feature across multiple SGs
        @tms_description:
        Test to verify that if an applied failover SG is FAULTED on one of its
        nodes in the cluster, and a plan is created, the opposite node
        (standby-node) that is ONLINE will be locked first and will be the node
        that the SG is brought ONLINE with at end of plan.
        @tms_test_steps:
            @step: Create a failover SG that has a node list n1,n2
            @result: Failover SG is defined in litp model
            @step: Create/ Run plan
            @result: Ensure plan runs to completion
            @result: Ensure SG comes ONLINE
            @step: Remove PID from n1, causing the SG to go FAULTED on n1
            @result: Wait for SG to become FAULTED on n1
            @result: Wait for SG to come ONLINE on n2
            @result: Plan should fail
            @step: Update cluster by adding a sinlge node Parallel SG on the
            FAULTED node (n1)
            @result: One node parallel SG is defined in litp model
            @step: Create/ Run plan again
            @result: Plan is created and run to completion
            @result: Lock task should pass
            @result: Unlock task should pass
            @result: Ensure Parallel SG comes ONLINE on n1
            @result: Ensure failover SG comes back ONLINE on n2 due to being
            unlocked first
        @tms_test_precondition: 2 Node cluster installed with litp
        @tms_execution_type: Automated
        """

        timeout_mins = 90
        self.log('info', 'Beginning Test Case 08')

        # Pre-condition for TC1
        self.log('info', 'Pre-Step 1: Create a failover SG that has a node '
                         'list n1,n2 ')

        fixtures = self.baseline(vcs_len=1,
                                 app_len=1,
                                 hsc_len=1,
                                 valid_rpm=1,
                                 cleanup=True)

        fixtures_2 = self.baseline(vcs_len=1,
                                   app_len=1,
                                   hsc_len=1,
                                   cleanup=False,
                                   story=STORY + 'stable_PL'
                                   )
        cs_1_name = fixtures['service'][0]['parent']
        cs_2_name = fixtures_2['service'][0]['parent']

        self._setup_pre_condition_for_tcs(fixtures)
        # Create/ Run plan until failure occurs
        self.log('info', 'Pre-Step 2: Create/ Run plan')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 3: Wait for plan to finish')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

        self.assertTrue(self.is_text_in_list('ONLINE',
                                             self._assert_sg_in_stable_state(
                                                 cs_1_name, 'node1')))
        # Remove SG PID from N1
        self.log('info', 'Pre-Step 3: Remove SG PID from N1')
        self._stop_lsb_service(cs_1_name, node=self.node_exe[0])
        # Ensure SG goes OFFLINE/FAULTED on N1
        cs_grp_name = self.vcs.generate_clustered_service_name(cs_1_name,
                                                               self.cluster_id)
        hastatus_state = self.vcs.get_hagrp_value_cmd(cs_grp_name, "State")

        self.assertTrue(
            self.wait_for_cmd(self.node_exe[0], hastatus_state,
                              expected_rc=0,
                              expected_stdout=FAULTED_STATE,
                              timeout_mins=5, su_root=True),
            'Service {0} is not in OFFLINE/FAULTED state'.format(cs_1_name))

        # Ensure SG goes ONLINE on N2
        self.log('info', 'Waiting for FO SG to come ONLINE on N2')
        self.assertTrue(
            self.wait_for_cmd(self.node_exe[1], hastatus_state,
                              expected_rc=0,
                              expected_stdout=ONLINE_STATE,
                              timeout_mins=5, su_root=True),
            'Service {0} is not in an ONLINE state'.format(cs_1_name))
        # Create and run plan
        self.log("info", "Finished pre-conditions for test")
        self.log("info", "Beginning Steps for test")
        self.log("info", "Step 1: Update cluster with single node PL SG on "
                         "faulted node 'Node1'")
        # Create a 1 node PL service group on node1
        self._setup_sgs_pre_condition_for_tc8(fixtures_2,
                                              story=STORY + 'stable_PL')
        # Create/ Run plan until plan completes occurs
        self.log('info', 'Step 2: Create/ Run plan')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)
        self.log('info', 'Step 3: Wait for plan to finish, Expect Success')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))
        # Ensure SG goes ONLINE on N1
        self.log('info', 'Waiting for PL SG to come ONLINE on N1')
        self.assertTrue(self.is_text_in_list('ONLINE',
                                             self._assert_sg_in_stable_state(
                                                 cs_2_name, 'node1')))
        # Ensure SG goes ONLINE on N2
        self.log('info', 'Waiting for FO SG to come back ONLINE on N2')
        self.assertTrue(self.is_text_in_list('ONLINE',
                                             self._assert_sg_in_stable_state(
                                                 cs_1_name, 'node2')))
        self.log('info', 'Finished Tc_08')

    @attr('all', 'expansion', 'story107502', 'story107502_tc09')
    def test_09_n_fnl_with_serv_expansion_contraction_and_migration(self):
        """
        @tms_id: torf_107502_tc09
        @tms_requirements_id: TORF-107502
        @tms_title: Faulted SGs can be fixed during
        expansion/contraction/migration and FO to PL
        @tms_description:
        test_09_n_fnl_with_serv_expansion_contraction_and_migration:
        If a user has multiple SGs that are FAULTED on a node and wishes to
        update said SGs, by either expanding/contracting/migrating the SGs to
        other nodes in the cluster
        test_10_n_fnl_with_full_serv_migration:
        Test to verify that if an applied (2 node) parallel SG is FAULTED on
        both of its nodes in the cluster, as a user we can fully migrate the
        nodes that are FAULTED on the SG in the cluster if desired
        (i.e. n1,n2 -> n2,n4) by using the fnl feature
        test_14_n_fnl_failover_sg_faulted_to_parallel:
        Test to verify that if an applied failover type SG goes faulted on
        both of its nodes and a user wishes to update the failover SG to be a
        2 node parallel SG litp they may do so using the fnl feature
        @tms_test_steps:
            @step: Create 3 SGs in litp (2 PL (n1,n2), 1 FO (n1,n2)) with
            stable RPM packages
            @result: 3 Sgs are now defined in litp model
            @step: Create/ Run plan to completion
            @result: Plan is run to completion and SGs are all ONLINE
            @step: Remove PID files for all SGs installed on Node1
            @result: PID file is removed from /tmp directory on node 1
            @step: Ensure All Sgs become OFFLINE| FAULTED on node 1
            @result: All Sgs become Faulted on node1
            @step: Remove PID file from node 2 for PL SG2
            @result: PID file is removed from node 2
            @step: Ensure SG2 becomes OFFLINE|FAULTED on node 2
            @result: SG2 becomes OFFLINE|FAULTED
            @step: Update SG1 node list (n1,n2)-> (n2,n3)
            @result: Node list for PL SG1 is now being expanded/contracted
            @step: Update SG2 node list for migration (n1,n2) -> (n3,n4)
            @result: Node list for PL SG2 is migrating to new node list
            @step: Update SG3 for FO to PL (active=1,standy=1 -> active=2,
            standby=0)
            @result: SG3 is being updated from FO to PL
            @step: Create/ Run plan again
            @result: Ensure plan runs to completion
            @step: Ensure all SGs are now ONLINE state
            @result: SGs are now ONLINE
        @tms_test_precondition: 4 Node cluster installed with litp
        @tms_execution_type: Automated
        """
        timeout_mins = 90
        self._is_model_expanded()

        self.log('info', 'Step 1: Create 3 SGs in litp 2 PL and 1 FO')
        fixtures = self.baseline(vcs_len=3, app_len=3, hsc_len=3)

        self._setup_sgs_pre_condition_for_tc9(fixtures)

        self.log('info', 'Step 2: Create/ Run plan to completion')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 3: Wait for plan to finish')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

        cs_pl_1_name = fixtures['service'][0]['parent']
        cs_pl_2_name = fixtures['service'][1]['parent']
        cs_fo_3_name = fixtures['service'][2]['parent']

        self.log('info', 'Step 4 Remove PID file from node 1 for all SGs')
        for sg_name in [cs_pl_1_name, cs_pl_2_name, cs_fo_3_name]:
            self._stop_lsb_service(sg_name, 'node1')
            cs_grp_name = \
                self.vcs.generate_clustered_service_name(sg_name,
                                                         self.cluster_id)
            hastatus_state = self.vcs.get_hagrp_value_cmd(cs_grp_name, "State")

            self.log('info', 'Step 5: Ensure all Node 1 SGs become FAULTED')
            self.assertTrue(
                self.wait_for_cmd(self.node_exe[0], hastatus_state,
                                  expected_rc=0,
                                  expected_stdout=FAULTED_STATE,
                                  timeout_mins=5, su_root=True),
                'Service {0} is not FAULTED'.format(sg_name))

        self.log('info', 'Step 4 Remove PID file from node 2 for PL SG2')
        self._stop_lsb_service(cs_pl_2_name, 'node2')

        cs_grp_name = \
            self.vcs.generate_clustered_service_name(cs_pl_2_name,
                                                     self.cluster_id)
        hastatus_state = self.vcs.get_hagrp_value_cmd(cs_grp_name, "State")

        self.log('info', 'Step 5: Ensure all Node 1 SGs become FAULTED')
        self.assertTrue(
            self.wait_for_cmd(self.node_exe[1], hastatus_state,
                              expected_rc=0,
                              expected_stdout=FAULTED_STATE,
                              timeout_mins=5, su_root=True),
            'Service {0} is not FAULTED'.format(cs_pl_2_name))

        self.log('info', 'Step 6: Update SG1 to have node list n2,n3')
        self.execute_cli_update_cmd(self.management_server,
                                    fixtures['vcs-clustered-service'][0]
                                    ['vpath'], props='node_list="n2,n3"')

        self.log('info', 'Step 7: Update SG2 to have node list n3,n4')
        self.execute_cli_update_cmd(self.management_server,
                                    fixtures['vcs-clustered-service'][1]
                                    ['vpath'], props='node_list="n3,n4"')

        self.log('info', 'Step 8: Update SG3 to be parallel on nodes 1 and 2')
        self.execute_cli_update_cmd(self.management_server,
                                    fixtures['vcs-clustered-service'][2]
                                    ['vpath'], props='active=2 standby=0 '
                                                     'node_list="n1,n2"')

        self.log('info', 'Step 9: Create/ Run plan to completion')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 10: Wait for plan to finish')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

        self.log('info', 'Step 11: Ensure all SGs are now ONLINE')
        for sg_name, node in zip([cs_pl_1_name, cs_pl_2_name, cs_fo_3_name],
                                 ['node3', 'node3', 'node1']):
            self.assertEqual('ONLINE',
                             self._assert_sg_in_stable_state(sg_name, node)[0])

    @attr('all', 'revert', 'story107502', 'story107502_tc13')
    def test_13_p_fnl_initial_online_dependency(self):
        """
        @tms_id: torf_107502_tc13
        @tms_requirements_id: TORF-107502
        @tms_title: Faulted SG with initial_online_dependencies fixed
        with fnl feature
        @tms_description:
        Test to verify that the fnl feature can be used to ONLINE sgs that
        have initial_online_dependencies defined between them provided they may
        get into a FAULTED state and requires to be fixed
        @tms_test_steps:
            @step: Create 2 parallel SGs with initial_online_dependencies
            between each.
            One SG should have bad RPM
            @result: 2 parallel SGs are defined in the model
            with initial_online_dependency
            @step: Create/Run plan
            @result: Plan failed. SG with bad RPM is in FAULTED state.
            SG depending on the one above are not brought online
            @step: Update package in FAULTED SG to good one
            @result: Package is updated
            @step: Create/run plan
            @result: SG1 becomes ONLINE, as well as SG2
            Plan passed
        @tms_test_precondition: None
        @tms_execution_type: Automated
        """
        timeout_mins = 90
        self.log('info', 'Beginning Test Case 1')

        self.log('info',
                 'Step 1: Creating the two PL SGs: SG1 has bad RPM,'
                 ' SG2 has initial online dependency on SG1')
        # Creation of SG1 with bad RPM
        faulted_pl_fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1,
                                            valid_rpm=3, story=STORY +
                                                               'PL_Faulted',
                                            cleanup=True)
        cs_pl_1_name = faulted_pl_fixtures['service'][0]['parent']
        self._setup_pre_condition_for_tcs(faulted_pl_fixtures, active='2',
                                          standby='0', critical_flag=False)

        # Creation of SG2 depending on SG1 with good RPM
        stable_pl_fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1,
                                           story=STORY + 'PL_Stable',
                                           cleanup=True)
        cs_pl_2_name = stable_pl_fixtures['service'][0]['parent']

        self. \
            _setup_pre_condition_for_tc13(stable_pl_fixtures,
                                          active='2',
                                          standby='0',
                                          initial_dependency_list=cs_pl_1_name
                                          )

        self.log('info', 'Step 2: Create/Run plan')

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info',
                 'Step 3: Wait for plan to fail because SG1 has bad package')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_FAILED, timeout_mins))

        # Checking the SG status on both nodes using hagrp command
        # Should be OFFLINE|FAULTED
        for node in [self.node_exe[0], self.node_exe[1]]:
            cs_grp_name = \
                self.vcs.generate_clustered_service_name(cs_pl_1_name,
                                                         self.cluster_id)
            hastatus_state = self.vcs.get_hagrp_value_cmd(cs_grp_name, "State")

            self.log('info', 'Step 4: Ensure SG1 became FAULTED on {0}'
                     .format(node))

            self.assertTrue(
                self.wait_for_cmd(node, hastatus_state,
                                  expected_rc=0,
                                  expected_stdout=FAULTED_STATE,
                                  timeout_mins=5, su_root=True),
                'Service {0} is not FAULTED'.format(cs_pl_1_name))

        # Checking that SG2 was not brought online -
        # Should not be in the list of CSs
        cs_grp_name_2 = \
            self.vcs.generate_clustered_service_name(cs_pl_2_name,
                                                     self.cluster_id)
        hastatus_state_2 = self.vcs.get_hagrp_cmd("-list")

        self.log('info', 'Step 5: Ensure SG2 is not in CS list')
        vcs_grp_out = self.run_command(self.node_exe[0], hastatus_state_2,
                                       su_root=True,
                                       default_asserts=True)[0]

        self.assertFalse(self.is_text_in_list(cs_grp_name_2, vcs_grp_out))

        self.log('info', 'Step 6: Fix the bad RPM on Faulted SG')
        self._update_faulted_rpm_on_sg(number=1, story=STORY + 'PL_Faulted')

        self.log('info', 'Step 7: Create/Run plan again')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        for node in [self.node_exe[0], self.node_exe[1]]:
            self.log('info', 'Step 8.1: Lock Task on {0} pass in plan'
                     .format(node))

            self.assertTrue(self.wait_for_task_state(self.management_server,
                                                     LOCK_TASK.format(node),
                                                     PLAN_TASKS_SUCCESS,
                                                     ignore_variables=False))

            self.log('info', 'Step 8.2: Unlock Task on {0} pass in plan'
                     .format(node))
            self.assertTrue(self.wait_for_task_state(self.management_server,
                                                     UNLOCK_TASK.format(node),
                                                     PLAN_TASKS_SUCCESS,
                                                     ignore_variables=False))

        self.log('info', 'Step 9: Wait for plan to complete successfully')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

    @attr('all', 'revert', 'story107502', 'story107502_tc15')
    def test_15_n_fnl_with_applied_sgs_with_deps_fault(self):
        """
            @tms_id: torf_107502_tc15
            @tms_requirements_id: TORF-107502
            @tms_title: Test to verify parent faulted services doesn't allow to
            bring ONLINE other services but it's possible to perform an upgrade
            to solve the problem
            @tms_description: Test to verify that the fnl property can be used
            to online sgs that (applied state) have dependencies between them
            provided when they may get into a FAULTED state and require to be
            fixed can be using the fnl feature
            @tms_test_steps:
                @step: Create 3 SGs in litp (3 PL one faulted and two stable
                depending on the faulted one)
                @result: 3 Sgs are now defined in litp model
                @step: Update cs_initial_online to off
                @result: cs_initial_online=off
                @step: Create and run plan
                @result: Plan will succeed
                @step: Attemp to ONLINE the SGs
                @result: The parent services will fail avoiding all the SGs to
                come online
                @step: Upgrade faulted RPM
                @result: Faulted SG now is fixed
                @step: Create and run a plan
                @result: Plan will succeed
                @step: Try to bring SGs online
                @result: SGs will come online
            @tms_test_precondition: 2 Node cluster installed with litp
            @tms_execution_type: Automated
        """
        timeout = 90
        services = []

        # Create clustered service 1 (Faulted)
        self.log("info", "Step 1: Create clustered services")
        fault_pl_name = STORY + '_PL_fault_1'
        fault_pl_fixtures = self.create_service(fault_pl_name, 3, 2, 0,
                                                'n1,n2')

        self.apply_cs_and_apps_sg(self.management_server, fault_pl_fixtures,
                                  self.rpm_src_dir)

        services.append(fault_pl_fixtures['service'][0]['parent'])

        # Create clustered service 2
        stable_pl_name = STORY + '_PL_stable_1'
        stable_pl_fixtures = self.create_service(stable_pl_name, 1, 2, 0,
                                                 'n1,n2')

        apply_options_changes(stable_pl_fixtures, 'vcs-clustered-service', 0, {
            'dependency_list': 'CS_{0}_1'.format(fault_pl_name)
        })

        self.apply_cs_and_apps_sg(self.management_server, stable_pl_fixtures,
                                  self.rpm_src_dir)

        services.append(stable_pl_fixtures['service'][0]['parent'])

        # Create clustered service 3
        stable_pl_name = STORY + '_PL_stable_2'
        stable_pl_fixtures = self.create_service(stable_pl_name, 1, 2, 0,
                                                 'n1,n2')

        apply_options_changes(stable_pl_fixtures, 'vcs-clustered-service', 0, {
            'dependency_list': 'CS_{0}_1'.format(fault_pl_name)
        })

        self.apply_cs_and_apps_sg(self.management_server, stable_pl_fixtures,
                                  self.rpm_src_dir)

        services.append(stable_pl_fixtures['service'][0]['parent'])

        # Set cs_initial_online to off
        self.log("info", "Step 2: Set cs_initial_online to off")
        self._update_vcs_cluster('off')

        # Create and run the plan
        self.log("info", "Step 3: Create and run plan")
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout))

        # Attemp to ONLINE clustered service
        self.log("info",
                 "Step 4: Attemp to manually online the clustered services")
        for service in services:
            self._manually_attempt_bring_sg_online(service, "node1")
            self._manually_attempt_bring_sg_online(service, "node2")

        # Ensure CS with faulted RPM is in a FAULTED state
        self.log("info", "Step 5: Check faulted clustered"
                         "services are effectively faulted")
        hagrp_cmd = self.vcs.get_hagrp_value_cmd(
            self.vcs.generate_clustered_service_name(services[0],
                                                     self.cluster_id),
            "State")

        self.assertTrue(self.wait_for_cmd(self.node_exe[0], hagrp_cmd,
                                          expected_rc=0,
                                          expected_stdout=FAULTED_STATE,
                                          timeout_mins=5, su_root=True))
        self.assertTrue(self.wait_for_cmd(self.node_exe[1], hagrp_cmd,
                                          expected_rc=0,
                                          expected_stdout=FAULTED_STATE,
                                          timeout_mins=5, su_root=True))

        # Ensure other CS that depends on the faulted CS are OFFLINE
        self.log("info", "Step 6: Ensure dependent clustered services are"
                         "offline")
        hagrp_cmds = [
            self.vcs.get_hagrp_value_cmd(
                self.vcs.generate_clustered_service_name(services[1],
                                                         self.cluster_id),
                "State"),
            self.vcs.get_hagrp_value_cmd(
                self.vcs.generate_clustered_service_name(services[2],
                                                         self.cluster_id),
                "State")
        ]

        for hagrp_cmd in hagrp_cmds:
            self.assertTrue(self.wait_for_cmd(self.node_exe[0], hagrp_cmd,
                                              expected_rc=0,
                                              expected_stdout=OFFLINE_STATE,
                                              timeout_mins=5, su_root=True))

            self.assertTrue(self.wait_for_cmd(self.node_exe[1], hagrp_cmd,
                                              expected_rc=0,
                                              expected_stdout=OFFLINE_STATE,
                                              timeout_mins=5, su_root=True))

        # Update faulted clustered service
        self.log("info", "Step 7: Fix the faulted clustered service")
        self._update_faulted_rpm_on_sg(story=STORY + '_PL_fault_1')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout))

        # Bring online all the clustered services
        self.log("info", "Step 8: Bring online all the clustered services")
        for service in services:
            self._manually_attempt_bring_sg_online(service, "node1")
            self._manually_attempt_bring_sg_online(service, "node2")

        # Ensure CS with fixed RPM is now ONLINE
        self.log("info", "Step 9: Check clustered services all effectively"
                         "online")
        hagrp_cmd = self.vcs.get_hagrp_value_cmd(
            self.vcs.generate_clustered_service_name(services[0],
                                                     self.cluster_id),
            "State")

        self.assertTrue(self.wait_for_cmd(self.node_exe[0], hagrp_cmd,
                                          expected_rc=0,
                                          expected_stdout=ONLINE_STATE,
                                          timeout_mins=5, su_root=True))
        self.assertTrue(self.wait_for_cmd(self.node_exe[1], hagrp_cmd,
                                          expected_rc=0,
                                          expected_stdout=ONLINE_STATE,
                                          timeout_mins=5, su_root=True))

        # Ensure other CS that depends on the fixed CS are now ONLINE
        hagrp_cmds = [
            self.vcs.get_hagrp_value_cmd(
                self.vcs.generate_clustered_service_name(services[1],
                                                         self.cluster_id),
                "State"),
            self.vcs.get_hagrp_value_cmd(
                self.vcs.generate_clustered_service_name(services[2],
                                                         self.cluster_id),
                "State")
        ]

        for hagrp_cmd in hagrp_cmds:
            self.assertTrue(self.wait_for_cmd(self.node_exe[0], hagrp_cmd,
                                              expected_rc=0,
                                              expected_stdout=ONLINE_STATE,
                                              timeout_mins=5,
                                              su_root=True))

            self.assertTrue(self.wait_for_cmd(self.node_exe[1], hagrp_cmd,
                                              expected_rc=0,
                                              expected_stdout=ONLINE_STATE,
                                              timeout_mins=5,
                                              su_root=True))

        self._update_vcs_cluster()

    @attr('all', 'revert', 'story107502', 'story107502_tc19')
    def test_19_n_plan_proceeds_fnl_with_fault_rpm_on_serv(self):
        """
        @tms_id: torf_107502_tc19
        @tms_requirements_id: TORF-107502
        @tms_title: Initial Faulted SG can be fixed with fnl feature
        @tms_description:
        test_19_p_plan_proceeds_fnl_with_fault_rpm_on_serv:
        Test to verify if a plan fails to bring a SG online a user can update
        a bad RPM package and re-create the plan in attempt to successfully
        bring the SG ONLINE
        test_12_n_fnl_with_initial_sgs_with_deps_fault:
        Test to verify is a user defines multiple SGs in litp with vcs
        dependencies between the onlining of the SGs, and one of the SGs
        becomes FAULTED the onlining task should fail and the other SGs
        should be prevented from coming ONLINE regarless of fnl feature
        @tms_test_steps:
            @step: Create 3 PL SGs in litp model with dependencies on SG2
            (2 with Bad RPMs, 1 with stable)
            @result: 3 PL SGs are defined in the litp model
            @step: Create/ Run plan
            @result: Wait for litp plan to fail
            @step: Assert SG1 is in a FAULTED state
            @result: SG1 is FAULTED
            @step: Ensure all SGs are in initial state in litp
            @result: All SGs are in initial state
            @step: Update bad RPM packages on SG1 and SG2
            @result: Packages are imported and updated in litp
            @step: Create/ Run again
            @result: Ensure plan runs to completion
            @step: Ensure all SGs come ONLINE in correct order based on
            dependency list
            @result: All Sgs are ONLINE
            @step: Ensure all SGs are ONLINE
            @result: All Sgs are now ONLINE.
        @tms_test_precondition: None
        @tms_execution_type: Automated
        """
        timeout_mins = 90
        self.log('info', 'Step 1: Create 2 PL SGs with faulted packages')
        faul_pl_fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2,
                                         valid_rpm=3, cleanup=True,
                                         story=STORY + 'PL_Faul_tc19')

        stable_pl_fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1,
                                           cleanup=True,
                                           story=STORY + 'PL_Stab_tc19')

        self._setup_sgs_pre_condition_for_tc19(faul_pl_fixtures,
                                               stable_pl_fixtures,
                                               story_faul=STORY +
                                                          'PL_Faul_tc19',
                                               story_stable=STORY +
                                                            'PL_Stab_tc19')

        pl_sg1 = faul_pl_fixtures['vcs-clustered-service'][0]['id']
        pl_sg2 = faul_pl_fixtures['vcs-clustered-service'][1]['id']
        pl_sg3 = stable_pl_fixtures['vcs-clustered-service'][0]['id']

        self.log('info', 'Step 2: Create/ Run')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 3: Wait for plan to fail')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_FAILED, timeout_mins))

        self.log('info', 'Step 4: Assert SG1 is in a FAULTED state')
        cs_grp_name = self.vcs.generate_clustered_service_name(pl_sg2,
                                                               self.cluster_id)
        hastatus_state = self.vcs.get_hagrp_value_cmd(cs_grp_name, "State")
        self.assertTrue(self.wait_for_cmd(self.node_exe[0], hastatus_state,
                                          expected_rc=0,
                                          expected_stdout=FAULTED_STATE,
                                          timeout_mins=5, su_root=True,
                                          default_time=10),
                        'Service {0} is not in proper state'.format(pl_sg2))

        self.log('info', 'Step 5: Update and import good packages in attempt '
                         'to ONLINE FAULTED SG')
        # Loop through the faulted SGs and update the package version for
        # under /software/items
        for num in xrange(1, 3):
            self._update_faulted_rpm_on_sg(story=STORY + 'PL_Faul_tc19',
                                           number=num)

        self.log('info', 'Step 6: Create/ Run again')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 7: Wait for plan to finish')
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

        self.log('info', 'Step 8: Ensure SG is ONLINE')
        for sg_name in [pl_sg1, pl_sg2, pl_sg3]:
            self.assertEqual('ONLINE',
                             self._assert_sg_in_stable_state(sg_name,
                                                             'node1')[0],
                             'SG {0} did not come ONLINE'.format(sg_name))

    @attr('all', 'revert', 'story107502', 'story107502_tc25')
    def test_25_n_plan_proceeds_fnl_with_offline_rpm_upd_serv(self):
        """
        @tms_id: torf_107502_tc25
        @tms_requirements_id: TORF-107502
        @tms_title: Test to update service with a bad RPM to a working RPM
        @tms_description:
        Test to verify if a plan fails to bring a SG online a user can update
        a bad RPM package and re-create the plan in attempt to successfully
        bring the SG ONLINE
        @tms_test_steps:
            @step: Create 2 SGs in litp (2 PL one on n1 and one on n2) with
            stable RPM and faulted rpm packages
            @result: 2 Sgs are now defined in litp model
            @step: Create and run plan
            @result: Plan will fail
            @step: Assert SG1 is now faulted
            @result: SG1 is faulted
            @step: Manually offline the SGs
            @result: SGs are now offline
            @step: Ensure SGs are in initial state in the model
            @result: SGs are in initial state in the model
            @step: Upgrade faulted SG
            @result: Now the faulted SG is fixed
            @step: Create and run plan
            @result: Plan will succeed
        @tms_test_precondition: 2 Node cluster installed with litp
        @tms_execution_type: Automated
        """
        timeout = 90
        services = []

        # Create a one node faulted clustered service on node1
        self.log("info", "Step 1: Create clustered services")
        fault_pl_name = STORY + '_PL_fault_1'
        fault_pl_fixtures = self.create_service(fault_pl_name, 3, 1, 0,
                                                'n1')

        self.apply_cs_and_apps_sg(self.management_server, fault_pl_fixtures,
                                  self.rpm_src_dir)

        services.append(fault_pl_fixtures['service'][0]['parent'])

        # Create a one node clustered service on node2
        stable_pl_name = STORY + '_PL_stable_1'
        stable_pl_fixtures = self.create_service(stable_pl_name, 1, 1, 0,
                                                 'n2')

        self.apply_cs_and_apps_sg(self.management_server, stable_pl_fixtures,
                                  self.rpm_src_dir)

        services.append(stable_pl_fixtures['service'][0]['parent'])

        # Create and run the plan
        self.log("info", "Step 2: Create and run the plan")
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_FAILED, timeout))

        # Ensure CS with faulted RPM is in a FAULTED state
        self.log("info", "Step 3: Ensure clustered services are faulted")
        hagrp_cmd = self.vcs.get_hagrp_value_cmd(
            self.vcs.generate_clustered_service_name(services[0],
                                                     self.cluster_id),
            "State")

        self.assertTrue(self.wait_for_cmd(self.node_exe[0], hagrp_cmd,
                                          expected_rc=0,
                                          expected_stdout=FAULTED_STATE,
                                          timeout_mins=5, su_root=True))

        # Manually clear the faulted clustered service
        self.log("info", "Step 4: Clear status of faulted clustered service on"
                         "node1")
        self._clear_faults_on_sgs_on_nodes(services[0], "node1")

        # Ensure clustered services are in an initial state in the litp model
        self.log("info", "Step 5: Ensure clustered service is still in an"
                         "initial state in LITP model")
        vcs_sg_name = self.vcs_cluster_url + "/services/CS_{0}_1".format(
            fault_pl_name)

        self.assertTrue(
            match("^Initial.*$", self.get_item_state(self.management_server,
                                                     vcs_sg_name),
                  insensitive))

        vcs_sg_name = self.vcs_cluster_url + "/services/CS_{0}_1".format(
            stable_pl_name)
        self.assertTrue(
            match("^Initial.*$", self.get_item_state(self.management_server,
                                                     vcs_sg_name),
                  insensitive))

        # Upgrade faulted RPM
        self.log("info", "Step 6: Fix the faulted clustered service")
        self._update_faulted_rpm_on_sg(story=fault_pl_name)

        # Create and run the plan
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout))

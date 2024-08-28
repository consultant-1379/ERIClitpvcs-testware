"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     September 2016
@author:    Ciaran Reilly
@summary:   Integration Tests
            Agile: STORY-128825
"""
import os
from vcs_utils import VCSUtils
from test_constants import PLAN_COMPLETE, PLAN_TASKS_SUCCESS, \
    VCS_MAIN_CF_FILENAME
from litp_generic_test import GenericTest, attr
from redhat_cmd_utils import RHCmdUtils
from generate import load_fixtures, generate_json, apply_options_changes, \
    apply_item_changes
from networking_utils import NetworkingUtils

STORY = '128825'
LOC_DIR = os.path.dirname(os.path.realpath(__file__))
DUMMY_FILE = 'dummy_file.txt'
PID_ID = ''


class Story128825(GenericTest):
    """
    TORF-128825:
        Description:
            As a LITP User I want to migrate my service to a new VCS
            Clustered service on a new node_list so i can minimise service
            distruption
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
        super(Story128825, self).setUp()

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

        self.net_utils = NetworkingUtils()
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
        super(Story128825, self).tearDown()

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
                              valid_rpm=valid_rpm,
                              add_to_cleanup=cleanup)

        return load_fixtures(story, self.vcs_cluster_url,
                             self.nodes_urls, input_data=_json)

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

    def _create_snapshot(self):
        """
        Method that will remove any pre-existing snapshot and create a new one
        based on plugin updates for KGB suite
        :return: Nothing
        """

        self.execute_and_wait_createsnapshot(self.management_server,
                                             add_to_cleanup=False,
                                             remove_snapshot=True)

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

    def _check_disk_based_fencing(self):
        """
        This Method will verify the disk based fencing configuration on a
        physical deployment.
        :return: Nothing
        """
        gabconfig_cmd = 'gabconfig -a'
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

    def _put_dummy_file_on_active_node(self, cs_url, cs_name):
        """
        Method that will copy a file to the mount point used by a CS in its
        mount point
        :param cs_url: (str) CS URL that is has a file system configured
        :return: mnt_point: (str) mount point of file system
        """
        cs_grp_name = self.vcs.generate_clustered_service_name(cs_name,
                                                               self.cluster_id)
        fs_url = self.find(self.management_server, cs_url,
                           'reference-to-file-system', find_refs=True)

        mnt_point = self.get_props_from_url(self.management_server, fs_url[0],
                                            filter_prop='mount_point')

        active_node, _ = self._check_active_node(cs_grp_name)

        self.assertTrue(self.copy_file_to(active_node, LOC_DIR + '/' +
                                          DUMMY_FILE, mnt_point,
                                          root_copy=True,
                                          add_to_cleanup=False))
        return mnt_point

    def _check_deactivated_sg_in_vcs(self, cs_name):
        """
        Method to verify that a service group that is deactivated is fully
        removed from the VCS engine
        :param cs_name: (str) VCS clustered service name
        :return: (bool) True/False
        """
        cs_grp_name = self.vcs.generate_clustered_service_name(cs_name,
                                                               self.cluster_id)
        hagrps_cmd = self.vcs.get_hagrp_cmd('-list')
        vcs_list = self.run_command(self.node_exe[0], hagrps_cmd, su_root=True,
                                    default_asserts=True)[0]

        return self.is_text_in_list(cs_grp_name, vcs_list) \
               and not cs_grp_name + '0'

    def _add_firewall(self):
        """
        Method that creates the firewall configurations for HTTP service
        between the MS and MNs
        :return: nothing
        """

        ms_firewall_url = self.find(self.management_server, '/ms',
                                    'collection-of-firewall-rule')
        node_firewall_urls = []
        for node_url in self.nodes_urls:
            node_firewall_urls.append(self.find(self.management_server,
                                                node_url,
                                                'collection-of-firewall-rule')
                                      [0])

        self.execute_cli_create_cmd(self.management_server,
                                    ms_firewall_url[0] + '/fw_test',
                                    'firewall-rule',
                                    props='name="128825 test" dport="8000" '
                                          'proto="tcp"',
                                    add_to_cleanup=True)
        for node_url in node_firewall_urls:
            self.execute_cli_create_cmd(self.management_server,
                                        node_url + '/fw_test',
                                        'firewall-rule',
                                        props='name="128825 test" '
                                              'dport="8000" proto="tcp"',
                                        add_to_cleanup=True)

    def _copy_and_run_http_bash_script_to_ms(self):
        """
        Method that will copy simple_http_server to the MS
        :return: (bool) If successfully copied over and run
        """
        http_file = 'simple_http_server.sh'

        self.assertTrue(self.copy_file_to(self.management_server,
                                          self.loc_dir + '/' + http_file,
                                          '/root', root_copy=True,
                                          add_to_cleanup=False))

        stdout, _, _ = self.run_command(self.management_server,
                                        cmd='sh /root/{0}'
                                        .format(http_file),
                                        su_root=True)
        self.assertEqual(stdout, [])

        cat_cmd = self.rh_cmds.get_cat_cmd('/tmp/PID')

        stdout = self.run_command(self.management_server, cmd=cat_cmd,
                                  su_root=True, default_asserts=True)

        global PID_ID

        PID_ID = stdout[0][0]

        self.assertNotEqual(PID_ID, '')

    def _read_timestamp_from_http_server(self, file_path, active_nodes):
        """
        Method to read the output from the HTTP server being hosted by MS1
        and compare the time stamps between two service groups
        :param: file_path: (str) Path to http server output
                active_nodes: (list) List of active nodes used for various
                clustered service groups
        :return: Nothing
        """
        http_list = self.get_file_contents(self.management_server, file_path,
                                           su_root=True)

        sg1_online_times = []
        sg2_online_times = []

        for line in http_list:
            if active_nodes[0] in line.split()[0]:
                sg1_online_times.append(line.split()[4].replace(']', ''))
            elif active_nodes[1] in line.split()[0]:
                sg2_online_times.append(line.split()[4].replace(']', ''))

        return sg1_online_times, sg2_online_times

    def _kill_pid(self):
        """
        Method that will kill the PID ID for the HTTP service
        :return: Nothing
        """
        stdout = self.run_command(self.management_server,
                                  cmd='/bin/kill {0}'.format(PID_ID),
                                  su_root=True, default_asserts=True)
        self.assertEqual(stdout[0], [])

    def _update_vcs_cluster(self, swtch='on'):
        """
        Description:
            Runs with PCDB test cases to update the cs_initial_online
            property to on
        Parameters:
            swtch: used to turn cs_initial_online on /off
        Actions:
            Updates the vcs-cluster item
        Returns: None
        """
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    'cs_initial_online={0}'.format(swtch))

    def _cleanup_cs_before_testware(self):
        """
        Method that will cleanup CS that have been deactivated by other CSs,
        making the testware cleanup pass new validations seen in TORF-152158
        :return: Nothing
        """
        timeout_mins = 20

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

    @attr('all', 'expansion', 'story128825', 'story128825_tc34')
    def test_34_p_deactivate_during_expansion(self):
        """
        @tms_id: torf_128825_tc34
        @tms_requirements_id: TORF-128825
        @tms_title: Deactivate during expansion
        @tms_description:
        Test to verify that deactivating a CS can be done during expansion
        of a cluster
        @tms_test_steps:
            @step: Create CS in model
            @result: CS is created in model
            @step: Create/ Run Plan
            @result: CS is applied in model
            @step: Expand cluster in model to be 4 nodes and create additional
            CS that will deactivate CS1
            @result: Model is expanded and CS2 is created that will deactivate
            CS1
            @step: Create/ Run Plan
            @result: Ensure no validation messages are returned and
            deacivated flag is set on CS1
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        timeout_mins = 90

        self.log('info', 'Creating snapshot of the updated system')
        self._create_snapshot()

        self.log('info', 'Step 1: Creating suitable Service groups for TC34')
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1, cleanup=True)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '1', 'standby': '0', 'name': 'CS_{0}_1'.format(STORY),
             'node_list': 'n1'}, overwrite=True)
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.log('info', 'Step 2: Create/ Run Plan for CS1')
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                add_to_cleanup=False)
        old_fixtures = fixtures

        self.log('info', 'Step 3: Expand model and create new CS2 that '
                         'deactivates CS1')
        self._is_model_expanded()

        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1,
                                 story=STORY + '_2', cleanup=True)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '1', 'standby': '0', 'name': 'CS_{0}_2'.format(STORY),
             'node_list': 'n4', 'deactivates': '{0}'.format(
                old_fixtures['service'][0]['parent'])}, overwrite=True)
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.log('info', 'Step 4: Create/ Run plan again')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.set_Passwords()

        self.log('info', 'Step 5: Ensuring deactivated flag is true')
        self.assertEqual(self.get_props_from_url(
            self.management_server, old_fixtures['vcs-clustered-service']
            [0]['vpath'], filter_prop='deactivated'), 'true',
            'Deactivated Flag Not Set')

        self.log('info', 'Check deactivated SG is removed from VCS engine')
        self.assertFalse(self._check_deactivated_sg_in_vcs(
            old_fixtures['service'][0]['parent']))

        # Cleanup prior to testware cleanup
        self._cleanup_cs_before_testware()

    @attr('all', 'expansion', 'story128825', 'story128825_tc19')
    def test_19_p_deactivate_cs_with_multiple_services_inherited(self):
        """
        @tms_id: torf_128825_tc19
        @tms_requirements_id: TORF-128825
        @tms_title: Deactivate CS with multiple services inherited
        @tms_description:
        Test to verify that deactivating a CS with multiple services inherited
        can be deactivated by another CS
        @tms_test_steps:
            @step: Create 1 FO CS with multiple services inherited
            @result: CS is created in model
            @step: Create/ Run Plan
            @result: CS is applied in model
            @step: Create additional identical CS to CS1 that will deactivate
            it
            @result: CS2 will be in initial state and deactivate CS1
            @step: Create/ Run Plan
            @result: Ensure no validation messages are returned and
            deactivated flag is set on CS1
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        timeout_mins = 30
        self._is_model_expanded()

        self.log('info', 'Step 1: Creating suitable Service groups for TC19')
        fixtures = self.baseline(vcs_len=1, app_len=3, hsc_len=3, cleanup=True)
        app_url = fixtures['vcs-clustered-service'][0]['vpath'] + \
                  '/applications/'
        ha_conf_url = fixtures['vcs-clustered-service'][0]['vpath'] + \
                      '/ha_configs/'
        apply_options_changes(fixtures, 'vcs-clustered-service', 0,
                              {'active': '1', 'standby': '1',
                               'name': 'CS_{0}_1'.format(STORY),
                               'node_list': 'n1,n2'},
                              overwrite=True)
        apply_item_changes(fixtures, 'ha-service-config', 0,
                           {'parent': "CS_{0}_1".format(STORY),
                            'vpath': ha_conf_url + 'APP_{0}_1'.format(STORY)})
        apply_options_changes(fixtures, 'ha-service-config', 0,
                              {'service_id': 'APP_{0}_1'.format(STORY)},
                              overwrite=True)
        apply_item_changes(fixtures, 'service', 1,
                           {'parent': "CS_{0}_1".format(STORY),
                            'destination': app_url + 'APP_{0}_2'
                           .format(STORY)})
        apply_item_changes(fixtures, 'ha-service-config', 1,
                           {'parent': "CS_{0}_1".format(STORY),
                            'vpath': ha_conf_url + 'APP_{0}_2'.format(STORY)})
        apply_options_changes(fixtures, 'ha-service-config', 1,
                              {'service_id': 'APP_{0}_2'.format(STORY)},
                              overwrite=True)
        apply_item_changes(fixtures, 'service', 2,
                           {'parent': "CS_{0}_1".format(STORY),
                            'destination': app_url + 'APP_{0}_3'
                           .format(STORY)})
        apply_item_changes(fixtures, 'ha-service-config', 2,
                           {'parent': "CS_{0}_1".format(STORY),
                            'vpath': ha_conf_url + 'APP_{0}_3'
                           .format(STORY)})
        apply_options_changes(fixtures, 'ha-service-config', 2,
                              {'service_id': 'APP_{0}_3'.format(STORY)},
                              overwrite=True)
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.log('info', 'Step 2: Create and Run plan')
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 60)

        old_fixtures = fixtures
        story = STORY + '_2'
        fixtures = self.baseline(vcs_len=1, app_len=3, hsc_len=3, story=story,
                                 cleanup=True)
        app_url = fixtures['vcs-clustered-service'][0]['vpath'] + \
                  '/applications/'
        ha_conf_url = fixtures['vcs-clustered-service'][0]['vpath'] + \
                      '/ha_configs/'
        apply_options_changes(fixtures, 'vcs-clustered-service', 0,
                              {'active': '1', 'standby': '1',
                               'name': 'CS_{0}'.format(story),
                               'node_list': 'n3,n4',
                               'deactivates': '{0}'.format(
                                   old_fixtures['service'][0]['parent'])},
                              overwrite=True)
        apply_item_changes(fixtures, 'ha-service-config', 0,
                           {'parent': "CS_{0}_1".format(story),
                            'vpath': ha_conf_url + 'APP_{0}_1'.format(story)})
        apply_options_changes(fixtures, 'ha-service-config', 0,
                              {'service_id': 'APP_{0}_1'.format(story)},
                              overwrite=True)
        apply_item_changes(fixtures, 'service', 1,
                           {'parent': "CS_{0}_1".format(story),
                            'destination': app_url + 'APP_{0}_2'
                           .format(story)})
        apply_item_changes(fixtures, 'ha-service-config', 1,
                           {'parent': "CS_{0}_1".format(story),
                            'vpath': ha_conf_url + 'APP_{0}_2'.format(story)})
        apply_options_changes(fixtures, 'ha-service-config', 1,
                              {'service_id': 'APP_{0}_2'.format(story)},
                              overwrite=True)
        apply_item_changes(fixtures, 'service', 2,
                           {'parent': "CS_{0}_1".format(story),
                            'destination': app_url + 'APP_{0}_3'
                           .format(story)})
        apply_item_changes(fixtures, 'ha-service-config', 2,
                           {'parent': "CS_{0}_1".format(story),
                            'vpath': ha_conf_url + 'APP_{0}_3'
                           .format(story)})
        apply_options_changes(fixtures, 'ha-service-config', 2,
                              {'service_id': 'APP_{0}_3'.format(story)},
                              overwrite=True)

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)
        self.log('info', 'Step 3: Create additional CS that will deactivate '
                         'CS1')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.assertEqual(self.get_props_from_url(
            self.management_server, old_fixtures['vcs-clustered-service']
            [0]['vpath'], filter_prop='deactivated'), 'true',
            'Deactivated Flag Not Set')

        self.log('info', 'Check deactivated SG is removed from VCS engine')
        self.assertFalse(self._check_deactivated_sg_in_vcs(
            old_fixtures['service'][0]['parent']))

        # Cleanup prior to testware cleanup
        self._cleanup_cs_before_testware()

    @attr('all', 'expansion', 'story128825', 'story128825_tc23')
    def test_23_p_deact_fo_and_pl_cs_with_vips_deps_and_during_apd(self):
        """
        @tms_id: torf_128825_tc23
        @tms_requirements_id: TORF-128825
        @tms_title: Deactivate FO and PL CS with VIPs and Dependencies
                    configured
        @tms_description:
        Test to verify that a user can deactivate both a FO type and PL type
        of CS that have VIPs and dependencies configured during APD checking
        @tms_test_steps:
            @step: Create 2 CS, one FO and one PL, that depend on one another
            and have VIPs configured
            @result: 2 SGs are created in model
            @step: Create/ Run Plan
            @result: 2 SGs are applied in model
            @step: Create additional FO CS_3 with same VIP addresses that
            will deactivate FO CS_1
            @result: CS3 is created in model with same VIPs
            @step: Update dependency on CS2
            @result: CS2 dependency is updated to point at CS3 now
            @step: Create/ Run Plan again
            @result: Plan is running
            @step: Stop plan during redeployment of new CS
            @result: plan is stopped during CS redeployment
            @step: Perform litpd restart
            @result: LITP deamon is restarted
            @step: Create/ Run Plan again
            @result: Plan is created and run to completion
            @step: Create additional PL CS_4 that deactivates PL CS_2
            @result: CS4 is created in model
            @step: Create/ Run Plan again
            @result: Plan is created and run
            @step: Stop plan during redeployment of new CS
            @result: plan is stopped during CS redeployment
            @step: Perform litpd restart
            @result: LITP deamon is restarted
            @step: Create/ Run Plan again
            @result: Plan is created and run to completion
        @tms_test_precondition: Expansion of Cluster should be done
        @tms_execution_type: Automated
        """
        task_desc = ['Deactivate VCS service group "Grp_CS_c1_CS_128825_1"',
                     'Deactivate VCS service group "Grp_CS_c1_CS_128825_2"']

        vip_props = {'network_name': 'traffic1',
                     'ipaddress': ['172.16.100.10', '172.16.100.12']}

        timeout_mins = 60
        self._is_model_expanded()

        self.log('info', 'Step 1: Creating suitable Service groups for TC23')
        fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2, vips_len=2,
                                 cleanup=True)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '1', 'standby': '1',
             'name': 'CS_{0}_1'.format(STORY), 'node_list': 'n1,n2',
             'dependency_list': 'CS_{0}_2'.format(STORY)},
            overwrite=True)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 1,
            {'active': '2', 'standby': '0',
             'name': 'CS_{0}_2_2'.format(STORY), 'node_list': 'n1,n2'},
            overwrite=True)
        apply_item_changes(
            fixtures, 'ha-service-config', 1,
            {'parent': "CS_{0}_2".format(STORY),
             'vpath':
                 self.vcs_cluster_url + '/services/CS_{0}_2/ha_configs/'
                                        'HSC_{1}_2'.format(STORY, STORY)})
        apply_item_changes(
            fixtures, 'service', 1,
            {'parent': "CS_{0}_2".format(STORY),
             'destination':
                 self.vcs_cluster_url + '/services/CS_{0}_2/applications'
                                        '/APP_{1}_2'.format(STORY, STORY)})
        apply_options_changes(
            fixtures, 'vip', 0, {
                'network_name': '{0}'.format(vip_props['network_name']),
                'ipaddress': '{0}'.format(vip_props['ipaddress'][0])},
            overwrite=True)
        apply_item_changes(
            fixtures, 'vip', 1, {
                'vpath': self.vcs_cluster_url +
                         '/services/CS_{0}_1/ipaddresses/VIP2'.format(STORY)})
        apply_options_changes(
            fixtures, 'vip', 1, {
                'network_name': '{0}'.format(vip_props['network_name']),
                'ipaddress': '{0}'.format(vip_props['ipaddress'][1])},
            overwrite=True)

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)
        self.log('info', 'Step 2: Create/ Run Plan for CS1 and CS2')
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 60,
                                add_to_cleanup=True)

        self.log('info', 'Step 3: Create CS3 that will deactivate CS1')
        old_fixtures = fixtures
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1, vips_len=2,
                                 story=STORY + '_3', cleanup=True)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '1', 'standby': '1',
             'name': 'CS_{0}'.format(STORY + '_3'), 'node_list': 'n4,n3',
             'dependency_list': 'CS_{0}_2'.format(STORY),
             'deactivates': '{0}'
                 .format(old_fixtures['service'][0]['parent'])},
            overwrite=True)
        apply_options_changes(
            fixtures, 'vip', 0, {
                'network_name': '{0}'.format(vip_props['network_name']),
                'ipaddress': '{0}'.format(vip_props['ipaddress'][0])},
            overwrite=True)
        apply_item_changes(
            fixtures, 'vip', 1, {
                'vpath': self.vcs_cluster_url +
                         '/services/CS_{0}/ipaddresses/VIP2'
                             .format(STORY + '_3_1')})
        apply_options_changes(
            fixtures, 'vip', 1, {
                'network_name': '{0}'.format(vip_props['network_name']),
                'ipaddress': '{0}'.format(vip_props['ipaddress'][1])},
            overwrite=True)

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.log('info', 'Step 4: Create / Run plan')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 5: Stop plan after deactivation')
        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 task_desc[0],
                                                 PLAN_TASKS_SUCCESS,
                                                 ignore_variables=False),
                        'CS_1 did not get deactivated')
        self.restart_litpd_service(self.management_server)

        self.log('info', 'Step 6: Create / Run plan again')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Check deactivated SG is removed from VCS engine')
        self.assertFalse(self._check_deactivated_sg_in_vcs(
            old_fixtures['service'][0]['parent']))

        old_fixtures_2 = fixtures
        self.log('info', 'Step 7: Create CS_4 that will deactivate CS_2')
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1,
                                 story=STORY + '_4', cleanup=True)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '2', 'standby': '0',
             'name': 'CS_{0}'.format(STORY + '_4'),
             'node_list': 'n4,n3', 'deactivates': '{0}'
                .format(old_fixtures['service'][1]['parent'])},
            overwrite=True)
        self.execute_cli_update_cmd(
            self.management_server, old_fixtures_2['vcs-clustered-service']
            [0]['vpath'], props='dependency_list={0}'
                .format(fixtures['service'][0]['parent']))

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Step 8: Stop plan after deactivation')
        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 task_desc[1],
                                                 PLAN_TASKS_SUCCESS,
                                                 ignore_variables=False),
                        'CS_2 did not get deactivated')
        self.restart_litpd_service(self.management_server)

        self.log('info', 'Step 9: Create / Run plan again')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Check deactivated SG is removed from VCS engine')
        self.assertFalse(self._check_deactivated_sg_in_vcs(
            old_fixtures['service'][1]['parent']))

    @attr('all', 'expansion', 'story128825', 'story128825_tc24')
    def test_24_p_restore_model_after_deactivate_a_cs_group(self):
        """
        @tms_id: torf_128825_tc24
        @tms_requirements_id: TORF-128825
        @tms_title: Restore model after CS deactivates
        @tms_description:
        Test to verify that if a CS is listed for removal after being
        deactivated that it does not get restored by a user after running a
        litp restore model
        @tms_test_steps:
            @step: Create suitable CS
            @result: Suitable ForRemoval CS is found in model
            @step: Update CS property (i.e. online/offline timeouts) that was
            set ForRemoval by deactivated property set to True
            @result: CS is now Updated
            @step: Run litp restore_model
            @result: Model is restored
            @step: Ensure CS is not restored in model and still in ForRemoval
            after create_plan ForRemoval state
            @result: CS will still be removed next create plan iteration
        @tms_test_precondition: Expansion of Cluster
        @tms_execution_type: Automated
        """
        timeout_mins = 20
        self.log('info', 'Step 1 : Create suitable CS in model')
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1, cleanup=True)
        apply_options_changes(fixtures, 'vcs-clustered-service', 0,
                              {'active': '1', 'standby': '1',
                               'name': 'CS_{0}_1'.format(STORY),
                               'node_list': 'n3,n4'},
                              overwrite=True)
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                add_to_cleanup=False)
        vcs_fo_sg = fixtures['vcs-clustered-service'][0]['vpath']
        fo_cs_name = fixtures['service'][0]['parent']

        self.log('info', 'Deactivating existing CS in model')
        story = STORY + '_2'
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1, story=story,
                                 cleanup=True)
        apply_options_changes(fixtures, 'vcs-clustered-service', 0,
                              {'active': '1', 'standby': '1',
                               'name': 'CS_{0}_1'.format(story),
                               'node_list': 'n1,n2',
                               'deactivates': '{0}'.format(fo_cs_name)},
                              overwrite=True)
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))
        self.log('info', 'Step 2: Update CS thats set ForRemoval after '
                         'deactivation')
        self.execute_cli_update_cmd(self.management_server, vcs_fo_sg,
                                    props='online_timeout=300')

        self.log('info', 'Step 3: Run litp restore model')
        self.execute_cli_restoremodel_cmd(self.management_server)

        vcs_fo_state = self.get_item_state(self.management_server, vcs_fo_sg)
        self.assertEqual(vcs_fo_state, 'Applied')

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)

        self.log('info', 'Step 4: Ensure CS is not restored in model and '
                         'still in ForRemoval after create_plan '
                         'ForRemoval state')
        vcs_fo_state = self.get_item_state(self.management_server, vcs_fo_sg)
        self.assertEqual(vcs_fo_state, 'ForRemoval')

        self.execute_cli_runplan_cmd(self.management_server)
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Check deactivated SG is removed from VCS engine')
        self.assertFalse(self._check_deactivated_sg_in_vcs(fo_cs_name))

    @attr('all', 'expansion', 'story128825', 'story128825_tc25')
    def test_25_p_deactivate_cs_with_triggers_present(self):
        """
        @tms_id: torf_128825_tc25
        @tms_requirements_id: TORF-128825
        @tms_title: Deactivate CS with triggers configured
        @tms_description:
        Test to verify that a CS with triggers can be deactivated
        @tms_test_steps:
            @step: Create 1 FO CS with triggers
            @result: CS with triggers is configured in model
            @step: Create/ Run plan
            @result: CS is now applied
            @step: Create additional CS that will deactivate CS1 with
            triggers configured
            @result: CS1 will be deactivated
            @step: Create/ Run plan
            @result: CS1 is set to ForRemoval and CS2 comes online
        @tms_test_precondition: Expansion of Cluster
        @tms_execution_type: Automated
        """
        timeout_mins = 20
        self.log('info', 'Step 1 : Create suitable CS in model')
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1, vcs_trig=1,
                                 cleanup=True)
        apply_options_changes(fixtures, 'vcs-clustered-service', 0,
                              {'active': '1', 'standby': '1',
                               'name': 'CS_{0}_1'.format(STORY),
                               'node_list': 'n3,n4'},
                              overwrite=True)
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.log('info', 'Step 2 : Create and run plan')
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                add_to_cleanup=False)
        vcs_fo_sg = fixtures['vcs-clustered-service'][0]['vpath']
        fo_cs_name = fixtures['service'][0]['parent']

        story = STORY + '_2'
        self.log('info', 'Creating suitable Service groups for TC25')
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1, vcs_trig=1,
                                 story=story, cleanup=True)
        apply_options_changes(fixtures, 'vcs-clustered-service', 0,
                              {'active': '1', 'standby': '1',
                               'name': 'CS_{0}_1'.format(story),
                               'node_list': 'n1,n2',
                               'deactivates': '{0}'.format(fo_cs_name)},
                              overwrite=True)
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)
        self.log('info', 'Step 4 : Create Run plan to completion')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.execute_cli_createplan_cmd(self.management_server)

        self.log('info', 'Step 5 : CS1 is set to ForRemoval')
        vcs_fo_state = self.get_item_state(self.management_server, vcs_fo_sg)
        self.assertEqual(vcs_fo_state, 'ForRemoval')
        self.execute_cli_runplan_cmd(self.management_server)
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Check deactivated SG is removed from VCS engine')
        self.assertFalse(self._check_deactivated_sg_in_vcs(fo_cs_name))

    @attr('all', 'expansion', 'story128825', 'story128825_tc26')
    def test_26_p_deactivate_cs_offline_due_to_cs_initial_online(self):
        """
        @tms_id: torf_128825_tc26
        @tms_requirements_id: TORF-128825
        @tms_title: Deactivate CS with cs_initial_online = off
        @tms_description:
        Test to verify that after a CS is created with cs_initial_online=off,
        that it can be deactivated
        @tms_test_steps:
            @step: Create 1 CS with cs_initial_online = off
            @result: CS is created
            @step: Create/ Run plan
            @result: CS is now applied and offline
            @step: Create additional CS that will deactivate CS1
            @result: CS1 will be deactivated
            @step: Update cs_initial_online=on
            @result: All CS will now become online
            @step: Create/ Run plan
            @result: CS1 is set to ForRemoval and CS2 comes online
        @tms_test_precondition: Expansion of Cluster
        @tms_execution_type: Automated
        """
        timeout_mins = 20
        self.backup_path_props(self.management_server, self.vcs_cluster_url)

        self.log('info', 'Step 1: Update cs_intial_online = off')
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    props='cs_initial_online=off')

        self.log('info', 'Step 1: Creating suitable CS for test case')
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1, cleanup=True)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '1', 'standby': '0',
             'name': 'CS_{0}_1'.format(STORY),
             'node_list': 'n1'}, overwrite=True)

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.log('info', 'Step 2: Create/ Run plan')
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 10)

        cs_1_url = fixtures['vcs-clustered-service'][0]['vpath']
        cs_1_name = fixtures['service'][0]['parent']

        self.log('info', 'Ensure that CS_1 is OFFLINE')
        cs_grp_name = self.vcs.generate_clustered_service_name(cs_1_name,
                                                               self.cluster_id)
        hastatus_state = self.vcs.get_hagrp_value_cmd(cs_grp_name, "State")
        self.assertTrue(self.wait_for_cmd(self.node_exe[0], hastatus_state,
                                          expected_rc=0,
                                          expected_stdout='|OFFLINE|',
                                          timeout_mins=2, su_root=True),
                        'Service CS_1 is not OFFLINE')

        self.log('info', 'Step 3: Create additional CS that will '
                         'deactivate CS_1')
        story = STORY + '_2'
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1, story=story,
                                 cleanup=True)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '1', 'standby': '0',
             'name': 'CS_{0}_1'.format(story),
             'node_list': 'n4', 'deactivates': '{0}'.format(cs_1_name)},
            overwrite=True)
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.log('info', 'Step 4: Update cs_initial_online = on')
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    props='cs_initial_online=on')

        self.log('info', 'Step 5: Create / Run plan again')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        cs_2_name = fixtures['service'][0]['parent']
        self.log('info', 'Step 6: Ensure that CS_2 is ONLINE')
        cs_grp_name = self.vcs.generate_clustered_service_name(cs_2_name,
                                                               self.cluster_id)
        hastatus_state = self.vcs.get_hagrp_value_cmd(cs_grp_name, "State")
        self.assertTrue(self.wait_for_cmd(self.node_exe[3], hastatus_state,
                                          expected_rc=0,
                                          expected_stdout='|ONLINE|',
                                          timeout_mins=2, su_root=True),
                        'Service CS_2 is not ONLINE')

        self.log('info', 'Checking CS_1 gets set to ForRemoval')
        self.execute_cli_createplan_cmd(self.management_server)
        vcs_fo_state = self.get_item_state(self.management_server, cs_1_url)
        self.assertEqual(vcs_fo_state, 'ForRemoval')
        self.execute_cli_runplan_cmd(self.management_server)
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Check deactivated SG is removed from VCS engine')
        self.assertFalse(self._check_deactivated_sg_in_vcs(cs_1_name))

    @attr('all', 'expansion', 'story128825', 'story128825_tc27')
    def test_27_p_deactivate_after_migration(self):
        """
        @tms_id: torf_128825_tc27
        @tms_requirements_id: TORF-128825
        @tms_title: Deactivate CS after migration has to different nodes
        @tms_description:
        Test to verify that if a CS previously undergone migration to
        different nodes can be deactivated successfully
        @tms_test_steps:
            @step: Create one CS
            @result: CS is configured in model
            @step: Create/ Run plan
            @result: CS is now applied
            @step: Migrate CS to different set of nodes
            @result: CS1 will be migrated to different nodes
            @step: Create/ Run plan
            @result: CS1 is now on new set of nodes
            @step: Create additional CS that will deactivate previously
            migrated CS
            @result: CS2 will deactivate CS1
            @step: Create/ Run plan
            @result: Plan is created and run to completion with no errors
        @tms_test_precondition: Expansion of Cluster
        @tms_execution_type: Automated
        """
        timeout_mins = 20
        self.log('info', 'Step 1: Creating suitable CS for test case')
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1, cleanup=True)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '1', 'standby': '0',
             'name': 'CS_{0}_1'.format(STORY),
             'node_list': 'n1'},
            overwrite=True)

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.log('info', 'Step 2: Create/ Run plan')
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 10)

        cs_1_url = fixtures['vcs-clustered-service'][0]['vpath']
        cs_1_name = fixtures['service'][0]['parent']

        self.log('info', 'Step 3: Update CS_1 to be migrated to different '
                         'nodes')
        self.execute_cli_update_cmd(self.management_server, cs_1_url,
                                    props='node_list=n3')
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 10)

        self.log('info', 'Step 4: Create additional CS that deactivates CS_1 '
                         'after migration')
        story = STORY + '_2'
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1, story=story,
                                 cleanup=True)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '1', 'standby': '0',
             'name': 'CS_{0}_1'.format(story),
             'node_list': 'n4',
             'deactivates': '{0}'.format(cs_1_name)},
            overwrite=True)
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.log('info', 'Step 5: Create/ Run Plan again')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, timeout_mins))

        self.log('info', 'Checking CS_1 gets set to ForRemoval')
        self.execute_cli_createplan_cmd(self.management_server)
        vcs_fo_state = self.get_item_state(self.management_server, cs_1_url)
        self.assertEqual(vcs_fo_state, 'ForRemoval')
        self.execute_cli_runplan_cmd(self.management_server)
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Check deactivated SG is removed from VCS engine')
        self.assertFalse(self._check_deactivated_sg_in_vcs(cs_1_name))

    @attr('manual-test', 'revert', 'story128825', 'story128825_tc38')
    def test_38_p_deactivation_same_time_as_normal_failover_of_cs(self):
        """
        @tms_id: torf_128825_tc38
        @tms_requirements_id: TORF-128825
        @tms_title: Verify a FO roughly takes the same amount of time as
        deactivating a SG
        @tms_description:
        Test to verify when deactivating a CS that it should roughly take the
        same amount of time as regular FO
        @tms_test_steps:
            @step: Create two CS (CS_1 (PL) and CS_2 (FO))
            @result: Two CS is configured in model
            @step: Create/ Run plan
            @result: CS are now applied
            @step: Create CS_3 in model that will deactivate CS_1
            @result: CS_3 is created in model
            @step: Cause CS_2 to Fail over to its standby node
            @result: CS_2 will be running on standby node
            @step: Create/ Run plan
            @result: CS_3 will deactivate CS_1 and CS_2 should fail over
            @step: Monitor the timing of plan to deactivate CS_1 and how long
            it takes for CS_2 to fail over
            @result: Plan should complete successfully and timing of
            deactivation should be roughly the same as a regular CS Fail over
        @tms_test_precondition: Expansion of Cluster
        @tms_execution_type: Manual
        """
        vip_props = {'network_name': 'traffic1',
                     'ipaddress': '172.16.100.10'}
        # Add firewall configuration for HTTP service between nodes
        self._add_firewall()

        self.log('info', 'Step 1: Creating two CS')
        fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2, valid_rpm=4,
                                 vips_len=1,
                                 cleanup=True)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '1', 'standby': '0',
             'name': 'CS_{0}_1'.format(STORY),
             'node_list': 'n1'}, overwrite=True)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 1,
            {'active': '1', 'standby': '1',
             'name': 'CS_{0}_2'.format(STORY), 'node_list': 'n2,n3'},
            overwrite=True)
        apply_item_changes(
            fixtures, 'ha-service-config', 1,
            {'parent': "CS_{0}_2".format(STORY),
             'vpath':
                 self.vcs_cluster_url + '/services/CS_{0}_2/ha_configs/'
                                        'HSC_{1}_2'.format(STORY, STORY)})
        apply_item_changes(
            fixtures, 'service', 1,
            {'parent': "CS_{0}_2".format(STORY),
             'destination':
                 self.vcs_cluster_url + '/services/CS_{0}_2/applications'
                                        '/APP_{1}_2'.format(STORY, STORY)})
        apply_item_changes(
            fixtures, 'vip', 0,
            {'vpath': self.vcs_cluster_url +
                      '/services/CS_{0}_2/ipaddresses/VIP1'.format(STORY)})
        apply_options_changes(
            fixtures, 'vip', 0, {
                'network_name': '{0}'.format(vip_props['network_name']),
                'ipaddress': '{0}'.format(vip_props['ipaddress'])},
            overwrite=True)
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.log('info', 'Step 2: Create/ Run plan to completion')
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 20,
                                add_to_cleanup=False)

        # Run HTTP server on MS
        self._copy_and_run_http_bash_script_to_ms()

        cs_1_name = fixtures['service'][0]['parent']

        self.log('info', 'Step 3: Create CS_3 that deactivates CS_1')
        story = STORY + '_3'
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1, valid_rpm=4,
                                 cleanup=True, story=story)
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '1', 'standby': '0',
             'name': 'CS_{0}_3'.format(story),
             'node_list': 'n4', 'deactivates': '{0}'.format(cs_1_name)},
            overwrite=True)
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)

        self.log('info', 'Step 4: Cause CS_2 SG to fail over to standby node')
        cmd = self.net_utils.get_clear_ip_cmd('172.16.100.10/24', 'eth4:0')
        stdout, stderr, rc = \
            self.run_command(self.node_exe[1], cmd, su_root=True)
        self.assertEqual(0, rc)
        self.assertEqual([], stderr)
        self.assertEqual([], stdout)

        self.log('info', 'Step 5: Create/ Run Plan to deactivate CS_1')
        self.execute_cli_runplan_cmd(self.management_server)

        #   Monitor Server access
        pl_sg_times = []
        fo_sg_times = []

        while pl_sg_times == [] or fo_sg_times == []:
            pl_sg_times, fo_sg_times = self._read_timestamp_from_http_server(
                '/tmp/http_output', ['node4', 'node3'])

        # Kill HTTP server process
        self._kill_pid()

        # Cleanup prior to testware cleanup
        self._cleanup_cs_before_testware()

    @attr('all', 'kgb-physical', 'story128825', 'story128825_tc28')
    def test_28_p_deactivate_cs_with_fencing_configured(self):
        """
        @tms_id: torf_128825_tc28
        @tms_requirements_id: TORF-128825
        @tms_title: Deactivate CS with fencing configured
        @tms_description:
        Test to verify that if a CS is configured with fencing that it can
        be deactivated successfully by another CS
        @tms_test_steps:
            @step: Check for suitable CS with fencing configured in model
            exists
            @result: CS is applied in model
            @step: Create CS2 that will be used to deactivate CS1
            @result: CS2 will deactivate CS1
            @step: Ensure fencing is running prior to running plan
            @result: Fencing is running
            @step: Create/ Run plan
            @result: CS1 is now deactivated by CS2
            @step: Ensure CS2 comes online and fencing is still running
            @result: CS2 is online
        @tms_test_precondition: Physical hardware deployment
        @tms_execution_type: Automated
        """
        vcs_prop = self.get_props_from_url(self.management_server,
                                           self.vcs_cluster_url,
                                           filter_prop='cs_initial_online')
        if vcs_prop == 'off':
            self._update_vcs_cluster()

        timeout_mins = 60
        vip_props = {'network_name': 'traffic3',
                     'ipaddress': ['172.16.201.10', '172.16.201.11']}

        self.log('info', 'Step 1: Check for suitable CS in model for '
                         'deactivation')
        vcs_sgs = self.find_children_of_collect(self.management_server,
                                                self.vcs_cluster_url +
                                                '/services/',
                                                'clustered-service')
        for grps in vcs_sgs:
            if 'mysgroup2' in grps:
                cs_1_url = grps
            elif 'mysgroup1' in grps:
                cs_fo_url = grps

        self.assertNotEqual(cs_1_url, '', 'No Suitable SG found in model')

        cs_1_name = cs_1_url.split(self.vcs_cluster_url + '/services/')[1]

        self.log('info', 'Ensure SG is in Applied state')
        sg_state = self.get_item_state(self.management_server, cs_1_url)
        self.assertEqual(sg_state, 'Applied')

        self.log('info', 'Step 2: Create CS_2 in model that will deactivate '
                         'CS_1')
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1, vips_len=2)

        apply_options_changes(fixtures, 'vcs-clustered-service', 0,
                              {'active': '2', 'standby': '0',
                               'name': 'CS_{0}_1'.format(STORY),
                               'node_list': 'n4,n3',
                               'deactivates': '{0}'.format(cs_1_name)},
                              overwrite=True)
        apply_item_changes(
            fixtures, 'vip', 0, {
                'vpath': self.vcs_cluster_url +
                         '/services/CS_{0}_1/ipaddresses/ip1'.format(STORY)})
        apply_options_changes(
            fixtures, 'vip', 0, {
                'network_name': '{0}'.format(vip_props['network_name']),
                'ipaddress': '{0}'.format(vip_props['ipaddress'][0])},
            overwrite=True)
        apply_item_changes(
            fixtures, 'vip', 1, {
                'vpath': self.vcs_cluster_url + '/services/CS_{0}_1/'
                                                'ipaddresses/ip2'
                    .format(STORY)})
        apply_options_changes(
            fixtures, 'vip', 1, {
                'network_name': '{0}'.format(vip_props['network_name']),
                'ipaddress': '{0}'.format(vip_props['ipaddress'][1])},
            overwrite=True)
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        self.log('info', 'Updating dependency list in model to prevent error')
        self.execute_cli_update_cmd(self.management_server, cs_fo_url,
                                    props="dependency_list=''")

        self.log('info', 'Step 3: Ensure fencing is still running in model '
                         'prior to plan running')
        self._check_disk_based_fencing()

        self.log('info', 'Step 4: Create/ Run Plan')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Step 5: Ensure fencing is still running after '
                         'plan completion')
        self._check_disk_based_fencing()

        self.execute_cli_createplan_cmd(self.management_server)
        self.log('info', 'Ensure SG is in ForRemoval state')
        sg_state = self.get_item_state(self.management_server, cs_1_url)
        self.assertEqual(sg_state, 'ForRemoval')
        self.execute_cli_runplan_cmd(self.management_server)
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self.log('info', 'Check deactivated SG is removed from VCS engine')
        self.assertFalse(self._check_deactivated_sg_in_vcs(cs_1_name))

    @attr('all', 'kgb-physical', 'story128825', 'story128825_tc29')
    def test_29_p_deactivate_cs_with_filesystems(self):
        """
        @tms_id: torf_128825_tc29
        @tms_requirements_id: TORF-128825
        @tms_title: Deactivate CS with filesystems configured
        @tms_description:
        Test to verify that if a CS was created with file-systems that it can
        be deactivated by another CS successfully
        @tms_test_steps:
            @step: Check for suitable CS in model
            @result: CS1 is configured in model
            @step: Create CS2 that will be used to deactivate CS1
            @result: CS2 will deactivate CS1
            @step: Create/ Run plan
            @result: CS1 is now deactivated by CS2
            @step: Ensure CS2 file-systems are maintained
            @result: CS2 file-systems are maintained
        @tms_test_precondition: Physical hardware deployment
        @tms_execution_type: Automated
        """
        vcs_prop = self.get_props_from_url(self.management_server,
                                           self.vcs_cluster_url,
                                           filter_prop='cs_initial_online')
        if vcs_prop == 'off':
            self._update_vcs_cluster()
        timeout_mins = 60
        self.log('info', 'Check if litp model is expanded')
        self._is_model_expanded()
        # Check if model has been expanded already
        # Check if there are suitable service groups existing in
        # the model if not create them
        self.log('info', 'Step 1: Check for suitable CS in model for '
                         'migration')
        vcs_sgs = self.find_children_of_collect(self.management_server,
                                                self.vcs_cluster_url +
                                                '/services/',
                                                'clustered-service')
        for grps in vcs_sgs:
            if 'mysgroup1' in grps:
                fo_sg_url = grps
                fo_sg_name = fo_sg_url.split(self.vcs_cluster_url +
                                             '/services/')[1]
        self.assertNotEqual(fo_sg_url, '', 'No FO Service groups found '
                                           'in model')

        file_system_list = self.find(self.management_server,
                                     self.vcs_cluster_url +
                                     '/storage_profile/vxvm_profile/',
                                     'reference-to-file-system',
                                     find_refs=True)
        mnt_point = self._put_dummy_file_on_active_node(fo_sg_url, fo_sg_name)

        self.log('info', 'Step 2: Create CS_2 in model that will deactivate '
                         'CS_1')
        story = STORY + '_2'
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1, story=story)

        apply_options_changes(fixtures, 'vcs-clustered-service', 0,
                              {'active': '1', 'standby': '1',
                               'name': 'CS_{0}_1'.format(story),
                               'node_list': 'n4,n3',
                               'deactivates': '{0}'.format(fo_sg_name)},
                              overwrite=True)
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)
        cs_2_name = fixtures['service'][0]['parent']

        self.log('info', 'Inherit File_system to same location shared from '
                         'CS_1')
        self.execute_cli_inherit_cmd(
            self.management_server,
            fixtures['vcs-clustered-service'][0]['vpath'] +
            '/filesystems/fs1', file_system_list[0], add_to_cleanup=False)
        self.log('info', 'Update CS_2 to be new critical_service')
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    props='critical_service={0}'
                                    .format(cs_2_name))

        self.log('info', 'Step 3: Create/ Run plan')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        cs_grp_name = self.vcs.generate_clustered_service_name(cs_2_name,
                                                               self.cluster_id)

        self.log('info', 'Step 4: Ensure CS_2 file-systems are maintained')
        active_node, _ = self._check_active_node(cs_grp_name)
        self.assertTrue(
            self.is_text_in_list(
                DUMMY_FILE,
                self.run_command(
                    active_node,
                    'ls {0} -al'.format(mnt_point),
                    default_asserts=True)[0]))

        self.log('info', 'Check deactivated SG is removed from VCS engine')
        self.assertFalse(self._check_deactivated_sg_in_vcs(fo_sg_name))

        # Cleanup prior to testware cleanup
        self._cleanup_cs_before_testware()

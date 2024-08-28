"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     Dec 2015
@author:    Ciaran Reilly,
            Terry Meyler
@summary:   Integration Tests
            Agile: STORY-11240
"""

import os
import sys
import time
import socket
import exceptions
import test_constants
from litp_generic_test import GenericTest, attr
from redhat_cmd_utils import RHCmdUtils
from vcs_utils import VCSUtils
from generate import load_fixtures, generate_json, apply_options_changes

STORY = '11240'


class Story11240(GenericTest):
    """
    LITPCDS-11240:
    As a LITP User I want a means of disabling the on-lining of VCS Service
    Groups when initially created so that i can carry out a controlled restore
    procedure
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
        super(Story11240, self).setUp()
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

        self.node_1 = self.get_node_filename_from_url(self.management_server,
                                                      self.nodes_urls[0])
        self.list_of_cs_names = []
        self.repo_dir_3pp = test_constants.PP_PKG_REPO_DIR
        self.expected_grp_state = ['#Group               Attribute      '
                                   '       System     Value',
                                   'Grp_CS_c1_CS_11240_1 State          '
                                   '       node1      |OFFLINE|',
                                   'Grp_CS_c1_CS_11240_1 State          '
                                   '       node2      |OFFLINE|']

        self.nodes_to_expand = list()
        for nodes in ["node2", "node3", "node4"]:
            self.nodes_to_expand.append(nodes)
        self.fixtures = []

    def baseline(self, vcs_len, app_len, hsc_len, cleanup=False):
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
                              add_to_cleanup=cleanup)

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
        super(Story11240, self).tearDown()

    def _up_time(self, node):
        """
            Return uptime of node
        """
        cmd = self.rhcmd.get_cat_cmd('/proc/uptime')
        out, err, ret_code = self.run_command(node, cmd, su_root=True)
        self.assertEqual(0, ret_code)
        self.assertEqual([], err)
        self.assertNotEqual([], out)
        uptime_seconds = float(out[0].split()[0])
        return uptime_seconds

    def _node_rebooted(self, node):
        """
            Verify that a node  has rebooted.
        """
        node_restarted = False
        max_duration = 1800
        elapsed_sec = 0
        # uptime before reboot
        up_time_br = self._up_time(node)
        while elapsed_sec < max_duration:
            # if True:
            try:
                # uptime after reboot
                up_time_ar = self._up_time(node)
                self.log("info", "{0} is up for {1} seconds"
                         .format(node, str(up_time_ar)))

                if up_time_ar < up_time_br:
                    self.log("info", "{0} has been rebooted"
                             .format(node))
                    node_restarted = True
                    break
            except (socket.error, exceptions.AssertionError):
                self.log("info", "{0} is not up at the moment"
                         .format(node))
            except:
                self.log("error", "Reboot check. Unexpected Exception: {0}"
                         .format(sys.exc_info()[0]))
                self.disconnect_all_nodes()

            time.sleep(10)
            elapsed_sec += 10

        if not node_restarted:
            self.log("error", "{0} not rebooted in last {1} seconds."
                     .format(node, str(max_duration)))
        return node_restarted

    def _m_node_up(self, node):
        """
            Check if managed node is up
        """
        m_node_up = False
        max_duration = 300
        elapsed_sec = 0
        cmd = "/bin/hostname"
        while elapsed_sec < max_duration:
            try:
                # for node in self.mn_nodes:
                #node = self.mn_nodes[0]
                _, _, ret_code = self.run_command(node, cmd)
                self.assertEqual(0, ret_code)
                if ret_code == 0:
                    m_node_up = True
                    break
                else:
                    self.log(
                        "info",
                        "Node {0} is not up in last {1} seconds.".format(
                            node, elapsed_sec
                        )
                    )
            except (socket.error, exceptions.AssertionError):
                self.log(
                    "info",
                    "Litp is not up after {0} seconds".format(elapsed_sec)
                )
            except:
                self.log(
                    "error",
                    "Unexpected Exception: {0}".format(sys.exc_info()[0])
                )

            time.sleep(10)
            elapsed_sec += 10

        if not m_node_up:
            self.log(
                "error",
                "Node {0} is not up in last {1} seconds.".format(
                    node, str(max_duration)
                )
            )

        # Wait for NTP to resync times so that mco works again.
        time.sleep(60)
        return m_node_up

    def reboot_node(self, node):
        """ Reboot a node and wait for it to come up. """
        cmd = "/sbin/reboot now"
        out, err, ret_code = self.run_command(node, cmd, su_root=True)
        self.assertTrue(self.is_text_in_list("The system is going down", out))

        self.assertEqual([], err)
        self.assertEqual(0, ret_code)

        self.assertTrue(self._node_rebooted(node))
        time.sleep(5)

    def update_vcs_cluster(self, swtch='on'):
        """
        Description:
            Runs with every test case to update the cs_initial_online on/off
            via a litp update command
        Parameters:
            swtch: used to turn cs_initial_online on /off
        Actions:
            Updates the vcs-cluster item
        Returns: None
        """
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    'cs_initial_online={0}'.format(swtch))

    def vcs_health_check(self):
        """
        VCS health check.
        (useful after plan execution or failure)
        Used commands:
            hasys -display "node name" -attribute SysState
            haclus -state "cluster name"
            haclus -display | grep -i 'readonly'
            hacf -verify /etc/VRTSvcs/conf/config
        """
        # get nodes vpaths
        nodes = []
        for node in self.nodes_urls:
            node_vpath = \
                self.get_node_filename_from_url(self.management_server, node)
            node_hostname = \
                self.get_node_att(node_vpath, 'hostname')
            # Check nodes state
            hasys_cmd = \
                self.vcs.get_hasys_cmd('-display {0} -attribute SysState'.
                                       format(node_hostname))
            std_out, std_err, r_code = self.run_command(node_vpath,
                                                        hasys_cmd,
                                                        su_root=True)
            self.assertEqual('{0} SysState RUNNING'.format(node_hostname),
                             ' '.join(std_out[1].split()))
            self.assertEqual(0, r_code)
            self.assertEqual([], std_err)
            nodes.append(node_vpath)
        # Check main.cf is read only
        haclus_cmd = \
            self.vcs.get_haclus_cmd('-display | grep -i \'readonly\'')
        std_out, std_err, r_code = self.run_command(nodes[0],
                                                    haclus_cmd,
                                                    su_root=True)
        self.assertEqual('ReadOnly 1', ' '.join(std_out[0].split()))
        self.assertEqual(0, r_code)
        self.assertEqual([], std_err)
        # Check main.cf is valid
        haclus_cmd = self.vcs.validate_main_cf_cmd()
        std_out, std_err, r_code = self.run_command(nodes[0],
                                                    haclus_cmd,
                                                    su_root=True)
        self.assertEqual([], std_out, 'VCS main.cf is not valid')
        self.assertEqual(0, r_code)
        self.assertEqual([], std_err)
        # Check cluster is running
        cluster_name = self.vcs_cluster_url.split('/')[-1]
        haclus_cmd = self.vcs.get_haclus_cmd('-state {0}'.
                                             format(cluster_name))
        std_out, std_err, r_code = self.run_command(nodes[0],
                                                    haclus_cmd,
                                                    su_root=True)
        self.assertEqual('RUNNING', std_out[0])
        self.assertEqual(0, r_code)
        self.assertEqual([], std_err)

    def add_cs_grp(self):
        """
        Description:
            Method to add additional VCS CS that will be used in tests
        Variables used:
            second_cs: name of the clustered service
            cs_create_props: optional parameters for CS creation
            lsb_create_props: optional lsb service parameters
            pkge_props: optional parameters for package creation
            rpms: name of the RPM used in test case (Note is removed at end
                    of test case)
         Returns:
            stdout: standard output from run plan
            stderr: stand error output from run plan
            rc: return code output from run plan

        """
        second_cs = 'CS_11240_2'
        cs_create_props = ('name={0} standby=0 node_list={1} active=1'.
                           format(second_cs, self.node_ids[0]))
        lsb_create_props = ('service_name=test-lsb-12 name=test-lsb-12 '
                            'user=root')

        pkge_props = 'name=EXTR-lsbwrapper12 version=1.1.0-1'

        # List of rpms required for this test
        rpms = "EXTR-lsbwrapper12-1.1.0.rpm"

        # Location where RPMs to be used are stored
        rpm_src_dir = \
            os.path.dirname(os.path.realpath(__file__)) + "/test_lsb_rpms/"

        filelist = []
        filelist.append(self.get_filelist_dict(rpm_src_dir + rpms, "/tmp/"))
        self.copy_filelist_to(self.management_server, filelist, root_copy=True)
        self.execute_cli_import_cmd(self.management_server, '/tmp/' + rpms,
                                    self.repo_dir_3pp)

        self.execute_cli_create_cmd(self.management_server,
                                    self.vcs_cluster_url + '/services/' +
                                    second_cs,
                                    'vcs-clustered-service',
                                    cs_create_props)

        self.execute_cli_create_cmd(self.management_server,
                                    self.vcs_cluster_url +
                                    '/services/' + second_cs +
                                    '/ha_configs/service_config',
                                    'ha-service-config')

        self.execute_cli_create_cmd(self.management_server,
                                    self.vcs_cluster_url +
                                    '/services/' + second_cs +
                                    '/runtimes/APP_11240_2',
                                    'lsb-runtime',
                                    lsb_create_props)

        self.execute_cli_create_cmd(self.management_server,
                                    '/software/items/EXTR-lsbwrapper12',
                                    'package',
                                    pkge_props)

        self.execute_cli_inherit_cmd(self.management_server,
                                     self.vcs_cluster_url +
                                     '/services/' + second_cs +
                                     '/runtimes/APP_11240_2/packages'
                                     '/EXTR-lsbwrapper12',
                                     '/software/items/EXTR-lsbwrapper12',
                                     )

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

    def _execute_prepare_restore(self, expect_error=None):
        """
        Description:
            Run the litp prepare_restore cli command and wait for plan
            to complete
        Args:
            expect_error (str): Expected error type
        """
        if expect_error is None:
            self.execute_cli_prepare_restore_cmd(self.management_server)
            self.wait_for_plan_state(self.management_server,
                                     test_constants.PLAN_COMPLETE)
        else:
            _, stderr, _ = self.execute_cli_prepare_restore_cmd(
                            self.management_server, expect_positive=False)
            self.assertTrue(self.is_text_in_list(expect_error, stderr),
                            'Expected error {0} not found in {1}'
                            .format(expect_error, stderr))

    def _expand_model(self):
        """
        Description:

            Method that will expand the litp model to have four running nodes
        Steps:
            1. Expand the litp model cluster to run on four nodes
        Return:
            Nothing
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

    def create_clust_services(self):
        """
        Method that will create the cluster services for testing expansion
        with
        :return: Nothing
        """
        self.fixtures = self.baseline(1, 1, 1)

        apply_options_changes(self.fixtures,
                              'vcs-clustered-service', 0,
                              {'active': '1', 'standby': '0',
                               'name': 'CS_11240_1', 'node_list': 'n1'},
                              overwrite=True)
        self.list_of_cs_names = [self.fixtures['service'][0]['parent']]

        self.apply_cs_and_apps_sg(self.management_server, self.fixtures,
                                  self.rpm_src_dir)

    @attr('all', 'non-revert', 'story11240', 'story11240_tc05',
          'cdb_priority1')
    def test_05_p_cs_initial_off_sg_no_online(self):
        """
        @tms_id: litpcds_11240_tc05
        @tms_requirements_id: LITPCDS-11240
        @tms_title: test_05_p_cs_initial_off_sg_no_online
        @tms_description: Test to validate when the cs_initial_online property
            is set to off, after the plan deploys a clustered service, they
            will be in an offline state, even after deploying a another CS.
            Until the first CS is brought online manually the lock task in the
            subsequent plans will fail.
        @tms_test_steps:
            @step: Update the VCS CS cs_initial_online property to off
            @result: The VCS CS cs_initial_online property is updated in the
                model to off
            @step: Create a failover CS if one does not exist
            @result: There is a failover CS in the model
            @step: Check that the SG state matches the expected state
            @result: The state of the SG matches the expected state
            @step: Update the VCS CS cs_initial_online property to on
            @result: The VCS CS cs_initial_online property is updated in the
                model to on
            @step: Create a new clustered service.
            @result: A new CS exists in the model
            @step: Create and Run plan
            @result: Plan runs successfully
            @step: Check that the SG is OFFLINE one node 1
            @result: The SG is OFFLINE
            @step: Manually bring the CS online
            @result: The CS is in an ONLINE state
            @step: Check that the SG is ONLINE one node 1
            @result: The SG is ONLINE
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        plan_timeout_mins = 5

        # Step 1 and 2
        self.update_vcs_cluster(swtch='off')
        fixtures = self.baseline(1, 1, 1, True)

        cs_url = self.get_cs_conf_url(self.management_server,
                                      fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)
        if cs_url is None:
            apply_options_changes(
                fixtures,
                'vcs-clustered-service', 0, {'active': '1', 'standby': '1',
                                             'name': 'CS_11240_1',
                                             'node_list': '{0}'
                .format(','.join(self.node_ids))},
                overwrite=True)
            self.list_of_cs_names = [fixtures['service'][0]['parent']]

            self.apply_cs_and_apps_sg(self.management_server,
                                      fixtures,
                                      self.rpm_src_dir)

            # Step 3 and 4
            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE, 5)

        cs_grp_name = \
            self.vcs.generate_clustered_service_name(self.list_of_cs_names[0],
                                                     self.cluster_id)
        # Step 5
        get_vcs_grp_state = self.vcs.get_hagrp_state_cmd()
        stdout, _, rc = self.run_command(self.node_1, get_vcs_grp_state +
                                         cs_grp_name,
                                         add_to_cleanup=False, su_root=True)

        self.assertEqual(0, rc)
        self.assertEqual(self.expected_grp_state, stdout)

        # Step 6
        self.update_vcs_cluster()

        # Steps 7 and 8
        self.add_cs_grp()

        # Step 9
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 test_constants.PLAN_COMPLETE,
                                                 plan_timeout_mins))

        hastat_cmd = self.vcs.get_hastatus_sum_cmd()

        stdout, _, _ = self.run_command(self.node_1, hastat_cmd, su_root=True)

        cs_state = self.vcs.get_hastatus_sg_sys_state(stdout, cs_grp_name,
                                                      'node1')
        self.assertEqual(cs_state, 'OFFLINE')

        # Step 10
        brng_sg_grp_online = self.vcs.get_hagrp_cs_online_cmd(cs_grp_name,
                                                              self.node_1)
        self.run_command(self.node_1, brng_sg_grp_online, su_root=True,
                         default_asserts=True)

        # Check service group 1 is online
        ha_stat_cmd = self.vcs.get_hagrp_value_cmd(cs_grp_name,
                                                         'State',
                                                         system=self.node_1)
        self.assertTrue(self.wait_for_cmd(self.node_1, ha_stat_cmd,
                                          expected_rc=0,
                                          expected_stdout='ONLINE',
                                          timeout_mins=5,
                                          su_root=True))
        # Check service group 2 is online
        cs_grp_name = \
            self.vcs.generate_clustered_service_name('CS_11240_2',
                                                     self.cluster_id)

        cs_state = self.vcs.get_hastatus_sg_sys_state(stdout, cs_grp_name,
                                                      'node1')
        self.assertEqual(cs_state, 'ONLINE')

    # @attr('pre-reg', 'non-revert', 'story11240', 'story11240_tc06')
    def obsolete_06_p_sg_online_update_ignore_cs_initial(self):
        """
        The original TMS description for this test was incorrect and
        doesn't reflect the code. The test actually checks that no plan was
        created when the cs_inital_online property was updated. This test has
        been obsoleted and is covered in AT found testset_story11240/
        test_02_n_no_model_update_cs_initial_no_generate_plan.at
        #tms_id: litpcds_11240_tc06
        #tms_requirements_id: LITPCDS-11240
        #tms_title: test_06_p_sg_online_update_ignore_cs_initial
        #tms_description: Test to validate when the cs_initial_online property
            is set to off and an online service group is brought to an updated
            state, litp will ignore the property value and proceed with the
            update successfully.
        #tms_test_steps:
            #step: Update the VCS CS cs_initial_online property to on
            #result: The VCS CS cs_initial_online property is updated in the
                model to on
            #step: Create a failover CS if one does not exist
            #result: There is a failover CS in the model
            #step: Update the VCS CS cs_initial_online property to off
            #result: The VCS CS cs_initial_online property is updated in the
                model to off
            #step: Execute litp create_plan
            #result: Expected "DoNothingPlanError" returned
            #step: Run VCS hagrp command
            #result: VCS SG state is obtained
            #step: Check that the SG state matches the expected state
            #result: The state of the SG matches the expected state
        #tms_test_precondition: NA
        #tms_execution_type: Automated
        """
        pass

    # @attr('pre-reg', 'non-revert', 'story11240', 'story11240_tc07')
    def obsolete_07_p_stop_plan_pre_online_task_update_cs_initial_off(self):
        """
        Obsoleted as it is deemed to be an edge case and has become invalid
        due to the use of resume plan.
        #tms_id: litpcds_11240_tc07
        #tms_requirements_id: LITPCDS-11240
        #tms_title: test_07_p_stop_plan_pre_online_task_update_cs_initial_off
        #tms_description: Test to validate when the cs_initial_online property
            is set to on and a new vcs-clustered-service is added, if the litp
            plan is stopped before the online task phase is executed and the
            cs_initial_online property is updated to off, then the subsequent
            plan will not include service group online task.
        #tms_test_steps:
            #step: Update the VCS CS cs_initial_online property to on
            #result: The VCS CS cs_initial_online property is updated in the
                model to on
            #step: Create a CS if one does not exist
            #result: There is a CS in the model
            #step: Create and Run plan
            #result: Plan is runnning
            #step: Wait for plan to complete task 'Create VCS service group..'
            #result: The plan has completed the creation of the VCS SG.
            #step: Restart the litpd service
            #result: the litpd service is restarted
            #step: Check that VCS is running in a healthy state
            #result: VCS is running
            #step: Update the VCS CS cs_initial_online property to off
            #result: The VCS CS cs_initial_online property is updated in the
                model to off
            #step: Manually bring the CS online
            #result: The CS is in an ONLINE state
            #step: Manually remove the SG to check idempotency
            #result: The SG is removed
            #step: Create and Run plan
            #result: Plan runs successfully
            #step: Run VCS hagrp command
            #result: VCS SG state is obtained
            #step: Check that the SG state matches the expected state
            #result: The state of the SG matches the expected state
            #step: Update the VCS CS cs_initial_online property to on
            #result: The VCS CS cs_initial_online property is updated in the
                model to on
        #tms_test_precondition: NA
        #tms_execution_type: Automated
        """
        pass

    @attr('manual-test', 'revert', 'story11240', 'story11240_tc08')
    def test_08_p_prepare_restore_initial_install_cs_initial_off(self):
        """
        @tms_id: litpcds_11240_tc08
        @tms_requirements_id: LITPCDS-11240
        @tms_title: test_08_p_prepare_restore_initial_install_cs_initial_off
        @tms_description: Test to validate when prepare_restore command is
            executed, all nodes in the litp model, except MS will be reset to
            initial state and will be reinstalled. The service groups will
            then be configured based on the cs_initial_online property value.
        @tms_test_steps:
            @step: Execute the litp prepare_restore command
            @result: All items in the model are set to an initial state
            @step: Create and Run plan
            @result: Plan runs successfully
            @step: Update the VCS CS cs_initial_online property to off
            @result: The VCS CS cs_initial_online property is updated in the
                model to off
            @step: Create a CS if one does not exist
            @result: There is a CS in the model
            @step: Create and Run plan
            @result: Plan runs successfully
            @step: Check the CS is configured for VCS but is in an OFFLINE
                state
            @result: The CS is in an OFFLINE state
            @step: Manually bring the CS online
            @result: The CS is in an ONLINE state
            @step: Update the VCS CS cs_initial_online property to on
            @result: The VCS CS cs_initial_online property is updated in the
                model to on
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        timeout_mins = 60
        node_2 = self.get_node_filename_from_url(self.management_server,
                                                 self.nodes_urls[1])
        # Step 1
        self._execute_prepare_restore()

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.wait_for_plan_state(self.management_server,
                                test_constants.PLAN_COMPLETE,
                                timeout_mins)

        cmd = "/bin/rm -rf /home/litp-admin/.ssh/known_hosts"
        stdout, _, _ = self.run_command(self.management_server, cmd,
                                        default_asserts=True,
                                        su_root=True)

        cmd = "/bin/rm -rf /root/.ssh/known_hosts"
        stdout, _, _ = self.run_command(self.management_server, cmd,
                                        default_asserts=True, su_root=True)

        self.set_pws_new_node(self.management_server, self.node_1)
        self.set_pws_new_node(self.management_server, node_2)

        # Step 2
        switch = 'off'
        self.update_vcs_cluster(switch)

        # Step 3
        fixtures = self.baseline(1, 1, 1, True)

        cs_url = self.get_cs_conf_url(self.management_server,
                                      fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)
        if cs_url is None:
            apply_options_changes(
                fixtures,
                'vcs-clustered-service', 0, {'active': '1', 'standby': '1',
                                             'name': 'CS_11240_1',
                                             'node_list': '{0}'.format
                                             (','.join(self.node_ids))},
                overwrite=True)
            self.list_of_cs_names = [fixtures['service'][0]['parent']]

            self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                      self.rpm_src_dir)
        # Step 4 and 5
            self.execute_cli_createplan_cmd(self.management_server)
            self.execute_cli_runplan_cmd(self.management_server)

        cs_grp_name = self.vcs.generate_clustered_service_name(
            self.list_of_cs_names[0], self.cluster_id)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 test_constants.PLAN_COMPLETE))
        # Step 6
        get_vcs_grp_state = self.vcs.get_hagrp_state_cmd()
        stdout, _, rc = self.run_command(self.node_1, get_vcs_grp_state +
                                         cs_grp_name,
                                         add_to_cleanup=False, su_root=True)

        self.assertEqual(0, rc)
        self.assertEqual(self.expected_grp_state, stdout)

        # Step 7
        brng_sg_grp_online = self.vcs.get_hagrp_cs_online_cmd(cs_grp_name,
                                                              self.node_1)

        self.run_command(self.node_1, brng_sg_grp_online, su_root=True,
                         default_asserts=True)

        self.wait_for_vcs_service_group_online(self.node_1, cs_grp_name,
                                               online_count=1)

        self.update_vcs_cluster()

    @attr('manual-test', 'revert', 'story11240', 'story11240_tc09')
    def test_09_p_prepare_restore_initial_install_cs_initial_off(self):
        """
        @tms_id: litpcds_11240_tc09
        @tms_requirements_id: LITPCDS-11240
        @tms_title: test_10_p_expand_service_group_cs_initial_off
        @tms_description: Test to validate that cluster expansion works when
            cs_initial_online set to off.
        @tms_test_steps:
            @step: Update the VCS CS cs_initial_online property to off
            @result: The VCS CS cs_initial_online property is updated in the
                model to off
            @step: Create one node parallel CS if one does not exist
            @result: There is a one node CS in the model
            @step: Expand the model, adding node 2 and node 3
            @result: The model is updated with node 2 and node 3
            @step: Create and Run plan
            @result: Plan runs successfully
            @step: Check the CS is configured for VCS but is in an OFFLINE
                state
            @result: The CS is in an OFFLINE state
            @step: Update the CS node_list property to include the expanded
                nodes and active property from '1' to '3'
            @result: The CS properties are updated successfully in the model
            @step: Create and Run plan
            @result: Plan runs successfully
            @step: Check the CS is OFFLINE on all 3 nodes
            @result: The CS in online on 3 nodes.
            @step: Update the VCS CS cs_initial_online property to on
            @result: The VCS CS cs_initial_online property is updated in the
                model to on
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        phase_14_success = \
        "Create application resource \"Res_App_c1_CS_11240_1_APP_11240_1\" "\
        "for VCS service group \"Grp_CS_c1_CS_11240_1\""

        offline_count = 2
        wait_time_mins = 180
        node_2 = self.get_node_filename_from_url(self.management_server,
                                                 self.nodes_urls[1])

        # Step 1
        self._execute_prepare_restore()

        # Step 2
        switch = 'off'
        self.update_vcs_cluster(switch)
        # Step 3
        fixtures = self.baseline(1, 1, 1)

        cs_url = self.get_cs_conf_url(
            self.management_server, fixtures['service'][0]['parent'],
            self.vcs_cluster_url
        )
        if not cs_url:
            apply_options_changes(
                fixtures,
                'vcs-clustered-service',
                0,
                {
                    'active': '1',
                    'standby': '1',
                    'name': 'CS_11240_1',
                    'node_list': '{0}'.format(','.join(self.node_ids))
                },
                overwrite=True
            )
            self.apply_cs_and_apps_sg(
                self.management_server, fixtures, self.rpm_src_dir
            )

        # Step 4 and 5
        self.list_of_cs_names = [fixtures['service'][0]['parent']]
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        cs_grp_name = self.vcs.generate_clustered_service_name(
            self.list_of_cs_names[0], self.cluster_id
        )

        self.assertTrue(
            self.wait_for_task_state(
                self.management_server, phase_14_success,
                test_constants.PLAN_TASKS_SUCCESS, timeout_mins=wait_time_mins
            )
        )

        self.assertTrue(
            self.wait_for_plan_state(
                self.management_server, test_constants.PLAN_COMPLETE,
                timeout_mins=wait_time_mins
            )
        )

        # reset passwords after prepare_restore() deployment complete
        cmd = "/bin/rm -rf /home/litp-admin/.ssh/known_hosts"
        stdout, _, _ = self.run_command(self.management_server, cmd,
                                        default_asserts=True,
                                        su_root=True)
        cmd = "/bin/rm -rf /root/.ssh/known_hosts"
        stdout, _, _ = self.run_command(self.management_server, cmd,
                                        default_asserts=True, su_root=True)

        self.set_pws_new_node(self.management_server, self.node_1)
        self.set_pws_new_node(self.management_server, node_2)

        # Step 6
        mn_1_offline = False
        mn_2_offline = False
        get_vcs_grp_state = self.vcs.get_hagrp_state_cmd()
        stdout, _, rc = self.run_command(
            self.node_1, '{0}{1}'.format(get_vcs_grp_state, cs_grp_name),
            add_to_cleanup=False, su_root=True
        )
        self.assertEqual(0, rc)
        for line in stdout:
            if cs_grp_name in line:
                if 'node1' in line and 'OFFLINE' in line:
                    mn_1_offline = True
                if 'node2' in line and 'OFFLINE' in line:
                    mn_2_offline = True
        self.wait_for_vcs_service_group_offline(
            self.node_1, cs_grp_name, offline_count
        )
        self.assertTrue(mn_1_offline)
        self.assertTrue(mn_2_offline)

        # Step 7
        self.reboot_node(self.node_1)
        self.reboot_node(node_2)
        self.assertTrue(self._m_node_up(self.node_1))
        self.assertTrue(self._m_node_up(node_2))

        # Step 8
        online_count = 1
        wait_time_mins = 20
        mn_1_online = False
        mn_2_offline = False
        get_vcs_grp_state = self.vcs.get_hagrp_state_cmd()
        stdout, _, rc = self.run_command(
            self.node_1, '{0}{1}'.format(get_vcs_grp_state, cs_grp_name),
            add_to_cleanup=False, su_root=True
        )
        self.assertEqual(0, rc)
        for line in stdout:
            if cs_grp_name in line:
                if 'node1' in line and 'ONLINE' in line:
                    mn_1_online = True
                if 'node2' in line and 'OFFLINE' in line:
                    mn_2_offline = True
        self.wait_for_vcs_service_group_online(
            self.node_1, cs_grp_name, online_count
        )
        self.assertTrue(mn_1_online)
        self.assertTrue(mn_2_offline)

        self.update_vcs_cluster()

    @attr('all', 'expansion', 'story11240', 'story11240_tc10')
    def test_10_p_expand_service_group_cs_initial_off(self):
        """
        @tms_id: litpcds_11240_tc10
        @tms_requirements_id: LITPCDS-11240
        @tms_title: test_10_p_expand_service_group_cs_initial_off
        @tms_description: Test to validate that cluster expansion works when
            cs_initial_online set to off.
        @tms_test_steps:
            @step: Update the VCS CS cs_initial_online property to off
            @result: The VCS CS cs_initial_online property is updated in the
                model to off
            @step: Create one node parallel CS if one does not exist
            @result: There is a one node CS in the model
            @step: Expand the model, adding node 2 and node 3
            @result: The model is updated with node 2 and node 3
            @step: Create and Run plan
            @result: Plan runs successfully
            @step: Check the CS is configured for VCS but is in an OFFLINE
                state
            @result: The CS is in an OFFLINE state
            @step: Update the CS node_list property to include the expanded
                nodes and active property from '1' to '3'
            @result: The CS properties are updated successfully in the model
            @step: Create and Run plan
            @result: Plan runs successfully
            @step: Check the CS is OFFLINE on all 3 nodes
            @result: The CS in online on 3 nodes.
            @step: Update the VCS CS cs_initial_online property to on
            @result: The VCS CS cs_initial_online property is updated in the
                model to on
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        timeout_mins = 90
        # update cs_initial flag to off
        self.update_vcs_cluster(swtch='off')
        nodes = ['n1', 'n2', 'n3', 'n4']
        expand_list = []

        # Check if the model already has three nodes configured, if not
        # proceed with expansion
        node_list = self.find_children_of_collect(self.management_server,
                                                  self.vcs_cluster_url +
                                                  '/nodes/',
                                                  'node',
                                                  find_all_collect=True)
        for items, node in zip(node_list, nodes):
            expand_list.append((
                items.split(self.vcs_cluster_url + '/nodes/')[1], node)[0])

        # Step 2: Create one node parallel vcs clustered service
        if sorted(expand_list) == sorted(nodes):
            self.create_clust_services()
        else:
            self._expand_model()
            self.create_clust_services()
        # Steps 3 and 4: Create/ Run plan
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 test_constants.PLAN_COMPLETE,
                                                 timeout_mins))

        cs_grp_name = self.vcs.generate_clustered_service_name(
            self.list_of_cs_names[0], self.cluster_id)

        # Step 5: Assert the service group is in an OFFLINE state
        expected_grp_state = ['#Group               Attribute             '
                              'System     Value',
                              'Grp_CS_c1_CS_11240_1 State                 '
                              'node1      |OFFLINE|']
        get_vcs_grp_state = self.vcs.get_hagrp_state_cmd()
        actual_state, _, rc = self.run_command(self.node_1, get_vcs_grp_state
                                               + cs_grp_name,
                                               add_to_cleanup=False,
                                               su_root=True)

        self.assertEqual(0, rc)
        self.assertEqual(expected_grp_state, actual_state)

        # Step 6: Update the node list to include 3 active nodes instead of '1'
        node_props = 'node_list=n1,n2,n3 active=3'
        self.execute_cli_update_cmd(self.management_server,
                                    self.fixtures['vcs-clustered-service'][0]
                                    ['vpath'], node_props)
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)

        # Step 7 and 8: Create/ Run plan
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 10,
                                add_to_cleanup=False)

        # Step 9: Assert the service groups are OFFLINE on all nodes
        expected_grp_state = ['#Group               Attribute             '
                              'System     Value',
                              'Grp_CS_c1_CS_11240_1 State                 '
                              'node1      |OFFLINE|',
                              'Grp_CS_c1_CS_11240_1 State                 '
                              'node2      |OFFLINE|',
                              'Grp_CS_c1_CS_11240_1 State                 '
                              'node3      |OFFLINE|']

        actual_state, _, rc = self.run_command(self.node_1, get_vcs_grp_state
                                               + cs_grp_name,
                                               add_to_cleanup=False,
                                               su_root=True)

        self.assertEqual(actual_state, expected_grp_state)

        # Set cs_initial_flag back to on
        self.update_vcs_cluster()

    @attr('manual-test', 'revert', 'story11240', 'story11240_tc11')
    def test_11_p_failover_to_parallel_cs_initial_off(self):
        """
        @tms_id: litpcds_11240_tc11
        @tms_requirements_id: LITPCDS-11240
        @tms_title: test_11_p_failover_to_parallel_cs_initial_off
        @tms_description: Test to validate that a cluster service group can go
            from a failover to a parallel service group when cs_initial_online
            is set to off
        @tms_test_steps:
            @step: Create CS if one does not exist
            @result: There is a CS in the model
            @step: Update the CS cs_initial_online property to off
            @result: The cs_initial_online property is updated in the model
            @step: Create and Run plan
            @result: Plan runs successfully
            @step: Check the CS is configured for VCS but is in an OFFLINE
                state
            @result: The CS is in an OFFLINE state
            @step: Manually bring the CS online
            @result: The CS is in an ONLINE state
            @step: Update the active property of the CS to a value of '2' and
                the standby property to '0'
            @result: The CS properties are updated successfully in the model
            @step: Create and Run plan
            @result: Plan runs successfully
            @step: Check that the CS is ONLINE on both nodes
            @result: The CS is online on both nodes.
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        # Step 1 and Step 2
        self.update_vcs_cluster(swtch='off')
        fixtures = self.baseline(1, 1, 1, True)

        cs_url = self.get_cs_conf_url(self.management_server,
                                      fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)
        if cs_url is None:
            apply_options_changes(
                fixtures,
                'vcs-clustered-service', 0, {'active': '1', 'standby': '1',
                                             'name': 'CS_11240_1',
                                             'node_list': '{0}'.format
                                             (','.join(self.node_ids))},
                overwrite=True)
            self.list_of_cs_names = [fixtures['service'][0]['parent']]

            self.apply_cs_and_apps_sg(self.management_server,
                                      fixtures,
                                      self.rpm_src_dir)

            # Step 3 and 4
            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE, 5)

        cs_grp_name = \
            self.vcs.generate_clustered_service_name(self.list_of_cs_names[0],
                                                     self.cluster_id)

        expected_grp_state = ['#Group               Attribute             '
                              'System     Value',
                              'Grp_CS_c1_CS_11240_1 State                 '
                              'node1      |OFFLINE|',
                              'Grp_CS_c1_CS_11240_1 State                 '
                              'node2      |OFFLINE|']
        # Step 5
        get_vcs_grp_state = self.vcs.get_hagrp_state_cmd()

        stdout, _, rc = self.run_command(self.node_1, get_vcs_grp_state +
                                         cs_grp_name, add_to_cleanup=False,
                                         su_root=True)

        self.assertEqual(0, rc)
        self.assertEqual(expected_grp_state, stdout)

        # Step 6
        brng_sg_grp_online = self.vcs.get_hagrp_cs_online_cmd(cs_grp_name,
                                                              self.node_1)
        self.run_command(self.node_1, brng_sg_grp_online, su_root=True,
                         default_asserts=True)

        # Step 7
        node_props = 'active=2 standby=0'

        cs_url = self.get_cs_conf_url(self.management_server,
                                      fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)

        self.execute_cli_update_cmd(self.management_server, cs_url, node_props)

        # Step 8 and Step 9
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 10)
        # Step 10
        expected_grp_state = ['#Group               Attribute             '
                              'System     Value',
                              'Grp_CS_c1_CS_11240_1 State                 '
                              'node1      |ONLINE|',
                              'Grp_CS_c1_CS_11240_1 State                 '
                              'node2      |OFFLINE|']

        get_vcs_grp_state = self.vcs.get_hagrp_state_cmd()

        stdout, _, rc = self.run_command(self.node_1, get_vcs_grp_state +
                                         cs_grp_name, add_to_cleanup=False,
                                         su_root=True)

        self.assertEqual(0, rc)
        self.assertEqual(expected_grp_state, stdout)

        self.update_vcs_cluster()

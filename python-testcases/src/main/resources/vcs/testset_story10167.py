"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     July 2015
@author:    Boyan Mihovski
@summary:   Integration
            Agile: STORY-10167
"""

import os
from litp_generic_test import GenericTest, attr
import test_constants
from litp_cli_utils import CLIUtils
from vcs_utils import VCSUtils
from test_constants import (PLAN_TASKS_SUCCESS, PLAN_TASKS_INITIAL,
                            PLAN_TASKS_RUNNING)

# Location where RPMs to be used are stored
RPM_SRC_DIR = os.path.dirname(os.path.realpath(__file__)) + '/test_lsb_rpms/'


class Story10167(GenericTest):
    """
    LITPCDS-10167:
    The "critical-service" property is an optional property at
        the cluster level.
    The "critical-service" property can only be assigned in clusters of type
        VCS-Cluster with SFHA - validation error occurs otherwise.
    The "critical-service" property can only refer to a service name
        that is and active-standby service group -
        otherwise validation error should occur.
    The "critical-service" property can only be set on a cluster of 2 nodes,
        where there are not exactly 2 nodes in the cluster
        a validation error is to be raised.
    There can be one and only one critical service defined for a cluster,
        otherwise a validation error is raised.
    All other service groups are subject to the lock order arising from
        the location of the active instance of the "critical-service".
    The "critical-service" property is to be marked as "deprecated"
        immediately on implementation.
    A view "node_upgrade_ordering" is to be provided by on the vcs-cluster
        which when a "critical-service" is prvovided will return
        the desired node upgrade ordering favoring the critical service.
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
        super(Story10167, self).setUp()

        # specify test data constants
        self.cs_num = '10167'
        self.crit_serv = 'APP10167'
        self.lsb_rpm = 'EXTR-lsbwrapper10167-1.1.0.rpm'

        # define test data constants dict
        self.conf = {}

        # List of VCS clustered services names and associated run-time names
        self.conf['app_per_cs'] = {
            self.cs_num: self.crit_serv
        }

        # List of nodes defined per vcs-clustered-service
        self.conf['nodes_per_cs'] = {
            self.cs_num: [1, 2]
        }

        # Parameters per clustered-service
        self.conf['params_per_cs'] = {
            self.cs_num: {'active': 1, 'standby': 1}
        }

        # List of ip resources per run-time in a clustered service
        self.conf['ip_per_app'] = {
            self.crit_serv: []
        }

        # List of ip addresses and their associated networks
        self.conf['network_per_ip'] = {}

        # List of packages that will exist per run-time
        self.conf['pkg_per_app'] = {
            self.crit_serv: {'EXTR-lsbwrapper10167': {}}
        }

        # List of properties per lsb runtime
        self.conf['lsb_app_properties'] = {
            self.crit_serv: {'service_name': 'test-lsb-10167'}
        }

        # List of ha properties per CS
        self.conf['ha_service_config_properties'] = {
            self.cs_num: {}
        }

        self.management_server = self.get_management_node_filename()
        self.list_managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.list_managed_nodes[0]
        self.primary_node_url = (self.get_node_url_from_filename(
            self.management_server, self.primary_node))
        self.vcs = VCSUtils()
        self.cli = CLIUtils()

        # Repo where rpms will be installed
        self.repo_dir_3pp = test_constants.PP_PKG_REPO_DIR

        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.management_server,
                                         '/deployments', 'vcs-cluster')[-1]
        self.cluster_id = self.vcs_cluster_url.split('/')[-1]

        self.vcs_nodes_url = self.find(self.management_server,
                                       self.vcs_cluster_url, "node")
        self.vcs_nodes_url.sort()

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story10167, self).tearDown()

    def generate_execute_cs_cli(self, conf, vcs_cluster_url, cs_name,
                                app_class='lsb-runtime'):
        """
        This function will generate and execute the CLI to create
        a clustered services

        Args:
            conf (dict): configuration details for clustered-services

            vcs_cluster_url (str): Model url of vcs cluster item

            cs_name (str): clustered-service name

            app_class (str): class name of the application item

        Returns: -
        """

        # Get CLI commands
        cli_data = self.vcs.generate_cli_commands(vcs_cluster_url,
                                                  conf, cs_name,
                                                  app_class)

        # This section of code will add the nodes to the CS
        # Find cluster node urls
        nodes_urls = self.find(self.management_server,
                               vcs_cluster_url,
                               'node')
        node_cnt = 0
        node_vnames = []
        num_of_nodes = int(conf['params_per_cs'][cs_name]['active']) + \
                       int(conf['params_per_cs'][cs_name]['standby'])

        for node_url in nodes_urls:
            node_cnt += 1

            # Add the node to the cluster
            if node_cnt <= num_of_nodes:
                node_vnames.append(node_url.split('/')[-1])

        # Create Clustered-Service in the model
        cs_options = '{0} node_list="{1}"'.format(cli_data['cs']['options'],
                                                  ','.join(node_vnames))

        self.execute_cli_create_cmd(self.management_server,
                                    cli_data['cs']['url'],
                                    cli_data['cs']['class_type'],
                                    cs_options,
                                    add_to_cleanup=False)

        # Create lsb apps in the model
        self.execute_cli_create_cmd(self.management_server,
                                    cli_data['apps']['url'],
                                    cli_data['apps']['class_type'],
                                    cli_data['apps']['options'],
                                    add_to_cleanup=False)

        # Create all packages associated with lsb-app
        for pkg_data in cli_data['pkgs']:
            self.execute_cli_create_cmd(self.management_server,
                                        pkg_data['url'],
                                        pkg_data['class_type'],
                                        pkg_data['options'],
                                        add_to_cleanup=False)

        # CREATE THE HA SERVICE CONFIG ITEM
        if cli_data['ha_service_config'].keys():
            self.execute_cli_create_cmd(self.management_server,
                                        cli_data['ha_service_config']['url'],
                                        cli_data['ha_service_config']
                                        ['class_type'],
                                        cli_data['ha_service_config']
                                        ['options'],
                                        add_to_cleanup=False)

        # Create pkgs under the lsb-app
        for pkg_link_data in cli_data['pkg_links']:
            self.execute_cli_inherit_cmd(self.management_server,
                                         pkg_link_data['child_url'],
                                         pkg_link_data['parent_url'],
                                         add_to_cleanup=False)

        # create inherit to the service
        if app_class in ['service', 'vm-service']:
            self.execute_cli_inherit_cmd(self.management_server,
                                         cli_data['apps']
                                         ['app_url_in_cluster'],
                                         cli_data['apps']['url'],
                                         add_to_cleanup=False)

    def apply_cs_and_apps(self):
        """
        Description:
            To ensure that it is possible to specify, and deploy,
            a vcs-clustered-services containing different values about
            fault_on_monitor_timeout tolerance_limit and clean_timeout.
            Below a vcs-clustered-service of configuration active=1 standby=1

            It will create a
                2 nodes ha mode = failover.
                CS 10167 - 1 app.

        Actions:
             1. Add dummy lsb-services to repo
             2. Executes CLI to create model
             3. Create and execute plan.

        Results:
            The plan runs successfully
        """
        vcs_cluster_url = self.find(self.management_server,
                                    '/deployments', 'vcs-cluster')[-1]
        # It is assumed that any rpms required for this test
        # exist in a repo before the plan is executed
        # This section of the test sets this up
        # Copy RPMs to Management Server
        self.copy_file_to(self.management_server,
                          RPM_SRC_DIR + self.lsb_rpm, '/tmp/',
                          root_copy=True,
                          add_to_cleanup=False)

        # Use LITP import to add to repo for each RPM
        self.execute_cli_import_cmd(
            self.management_server,
            '/tmp/' + self.lsb_rpm,
            self.repo_dir_3pp)
        # This section of the test sets up the model and creates the plan
        # Maximum duration of running plan
        plan_timeout_mins = 20

        # Generate configuration for the plan
        # This configuration will contain the configuration for all
        # clustered-services to be created
        self.generate_execute_cs_cli(self.conf,
                                     vcs_cluster_url,
                                     self.cs_num,
                                     app_class='service')

        # update the cluster with critical service
        cluster_conf_props = 'critical_service=' + self.cs_num
        # Update with the values
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url, cluster_conf_props)
        # Create and execute plan
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(
            self.management_server,
            test_constants.PLAN_COMPLETE,
            plan_timeout_mins
        ))

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
        for node in self.vcs_nodes_url:
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

    def check_grp_online_node(self, nodes, grp_name):
        """
        Function to retrieve CS active node using the specified service group
        and nodes vpaths.
        Args:
            - nodes (str): Used nodes vpaths.
            - grp_name(str): Unique clustered service group name.

        Returns:
            - grp_online_node (str): Online node system name.
            - grp_offline_node (str): Offline node system name.
        """
        online_value = '|ONLINE|'
        offline_value = '|OFFLINE|'
        grp_offline_node = []
        grp_online_node = []
        grp_status_cmd = \
            self.vcs.get_hagrp_cmd('-state ' + grp_name + " | awk  'NR >= 2 "
                                                          "{{print $3}"
                                                          "{print $4}}'")
        stdout = self.run_command(nodes[0], grp_status_cmd,
                                  su_root=True,
                                  default_asserts=True)[0]
        if online_value in stdout:
            index = stdout.index(online_value)
            previous_value = stdout[index - 1]
            grp_online_node.append(previous_value)
        if offline_value in stdout:
            index = stdout.index(offline_value)
            previous_value = stdout[index - 1]
            grp_offline_node.append(previous_value)
        else:
            self.fail('Expected Online of Offline. Output: {0}'.format(stdout))

        self.assertFalse(len(grp_online_node) != 1,
                         'CS should be online only on one node')
        return grp_online_node[0], grp_offline_node[0]

    def check_plan_nodes_lock_order(self, first_node, second_node,
                                    first_lock_plan, second_lock_plan):
        """
        Check nodes lock order after litp create_plan.
        Args:
            - first_node (str): First locked node.
            - second_node(str): Second locked node.
            - first_lock_plan (tuple): Expected first lock phase
                and task numbers.
            - second_lock_plan (tuple): Expected second lock phase
                and task numbers.
        Returns:
            - Assert error and message if no match.
        """
        plan_output, _, _ = \
            self.execute_cli_showplan_cmd(self.management_server)
        phases_dict = self.cli.parse_plan_output(plan_output)
        plan_first_lock_msgs = (phases_dict[first_lock_plan[0]]
                                [first_lock_plan[1]]['DESC'][1])
        plan_second_lock_msgs = (phases_dict[second_lock_plan[0]]
                                 [second_lock_plan[1]]['DESC'][1])
        model_vcs_first_lock = 'Lock VCS on node "{0}"'. \
            format(first_node)
        model_vcs_second_lock = 'Lock VCS on node "{0}"'. \
            format(second_node)
        self.assertEqual(plan_first_lock_msgs, model_vcs_first_lock)
        self.assertEqual(plan_second_lock_msgs, model_vcs_second_lock)

    @attr('all', 'non-revert', 'story10167',
          'story10167_tc01', 'cdb_priority1')
    def test_01_p_cs_deploy_and_set_props(self):
        """
        @tms_id: litpcds_10167_tc01
        @tms_requirements_id: LITPCDS-10167
        @tms_title:
        Critical Service deploy and set properties
        @tms_description:
         To ensure that it is possible to create, a vcs-cluster(sfha) with
         "critical_service" property and a "vcs-clustered-service" as part
         from the cluster. Update the model with task which can cause node lock
         (change kernel parameter). Create plan and fail over the service
         before create plan. Run the plan and check critical service
         online status during all of lock phases. After successful plan
         check critical service is still online on the same node
         as before create plan.
        @tms_test_steps:
        @step: Run a plan which creates a service object and a
                "clustered-service" as part from
                present "vcs-cluster", and adds "critical_service" property
                which is pointing to the service.
        @result: Plan executes successfully
        @step: Create a plan which updates the model with a task which
                can cause node lock.
        @result: The first lock should be in the standby node of the plan
        @step: Remove the plan
        @result: Removal command executes successfully
        @step: Switch the service to the standby node and wait for it to
            come online
        @result: Service has now been switched to the standby node
        @step: Run create plan command
        @result: Check lock order
        @step: Run Plan
        @result: During first node lock the service is not running in the
            standby node and is running in the active node.
        @step: Restart the litp service while plan is running
        @result: Restarts and healthcheck passes
        @step: Create and run the plan
        @result: First lock applied phase is not present in initial state.
        @result: During second node lock the service is running in the standby
            node and is not running in the active node.
        @result: Plan completes successfully
        @tms_test_precondition: NA
        @tms_execution_type: Automated

        """
        # determine service group active node
        cs_group_name = \
            self.vcs.generate_clustered_service_name(self.cs_num,
                                                     self.cluster_id)

        # Step 1, 2, 3
        # set cs conf dep path
        cs_url = self.get_cs_conf_url(self.management_server,
                                      self.cs_num,
                                      self.vcs_cluster_url)
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.apply_cs_and_apps()
            # check main vcs attributes after plan
            self.vcs_health_check()

        # Step 4
        # get nodes hostnames and add new sys par per node
        nodes = []
        for node_path in self.vcs_nodes_url:
            nodes.append(self.get_node_filename_from_url
                         (self.management_server, node_path))
            sysparam_node = self.find(
                self.management_server, node_path, 'sysparam-node-config')
            # Need two tasks within the node lock as first one will run
            # to completion when litpd restart is performed later in test
            sysparam_conf_props = 'key="net.core.wmem_max" value="524287"'
            self.execute_cli_create_cmd(self.management_server,
                                        '{0}{1}'.format(
                                            sysparam_node[0],
                                            '/params/sysctrl_02'),
                                        'sysparam',
                                        sysparam_conf_props)

            sysparam_conf_props2 = 'key="net.core.rmem_max" value="524287"'
            self.execute_cli_create_cmd(self.management_server,
                                        '{0}{1}'.format(
                                            sysparam_node[0],
                                            '/params/sysctrl_03'),
                                        'sysparam',
                                        sysparam_conf_props2)

        # Step 5
        online_node, offline_node = self.check_grp_online_node(nodes,
                                                               cs_group_name)
        self.execute_cli_createplan_cmd(self.management_server)

        # Step 6
        self.check_plan_nodes_lock_order(offline_node, online_node,
                                         (1, 1), (4, 1))

        # Step 7
        _, _, r_code = self.execute_cli_removeplan_cmd(self.management_server)
        self.assertEqual(0, r_code)

        # Step 8
        # switch the group to non active node
        switch_grp_cmd = \
            self.vcs.get_hagrp_cmd('-switch {0} -to {1}'.
                                   format(cs_group_name,
                                          offline_node))
        _, stderr, r_code = self.run_command(nodes[0],
                                             switch_grp_cmd,
                                             su_root=True)
        self.assertEqual(0, r_code)
        self.assertEqual([], stderr)

        # Step 9
        # Waiting vcs command to be completed.
        self.wait_for_vcs_service_group_online(nodes[0], cs_group_name,
                                               online_count=1,
                                               wait_time_mins=1)
        online_node, standby_node = self.check_grp_online_node(nodes,
                                                               cs_group_name)
        self.assertEqual(offline_node, online_node)
        self.execute_cli_createplan_cmd(self.management_server)

        # Step 10
        self.check_plan_nodes_lock_order(standby_node, online_node,
                                         (1, 1), (4, 1))

        # Step 11
        self.execute_cli_runplan_cmd(self.management_server)

        # Step 12
        phase_1 = 'Lock VCS on node "{0}"'.format(standby_node)
        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 phase_1,
                                                 PLAN_TASKS_RUNNING,
                                                 False),
                        'First node lock is in incorrect node from LITP side'
                        )
        active_node, _ = self.check_grp_online_node(nodes,
                                                    cs_group_name)
        self.assertEqual(online_node, active_node)

        # Step 13
        phase_1_success = 'Lock VCS on node "{0}"'.format(standby_node)
        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 phase_1_success,
                                                 PLAN_TASKS_SUCCESS,
                                                 False),
                        'First node lock task is not succeed'
                        )
        self.restart_litpd_service(self.management_server)
        # check main vcs attributes after stop plan
        self.vcs_health_check()
        self.execute_cli_createplan_cmd(self.management_server)

        # Step 14
        self.assertEqual(PLAN_TASKS_INITIAL,
                         self.get_task_state(self.management_server,
                                             'Unlock VCS on node "{0}"'
                                             .format(standby_node),
                                             False)
                         )
        # Second run on the previous plan
        self.execute_cli_runplan_cmd(self.management_server)

        # Step 15
        phase_5 = 'Lock VCS on node "{0}"'.format(online_node)
        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 phase_5,
                                                 PLAN_TASKS_SUCCESS,
                                                 False),
                        'Second node lock is in incorrect node from LITP side'
                        )
        running_node, _ = self.check_grp_online_node(nodes,
                                                     cs_group_name)
        self.assertEqual(standby_node, running_node)

        # Step 16
        self.assertTrue(self.wait_for_plan_state(
            self.management_server,
            test_constants.PLAN_COMPLETE),
            'The plan execution did not succeed'
        )

    @attr('all', 'non-revert', 'story10167', 'story10167_tc11')
    def test_11_n_internal_critical_service_msges(self):
        """
        @tms_id: litpcds_10167_tc11
        @tms_requirements_id: LITPCDS-10167
        @tms_title:
        Internal critical service messages
        @tms_description:
        Ensure that the correct error messages are displayed during create plan
        @tms_test_steps:
        @step: Create a "vcs-cluster" with two nodes
        @result: VCS cluster created with two nodes
        @step:Create failover cluster service and set it to be
                a critical-service.
        @result: Critical service failover cluster created
        @step: Create a software package to be inherited by both nodes
        @result: Package inherited to both nodes
        @step: Create the plan, once nodes go into lock state repeat first
            three steps then set nodes into
            offline state.
        @result: Nodes are in offline state
        @result: The correct error message is returned during create_plan
               (Node upgrading view on the cluster cannot execute due to the
               rpc command failing, (vcs cluster is down)
        @result:The correct error message is returned during create_plan
               (Status of Critical-Service is offline on both nodes)
               (mcollective is not available during create_plan)

        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # determine service group active node
        cs_group_name = \
            self.vcs.generate_clustered_service_name(self.cs_num,
                                                     self.cluster_id)
        # Step 1, 2, 3
        # set cs conf dep path
        cs_url = self.get_cs_conf_url(self.management_server,
                                      self.cs_num,
                                      self.vcs_cluster_url)
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.apply_cs_and_apps()
            # check main vcs attributes after plan
            self.vcs_health_check()

        # Step 4
        # get nodes hostnames and add new sys par per node
        nodes = []
        for node_path in self.vcs_nodes_url:
            nodes.append(self.get_node_filename_from_url
                         (self.management_server, node_path))
            sysparam_node = self.find(
                self.management_server, node_path, 'sysparam-node-config')
            sysparam_conf_props = 'key="net.core.wmem_max" value="524287"'
            # Update with the values
            self.execute_cli_create_cmd(self.management_server,
                                        '{0}{1}'.format(
                                            sysparam_node[0],
                                            '/params/sysctrl_02'),
                                        'sysparam',
                                        sysparam_conf_props)

        # Step 6
        stop_vcs_cmd = self.vcs.get_hastop_force('-all')
        _, stderr, r_code = self.run_command(nodes[0],
                                             stop_vcs_cmd,
                                             su_root=True)
        self.assertEqual(0, r_code)
        self.assertEqual([], stderr)
        _, stderr, _ = self.execute_cli_createplan_cmd(self.management_server,
                                                       expect_positive=False)
        self.assertEqual('InternalServerError    Create plan failed: The '
                         'node_upgrade_ordering view on the cluster "{0}" '
                         'cannot execute because the rpc command is failing.'.
                         format(self.cluster_id), stderr[0]
                         )

        start_vcs_cmd = self.vcs.get_hastart()

        for node in nodes:
            _, stderr, _ = self.run_command(node,
                                            start_vcs_cmd,
                                            su_root=True)
            self.assertEqual([], stderr)

        for node in nodes:
            # Wait for cluster availability
            self.wait_for_vcs_service_group_online(node, cs_group_name,
                                                   online_count=1,
                                                   wait_time_mins=1)

        # Step 7
        _, _, r_code = self.stop_service(nodes[0], 'mcollective')
        self.assertEqual(0, r_code)
        _, stderr, _ = self.execute_cli_createplan_cmd(self.management_server,
                                                       expect_positive=False)
        self.assertEqual('InternalServerError    Create plan failed: The '
                         'status of the critical service "{0}" '
                         'on the node "{1}" cannot be determined.'.
                         format(self.cs_num, nodes[0]), stderr[0]
                         )
        _, _, r_code = self.start_service(nodes[0], 'mcollective')
        self.assertEqual(0, r_code)

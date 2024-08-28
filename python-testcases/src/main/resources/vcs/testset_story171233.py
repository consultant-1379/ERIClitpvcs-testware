"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     February 2017
@author:    Ciaran Reilly, Iacopo Isimbaldi
@summary:   Integration Tests
            Agile: STORY-159932
"""
import os

from generate import load_fixtures, generate_json, apply_options_changes, \
    apply_item_changes
from litp_generic_test import GenericTest, attr
from re import match
from redhat_cmd_utils import RHCmdUtils
from test_constants import GABTAB_PATH, PLAN_COMPLETE
from time import sleep
from vcs_utils import VCSUtils

STORY = '171233'


class Story171233(GenericTest):
    """
    TORF-171233:
        Seeding of VCS clusters
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
        super(Story171233, self).setUp()

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

        self.nodes_to_expand = ["node2", "node3", "node4"]

        self.expansion_performed = False

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story171233, self).tearDown()

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

    def create_FO_PL_services(self, nodeslist):
        """
        Create a FO and a PL clustered services
        :param nodeslist: List() of two strings that contains the nodes list
         for the two services (FO and PL)
        :return: None
        """
        fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2, cleanup=True)

        # FO service Definition
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 0,
            {'active': '1', 'standby': '1',
             'name': 'CS_{0}_1'.format(STORY),
             'node_list': '{0}'.format(nodeslist[0])
             },
            overwrite=True
        )
        # PL service Definition
        apply_options_changes(
            fixtures, 'vcs-clustered-service', 1,
            {'active': '2', 'standby': '0',
             'name': 'CS_{0}_2'.format(STORY),
             'node_list': '{0}'.format(nodeslist[1])
             },
            overwrite=True
        )
        # Updating value for PL service
        apply_item_changes(
            fixtures, 'ha-service-config', 1,
            {'parent': 'CS_{0}_2'.format(STORY),
             'vpath': self.vcs_cluster_url +
                      '/services/CS_{0}_2/ha_configs/HSC_{0}_2'.format(STORY)
             }
        )
        apply_item_changes(
            fixtures, 'service', 1,
            {'parent': 'CS_{0}_2'.format(STORY),
             'destination': self.vcs_cluster_url +
                            '/services/CS_{0}_2/applications/APP_{0}_2'
                                .format(STORY)
             }
        )
        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

    def do_model_expansion(self):
        """
        Expand the model to a 4 nodes deployment

        :return: None
        """

        # Assign IP to the bridges to have traffic going on and avoid vcs bring
        # it down
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

        # Ensure 4 nodes are in the model
        self.nodes_urls = self.find(self.management_server,
                                    self.vcs_cluster_url,
                                    'node')
        self.node_ids = [node.split('/')[-1] for node in self.nodes_urls]

        self.node_exe = []
        for node in self.nodes_urls:
            self.node_exe.append(
                self.get_node_filename_from_url(self.management_server, node))

        self.assertEqual(len(self.node_exe), 4)

        self.expansion_performed = True

    def is_model_expanded(self):
        """
        Method that checks if litp is expanded if not, execute node expansion,
        otherwise proceed with test

        :return: Boolean
        """
        nodes = ['n1', 'n2', 'n3', 'n4']
        # Check if model is expanded to 4 nodes if not proceed with test

        if sorted(nodes) == sorted(self.node_ids):
            return True

        return False

    def restore_snapshot(self):
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

    def set_nodes_passwords(self, nodes):
        """
        Method that sets the passwords for newly expanded nodes

        :return: None
        """
        for node in nodes:
            self.assertTrue(self.set_pws_new_node(self.management_server,
                                                  node),
                            "Failed to set password")

            # Sanity check to prove passwds have been set
            stdout, _, _ = self.run_command(node, 'hostname')

            self.assertEqual(stdout[0], node)

    def verify_fencing_and_gabconfig(self, node, port_flag=False,
                                     seed_flag=False):
        """
        Method that will check if fencing is configured and the number of
        minimal nodes required to keep cluster running in VCS
        :param port_flag: (bool) Used to determine whether fencing is
        configured or not
        :param node (str): Node to run command on
        :return: None
        """
        gab_cmd = self.vcs.get_gabconfig_cmd()

        # The seeding value of the cluster depends on the number of nodes
        # listed in the model.
        # If I have 2 or less nodes the seeding is 1. Otherwise I use the
        # formula (#nodes / 2) + 1
        # Obtain vcs_seed_threshold from litp model
        if seed_flag:
            gab_nodes = \
                self.get_props_from_url(self.management_server,
                                        self.vcs_cluster_url,
                                        filter_prop="vcs_seed_threshold")
        else:
            if len(self.node_exe) > 2:
                gab_nodes = (len(self.node_exe) / 2) + 1
            else:
                gab_nodes = 1

        cat_cmd = self.rh_cmds.get_cat_cmd(filepath=GABTAB_PATH)

        vcs_conf_out = self.run_command(node, gab_cmd, su_root=True,
                                        default_asserts=True)[0]
        gab_node_out = self.run_command(node, cat_cmd, su_root=True,
                                        default_asserts=True)[0]

        # Ensuring vcs_seed_threshold and gabconfig are in sync
        self.assertTrue(self.is_text_in_list("/sbin/gabconfig -c -n{0}"
                                             .format(str(gab_nodes)),
                                             gab_node_out))
        # Check if fencing is enabled or not
        if port_flag:
            # Fencing enabled
            self.assertTrue(self.is_text_in_list('Port b gen', vcs_conf_out))
        else:
            # Fencing disabled
            self.assertFalse(self.is_text_in_list('Port b gen', vcs_conf_out))

    def verify_clustered_service_online(self, node_cmd, service_to_check):
        """
        Method that will verify the clustered service is ONLINE

        :param node_cmd: Node on which the check is performed
        :param service_to_check: Node to check
        :return: None
        """
        # Check that the service is ONLINE on at least one node
        hastatus_cmd = self.vcs.get_hastatus_sum_cmd() + \
                       " | grep -E \"^B\\s+.+{0}\\s+node[0-9]+\\s+(Y|N)\\s+" \
                       "(Y|N)\\s+ONLINE\"".format(service_to_check)

        service_state = ''.join(
            self.run_command(node_cmd, hastatus_cmd, su_root=True,
                             default_asserts=True)[0])

        # The regex has to have a match. If the service_state is empty it means
        # the service is not running
        self.assertNotEqual("", service_state)

    def verify_node_running(self, node_cmd, node_to_check):
        """
        Method that will verify the node is RUNNING in the cluster service

        :param node_cmd: Node on which the check is performed
        :param node_to_check: Node to check
        :return: None
        """
        hastatus_cmd = self.vcs.get_hastatus_sum_cmd() + \
                       " | grep -E \"^A\\s*{0}\\s*RUNNING\"" \
                           .format(node_to_check)

        node_state = ''.join(self.run_command(node_cmd, hastatus_cmd,
                                              su_root=True,
                                              default_asserts=True)[0])

        self.assertNotEqual("", node_state)

    def wait_vcs_running(self, node, timeout=10, polling=3):
        """
        Method that check if VCS service is running on the node

        :param node: Node on which the check is performed
        :param timeout: Timeout in minutes (default 10 minutes)
        :return: Boolean
        """
        status_cmd = self.rh_cmds.get_systemctl_is_active_cmd("vcs")

        rc = 1
        time = 0

        # Loop until the output of "service vcs status" says that
        # vcs is running
        while rc != 0:
            _, _, rc = self.run_command(node, status_cmd, su_root=True)

            time += 1

            if time * polling > timeout * 60:
                self.log("info",
                         "wait_vcs_running timeout after {0} minutes"
                         .format(timeout))

                return False

            sleep(polling)

        # Timeout to allow vcs to connect to the cluster
        # (The VCS service is now running but it needs a while before it is
        # back in the cluster)
        sleep(30)

        # Get a list of running clustered services on the node_cmd
        hagrp_cmd = self.vcs.get_hagrp_cmd("-list") + " | grep -E " \
                                                      "\"^Grp_CS.+\\s+{0}\"" \
            .format(node)

        services = self.run_command(node, hagrp_cmd,
                                    su_root=True,
                                    default_asserts=True)[0]

        # Check the status of every service
        for service in services:
            service = service.split()[0]

            hagrp_cmd = self.vcs.get_hagrp_cmd("-state {0} -sys {1}"
                                               .format(service, node))

            status = ""
            time = 0

            # Ensure every clustered service is "ONLINE" or "OFFLINE"
            # Not "STOPPING" or "STARTING"
            while match("^((ONLINE|OFFLINE)(?!\\|(STARTING|STOPPING)))",
                        status) is None:
                status = ''.join(self.run_command(node, hagrp_cmd,
                                                  su_root=True,
                                                  default_asserts=True)[0])

                time += 1

                if time * polling > timeout * 60:
                    self.log("info",
                             "Service {0} not started after {1} minutes"
                             .format(service, timeout))

                    return False

                sleep(polling)

        return True

    def _power_relevant_nodes(self, node_list, ilo_ip, on_flag=False):
        """
        Method that will power off relevant nodes based off the size of the
        cluster
        :param: node_list: (list) Nodes that will be used to power off for TC
        :param: ilo_ip: (list) Physical IP addresses for .120 hardware
        :return: Nothing
        """
        for node, hw_ip in zip(node_list, ilo_ip):
            if on_flag:
                self.poweron_peer_node(self.management_server, node,
                                       wait_poweron=True,
                                       poweron_timeout_mins=15, ilo_ip=hw_ip)
                self.assertTrue(self.wait_vcs_running(node))
                self.verify_node_running(node, node)
            else:
                self.poweroff_peer_node(self.management_server, node,
                                        ilo_ip=hw_ip)

    @attr('all', 'kgb-physical', 'story171233', 'story171233_tc01')
    def test_01_p_check_clus_on_4_node_with_without_seeding_fencing(self):
        """
        @tms_id: torf_171233_tc01
        @tms_requirements_id: TORF-198359
        @tms_title: Check VCS behaviour on fencing cluster when seeding
        value is set and then not set
        @tms_description:
        Test to verify if a user has a 4 node cluster with fencing
        configured that does not have the seeding value on the cluster set,
        it will take the default value set via the formula defined in VCS
        plugin. Meaning if more than 2 nodes leave the cluster VCS will
        remain operational and SGs remain ONLINE. Then if we set the seeding
        value and re-run the same test the value should be equal to the
        new vcs_seed_threshold.
        NOTE: Verifies task TORF-171233
        @tms_test_steps:
            @step: Ensure fencing is configured in the cluster
            @result: Fencing is configured correctly
            @step: Check whether the litp model is two or 4 node deployment
            @result: Model has N number of nodes
            @step: Create 1 FO and 1 PL SG based on size of cluster
            @result: SGs are defind in the model
            @step: Create/ Run plan
            @result: Plan is run to completion
            @step: Assert vcs_seed_threshold and gabtab value based of
            cluster size
            @result: vcs_seed_threshold are in sync
            @step: Power off relevant nodes depending on size of cluster
            @result: Relevant nodes are powered off for testing purposes
            @step: Ensure VCS is still fully operational and SGs remain online
            on correct nodes
            @result: Nodes that are powered up still have SGs ONLINE
            @step: Wait for nodes to be powered back on
            @result: Nodes are powered back on and VCS is back running
            @step: Set vcs_seed_value within range of node count in cluster
            @result: vcs_seed_value is set
            @step: Power off nodes again relevant to the size of the cluster
            @result: Nodes are powered off
            @step: Ensure VCS is still fully operational and SGs remain online
            on correct nodes
            @result: Nodes that are powered up still have SGs ONLINE
            @step: Wait for nodes to be powered back on
            @result: Nodes are pwoered back on and VCS is back running
        @tms_test_precondition: N/A
        @tms_execution_type: Automated
        """
        # Physical HW ILO IP addresses. DO NOT CHANGE!!
        node_ilo_ip = {'node1': '10.44.84.9',
                       'node2': '10.44.84.11',
                       'node3': '10.44.84.41',
                       'node4': '10.44.84.42'
                       }
        timeout = 90
        self.log('info', 'Step 1: Ensure fencing is configured')
        self.log('info', 'Step 2: Check the number of nodes running in '
                         'cluster')
        self.verify_fencing_and_gabconfig(port_flag=True,
                                          node=self.node_exe[0],
                                          seed_flag=True)

        self.log('info', 'Step 3: Create PL and FO ')
        if len(self.node_exe) > 2:
            self.create_FO_PL_services(nodeslist=['n2,n4', 'n1,n3'])
        else:
            self.create_FO_PL_services(nodeslist=['n1,n2', 'n1,n2'])

        self.log('info', 'Step 4: Create/ Run plan to completion')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.wait_for_plan_state(self.management_server,
                                 PLAN_COMPLETE,
                                 timeout_mins=timeout)

        self.log('info', 'Step 5: Power off relevant nodes based on size of '
                         'cluster')
        if len(self.node_exe) > 2:
            self._power_relevant_nodes(node_list=[self.node_exe[1],
                                                  self.node_exe[2]],
                                       ilo_ip=[node_ilo_ip['node2'],
                                               node_ilo_ip['node3']])
        else:
            self._power_relevant_nodes(node_list=[self.node_exe[1]],
                                       ilo_ip=[node_ilo_ip['node2']])

        self.log('info', 'Step 6: Ensure VCS and gabtab are still '
                         'functioning')
        self.verify_fencing_and_gabconfig(port_flag=True,
                                          node=self.node_exe[0],
                                          seed_flag=True)

        self.log('info', 'Step 7: Verify SG is still ONLINE on relevant nodes')
        self.verify_clustered_service_online(self.node_exe[0],
                                             "CS_{0}_2".format(STORY))

        self.log('info', 'Step 8: Verify Node comes back with VCS running')
        if len(self.node_exe) > 2:
            self._power_relevant_nodes([self.node_exe[2], self.node_exe[1]],
                                       ilo_ip=[node_ilo_ip['node3'],
                                               node_ilo_ip['node2']],
                                       on_flag=True)
        else:
            self._power_relevant_nodes([self.node_exe[1]],
                                       ilo_ip=[node_ilo_ip['node2']],
                                       on_flag=True)

        self.log('info', 'Step 9: Update vcs_seed_threshold to suitable value '
                         'of cluster size')
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    props='vcs_seed_threshold={0}'.format(
                                        len(self.node_exe)))

        self.log('info', 'Step 10: Create/ Run plan again for seeding value')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.wait_for_plan_state(self.management_server,
                                 PLAN_COMPLETE,
                                 timeout_mins=timeout)

        self.log('info', 'Step 11: Power off relevant nodes based on size of '
                         'cluster')
        if len(self.node_exe) > 2:
            self._power_relevant_nodes(node_list=[self.node_exe[1],
                                                  self.node_exe[2]],
                                       ilo_ip=[node_ilo_ip['node2'],
                                               node_ilo_ip['node3']])
        else:
            self._power_relevant_nodes(node_list=[self.node_exe[1]],
                                       ilo_ip=[node_ilo_ip['node2']])

        self.log('info', 'Step 12: Ensure VCS and gabtab are still '
                         'functioning')
        self.verify_fencing_and_gabconfig(port_flag=True, seed_flag=True,
                                          node=self.node_exe[0])

        self.log('info', 'Step 13. Verify SG is still ONLINE on relevant '
                         'nodes')
        self.verify_clustered_service_online(self.node_exe[0],
                                             "CS_{0}_2".format(STORY))

        self.log('info', 'Step 14: Verify Node comes back with VCS running')
        if len(self.node_exe) > 2:
            self._power_relevant_nodes([self.node_exe[2], self.node_exe[1]],
                                       ilo_ip=[node_ilo_ip['node3'],
                                               node_ilo_ip['node2']],
                                       on_flag=True)
        else:
            self._power_relevant_nodes([self.node_exe[1]],
                                       ilo_ip=[node_ilo_ip['node2']],
                                       on_flag=True)

    @attr('all', 'expansion', 'story171233', 'story171233_tc4')
    def test_04_p_check_seeding_value_on_a_cluster_without_fencing(self):
        """
        @tms_id: torf_171233_tc04
        @tms_requirements_id: TORF-198359
        @tms_title: Check VCS behaviour on non-fencing cluster when seeding
        value is set
        @tms_description:
        Test to verify that a 4 node non-fencing VCS cluster behaves
        accordingly when seeding value is set in gabconfig and when nodes
        leave the cluster, it remains functionable, even when one re-joins
        successfully
        NOTE: Verifies task TORF-171233
        @tms_test_steps:
            @step: Create 4 node cluster with 2 SGs, 1 parallel and 1 FO
            @result: Service Groups created successfully.
            @step: Verify fencing is not configured and gabtab is configured
            as expected
            @result: Fencing is not configured and gabtab returns a number 3
            @step: Temporarily power off node 1
            @result: Gabtab has to be the same as before
            @step: Ensure node 1 rejoins the cluster and SGs remain online
            @result: SGs remain online and node 1 rejoins cluster
        @tms_test_precondition: N/A
        @tms_execution_type: Automated
        """
        timeout = 90

        self.log("info",
                 "Step1: Expand the model to a 4 nodes cluster and create a FO"
                 " and a PL clustered services")

        # Perform the expansion
        if not self.is_model_expanded():
            self.do_model_expansion()

        # Create service groups
        self.create_FO_PL_services(["n1,n2", "n3,n4"])

        # Execute the plan
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.wait_for_plan_state(self.management_server,
                                 PLAN_COMPLETE,
                                 timeout_mins=timeout)

        # Set the password on the new nodes
        if self.expansion_performed:
            self.set_nodes_passwords(self.nodes_to_expand)

        self.log("info", "Step 2: Verify fencing is not configured and gabtab"
                         " is configured correctly")
        self.verify_fencing_and_gabconfig(port_flag=False,
                                          node=self.node_exe[0])

        self.log("info", "Step 3: Power off node1")
        self.poweroff_peer_node(self.management_server, self.node_exe[0])

        # Check still get the right setting
        self.verify_fencing_and_gabconfig(port_flag=False,
                                          node=self.node_exe[1])

        # Check clustered service is still online
        self.verify_clustered_service_online(self.node_exe[1],
                                             "CS_{0}_1".format(STORY))

        self.log("info", "Step 4: Power off node4")
        self.poweroff_peer_node(self.management_server, self.node_exe[3])

        # Check still get the right setting
        self.verify_fencing_and_gabconfig(port_flag=False,
                                          node=self.node_exe[1])

        # Check clustered service is still online
        self.verify_clustered_service_online(self.node_exe[1],
                                             "CS_{0}_2".format(STORY))

        self.log("info", "Step 5: Power on node 1")
        self.poweron_peer_node(self.management_server, self.node_exe[0],
                               wait_poweron=True)

        # Wait VCS is running
        self.assertTrue(self.wait_vcs_running(self.node_exe[0]))

        # Check CS running on node 1
        self.verify_node_running(self.node_exe[1], "node1")

        # Check clustered service is still online
        self.verify_clustered_service_online(self.node_exe[1],
                                             "CS_{0}_1".format(STORY))

        self.log("info", "Step 6: Power on node 4")
        self.poweron_peer_node(self.management_server, self.node_exe[3],
                               wait_poweron=True)

        # Wait VCS is running
        self.assertTrue(self.wait_vcs_running(self.node_exe[3]))

        # Check CS running on node 4
        self.verify_node_running(self.node_exe[2], "node4")

        # Check clustered service is still online
        self.verify_clustered_service_online(self.node_exe[1],
                                             "CS_{0}_2".format(STORY))

    @attr('all', 'revert', 'story171233', 'story171233_tc05')
    def test_05_p_check_2_node_cluster_without_fencing(self):
        """
        @tms_id: torf_171233_tc05
        @tms_requirements_id: TORF-198359
        @tms_title: Check VCS behaviour on non-fencing cluster when seeding
        value is set
        @tms_description:
        Test to verify that a 2 node non-fencing VCS cluster behaves
        accordingly when seeding value is set in gabconfig and when nodes
        leave the cluster, it remains functionable, even when one re-joins
        successfully
        NOTE: Verifies task TORF-171233
        @tms_test_steps:
            @step: Create a 2 node cluster with 2 SGs - 1 parallel and 1 FO
            @result: Service Groups created successfully.
            @step: Verify fencing is not configured and gabtab is configured
            as expected
            @result: Fencing is not configured and gabtab returns a number 1
            @step: Temporarily power off node 1
            @result: Gabtab has to be the same as before
            @step: Ensure node 1 rejoins the cluster and SGs remain online
            @result: SGs remain online and node 1 rejoins cluster
        @tms_test_precondition: N/A
        @tms_execution_type: Automated
        """
        timeout = 90

        self.log("info",
                 "Step 1: Create a FO and a PL clustered services")

        # Create service groups
        self.create_FO_PL_services(["n1,n2", "n1,n2"])

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.wait_for_plan_state(self.management_server,
                                 PLAN_COMPLETE,
                                 timeout_mins=timeout)

        self.log("info",
                 "Step 2: Verify fencing is not configured and gabtab"
                 " is configured correctly")
        self.verify_fencing_and_gabconfig(port_flag=False,
                                          node=self.node_exe[0])

        self.log("info", "Step 3: Power off nodes 1")
        self.poweroff_peer_node(self.management_server, self.node_exe[0])

        # Check still get the right setting
        self.verify_fencing_and_gabconfig(port_flag=False,
                                          node=self.node_exe[1])

        # Check clustered services are still online
        self.verify_clustered_service_online(self.node_exe[1],
                                             "CS_{0}_1".format(STORY))
        self.verify_clustered_service_online(self.node_exe[1],
                                             "CS_{0}_2".format(STORY))

        self.log("info", "Step 4: Power on node 1")
        self.poweron_peer_node(self.management_server, self.node_exe[0],
                               wait_poweron=True)

        # Wait VCS is running
        self.assertTrue(self.wait_vcs_running(self.node_exe[0]))

        # Check CS running on node 1
        self.verify_node_running(self.node_exe[1], "node1")

        # Check clustered services are still online
        self.verify_clustered_service_online(self.node_exe[1],
                                             "CS_{0}_1".format(STORY))
        self.verify_clustered_service_online(self.node_exe[1],
                                             "CS_{0}_2".format(STORY))

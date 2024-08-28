"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     March 2016
@author:    Ciaran Reilly
            James Maher
@summary:   Integration Tests
            Agile: STORY-13258
"""

import test_constants
from litp_generic_test import GenericTest, attr
from vcs_utils import VCSUtils
from generate import load_fixtures, generate_json, apply_options_changes
import os

STORY = '13258'


class Story13258(GenericTest):
    """
    LITPCDS-13258:
        As a LITP user i want to reconfigure the Mii attribute of a VCS NIC
        resource so that i can choose how to monitor a network interface
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
        super(Story13258, self).setUp()
        self.management_server = self.get_management_node_filename()
        self.vcs = VCSUtils()
        self.netstat = 'netstat'
        self.mii = 'mii'

        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.management_server,
                                         '/deployments', 'vcs-cluster')[-1]

        self.net_hosts_urls = self.find(self.management_server,
                                        '/deployments', 'vcs-network-host')

        self.nodes_urls = self.find(self.management_server,
                                    self.vcs_cluster_url,
                                    'node')
        # Location where RPMs to be used are stored
        self.rpm_src_dir = (os.path.dirname(os.path.realpath(__file__)) +
                            '/rpm-out/dist/')

        self.node_1 = self.get_node_filename_from_url(self.management_server,
                                                      self.nodes_urls[0])
        self.node_ids = [node.split('/')[-1] for node in self.nodes_urls]

        self.network_hosts_url = self.find(self.management_server,
                                           '/deployments',
                                           'collection-of-vcs-network-host')

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story13258, self).tearDown()

    def update_def_nic_monitor(self, value):
        """
        Method to update the default_nic_monitor parameter on the cluster level
        :param
            value (str): Can either be netstat or mii
        :return:
            Nothing
        """
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    'default_nic_monitor={0}'.format(value))

    def _create_net_hosts(self, nh_dict):
        """
        Re-create all the removed network hosts from test cases
        :param nh_dict: The network hosts dictionary with all of the models
         configuration i.e. ip addresses, network names, and urls
        :return: Nothing
        """

        net_hosts_url = nh_dict['NetHosts']
        nh_ip_addrs = []
        net_names = []
        props = 'ip={0} network_name={1}'

        for addrs_and_names in nh_dict['Options']:
            nh_ip_addrs.append(addrs_and_names['ip'])
            net_names.append(addrs_and_names['network_name'])

        for urls, addrs, names in zip(net_hosts_url, nh_ip_addrs, net_names):
            self.execute_cli_create_cmd(self.management_server, urls,
                                        'vcs-network-host',
                                        props.format(addrs, names),
                                        add_to_cleanup=False)

    def remove_net_hosts_from_model(self, network_name='', nuke_nets=False):
        """
            Method used to remove specific network hosts from the model based
            off the network_name, or if boolean flag is TRUE all network hosts
            will be removed
        :param
            network_name (str): Network name used to remove hosts from i.e.
            traffic2
            nuke_nets (bool): default FALSE but If TRUE will remove ALL
            network hosts from model
        :return:
            nethosts_dict (dict): Holds all the network configuration
            that was removed during testing
        """
        self.net_hosts_urls = self.find(self.management_server,
                                        '/deployments', 'vcs-network-host')
        nethosts_dict = {"NetHosts": [], "Options": []}
        if not nuke_nets:
            for net_host in self.net_hosts_urls:
                net_name = self.get_props_from_url(self.management_server,
                                                   net_host, 'network_name')
                if net_name == network_name:
                    self.execute_cli_remove_cmd(self.management_server,
                                                net_host)
                    nethosts_dict["NetHosts"].append(net_host)
                    nethosts_dict["Options"].append(
                        self.get_props_from_url(self.management_server,
                                                net_host))
        elif nuke_nets:
            for net_host in self.net_hosts_urls:
                self.execute_cli_remove_cmd(self.management_server, net_host)
                nethosts_dict["NetHosts"].append(net_host)
                nethosts_dict["Options"].append(
                    self.get_props_from_url(self.management_server, net_host))

        return nethosts_dict

    def check_mii_state(self, exp_state, sg_name='Grp_NIC_c1_eth5'):
        """
        Method to run vcs command on node and check state of Mii attribute
        :param
            exp_state (str): 1 or 0 state of Mii attribute for service group
              resources
            sg_name (str): Specifies the Service Group to perform Mii check on,
              default is eth5 for traffic2 network
        :return:
            Nothing
        """
        cmd = self.vcs.get_hagrp_resource_list_cmd(sg_name)

        stdout = self.run_command(self.node_1, cmd, su_root=True,
                                  default_asserts=True)

        cmd = self.vcs.get_hares_cmd('-value {0} Mii'
                                     .format(stdout[0][0]))

        stdout = self.run_command(self.node_1, cmd, su_root=True,
                                  default_asserts=True)
        self.assertEqual(stdout[0][0], exp_state)

    def baseline(self, vcs_len, app_len, hsc_len, cleanup=False,
                 valid_rpm=1):
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

    # @attr('pre-reg', 'non-revert', 'story13258', 'story13258_tc01')
    def obsolete_01_p_chck_mii_att_updated(self):
        """
        Merged with test_02_p_update_default_nic_monitor.
        #tms_id: litpcds_13258_tc1
        #tms_requirements_id: LITPCDS-13258
        #tms_title: check mii property updated
        #tms_description: Test to validate if the Mii attribute is affected
                          when updating the default_nic_monitor property from
                          netstat to mii. Verify the mii attribute is set
                          correctly for service group resources with/ without
                          network hosts.
        #tms_test_steps:
            #step: Remove network hosts from a traffic 2 network on Vapp
            #result: item in for removal state
            #step:  Update the default_nic_monitor property to mii
            #result: item updated
            #step: create and run plan
            #result: plan executes successfully
            #result: the resource without any network hosts present has mii
                set to 1 and the others with network hosts present, mii remains
                equal to 0
        #tms_test_precondition: NA
        #tms_execution_type: Automated
        """
        pass

    @attr('all', 'non-revert', 'story13258', 'story13258_tc02')
    def test_02_p_update_default_nic_monitor(self):
        """
        @tms_id: litpcds_13258_tc2
        @tms_requirements_id: LITPCDS-13258
        @tms_title: Test default_nic_monitor property can be updated.
        @tms_description:
            Test to validate if the Mii attribute is affected
            when updating the default_nic_monitor property from
            netstat to mii. Verify the mii attribute is set
            correctly for service group resources with/ without
            network hosts.
            Test to validate if there are networks present with and without
            network hosts, and a user tries to change the default_nic_monitor
            to netstat from mii, we expect the network with no network hosts
            to have the mii attribute set to 0 and the networks with hosts
            present to have mii remain set to 0. During the plan we do a litpd
            restart for idempotency check, and verify the networks with no
            hosts present have the mii attribute set to 1. We then need to
            create a clustered service to ensure when we remove all network
            hosts that no service group goes into a faulted state. Add a
            network host back and then ensure all of the values for Mii are
            correct.
            This test covers "litpcds_13258_tc1"
        @tms_test_steps:
            @step:  Update the default_nic_monitor property to mii and verify
                    expected state of mii=0.
            @result: Item updated and expected state of mii=0.
            @step: Store network hosts config for cleanup. Remove network hosts
                   from a traffic2 network.
            @result: Network hosts stored and Items in removal state.
            @step: Create and run plan.
            @result: Plan executes successfully.
            @step: Verify resources on SGs have expected state of mii=1.
            @result: Resources have expected state of mii=1.
            @step: Update the default_nic_monitor property to netstat.
            @result: Item updated.
            @step: Verify the resources on SGs have mii=1.
            @result: Resources have expected state of mii=1.
            @step: Create Clustered Service.
            @result: Item created.
            @step: Create and run plan.
            @result: Plan executes.
            @step: Stop Plan at phase "Reconfigure NIC resource
                     Res_NIC_c1_eth4 on node1" and restart LITP.
            @result: Plan stops and LITP is restarted.
            @step: Re-create and run plan.
            @result: Plan executes successfully.
            @step: Verify the resources on the SGs have mii=0.
            @result: The resources on the SGs have mii=0.
            @step:  Update the default_nic_monitor property to mii.
            @result: Item updated.
            @step: Remove all network hosts from the model.
            @result: Items removed.
            @step: Add one network host to network(traffic2).
            @result: Item created.
            @step: Create and run plan.
            @result: Plan executes successfully.
            @step: Verify the resources on the SGs have mii=1
            @result: Resources are as expected.
            @step: Verify the resources on the SGs have mii=0.
            @result: Resources are as expected.
            @step: Cleanup after test completes.
            @result: Cleanup executes successfully.
        @tms_test_precondition: NA
        @tms_execution_type: Automated

        """

        self.log('info', '1. Update the default_nic_monitor to mii.')
        self.update_def_nic_monitor(self.mii)

        self.log('info', '2. Verify the resources on the service groups has '
                         'mii=0')
        self.check_mii_state(exp_state='0')

        self.log('info', '3. Store network hosts config for cleanup. '
                         'Remove network hosts from a traffic 2 network.')
        nethost_dicts_trfc2 = self.remove_net_hosts_from_model('traffic2')

        self.log('info', '4. Create and run plan.')
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE,
                                plan_timeout_mins=10)

        self.log('info', '5. Verify the resources on the service groups have '
                         'mii=1')
        self.check_mii_state(exp_state='1')

        self.log('info', '6. Update the default_nic_monitor property to '
                         'netstat')
        self.update_def_nic_monitor(self.netstat)

        self.log('info', '7. Verify the resources on the service groups have '
                         'mii=1')
        self.check_mii_state(exp_state='1')

        # Step 4: Create Clustered Service with status_command on service equal
        #  "ping -c 20 172.16.100.2 and ping -c 20 172.16.200.3"
        self.log('info', '8. Create Clustered Service.')
        fixtures = self.baseline(1, 1, 1, True, valid_rpm=2)

        cs_url = self.get_cs_conf_url(self.management_server,
                                      fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)
        if cs_url is None:
            apply_options_changes(
                fixtures,
                'vcs-clustered-service', 0, {'active': '1', 'standby': '1',
                                             'name': 'CS_13258_1',
                                             'node_list': '{0}'.format
                                             (','.join(self.node_ids))},
                overwrite=True)

            self.apply_cs_and_apps_sg(self.management_server,
                                      fixtures,
                                      self.rpm_src_dir)

        self.log('info', '9. Create and Run plan.')
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        phase_success = 'Reconfigure NIC resource "Res_NIC_c1_eth4" on ' \
                        'node "node1"'
        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 phase_success,
                                                 test_constants.
                                                 PLAN_TASKS_SUCCESS,
                                                 ignore_variables=False,
                                                 ),
                        'NIC resource was not updated successfully'
                        )

        self.log('info', '10. Stop plan at certain phase and restart LITP.')
        self.restart_litpd_service(self.management_server)

        self.log('info', '11. Re-create and run plan.')
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE,
                                plan_timeout_mins=10)

        self.log('info', '12. Verify the resources on the service groups have '
                         'mii=0.')
        self.check_mii_state(exp_state='0')

        self.log('info', '13. Update default_nic_monitor to mii')
        self.update_def_nic_monitor(self.mii)

        self.log('info', '14. Remove all network hosts from the model.')
        nethosts_dict = self.remove_net_hosts_from_model(nuke_nets=True)

        self.log('info', '15. Add one network host to network(traffic2).')
        network_host_props = 'ip=172.16.200.130 network_name=traffic2'
        self.execute_cli_create_cmd(self.management_server,
                                    self.network_hosts_url[0] + '/nh23',
                                    'vcs-network-host',
                                    network_host_props)

        self.log('info', '16. Create and run plan.')
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE,
                                plan_timeout_mins=10)

        self.log('info', '17. Verify the resources on the service groups have'
                         ' mii=1.')
        self.check_mii_state(exp_state='1', sg_name='Grp_NIC_c1_eth4')

        self.log('info', '18. Verify the resources on the service groups have'
                         ' mii=0.')
        self.check_mii_state(exp_state='0')

        self.log('info', '19. Cleanup after test completes')
        self.execute_cli_remove_cmd(self.management_server,
                                    self.network_hosts_url[0] + '/nh23',
                                    expect_positive=True, add_to_cleanup=False)
        self.update_def_nic_monitor(self.netstat)
        self._create_net_hosts(nethosts_dict)
        self._create_net_hosts(nethost_dicts_trfc2)
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE,
                                plan_timeout_mins=10)

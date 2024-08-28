"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     November 2015
@author:    Boyan Mihovski
@summary:   Integration
            Agile: STORY-8558
"""

import os
from litp_generic_test import GenericTest, attr
from test_constants import PLAN_TASKS_SUCCESS, PLAN_COMPLETE
from vcs_utils import VCSUtils
from generate import load_fixtures, generate_json, apply_options_changes

STORY = '8558'


class Story8558(GenericTest):
    """
    LITPCDS-8558:
    I can create more than 1 service within an applications collection of a
        vcs-clustered-service.
    I can specify a dependency between service items, once applied these
        will be dependent VCS Application Resources
        within the VCS Service Group.
    I can create up to a maximum of 10 service items within the applications
        collection.
    If I try to enable for a vcs-clustered-service with properties other than
        active=1 standby=1 then a validation error should be reported
        (support for FO Service Group Only).
    """

    def setUp(self):
        super(Story8558, self).setUp()
        # specify test data constants
        self.management_server = self.get_management_node_filename()
        self.vips_nets = self.select_non_mgmt_hb_network()
        self.vcs = VCSUtils()
        # Location where RPMs to be used are stored
        # Location where RPMs to be used are stored
        self.rpm_src_dir = (os.path.dirname(
            os.path.realpath(__file__)) + '/rpm-out/dist/')
        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.management_server,
                                         '/deployments', 'vcs-cluster')[-1]
        self.cluster_id = self.vcs_cluster_url.split('/')[-1]

        self.nodes_urls = self.find(self.management_server,
                                    self.vcs_cluster_url,
                                    'node')
        self.node_flnmes = self.get_managed_node_filenames()
        node_ids = [node.split('/')[-1] for node in self.nodes_urls]

        _json = generate_json(to_file=False, story=STORY,
                              vcs_length=1,
                              app_length=3,
                              hsc_length=3,
                              vip_length=1
                              )
        self.fixtures = load_fixtures(
            STORY, self.vcs_cluster_url, self.nodes_urls, input_data=_json)
        apply_options_changes(
            self.fixtures,
            'vcs-clustered-service', 0, {'active': '1', 'standby': '1',
                                         'name': 'CS_8558_1',
                                         'node_list': '{0}'.
                                         format(','.join(node_ids))},
            overwrite=True)
        apply_options_changes(
            self.fixtures,
            'vip', 0, {'network_name': '{0}'.format(self.vips_nets[0]),
                       'ipaddress': '2001:1100:82a1:0103:8558::1/64'},
            overwrite=True)
        apply_options_changes(
            self.fixtures,
            'ha-service-config', 0, {'service_id': 'APP_8558_1',
                                     'dependency_list': self.fixtures
                                     ['service'][1]['id'] +
                                     ',' + self.fixtures['service'][2]['id']},
            overwrite=True)
        apply_options_changes(
            self.fixtures,
            'ha-service-config', 1, {'service_id': 'APP_8558_2',
                                     'dependency_list': self.fixtures
                                     ['service'][2]['id']},
            overwrite=True)

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story8558, self).tearDown()

    def select_non_mgmt_hb_network(self):
        """
        Finds a network name which can be
        used for create/update tasks in other tests.
            (mgmt and hb networks are excluded)
        """
        # find non-mgmt/non hb network
        net_name = []
        network_urls = self.find(self.management_server,
                                 "/infrastructure", "network")
        for url in network_urls:
            net_props = self.get_props_from_url(self.management_server, url)
            if 'mgmt' not in net_props['name'] \
                    and 'hb' not in net_props['name']:
                net_name.append(net_props['name'])
        return net_name

    def get_res_deps(self, cs_name, app_ids):
        """
        Function to retrieve a CS resources dependencies from VCS.

        Args:
            - cs_name (str): CS group name.
            - app_ids (list): APP ids which belong to cs_name.

        Returns:
            - deps_list (list): CS group resources dependencies retrieved
                via VCS command.
        """
        deps_list = []
        cs_res_names = \
            self.vcs.generate_applications_resource_name(cs_name,
                                                         self.cluster_id,
                                                         app_ids)
        for res in cs_res_names:
            cmd_arg = '-dep {0} | awk "NR > 1"'.format(res)
            hares_cmd = self.vcs.get_hares_cmd(cmd_arg)
            stdout, _, _ = self.run_command(self.node_flnmes[0],
                                            hares_cmd,
                                            su_root=True,
                                            default_asserts=True)
            deps_list.append([' '.join(i.split()) for i in stdout])
            # check resources online state
            check_online_arg = \
                ('-state {0} -sys {1}'.
                 format(res, self.get_node_filename_from_url(self.
                                                             management_server,
                                                             self.nodes_urls[0]
                                                             )
                        ))
            hares_cmd = self.vcs.get_hares_cmd(check_online_arg)
            stdout, _, _ = self.run_command(self.node_flnmes[0],
                                            hares_cmd,
                                            su_root=True,
                                            default_asserts=True)
            self.assertEqual('ONLINE', stdout[0])
        return deps_list

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
            std_out, _, _ = self.run_command(node_vpath, hasys_cmd,
                                             su_root=True,
                                             default_asserts=True)
            self.assertEqual('{0} SysState RUNNING'.format(node_hostname),
                             ' '.join(std_out[1].split()))
            nodes.append(node_vpath)
        # Check main.cf is read only
        haclus_cmd = \
            self.vcs.get_haclus_cmd('-display | grep -i \'readonly\'')
        std_out, _, _ = self.run_command(nodes[0], haclus_cmd,
                                         su_root=True,
                                         default_asserts=True)
        self.assertEqual('ReadOnly 1', ' '.join(std_out[0].split()))
        # Check main.cf is valid
        haclus_cmd = self.vcs.validate_main_cf_cmd()
        std_out, _, _ = self.run_command(nodes[0], haclus_cmd,
                                         su_root=True, default_asserts=True)
        self.assertEqual([], std_out)
        # Check cluster is running
        cluster_name = self.vcs_cluster_url.split('/')[-1]
        haclus_cmd = self.vcs.get_haclus_cmd('-state {0}'.
                                             format(cluster_name))
        std_out, _, _ = self.run_command(nodes[0], haclus_cmd,
                                         su_root=True, default_asserts=True)
        self.assertEqual('RUNNING', std_out[0])

    @attr('all', 'non-revert', 'story8558',
          'story8558_tc04', 'cdb_priority1')
    def test_04_p_vcs_cs_dep_list_1_cs_failover(self):
        """
        @tms_id: litpcds_8558_tc4
        @tms_requirements_id: LITPCDS-8558
        @tms_title: Specify and deploy a vcs-clustered-service
        containing multiple servers
        @tms_description:
        To ensure that it is possible to specify, and deploy,
        a vcs-clustered-service containing multiple srvs, in this case3
        Below a vcs-clustered-service of configuration active=1 standby=1.
        Create apps dependencies and check them with ha_res command
        @tms_test_steps:
        @step:  Create one CS group with three services with dependencies
        @result: items created
        @step: create and run plan
        @result: plan is running
        @step: service litpd restart when plan is runing
        @result: plan stops
        @step: Manually delete resources and service groups to re-create plan
        @result:  service groups deleted
        @step: crete and run plan
        @result: plan executes successfully:
        @result: all packages,ha-service-config properties
         and vcs-clustered-service have been deployed
        @result:VCS groups and resources modelled correctly
        @tms_test_precondition:N/A
        @tms_execution_type: Automated
        """
        cs_url = self.get_cs_conf_url(self.management_server,
                                      self.fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)

        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            self.apply_cs_and_apps_sg(self.management_server,
                                      self.fixtures,
                                      self.rpm_src_dir)
            # This section of the test sets up the model and creates the plan
            self.execute_cli_createplan_cmd(self.management_server)
            self.execute_cli_runplan_cmd(self.management_server)
            self.execute_cli_showplan_cmd(self.management_server)

            phase_9_success = ('Create application resource '
                               '"Res_App_c1_CS_8558_1_APP_8558_2" for VCS '
                               'service group "Grp_CS_c1_CS_8558_1"')
            self.assertTrue(self.wait_for_task_state(self.management_server,
                                                     phase_9_success,
                                                     PLAN_TASKS_SUCCESS,
                                                     False),
                            'App resource is not created'
                            )
            self.restart_litpd_service(self.management_server)

            # Manually delete resources and service groups to re-create plan
            # with no errors
            self.reset_vcs_sg_after_idep(STORY, self.node_flnmes[0])

            # create/run plan after plan stopped
            self.run_and_check_plan(self.management_server,
                                    PLAN_COMPLETE, 6)
            # check main vcs attributes after stopped plan
            self.vcs_health_check()

            cs_url = self.get_cs_conf_url(self.management_server,
                                          self.fixtures['service']
                                          [0]['parent'],
                                          self.vcs_cluster_url)
        # Determine if all packages have been deployed on
        # the nodes in the cluster
        for pkg in [self.fixtures['service'][0]['package_id'],
                    self.fixtures['service'][1]['package_id'],
                    self.fixtures['service'][2]['package_id']]:
            for node in self.node_flnmes:
                self.assertTrue(self.check_pkgs_installed(node, [pkg]),
                                'The packages are not present in target node')
        # check resources deps from vcs
        res_deps_list = [
            ['Grp_CS_c1_CS_8558_1 Res_App_c1_CS_8558_1_APP_8558_1 Res_App_c1_'
             'CS_8558_1_APP_8558_3', 'Grp_CS_c1_CS_8558_1 Res_App_c1_CS_8558_'
             '1_APP_8558_1 Res_App_c1_CS_8558_1_APP_8558_2'],
            ['Grp_CS_c1_CS_8558_1 Res_App_c1_CS_8558_1_APP_8558_1 Res_App_c1_'
             'CS_8558_1_APP_8558_2', 'Grp_CS_c1_CS_8558_1 Res_App_c1_CS_8558_'
             '1_APP_8558_2 Res_App_c1_CS_8558_1_APP_8558_3'],
            ['Grp_CS_c1_CS_8558_1 Res_App_c1_CS_8558_1_APP_8558_1 Res_App_c1_'
             'CS_8558_1_APP_8558_3', 'Grp_CS_c1_CS_8558_1 Res_App_c1_CS_8558_1'
             '_APP_8558_2 Res_App_c1_CS_8558_1_APP_8558_3',
             'Grp_CS_c1_CS_8558_1 Res_App_c1_CS_8558_1_APP_8558_3 Res_IP_c1_'
             'CS_8558_1_traffic1_1']
                         ]
        res_deps = self.get_res_deps(self.fixtures['service'][0]['parent'],
                                     [self.fixtures['service'][0]['id'],
                                      self.fixtures['service'][1]['id'],
                                      self.fixtures['service'][2]['id']])
        self.assertEqual(res_deps_list, res_deps)

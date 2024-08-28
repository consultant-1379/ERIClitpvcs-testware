"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     April 2016
@author:    Ciaran Reilly, James Maher
@summary:   Integration Tests
            Agile: STORY-107501
"""
import os
from redhat_cmd_utils import RHCmdUtils
from litp_generic_test import GenericTest, attr
from test_constants import PLAN_COMPLETE, PLAN_TASKS_SUCCESS
from vcs_utils import VCSUtils
from generate import load_fixtures, generate_json, apply_options_changes, \
    apply_item_changes


STORY = '107501'


class Story107501(GenericTest):
    """
    TORF-107501:
        Description:
            As a LITP User I want to order the creation and onlining
            of VCS Service Group for an initial installation so that
            I can ensure a critical service is running before
            dependent services

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
        super(Story107501, self).setUp()
        self.management_server = self.get_management_node_filename()
        self.vcs = VCSUtils()
        # Location where RPMs to be used are stored
        self.rpm_src_dir = (os.path.dirname(
            os.path.realpath(__file__)) + '/rpm-out/dist/')
        self.rh_cmd = RHCmdUtils()

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
        self.nodes_to_expand = list()

    def baseline(self, vcs_len, app_len, hsc_len, cleanup=False,
                 valid_rpm=1, vcs_cluster_url=''):
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

        _json = generate_json(to_file=True, story=STORY,
                              vcs_length=vcs_len,
                              app_length=app_len,
                              hsc_length=hsc_len,
                              add_to_cleanup=cleanup,
                              valid_rpm=valid_rpm)

        if vcs_cluster_url == '':
            return load_fixtures(STORY, self.vcs_cluster_url,
                                 self.nodes_urls, input_data=_json)
        else:
            return load_fixtures(STORY, vcs_cluster_url,
                                 self.nodes_urls, input_data=_json)

    def _add_new_cluster(self):
        """
        Description:
            This Method performs an initial deployment of a VCS Cluster

        Steps:
            1. Create New VCS Cluster
            2. Expand cluster with new node
            3. Create two new cluster service in c2 with initial/ dependency
            list present
        """
        vcs_cluster_url = self.find(self.management_server, '/deployments',
                                    'cluster', False)[0] + '/c2'
        vcs_cluster_props = 'cluster_type=sfha cluster_id=2 ' \
                            'low_prio_net=mgmt llt_nets=hb1,hb2 ' \
                            'cs_initial_online=on app_agent_num_threads=2'
        self.nodes_to_expand.append("node2")
        self.nodes_to_expand.append("node3")

        # Step 1: Create New Cluster 'C2'
        self.execute_cli_create_cmd(self.management_server, vcs_cluster_url,
                                    'vcs-cluster',
                                    vcs_cluster_props,
                                    add_to_cleanup=False)

        # Step 2: Expand new cluster with two new nodes
        self.execute_expand_script(self.management_server,
                                   'expand_cloud_c2_mn2.sh')
        self.execute_expand_script(self.management_server,
                                   'expand_cloud_c2_mn3.sh')

        # Step 3: Create two new cluster services in c2 with initial/
        # dependency list present
        fixtures = self.baseline(2, 2, 2, vcs_cluster_url=vcs_cluster_url)

        apply_options_changes(
            fixtures,
            'vcs-clustered-service', 0, {'active': '1', 'standby': '1',
                                         'name': 'CS_107501_1',
                                         'initial_online_dependency_list':
                                         'CS_107501_2',
                                         'node_list': 'n2,n3'},
            overwrite=True)

        apply_options_changes(
            fixtures,
            'vcs-clustered-service', 1, {'active': '1', 'standby': '1',
                                         'name': 'CS_107501_2',
                                         'node_list': 'n3,n2'},
            overwrite=True)

        apply_item_changes(fixtures, 'ha-service-config', 1,
                           {'parent': "CS_107501_2"})

        apply_item_changes(fixtures, 'service', 1,
                           {'parent': "CS_107501_2",
                            'destination': vcs_cluster_url +
                            '/services/CS_107501_2/applications/APP_107501_2'})

        apply_item_changes(fixtures, 'ha-service-config', 1,
                           {'vpath': vcs_cluster_url +
                            '/services/CS_107501_2/ha_configs/HSC_107501_2'})

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

    @attr('all', 'non-revert', 'story107501', 'story107501_tc01')
    def test_01_p_ordered_dep_list_idemp(self):
        """
        @tms_id: torf_107501_tc01
        @tms_requirements_id: TORF-107501
        @tms_title: ordered dependency list idempotent
        @tms_description:
        Test to verify that SGs can be created with
        initial_online_dependency_list defined and that the
        SGs come online in the correct order.
        @tms_test_steps:
        @step: Create 3 cluster services with
        initial_online_dependency/dependency list
        @result: items created
        @step: create and run plan
        @result: plan is tuning
        @step: execute litpd restart
        @result: litp restarts
        @step: create and run plan
        @result:  plan executes successfully
        @result:the cluster services come online is accordance with the
        initial_online_dependency and dependency list
        @step: Update 2 cluster services items initial_online_dependency_list
        @result: items updated
        @step: remove 1 cluster services
        @result: item in forremoval state
        @step: remove 2 services
        @result: items in forremoval state
        @step: create and run plan
        @result: plan executes successfully
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """

        plan_timeout_mins = 5

        # Step1:Create 3 CS with and
        # initial_online_dependency/dependency list
        # CS1 has initial dep on CS2 and a dep on CS3
        # CS2 has initial dep on CS3
        # CS3 has no dep
        fixtures = self.baseline(3, 3, 3, False)

        cs_url = self.get_cs_conf_url(self.management_server,
                                      fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)

        dep_check = ['Bring VCS service group "Grp_CS_c1_CS_107501_3"',
                     'Bring VCS service group "Grp_CS_c1_CS_107501_2"',
                     'Bring VCS service group "Grp_CS_c1_CS_107501_1"']

        if cs_url is None:
            apply_options_changes(
                fixtures,
                'vcs-clustered-service', 0, {'active': '1', 'standby': '1',
                                             'name': 'CS_107501_1',
                                             'initial_online_dependency_list':
                                             'CS_107501_2',
                                             'node_list': '{0}'
                                             .format(','.join(self.node_ids)),
                                             'dependency_list': 'CS_107501_3'},
                overwrite=True)

            apply_options_changes(
                fixtures,
                'vcs-clustered-service', 1, {'active': '2', 'standby': '0',
                                             'name': 'CS_107501_2',
                                             'initial_online_dependency_list':
                                             'CS_107501_3',
                                             'node_list': '{0}'
                                             .format(','.join(self.node_ids))},
                overwrite=True)

            apply_item_changes(
                fixtures,
                'ha-service-config', 1, {'parent': "CS_107501_2",
                                         'vpath': self.vcs_cluster_url +
                                                  '/services/CS_107501_2/'
                                                  'ha_configs/HSC_107501_2',
                                         })

            apply_item_changes(fixtures, 'service', 1,
                           {'parent': "CS_107501_2",
                            'destination': self.vcs_cluster_url +
                            '/services/CS_107501_2/applications/APP_107501_2'})

            apply_options_changes(
                fixtures,
                'vcs-clustered-service', 2, {'active': '1', 'standby': '1',
                                             'name': 'CS_107501_3',
                                             'node_list': '{0}'
                                             .format(','.join(self.node_ids))},

                overwrite=True)

            apply_item_changes(
                fixtures,
                'ha-service-config', 2, {'parent': "CS_107501_3",
                                         'vpath': self.vcs_cluster_url +
                                                  '/services/CS_107501_3/'
                                                  'ha_configs/HSC_107501_3',
                                         })
            apply_item_changes(fixtures, 'service', 2,
                           {'parent': "CS_107501_3",
                            'destination': self.vcs_cluster_url +
                            '/services/CS_107501_3/applications/APP_107501_3'})

            self.apply_cs_and_apps_sg(self.management_server,
                                      fixtures,
                                      self.rpm_src_dir)

            # Step 2 - Create/Run plan
            self.execute_cli_createplan_cmd(self.management_server)
            self.execute_cli_runplan_cmd(self.management_server,
                                         add_to_cleanup=False)
            # Step 3
            # Run litpd restart (idpempotency) after CS3 brought online
            # If CS3 is not onlined first, tc will fail.
            self.assertTrue(self.wait_for_task_state(self.management_server,
                                                     dep_check[0],
                                                     PLAN_TASKS_SUCCESS,
                                                     ignore_variables=False),
                            'SG not brought on line in correct order'
                            )
            self.restart_litpd_service(self.management_server)
            # Step 4
            # Create/ Run plan again
            self.execute_cli_createplan_cmd(self.management_server)
            self.execute_cli_runplan_cmd(self.management_server,
                                         add_to_cleanup=False)
            # Step 5
            # Verify the CSs come online is accordance with the
            # initial_online_dependency and dependency list
            # Check after CS3 came online(Step 3),that CS2
            # comes online next followed by CS1
            self.assertTrue(self.wait_for_task_state(self.management_server,
                                                     dep_check[1],
                                                     PLAN_TASKS_SUCCESS,
                                                     ignore_variables=False),
                            'SG not brought on line in correct order'
                            )
            self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 dep_check[2],
                                                 PLAN_TASKS_SUCCESS,
                                                 ignore_variables=False),
                            'SG not brought on line in correct order'
                            )
            self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 plan_timeout_mins))
        # Step 6: Update CS  ordering list
        # CS1 initial_online_dependency_list set to ""
        self.execute_cli_update_cmd(self.management_server,
                                    fixtures['vcs-clustered-service']
                                    [0]['vpath'],
                                    'initial_online_dependency_list=""')
        # CS2 initial_online_dependency_list set to ""
        self.execute_cli_update_cmd(self.management_server,
                                    fixtures['vcs-clustered-service']
                                    [1]['vpath'],
                                    'initial_online_dependency_list=""')
        # Step 7 : Remove CS from model
        self.execute_cli_remove_cmd(self.management_server,
                                    fixtures['vcs-clustered-service']
                                    [1]['vpath'],
                                    add_to_cleanup=False)
        self.execute_cli_remove_cmd(self.management_server,
                                    fixtures['service'][1]['package_vpath'],
                                    add_to_cleanup=False)
        self.execute_cli_remove_cmd(self.management_server,
                                    fixtures['service'][1]['vpath'],
                                    add_to_cleanup=False)
        # Step 8: Create/ Run plan
        self.run_and_check_plan(self.management_server,
                                PLAN_COMPLETE,
                                plan_timeout_mins=10, add_to_cleanup=False)
        # Step 9: Verify the initial_online_dependency_list
        # and CS2 is removed form model
        init_on_dep = self.get_props_from_url(
        self.management_server, fixtures['vcs-clustered-service'][0]['vpath'],
            filter_prop='initial_online_dependency_list')
        self.assertEqual(init_on_dep, '')

        vcs_cluster_url = self.find(self.management_server,
                                    '/deployments', 'vcs-clustered-service')
        self.assertFalse(self.is_text_in_list
                         (fixtures['vcs-clustered-service'][1]['vpath'],
                          vcs_cluster_url),
                         "SG not removed")

    @attr('all', 'expansion', 'story107501', 'story107501_tc09')
    def test_09_p_initial_dep_list_at_initial_install(self):
        """
        @tms_id: torf_107501_tc09
        @tms_requirements_id: TORF-107501
        @tms_title: initial dependency list at initial install
        @tms_description:
        Test to verify main use case at initial installation that service
        groups start up in correct order at initial installation
        @tms_test_steps:
        @step: Create vcs-cluster
        @result: items created
        @step: Create two service groups under the new cluster.
        @result: item created
        @step: create and run plan
        @result: plan executes successfully
        @result: service groups come online in correct order
        @step: create snapshot
        @result: snapshot created
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        mco_command = "mco puppet runonce"
        timeout_mins = 90
        dep_check = ['Create VCS service group "Grp_CS_c2_CS_107501_2"',
                     'Create VCS service group "Grp_CS_c2_CS_107501_1"']

        # Step 1: Create new cluster with two nodes
        # Step 2: Create two service groups under the new cluster
        self._add_new_cluster()

        # Step 3: Create/ Run plan
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        # Step 4: Validate the service groups are brought online in correct
        # order
        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 dep_check[0],
                                                 PLAN_TASKS_SUCCESS,
                                                 ignore_variables=False,
                                                 timeout_mins=timeout_mins,
                                                 seconds_increment=1),
                        'SG not brought on line in correct order'
                        )
        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 dep_check[1],
                                                 PLAN_TASKS_SUCCESS,
                                                 ignore_variables=False,
                                                 timeout_mins=timeout_mins,
                                                 seconds_increment=1),
                        'SG not brought on line in correct order'
                        )

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))
        self.run_command(self.management_server, mco_command)

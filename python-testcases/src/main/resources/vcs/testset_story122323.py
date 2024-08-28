"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     June 2016
@author:    Ciaran Reilly
@summary:   Integration Tests
            Agile: STORY-122323
"""
import os
from redhat_cmd_utils import RHCmdUtils
from litp_generic_test import GenericTest, attr
from test_constants import PLAN_COMPLETE, PLAN_TASKS_SUCCESS, PP_PKG_REPO_DIR
from vcs_utils import VCSUtils
from generate import load_fixtures, generate_json, apply_options_changes

STORY = '122323'
RPM_SRC_DIR = os.path.dirname(os.path.realpath(__file__)) + '/test_lsb_rpms/'


class Story122323(GenericTest):
    """
    LITPCDS-122323:
        Update LITP to allow a service to be identified as critical when
        there is more than 2 nodes in the cluster

    Acceptance Criteria:
        1 . I can create a vcs-cluster item with its critical_service property
        defined where the number of nodes in the cluster is greater than 2.
        2. I can update a vcs-cluster item with its critical_service property
        defined where the number of nodes in the cluster is greater than 2.
        3. On a cluster greater than 2 nodes, if a critical_service is defined
        then for that critical service I should see the standby node locked
        before the active node.
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
        super(Story122323, self).setUp()
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

        self.nodes_to_expand = list()
        for nodes in ["node2", "node3", "node4"]:
            self.nodes_to_expand.append(nodes)

    def baseline(self, vcs_len, app_len, hsc_len, cleanup=False):
        """
        Description:
            Runs initially with every test case to set up litp model
            with vcs/app and ha service parameters
        Parameters:
            vcs_len: (int) Number of VCS CS
            app_len: (int) Number of applications
            hsc_len: (int) Number of HA Service Configs
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

    def _create_new_service(self, cs_url):
        """
        Method to create new service and inherit package onto detected FO CS
        found in the model
        :param cs_url: (str) URL for cluster service
        :return: Nothing
        """

        lsb_rpm = 'EXTR-lsbwrapper-122323-2-1.1.rpm'

        self.copy_file_to(self.management_server, RPM_SRC_DIR + lsb_rpm,
                          '/tmp', root_copy=True, add_to_cleanup=False)

        self.execute_cli_import_cmd(self.management_server, '/tmp/' + lsb_rpm,
                                    PP_PKG_REPO_DIR)

        self.execute_cli_create_cmd(self.management_server,
                                    '/software/services/APP_122323_2',
                                    'service',
                                    props='service_name="test-lsb-122323-2"',
                                    add_to_cleanup=False)
        self.execute_cli_create_cmd(self.management_server,
                                    '/software/items/EXTR-lsbwrapper122323',
                                    'package',
                                    props='name=EXTR-lsbwrapper-122323-2',
                                    add_to_cleanup=False)
        self.execute_cli_inherit_cmd(self.management_server,
                                     cs_url + '/applications/APP_122323_2',
                                     '/software/services/APP_122323_2',
                                     add_to_cleanup=False)
        self.execute_cli_inherit_cmd(self.management_server,
                                     '/software/services/APP_122323_2/'
                                     'packages/EXTR-lsbwrapper122323',
                                     '/software/items/EXTR-lsbwrapper122323',
                                     add_to_cleanup=False)
        self.execute_cli_create_cmd(self.management_server, cs_url +
                                    '/ha_configs/APP_122323_2',
                                    'ha-service-config',
                                    props='service_id="APP_122323_2"',
                                    add_to_cleanup=False)

    @attr('all', 'expansion', 'story122323', 'story122323_tc01')
    def test_01_p_update_litp_model_with_crit_serv_to_have_mult_nodes(self):
        """
        @tms_id: torf_122323_tc_01
        @tms_requirements_id: TORF-122323
        @tms_title:
            test_01_p_update_litp_model_with_crit_serv_to_have_mult_nodes
        @tms_description: Verify that the model can be updated with additional
        nodes whilst having a FO CS that is a critical service on the cluster

        @tms_test_steps:
            @step: Define FO service group in model, and list as a
             critical service
            @result: FO service group is created and listed as a critical
            service on the cluster
            @step: Expand the litp model to have additional nodes
            (number of nodes equal to 4)
            @result: Litp model is expanded to have additional nodes
            @step: Create/ Run Plan
            @result: Plan is created and run
            @step: Wait for successful completion
            @result: Plan completes successfully
            @step: Assert the node count in the litp model
            @result: Node count is equal to 4 in the litp model

        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """
        # Note: The way Vapps are configured means we always start with a one
        # node cluster, therefore the model is expanded to three nodes and
        # FO SG is created and listed as a critical service in the same plan

        timeout_mins = 60
        nodes = ['n1', 'n2', 'n3', 'n4']
        expand_list = []
        node_list = self.find_children_of_collect(self.management_server,
                                                  self.vcs_cluster_url +
                                                  '/nodes/',
                                                  'node',
                                                  find_all_collect=True)
        for items, node in zip(node_list, nodes):
            expand_list.append((
                items.split(self.vcs_cluster_url + '/nodes/')[1], node)[0])
        # Check if model is expanded to 4 nodes if not proceed with test
        if sorted(expand_list) != sorted(nodes):
            self._four_node_expansion()

        # Create a FO service group that will be named as a critical service
        # on the cluster level
        # Step 1: Define FO service group in model, and list as a
        # critical service
        fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1)
        list_of_cs_names = [fixtures['service'][0]['parent']]

        apply_options_changes(fixtures,
                              'vcs-clustered-service', 0,
                              {'active': '1', 'standby': '1',
                               'name': 'CS_122323_1',
                               'node_list': 'n1,n2'},
                              overwrite=True)

        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    props="critical_service={0}"
                                    .format(list_of_cs_names[0]))

        self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                  self.rpm_src_dir)

        # Step 3: Create/ Run plan
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        # Step 4: Wait for successful completion
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        # Step 5: Assert the node count in the litp model
        for items, node in zip(node_list, nodes):
            self.assertEqual(items.split(self.vcs_cluster_url + '/nodes/')[1],
                             node)

    @attr('all', 'expansion', 'story122323', 'story122323_tc03')
    def test_03_p_update_3_node_cluster_sg_to_critical_serv_idemp(self):
        """
        @tms_id: torf_122323_tc_03
        @tms_requirements_id: TORF-122323
        @tms_title: test_03_p_update_3_node_cluster_sg_to_critical_serv_idemp
        @tms_description: Verify that a user can update their sg to critical
        service on a 3 node cluster

        @tms_test_steps:
            @step: Define FO service group in model with 3 nodes available
            @result: FO service group defined in model
            @step: Create/ Run Plan
            @result: Plan created and run to completion
            @step: Update cluster for FO SG to be a critical service
            @result: FO SG is listed as a critical service
            @step: Create new service with package for lock task in plan
            @result: New service is created and inherited onto SG to create
            lock task
            @step: Create/ Run Plan
            @result: Plan is created and run
            @step: Assert lock task are in correct order
            @result: Lock tasks are in correct order starting with node 2
            @step: After node 1 lock task perform a litpd restart
            @result: litp is restarted
            @step: Create/ Run plan
            @result: Plan is created and run to completion

        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        # Note: this test dynamically checks if the model has four nodes and
        # a FO cluster service already. If not the litp model will be expanded
        # and a FO service group will be created

        nodes = ['n1', 'n2', 'n3', 'n4']
        expand_list = []
        timeout_mins = 60
        task_desc = 'Lock VCS on node "{0}"'

        # Pre-condition is to have a FO clustered service on a three node
        # cluster, if the service or cluster does not have either. The test
        # will take this into account.
        # Step 1: Define FO service group in model with 3 nodes available
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
        # If the cluster has three nodes then check if there is a suitable
        # cluster service available
        if sorted(expand_list) == sorted(nodes):
            vcs_sgs = self.get_matching_vcs_cs_in_model(self.management_server,
                                                        apps=1, ha_srv_cfgs=1,
                                                        cs_props_dict={
                                                            'active': '1',
                                                            'standby': '1',
                                                            'node_list':
                                                                'n1,n2'})
            if vcs_sgs == []:
                fixtures = self.baseline(vcs_len=1, app_len=1, hsc_len=1)
                cs_url = \
                    self.vcs_cluster_url + fixtures['service'][0]['parent']
                apply_options_changes(fixtures,
                                      'vcs-clustered-service', 0,
                                      {'active': '1', 'standby': '1',
                                       'name': 'CS_122323_1',
                                       'node_list': 'n1,n2'},
                                      overwrite=True)
                self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                          self.rpm_src_dir)
                # Step 2: Create/ Run plan
                self.execute_cli_createplan_cmd(self.management_server)
                self.execute_cli_showplan_cmd(self.management_server)
                self.execute_cli_runplan_cmd(self.management_server)
                self.assertTrue(
                    self.wait_for_plan_state(self.management_server,
                                             PLAN_COMPLETE,
                                             timeout_mins))
            else:
                cs_url = vcs_sgs[0]
        else:
            self._four_node_expansion()

        cs_name = self.get_props_from_url(self.management_server,
                                          cs_url, filter_prop='name')

        # Step 3: Update fo sg to be a critical service
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster_url,
                                    props="critical_service={0}"
                                    .format(cs_name))
        # Add new service and packages to cause node lock
        self._create_new_service(cs_url)

        # Step 4: Create/ Run Plan
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        # Step 5: Assert Lock tasks are in correct order
        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 task_desc.format("node2"),
                                                 PLAN_TASKS_SUCCESS,
                                                 ignore_variables=False),
                        'Lock task did not happen in correct order')
        self.assertTrue(self.wait_for_task_state(self.management_server,
                                                 task_desc.format("node1"),
                                                 PLAN_TASKS_SUCCESS,
                                                 ignore_variables=False),
                        'Lock task did not happen in correct order')

        # Step 6: Stop plan at node 1 lock task litpd restart
        self.restart_litpd_service(self.management_server)

        # Step 7: Create/ Run Plan
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

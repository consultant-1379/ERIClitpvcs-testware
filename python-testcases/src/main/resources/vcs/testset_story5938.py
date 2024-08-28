"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     Nov 2014, April 2016
@author:    Pat Bohan, Ciaran Reilly
@summary:   Integration tests for testing litpcds-5938
            Agile:
"""

from litp_generic_test import GenericTest, attr
from vcs_utils import VCSUtils
import re
from redhat_cmd_utils import RHCmdUtils
from generate import load_fixtures, generate_json, apply_options_changes, \
    apply_item_changes
import os
from test_constants import PLAN_TASKS_SUCCESS, PLAN_COMPLETE

STORY = '5938'


class Story5938(GenericTest):
    """
    LITPCDS-5938
    As an application designer I want to set up dependencies between my VCS
    service groups so that I can control their start up order

    In VCS terminology if
        CS-X is dependent on CS-Y than
        CS-X is the parent group and CS-Y is the child group
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
        super(Story5938, self).setUp()

        self.model = self.get_model_names_and_urls()
        self.ms_node = self.model["ms"][0]["name"]
        self.list_managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.list_managed_nodes[0]
        self.vcs = VCSUtils()
        self.rh_os = RHCmdUtils()

        self.vcs_cluster_url = self.find(self.ms_node,
                                    "/deployments", "vcs-cluster")[-1]
        self.cluster_id = self.vcs_cluster_url.split("/")[-1]

        self.nodes_urls = self.find(self.ms_node,
                                    self.vcs_cluster_url, 'node')
        self.nodes_to_expand = list()
        self.list_of_cs_names = list()
        # Location where RPMs to be used are stored
        self.rpm_src_dir = (os.path.dirname(os.path.realpath(__file__)) +
                            '/rpm-out/dist/')

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
        super(Story5938, self).tearDown()

    def get_vcs_model_info(self):
        """
        Function that returns a dictionary all the vcs clustered service
        information from the LITP model
        """

        service_groups = []

        prop_dict = {}
        service_group = {}

        for cluster in self.model['clusters']:

            clus_servs = self.find(self.ms_node, cluster['url'],
                                   'vcs-clustered-service',
                                   assert_not_empty=False)
            for serv in clus_servs:
                # Check if this clustered service is a vm service
                vm_service = self.find(self.ms_node, serv, 'vm-service',
                                  assert_not_empty=False)
                # Ignore if VM service as it's tested in testset_vcs_vm.py
                if vm_service:
                    continue

                prop_dict['url'] = serv

                props = self.get_props_from_url(self.ms_node, serv)

                for prop in props:
                    prop_dict[prop] = props[prop]

                service_group['vcs-clustered-service'] = prop_dict

                prop_dict = {}

                service_groups.append(service_group)
                service_group = {}

        self.log("info", "Printing dict from get_vcs_model_info()")
        self._print_list(0, service_groups)
        self.log("info", "Finished printing dict")

        return service_groups

    def baseline(self, vcs_len, app_len, hsc_len, cleanup=False, valid_rpm=1):
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

        return load_fixtures(STORY, self.vcs_cluster_url, self.nodes_urls,
                             input_data=_json)

    def create_clust_services(self):
        """
        Method that creates three clustered services
        :return: Nothing
        """

        fixtures = self.baseline(3, 3, 3)

        # CS_1
        apply_options_changes(
            fixtures,
            'vcs-clustered-service', 0, {'active': '3', 'standby': '0',
                                         'name': 'CS_5938_1',
                                         'dependency_list': 'CS_5938_2,'
                                                            'CS_5938_3',
                                         'node_list': 'n1,n2,n3'},
            overwrite=True)

        # CS_2
        apply_options_changes(
            fixtures,
            'vcs-clustered-service', 1, {'active': '3', 'standby': '0',
                                         'name': 'CS_5938_2',
                                         'node_list': 'n1,n2,n3'},
            overwrite=True)

        apply_item_changes(
            fixtures,
            'ha-service-config', 1, {'parent': "CS_5938_2",
                                     'vpath': self.vcs_cluster_url +
                                              '/services/CS_5938_2/ha_configs'
                                              '/HSC_5938_2'})
        apply_item_changes(
            fixtures,
            'service', 1, {'parent': "CS_5938_2",
                           'destination': self.vcs_cluster_url +
                                          '/services/CS_5938_2/applications/'
                                          'APP_5938_2'})

        # CS_3
        apply_options_changes(
            fixtures,
            'vcs-clustered-service', 2, {'active': '1', 'standby': '1',
                                         'name': 'CS_5938_3',
                                         'dependency_list': 'CS_5938_2',
                                         'node_list': 'n1,n2'},
            overwrite=True)

        apply_item_changes(
            fixtures,
            'ha-service-config', 2, {'parent': "CS_5938_3",
                                     'vpath': self.vcs_cluster_url +
                                              '/services/CS_5938_3/ha_configs/'
                                              'HSC_5938_3'})

        apply_item_changes(
            fixtures,
            'service', 2, {'parent': "CS_5938_3",
                           'destination': self.vcs_cluster_url +
                                          '/services/CS_5938_3/applications/'
                                          'APP_5938_3'})

        self.apply_cs_and_apps_sg(self.ms_node, fixtures,
                                  self.rpm_src_dir)

        self.list_of_cs_names = [fixtures['service'][0]['parent'],
                                 fixtures['service'][1]['parent'],
                                 fixtures['service'][2]['parent']]

    def expand_model(self):
        """
        This Method is used to expand the LITP model using UTIL scripts
        supplied
        :return: Nothing
        """
        net_hosts_props = {'ip': '10.10.14.4',
                           'network_name': 'dhcp_network'}

        self.execute_expand_script(self.ms_node, 'expand_cloud_c1_mn2.sh',
                                   cluster_filename='192.168.0.42_4node.sh')
        self.execute_expand_script(self.ms_node, 'expand_cloud_c1_mn3.sh',
                                   cluster_filename='192.168.0.42_4node.sh')
        self.execute_expand_script(self.ms_node, 'expand_cloud_c1_mn4.sh',
                                   cluster_filename='192.168.0.42_4node.sh')

        self.execute_cli_create_cmd(self.ms_node, self.vcs_cluster_url +
                                    '/network_hosts/nh21', 'vcs-network-host',
                                    props='ip={0} network_name={1}'
                                    .format(net_hosts_props['ip'],
                                            net_hosts_props['network_name']))

        # Step 2: Create 3 clustered services with various dependencies
        self.create_clust_services()

    def _get_online_ordering_dependencies(self):
        """
        Method to determine the online ordering dependencies between
        vcs-clustered-services in the LITP Model. Returns a dict with parent
        and child CS
        """
        info = self.get_vcs_model_info()
        dep = {}
        for service in info:
            url = service['vcs-clustered-service']['url']
            if '11241' in url:
                continue
            key = url.split('/')[-1]
            if "dependency_list" in service['vcs-clustered-service']:
                value = [service['vcs-clustered-service']["dependency_list"]]
                value = [i.split(',') for i in value][0]
                dep.update({key: value})

        return dep

    @attr('all', 'non-revert', 'story5938', 'story5938_tc01')
    def test_01_p_verify_dependency_order(self):
        """
        @tms_id: litpcds_5938_tc01
        @tms_requirements_id: LITPCDS-5938
        @tms_title: test_01_p_verify_dependency_order
        @tms_description: Test case will verify that all the dependencies were
        set correctly in VCS. The VCS dependencies should be configured as:
        'online local soft' or 'online global soft'
        - online: The parent group must wait for the child group to be brought
                  online before it can start.
        - local: The parent group depends on the child group being online on
                 the same system.
        - global: An instance of the parent group depends on one or more
        instances of the child group being online on any system in the cluster.
        - soft: Specifies the minimum constraints while bringing parent and
        child groups online. The only constraint is that the child group must
        be online before the parent group is brought online.

        @tms_test_steps:
            @step: Verify that VCS is configured correctly using VCS commands
            @result: VCS Service group dependencies are configured as online,
                     local|global and soft.

        @tms_test_precondition: A 2 node LITP cluster is installed and service
                                groups deployed on both nodes
        @tms_execution_type: Automated
        """
        dep = self._get_online_ordering_dependencies()

        # verify that VCS is configured correctly
        for parent_cs in dep:
            parent_cs_grp = self.vcs.generate_clustered_service_name(parent_cs,
                                                             self.cluster_id)

            cmd = self.vcs.get_hagrp_cmd('-dep ' + parent_cs_grp)
            stdout, stderr, rc = self.run_command(self.primary_node, cmd,
                                                  su_root=True)
            self.assertEqual(0, rc)
            self.assertEqual([], stderr)

            for child_cs in dep[parent_cs]:
                child_cs_grp = \
                            self.vcs.generate_clustered_service_name(child_cs,
                                                               self.cluster_id)
                exp_reg_ex = parent_cs_grp + r'\s+' + child_cs_grp +\
                             r'\s+online\s+(global|local)\s+soft'
                exp_reg_ex_compiled = re.compile(exp_reg_ex)
                result = False

                for line in stdout:
                    if re.search(exp_reg_ex_compiled, line):
                        result = True
                self.assertTrue(result)

    # attr('pre-reg', 'non-revert', 'story5938', 'story5938_tc02')
    def obsolete_02_p_verify_dependency_order_after_node_locking(self):
        """
        This is a basic test that simply checks that the dependency parameter
        is either online local soft or online global soft. The order of the
        tests is defined so that this test runs after a test with a node lock.
        Keeping this test with a dependency on an earlier test, increases
        the complexity of the VCS KGB and is not justified.
        #tms_id: litpcds_5938_tc02
        #tms_requirements_id: LITPCDS-5938

        #tms_title: test_02_p_verify_dependency_order_after_node_locking
        #tms_description: This test assume the setup test has run successfully.
        It assumes that the node locking tests have also run.
        Test case will verify that all the dependencies were set correctly in
        VCS. The VCS dependencies should be configured as:
        'online local soft' or 'online global soft'
        - online: The parent group must wait for the child group to be brought
                  online before it can start.
        - local: The parent group depends on the child group being online on
                 the same system.
        - global: An instance of the parent group depends on one or more
        instances of the child group being online on any system in the cluster.
        - soft: Specifies the minimum constraints while bringing parent and
        child groups online. The only constraint is that the child group must
        be online before the parent group is brought online.

        #tms_test_steps:
            #step: Verify that VCS is configured correctly using VCS commands
            #result: VCS Service group dependencies are configured as online,
                     local|global and soft.

        #tms_test_precondition: A 2 node LITP cluster is installed and service
                                groups deployed on both nodes. Node lock/unlock
                                test cases have been executed successfully.
        #tms_execution_type: Automated
        """
        pass

    @attr('all', 'non-revert', 'expansion', 'story5938', 'story5938_tc20')
    def test_20_21_22_p_deps_on_expanded_services(self):
        """
        Description:
            Test to verify a user can have various configurations with
            dependencies between fail over and parallel clustered services
            that have gone through an expansion job, and the node_list
            attribute is equal to a four node cluster.

            Note: The node list attribute was previosuly validated in
            testset_story5167, but was moved here for optimisation.
            Old test case was named:
            test_04_p_expand_cs_two_to_three_nodes

        Steps:
            1. Expand Model to 4 node configuration
            2. Create 2, three node parallel (CS1, CS2) and 1, two node fail
            (CS3) over clustered services
            3. Make CS1 dependent on CS2 and CS3
            4. Make CS3 dependent on CS2
            5. Create/ Run plan
            6. Ensure dependency lists are justified

        Expected Result:
            Cluster Services come online in defined order
        """
        phase_check = 'Bring VCS service group "{0}" online'
        timeout_mins = 90
        nodes = ['n1', 'n2', 'n3', 'n4']
        expand_list = []
        # Step 1: Expand Model to 4 node configuration
        # Step 2: Create 2, three node parallel (CS1, CS2) and 1, two node fail
        # (CS3) over clustered services
        # Step 3. Make CS1 dependent on CS2 and CS3
        # Step 4. Make CS3 dependent on CS2

        # Check if the model already has four nodes configured, if not
        # proceed with expansion
        node_list = self.find_children_of_collect(self.ms_node,
                                                  self.vcs_cluster_url +
                                                  '/nodes/',
                                                  'node',
                                                  find_all_collect=True)
        for items, node in zip(node_list, nodes):
            expand_list.append((
                items.split(self.vcs_cluster_url + '/nodes/')[1], node)[0])

        if sorted(expand_list) == sorted(nodes):
            self.create_clust_services()
        else:
            self.expand_model()

        # Step 5: Create/ Run plan
        self.execute_cli_createplan_cmd(self.ms_node)
        self.execute_cli_showplan_cmd(self.ms_node)
        self.execute_cli_runplan_cmd(self.ms_node)

        cs_two_group_name = \
            self.vcs.generate_clustered_service_name(self.list_of_cs_names[1],
                                                     self.cluster_id)
        cs_three_group_name = \
            self.vcs.generate_clustered_service_name(self.list_of_cs_names[2],
                                                     self.cluster_id)

        # Step 6: Ensure dependency lists are justified
        self.assertTrue(self.wait_for_task_state(self.ms_node,
                                                 phase_check
                                                 .format(cs_two_group_name),
                                                 PLAN_TASKS_SUCCESS,
                                                 ignore_variables=False,
                                                 timeout_mins=timeout_mins,
                                                 seconds_increment=1),
                        'SG not brought on line in correct order'
                        )

        self.assertTrue(self.wait_for_task_state(self.ms_node,
                                                 phase_check
                                                 .format(cs_three_group_name),
                                                 PLAN_TASKS_SUCCESS,
                                                 ignore_variables=False,
                                                 timeout_mins=timeout_mins,
                                                 seconds_increment=1),
                        'SG not brought on line in correct order'
                        )

        self.assertTrue(self.wait_for_plan_state(self.ms_node,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        # Validate story 5167 test_04_p_expand_cs_two_to_three_nodes
        node_list = self.get_props_from_url(self.ms_node,
                                            self.vcs_cluster_url +
                                            '/services/' +
                                            self.list_of_cs_names[0],
                                            filter_prop='node_list')
        self.assertEqual(node_list, 'n1,n2,n3')

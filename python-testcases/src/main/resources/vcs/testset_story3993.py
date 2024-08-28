"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     June 2014
@author:    Pat Bohan
@summary:   Integration tests for testing VCS scenarios
            Agile:
"""

from litp_generic_test import GenericTest, attr
from vcs_utils import VCSUtils
import test_constants
import os
import re


class Story3993(GenericTest):
    """
    LITPCDS-3993
    As a LITP User I want the VCS plugin to provide a method of locking
    a node within the VCS cluster so that I can carry out upgrades safely
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
        super(Story3993, self).setUp()

        self.model = self.get_model_names_and_urls()
        self.ms_node = self.model["ms"][0]["name"]
        self.list_managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.list_managed_nodes[0]
        self.software_path = self.find(self.ms_node, '/software',
                                       'collection-of-software-item')[0]
        self.vcs = VCSUtils()
        self.traffic_networks = ["traffic1", "traffic2"]
        # Location where RPMs to be used are stored
        self.rpm_src_dir = \
            os.path.dirname(os.path.realpath(__file__)) + \
            "/test_lsb_rpms/"

        # Repo where rpms will be installed
        self.repo_dir_3pp = test_constants.PP_PKG_REPO_DIR

        self.vcs_cluster_url = self.model['clusters'][0]['url']
        self.cluster_id = self.vcs_cluster_url.split("/")[-1]
        self.nodes_urls = self.find(self.ms_node, self.vcs_cluster_url, "node")
        self.n1_items = self.find(self.ms_node, self.nodes_urls[0],
                                  'ref-collection-of-software-item')[0]
        self.n2_items = self.find(self.ms_node, self.nodes_urls[1],
                                  'ref-collection-of-software-item')[0]

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story3993, self).tearDown()

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

    def store_data_before_node_locking(self, info, hagrp_output,
                                       cluster_id):
        """
        Returns state of system before node locking is triggered

        Args: info (dict): LITP Model VCS Information.

              hagrp_output (array): Output from the hagrp -state  command

              cluster_id (str): id of the cluster in the model

        Returns:
            list_of_groups_types (dict): list of groups and whether they are
                                         parallel or failover

            list_of_active_cnt (dict): list of the groups and how many nodes
                                       they should be active on

            before_online_cnt (dict): list of groups and there actual state

            after_online_cnt (dict): list of groups and dummy state information

        """
        list_of_groups_types = {}
        list_of_active_cnt = {}
        before_online_cnt = {}
        after_online_cnt = {}
        # Loop through the list of clustered-service defined in LITP Model
        # and see which ones exist and Store all data before locking
        for clustered_service in info:
            cs_grp_name = \
                    self.vcs.generate_clustered_service_name(
                         clustered_service['vcs-clustered-service']['name'],
                         cluster_id)
            cnt = 0
            for line in hagrp_output:
                search_result = re.search(cs_grp_name +\
                                          r'\s+State\s+(\S+)\s+\|?([A-Z]+)\|?',
                                          line)
                if search_result:
                    node = search_result.group(1)
                    state = search_result.group(2)
                    # standby = 0 implies parallel clustered-service
                    # otherwise clustered-service is Failover
                    list_of_groups_types[cs_grp_name] =\
                        clustered_service['vcs-clustered-service']['standby']
                    # Current active count
                    list_of_active_cnt[cs_grp_name] =\
                        int(
                          clustered_service['vcs-clustered-service']['active'])

                    # If state is online find out how many are online
                    # the node field is used for failover clustered-services
                    # only, irrelevant for parallel
                    if state == 'ONLINE':
                        cnt = cnt + 1
                        before_online_cnt[cs_grp_name] = {'node': node,
                                                          'cnt': cnt}
                        after_online_cnt[cs_grp_name] = {'node': 'nodeXX',
                                                         'cnt': 0}

        return before_online_cnt, \
               after_online_cnt, \
               list_of_groups_types, \
               list_of_active_cnt

    def store_data_after_node_locking(self, info, hagrp_output,
                                      cluster_id,
                                      after_online_cnt):
        """
        Returns state of system before node locking is triggered

        Args: info (dict): LITP Model VCS Information

              hagrp_output (array): Output from the hagrp -state  command

              cluster_id(str): id of the cluster in the model

              after_online_cnt (dict): list of groups and dummy
                                       state information

        Returns:
            after_online_cnt (dict): list of groups and their state information
        """
        for clustered_service in info:
            cs_grp_name = \
                    self.vcs.generate_clustered_service_name(
                         clustered_service['vcs-clustered-service']['name'],
                         cluster_id)
            cnt = 0
            for line in hagrp_output:
                search_result = re.search(cs_grp_name +
                                          r'\s+State\s+(\S+)\s+\|?([A-Z]+)\|?',
                                          line)
                if search_result:
                    node = search_result.group(1)
                    state = search_result.group(2)
                    if state == 'ONLINE':
                        cnt = cnt + 1
                        after_online_cnt[cs_grp_name] = {'node': node,
                                                         'cnt': cnt}

        return after_online_cnt

    def create_package(self, pkg_name):
        """
        Creating a package under software.
        Args:
            pkg_name: Name of package that is to be created.
        """
        package_path = '{0}/{1}'.format(self.software_path, pkg_name)
        props = 'name={0}'.format(pkg_name)
        self.execute_cli_create_cmd(
            self.ms_node, package_path, 'package', props, add_to_cleanup=False)

    def import_package_to_3pp_dir(self, pkg_to_add):
        """
        Importing package to 3pp directory, this is to trigger node lock.
        Args:
            pkg_to_add: Name of package that is to be added.
        """
        filelist = []
        filelist.append(self.get_filelist_dict(self.rpm_src_dir + pkg_to_add,
                                               "/tmp/"))

        self.copy_filelist_to(self.ms_node, filelist,
                              add_to_cleanup=False, root_copy=True)

        self.execute_cli_import_cmd(self.ms_node,
                                    '/tmp/' + pkg_to_add,
                                    self.repo_dir_3pp)

    def verify_clustered_services_online(
            self, before_online_cnt, list_of_groups_types, list_of_active_cnt):
        """
        Verify that the clustered-services are online.
            Args:
            list_of_groups_types (dict): list of groups and whether they are
                                         parallel or failover
            list_of_active_cnt (dict): list of the groups and how many nodes
                                       they should be active on
            before_online_cnt (dict): list of groups and there actual state

        """
        for group_name in before_online_cnt:
            # Failover group
            if list_of_groups_types[group_name] == 1:
                self.assertEqual(1, before_online_cnt[group_name]['cnt'])
            else:
                self.assertEqual(list_of_active_cnt[group_name],
                                 before_online_cnt[group_name]['cnt'])

    def retrieve_data_before_node_lock(self, info):
        """
        Get the clustered services state information.
        Args:
            info (dict): LITP Model VCS Information.
        Returns:
            before_online_cnt (dict): list of groups and there actual state
            list_of_groups_types (dict): list of groups and whether they are
                                         parallel or failover
            after_online_cnt (dict): list of groups and dummy state information
            list_of_active_cnt (dict): list of the groups and how many nodes
                                       they should be active on
        """
        cmd = self.vcs.get_hagrp_state_cmd()
        hagrp_output, _, _ = self.run_command(
            self.primary_node, cmd, su_root=True, default_asserts=True)

        before_online_cnt, \
        after_online_cnt, \
        list_of_groups_types, \
        list_of_active_cnt = self.store_data_before_node_locking(
            info, hagrp_output, self.cluster_id)

        self.log("info", "before_online_cnt {0}".format(before_online_cnt))
        self.log("info", "after_online_cnt {0}".format(after_online_cnt))
        self.log("info", "list_of_groups_types {0}"
                 .format(list_of_groups_types))
        self.log("info", "list_of_active_cnt {0}".format(list_of_active_cnt))

        return before_online_cnt, after_online_cnt, list_of_groups_types, \
               list_of_active_cnt

    # @attr('pre-reg', 'non-revert', 'story3993', 'story3993_tc01')
    def obsolete_01_p_node1_unlocking(self):
        """
        Merged with test_03_p_both_nodes_unlocking
        #tms_id: litpcds_3993_tc_01
        #tms_requirements_id: LITPCDS-3993
        #tms_title: test_01_p_node1_unlocking
        #tms_description: Verify that node lock/unlock tasks are generated
                          for node1 only. Since only 1 node is locked, failover
                          clustered-services should be on the opposite node
                          after the node unlocking has completed.
        #tms_test_steps:
            #step: Determine clustered-services state information
            #result: VCS clustered service state information is stored
            #step: Verify that clustered-services are online
            #result: VCS clustered service are verified to be online
            #step: Trigger a node lock/unlock of node1 only
            #result: Plan is created with lock/unlock tasks for node1 only
            #step: Retrieve clustered-service state information
            #result: VCS clustered service state information is retrieved
            #step: Compare state information from before and after node lock
            #result: VCS service state information before and after node lock
            and unlock is verified to be the same
        #tms_test_precondition: VCS Clustered Services are deployed
        #tms_execution_type: Automated
        """
        pass

    # @attr('pre-reg', 'non-revert', 'story3993', 'story3993_tc02')
    def obsolete_02_p_node2_unlocking(self):
        """
        Covered in test_03_p_both_nodes_unlocking
        #tms_id: litpcds_3993_tc_02
        #tms_requirements_id: LITPCDS-3993
        #tms_title: test_02_p_node2_unlocking
        #tms_description: Verify that node lock/unlock tasks are generated
                          for node2 only. Since only 2 node is locked, failover
                          clustered-services should be on the opposite node
                          after the node unlocking has completed.
        #tms_test_steps:
            #step: Determine clustered-services state information
            #result: VCS clustered service state information is stored
            #step: Verify that clustered-services are online
            #result: VCS clustered service are verified to be online
            #step: Trigger a node lock/unlock of node2 only
            #result: Plan is created with lock/unlock tasks for node2 only
            #step: Retrieve clustered-service state information
            #result: VCS clustered service state information is retrieved
            #step: Compare state information from before and after node lock
            #result: VCS service state information before and after node lock
                     and unlock is verified to be the same
        #tms_test_precondition: VCS Clustered Services are deployed
        #tms_execution_type: Automated
        """
        pass

    @attr('all', 'non-revert', 'story3993', 'story3993_tc03')
    def test_03_p_both_nodes_unlocking(self):
        """
        @tms_id: litpcds_3993_tc_03
        @tms_requirements_id: LITPCDS-3993
        @tms_title: test_03_p_both_nodes_unlocking
        @tms_description: Verify that node lock/unlock tasks are generated
                          for node1 only,  as only 1 node is locked, failover
                          clustered-services should be on the opposite node
                          after the node unlocking has complete.
                          Repeat process for both nodes. This covers
                          litpcds_3993_tc_01 and litpcds_3993_tc_02.
        @tms_test_steps:
            @step: Determine clustered-services state information
            @result: VCS clustered service state information is stored
            @step: Verify that clustered-services are online
            @result: VCS clustered service are verified to be online
            @step: Create a package on node1, create and run plan
            @result: Plan runs successfully.
            @step: Retrieve clustered-service state information
            @result: VCS clustered service state information is retrieved
            @step: Compare state information from before and after node lock
            @result: Any FO SG should now be active on the other node - as only
                     one node was locked during the plan.
            @step: Trigger a node lock/unlock of both nodes in cluster
            @result: Plan is created with lock/unlock tasks for both nodes
            @step: Retrieve clustered-service state information
            @result: VCS clustered service state information is retrieved
            @step: Compare state information from before and after node lock
            @result: VCS service state information before and after node lock
                     and unlock is verified to be the same
        @tms_test_precondition: VCS Clustered Services are deployed
        @tms_execution_type: Automated
        """
        info = self.get_vcs_model_info()
        cmd = self.vcs.get_hagrp_state_cmd()

        ######################## Test one node ##############################
        self.log('info', '1. Get the clustered services state information.')
        before_online_cnt, \
        after_online_cnt, \
        list_of_groups_types, \
        list_of_active_cnt = self.retrieve_data_before_node_lock(info)

        self.log('info', '2. Verify that the clustered-services are online.')
        self.verify_clustered_services_online(before_online_cnt,
                                              list_of_groups_types,
                                              list_of_active_cnt)

        self.log('info', '3. Trigger a node lock by adding a package to '
                         'node1 only.')
        # Add package via plan to trigger a node lock
        pkg_to_add = 'EXTR-lsbwrapper37-1.1.0.rpm'
        self.import_package_to_3pp_dir(pkg_to_add)

        # Create pkg in infrastructure
        pkg_name = 'EXTR-lsbwrapper37'
        self.create_package(pkg_name)

        # Add package under node1
        package_path = '{0}/{1}'.format(self.software_path, pkg_name)
        node_path = '{0}/{1}'.format(self.n1_items, pkg_name)

        locked_hostname = self.get_props_from_url(
            self.ms_node, node_path, filter_prop="hostname")

        self.execute_cli_inherit_cmd(
            self.ms_node, node_path, package_path, add_to_cleanup=False)

        self.execute_cli_createplan_cmd(self.ms_node)
        self.execute_cli_runplan_cmd(self.ms_node)
        self.assertTrue(self.wait_for_plan_state(
            self.ms_node, test_constants.PLAN_COMPLETE, timeout_mins=20))

        self.log('info', '4. Get data after node locking.')
        hagrp_output, _, _ = self.run_command(
            self.primary_node, cmd, su_root=True, default_asserts=True)

        after_online_cnt = self.store_data_after_node_locking(
            info, hagrp_output, self.cluster_id, after_online_cnt)

        self.log("info", "after_online_cnt {0}".format(after_online_cnt))

        self.log('info', '5. Compare clustered service state information'
                         'before and after node lock.')
        for cs_grp_name in before_online_cnt:
            # if parallel, nr of online instances should equal to active count
            if list_of_groups_types[cs_grp_name] == 0:
                self.assertEqual(list_of_active_cnt[cs_grp_name],
                                 after_online_cnt[cs_grp_name]['cnt'])
            else:
                # Active count should be 1
                self.assertEqual(list_of_active_cnt[cs_grp_name],
                                 after_online_cnt[cs_grp_name]['cnt'])

                # Active instance should not be on node where it was initially
                if before_online_cnt[cs_grp_name]['node'] == locked_hostname:
                    self.assertNotEqual(before_online_cnt[cs_grp_name]['node'],
                                        after_online_cnt[cs_grp_name]['node'])

        ######################## Test both nodes ##############################
        self.log('info', '6. Get the clustered services state information.')

        before_online_cnt, \
        after_online_cnt, \
        list_of_groups_types, \
        list_of_active_cnt = self.retrieve_data_before_node_lock(info)

        self.log('info', '7. Verify that the clustered-services are online.')
        self.verify_clustered_services_online(before_online_cnt,
                                              list_of_groups_types,
                                              list_of_active_cnt)

        self.log('info', '8. Trigger a node lock by adding a package to both'
                         'nodes.')
        # Add package via plan to trigger a node lock
        pkg_to_add = 'EXTR-lsbwrapper39-1.1.0.rpm'
        self.import_package_to_3pp_dir(pkg_to_add)

        # Create pkg in infrastructure
        pkg_name = 'EXTR-lsbwrapper39'
        self.create_package(pkg_name)

        # Add package under node2
        package_path = '{0}/{1}'.format(self.software_path, pkg_name)

        node_path = '{0}/{1}'.format(self.n2_items, pkg_name)
        self.execute_cli_inherit_cmd(
            self.ms_node, node_path, package_path, add_to_cleanup=False)

        # Add package under node1
        node_path = '{0}/{1}'.format(self.n1_items, pkg_name)
        self.execute_cli_inherit_cmd(
            self.ms_node, node_path, package_path, add_to_cleanup=False)

        self.execute_cli_createplan_cmd(self.ms_node)
        self.execute_cli_runplan_cmd(self.ms_node)
        self.assertTrue(self.wait_for_plan_state(
            self.ms_node, test_constants.PLAN_COMPLETE, timeout_mins=20))

        self.log('info', '9. Get data after node locking.')
        hagrp_output, _, _ = self.run_command(
            self.primary_node, cmd, su_root=True, default_asserts=True)

        after_online_cnt = self.store_data_after_node_locking(
            info, hagrp_output, self.cluster_id, after_online_cnt)

        self.log("info", "after_online_cnt {0}".format(after_online_cnt))

        self.log('info', '10. Compare clustered service state information '
                         'before and after node lock.')
        for cs_grp_name in before_online_cnt:
            # if parallel, nr of online instances should equal to active count
            if list_of_groups_types[cs_grp_name] == 0:
                self.assertEqual(list_of_active_cnt[cs_grp_name],
                                 after_online_cnt[cs_grp_name]['cnt'])
            else:
                # FO services active on the same node as before the plan was
                # run
                self.assertEqual(list_of_active_cnt[cs_grp_name],
                                 after_online_cnt[cs_grp_name]['cnt'])

"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     August 2017
@author:    Ulian Stefan
@summary:   Integration Tests
            Agile: STORY-194491
"""
import os
from vcs_utils import VCSUtils
from test_constants import PLAN_COMPLETE
from litp_generic_test import GenericTest, attr
from redhat_cmd_utils import RHCmdUtils
from generate import load_fixtures, generate_json, apply_options_changes, \
    apply_item_changes

STORY = '194491'


class Story194491(GenericTest):
    """
    TORF-194491:
        Description:
            As a LITP user, I want the ability to delete a powered-off node so
            that I can contract a VCS cluster in my deployment
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
        super(Story194491, self).setUp()

        self.management_server = self.get_management_node_filename()
        self.vcs = VCSUtils()
        # Location where RPMs to be used are stored
        self.rpm_src_dir = (os.path.dirname(
            os.path.realpath(__file__)) + '/rpm-out/dist/')

        self.vcs_clusters_url = self.find(self.management_server,
                                 '/deployments', 'cluster', False)[0]
        self.vcs_cluster1_url = "{0}/{1}".format(self.vcs_clusters_url, 'c1')
        self.vcs_cluster2_url = "{0}/{1}".format(self.vcs_clusters_url, 'c2')

        self.c1_nodes_urls = self.find(self.management_server,
                                       self.vcs_cluster1_url,
                                       'node')

        self.c2_nodes_urls = self.find(self.management_server,
                                       self.vcs_cluster2_url,
                                       'node')

        self.c1_node_exe = []
        self.c2_node_exe = []
        self.c2_node = []
        self.rh_cmds = RHCmdUtils()
        self.gabtab = 'cat /etc/gabtab'

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story194491, self).tearDown()

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
            cleanup: (bool) Add to cleanup
            vcs_trig: (int) Number of vcs triggers
            story: (int) Story number
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

        return load_fixtures(story, self.vcs_cluster2_url,
                             self.c2_nodes_urls, input_data=_json)

    def _get_node_list_for_cs(self, cs_url):
        """
        Method to obtain the node list of a clustered service group before
        and after migration
        :param cs_url: (str) clustered service URL
        :return: node_list: (str) Service group Node list
        """
        node_list = self.get_props_from_url(self.management_server, cs_url,
                                            filter_prop='node_list')

        return node_list

    def get_vcs_fo_sg(self, sg_props):
        """
        Method to retrieve a service group from the model, if it exists
        :param sg_props: (list) properties of the desired service group
        :return: A service group matching what was requested or an empty
        list if no such service exists
        """
        try:
            return self.get_matching_vcs_cs_in_model(
                    self.management_server, apps=1, ha_srv_cfgs=1,
                    cs_props_dict={'active': sg_props['active'],
                                   'standby': sg_props['standby'],
                                   'node_list': sg_props['node_list'],
                                   'name': sg_props['name']})
        except AssertionError:
            self.log('error', 'Service Group could not be found')
            return []

    def _check_cs_in_model(self, svc_info, dependencies=False):
        """
        Method that will check for existing service groups in the model
        :param svc_info: (list) service name node list key value pairs
        :return: vcs_fo1_sg (str): FO SG URL
                 vcs_fo2_sg (str): FO SG URL
        """
        self.log('info', 'Checking if suitable service groups exist')
        vip_props = {'network_name': 'traffic1',
                     'ipaddress': ['172.16.100.14', '172.16.100.16']}

        sg1_props = {'active': '1', 'standby': '1',
                     'node_list': svc_info.values()[0],
                     'name': svc_info.keys()[0]}
        sg2_props = {'active': '1', 'standby': '1',
                     'node_list': svc_info.values()[1],
                     'name': svc_info.keys()[1]}
        vcs_fo1_sg = self.get_vcs_fo_sg(sg1_props)
        vcs_fo2_sg = self.get_vcs_fo_sg(sg2_props)

        dep_list = self.get_props_from_url(self.management_server, vcs_fo1_sg,
                                            filter_prop='dependency_list')

        if not dependencies and vcs_fo1_sg and dep_list:
            self.execute_cli_update_cmd(self.management_server, vcs_fo1_sg,
                                        'dependency_list', action_del=True)

        if vcs_fo1_sg == [] or vcs_fo2_sg == []:
            self.log('info', 'Creating suitable Service groups for TC')
            fixtures = self.baseline(vcs_len=2, app_len=2, hsc_len=2,
                                     vips_len=2)
            if dependencies:
                apply_options_changes(
                fixtures, 'vcs-clustered-service', 0,
                {'active': '1', 'standby': '1', 'name': 'CS_194491_1',
                 'node_list': svc_info.values()[0],
                 'dependency_list': 'CS_194491_2'}, overwrite=True)
            else:
                apply_options_changes(
                fixtures, 'vcs-clustered-service', 0,
                {'active': '1', 'standby': '1', 'name': 'CS_194491_1',
                 'node_list': svc_info.values()[0]}, overwrite=True)
            apply_options_changes(
                fixtures, 'vcs-clustered-service', 1,
                {'active': '1', 'standby': '1', 'name': 'CS_194491_2',
                 'node_list': svc_info.values()[1]}, overwrite=True)
            apply_item_changes(
                fixtures, 'ha-service-config', 1,
                {'parent': "CS_194491_2",
                 'vpath': self.vcs_cluster2_url + '/services/CS_194491_2/'
                                                 'ha_configs/HSC_194491_2'}
                )
            apply_item_changes(
                fixtures, 'service', 1,
                {'parent': "CS_194491_2",
                 'destination': self.vcs_cluster2_url +
                                '/services/CS_194491_2/applications/'
                                'APP_194491_2'})
            apply_item_changes(
                fixtures, 'vip', 0, {'vpath': self.vcs_cluster2_url +
                                              '/services/CS_194491_2/'
                                              'ipaddresses/VIP1'}
            )
            apply_options_changes(
                fixtures, 'vip', 0, {
                    'network_name': '{0}'.format(vip_props['network_name']),
                    'ipaddress': '{0}'.format(vip_props['ipaddress'][0])},
                overwrite=True)
            apply_item_changes(
                fixtures, 'vip', 1, {'vpath': self.vcs_cluster2_url +
                                              '/services/CS_194491_2/'
                                              'ipaddresses/VIP2'}
            )
            apply_options_changes(
                fixtures, 'vip', 1, {
                    'network_name': '{0}'.format(vip_props['network_name']),
                     'ipaddress': '{0}'.format(vip_props['ipaddress'][1])},
                overwrite=True)

            self.apply_cs_and_apps_sg(self.management_server, fixtures,
                                      self.rpm_src_dir)

            vcs_fo1_sg.append(self.vcs_cluster2_url + '/services/' +
                fixtures['service'][0]['parent'])
            vcs_fo2_sg.append(self.vcs_cluster2_url + '/services/' +
                fixtures['service'][1]['parent'])

            if dependencies:
                self.execute_cli_update_cmd(self.management_server,
                                                     vcs_fo1_sg,
                                        props='dependency_list=CS_194491_2')

        return vcs_fo1_sg[-1], vcs_fo2_sg[-1]

    def _expand_cluster(self, tc_name, expansion_scripts):
        """
        Description:
            This Method performs cluster expansion
        Steps:
            1. Expand specified cluster with desired node
        """
        self.log('info', 'Expand cluster for {0}'.format(tc_name))

        # Step 2: Expand cluster
        for script in expansion_scripts:
            self.execute_expand_script(self.management_server,
                                       script)

        self.c1_nodes_urls = self.find(self.management_server,
                                       self.vcs_cluster1_url,
                                       'node')

        self.c2_nodes_urls = self.find(self.management_server,
                                       self.vcs_cluster2_url,
                                       'node')

        self.rh_cmds = RHCmdUtils()

        for node in self.c1_nodes_urls:
            self.c1_node_exe.append(
                self.get_node_filename_from_url(self.management_server, node))

        for node in self.c2_nodes_urls:
            self.c2_node_exe.append(
                self.get_node_filename_from_url(self.management_server, node))

    def check_for_vcs_seed_threshold(self):
        """
        Description:
            Method to check if the vcs_seeding_threshold property value is
            modelled.
        Steps:
            1. Search the vcs cluster/s for vcs_seedng_threshold property.
            And record its value.
        Returns:
            seeding_value: int

        """
        self.log('info', 'Searching vcs clusters for vcs_seeding_threshold '
                         'property')
        vcs_clusters = self.find(self.management_server,
                               '/deployments',
                               'vcs-cluster')
        for cluster in vcs_clusters:
            seeding_value = \
                self.get_props_from_url(
                    self.management_server,
                    cluster,
                    "vcs_seed_threshold")
            if seeding_value == None:
                self.log("info",
                         "No seeding value modelled in {0}".format(cluster))
            else:
                self.log("info",
                         "vcs_seed_threshold is : {0} for cluster {1}"
                         .format(seeding_value, cluster))
                seed_value = seeding_value.strip()
                return seed_value[-1]

    @attr('all', 'expansion', 'story194491', 'story194491_tc01')
    def test_01_p_rm_node_and_cs_during_migration_with_deps(self):
        """
        @tms_id: torf_194491_tc01
        @tms_requirements_id: TORF-194491
        @tms_title: Remove powered off node during clustered service
        migration with dependencies.
        @tms_description:
        Test to verify that a user can remove a powered off node during
        migration with dependencies.
        @tms_test_steps:
            @step: Run restore_model to remove all the updates made in the
            LITP Model that were not applied.
            @result: Restore_model run successfully.
            @step: Run expansion script to expand cluster c2 with node4.
            @result: The expansion script to expand cluster c2 with node4 is
            run
            @step: Check if suitable CS is available in model if not create
            CS_194491_1 FO (n2,n3) and CS_194491_2 FO (n2,n3) where
            CS_194491_1 depends on CS_194491_2
            @result: SG exists in LITP model
            @step: Assert node list prior to migration
            @result: Node list is equal to n2,n3
            @step: Update CS group node list attribute to migrate nodes for
            both SG to (n2,n4).
            @result: CS has updated node list
            @step: Powered off node3 (old node) from c2 vcs_cluster
            @result: node3 is powered down
            @step: Remove node3 from c2 vcs_cluster
            @result: node3 is in ForRemoval State
            @step: Remove vcs_seed_threshold property from cluster c2 to
            make the VCS plugin recalculate it.
            @result: The vcs_seed_threshold property is removed from cluster c2
            @step: Create/ Run plan
            @result: Plan is created, run to completion and is successful.
            @step: Assert Node list after migration
            @result: Node list is equal to n2,n4
            @step: Assert vcs_seed_threshold value is recalculated correctly
            and gabtab has the correct threshold.
            @result: vcs_seed_threshold value is recalculated to 1
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        timeout_mins = 90
        self.log('info', 'Run litp restore model')
        self.execute_cli_restoremodel_cmd(self.management_server)
        # Get paths to cluster 2 nodes
        self.c2_nodes_urls = self.find(self.management_server,
                                       self.vcs_cluster2_url,
                                       'node')

        # Append the list to run gabtab command on.
        for nodes in self.c2_nodes_urls:
            self.c2_node.append(
                self.get_node_filename_from_url(self.management_server, nodes))
        self.set_pws_new_node(self.management_server, self.c2_node[0])
        self.log('info', 'Check gabtab value is calculated correctly '
                         'for the number of nodes in the cluster')
        vcs_seed_gabtab_pre_expansion, _, _ = \
            self.run_command(self.c2_node[0],
                             self.gabtab)
        self.assertEqual(vcs_seed_gabtab_pre_expansion[0],
                         '/sbin/gabconfig -c -n1')
        # TORF-198359 update cluster C2 to include modelled vcs_seed_threshold
        # value of 2
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster2_url,
                                    props='vcs_seed_threshold=2')
        # Step 1: Expand cluster c2 with node4
        self.log('info', 'Expand cluster c2 with node4')
        self._expand_cluster('TC04', ['expand_cloud_c2_mn4.sh'])
        # Check if the seed value is modelled as expected
        seed_value = self.check_for_vcs_seed_threshold()
        # Ensure seed value is as expected
        self.assertTrue(seed_value == '2',
                        "Seed value is not modelled as expected")
        # Check if suitable service groups exist in the model if not create
        # them
        svc_info = {'CS_107501_1': 'n2,n3', 'CS_107501_2': 'n3,n2'}
        vcs_fo1_sg, vcs_fo2_sg = self._check_cs_in_model(svc_info,
                                                         dependencies=True)

        self.log('info', 'Checking node list is as expected')
        node_list = self._get_node_list_for_cs(vcs_fo1_sg)
        self.assertEqual(node_list, 'n2,n3')
        node_list = self._get_node_list_for_cs(vcs_fo2_sg)
        self.assertEqual(node_list, 'n3,n2')

        self.log('info', 'Updating node list for migration, with '
                         'Expansion')
        self.execute_cli_update_cmd(self.management_server, vcs_fo1_sg,
                                    props='active=1 standby=1 '
                                          'node_list=n2,n4')
        self.execute_cli_update_cmd(self.management_server, vcs_fo2_sg,
                                    props='active=1 standby=1 '
                                          'node_list=n2,n4')

        self.log("info", "Powered off node3 (old node) from c2 vcs_cluster")
        self.poweroff_peer_node(self.management_server, self.c2_node_exe[1])

        self.log("info", "Remove node3 from c2 vcs_cluster")
        self.execute_cli_remove_cmd(self.management_server,
                                    self.c2_nodes_urls[1])
        self.c2_node_exe.remove(self.c2_node_exe[1])

        # Get the infrastructure path for node3 and remove it
        inherited_path = self.deref_inherited_path(self.management_server,
                                                   self.c2_nodes_urls[1] +
                                                   '/system')
        self.execute_cli_remove_cmd(self.management_server, inherited_path)
        # TORF-198359 update cluster C2 to remove modelled vcs_seed_threshold
        # property so vcs recalculated based on the new number of nodes
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster2_url,
                                    props='vcs_seed_threshold',
                                    action_del=True)

        self.run_and_check_plan(self.management_server, PLAN_COMPLETE,
                                timeout_mins, add_to_cleanup=False)

        self.assertTrue(self.wait_for_plan_state(
                self.management_server, PLAN_COMPLETE))

        self.log('info', 'Asserting node list after migration update')
        node_list = self._get_node_list_for_cs(vcs_fo1_sg)
        self.assertEqual(node_list, 'n2,n4')
        node_list = self._get_node_list_for_cs(vcs_fo2_sg)
        self.assertEqual(node_list, 'n2,n4')

        # TORF-215583
        self.log('info', 'Check value is recalculated correctly in gabtab')
        vcs_seed_gabtab_post_expansion, _, _ = \
            self.run_command(self.c2_node_exe[0],
                             self.gabtab)
        self.assertEqual(vcs_seed_gabtab_post_expansion[0],
                         '/sbin/gabconfig -c -n1')

        self.execute_cli_remove_cmd(self.management_server, vcs_fo1_sg)
        self.execute_cli_remove_cmd(self.management_server, vcs_fo2_sg)

        self.run_and_check_plan(self.management_server, PLAN_COMPLETE,
                                timeout_mins, add_to_cleanup=False)

    @attr('all', 'expansion', 'Story194491', 'Story194491_tc02')
    def test_02_p_remove_and_migrate_standby_node_while_apd_is_false(self):
        """
        @tms_id: torf_194491_tc02
        @tms_requirements_id: TORF-194491
        @tms_title: Test to verify that you can remove a powered off node and
        migrate a FO SG standby node while apd is false.
        @tms_description:
        Test to verify that you can remove a powered off node and migrate
        the standby node of a FO SG without a dependency on another SG while
        apd is false for model the item.
        @tms_test_steps:
            @step: Check if CS_194491_1 and CS_194491_2 FO CSs are available
            in the model if not create them.
            @result: CS_194491_1 and CS_194491_2 FO SGs are present in LITP
            model
            @step: Assert Node list prior to migration
            @result: CS_194491_1 and CS_194491_2 are on node2,node4
            @step: Update CS_194491_1 and CS_194491_2 to migrate standby node
            to node2, node3
            @result: CS_194491_1 and CS-194491_2 CS_ FO SGs updated
            @step: Powered off node4 from c2 vcs_cluster
            @result: node4 is powered down
            @step: Remove node4 from c2 vcs_cluster
            @result: node4 is in ForRemoval State
            @step: Create/ Run plan
            @result: Plan is created and run
            @step: Run litpd restart prior to node lock and after service
            group is removed
            @result: LITPD deamon is restarted
            @step: Assert CS is fully re-installed and online after node
            lock phases
            @result: Sgs are online on different nodes after migration
            @step: Assert Node list after migration
            CS_194491_1 and CS_194491_2 are present on node2, node3
            @result: Node list is updated after plan
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        timeout_mins = 60
        # Append the list to run gabatab command on.
        for nodes in self.c2_nodes_urls:
            self.c2_node.append(
                self.get_node_filename_from_url(self.management_server,
                                                nodes))
        # TORF-198359 update cluster C2 to include modelled vcs_seed_threshold
        # value of 1
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster2_url,
                                    props='vcs_seed_threshold=1')
        # Step 1: Expand cluster c2 with node3
        self.log('info', 'Expand cluster c2 with node3')
        self._expand_cluster('TC02', ['expand_cloud_c2_mn3.sh'])
        # Ensure the gabtab value for vcs seeding matches the model
        vcs_seed_gabtab, _, _ = \
            self.run_command(self.c2_node[0],
                             self.gabtab)
        self.assertEqual(vcs_seed_gabtab[0],
                         '/sbin/gabconfig -c -n1')
        # Check if there are suitable service groups existing in
        # the model if not create them
        self.log('info', 'Checking for suitable Service Groups')
        svc_info = {'CS_194491_1': 'n2,n4', 'CS_194491_2': 'n2,n4'}
        vcs_fo1_sg, vcs_fo2_sg = self._check_cs_in_model(svc_info)

        self.log('info', 'Checking node list is as expected')
        node_list = self._get_node_list_for_cs(vcs_fo1_sg)
        self.assertEqual(node_list, 'n2,n4')
        node_list = self._get_node_list_for_cs(vcs_fo2_sg)
        self.assertEqual(node_list, 'n2,n4')

        self.log('info', 'Updating node list for migration')
        self.execute_cli_update_cmd(self.management_server, vcs_fo1_sg,
                                    props='active=1 standby=1 '
                                          'node_list=n2,n3')
        self.execute_cli_update_cmd(self.management_server, vcs_fo2_sg,
                                    props='active=1 standby=1 '
                                          'node_list=n2,n3')
        # TORF-198359 update cluster C2 to remove modelled vcs_seed_threshold
        # property so vcs recalculated based on the new number of nodes
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster2_url,
                                    props='vcs_seed_threshold',
                                    action_del=True)
        self.log("info", "Step 4: Power off old node (node4)")
        self.poweroff_peer_node(self.management_server, self.c2_node_exe[2])
        self.log("info", "Step 4: Remove old node (node4)")
        self.execute_cli_remove_cmd(self.management_server,
                                    self.c2_nodes_urls[2])
        self.c2_node_exe.remove(self.c2_node_exe[2])

        # Get the infrastructure path for node4 and remove it
        inherited_path = self.deref_inherited_path(self.management_server,
                                                   self.c2_nodes_urls[2] +
                                                   '/system')
        self.execute_cli_remove_cmd(self.management_server, inherited_path)

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.log('info', 'Running litpd restart')
        self.restart_litpd_service(self.management_server)

        self.run_and_check_plan(self.management_server, PLAN_COMPLETE,
                                timeout_mins, add_to_cleanup=False)

        self.log('info', 'Asserting node list after migration update')
        # Assert node list after migration to other nodes
        node_list = self._get_node_list_for_cs(vcs_fo1_sg)
        self.assertEqual(node_list, 'n2,n3')
        node_list = self._get_node_list_for_cs(vcs_fo2_sg)
        self.assertEqual(node_list, 'n2,n3')

        self.execute_cli_remove_cmd(self.management_server, vcs_fo1_sg)
        self.execute_cli_remove_cmd(self.management_server, vcs_fo2_sg)

        self.run_and_check_plan(self.management_server, PLAN_COMPLETE,
                                timeout_mins, add_to_cleanup=False)
        # Ensure the gabtab value for vcs seeding is correct after contraction
        # plans
        vcs_seed_gabtab, _, _ = \
            self.run_command(self.c2_node[0],
                             self.gabtab)
        self.assertEqual(vcs_seed_gabtab[0],
                         '/sbin/gabconfig -c -n1')

    @attr('all', 'expansion', 'story194491', 'story194491_tc03')
    def test_03_p_remove_multiple_nodes_different_clusters(self):
        """
        @tms_id: torf_194491_tc03
        @tms_requirements_id: TORF-194491
        @tms_title: Remove multiple powered off nodes from multiple clusters.
        @tms_description:
        Test to verify that a user can remove multiple powered off nodes from
        different vcs-clusters.
        @tms_test_steps:
            @step: Expand cluster c1 with node3 and cluster c2 with node4
            @result: c1 expanded with node3 and c2 expanded with node4.
            @step: Create and run plan.
            @result: plan creates and executes successfully.
            @step: Powered off node3 and node4.
            @result: node3 and node4 are powered down.
            @step: Remove node3 from c1 and node4 from c2.
            @result: Node3 from c1 and Node4 from c2 vcs-clusters are in
                     "ForRemoval" state.
            @step: Create and run plan.
            @result: plan creates and executes successfully.
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        timeout_mins = 90

        # Step 1: Expand cluster c1 with node4
        self.log('info', 'Expand cluster c1 with node4')
        # TORF-198359 update cluster C1 to include modelled vcs_seed_threshold
        # value of 2
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster1_url,
                                    props='vcs_seed_threshold=2')
        self._expand_cluster('TC03', ['expand_cloud_c1_mn4.sh'])
        self.run_and_check_plan(self.management_server, PLAN_COMPLETE, 30,
                                add_to_cleanup=False)
        # Ensure the gabtab value for vcs seeding matches the model
        vcs_seed_gabtab, _, _ = \
            self.run_command(self.c1_node_exe[0],
                             self.gabtab)
        self.assertEqual(vcs_seed_gabtab[0],
                         '/sbin/gabconfig -c -n2')

        self.log("info", "Step 4: Power off node3")
        self.poweroff_peer_node(self.management_server, self.c2_node_exe[1])

        self.log("info", "Step 4: Power off node4")
        self.poweroff_peer_node(self.management_server, self.c1_node_exe[1])

        self.log("info", "Step 4: Remove node3")
        self.execute_cli_remove_cmd(self.management_server,
                                    self.c2_nodes_urls[1])

        self.log("info", "Step 4: Remove node4")
        self.execute_cli_remove_cmd(self.management_server,
                                    self.c1_nodes_urls[1])

        # Get the infrastructure path for node3 and remove it
        inherited_path = self.deref_inherited_path(self.management_server,
                                                   self.c2_nodes_urls[1] +
                                                   '/system')
        self.execute_cli_remove_cmd(self.management_server, inherited_path)
        # Get the infrastructure path for node4 and remove it
        inherited_path = self.deref_inherited_path(self.management_server,
                                                   self.c1_nodes_urls[1] +
                                                   '/system')
        self.execute_cli_remove_cmd(self.management_server, inherited_path)

        self.c1_node_exe.remove(self.c1_node_exe[1])
        self.c2_node_exe.remove(self.c2_node_exe[1])

        # TORF-198359 update cluster C1 to remove modelled vcs_seed_threshold
        # property so vcs recalculated based on the new number of nodes after
        # contraction
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster1_url,
                                    props='vcs_seed_threshold',
                                    action_del=True)

        # TORF-198359 update cluster C2 to remove modelled vcs_seed_threshold
        # property so vcs recalculated based on the new number of nodes after
        # contraction
        self.execute_cli_update_cmd(self.management_server,
                                    self.vcs_cluster2_url,
                                    props='vcs_seed_threshold=1')

        self.run_and_check_plan(self.management_server, PLAN_COMPLETE,
                                timeout_mins, add_to_cleanup=False)
        # Ensure the gabtab value for vcs seeding matches the model
        vcs_seed_gabtab_pre_expansion, _, _ = \
            self.run_command(self.c1_node_exe[0],
                             self.gabtab)
        self.assertEqual(vcs_seed_gabtab_pre_expansion[0],
                         '/sbin/gabconfig -c -n1')
        # Ensure the gabtab value for vcs seeding matches the model
        vcs_seed_gabtab_pre_expansion, _, _ = \
            self.run_command(self.c2_node_exe[0],
                             self.gabtab)
        self.assertEqual(vcs_seed_gabtab_pre_expansion[0],
                         '/sbin/gabconfig -c -n1')

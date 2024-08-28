"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     October 2015
@author:    Ciaran Reilly
            Boyan Mihovski
@summary:   Integration
            Agile: STORY-5169
"""

import os
from litp_generic_test import GenericTest, attr
import test_constants
from vcs_utils import VCSUtils
from redhat_cmd_utils import RHCmdUtils
from generate import load_fixtures, generate_json, apply_options_changes, \
    apply_item_changes

STORY = '5169'


class Story5169(GenericTest):
    """
    LITPCDS-5169:
    As a LITP user i want to remove a VCS Clustered Service from
    the cluster so that i can remove applications that are no
    longer required.
    The user should be able to perform the following:
        -A user can remove a vcs-clustered-service from the model and
         it will be taken out of service in the cluster
        -If I remove 2 clustered services that are dependant on each
         another, the dependent vcs-clustered-serivce must be removed
         also to avoid failures
        -If I remove a clustered service that another clustered
         service depends upon, I will get a validation error
        -The service group removal should be done in a phase before
         any node locking/unlocking happens to avoid failures.
        -If I have a vcs-clustered-service defined as a critical_service,
         I should see a validation error if the vcs-clustered-service
         is ForRemoval

         Generator command:
        python generate.py --s 5169 --a 1 --vcs 1 --hsc 1 \
        --vcso 'active="2"'
    """

    def setUp(self):
        super(Story5169, self).setUp()
        # specify test data constants
        self.management_server = self.get_management_node_filename()
        self.vcs = VCSUtils()
        self.rhcmd = RHCmdUtils()
        # Location where RPMs to be used are stored
        self.rpm_src_dir = (os.path.dirname(
            os.path.realpath(__file__)) + '/rpm-out/dist/')

        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.management_server,
                                         '/deployments', 'vcs-cluster')[0]
        self.cluster_id = self.vcs_cluster_url.split('/')[-1]
        self.node_flnmes = self.get_managed_node_filenames()
        nodes_urls = self.find(self.management_server,
                               self.vcs_cluster_url,
                               'node')

        _json = generate_json(to_file=False, story=STORY,
                              vcs_length=1,
                              app_length=1,
                              hsc_length=1
                              )
        self.fixtures = load_fixtures(
            STORY, self.vcs_cluster_url, nodes_urls, input_data=_json)
        apply_options_changes(
            self.fixtures,
            'vcs-clustered-service', 0, {'active': '2', 'standby': '0',
                                         'name': 'CS_5169_1',
                                         'node_list': 'n1,n2'},
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
        super(Story5169, self).tearDown()

    def check_vcs_license_keys(self, puppet_flag=False,
                               verify_keys=False):
        """
        Method that will test for TORF-191968 Improvement on VCS license keys
        being regenerated after a puppet cycle. Note if puppet is stopped
        the VCS licenses will not be re-generated
        :param: Puppet_flag: (bool) Used to disable puppet and delete license
        keys on node. (TRUE) - Deletes keys and stops puppet
                      (FALSE) - Restarts Puppet
        :param: Verify_keys: (bool) To determine whether or not to check for
        vcs license keys on nodes or not
        :return: Nothing
        """
        start_puppet_cmd = self.rhcmd.get_systemctl_start_cmd('puppet')
        stop_puppet_cmd = self.rhcmd.get_systemctl_stop_cmd('puppet')
        license_url = "/etc/vx/licenses/lic/"

        rm_licenses_cmd = "rm -rf {0}*".format(license_url)

        # Verify that vcs keys exist after a plan completes with a config
        # task
        if verify_keys:
            for node in self.node_flnmes:
                # wait for puppet run to finish
                self.assertTrue(
                    self.wait_for_puppet_idle(self.management_server, node),
                    "Puppet hasn't reached idle state after its cycle "
                    "interval has expired")
                self.assertTrue(
                    self.wait_for_cmd(node, 'ls {0} | {1} .vxlic'.format(
                        license_url, test_constants.GREP_PATH), 0),
                    "VCS license keys not restored by puppet"
                )

                stdout = self.run_command(node, start_puppet_cmd,
                                          su_root=True,
                                          default_asserts=True)[0]
                self.assertEqual([], stdout)

        elif puppet_flag:
            # Remove VCS license keys and stop puppet
            for node in self.node_flnmes:
                stdout = self.run_command(node, rm_licenses_cmd,
                                          su_root=True,
                                          default_asserts=True)[0]
                self.assertEqual([], stdout)

                stdout = self.run_command(node, stop_puppet_cmd,
                                          su_root=True,
                                          default_asserts=True)[0]
                self.assertEqual([], stdout)
        return

    @attr('all', 'non-revert',
          'story5169', 'story5169_tc01', 'cdb_priority1')
    def test_01_p_rmve_vcs_cs_from_model(self):
        """
        @tms_id: litpcds_5169_tc1, torf_191968_tc15, torf_191968_tc14
        @tms_requirements_id: LITPCDS-5169
        @tms_title: remove vcs cluster service from model
        @tms_description:
        Test to verify that a VCS Clustered Service (Without any
        dependencies) can be removed from the model and will be
        taken out of service successfully, whilst there are no valid license
        keys.
        NOTE: Also verifies task TORF-191968
        @tms_test_steps:
        @step: Remove VCS license Keys and stop puppet
        @result: VCS keys are removed from all nodes and puppet is stopped
        @step: Create VCS clustered service used for testing
        @result: VCS Clustered service is removed
        @step: Create/ Run plan
        @result: Plan is run to completion
        @step: Verify Keys exist due to puppet configuration
        @result: VCS license keys are present
        @step:  Remove vcs cluster service with no dependencies from model
        @result: items set to for removal
        @step: create and run plan
        @result: plan executes successfully
        @result: RPMS are removed from nodes
        @step: HA GRP commands
        @result: service groups are deleted
        @tms_test_precondition:N/A
        @tms_execution_type: Automated
        """

        # TORF-191968: test_15_p_create_vcs_sg_after_keys_are_removed
        # test_01_p_delete_vcs_permanent_keys
        self.check_vcs_license_keys(puppet_flag=True)

        # Step 1, 2 and 3
        cs_url = self.get_cs_conf_url(self.management_server,
                                      self.fixtures['service']
                                      [0]['parent'],
                                      self.vcs_cluster_url)
        if cs_url is None:
            apply_item_changes(self.fixtures, 'service', 0,
                               {'add_to_cleanup': True})
            self.apply_cs_and_apps_sg(
                self.management_server, self.fixtures, self.rpm_src_dir)
            # This section of the test sets up the model and creates the plan
            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE, 10)
            cs_url = self.get_cs_conf_url(self.management_server,
                                          self.fixtures['service']
                                          [0]['parent'],
                                          self.vcs_cluster_url)
            self.log('info', 'TORF-191968: TC1, TC15')
            # TORF-191968:
            # Verify VCS license keys are still deleted
            self.check_vcs_license_keys(verify_keys=True)
            self.check_vcs_license_keys(puppet_flag=True)

        # self.log('info', 'TORF-191968: TC14')
        # TORF-191968: test_14_p_remove_vcs_sg_after_keys_are_removed
        self.execute_cli_remove_cmd(self.management_server, cs_url,
                                    add_to_cleanup=False)
        # Step 4
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 10)

        # Step 5
        cs_group_name = \
            self.vcs.generate_clustered_service_name(self.fixtures['service']
                                                     [0]['parent'],
                                                     self.cluster_id)
        get_vcs_grp_state = self.vcs.get_hagrp_state_cmd()
        stdout, _, rc = self.run_command(self.node_flnmes[0],
                                         get_vcs_grp_state +
                                         cs_group_name,
                                         add_to_cleanup=False, su_root=True)
        self.assertEqual(1, rc)
        self.assertEqual('VCS WARNING V-16-1-40131 Group {0} does not exist '
                         'in the local cluster'.format(cs_group_name),
                         stdout[0])
        # Step 6
        pkg = self.fixtures['service'][0]['package_id']
        for node in self.node_flnmes:
            self.assertFalse(self.check_pkgs_installed(node, [pkg]),
                             "The packages are not present in target node")

        self.log('info', 'TORF-191968: TC3, TC14')
        # Ensure VCS license keys are re-generated
        # test_03_p_puppet_regenerates_license_keys_after_deletion
        self.check_vcs_license_keys(verify_keys=True)

    @attr('all', 'non-revert',
          'story5169', 'story5169_tc05')
    def test_05_p_rmve_vcs_cs_cs_already_rm(self):
        """
        @tms_id: litpcds_5169_tc5
        @tms_requirements_id: LITPCDS-5169
        @tms_title: remove vcs cluster service already manually removed
        @tms_description:
        Test to verify that when a user tries to remove a vcs
        clustered service plan, when the CS has already been removed
        by a user manually
        @tms_test_steps:
        @step:  Create a VCS clustered service
        @result: VCS clustered service created
        @step: create and run plan
        @result: plan executes successfully
        @step: deleted VCS clustered service manually
        @result: service group is deleted manually
        @step: remove VCS clustered servic from litp model
        @result: item is set to for removal
        @step: create and run plan
        @result: plan executes successfully
        @result: RPMS are removed from nodes
        @tms_test_precondition:N/A
        @tms_execution_type: Automated
        """
        # Step 1, 2
        cs_url = self.get_cs_conf_url(self.management_server,
                                      self.fixtures['service']
                                      [0]['parent'],
                                      self.vcs_cluster_url)
        if cs_url is None:
            self.apply_cs_and_apps_sg(
                self.management_server, self.fixtures, self.rpm_src_dir)
            # This section of the test sets up the model and creates the plan
            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE, 10)
            cs_url = self.get_cs_conf_url(self.management_server,
                                          self.fixtures['service']
                                          [0]['parent'],
                                          self.vcs_cluster_url)

        sg_name = \
            self.vcs.generate_clustered_service_name(self.fixtures['service']
                                                     [0]['parent'],
                                                     self.cluster_id)

        # Step 3
        get_res_lst = self.vcs.get_hagrp_resource_list_cmd(sg_name)
        grp_resources, _, _ = self.run_command(self.node_flnmes[0],
                                               get_res_lst,
                                               su_root=True,
                                               default_asserts=True)

        # Switching VCS to read/write mode for deletion
        self.run_command(self.node_flnmes[0],
                         self.vcs.get_haconf_cmd("-makerw"),
                         su_root=True)

        for rsrces in grp_resources:
            self.run_command(self.node_flnmes[0],
                             self.vcs.get_hares_del_cmd(rsrces),
                             su_root=True)

            # Deleting service groups
            self.run_command(self.node_flnmes[0],
                             self.vcs.get_hagrp_del_cmd(sg_name),
                             su_root=True)
            # Close conf
            self.run_command(self.node_flnmes[0],
                             self.vcs.get_haconf_cmd("-dump -makero"),
                             su_root=True)

        # Step 4
        self.execute_cli_remove_cmd(self.management_server, cs_url,
                                    add_to_cleanup=False)

        # Step 5 and 6
        self.run_and_check_plan(self.management_server,
                                test_constants.PLAN_COMPLETE, 10)

        # Step 7
        pkg = self.fixtures['service'][0]['package_id']
        for node in self.node_flnmes:
            self.assertFalse(self.check_pkgs_installed(node, [pkg]),
                             "The packages are not present in target node")

"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     August 2015
@author:    Boyan Mihovski
@summary:   Integration
            Agile: STORY-9490
"""

import os
from litp_generic_test import GenericTest, attr
import test_constants
from vcs_utils import VCSUtils
from generate import load_fixtures, generate_json, apply_options_changes, \
    apply_item_changes

STORY = '9490'


class Story9490(GenericTest):
    """
    LITPCDS-9490:
    Acceptance Criteria

        I can create more than 1 service within an applications collection of a
            vcs-clustered-service.
        I can specify a dependency between service items, once applied these
            will be dependent VCS Application Resources within
            the VCS Service Group.
        I can create up to a maximum of 10 service items within
            the applications collection

    Out of Scope

        Plugins that use VCS model item types such as Libvrt are responsible
            for handling the new functionality that this story enables
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
        super(Story9490, self).setUp()

        self.management_server = self.get_management_node_filename()

        # specify test data constants

        self.list_managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.list_managed_nodes[0]
        self.vcs = VCSUtils()
        # Location where RPMs to be used are stored
        self.rpm_src_dir = (os.path.dirname(os.path.realpath(__file__)) +
                            '/rpm-out/dist/')

        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.management_server,
                                         '/deployments', 'vcs-cluster')[-1]
        self.cluster_id = self.vcs_cluster_url.split('/')[-1]
        self.nodes_url = self.find(self.management_server,
                                   self.vcs_cluster_url, "node")
        self.nodes_url.sort()

        self.list_of_lsb_rpms = ['EXTR-lsbwrapper-9490-1-1.0-1.noarch.rpm',
                                 'EXTR-lsbwrapper-9490-2-1.0-1.noarch.rpm',
                                 'EXTR-lsbwrapper-9490-3-1.0-1.noarch.rpm',
                                 'EXTR-lsbwrapper-9490-4-1.0-1.noarch.rpm']

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story9490, self).tearDown()

    def baseline(self, vcs_len, app_len, hsc_len, vip_len, cleanup=False,
                 valid_rpm=True):
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
                              vip_length=vip_len,
                              add_to_cleanup=cleanup,
                              valid_rpm=valid_rpm)

        return load_fixtures(
            STORY, self.vcs_cluster_url, self.nodes_url, input_data=_json)

    def cs_nodes_list(self, conf, cs_name, par_mode=1):
        """
        Find nodes_list from LITP model.
        Args:
            - conf (dict): Initial test dataCS or HA deployment path by CS.
            - cs_name (str): clustered-service name.
            - par_mode (int): CS group HA parallel mode.
                (single parallel by default)

        Returns:
                node_vnames (list): Node names.
        """
        # This section of code will add the nodes to the CS
        # Find cluster node urls
        nodes_urls = self.find(self.management_server,
                               self.vcs_cluster_url,
                               'node')
        node_cnt = 0
        node_vnames = []

        if par_mode == 2:
            conf['params_per_cs'][cs_name]['active'] = par_mode
        for node_url in nodes_urls:
            node_cnt += 1
            nr_of_nodes = int(conf['params_per_cs'][cs_name]['active']) + \
                int(conf['params_per_cs'][cs_name]['standby'])

            # Add the node to the cluster
            if node_cnt <= nr_of_nodes:
                node_vnames.append(node_url.split('/')[-1])
        return node_vnames

    def get_node_group_syslist(self, node, cs_name):
        """
        Description:
            Check SystemList vcs attribute from node and specific
                service group.
        Args:
            - node (str): node with installed vcs.
            - cs_name (str): clustered-service name.
        Returns:
            - grp_syslist(str): The output from the command (only node name).
        """
        cs_group_name = \
            self.vcs.generate_clustered_service_name(cs_name,
                                                     self.cluster_id)
        att_systemlist = \
            self.vcs.get_hagrp_value_cmd(cs_group_name, "SystemList")
        # execute the command and take the output.
        stdout = self.assert_get_cmd_out(self.run_command,
                                         node=node,
                                         cmd=att_systemlist, su_root=True)
        return stdout[0].partition('\t')[0]

    def assert_get_cmd_out(self, util, **kwargs):
        """
        Execute litputils func assert execution and return stdout.
        Args:
            - util (object): Litputil func from test framework.
        Returns:
            - stdout (list): Output from executed command.
        """
        stdout, stderr, rc = util(**kwargs)
        self.assertEqual(0, rc)
        self.assertEqual([], stderr)
        return stdout

    def get_res_deps(self, cs_name, app_ids):
        """
        Function to retrieve a CS resources dependencies from VCS.

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
            cmd_arg = '-dep {0}'.format(res)
            hares_cmd = self.vcs.get_hares_cmd(cmd_arg)
            stdout = self.assert_get_cmd_out(self.run_command,
                                             node=self.primary_node,
                                             cmd=hares_cmd, su_root=True)
            deps_list.append([' '.join(i.split()) for i in stdout])
        return deps_list

    @attr('all', 'non-revert', 'story9490',
          'story9490_tc01', 'cdb_priority1')
    def test_01_p_add_four_apps_multi_deps(self):
        """
        @tms_id: litpcds_9490_tc2
        @tms_requirements_id: LITPCDS-9490
        @tms_title: Specify, and deploy, a vcs-clustered-service
        containing 4 multiple services
        @tms_description:
        To ensure that it is possible to specify, and deploy,
        a vcs-clustered-service containing 4 multiple services,
        3 of them with dependencies and two vips (IPv6),
        the fourth in out of any app dependencies.
        Naming of the apps should be "service, service_1, service_2, service_3"
        . Below a vcs-clustered-service of configuration
        active=1 standby=0.
        @tms_test_steps:
        @step:  Create four service objects below the vcs-clustered-service.
        @result: items created
        @step: Create a ha-service-config object for each of the services.
        @result: object created
        @result: The dependency_list - service_1 depends on service_2 and
        service_3, service_2 depends on service_3,
        and service_4 is not depending from any app.
        @step: create and run plan
        @result: plan executes successfully
        @result:  Dependencies are correct and all of the VIPs resources are
        attached to service_3 and service_4 only
        @tms_test_precondition:N/A
        @tms_execution_type: Automated
        """

        fixtures = self.baseline(1, 4, 4, 2, cleanup=False)
        app_list = ['APP_9490_1', 'APP_9490_2', 'APP_9490_3', 'APP_9490_4']

        exp_res_deps = [['#Group Parent Child',
                         'Grp_CS_c1_CS_9490_1 Res_App_c1_CS_9490_1_APP_9490_1 '
                         'Res_IP_c1_CS_9490_1_traffic2_1',
                         'Grp_CS_c1_CS_9490_1 Res_App_c1_CS_9490_1_APP_9490_1 '
                         'Res_IP_c1_CS_9490_1_traffic1_1',
                         'Grp_CS_c1_CS_9490_1 Res_App_c1_CS_9490_1_APP_9490_2 '
                         'Res_App_c1_CS_9490_1_APP_9490_1',
                         'Grp_CS_c1_CS_9490_1 Res_App_c1_CS_9490_1_APP_9490_4 '
                         'Res_App_c1_CS_9490_1_APP_9490_1'],
                        ['#Group Parent Child',
                         'Grp_CS_c1_CS_9490_1 Res_App_c1_CS_9490_1_APP_9490_2 '
                         'Res_App_c1_CS_9490_1_APP_9490_1',
                         'Grp_CS_c1_CS_9490_1 Res_App_c1_CS_9490_1_APP_9490_4 '
                         'Res_App_c1_CS_9490_1_APP_9490_2'],
                        ['#Group Parent Child',
                         'Grp_CS_c1_CS_9490_1 Res_App_c1_CS_9490_1_APP_9490_3 '
                         'Res_IP_c1_CS_9490_1_traffic2_1',
                         'Grp_CS_c1_CS_9490_1 Res_App_c1_CS_9490_1_APP_9490_3 '
                         'Res_IP_c1_CS_9490_1_traffic1_1'],
                        ['#Group Parent Child',
                         'Grp_CS_c1_CS_9490_1 Res_App_c1_CS_9490_1_APP_9490_4 '
                         'Res_App_c1_CS_9490_1_APP_9490_2',
                         'Grp_CS_c1_CS_9490_1 Res_App_c1_CS_9490_1_APP_9490_4 '
                         'Res_App_c1_CS_9490_1_APP_9490_1']]
        # Step 1: Create 4 service objects below the vcs-clustered-service.
        # Step 2: Create a ha-service-config object for each service
        # Step 3: Ensure dependency list service 1 depends on service 2 and 3
        #   and service
        # set cs conf dep path
        cs_url = self.get_cs_conf_url(self.management_server,
                                      fixtures['service'][0]['parent'],
                                      self.vcs_cluster_url)
        # Execute initial plan creation if test data if is not applied already
        if cs_url is None:
            apply_options_changes(
                fixtures,
                'vcs-clustered-service', 0, {'active': '1', 'standby': '0',
                                             'name': 'CS_9490_1',
                                             'node_list': 'n1'},
                overwrite=True)
            apply_item_changes(fixtures, 'ha-service-config', 0,
                               {'parent': "CS_9490_1",
                                'vpath': self.vcs_cluster_url + '/services/'
                                                                'CS_9490_1/'
                                                                'ha_configs/'
                                                                'APP_9490_1'})
            apply_options_changes(fixtures, 'ha-service-config', 0,
                                  {'service_id': 'APP_9490_1'},
                                  overwrite=True)
            apply_options_changes(fixtures, 'vip', 0,
                                  {'network_name': 'traffic1',
                                   'ipaddress':
                                       '2001:1100:82a1:0103:9490::1/64'},
                                  overwrite=True)
            apply_options_changes(fixtures, 'vip', 1,
                                  {'network_name': 'traffic2',
                                   'ipaddress':
                                       '2001:1200:82a1:0103:9490::2/64'},
                                  overwrite=True)

            apply_item_changes(fixtures, 'service', 1,
                               {'parent': "CS_9490_1",
                                'destination': self.vcs_cluster_url +
                                               '/services/CS_9490_1/'
                                               'applications/APP_9490_2'})
            apply_item_changes(fixtures, 'ha-service-config', 1,
                               {'parent': "CS_9490_1",
                                'vpath': self.vcs_cluster_url + '/services/'
                                                                'CS_9490_1/'
                                                                'ha_configs/'
                                                                'APP_9490_2'})
            apply_options_changes(fixtures, 'ha-service-config', 1,
                                  {'dependency_list': 'APP_9490_1',
                                   'service_id': 'APP_9490_2'},
                                  overwrite=True)

            apply_item_changes(fixtures, 'service', 2,
                               {'parent': "CS_9490_1",
                                'destination': self.vcs_cluster_url +
                                               '/services/CS_9490_1/'
                                               'applications/APP_9490_3'})
            apply_item_changes(fixtures, 'ha-service-config', 2,
                               {'parent': "CS_9490_1",
                                'vpath': self.vcs_cluster_url + '/services/'
                                                                'CS_9490_1/'
                                                                'ha_configs/'
                                                                'APP_9490_3'})
            apply_options_changes(fixtures, 'ha-service-config', 2,
                                  {'service_id': 'APP_9490_3'},
                                  overwrite=True)

            apply_item_changes(fixtures, 'service', 3,
                               {'parent': "CS_9490_1",
                                'destination': self.vcs_cluster_url +
                                               '/services/CS_9490_1/'
                                               'applications/APP_9490_4'})
            apply_item_changes(fixtures, 'ha-service-config', 3,
                               {'parent': "CS_9490_1",
                                'vpath': self.vcs_cluster_url + '/services/'
                                                                'CS_9490_1/'
                                                                'ha_configs/'
                                                                'APP_9490_4'})
            apply_options_changes(fixtures, 'ha-service-config', 3,
                                  {'dependency_list': 'APP_9490_1,APP_9490_2',
                                   'service_id': 'APP_9490_4'},
            overwrite=True)

            self.apply_cs_and_apps_sg(
                self.management_server, fixtures, self.rpm_src_dir)
            # This section of the test sets up the model and creates the plan
            self.run_and_check_plan(self.management_server,
                                    test_constants.PLAN_COMPLETE, 10)

        # Step 6.
        res_deps = self.get_res_deps(fixtures['service'][0]['parent'],
                           app_list)
        self.assertEqual(exp_res_deps, res_deps)
        pkgs = []
        for pkg in [a[:-19] for a in self.list_of_lsb_rpms]:
            pkgs.append(pkg)
        self.assertTrue(self.check_pkgs_installed(
            self.get_node_group_syslist(self.list_managed_nodes[0],
                                        'CS_9490_1'),
            pkgs, su_root=True),
            'The packages are not present in target node')

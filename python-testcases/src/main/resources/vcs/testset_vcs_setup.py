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
from redhat_cmd_utils import RHCmdUtils
from vcs_utils import VCSUtils
import test_constants
import os


class Vcssetup(GenericTest):
    """
    LITPCDS-4377
    As a LITP Developer I want to re-work how the VCS plug-in defines Virtual
    IPs so that the plug-in is aligned with the networking model
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
        super(Vcssetup, self).setUp()

        self.rh_os = RHCmdUtils()
        self.management_server = self.get_management_node_filename()
        self.list_managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.list_managed_nodes[0]
        self.primary_node_url = self.get_node_url_from_filename(
        self.management_server, self.primary_node)
        self.vcs = VCSUtils()
        self.traffic_networks = ["traffic1", "traffic2"]
        # Location where RPMs to be used are stored
        self.rpm_src_dir = \
            os.path.dirname(os.path.realpath(__file__)) + \
            "/test_lsb_rpms/"

        # Repo where rpms will be installed
        self.repo_dir_3pp = test_constants.PP_PKG_REPO_DIR

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Vcssetup, self).tearDown()

    def generate_execute_cs_cli(self, conf, vcs_cluster_url, cs_name,
                                app_class="lsb-runtime", node_ordering=False):
        """
        This function will generate and execute the CLI to create
        a clustered services

        Args:
            conf (dict): configuration details for clustered-services

            vcs_cluster_url (str): Model url of vcs cluster item

            cs_name (str): clustered-service name

            app_class (str): class name of the application item

        Returns: -
        """

        # Get CLI commands
        cli_data = self.vcs.generate_cli_commands(vcs_cluster_url,
                                                     conf, cs_name,
                                                     app_class)

        # ===========================================================
        # This section of code will add the nodes to the CS
        # ===========================================================
        # Find cluster node urls
        nodes_urls = self.find(self.management_server,
                               vcs_cluster_url,
                               "node")
        node_cnt = 0
        node_vnames = []

        for node_url in nodes_urls:
            node_cnt = node_cnt + 1
            # Retrieve the nodes hostname - key used to link
            hostname = self.get_props_from_url(self.management_server,
                                               node_url,
                                               'hostname')
            self.assertNotEqual(None, hostname)

            nr_of_nodes = int(conf['params_per_cs'][cs_name]['active']) + \
                          int(conf['params_per_cs'][cs_name]['standby'])

            # Add the node to the cluster
            if node_cnt <= nr_of_nodes:
                node_vnames.append(node_url.split('/')[-1])

        if node_ordering:
            # order the node list according to how they are
            # define in the config
            node_vnames = self.vcs.order_node_list(node_vnames, conf, cs_name)

        # Create Clustered-Service in the model
        cs_options = cli_data['cs']['options'] + \
                     " node_list='{0}'".format(",".join(node_vnames))
        self.execute_cli_create_cmd(self.management_server,
                                    cli_data['cs']['url'],
                                    cli_data['cs']['class_type'],
                                    cs_options,
                                    add_to_cleanup=False)

        # Create lsb apps in the model
        self.execute_cli_create_cmd(self.management_server,
                                    cli_data['apps']['url'],
                                    cli_data['apps']['class_type'],
                                    cli_data['apps']['options'],
                                    add_to_cleanup=False)

        # Create all IPs associated with the lsb-app
        for ip_data in cli_data['ips']:
            self.execute_cli_create_cmd(self.management_server,
                                        ip_data['url'],
                                        ip_data['class_type'],
                                        ip_data['options'],
                                        add_to_cleanup=False)

        # Create all packages associated with lsb-app
        for pkg_data in cli_data['pkgs']:
            self.execute_cli_create_cmd(self.management_server,
                                        pkg_data['url'],
                                        pkg_data['class_type'],
                                        pkg_data['options'],
                                        add_to_cleanup=False)

        # CREATE THE HA SERVICE CONFIG ITEM
        if len(cli_data['ha_service_config'].keys()) > 0:
            self.execute_cli_create_cmd(self.management_server,
                                cli_data['ha_service_config']['url'],
                                cli_data['ha_service_config']['class_type'],
                                cli_data['ha_service_config']['options'],
                                add_to_cleanup=False)

        # Create pkgs under the lsb-app
        for pkg_link_data in cli_data['pkg_links']:
            self.execute_cli_inherit_cmd(self.management_server,
                                        pkg_link_data['child_url'],
                                        pkg_link_data['parent_url'],
                                        add_to_cleanup=False)

        # create inherit to the service
        if app_class in ["service", "vm-service"]:
            self.execute_cli_inherit_cmd(self.management_server,
                                        cli_data['apps']['app_url_in_cluster'],
                                        cli_data['apps']['url'],
                                        add_to_cleanup=False)

    @attr('all', 'non-revert', 'kgb-other', 'cdb_priority1', 'vcssetup_tc01')
    def test_01_deploy_cdb_cs(self):
        """
        Description:
            This test will generate the CLI and run the plan which will
            deploy clustered-services on a CDB system

            It will create a
                2 node failover CS
                2 node parallel
                1 node parallel
                2 node parallel ipV6
                2 node parallel under service item

        Actions:
             1. Add dummy lsb-services to repo
             2. Executes CLI to create model
             3. Create and execute plan

        Results:
            The plan runs successfully
        """
        vcs_cluster_url = self.find(self.management_server,
                                    "/deployments", "vcs-cluster")[-1]

        # ==================================================
        # It is assumed that any rpms required for this test
        # exist in a repo before the plan is executed
        # This section of the test sets this up
        # ===================================================
        # List of rpms required for this test
        list_of_lsb_rpms = [
            "EXTR-lsbwrapper2-1.1.0.rpm",
            "EXTR-lsbwrapper28-1.1.0.rpm",
            "EXTR-lsbwrapper30-1.1.0.rpm",
            "EXTR-lsbwrapper31-1.1.0.rpm",
            "EXTR-lsbwrapper32-1.1.0.rpm",
            "EXTR-lsbwrapper34-1.1.0.rpm",
            "EXTR-lsbwrapper35-1.1.0.rpm",
            "EXTR-lsbwrapper24-1.1.0.rpm",
            "EXTR-lsbwrapper25-1.1.0.rpm"
        ]
        # Copy RPMs to Management Server
        filelist = []
        for rpm in list_of_lsb_rpms:
            filelist.append(self.get_filelist_dict(self.rpm_src_dir + rpm,
                                                   "/tmp/"))

        self.copy_filelist_to(self.management_server, filelist,
                              add_to_cleanup=False, root_copy=True)

        # Use LITP import to add to repo for each RPM
        for rpm in list_of_lsb_rpms:
            self.execute_cli_import_cmd(
                self.management_server,
                '/tmp/' + rpm,
                self.repo_dir_3pp)

        # ===============================================================
        # This section of the test sets up the model and creates the plan
        # ===============================================================
        # Maximum duration of running plan
        plan_timeout_mins = 40

        # Generate configuration for the plan
        # This configuration will contain the configuration for all
        # clustered-services to be created but only CS1 will be used

        list_of_cs_names_orig = ["CS2"]
        list_of_cs_names_service = ["CS28"]
        list_of_cs_names_service_vips = ['CS31', 'CS32', 'CS34', 'CS35']
        list_of_cs_name_priority_order = ['CS24', 'CS25']

        configuration_orig = self.vcs.generate_plan_conf(self.traffic_networks)
        configuration_service = self.vcs.generate_plan_conf_service()
        configuration_service_vips = \
        self.vcs.generate_plan_conf_service_and_vip_children(
                                                         self.traffic_networks)
        conf_srv_prio_order = self.vcs.generate_plan_conf_priority_order()

        for cs_name in list_of_cs_names_orig:
            self.generate_execute_cs_cli(configuration_orig,
                                         vcs_cluster_url,
                                         cs_name)

        for cs_name in list_of_cs_names_service:
            self.generate_execute_cs_cli(configuration_service,
                                         vcs_cluster_url,
                                         cs_name,
                                         app_class="service")

        for cs_name in list_of_cs_names_service_vips:
            self.generate_execute_cs_cli(configuration_service_vips,
                                         vcs_cluster_url, cs_name,
                                         app_class="service")

        for cs_name in list_of_cs_name_priority_order:
            self.generate_execute_cs_cli(conf_srv_prio_order,
                                         vcs_cluster_url,
                                         cs_name, app_class="service",
                                         node_ordering=True)

        # Create and execute plan
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(
            self.management_server,
            test_constants.PLAN_COMPLETE,
            plan_timeout_mins
        ))

    @attr('all', 'non-revert', 'kgb-other', 'cdb_priority1', 'vcssetup_tc02')
    def test_02_verify_cdb_config(self):
        """
        Description:
            This test will verify that clustered-services
            cs2, cs34, CS31, CS32, CS35 have been created.
            The clustered-service were created in a previously
            executed plan

                  Active_cnt standby_cnt
            CS2       1            1
            CS34      1            1
            CS31      1            1
            CS32      2            0
            CS35      1            1
            CS28      2            0

        Actions:
                Verify that the plan has deployed the VCS groups and resources
                modelled correctly

        Results:
            The clustered-services and its resources are
        """
        vcs_cluster_url = self.find(self.management_server,
                                    "/deployments", "vcs-cluster")[-1]

        # ==================================================
        # It is assumed that any rpms required for this test
        # exist in a repo before the plan is executed
        # This section of the test sets this up
        # ===================================================

        list_of_cs_names_orig = ["CS2"]
        list_of_cs_names_service = ["CS28"]
        list_of_cs_names_service_vips = ['CS31', 'CS32', 'CS34', 'CS35']
        list_of_cs_name_priority_order = ['CS24', 'CS25']

        configuration_orig = self.vcs.generate_plan_conf(self.traffic_networks)
        configuration_service = self.vcs.generate_plan_conf_service()
        configuration_service_vips = \
        self.vcs.generate_plan_conf_service_and_vip_children(
                                                         self.traffic_networks)
        conf_srv_prio_order = self.vcs.generate_plan_conf_priority_order()

        vcs_cluster_url = self.find(self.management_server,
                                    "/deployments", "vcs-cluster")[-1]
        cluster_id = vcs_cluster_url.split("/")[-1]

        nodes_urls = self.find(self.management_server,
                               vcs_cluster_url,
                               "node")

        # =============================================================
        # This part of the test will retrieve all the data required
        # to verify that the clustered-services has been setup correctly
        # =============================================================

        # Output from hasys -state command
        cmd = self.vcs.get_hasys_state_cmd()
        hasys_output, stderr, return_code = self.run_command(self.primary_node,
                cmd, su_root=True)
        self.assertEqual(0, return_code)
        self.assertEqual([], stderr)
        self.assertTrue(self.vcs.verify_vcs_systems_ok(nodes_urls,
                                                          hasys_output))

        # Output from the hagrp -state command
        cmd = self.vcs.get_hagrp_state_cmd()
        hagrp_output, stderr, return_code = self.run_command(self.primary_node,
                cmd, su_root=True)
        self.assertEqual(0, return_code)
        self.assertEqual([], stderr)

        # Output from the hares -state command
        cmd = self.vcs.get_hares_state_cmd()
        hares_output, stderr, return_code = self.run_command(self.primary_node,
                cmd, su_root=True)
        self.assertEqual(0, return_code)
        self.assertEqual([], stderr)

        # Determine the device that each network is on
        network_dev_map = self.get_node_network_devices(self.management_server,
                                                        self.primary_node_url)

        # Verify the deployment of all Clustered-services
        self.verify_deployments_by_node(list_of_cs_names_orig, cluster_id,
                                        configuration_orig, hagrp_output,
                                        hares_output, network_dev_map,
                                        self.list_managed_nodes)

        self.verify_deployments_by_node(list_of_cs_names_service_vips,
                                        cluster_id,
                                        configuration_service_vips,
                                        hagrp_output, hares_output,
                                        network_dev_map,
                                        self.list_managed_nodes)

        self.verify_deployments_by_node(list_of_cs_names_service, cluster_id,
                                        configuration_service, hagrp_output,
                                        hares_output, network_dev_map,
                                        self.list_managed_nodes)

        self.verify_deployments_by_node(list_of_cs_name_priority_order,
                                        cluster_id, conf_srv_prio_order,
                                        hagrp_output, hares_output,
                                        network_dev_map,
                                        self.list_managed_nodes)

    @attr('all', 'non-revert', 'kgb-other', 'vcs_deploy_setup',
          'vcssetup_tc03')
    def test_03_deploy_cs(self):
        """
        Description:
            This test will generate the CLI and run the plan which will
            deploy clustered-services which will then be used to by other
            tests

        Actions:
             1. Add dummy lsb-services to repo
             2. Executes CLI to create model
             3. Create and execute plan

        Results:
            The plan runs successfully
        """
        vcs_cluster_url = self.find(self.management_server,
                                    "/deployments", "vcs-cluster")[-1]

        # ==================================================
        # It is assumed that any rpms required for this test
        # exist in a repo before the plan is executed
        # This section of the test sets this up
        # ===================================================
        # List of rpms required for this test
        list_of_lsb_rpms = [
            "EXTR-lsbwrapper1-1.1.0.rpm",
            "EXTR-lsbwrapper3-1.1.0.rpm",
            "EXTR-lsbwrapper4-1.1.0.rpm",
            "EXTR-lsbwrapper5-1.1.0.rpm",
            "EXTR-lsbwrapper23-1.1.0.rpm",
            "EXTR-lsbwrapper6-1.1.0.rpm",
            "EXTR-lsbwrapper7-1.1.0.rpm",
            "EXTR-lsbwrapper8-1.1.0.rpm",
            "EXTR-lsbwrapper9-1.1.0.rpm",
            "EXTR-lsbwrapper10-1.1.0.rpm",
            "EXTR-lsbwrapper11-1.1.0.rpm",
            "EXTR-lsbwrapper12-1.1.0.rpm",
            "EXTR-lsbwrapper13-1.1.0.rpm",
            "EXTR-lsbwrapper14-1.1.0.rpm",
            "EXTR-lsbwrapper15-1.1.0.rpm",
            "EXTR-lsbwrapper16-1.1.0.rpm",
            "EXTR-lsbwrapper17-1.1.0.rpm",
            "EXTR-lsbwrapper18-1.1.0.rpm",
            "EXTR-lsbwrapper20-1.1.0.rpm",
            "EXTR-lsbwrapper21-1.1.0.rpm",
            "EXTR-lsbwrapper29-1.1.0.rpm",
            "EXTR-lsbwrapper30-1.1.0.rpm",
            "EXTR-lsbwrapper33-1.1.0.rpm",
            "EXTR-lsbwrapper36-1.1.0.rpm"

        ]
        # Copy RPMs to Management Server
        filelist = []
        for rpm in list_of_lsb_rpms:
            filelist.append(self.get_filelist_dict(self.rpm_src_dir + rpm,
                                                   "/tmp/"))

        self.copy_filelist_to(self.management_server, filelist,
                              add_to_cleanup=False, root_copy=True)

        # Use LITP import to add to repo for each RPM
        for rpm in list_of_lsb_rpms:
            self.execute_cli_import_cmd(
                self.management_server,
                '/tmp/' + rpm,
                self.repo_dir_3pp)

        # ===============================================================
        # This section of the test sets up the model and creates the plan
        # ===============================================================
        # Maximum duration of running plan
        plan_timeout_mins = 120

        # Generate configuration for the plan
        # This configuration will contain the configuration for all
        # clustered-services to be created but only CS1 will be used

        list_of_cs_names_orig = ["CS1", "CS6", "CS7", "CS9", "CS10", "CS12",
                                 "CS4", "CS3", "CS5", "CS8", "CS11",
                                 "CS13", "CS14", "CS15"]
        list_of_cs_names_ipv6 = ["CS16", "CS17", "CS18", "CS20", "CS21"]
        list_of_cs_names_service = ["CS29", "CS30"]
        list_of_cs_names_service_vips = ["CS33"]
        list_of_cs_names_serv_ha_conf = ["CS36"]

        configuration_orig = self.vcs.generate_plan_conf(self.traffic_networks)
        configuration_ipv6 = \
                          self.vcs.generate_plan_conf_v6(self.traffic_networks)
        configuration_service = self.vcs.generate_plan_conf_service()
        configuration_service_vips = \
                          self.vcs.generate_plan_conf_service_and_vip_children(
                                                         self.traffic_networks)
        configuration_service_ha_config = \
                                self.vcs.generate_plan_conf_ha_service_config()

        for cs_name in list_of_cs_names_orig:
            self.generate_execute_cs_cli(configuration_orig,
                                         vcs_cluster_url,
                                         cs_name)

        for cs_name in list_of_cs_names_ipv6:
            self.generate_execute_cs_cli(configuration_ipv6,
                                         vcs_cluster_url,
                                         cs_name)
        for cs_name in list_of_cs_names_service:
            self.generate_execute_cs_cli(configuration_service,
                                         vcs_cluster_url,
                                         cs_name, app_class="service")
        for cs_name in list_of_cs_names_service_vips:
            self.generate_execute_cs_cli(configuration_service_vips,
                                         vcs_cluster_url,
                                         cs_name, app_class="service")

        for cs_name in list_of_cs_names_serv_ha_conf:
            self.generate_execute_cs_cli(configuration_service_ha_config,
                                         vcs_cluster_url,
                                         cs_name, app_class="service")
        # Create and execute plan
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(
            self.management_server,
            test_constants.PLAN_COMPLETE,
            plan_timeout_mins
        ))

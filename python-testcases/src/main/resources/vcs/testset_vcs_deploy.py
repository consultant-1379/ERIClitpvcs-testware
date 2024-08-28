"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     July 2016
@author:    James Langan
@summary:   Initial Deployment script for VCS CS used in both CDB and KGB.
            Agile:
"""

import os
from litp_generic_test import GenericTest, attr
import test_constants
from litp_cli_utils import CLIUtils
from vcs_utils import VCSUtils


class Vcsdeploy(GenericTest):
    """
    Deployment Script which can load /software/services, /software/items
    and vcs-clustered-service configuration from a previously exported XML
    file and create/run plan until all VCS CS are deployed.
    """

    def setUp(self):
        """
        Description:
            Runs before every single test
        Actions:
            1. Call the super class setup method
            2. Set up variables used in the tests
        Results:
            The super class prints out diagnostics and variables
            common to all tests are available.
        """
        super(Vcsdeploy, self).setUp()

        self.ms_node = self.get_management_node_filename()
        self.cliutils = CLIUtils()
        self.vcsutils = VCSUtils()

        self.rpm_src_dir = \
            os.path.dirname(os.path.realpath(__file__)) + \
            "/test_lsb_rpms/"
        self.repo_dir_3pp = test_constants.PP_PKG_REPO_DIR

        self.xml_dir = os.path.dirname(os.path.realpath(__file__)) + '/'

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            1. Perform Test Cleanup
            2. Call superclass teardown
        Results:
            Items used in the test are cleaned up and the
            super class prints out end test diagnostics
        """
        super(Vcsdeploy, self).tearDown()

    @attr('all', 'non-revert', 'deploy_service_groups_tc01')
    def test_deploy_service_groups_tc01(self):
        """
        @tms_id: test_deploy_service_groups_tc01
        @tms_requirements_id: LITPCDS-8361, LITPCDS-4848, LITPCDS-4377,
        LITPCDS-4003, LITPCDS-3995, LITPCDS-3986, LITPCDS-2207, LITPCDS-5768,
        LITPCDS-6164, LITPCDS-6296, LITPCDS-5938, TORF-285704

        @tms_title: Deploy 10 VCS Services Groups
        @tms_description: Initial deployment of 10 vcs cluster services
        including Failover, Parallel 1 node, and Parallel 2 node, all with
        varying configurations.

        @tms_test_steps:
            @step: Import the 12 packages to be used during deployement
            @result: The 12 packages are imported successfully
            @step: Load software_items.xml using --merge option
            @result: software items are successfully merged into LITP model
            @step: Load software_services.xml using --merge option
            @result: software services are successfully merged into LITP model
            @step: Load service_groups.xml using --merge option
            @result: vcs-clustered-services successfully merged into LITP model
            @step: Create and run plan
            @result: Plan is created and completes successfully

        @tms_test_precondition: A 2 node LITP cluster is installed.
        @tms_execution_type: Automated
        """
        # Copy XML files to MS for test execution
        xml_list = ['software_items.xml',
                    'software_services.xml',
                    'service_groups.xml']

        filelist = []
        for xmls in xml_list:
            filelist.append(self.get_filelist_dict(self.xml_dir + xmls,
                                                   "/home/litp-admin/"))

        self.copy_filelist_to(self.ms_node, filelist, add_to_cleanup=False)

        plan_timeout_mins = 30
        # EXTR-lsbwrapper40-1.1.0.rpm added for TORF-285704
        # SERVICE ID IN service_groups.xml IS OVER 60 chars
        # IN ORDER TO TRIGGER CONCATENATION ERROR FROM
        # ORIGINAL REGEX.
        list_of_lsb_rpms = ['EXTR-lsbwrapper1-1.1.0.rpm',
                            'EXTR-lsbwrapper2-1.1.0.rpm',
                            'EXTR-lsbwrapper3-1.1.0.rpm',
                            'EXTR-lsbwrapper4-1.1.0.rpm',
                            'EXTR-lsbwrapper5-1.1.0.rpm',
                            'EXTR-lsbwrapper6-1.1.0.rpm',
                            'EXTR-lsbwrapper7-1.1.0.rpm',
                            'EXTR-lsbwrapper8-1.1.0.rpm',
                            'EXTR-lsbwrapper9-1.1.0.rpm',
                            'EXTR-lsbwrapper10-1.1.0.rpm',
                            'EXTR-lsbwrapper11-1.1.0.rpm',
                            'EXTR-lsbwrapper12-1.1.0.rpm',
                            'EXTR-lsbwrapper40-1.1.0.rpm']

        # Copy RPMs to Management Server
        filelist = []
        for rpm in list_of_lsb_rpms:
            filelist.append(self.get_filelist_dict(self.rpm_src_dir + rpm,
                                                   "/tmp/"))

        self.copy_filelist_to(self.ms_node, filelist,
                              add_to_cleanup=False, root_copy=True)

        for rpm in list_of_lsb_rpms:
            self.execute_cli_import_cmd(
                self.ms_node,
                '/tmp/' + rpm,
                self.repo_dir_3pp)

        software_url = '/software'
        filepath1 = '/home/litp-admin/software_items.xml'
        self.execute_cli_load_cmd(self.ms_node,
                                  software_url,
                                  filepath1,
                                  '--merge')

        filepath2 = '/home/litp-admin/software_services.xml'
        self.execute_cli_load_cmd(self.ms_node,
                                  software_url,
                                  filepath2,
                                  '--merge')

        filepath3 = '/home/litp-admin/service_groups.xml'

        # Current assumption is that only 1 VCS cluster will exist
        vcs_cluster_url = \
            self.find(self.ms_node, "/deployments", "vcs-cluster")[-1]
        self.execute_cli_load_cmd(self.ms_node,
                                  vcs_cluster_url,
                                  filepath3,
                                  '--merge')

        self.execute_cli_createplan_cmd(self.ms_node)
        self.execute_cli_runplan_cmd(self.ms_node)

        self.assertTrue(self.wait_for_plan_state(
            self.ms_node,
            test_constants.PLAN_COMPLETE,
            plan_timeout_mins
        ))

"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     March 2015
@author:    Boyan Mihovski
@summary:   Integration
            Agile: STORY-8361
"""

from litp_generic_test import GenericTest, attr
from litp_cli_utils import CLIUtils
import test_constants
from vcs_utils import VCSUtils


class Story8361(GenericTest):
    """
    LITPCDS-8361:
    I can set the following properties for a clustered-service
        offline_timeout default 300 seconds
        online_timeout default 300 seconds
    Only positive integers can be used for the timeout values.
    For VCS clustered services, the online_timeout
        must be applied to the OnlineTimeout attribute
        of the Application Resource.
    For VCS clustered services, the offline_timeout
        must be applied to the OfflineTimeout attribute
        of the Application Resource.
    When a clustered service is being brought online the task
        must take the startup_retry_limit into account,
        so the max time given for the task to online will be
        online_timeout + (startup_retry_limit*online_timeout)
    When a node is being unlocked, the time allowed by LITP
        to unlock the node will be the largest online time
        (as calculated in the previous acceptance criteria)
        of all clustered services in the cluster.
    When a node is being locked, the time allowed by LITP
        to lock the node will be the largest online time of all
        clustered services in the cluster plus the largest value
        for offline_timeout of all clustered services in the cluster.

    """
    # specify test data constants
    NOT_DEFAULT_ONLINE_TIMEOUT = "180"
    NOT_DEFAULT_OFFLINE_TIMEOUT = "401"

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
        super(Story8361, self).setUp()

        self.management_server = self.get_management_node_filename()
        self.vcs = VCSUtils()
        self.cli = CLIUtils()

        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.management_server,
                                         "/deployments", "vcs-cluster")[-1]
        self.cluster_id = self.vcs_cluster_url.split("/")[-1]

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story8361, self).tearDown()

    def get_cs_name_timeouts(self, service_ref_url):
        """
        Function to get the name property value of the parent clustered service
        of the provided vm-service url
        Args:
            - service_ref_url (str): The url of the inherited vm-service
                                     below the vcs-clustered-service object.

        Returns:
                cs_name (str): CS name per deployment.
                online_timeout (str): Online timeout from deployment.
                offline_timeout (str): Offline timeout from deployment.
        """
        # split url and move back up to parent.
        cs_name = \
            self.get_props_from_url(self.management_server,
                                    service_ref_url, "name")
        online_timeout = \
            self.get_props_from_url(self.management_server,
                                    service_ref_url, "online_timeout")
        offline_timeout = \
            self.get_props_from_url(self.management_server,
                                    service_ref_url, "offline_timeout")

        return cs_name, online_timeout, offline_timeout

    def find_setup_clustered_services_not_empty(self):
        """
        Function to get the clustered services, create by the setup tests,
        filtering out any CSs that are empty
        Args:

        Returns:
                clustered_service (str): URL of clustered service in model.
        """
        clustered_services = list()
        # get any two clustered services from the model
        # why do we need two CSs for this? isn't one enough?
        cl_services = self.find(
            self.management_server, '/deployments', 'vcs-clustered-service'
        )
        # return only CSs created by setup
        cl_services[:] = [
            cs_
            for cs_ in cl_services
            if 'CS' in cs_.split('/')[-1]
        ]
        # filter out any CSs that are empty
        # we do this by checking if they have children under their colletion
        for cs_ in cl_services:
            show_cmd = self.cli.get_show_cmd('{0}/applications'.format(cs_))
            stdout, stderr, rcode = self.run_command(
                self.management_server, show_cmd
            )
            self.assertEqual(0, rcode)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            if 'children:' in stdout:
                clustered_services.append(cs_)
        # get the last two CSs from list
        return clustered_services[-2:]

    def online_offline_timeouts_in_model(self, cs_):
        """
        Function to get the online and offline timeout values that are set in
        the LITP model for a particular clustered service
        Args:
            - cs_ (str): The url of the clustered service

        Returns:
                online_timeout (str): Online timeout from LITP model.
                offline_timeout (str): Offline timeout from LITP model.
        """
        # get online_timeout value from model
        online_timeout_model = self.execute_show_data_cmd(
            self.management_server, cs_, 'online_timeout'
        )
        # get offline_timeout value from model
        offline_timeout_model = self.execute_show_data_cmd(
            self.management_server, cs_, 'offline_timeout'
        )
        return online_timeout_model, offline_timeout_model

    def online_offline_timeouts_node(self, cs_, node_to_exe):
        """
        Function to get the online and offline timeout values configured
        on the managed node
        Args:
            - cs_ (str): The url of the clustered service
            - node_to_exe: The managed node object to execute on

        Returns:
                online_timeout (str): Online timeout configured on the node.
                offline_timeout (str): Offline timeout configured on the node.
        """
        # get the timeout values for the CS from the node
        cs_name, _, _ = \
            self.get_cs_name_timeouts(cs_)
        # get application_id
        cs_app, _, _ = self.execute_cli_show_cmd(
            self.management_server, '{0}/applications'.format(cs_)
        )
        cs_app_id = cs_app[-1].lstrip('/')
        resource_id = self.vcs.generate_application_resource_name(
            cs_name, self.cluster_id, cs_app_id
        )
        online_timeout_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'OnlineTimeout'
        )
        stdout, stderr, rcode = self.run_command(
            node_to_exe, online_timeout_res_cmd, su_root=True
        )
        self.assertEqual(0, rcode)
        self.assertEqual([], stderr)
        self.assertNotEqual([], stdout)
        online_timeout_node = stdout[0]
        offline_timeout_res_cmd = self.vcs.get_hares_resource_attr(
            resource_id, 'OfflineTimeout'
        )
        stdout, stderr, rcode = self.run_command(
            node_to_exe, offline_timeout_res_cmd, su_root=True
        )
        self.assertEqual(0, rcode)
        self.assertEqual([], stderr)
        self.assertNotEqual([], stdout)
        offline_timeout_node = stdout[0]
        return online_timeout_node, offline_timeout_node

    @attr('all', 'non-revert', 'story8361',
          'story8361_tc08', 'cdb_priority1')
    def test_08_p_check_CS_onlinetimeout_offlinetimeout_node(self):
        """
        @tms_id: litpcds_8361_tc08
        @tms_requirements_id: LITPCDS-8361
        @tms_title: Check CS offline/online timeouts
        @tms_description:
         Get a basic VCS cluster service application that is deployed by setup
         and verify the default values for the clustered service in the model
         and on the node. When these values are updated, after create and run
         plan, ensure the updates are applied on the node.
        @tms_test_steps:
        @step: Get node data from the model
        @result: Relevant node data is stored
        @step: Store the online/offline timeouts present in the model
        @result: Timeouts are stored
        @step: Store the offline/online timeouts on the node
        @result: Values are stored
        @step: Assert the online/offline timeout values from the node are equal
        to timeout values in the model, for each of the clustered services.
        @result: The above is asserted true.
        @step: Update the CS timeout values to "OnlineTimeout=180"
                                                "OfflineTimeout=401"
        @result: Timeout values updated
        @step: Execute create plan command
        @result: Plan is created
        @step: Execute run plan command
        @result: Plan is running
        @step: Assert plan completes successfully.
        @result: Plan is successful.
        @step: Assert that the online timeout on the node is equal to the new
        online timeout value set in the model.
        @result: The above is successfully asserted.
        @step: Assert that the offline timeout on the node is equal to the new
        offline timeout value set in the model.
        @result: The above is successfully asserted.
        @result: Updates were applied successfully.
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        # take node data from the model
        node_url = self.find(self.management_server, "/deployments", "node")
        # Execute test data
        #self.apply_cs_and_apps()
        # Test one when offline timeout is default
        node_to_exe = self.get_node_filename_from_url(self.management_server,
                                                      node_url[0])
        clustered_services = self.find_setup_clustered_services_not_empty()
        online_timeout_model, offline_timeout_model = \
            self.online_offline_timeouts_in_model(clustered_services[0])
        online_timeout_node, offline_timeout_node = \
            self.online_offline_timeouts_node(
                clustered_services[0], node_to_exe
            )
        # assert online/offline timeout from node equal to timeout values
        # in model
        self.assertEqual(online_timeout_model, online_timeout_node)
        self.assertEqual(offline_timeout_model, offline_timeout_node)
        online_timeout_model, offline_timeout_model = \
            self.online_offline_timeouts_in_model(clustered_services[1])
        online_timeout_node, offline_timeout_node = \
            self.online_offline_timeouts_node(
                clustered_services[1], node_to_exe
            )
        # assert online/offline timeout from node equal to timeout values
        # in model
        self.assertEqual(online_timeout_model, online_timeout_node)
        self.assertEqual(offline_timeout_model, offline_timeout_node)
        # update cs timeout values
        self.execute_cli_update_cmd(
            self.management_server, clustered_services[0],
            'online_timeout={0}'.format(Story8361.NOT_DEFAULT_ONLINE_TIMEOUT)
        )
        self.execute_cli_update_cmd(
            self.management_server, clustered_services[1],
            'offline_timeout={0}'.format(
                Story8361.NOT_DEFAULT_OFFLINE_TIMEOUT
            )
        )
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)
        self.assertTrue(
            self.wait_for_plan_state(
                self.management_server, test_constants.PLAN_COMPLETE
            )
        )
        online_timeout_node, offline_timeout_node = \
            self.online_offline_timeouts_node(
                clustered_services[0], node_to_exe
            )
        # assert online/offline timeout from node equal to timeout values
        # in model
        self.assertEqual(
            Story8361.NOT_DEFAULT_ONLINE_TIMEOUT, online_timeout_node
        )
        self.assertEqual(
            offline_timeout_model, offline_timeout_node
        )
        online_timeout_node, offline_timeout_node = \
            self.online_offline_timeouts_node(
                clustered_services[1], node_to_exe
            )
        self.assertEqual(
            Story8361.NOT_DEFAULT_OFFLINE_TIMEOUT, offline_timeout_node
        )
        self.assertEqual(
            online_timeout_model, online_timeout_node
        )

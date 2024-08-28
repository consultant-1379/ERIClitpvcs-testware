"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     July 2016
@author:    Ciaran Reilly, James Langan
@summary:   Agile: TORF: 107491
"""

from litp_generic_test import GenericTest, attr
from vcs_utils import VCSUtils
from redhat_cmd_utils import RHCmdUtils
from test_constants import VCS_MAIN_CF_FILENAME


class Story107491(GenericTest):
    """
    As a LITP user i want to reconfigure my split brain protection so that i
    can expand my SFHA cluster
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
            are defined which are required in the tests.
        """
        super(Story107491, self).setUp()
        self.management_server = self.get_management_node_filename()
        self.vcs = VCSUtils()
        self.rh_cmds = RHCmdUtils()
        self.managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.managed_nodes[0]

        self.vcs_cluster_url = self.find(self.management_server,
                                         "/deployments", "vcs-cluster")[-1]
        self.cluster_id = self.vcs_cluster_url.split("/")[-1]

        self.nodes_urls = self.find(self.management_server,
                                    self.vcs_cluster_url,
                                    'node')
        self.node_ids = [node.split('/')[-1] for node in self.nodes_urls]

        self.node_list = []
        for nodes in self.nodes_urls:
            self.node_list.append(self.get_node_filename_from_url(
                self.management_server, nodes))

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            1. Call superclass teardown
        """
        super(Story107491, self).tearDown()

    def _check_disk_based_fencing(self):
        """
        This Method will verify the disk based fencing configuration on a
        physical deployment.
        :return: Nothing
        """
        gabconfig_cmd = 'gabconfig -a'
        vxfenadm_cmd = 'vxfenadm -d'
        vxfenmode_dir = '/etc/vxfenmode'
        vxfentab_dir = '/etc/vxfentab'
        vx_running = 'node   {0} in state  8 (running)'

        # Verify fencing is correctly configured on nodes
        self.log('info', 'Verifying fencing is configured on nodes by '
                         'checking if Port b exists')
        for node in self.node_list:
            gabconfig_output = self.run_command(node, gabconfig_cmd,
                                                su_root=True,
                                                default_asserts=True)
            self.assertTrue(self.is_text_in_list('Port b gen',
                                                 gabconfig_output[0]))

            # Verify fencing is running on nodes
            self.log('info', 'Checking fencing is running on nodes')
            vxfenadm_output = self.run_command(node, vxfenadm_cmd,
                                               su_root=True,
                                               default_asserts=True)[0]
            node_astric = [active_node for active_node in vxfenadm_output
                           if '*' in active_node][0]
            node_id = node_astric.split()[1]
            self.assertTrue(self.is_text_in_list(vx_running.format(node_id),
                                                 vxfenadm_output))

            # Verify fencing configuration on nodes corresponds to main.cf
            # configuration
            self.log('info', 'Verfiying node configurations match main.cf '
                             'configuration')
            cat_cmd = self.rh_cmds.get_cat_cmd(vxfenmode_dir)
            vxfenout = self.run_command(node, cat_cmd, su_root=True,
                                        default_asserts=True)[0]
            vxfenmode = [vx_mode for vx_mode in vxfenout if 'vxfen_mode' in
                         vx_mode][0].split('vxfen_mode=')[1].upper()

            grep_cmd = \
                self.rh_cmds.get_grep_file_cmd(filepath=VCS_MAIN_CF_FILENAME,
                                               grep_items=[vxfenmode])
            maincf_out = self.run_command(node, grep_cmd, su_root=True,
                                          default_asserts=True)[0]

            self.assertEqual("UseFence = {0}".format(vxfenmode),
                             maincf_out[0])

            # Verify fencing disk type on nodes
            self.log('info', 'Verfiy disk types on nodes')
            cat_cmd = self.rh_cmds.get_cat_cmd('/etc/vxfendg')
            vxtypeout = self.run_command(node, cat_cmd, su_root=True,
                                         default_asserts=True)[0]
            self.assertEqual(vxtypeout[0].split('vxfen')[0], '')

            # Verify the number of nodes seen in vxfentab with the litp model
            self.log('info', 'Verifying the co-ordinator disks on nodes '
                             'seen in vxfentab')
            grep_cmd = \
                self.rh_cmds.get_grep_file_cmd(filepath=vxfentab_dir,
                                               grep_items='/dev')
            numdisk = self.run_command(node, grep_cmd, su_root=True,
                                       default_asserts=True)[0]
            self.assertEqual(len(numdisk), 3)

    def _get_LLT_network_interfaces(self, node_url):
        """
        Method to obtain all of the HB network interfaces from nodes and
        determine which interfaces to bring down

        Variables:
            node_url: (str) Used to obtain interfaces on node
        :return:
        """
        net_interfaces = self.find(self.management_server,
                                   node_url + '/',
                                   'eth')
        netinterfaces_dict = {"Network_name": [], "Dev_Name": []}
        for interfaces in net_interfaces:
            net_name = self.get_props_from_url(self.management_server,
                                               interfaces,
                                               filter_prop="network_name")
            dev_name = self.get_props_from_url(self.management_server,
                                               interfaces,
                                               filter_prop="device_name")
            if net_name == "heartbeat1" or net_name == "heartbeat2":
                netinterfaces_dict["Network_name"].append(net_name)
                netinterfaces_dict["Dev_Name"].append(dev_name)
            elif net_name == "hb1" or net_name == "hb2":
                netinterfaces_dict["Network_name"].append(net_name)
                netinterfaces_dict["Dev_Name"].append(dev_name)
            else:
                continue
        return netinterfaces_dict

    @attr('all', 'kgb-physical', 'story107491', 'story107491_tc01')
    def test_01_p_check_fencing_conf(self):
        """
        @tms_id: test_01_p_check_fencing_conf
        @tms_requirements_id: TORF-107491

        @tms_title: Shared Disk Fencing validation checks
        @tms_description: Test to validate that a cluster at initial
            installation can be created with disk fencing configured and the
            nodes will have fencing disks configured

        @tms_test_steps:
            @step: Validate fencing is correctly configured on nodes
            @result: Fencing is configured on nodes by verifying Port-b exists
            @step: Verify fencing is running on nodes
            @result: Fencing is running on all nodes through vxfenadm -d
            @step: Validate fencing configuration on nodes corresponds to
            main.cf
            @result: Fencing and main.cf correspond to each other
            @step: Validate fencing disk type on nodes are as expected 'vxfen'
            @result: Disk type on nodes are as expected 'vxfen'
            @step: Verify the number of nodes are mapped to the number of
            nodes seen in vxfentab
            @result: Nodes count matches vxfentab output

        @tms_test_precondition: PCDB 2 node has run
        @tms_execution_type: Automated
        """

        self._check_disk_based_fencing()

    @attr('all', 'kgb-physical', 'story107491', 'story107491_tc02')
    def test_02_p_check_fencing_conf_during_4_node_expansion(self):
        """
        @tms_id: test_02_p_check_fencing_conf_during_4_node_expansion
        @tms_requirements_id: TORF-107491

        @tms_title: Shared Disk Fencing validation checks
        @tms_description: Test to validate that a cluster during upgrade can
            be expanded with disk fencing configured and the nodes will have
            fencing disks configured.

        @tms_test_steps:
            @step: Validate fencing is correctly configured on nodes
            @result: Fencing is configured on nodes by verifying Port-b exists
            @step: Verify fencing is running on nodes
            @result: Fencing is running on all nodes through vxfenadm -d
            @step: Validate fencing configuration on nodes corresponds to
            main.cf
            @result: Fencing and main.cf correspond to each other
            @step: Validate fencing disk type on nodes are as expected 'vxfen'
            @result: Disk type on nodes are as expected 'vxfen'
            @step: Verify the number of nodes are mapped to the number of
            nodes seen in vxfentab
            @result: Nodes count matches vxfentab output

        @tms_test_precondition: PCDB 4node expansion has run
        @tms_execution_type: Automated
        """

        # NOTE: Step 2 is verified during plan execution

        self._check_disk_based_fencing()

    @attr('manual', 'kgb-physical', 'story107491')
    def test_04_n_vcs_split_brain_check_after_expansion(self):
        """
        @tms_id: test_04_n_vcs_split_brain_check_after_expansion
        @tms_requirements_id: TORF-107491

        @tms_title: Split Brain verification after 4 node expansion
        @tms_description: Test to validate that a vcs cluster after
            undergoing expansion with disk based fencing, maintains
            split-brain protection by bringing down llt links and
            stopping puppet

        @tms_test_steps:
            @step: Gather HB and LLT networks from LITP model
            @result: HB and LLT network are obtained from litp model
            @step: Stop Puppet daemon on all nodes
            @result: Puppet is stopped
            @step: Verify Puppet is stopped on all nodes
            @result: Puppet is stopped on all nodes
            @step: Run command "ifdown br0 (low_prio_net) ;
            ifdown eth4 (LLT) ; ifdown eth5 (LLT)"
            @result: llt links are brought down
            @step: Validate logs have correct information on nodes
            @result: logs are verified and have correct information
            @step: Ensure puppet is restarted
            @result: Puppet is running

        @tms_test_precondition: Local Physical deployment with fencing
        @tms_execution_type: Manual
        """
        llt_cmd = 'lltstat -l | grep lowpri'
        ifdown_cmd = '/sbin/ifdown {0}'
        network_intsdict = []

        # Gather LLT network from LITP model
        for node_url, exec_node in zip(self.nodes_urls, self.node_list):
            network_intsdict.append(self._get_LLT_network_interfaces(node_url))

            # Stop Puppet service on all nodes
            self.get_service_status(exec_node, 'puppet')
            self.stop_service(exec_node, 'puppet')
            # Verify Puppet is stopped on all nodes
            self.get_service_status(exec_node, 'puppet', assert_running=False)

        lltstat_output = self.run_command(self.node_list[0], llt_cmd,
                                          su_root=True,
                                          default_asserts=True)[0]

        self.assertTrue(len(lltstat_output[0].split()) > 2)

        lltstat_output = lltstat_output[0].split()[2]

        network_ints = [network_intsdict[0].values()[0][0],
                        network_intsdict[1].values()[0][1],
                        lltstat_output]

        for node_interfaces in network_ints:
            # Bring LLT links down to cause split brain
            self.run_command(self.node_list[0],
                             ifdown_cmd.format(node_interfaces), su_root=True,
                             connection_timeout_secs=10,
                             execute_timeout=0.1, su_timeout_secs=10)

        # Validate logs have correct information on node
        log_messages = ['Initiating Race for Coordination Point',
                        'Completed Fencing Operation.']
        self.assertTrue(self.wait_for_log_msg(self.node_list[1], log_messages))

        # Ensure Puppet and interfaces are back running
        self.assertTrue(self.wait_for_node_up(self.node_list[0],
                                              timeout_mins=15))
        for interfaces in [network_ints[0], network_ints[1]]:
            for node in self.node_list:
                self.run_command(node, '/sbin/ifup {0}'.format(interfaces),
                                 su_root=True, default_asserts=True)

"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     October 2016
@author:    Ciaran Reilly
@summary:   Agile: TORF: 106941
"""

from litp_generic_test import GenericTest, attr
from vcs_utils import VCSUtils
from redhat_cmd_utils import RHCmdUtils
from test_constants import PLAN_COMPLETE
import time
import os


class Story106941(GenericTest):
    """
    As a LITP user I want to extend my lun disk and the LVM volumes that are
    on it so that I can increase capacity

    NOTE: The test cases for this story involves manually setting up a suitable
    environment with SCSI disks available on the MNs in the cluster.

    The reason this is needed is to simulate the SAN plugin normally used to
    manage disk expansion for the litp model
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
        super(Story106941, self).setUp()
        self.management_server = self.get_management_node_filename()
        self.vcs = VCSUtils()
        self.rh_cmds = RHCmdUtils()

        self.vcs_cluster_url = self.find(self.management_server,
                                         "/deployments", "vcs-cluster")[-1]
        self.cluster_id = self.vcs_cluster_url.split("/")[-1]

        self.nodes_urls = self.find(self.management_server,
                                    self.vcs_cluster_url,
                                    'node')
        self.node_exe = []
        for nodes in self.nodes_urls:
            self.node_exe.append(self.get_node_filename_from_url(
                self.management_server, nodes))

        self.sys_url = self.find(self.management_server,
                                 "/infrastructure/systems",
                                 "collection-of-system")[0]

        self.physical_dev_url = self.find(self.management_server,
                                          "/infrastructure",
                                          "collection-of-physical-device")[-1]

        self.fs_url = self.find(self.management_server, "/infrastructure",
                                "collection-of-file-system")[-1]

        self.loc_dir = os.path.dirname(os.path.realpath(__file__))

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            1. Call superclass teardown
        """
        super(Story106941, self).tearDown()

    def _check_for_additional_disk_on_node(self):
        """
        Method that verifies there is a spare disk on the managed nodes in
        the cluster
        :return: Nothing
        """

        fdisk_cmd = '/sbin/fdisk -l | grep sdp'

        for node in self.node_exe:
            diskout = self.run_command(node, fdisk_cmd, su_root=True,
                                       default_asserts=True)[0]
            self.assertTrue(self.is_text_in_list('sdp', diskout))

    def _setup_additional_disk_for_litp(self):
        """
        This method will attach a newly LUN disk to a local cluster
        deployment
        :return: Nothing
        """
        disk_uuids = ['6006016011602D00325032273D95E611',
                      '6006016011602D00D6FC9A4A3D95E611',
                      '6006016011602D00EAF0BF45EC95E611',
                      '6006016011602D009CC42F69EC95E611']

        disk_props = {'name': 'sdp', 'size': '100M', 'bootable': 'false',
                      'uuid': '{0}'}
        file_system_props = {'type': 'ext4', 'mount_point': '/mnt',
                             'size': '12M'}

        for system, uuid in zip(['sys2', 'sys3', 'sys4', 'sys5'],
                                disk_uuids):
            # Create disk item type in LITP model
            self.execute_cli_create_cmd(
                self.management_server,
                self.sys_url + '/{0}/disks/disk4'.format(system), 'disk',
                props='name={0} size={1} bootable={2} uuid={3}'
                    .format(disk_props['name'], disk_props['size'],
                            disk_props['bootable'],
                            disk_props['uuid'].format(uuid)),
                add_to_cleanup=False)

        # Link physical-device to existing volume group
        self.execute_cli_create_cmd(self.management_server,
                                    self.physical_dev_url + '/internal4',
                                    'physical-device',
                                    props='device_name={0}'
                                    .format(disk_props['name']),
                                    add_to_cleanup=False)
        # Create file-system
        self.execute_cli_create_cmd(self.management_server,
                                    self.fs_url + '/mnt_tmp',
                                    'file-system',
                                    props='type={0} mount_point={1} size={2}'
                                    .format(file_system_props['type'],
                                            file_system_props['mount_point'],
                                            file_system_props['size']),
                                    add_to_cleanup=False)

    def _increase_litp_storage(self, disk_size, fs_size):
        """
        Method that will update the disk and file system items in the
        litp model (Specifically for TC1)
        :param disk_size: (str) Used to increase the disk size in the litp
        model
        :param fs_size: (str) Used to increase the file system size in the litp
        modle
        :return: Nothing
        """
        for disk_url in ['sys2', 'sys3', 'sys4', 'sys5']:
            # Create disk item type in LITP model
            self.execute_cli_update_cmd(
                self.management_server,
                self.sys_url + '/{0}/disks/disk4'.format(disk_url),
                props='size={0}'.format(disk_size))

        self.execute_cli_update_cmd(self.management_server,
                                    self.fs_url + '/mnt_tmp',
                                    props='size={0}'.format(fs_size))

        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE, 30))

    def _verify_pv_resize(self, new_pv_size):
        """
        Method to verify that the newly increased physical disk size is correct
        on the managed nodes using pvdisplay
        :param new_pv_size: (str) size of physical volume
        :return: Nothing
        """
        grep_cmd = '/sbin/pvdisplay | grep "PV Size"'
        stdout, _, _ = self.run_command(self.node_exe[0],
                                        grep_cmd, su_root=True)

        self.assertTrue(self.is_text_in_list(new_pv_size, stdout))

    def _verify_lv_resize(self, new_lv_size):
        """
        Method to verify that the newly increased logical volume size is
        correct on the managed nodes using lvdisplay command
        :param new_lv_size: (str) size of logical volume
        :return: Nothing
        """
        grep_cmd = '/sbin/lvdisplay | grep "LV Size"'
        stdout, _, _ = self.run_command(self.node_exe[0],
                                        grep_cmd, su_root=True)

        self.assertTrue(self.is_text_in_list(new_lv_size, stdout))

    def _increase_disk_with_fdisk_script(self, disk_name):
        """
        Method that expands the existing disk on node
        :param disk_name: (str) disk url i.e. /dev/sda
        :return: Nothing
        """
        fdisk_script = 'fdisk_script.sh'

        for node in self.node_exe:
            self.assertTrue(self.copy_file_to(node, self.loc_dir + '/' +
                                              fdisk_script, '/root',
                                              root_copy=True,
                                              add_to_cleanup=False))

            _, _, _ = self.run_command(node, cmd='sh /root/{0} {1}'
                                       .format(fdisk_script, disk_name),
                                       su_root=True)

            # Reboot Node
            self.log('info', 'Reboot Node for disk expansion to take affect')
            time.sleep(180)

            self.assertTrue(self.wait_for_node_up(node, timeout_mins=15))

    @attr('all', 'kgb-physical', 'story106941', 'story106941_tc01')
    def test_01_p_increase_pv_with_additional_scsi_disk_on_nodes(self):
        """
        @tms_id: test_01_p_increase_pv_with_additional_scsi_disk_on_nodes
        @tms_requirements_id: TORF-106941
        @tms_title: Increase Physical Volume of added SCSI disk to node
        @tms_description: Test to verify that a user can resize a new SCSI
        disk after it being added to the clusters managed nodes
        Test is executed in PCDB_4node_expansion_120 Job.
        @tms_test_steps:
            @step: Deploy cluster with nodes and additional LUNs
            @result: Cluster pre-deployed from PCDB
            @step: Add new disk to model under /infrastructure and inherit
            it under /deployments and filesystems under storage profiles
            @result: New disk added into litp model
            @step: Create/ Run plan
            @result: Plan is run to completion
            @step: Ensure New disk is added to litp model
            @result: New disk is added to model
            @step: Increase size of filesystems and disk item in litp model
            @result: File systems and disk are increased in model
            @step: Create/ Run plan again
            @result: No errors should be returned
            @step: Verify new disk size with _verify_lv_size
            @result: LV should be increased to newly assigned value
        @tms_test_precondition: PCDB 4 node expansion
        @tms_execution_type: Automated
        """
        timeout_mins = 60

        # Step 1: Deploy cluster with nodes and additional LUNs available

        # Step 2: Add new disk to model under /infrastructure and inherit
        # it under /deployments and filesystems under storage profiles
        self._check_for_additional_disk_on_node()

        self._setup_additional_disk_for_litp()

        # Step 3: Create/ Run Plan
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        # Step 4: Ensure new disk is added to litp model
        self.assertEqual(self.get_props_from_url(self.management_server,
                                                 self.sys_url +
                                                 '/sys2/disks/disk4',
                                                 filter_prop='name'), 'sdp')
        # Remove snapshot before file system update
        self.execute_cli_removesnapshot_cmd(self.management_server)
        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        # Step 5 & 6: Increase the PV disk size and filesystems in the model
        # Step 7: Create and run plan to completion
        self._increase_litp_storage(disk_size='110M', fs_size='40M')

        # Verify the disks correspond with updated property in litp
        self._verify_lv_resize(new_lv_size='40.00')

    @attr('manual-test', 'revert', 'story106941', 'story106941_tc02')
    def test_02_p_increase_pv_with_currently_installed_disk(self):
        """
        @tms_id: test_02_p_increase_pv_with_currently_installed_disk
        @tms_requirements_id: TORF-106941
        @tms_title: Increase Physical Volume of existing SCSI disk
        @tms_description: Test to verify that a user can resize an existing
        SCSI disk.
        Test is executed on a local desktop machine in the Trigger dock which
        is usually refered to as Vitallis machine.
        As such, some additional undocumented steps are required to configure
        the test environment before executing this test.
        @tms_test_steps:
            @step: Deploy 1 node cluster with existing SCSI disk
            @result: 1 node cluster deployed on local system
            @step: Create/ Run plan
            @result: Plan is run to completion
            @step: Increase existing disk by running relevant commands
            @result: Disk is expanded
            @step: Reboot the VM, and increase the PV disk size in the model
            @result: VM is back running and physical volume is increased
            on node
            @step: Create/ Run plan
            @result: Plan is run to completion
            @step: Ensure node and model have both been updated with increased
            disk size
            @result: Node and model are updated with increased disk size
            @step: Increase filesystems under disk
            @result: Filesystems are increased
            @step: Create/ Run plan again
            @result: Plan is run to completion with no errors returned
        @tms_test_precondition: Local machine configured for testing
        @tms_execution_type: Manual IT
        """
        timeout_mins = 60
        # Manual steps
        # Step 1: Deploy 1 node cluster with existing SCSI disk available
        # Step 2: Create/ Run plan to completion
        # Ensure credentials are updated on newly deployed node

        fdisk_grep_cmd = "/sbin/fdisk -l | grep 'sda'"

        fdiskout, _, _ = self.run_command(self.node_exe[0], fdisk_grep_cmd,
                                          su_root=True)

        disk_1 = fdiskout[0].split('Disk ')[1].split(':')[0]

        # Step 3: Increase existing disk by running relevant commands
        # Step 4: Reboot the node
        self._increase_disk_with_fdisk_script(disk_1)

        old_disk_size = self.get_props_from_url(self.management_server,
                                                self.sys_url +
                                                '/sys2/disks/disk0',
                                                filter_prop='size')

        # Increasing disk in litp model
        self.execute_cli_update_cmd(self.management_server,
                                    self.sys_url + '/sys2/disks/disk0',
                                    props='size=45G')

        # Step 4: Create/ Run Plan
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        # Step 5: Ensure node and model have both been updated with increased
        # disk size
        self.assertNotEqual(self.get_props_from_url(self.management_server,
                                                    self.sys_url +
                                                    '/sys2/disks/disk0',
                                                    filter_prop='size'),
                            old_disk_size)

        self._verify_pv_resize(new_pv_size='59')

        # Step 6: Increase file systems under disk
        self.execute_cli_update_cmd(self.management_server,
                                    self.fs_url + '/root', props='size=10G')

        # Step 7: Create/ Run Plan again
        self.execute_cli_createplan_cmd(self.management_server)
        self.execute_cli_showplan_cmd(self.management_server)
        self.execute_cli_runplan_cmd(self.management_server)

        self.assertTrue(self.wait_for_plan_state(self.management_server,
                                                 PLAN_COMPLETE,
                                                 timeout_mins))

        self._verify_lv_resize(new_lv_size='10.00')

"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     July 2015
@author:    James Langan, Ciaran Reilly, John Dolan, Brian Carey, Marco Gibboni
"""

from litp_generic_test import GenericTest, attr
from redhat_cmd_utils import RHCmdUtils
from networking_utils import NetworkingUtils
from vcs_utils import VCSUtils
from time import sleep
import test_constants


class VCS(GenericTest):
    """
    Test the VCS functionality in LITP.
    Item Types verified are 'vcs-cluster', 'vcs-network-host, 'disk',
    'storage-profile', 'vcs-clustered-service', 'ha-service-config',
    'vip', 'package', 'file-system', 'service' and 'lsb-runtime'
    """

    def setUp(self):
        """ Setup Variables for every test """

        super(VCS, self).setUp()

        self.model = self.get_model_names_and_urls()
        self.ms_node = self.model["ms"][0]["name"]
        self.all_nodes = self.model["nodes"][:]
        self.managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.managed_nodes[0]
        self.secondary_node = self.managed_nodes[1]
        self.rhc = RHCmdUtils()
        self.vcs = VCSUtils()
        self.net_utils = NetworkingUtils()

        # list of configuration files paths
        self.files_paths = ['/etc/sysconfig/llt', '/etc/sysconfig/gab',
                            '/etc/llthosts', '/etc/llttab', '/etc/gabtab']

        self.disk_props = sorted(['bootable',
                                  'disk_part',
                                  'name',
                                  'size',
                                  'uuid'])

        self.vcs_cluster_url = self.find(self.ms_node,
                                         "/deployments", "vcs-cluster")[-1]
        self.cluster_id = self.vcs_cluster_url.split("/")[-1]

    def tearDown(self):
        """ Teardown run after every test """

        super(VCS, self).tearDown()

    @staticmethod
    def get_vxfenconfig_cmd(args=""):
        """Returns a command to run a vxfenconfig cmd

        Args:
            args (str): arguments to be appended to the cmd.

        Returns:
            str. A command to return
            "/sbin/vxfenconfig [arguments]"
        """
        return "/sbin/vxfenconfig {0}".format(args)

    def parse_fencing_disk_config_list_for_uuids(self, vxfenconfig_output):
        """
        Function to parse through the output of a vxfenconfig -l command
        and return a list of the uuids found.

        Args:
           vxfenconfig_output (list): The output from a vxfenconfig -l command.

        Returns:
        list. A list of the uuids of the fencing disks created on the node."
        """
        uuids = []
        for line in vxfenconfig_output:
            split_lines = line.split(' ')
            if split_lines and split_lines[0] == "/":
                items = [x for x in split_lines if x != '']
                self.assertTrue(len(items) >= 4)
                uuids.append(items[3])
        uuids = uuids.sort()
        return uuids

    def verify_split_brain_protection(self, vcs_nodes, num_disks,
                                      uuid_specified_list):
        """
            VERIFY THE SPLIT BRAIN CONFIGURATION ON THE NODES IN THE CLUSTER
            IF 0 DISKS WERE ALLOCATED THEN AN ERROR MESSAGE OF 0 ACTIVE
            COORDINATION POINTS SHOULD BE RETURNED, OTHERWISE ENSURE THAT
            THE UUIDS CONFIGURED ON THE NODE MATCH THAT OF THOSE SPECIFIED.
        """
        for node in vcs_nodes:

            cmd = self.get_vxfenconfig_cmd("-l")

            stdout, stderr, returnc = self.run_command(node, cmd, su_root=True)

            if num_disks == 0:
                self.assertEqual(1, returnc)
                self.assertEqual("There are 0 active coordination points for "
                                 "this node", stdout[0])
                self.assertEqual([], stderr)

            else:
                self.assertEqual(0, returnc)
                self.assertEqual([], stderr)
                self.assertNotEqual([], stdout)

                node_uuids = \
                    self.parse_fencing_disk_config_list_for_uuids(stdout)

                self.assertEqual(uuid_specified_list, node_uuids)

    def get_res_state_per_node(self, node_filename, resource_name):
        """
        Return VCS resource state on the specified node

        @arg (str) node_filename  The node where to run the hares command
        @arg (str) resource_name  Name of the resource
        @ret (dict) Status of the given resource per node
        """
        cmd = self.vcs.get_hares_state_cmd() + resource_name
        stdout, stderr, rc = self.run_command(node_filename,
                                              cmd, su_root=True)
        self.assertEqual(0, rc)
        self.assertEqual([], stderr)

        return self.vcs.get_resource_state(stdout)

    def compare_disk_props(self, props_list):
        """
            This function compares the expected
            properties with the list name
            passed as parameter
        """
        for key in range(0, len(self.disk_props)):

            if self.disk_props[key] != props_list[key]:

                self.log('info', "The property '{0}' is missing!"
                         .format(self.disk_props[key]))

                return False

        return True

    def _verify_fencing_disks(self, cluster_url, cluster_id, cluster_type,
                              vcs_nodes):
        """
            Description:
                Verify fencing disk items in vcs-cluster
        """

        # Verify fencing disks and split brain protection.
        fen_disk_urls = self.find(self.ms_node, cluster_url +
                                  '/fencing_disks', "disk",
                                  assert_not_empty=False)

        num_disks = len(fen_disk_urls)

        allowed_num_disks = [0, 3]

        self.assertTrue(num_disks in allowed_num_disks)

        # Check to ensure that if the cluster type is not 'sfha', that no
        # fencing disks are then allocated
        if cluster_type != "sfha":

            self.assertEqual(0, num_disks)

        self.log("info", "Cluster Type: " + cluster_type +
                 ", Number of Fencing disks: " + str(num_disks))

        # Get the UUIDs of the fencing disks specified
        uuid_specified_list = []

        if num_disks == 0:
            self.log("info", "No fencing disks in model.")

        else:

            for fen_disk_url in fen_disk_urls:

                props = self.get_props_from_url(self.ms_node, fen_disk_url)

                self.log("info", "Cluster id: " + cluster_id +
                         ", Properties: " + str(props))

                # Check if all the properties are set
                prop_names = props.keys()

                same_lists = self.compare_disk_props(sorted(prop_names))

                self.assertTrue(same_lists)

                uuid_specified_list.append(props["uuid"])

            uuid_specified_list = uuid_specified_list.sort()

            self.verify_split_brain_protection(vcs_nodes, num_disks,
                                               uuid_specified_list)

    def _check_cluster_properties(self, props):
        """
            Description:
                Verifies that the values of some the properties under the
                cluster are set correctly
        """

        self.log("info", "Checking that the property 'cluster_type' is "
                         "present")
        self.assertTrue("cluster_type" in props)

        self.log("info", "Checking that the property 'cluster_id' is "
                         "present")
        self.assertTrue("cluster_id" in props)

        self.log("info", "Checking that the property 'default_nic_monitor' is "
                         "present")
        self.assertTrue("default_nic_monitor" in props)

        self.log("info", "Checking that the property 'llt_nets' is "
                         "present")
        self.assertTrue("llt_nets" in props)

        self.log("info", "Checking that the property 'low_prio_net' is "
                         "present")
        self.assertTrue("low_prio_net" in props)

    def _verify_gabconfig(self, vcs_nodes):
        """
            Description:
                Verify gabconfig is set correctly according to the model and
                that the correct nodes are running
        """

        gabconfig = self.vcs.get_gabconfig_cmd()

        gabconfig_cmd = gabconfig + " | grep gen | grep -vE 'Port d'"

        std_out, std_err, r_code = self.run_command(vcs_nodes[0],
                                                    gabconfig_cmd,
                                                    su_root=True)

        self.assertEqual(0, r_code)
        self.assertEqual([], std_err)
        self.assertNotEqual([], std_out)

        for line in std_out:
            new_std_out = line.split()

            self.log("info", "Checking the number of vcs nodes in "
                             "gabconfig '{0}' is equal to the number of "
                             "vcs nodes in the model '{1}'"
                     .format(len(new_std_out[-1]), len(vcs_nodes)))

            self.assertEqual(len(vcs_nodes), len(new_std_out[-1]))

        hastatus = self.vcs.get_hastatus_sum_cmd()

        hastatus_cmd = hastatus + " | /bin/grep RUNNING"

        std_out, std_err, r_code = self.run_command(vcs_nodes[0],
                                                    hastatus_cmd,
                                                    su_root=True)

        self.assertEqual(0, r_code)
        self.assertEqual([], std_err)
        self.assertNotEqual([], std_out)

        for node in vcs_nodes:
            self.log("info", "Checking that {0} is running".format(node))
            self.assertTrue(node in line for line in std_out)

    def _verify_vcs_network_host(self, interfaces, llt_nets, node,
                                 cluster_name, node_hostname,
                                 hosts_per_network):
        """
            Description:
                Verify vcs-network-host items
        """

        for if_url in interfaces:

            network_name = self.get_props_from_url(self.ms_node,
                                                   if_url,
                                                   'network_name')

            props = self.get_props_from_url(self.ms_node, if_url)

            if network_name in llt_nets:

                macadd = props["macaddress"].upper()

                cmd = "/sbin/lltconfig -a list | /bin/grep {0}".format(macadd)

                stdout, stderr, rc = self.run_command(node, cmd,
                                                      su_root=True)
                self.assertNotEqual([], stdout)
                self.assertEqual(0, rc)
                self.assertEqual([], stderr)
                continue

            # Only network interfaces with associated network name have
            # a NIC Service Group
            if network_name:

                dev_name = self.get_props_from_url(self.ms_node,
                                                   if_url,
                                                   'device_name')
                if "." in dev_name:

                    dev_name = dev_name.replace(".", "_")

                self.log("info", "Node: " + node +
                         ", network_name: " + network_name +
                         ", dev_name: " + dev_name)

                sys = node_hostname

                res_name = self.vcs.generate_nic_resource_name(
                    cluster_name, dev_name)

                # Ensure the NIC resource is in ONLINE state
                res_state_per_node = self.get_res_state_per_node(
                    node, res_name)

                self.assertEqual("online", res_state_per_node[sys])

                # Find the NetworkHosts of this node, as they
                # are seen by VCS
                cmd = self.vcs.get_hares_resource_attribute(
                    res_name, "NetworkHosts") + " -sys '{0}'" \
                          .format(sys)

                stdout, stderr, rc = self.run_command(node, cmd,
                                                      su_root=True)
                self.assertEqual(0, rc)
                self.assertEqual([], stderr)

                if stdout == []:

                    cmd = self.vcs.get_hares_resource_attribute(
                        res_name, "NetworkHosts") + " -sys 'global'"

                    stdout, stderr, rc = self.run_command(node, cmd,
                                                          su_root=True)
                    self.assertEqual(0, rc)
                    self.assertEqual([], stderr)

                self.assertTrue(len(stdout) >= 2)
                params = stdout[1].split(None, 3)

                out_hosts = params[3].upper().split() \
                    if len(params) > 3 else "No value"

                self.log("info", ", Node: " + node + ", out_hosts: " +
                         str(out_hosts))

                if network_name in hosts_per_network:

                    # Compare if the network hosts of this node match
                    # the items specified in the model
                    self.assertEqual(
                        sorted(hosts_per_network[network_name]),
                        sorted(out_hosts))

    def _find_nic_for_address_on_nodes(self, ipaddress, nodes):
        """
        Description:
            Finds the NIC and node that an ipaddress is assigned to
        :param ipaddress: The ipaddress to search for
        :param nodes: The nodes on which to search
        :return: The node and nic that the ipaddress is on
        """
        for node in nodes:
            cmd = self.net_utils.get_node_nic_interfaces_cmd()
            nics, _, _ = \
                self.run_command(node, cmd, su_root=True)
            for nic in nics:
                cmd = \
                    self.net_utils.get_ifconfig_cmd(nic)
                stdout, _, _ = \
                    self.run_command(node, cmd, su_root=True)
                ifcfg_dict = \
                    self.net_utils.get_ifcfg_dict(stdout, nic)
                if ifcfg_dict:
                    if ipaddress in ifcfg_dict["IPV6"]:
                        return node, nic
                    if ifcfg_dict["IPV4"] == ipaddress:
                        return node, nic
        return None, None

    # Testset_story2208: test_09_p_all_services_running
    def _test_vcs_after_stop(self):
        """
        Description:
            Verify the vcs service is restarted by puppet
            after being manually stopped by us
        Actions:
            1. get a command to stop the vcs service
            2. execute vcs stop cmd on first node in the cluster
            3. confirm that puppet performed restart of the vcs service
        Results:
            vsc service is restarted & running
        """
        # 1.

        try:
            stop_vcs_cmd = self.rhc.get_systemctl_stop_cmd("vcs")
            status_vcs_cmd = self.rhc.get_systemctl_status_cmd("vcs")
        # 2.
            _, std_err, r_code = self.run_command(self.primary_node,
                                    stop_vcs_cmd, su_root=True)
            self.assertEqual(0, r_code)
            self.assertEqual([], std_err)
        # 3.
            # wait for the current puppet cycle
            self.wait_full_puppet_run(self.ms_node)
            # get vcs status
            _, std_err, r_code = self.run_command(self.primary_node,
                                    status_vcs_cmd, su_root=True)
            self.assertEqual(0, r_code)
            self.assertEqual([], std_err)

        finally:
            # check status of vcs
            _, _, rc = \
                self.get_service_status(self.primary_node, "vcs",
                                        assert_running=False)
            # start vcs service if not started
            if rc != 0:
                self.start_service(self.primary_node, "vcs",
                                   assert_success=False)

    # Testset_story3764: test_01_check_hastatus
    def _test_hastatus_after_vcs_path_del(self):
        """
        Description:
            This test checks if it is possible to execute
            the command hastatus -sum by the root user
            before and after deleting /etc/profile.d/vcs_path.sh
            on one of the nodes in the vcs-cluster.
            File: vcs_path.sh is responsible for adding VCS tools
            into the PATH variable.
        Actions:
            1. Verify that root can run the hastatus cmd
            2. Remove /etc/profile.d/vcs_path.sh file on the 1st node
            3. Verify the command can still be executed
               without errors after puppet enforced changes
        Result:
             Successful output from hastatus -sum
             on the node
        """

        file_path = "/etc/profile.d/vcs_path.sh"

        # 1.
        _hastatus_cmd = self.vcs.get_hastatus_sum_cmd()
        _, std_err, r_code = self.run_command(self.primary_node,
                       _hastatus_cmd, su_root=True)
        self.assertEqual(0, r_code, "non-zero return code")
        self.assertEqual([], std_err)
        # 2.
        self.assertTrue(self.remove_item(self.primary_node,
                                         file_path, su_root=True))
        # 3.
        self.assertTrue(self.wait_for_puppet_action(self.ms_node,
                    self.primary_node, _hastatus_cmd, 0, su_root=True))

    def get_nic_sg_list_from_node_url(self, node_url):
        """
        Return a list of NIC Service Groups that we expect to be present
        on the node based on the LITP model
        """

        # Get the list of llt networks in the cluster
        llt_networks_str = self.execute_show_data_cmd(self.ms_node,
                                                      self.vcs_cluster_url,
                                                      "llt_nets")
        llt_networks = [s.strip() for s in llt_networks_str.split(",")]

        non_llt_devices = []
        node_interface_urls = self.find_children_of_collect(self.ms_node,
                                                            node_url,
                                                           'network-interface')
        # Include interfaces that are:
        #   not in llt networks; not assigned to a bridge or bond
        for interface_url in node_interface_urls:
            interface = self.get_props_from_url(self.ms_node, interface_url)
            if 'network_name' not in interface:
                interface['network_name'] = ""
            if not interface['network_name'] in llt_networks and\
                    'bridge' not in interface and 'master' not in interface:
                non_llt_devices.append(interface['device_name'])

        nic_sg_list = []
        for device in non_llt_devices:
            sg_name = "Grp_NIC_%s_%s" % (self.cluster_id,
                device)
            nic_sg_list.append(sg_name)

        return nic_sg_list

    def get_nic_sg_list_from_hastatus(self, hastatus_stdout):
        """
        Return a list of NIC Service Groups based on passed "hastatus -sum"
        output
        """

        nic_sg_list = []

        # Get a list of all SGs on the node
        sg_list = self.vcs.get_hastatus_sum_sg_list(
            hastatus_stdout)

        # Get a list of NIC SGs on the node
        nic_sg_list = []
        for sg_name in sg_list:
            if sg_name.startswith("Grp_NIC_"):
                nic_sg_list.append(sg_name)

        return nic_sg_list

    def _test_nic_service_groups(self):
        """
        Description:
            Using hastatus -sum, verify that a NIC SG has been created for
            each non-llt network and that it is online
        Actions:
            1. Run hastatus -sum on the nodes
            2. Make sure the output contains NIC SG for each non-llt network
            3. Make sure the output doesn't contain other NIC SGs
        Result:
            Nodes can only contain NIC SGs for non-llt networks
        """
        node_filenames = self.get_managed_node_filenames()
        for node_filename in node_filenames:

            # Get node URL
            node_url = self.get_node_url_from_filename(self.ms_node,
                node_filename)

            # Run "hastatus -sum" command
            cmd = self.vcs.get_hastatus_sum_cmd()
            hastatus_stdout, hastatus_stderr, rc = \
                self.run_command(node_filename, cmd, su_root=True)
            self.assertEquals(0, rc)
            self.assertEquals([], hastatus_stderr)

            expect_nic_sg_list = \
                self.get_nic_sg_list_from_node_url(node_url)
            actual_nic_sg_list = \
                self.get_nic_sg_list_from_hastatus(hastatus_stdout)

            # Important for comparison - lists must be in the same order
            expect_nic_sg_list.sort()
            actual_nic_sg_list.sort()

            # Ensure the node contains only expected NIC SGs
            self.assertEquals(
                expect_nic_sg_list,
                actual_nic_sg_list
            )

            # Ensure all NIC SGs on the node are online
            for sg_name in actual_nic_sg_list:
                systems = self.vcs.get_hastatus_sg_systems_list(
                    hastatus_stdout, sg_name)
                for system in systems:
                    status = self.vcs.get_hastatus_sg_sys_state(
                        hastatus_stdout, sg_name, system).lower()
                    self.assertEquals("online", status)

    def get_vcs_model_info(self):
        """
        Function that returns a dictionary all the vcs clustered service
        information from the LITP model
        """

        service_groups = []

        multi_type_list = ['ha-service-config', 'vip', 'package',
                           'file-system', 'service', 'lsb-runtime',
                           'vcs-trigger']
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

                for itype in multi_type_list:
                    urls = self.find(self.ms_node, serv, itype,
                                     assert_not_empty=False)
                    for url in urls:
                        props = self.get_props_from_url(self.ms_node, url)
                        prop_dict['url'] = url
                        for prop in props:
                            prop_dict[prop] = props[prop]

                        if itype in service_group:
                            service_group[itype].append(prop_dict)
                        else:
                            service_group[itype] = []
                            service_group[itype].append(prop_dict)
                        prop_dict = {}

                service_groups.append(service_group)
                service_group = {}

        self.log("info", "Printing dict from get_vcs_model_info()")
        self._print_list(0, service_groups)
        self.log("info", "Finished printing dict")

        return service_groups

    def _get_list_of_networks_in_cluster(self, cluster_url):
        """
        Function that returns a list of networks from the LITP model
        """
        networks = []

        # Get list of networks under the cluster in the LITP model
        network_ints = self.find_children_of_collect(self.ms_node, \
                                        cluster_url, "network-interface")
        for network_int in network_ints:
            networks.append(self.get_props_from_url(
                self.ms_node, network_int, filter_prop="network_name"))

        return networks

    def _verify_cluster_packages_installed(self, node_name, cluster):
        """
            Description:
                Verify packages used under the clustered service are
                installed on the relevant nodes
        """
        if "package" in cluster:

            cluster_packs = cluster["package"]

            for package in cluster_packs:

                props = package

                self.assertTrue("name" in props)

                name = [props["name"]]

                self.check_pkgs_installed(node_name, name)

    def _verify_autostart_and_system_list(self, node_name, service_group,
                                         service_props, node_hostnames):
        """
            Description:
                Verify AutoStartList and SystemList VCS attributes have been
                set to correct values based in LITP Model node_list.
                Story LITPCDS-5653.
        """
        gp_node_list = self.run_vcs_hagrp_display_command(
                node_name, service_group, "AutoStartList")

        gp_node_list2 = self.run_vcs_hagrp_display_command(
                node_name, service_group, "SystemList")

        exp_auto_start_list = '\t'.join(node_hostnames)
        sorted_hostnames = sorted(node_hostnames)

        check_auto_start_list = True
        if len(node_hostnames) == 1:
            exp_system_list = '{0}\t0'.format(node_hostnames[0])
        elif len(node_hostnames) == 2:
            if service_props['standby'] == "0":
                exp_system_list = '{0}\t0\t{1}\t0'.format(
                                                       sorted_hostnames[0],
                                                       sorted_hostnames[1])
                # There is no point checking the AutoStartList for PL groups
                # as the order doesn't matter
                check_auto_start_list = False
            else:
                if node_hostnames == sorted_hostnames:
                    exp_system_list = '{0}\t0\t{1}\t1'.format(
                                                       sorted_hostnames[0],
                                                       sorted_hostnames[1])
                else:
                    exp_system_list = '{0}\t1\t{1}\t0'.format(
                                                       sorted_hostnames[0],
                                                       sorted_hostnames[1])

        self.log("info", "Expected SystemList: {0}"
                     .format(exp_system_list))
        self.log("info", "Actual SystemList:   {0}"
                     .format(gp_node_list2['SystemList'][0]['VALUE']))

        if check_auto_start_list:
            self.log("info", "Expected AutoStartList: {0}"
                         .format(exp_auto_start_list))
            self.log("info", "Actual AutoStartList:   {0}"
                         .format(gp_node_list['AutoStartList'][0]['VALUE']))

            self.log("info", "Verifying AutoStartList for {0}"
                         .format(service_group))
            self.assertTrue(exp_auto_start_list == \
                            gp_node_list['AutoStartList'][0]['VALUE'])

        self.log("info", "Verifying SystemList for {0}"
                     .format(service_group))
        self.assertTrue(exp_system_list == \
                            gp_node_list2['SystemList'][0]['VALUE'])

    def _verify_lsbruntime_props(self, cluster, resource, node_name):
        """
            Description:
                Verify lsb-runtime item properties
                Story LITPCDS-4848, LITPCDS-2207
        """
        for config in cluster["lsb-runtime"]:

            # Get dictionary of lsb-runtime properties
            props = cluster["lsb-runtime"]

            self.log("info", "lsb-runtime properties : {0}"
                     .format(props))

            print "LSB Resources {0}".format(resource)
            res_app_list = list()
            for res in resource:
                if 'Res_App' in res:
                    res_app_list.append(res)

            print "LSB res_app_list {0}".format(res_app_list)

            for res in res_app_list:

                # if the cluster name is in the resource:
                if cluster["vcs-clustered-service"]["name"] in res:

                    if "service_id" in config:

                        # If the service id is not in the resource continue
                        # onto the next one
                        if config["service_id"] not in res:

                            continue

                    # Display resource information for each resource
                    hares_display = self.run_vcs_hares_display_command(
                        node_name, res)

                    self._verify_vcs_timeouts_limits(config, hares_display)

                    # LITPCDS-2207
                    self._verify_vcs_app_commands(config, hares_display)

                    self.log("info", "'lsb-runtime' check complete")

    def _verify_vcs_app_commands(self, config, hares_display):
        """
            Description:
                Verify the VCS Application Attributes for commands.
                Used to verify lsb-runtime and service item types
                Stories LITPCDS_2207, LITPCDS-5768
        """
        if "cleanup_command" in config:
            self.log("info", "Checking that "
                             "cleanup_command is correct")

            self.assertTrue("CleanProgram" in hares_display)
            self.assertEqual(
                config["cleanup_command"],
                hares_display["CleanProgram"][0]["VALUE"])

        if "start_command" in config:
            self.log("info", "Checking that "
                             "start_command is correct")

            self.assertTrue("StartProgram" in hares_display)
            self.assertEqual(
                config["start_command"],
                hares_display["StartProgram"][0]["VALUE"])

        if "stop_command" in config:
            self.log("info", "Checking that "
                             "stop_command is correct")

            self.assertTrue("StopProgram" in hares_display)
            self.assertEqual(
                config["stop_command"],
                hares_display["StopProgram"][0]["VALUE"])

        if "status_command" in config:
            self.log("info", "Checking that "
                             "status_command is correct")

            self.assertTrue("MonitorProgram" in hares_display)
            self.assertEqual(
                config["status_command"],
                hares_display["MonitorProgram"][0]["VALUE"])

    def _verify_service_props(self, cluster, resource, node_name):
        """
            Description:
                Verify service item properties
                Story LITPCDS-5768
        """
        for config in cluster["service"]:

            # Get dictionary of service properties
            props = cluster["service"]

            self.log("info", "service properties : {0}"
                     .format(props))

            res_app_list = list()
            for res in resource:
                if 'Res_App' in res:
                    res_app_list.append(res)

            config_id = config["url"].split('/')[-1]

            for res in res_app_list:
                res_app_id = res.split('_')[-1]

                if config_id != res_app_id:
                    self.log("info", "Skipping res {0} as not matching "
                                     "{1}.".format(res, config_id))
                    continue

                # if the cluster name is in the resource:
                if cluster["vcs-clustered-service"]["name"] in res:
                    if "service_id" in config:
                        # If the service id is not in the resource continue
                        # onto the next one
                        if config["service_id"] not in res:
                            continue

                    # Display resource information for each resource
                    hares_display = self.run_vcs_hares_display_command(
                        node_name, res)

                    # LITPCDS-5768
                    self._verify_vcs_app_commands(config, hares_display)

                    self.log("info", "'service' check complete for {0}"
                                               .format(res_app_id))

    def _verify_dependency_list(self, service_props, cluster_id, service_id,
                                node_name):
        """
            Description:
                Verify that the dependency list property has been applied
                correctly
                LITPCDS-5938
        """

        test_dependencies_list = []

        # Are there dependencies?
        if "dependency_list" in service_props and len(
                service_props["dependency_list"]) != 0:

            add_row = {}
            add_row["cluster_id"] = cluster_id

            add_row["node_name"] = node_name

            add_row["children"] = service_props['dependency_list'].split(",")

            add_row["parent"] = service_id
            test_dependencies_list.append(add_row)

        # After vcs services loop, check all dependencies found
        for dependency in test_dependencies_list:

            self.log("info", "Checking all dependencies found")
            node_name = dependency['node_name']

            # Find parent service group
            parent_sg = self.vcs.generate_clustered_service_name(
                dependency["parent"], dependency["cluster_id"])
            child_sgs = []

            # Find all child service groups
            for child in dependency['children']:
                child_sgs.append(
                    self.vcs.generate_clustered_service_name(
                        child, dependency["cluster_id"]))

            # Retrieve the output for parent sg deps
            gp_deps = self.run_vcs_hagrp_dep_command(node_name, parent_sg)

            # Assert that the prop and output values match
            for gp_dep in gp_deps:
                # Since hagrp -dep finds either parent and child deps
                # of the sg, if it's a child then skip to next row
                if parent_sg == gp_dep["CHILD"]:
                    continue
                self.assertTrue(gp_dep["PARENT"] == parent_sg)
                self.assertTrue(gp_dep["CHILD"] in child_sgs)

    def _verify_vip_addresses(self, networks, cluster, nodes,
                              cluster_id, service_id, ifcfgs):
        """
            Description:
                Verify vip items in vcs-clustered-service and ensure
                NIC_Proxy resources exist in VCS
                Story LITPCDS-4003, LITPCDS-6164
        """
        vip_networks_set = set()
        # If VIP in model, begin checks.
        if 'vip' in cluster:

            vips = cluster["vip"]
            vip_networks = []
            for vip in vips:

                # Gets the network name for each VIP
                vip_network = vip['network_name']

                # Finds corresponding network name
                if vip_network in networks:

                    self.log("info", "Vip {0} network found".format(
                        vip["network_name"]))
                    vip_networks.append(vip_network)

                self.log("info", "Verifying vip ipaddress {0}"
                                  .format(vip['ipaddress']))
                # Output from ifcfg will not contain :0 pattern.
                if ':0' in vip['ipaddress']:
                    vip['ipaddress'] = vip['ipaddress'].replace(':0', ':')

                vip['ipaddress'] = vip['ipaddress'].split("/")[0]
                # Check that the vip is online one a node.
                self.assertTrue(
                    any(vip['ipaddress'] in line for line in ifcfgs))

            vip_networks_set = set(vip_networks)
        else:
            self.log("info", "No VIPS")
            return True

        resources = list()
        for vip_network in vip_networks_set:
            proxy_res = "Res_NIC_Proxy_{0}_{1}_{2}".format(cluster_id,
                                                           service_id,
                                                           vip_network)
            resources.append(proxy_res)

        # Run "hares -state" command
        # Use first node in vcs cluster
        cmd = self.vcs.get_hares_cmd('-list')
        hares_stdout, _, _ = \
                self.run_command(nodes[0],
                                 cmd, su_root=True,
                                 default_asserts=True)

        nic_proxy_resources = self.get_resources_from_hares_list(
                                                       hares_stdout,
                                                       'NIC_Proxy')

        # Ensure NIC_Proxy resource exists
        for proxy_res in resources:
            self.log("info", "Verifying NIC Proxy resource {0}"
                              .format(proxy_res))
            self.assertTrue(proxy_res in nic_proxy_resources)

    def _verify_vcs_timeouts_limits(self, config, hares_display):
        """
            Description:
                Verify VCS Application Attributes MonitorTimeout, RestartLimit,
                MonitorInterval and OnlineRetryTimeout.
                These are common to both lsb-runtime and ha-service-config item
                types in the LITP Model.
                LITPCDS-6296
        """
        if "status_timeout" in config:
            self.log("info", "Checking that status timeout is correct")

            self.assertTrue("MonitorTimeout" in hares_display)
            self.assertEqual(config["status_timeout"],
                             hares_display["MonitorTimeout"][0]["VALUE"])

        if "restart_limit" in config:
            self.log("info", "Checking that restart limit is correct")

            self.assertTrue("RestartLimit" in hares_display)
            self.assertEqual(config["restart_limit"],
                             hares_display["RestartLimit"][0]["VALUE"])

        if "status_interval" in config:
            self.log("info", "Checking that status interval is correct")

            self.assertTrue("MonitorInterval" in hares_display)
            self.assertEqual(config["status_interval"],
                             hares_display["MonitorInterval"][0]["VALUE"])

        if "startup_retry_limit" in config:
            self.log("info", "Checking that startup_retry_limit is correct")

            self.assertTrue("OnlineRetryLimit" in hares_display)
            self.assertEqual(config["startup_retry_limit"],
                             hares_display["OnlineRetryLimit"][0]["VALUE"])

    def _verify_online_offline_timeout(self, cluster, resource, node_name):
        """
            Description:
                Verify online, offline timeout properties
                Story LITPCDS-8361.
        """
        res_app_list = list()
        for res in resource:
            if 'Res_App' in res:
                res_app_list.append(res)

        for res in res_app_list:
            # Display resource information for each resource
            hares_display = self.run_vcs_hares_display_command(
                            node_name, res)

            self.log("info", "Checking Online Timeout and Offline "
                                     "Timeout properties from "
                                     "vcs-cluster-service")
            self.assertEqual(
                cluster["vcs-clustered-service"]["online_timeout"],
                hares_display["OnlineTimeout"][0]["VALUE"])

            self.assertEqual(
                cluster["vcs-clustered-service"]["offline_timeout"],
                hares_display["OfflineTimeout"][0]["VALUE"])

    def _verify_haconfig_props(self, cluster, resource, node_name):
        """
            Description:
                Verify ha-service-config item properties
                LITPCDS-6296
        """
        for config in cluster["ha-service-config"]:

            # Get dictionary of ha-service-config properties
            props = cluster["ha-service-config"]

            self.log("info", "Ha-Service-Config properties : {0}"
                     .format(props))

            res_app_list = list()
            for res in resource:
                if 'Res_App' in res:
                    res_app_list.append(res)

            for res in res_app_list:
                # if the cluster name is in the resource:
                if cluster["vcs-clustered-service"]["name"] in res:

                    if "service_id" in config:

                        # If the service id is not in the resource continue
                        # onto the next one
                        if config["service_id"] not in res:

                            continue

                    # Display resource information for each resource
                    hares_display = self.run_vcs_hares_display_command(
                        node_name, res)

                    if "dependency_list" in config:

                        depend_list = config["dependency_list"].split(",")

                        for depend in depend_list:
                            self.log("info", "Checking that dependency '{0}' "
                                             "is available in the VCS cluster"
                                     .format(depend))

                            self.assertTrue(depend in item
                                            for item in resource)

                    self.log("info", "Checking that clean timeout is "
                                     "correct")

                    self.assertTrue("CleanTimeout" in hares_display)
                    self.assertEqual(
                        config["clean_timeout"],
                        hares_display["CleanTimeout"][0]["VALUE"])

                    self.log("info", "Checking that fault on monitor "
                                     "timeouts is correct")

                    self.assertTrue("FaultOnMonitorTimeouts" in hares_display)
                    self.assertEqual(
                        config["fault_on_monitor_timeouts"],
                        hares_display["FaultOnMonitor"
                                      "Timeouts"][0]["VALUE"])

                    self.log("info", "Checking that tolerance_limit is "
                                     "correct")

                    self.assertTrue("ToleranceLimit" in hares_display)
                    self.assertEqual(
                        config["tolerance_limit"],
                        hares_display["ToleranceLimit"][0]["VALUE"])

                    self._verify_vcs_timeouts_limits(config, hares_display)

                    self.log("info", "'ha-service-config check complete")

    def _verify_cluster_vxvm_volume(self, cluster, node_name,
                                    service_group):
        """
            Description:
                Verifies that any vxvm volumes under a clustered service are
                on the right nodes
        """

        # If file-system is in the model under cluster service
        if "file-system" in cluster:

            fss = cluster["file-system"]

            # Get the states of the service groups on the node
            gp_states = self.run_vcs_hagrp_display_command(node_name,
                                                           service_group,
                                                           "State")

            # For each filesystem in the model
            for filesys in fss:

                self.log("info", "VXVM Volume URL: {0}".format(filesys))

                # Get the url of the inherited path in the model
                vxvm = self.deref_inherited_path(self.ms_node, filesys["url"])

                self.log("info", "Inherited from {0}".format(vxvm))

                # Get the URL and the properties of the volume group
                volume_grp_url = "/".join(vxvm.split("/")[:-2])
                vol_grp_props = self.get_props_from_url(self.ms_node,
                                                        volume_grp_url)

                # Get name of volume group from the properties
                volume_grp = vol_grp_props["volume_group_name"]

                # Get the name of the volume from the url
                volume = vxvm.split("/")[-1]

                # Get the url of the vcs clustered service in the model
                url = cluster["vcs-clustered-service"]["url"]

                # Get the name of the service from the url
                service = url.split("/")[-1]

                # If the service name is in the service group name
                if service in service_group:

                    self.log("info", "Service '{0}' is in Service group '{1}'"
                             .format(service,
                                     service_group))

                    for state in gp_states["State"]:

                        # If the service group is online
                        if state["VALUE"] == "|ONLINE|":

                            self.log("info", "Service group '{0}' is ONLINE"
                                     .format(service_group))

                            self.log("info", "Checking if volume '{0}' is on "
                                             "{1}".format(volume,
                                                          state["SYSTEM"]))

                            # This command checks if the vxvm volume is
                            # available on the node
                            cmd = "/sbin/vxprint -g {0} | grep ' {1} '" \
                                .format(volume_grp, volume)

                            stdout, stderr, rc = self.run_command(
                                state["SYSTEM"], cmd, su_root=True)

                            self.assertNotEqual([], stdout)
                            self.assertEqual([], stderr)
                            self.assertEqual(0, rc)

                            self.log("info", "VXVM volume is on {0}".format(
                                state["SYSTEM"]))

    def _verify_services_running(self, cluster, nodes):
        """
            Description:
                Verify that the services are running on online nodes.
        """
        if 'service' not in cluster:
            return True

        for service in cluster['service']:
            for node in nodes:
                self.log("info", "Checking is service '{0}' running on node: "
                                 "'{1}'".format(service['service_name'], node))
                cmd = self.rhc.get_service_running_cmd(service['service_name'])
                out, err, rc = self.run_command(node, cmd, su_root=True)
                self.assertEqual(0, rc)
                self.assertEqual([], err)
                self.assertNotEqual([], out)

    def _get_vcs_cluster_node_filenames(self, vcs_nodes):
        """
            Description:
                Gets the filenames for each node in vcs_nodes and returns
                list of those filenames
        """
        node_hostnames = []
        for node in vcs_nodes:
            # Get hostname of nodes in node list
            node_list_name = self.get_props_from_url(self.ms_node,
                                                     node,
                                                    'hostname')

            node_hostnames.append(node_list_name)

        return node_hostnames

    def _get_ifcfgs_for_vcs_nodes(self, node_hostnames):
        """
            Description:
                Get list of ifcfg for each node in node_hostnames
        """
        cmd = self.net.get_ifconfig_cmd()
        ifcfgs = []
        for node in node_hostnames:
            out, err, rc = self.run_command(node, cmd)
            self.assertEqual(0, rc)
            self.assertEqual([], err)
            self.assertNotEqual([], out)
            ifcfgs.extend(out)

        return ifcfgs

    def _verify_llttab_file(self, interfaces, llt_nets, node_hostname,
                           low_prio_net):
        """
        Description:
            Verify llttab file on each node in vcs cluster
        """
        self.log("info", "llt_nets: " + str(llt_nets))
        self.log("info", "low_prio_net: " + low_prio_net)

        netlink = list()
        linklowpri = list()

        for if_url in interfaces:
            network_name = self.get_props_from_url(self.ms_node,
                                                   if_url,
                                                   'network_name')

            if network_name in llt_nets:
                props = self.get_props_from_url(self.ms_node, if_url)
                macadd = props["macaddress"]
                netdict = {'netname': network_name, 'macaddress': macadd,
                           'device': props["device_name"]}
                netlink.append(netdict)

            if network_name == low_prio_net:
                props = self.get_props_from_url(self.ms_node, if_url)
                if 'macaddress' in props:
                    macadd = props["macaddress"]
                    netdict = {'netname': network_name,
                         'macaddress': macadd, 'device': props["device_name"]}
                else:
                    netdict = {'netname': network_name,
                                   'device': props["device_name"]}
                linklowpri.append(netdict)

        file_path = '/etc/llttab'

        llttab_node = "set-node {0}".format(node_hostname)
        llttab_cluster = 'set-cluster 1042'
        cat_cmd = self.rhc.get_cat_cmd(file_path)

        self.log("info", node_hostname + " Verifying llttab file")

        stdout, _, _ = self.run_command(node_hostname, cat_cmd, su_root=False,
                                 default_asserts=True)

        self.log("info", "Verifying '{0}' in '{1}'".format(llttab_cluster,
                                                           file_path))
        self.assertTrue(llttab_cluster in stdout)

        self.log("info", "Verifying '{0}' in '{1}'".format(llttab_node,
                                                           file_path))
        self.assertTrue(llttab_node in stdout)

        for net in netlink:
            llttab_line = "link {0} {1}-{2} - ether - -"\
                                        .format(net["device"],
                                                net["device"],
                                                net["macaddress"])

            self.log("info", "Verifying '{0}' in '{1}'".format(llttab_line,
                                                               file_path))
            self.assertTrue(llttab_line in stdout)

        for net in linklowpri:
            if 'macaddress' in net:
                llttab_line = "link-lowpri {0} {1}-{2} - ether - -"\
                                        .format(net["device"],
                                                net["device"],
                                                net["macaddress"])
            else:
                llttab_line = "link-lowpri {0} {1} - ether - -"\
                                        .format(net["device"], net["device"])
            self.log("info", "Verifying '{0}' in '{1}'".format(llttab_line,
                                                               file_path))
            self.assertTrue(llttab_line in stdout)

    def _check_active_node(self, sg_name):
        """
        Method to check which node is ONLINE for any failover SG, the
        assumption is that at least one node will be ONLINE.

        :return: act_node (str): The active and standby node for any
        failover SG.
        """
        node_check = '-state {0} -sys {1}'.format(sg_name, 'node1')
        sg_state_cmd_n1 = self.vcs.get_hagrp_cmd(node_check)

        sg_grp_state, _, _ = self.run_command(self.primary_node,
                                              sg_state_cmd_n1,
                                              su_root=True)

        if sg_grp_state[0] == 'ONLINE':
            active_node = self.primary_node
            standby_node = self.secondary_node
        else:
            active_node = self.secondary_node
            standby_node = self.primary_node
        return active_node, standby_node

    def _verify_vcs_triggers_configured_and_running(self, cs_group_name,
                                                    lsb_script):
        """
        Method that will check that any existing VCS triggers are configured
        correctly in the VCS model and behave as expected
        :param: cs_group_name: (str) Name of clustered service group
        :param: lsb_script: (str) Number of lsb script that will be killed
        :return: Nothing
        """
        _file_path = "/tmp/test-lsb-{0}".format(lsb_script[1])
        grp_state_fault = '|OFFLINE|FAULTED|'
        grp_state_online = '|ONLINE|'

        # Check what node the service group is active on before proceeding
        active_node, standby_node = self._check_active_node(cs_group_name)

        hagrp_state = self.vcs.get_hagrp_value_cmd(cs_group_name, "State")

        # Verify trigger is configured as expected (Only 1 behaviour of
        # Triggers config)
        hagrp_trig = self.vcs.get_hagrp_value_cmd(cs_group_name,
                                                  "TriggersEnabled")
        self.assertEqual(True, self.wait_for_cmd(active_node, hagrp_trig,
                                                 expected_rc=0,
                                                 expected_stdout='NOFAILOVER',
                                                 su_root=True))
        # Cause failover of service group and ensure the service fails back
        # over
        service = "test-lsb-{0}".format(lsb_script[1])
        stop_lsb_cmd = self.rhc.get_systemctl_stop_cmd(service)
        self.run_command(active_node, stop_lsb_cmd, su_root=True)

        # Wait for SG to fail over to secondary node
        # Check SG on node1 is faulted
        self.assertEqual(True,
                         self.wait_for_cmd(active_node, hagrp_state,
                                           expected_rc=0,
                                           expected_stdout=grp_state_fault,
                                           timeout_mins=2, su_root=True,
                                           default_time=1))

        # Check SG on standby_node is ONLINE
        self.assertEqual(True,
                         self.wait_for_cmd(standby_node, hagrp_state,
                                           expected_rc=0,
                                           expected_stdout=grp_state_online,
                                           timeout_mins=5, su_root=True,
                                           default_time=1))

        # Cause failover of service group and ensure the service fails back
        # over
        self.run_command(standby_node, stop_lsb_cmd, su_root=True)

        sleep(60)
        active_node, standby_node = self._check_active_node(cs_group_name)

        # Check SG on active_node is ONLINE
        self.assertEqual(True,
                         self.wait_for_cmd(active_node, hagrp_state,
                                           expected_rc=0,
                                           expected_stdout=grp_state_online,
                                           timeout_mins=5, su_root=True,
                                           default_time=1))
        # Check trigger
        self.assertEqual(True, self.wait_for_cmd(active_node,
                                                 hagrp_trig, expected_rc=0,
                                                 expected_stdout='NOFAILOVER',
                                                 su_root=True))

    @attr('all', 'revert', 'vcs', 'vcs_tc01')
    def test_01_p_verify_vcs(self):
        """
        @tms_id: litpcds_vcs_tc01
        @tms_requirements_id: LITPCDS-2208, LITPCDS-3766, LITPCDS-5507,
        LITPCDS-3764, LITPCDS-2210, LITPCDS-4475, LITPCDS-3807, TORF-614688

        @tms_title: VCS cluster validation
        @tms_description: Validate various cluster level configurations

        @tms_test_steps:
            @step: Get VCS cluster urls under deployment and store them in a
            list
            @result: VCS cluster urls are stored in list
            @step: Gather vcs cluster properties under deployments
            @result: VCS cluster properties are stored in dictionary
            @step: Verify that the cluster properties are set correctly in
            the model
            @result: VCS cluster properties are present in the model
            @step: Gather URLs of all nodes under the VCS cluster
            @result: Node URLs under cluster are saved in list
            @step: Verify lltheartbeat threads are disabled on all nodes
            @result: lltheartbeat threads disabled
            @step: Verify gab files are present on nodes under cluster
            @result: GAB files are present on nodes under cluster
            @step: Verify llthosts file is present on nodes under cluster
            @result: LLTHOSTS file is present on nodes under cluster
            @step: Verify llttab file exists under node
            @result: LLTTAB file exists on node under cluster
            @step: Verify gabtab file exists on nodes under cluster
            @result: GABTAB file exists on nodes under cluster
            @step: Verify llt service is running
            @result: LLT service is running
            @step: Verify gab service is running
            @result: GAB service is running
            @step: Verify VCS is running
            @result: VCS is running
            @step: Verify gab, llthosts, llttab, and gabtab all exist on node
            and they're contents are correct
            @result: gab, llthosts, llttab, and gabtab all exist on node and
            contents are correct
            @step: Verify cluster_id is correct on all nodes in cluster
            @result: Cluster_id is correct on all nodes in cluster
            @step: Verify cluster name on all nodes in cluster
            @result: Cluster name is correct on all nodes in cluster
            @step: Verify main.cf file exists on all nodes in cluster
            @result: Main.cf file exists on all nodes in cluster
            @step: Verify fencing in cluster
            @result: Fencing is verified in model if present
            @step: Verify LLT links for split-brain behaviour is present
            @result: LLT links are present
            @step: Verify VCS NetworkHost parameters match 'vcs-network-host'
            in the LITP Model
            @result: VCS Network Hosts match Network hosts in litp model
            @step: Verify gab file configuration on nodes
            @result: GAB file is configured on nodes correctly
            @step: Verify puppet restarts vcs service in one cycle
            @result: Puppet restarts vcs service in one cycle
            @step: Verify HA Status works after vcs_path.sh is deleted
            @result: HA status command works after deletion
            @step: Verify NIC resources are online for all non-llt networks
            on nodes
            @result: All NIC resources are online on nodes

       @tms_test_precondition: testset_vcs_initial_xml.py has run
       @tms_execution_type: Automated
        """
        # 1. Get all vcs-clusters under the deployment from the model
        # Get VCS cluster urls and store them in a list
        vcs_cluster_urls = self.find(self.ms_node, "/deployments",
                                     "vcs-cluster", assert_not_empty=False)
        hasys_cmd = self.vcs.get_hasys_state_cmd()
        # 2. For each vcs cluster in model:
        for vcs_cluster_url in vcs_cluster_urls:

            # a. Get the properties of the cluster from the model
            props = self.get_props_from_url(self.ms_node, vcs_cluster_url)

            cluster_id = props["cluster_id"]
            self.log("info", "Cluster id: " + cluster_id + ", Properties: " +
                     str(props))

            # b. Verify that cluster properties are set correct in the model
            # LITPCDS_2208
            self._check_cluster_properties(props)

            cluster_type = props["cluster_type"]

            # c. Get urls of all nodes in the vcs-cluster
            vcs_nodes_urls = self.find(self.ms_node, vcs_cluster_url, "node")

            vcs_nodes = []

            # d. Create list of nodes under the VCS cluster
            for node in vcs_nodes_urls:

                filename = self.get_node_filename_from_url(self.ms_node, node)

                vcs_nodes.append(filename)

            if vcs_nodes == []:
                self.log("info", "No VCS nodes found")

            # e. Verify all VCS related files exist on all nodes in cluster
            # LITPCDS_2208
            for node in vcs_nodes:

                self.log("info", "Verifying llt heartbeat is disabled")
                llthb_expected_value = ["hbthread   = 0"]
                get_hbthread_status_cmd = \
                    "{0} -H query |  {1} 'hbthread.*=.*0'"\
                        .format(VCSUtils.get_llt_status_cmd(),
                                test_constants.GREP_PATH)
                llthb_cmd_out = self.run_command(node,
                                        get_hbthread_status_cmd,
                                        su_root=True, default_asserts=True)
                self.assertEqual(llthb_expected_value, llthb_cmd_out[0],
                                  "llthb output was not as expected")

                for conf_f in self.files_paths:

                    self.log("info", node + " Verifying " + conf_f +
                             " on node")

                    self.assertTrue(self.remote_path_exists(node,
                                                            conf_f),
                                    "File {0} not on node {1}"
                                    .format(conf_f, node))

                # f. Verify the llt, gab, vcs services are running
                # LITPCDS_2208
                for serv in ["llt", "gab", "vcs"]:
                    cmd = self.rhc.get_service_running_cmd(serv)
                    self.log("info", node + " Verifying " + cmd)
                    _, std_err, r_code = self.run_command(node, cmd,
                                                          su_root=True)
                    self.assertEqual(0, r_code)
                    self.assertEqual([], std_err)

                #g. Verify the MN are running
                # LITPCDS_3764
                std_out, std_err, r_code = self.run_command(node, hasys_cmd,
                                                            su_root=True)
                node_count = self.count_text_in_list("RUNNING", std_out)
                self.assertEqual(len(vcs_nodes), node_count)
                self.assertEqual(0, r_code)
                self.assertEqual([], std_err)

            # h. Verify sysconfig/llt and gab start/stop values
            # LITPCDS_2208, LITPCDS_3766
            sysconfllt_grep_cmd = \
                self.rhc.get_grep_file_cmd(self.files_paths[0],
                                           '"LLT_START=1|LLT_STOP=1"')
            sysconfgab_grep_cmd = \
                self.rhc.get_grep_file_cmd(self.files_paths[1],
                                           '"GAB_START=1|GAB_STOP=1"')

            # The seeding value of the cluster depends on the number of nodes
            # listed in the model.
            # If I have 2 or less nodes the seeding is 1. Otherwise I use the
            # formula (#nodes / 2) + 1
            number = 1
            if len(vcs_nodes) > 2:
                number = (len(vcs_nodes) / 2) + 1

            grep_gabtab_cmd = self.rhc.get_grep_file_cmd(self.files_paths[4],
                                                         "/sbin/gabconfig "
                                                         "-c -n{0}"
                                                         .format(number))

            # Verify gab, llthosts and gabtab all exist on node
            # and they're contents are correct
            for node in vcs_nodes:
                self.log("info", node + " Verifying LLT start/stop "
                                        "configurations in {0}"
                         .format(self.files_paths[0]))
                self.run_command(node, sysconfllt_grep_cmd, su_root=False,
                                 default_asserts=True)

                self.log("info", node + " Verifying GAB start/stop "
                                        "configurations in {0}"
                         .format(self.files_paths[1]))
                self.run_command(node, sysconfgab_grep_cmd, su_root=False,
                                 default_asserts=True)

                self.log("info", node + " Verifying gabtab file "
                                        "configurations in {0}"
                         .format(self.files_paths[4]))
                self.run_command(node, grep_gabtab_cmd, su_root=False,
                                 default_asserts=True)

                # LITPCDS_4475: Verify VXVM configurations
                vxvm_cmd = "/opt/VRTS/bin/vxdisk list"

                self.log("info", node + " Verifying VXVM disk list")
                self.run_command(node, vxvm_cmd, su_root=True,
                                 default_asserts=True)

            # i. Verify cluster name.
            # LITPCDS_2208
            cluster_name = vcs_cluster_url.split('/')[-1]

            haclus_cmd = self.vcs.get_haclus_cmd("-value ClusterName")

            main_cf_cmd = self.vcs.validate_main_cf_cmd()
            for node in vcs_nodes:

                self.log("info", node + " Verify ClusterName {0}"
                         .format(cluster_name))
                std_out, _, _ = self.run_command(node, haclus_cmd,
                                           su_root=True,
                                           default_asserts=True)
                self.assertEqual(std_out, [cluster_name])

                # j. Validate MAIN CF
                # LITPCDS_2208
                self.log("info", node + " validate_main_cf_cmd()")
                self.run_command(node, main_cf_cmd, su_root=True,
                                 default_asserts=True)

            # LITPCDS_2210, LITPCDS_4475
            self._verify_fencing_disks(vcs_cluster_url, cluster_id,
                                       cluster_type, vcs_nodes)

            # k .Verify VCS NetworkHost parameters match 'vcs-network-host' in
            # the LITP Model
            # LITPCDS_5507
            llt_nets = str(self.get_props_from_url(self.ms_node,
                                                   vcs_cluster_url,
                                                   'llt_nets')).split(",")

            self.log("info", "Cluster id: " + cluster_id + ", llt_nets: " +
                     str(llt_nets))

            # Find network hosts for each of the networks
            hosts_per_network = {}

            network_host_urls = self.find(self.ms_node, vcs_cluster_url,
                                          "vcs-network-host",
                                          assert_not_empty=False)

            low_prio_net = self.get_props_from_url(self.ms_node,
                                                   vcs_cluster_url,
                                                   'low_prio_net')

            # l. Verify VCS network hosts
            # LITPCDS_5507
            for host_url in network_host_urls:

                nh_props = self.get_props_from_url(self.ms_node, host_url)

                net_name = nh_props['network_name']

                ip_addr = str(nh_props['ip'])

                if net_name not in hosts_per_network:
                    hosts_per_network[net_name] = []

                hosts_per_network[net_name].append(ip_addr.upper())

            for node_url in vcs_nodes_urls:

                node = self.get_node_filename_from_url(self.ms_node, node_url)

                node_hostname = self.get_props_from_url(self.ms_node, node_url,
                                                        'hostname')

                interfaces = self.find_children_of_collect(self.ms_node,
                                                           node_url,
                                                           'network-interface')

                self._verify_llttab_file(interfaces, llt_nets, node_hostname,
                                        low_prio_net)

                self._verify_vcs_network_host(interfaces, llt_nets, node,
                                              cluster_name, node_hostname,
                                              hosts_per_network)

                self._verify_gabconfig(vcs_nodes)

        self.log("info", "Testing puppet cycle")
        # m. Test VCS restarts after a puppet cycle
        # LITPCDS_2208
        self._test_vcs_after_stop()

        self.log("info", "testing hastatus command after vcs_path.sh is "
                         "deleted")
        # n. Verify HA Status works after vcs_path.sh is deleted
        # LIPCDS_3764
        self._test_hastatus_after_vcs_path_del()

        self.log("info", "testing NIC SG has been created for each non-llt"
                         "network and is online")
        # o. Verify NIC SG has been created for each non-llt network and that
        # it is online
        # LITPCDS_3807
        self._test_nic_service_groups()

    @attr('all', 'revert', 'vcs', 'vcs_tc02')
    def test_02_verify_sg_vcs_clustered_service(self):
        """
        @tms_id: litpcds_vcs_tc02
        @tms_requirements_id: LITPCDS-8361, LITPCDS-5653, LITPCDS-4848,
        LITPCDS-4377, LITPCDS-4003, LITPCDS-3995, LITPCDS-3986, LITPCDS-2207,
        LITPCDS-5768, LITPCDS-6164, LITPCDS-6296, LITPCDS-5938, LITPCDS-5653

        @tms_title: VCS clustered service verification
        @tms_description: Verify the various vcs clustered services in the
        LITP Model are deployed correctly

        @tms_test_steps:
            @step: Get VCS clustered services information from LITP Model and
            store in a dictionary
            @result: VCS clustered service information stored in a dictionary
            @step: Get the url of the cluster associated with clustered service
            @result: cluster url acquired
            @step: Get cluster_id based on vcs-clustered-service path.
            @result: VCS Cluster is acquired
            @step: Check that active/standby item property values match with
            service group output result from hagrp -state command
            @result: Services are active on the correct number of nodes
            @step: Verify that packages are installed on the correct nodes
            @result: Packages are installed/not installed on nodes as expected
            @step: Verify VCS attributes AutoStartList and SystemList are set
            based on vcs-clustered-service items node_list property
            @result: AutoStartList and SystemLIst are set correctly
            @step: Verify haconfig item properties are configured correctly
            in VCS
            @result: VCS Attributes match haconfig item property settings
            @step: Verify lsb-runtime item properties are configured correctly
            in VCS
            @result: VCS Attributes match lsb-runtime item property settings
            @step: Verify VCS Application attributes OnlineTimeout and
            OfflineTimeout are set correctly based on LITP Model online and
            offline timeouts.
            @result: VCS Application attributes OnlineTimeout and
            OfflineTimeout are set correctly
            @step: Verify any VXVM volumes under the clustered service
            @result: vxvm volumes are on the right nodes
            @step: Verify vip items
            @result: vips are configured and available
            @step: Verify that services are running on online nodes
            @result: Services are running on online nodes
            @step: Verify that the dependency list property has been applied
            correctly in VCS
            @result: dependency list property has been applied correctly

        @tms_test_precondition: testset_vcs_initial_xml.py has run
        @tms_execution_type: Automated
        """

        # 1. Get all VCS clustered service information from the LITP model and
        # put it into a dictionary
        info = self.get_vcs_model_info()

        networks = list()
        vcs_cluster_url = self.model['clusters'][0]['url']
        networks = self._get_list_of_networks_in_cluster(vcs_cluster_url)

        vcs_nodes = self.find(self.ms_node, vcs_cluster_url, "node")
        node_hostnames = self. _get_vcs_cluster_node_filenames(vcs_nodes)

        # Take first cluster node name to use it for ha methods
        node_name = self.get_props_from_url(self.ms_node, vcs_nodes[0],
                                            'hostname')

        ifcfgs = self._get_ifcfgs_for_vcs_nodes(node_hostnames)

        for cluster in info:

            # Splits up the URL of the clustered service
            url_parts = cluster["vcs-clustered-service"]["url"].split("/")

            # 2. Get the url of the cluster that the clustered service is under
            vcs_cluster_url = "/".join(url_parts[:-2])

            self.log("info", "Cluster URL : {0}".format(vcs_cluster_url))

            # 3. Take cluster name from vcs-cluster path
            cluster_id = url_parts[-3]

            # 4. Retrieve service properties to check them
            service_props = cluster["vcs-clustered-service"]

            # Take service id from its path
            service_id = url_parts[-1]

            # 5. Generate sg name with vcs_utils method
            service_group = self.vcs.generate_clustered_service_name(
                service_id, cluster_id)

            self.log("info", "Checking {0} Service Group State".format(
                service_id))

            # 6. Find all clust.service State value for all the cluster nodes
            gp_states = self.run_vcs_hagrp_display_command(node_name,
                                                           service_group,
                                                           "State")
            # 7. Check that active/standby item values match with
            # service group output result
            actives = standbys = 0

            for node_state in gp_states['State']:
                if "ONLINE" in node_state['VALUE']:
                    actives += 1
                else:
                    standbys += 1

            self.assertTrue(actives == int(service_props['active']))
            self.assertTrue(standbys == int(service_props['standby']))

            # 8. Create a list from node_list property
            node_list = service_props['node_list'].split(",")

            node_hostnames = []
            for i in range(len(node_list)):
                # Get hostname of nodes in node list
                node_list_name = self.get_props_from_url(self.ms_node,
                                                     vcs_cluster_url +
                                                     "/nodes/" +
                                                     node_list[i],
                                                    'hostname')

                node_hostnames.append(node_list_name)

                # 9. Verify that packages under the node are installed
                self._verify_cluster_packages_installed(node_list_name,
                                                            cluster)

            # 10. Verify VCS attributes AutoStartList and SystemList are set
            # based on vcs-clustered-service items node_list property
            self._verify_autostart_and_system_list(node_name, service_group,
                                         service_props, node_hostnames)

            # 11. Find service resource State values for all the cluster nodes
            self.log("info", "Checking {0} Resource State"
                     .format(service_id))

            resource = self.run_vcs_hagrp_resource_command(node_name,
                                                           service_group)

            # 12. Gets the states of the resource
            res_states = self.run_vcs_hares_display_command(node_name,
                                                            resource[0],
                                                            "State")
            # 13. Verify haconfig item
            # ha-service-config item is optional and is not supported in
            # combination with deprecated 'lsb-runtime' item type
            if "ha-service-config" in cluster:
                self._verify_haconfig_props(cluster, resource, node_name)

            # 14. Verify lsb-runtime item
            # lsb-runtime item is optional and deprecated, but we still need
            # to verify it.
            if "lsb-runtime" in cluster:
                self._verify_lsbruntime_props(cluster, resource, node_name)

            # 15. Verify service item
            if "service" in cluster:
                self._verify_service_props(cluster, resource, node_name)

            # 15. Verify VCS Application attributes OnlineTimeout and
            # OfflineTimeout are set correctly based on LITP Model online and
            # offline timeouts.
            # lsb-runtime item type was deprecated before online/offline
            # timeouts were added. They are not managed by Application
            # resources when lsb-runtime is used.
            if "lsb-runtime" not in cluster:
                self._verify_online_offline_timeout(cluster, resource,
                                                    node_name)

            # 16. Verify any VXVM volumes under the clustered service
            self._verify_cluster_vxvm_volume(cluster, node_name,
                                             service_group)
            # 17. Verify vip items
            self._verify_vip_addresses(networks, cluster,
                                       node_hostnames, cluster_id,
                                       service_id, ifcfgs)

            # Check that active/standby item values match with
            # resource output result
            actives = standbys = 0
            online_nodes = []
            for node_state in res_states['State']:
                if "ONLINE" in node_state['VALUE']:
                    actives += 1
                    online_nodes.append(node_state['SYSTEM'])
                else:
                    standbys += 1

            self.assertTrue(actives == int(service_props['active']),
                            str(actives) + "!=" + service_props['active'])

            self.assertTrue(standbys == int(service_props['standby']))

            # 18. Check that services are running on online nodes
            self._verify_services_running(cluster, online_nodes)

            # 19. Checks for dependency list
            self._verify_dependency_list(service_props, cluster_id, service_id,
                                         node_name)

    @attr('all', 'revert', 'vcs', 'vcs_tc03')
    def test_03_verify_vcs_sg_after_update_1(self):
        """
        @tms_id: litpcds_vcs_tc03
        @tms_requirements_id: LITPCDS-11241, LITPCDS-5167, LITPCDS-13411,
        LITPCDS-5172, LITPCDS-5168, LITPCDS-8968

        @tms_title: VCS clustered service verification
        @tms_description: Verify the various vcs clustered services in the
        LITP Model are updated correctly

        @tms_test_steps:
            @step: Get VCS clustered services information from LITP Model and
            store in a dictionary
            @result: VCS clustered service information stored in a dictionary
            @step: Get the url of the cluster associated with clustered service
            @result: cluster url acquired
            @step: Get cluster_id based on vcs-clustered-service path.
            @result: VCS Cluster is acquired
            @step: Verify that the dependency list property has been updated
            correctly in VCS
            @result: dependency list property has been updated
            @step: Check that active/standby item property values match with
            service group output result from hagrp -state command
            @result: Services are active on the correct number of nodes
            @step: Verify that packages are installed on the correct nodes
            @result: Packages are installed/not installed on nodes as expected
            @step: Verify vip items
            @result: vips are configured and available
            @step: Verify haconfig item properties are configured correctly
            in VCS
            @result: VCS Attributes match haconfig item property settings
            @step: Verify VCS triggers are configured and behaving as expected
            @result: VCS triggers are configured correctly

        @tms_test_precondition: testset_vcs_initial_xml.py and
        testset_vcs_update_1.py has run
        @tms_execution_type: Automated
        """

        # 1. Get all VCS clustered service information from the LITP model and
        # put it into a dictionary
        info = self.get_vcs_model_info()

        networks = list()
        vcs_cluster_url = self.model['clusters'][0]['url']
        networks = self._get_list_of_networks_in_cluster(vcs_cluster_url)

        vcs_nodes = self.find(self.ms_node, vcs_cluster_url, "node")
        node_hostnames = self. _get_vcs_cluster_node_filenames(vcs_nodes)

        # Take first cluster node name to use it for ha methods
        node_name = self.get_props_from_url(self.ms_node, vcs_nodes[0],
                                            'hostname')

        ifcfgs = self._get_ifcfgs_for_vcs_nodes(node_hostnames)

        for cluster in info:

            # Splits up the URL of the clustered service
            url_parts = cluster["vcs-clustered-service"]["url"].split("/")

            # 2. Get the url of the cluster that the clustered service is under
            vcs_cluster_url = "/".join(url_parts[:-2])

            self.log("info", "Cluster URL : {0}".format(vcs_cluster_url))

            # 3. Take cluster name from vcs-cluster path
            cluster_id = url_parts[-3]

            # 4. Retrieve service properties to check them
            service_props = cluster["vcs-clustered-service"]

            # Take service id from its path
            service_id = url_parts[-1]

            # 5. Generate sg name with vcs_utils method
            service_group = self.vcs.generate_clustered_service_name(
                service_id, cluster_id)

            self.log("info", "Checking {0} Service Group State".format(
                service_id))

            # 6. Verify SG dependencies based on updated stories below
            # LITPCDS-11241-TC1, LITPCDS-5167-TC1, LITPCDS-8968-TC1
            self._verify_dependency_list(service_props, cluster_id, service_id,
                                         node_name)

            # 7. Check that active/standby item values match with
            # service group output result after update for the following
            # stories
            # LITPCDS-5167-TC1, LITPCDS-5168-TC1, LITPCDS-8968-TC1
            gp_states = self.run_vcs_hagrp_display_command(node_name,
                                                           service_group,
                                                           "State")
            actives = standbys = 0
            for node_state in gp_states['State']:
                if "ONLINE" in node_state['VALUE']:
                    actives += 1
                else:
                    standbys += 1
            self.assertTrue(actives == int(service_props['active']))
            self.assertTrue(standbys == int(service_props['standby']))

            node_hostnames = []
            # 8. Check VCS packages are installed on correct nodes after update
            # LITPCDS-5167-TC1, LITPCDS-5168-TC1, LITPCDS-8968-TC1
            node_list = service_props['node_list'].split(",")
            for i in range(len(node_list)):
                # Get hostname of nodes in node list
                node_list_name = self.get_props_from_url(self.ms_node,
                                                     vcs_cluster_url +
                                                     "/nodes/" +
                                                     node_list[i],
                                                    'hostname')

                node_hostnames.append(node_list_name)
                self._verify_cluster_packages_installed(node_list_name,
                                                        cluster)
            # 9. Verify VIPs after update script is run
            # LITCDS-5167-TC2, LITPCDS-8968-TC1
            self._verify_vip_addresses(networks, cluster,
                                       node_hostnames, cluster_id,
                                       service_id, ifcfgs)

            resource = self.run_vcs_hagrp_resource_command(node_name,
                                                           service_group)
            # 10. Verify haconfig items after update
            # ha-service-config item is optional and is not supported in
            # combination with deprecated 'lsb-runtime' item type
            # LITPCDS-5172-TC1
            if "ha-service-config" in cluster:
                self._verify_haconfig_props(cluster, resource, node_name)

            if "lsb-runtime" not in cluster:
                self._verify_online_offline_timeout(cluster, resource,
                                                    node_name)

            # 11. Verify VCS triggers if any are configured for service groups
            # LITPCDS-13411-TC6
            if "vcs-trigger" in cluster:
                lsb_num = cluster['package'][1]['name']\
                    .split('EXTR-lsbwrapper')
                self._verify_vcs_triggers_configured_and_running(
                    cs_group_name=service_group, lsb_script=lsb_num)

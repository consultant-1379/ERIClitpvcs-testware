"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     Sept 2014
@author:    Philip Daly
@summary:   As a LITP User I want to configure a VCS application attributes so
            that I can control application resource behaviour.
            Agile:
"""

from litp_generic_test import GenericTest, attr
from redhat_cmd_utils import RHCmdUtils
from vcs_utils import VCSUtils
from litp_cli_utils import CLIUtils
from networking_utils import NetworkingUtils
import test_constants
import os


class Story6164(GenericTest):
    """
    LITPCDS-6164:
    As a LITP User I want to configure a VCS application attributes so that I
    can control application resource behaviour.
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
        super(Story6164, self).setUp()

        self.rh_os = RHCmdUtils()
        self.management_server = self.get_management_node_filename()
        self.list_managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.list_managed_nodes[0]
        self.primary_node_url = \
        self.get_node_url_from_filename(self.management_server,
                                        self.primary_node)
        self.vcs = VCSUtils()
        self.traffic_networks = ["traffic1", "traffic2"]
        self.net_utils = NetworkingUtils()
        self.cli = CLIUtils()
        # Location where RPMs to be used are stored
        self.rpm_src_dir = \
            os.path.dirname(os.path.realpath(__file__)) + \
            "/test_lsb_rpms/"

        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.management_server,
                                    "/deployments", "vcs-cluster")[-1]
        self.cluster_id = self.vcs_cluster_url.split("/")[-1]
        self.nodes_urls = self.find(self.management_server,
                                    self.vcs_cluster_url, "node")
        self.node_info = {}
        # get all filenames of nodes in the vcs cluster
        for node in self.nodes_urls:
            filename = self.get_node_filename_from_url(
                self.management_server,
                node)
            hostname = self.get_node_att(filename, "hostname")

            self.node_info[filename] = {'hostname': hostname,
                                        'url': node}

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story6164, self).tearDown()

    def copy_and_import_dummy_lsb(self, list_of_lsb_rpms):
        """
        Function to copy dummy lsb serviced to the node and add them
        to the repo using the litp import command

        Args:
            list_of_lsb_rpms (dict): List of rpms to be added to the
                                     3pp repo on the node
        """
        # Location where RPMs to be used are stored
        rpm_src_dir = \
            os.path.dirname(os.path.realpath(__file__)) + \
            "/test_lsb_rpms/"

        # Repo where rpms will be installed
        repo_dir_3pp = test_constants.PP_PKG_REPO_DIR

        # Copy RPMs to Management Server
        filelist = []
        for rpm in list_of_lsb_rpms:
            filelist.append(self.get_filelist_dict(rpm_src_dir + rpm,
                                                   "/tmp/"))

        self.copy_filelist_to(self.management_server, filelist,
                              add_to_cleanup=False, root_copy=True)

        # Use LITP import to add to repo for each RPM
        for rpm in list_of_lsb_rpms:
            self.execute_cli_import_cmd(
                self.management_server,
                '/tmp/' + rpm,
                repo_dir_3pp)

    def execute_cluster_service_cli(self, conf, cs_name, cli_data):
        """
        Function to generate and execute the CLI which will create
        clustered-services

        Args:
            conf (dictionary): Configuration for clustered-service
            cs_name (str): clustered service name, key to conf dictionary
            cli_data (str): All the CLI data required to create the CS's
        """
        nr_of_nodes = int(conf['params_per_cs'][cs_name]['active']) + \
                          int(conf['params_per_cs'][cs_name]['standby'])

        node_vnames = []
        node_cnt = 0
        for node in self.node_info:
            node_url = self.node_info[node]['url']
            if node_cnt < nr_of_nodes:
                node_vnames.append(node_url.split('/')[-1])
                node_cnt = node_cnt + 1

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

        # create inherit to the service
        self.execute_cli_inherit_cmd(self.management_server,
                                     cli_data['apps']['app_url_in_cluster'],
                                     cli_data['apps']['url'],
                                     add_to_cleanup=False)

        # CREATE THE HA SERVICE CONFIG ITEM
        if 'ha_service_config' in cli_data.keys():
            self.execute_cli_create_cmd(self.management_server,
                                cli_data['ha_service_config']['url'],
                                cli_data['ha_service_config']['class_type'],
                                cli_data['ha_service_config']['options'],
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

        # Create pkgs under the lsb-app
        for pkg_link_data in cli_data['pkg_links']:
            self.execute_cli_inherit_cmd(self.management_server,
                                        pkg_link_data['child_url'],
                                        pkg_link_data['parent_url'],
                                        add_to_cleanup=False)

    def compile_cs_active_node_dict(self, conf):
        """
        Function to compile a dictionary detailing the nodes on which each
        clustered service is active.
        Args:
            conf (dict): Expected model of clustered services
                           and associated IP addresses
        Return:
            dict. A dictionary detailing which clustered services are
                  online on each node.
        """
        cs_active_node_dict = {}
        ##############################################################
        # The hostname of the node is used as the system name in VCS #
        # This piece of code is just retrieving all the hostnames ####
        # for the managed nodes ######################################
        ##############################################################
        list_of_systems = []
        for node in self.find(self.management_server, self.vcs_cluster_url,
                              "node"):
            list_of_systems.append(str(
                self.get_props_from_url(
                    self.management_server,
                    node,
                    filter_prop="hostname")))

        # CYCLE THROUGH CLUSTERED SERVICES BASED ON THEIR VCS NAME ENTRY
        # AND COMPILE A DICTIONARY OF ALL THE NODES ON WHICH THEY ARE ACTIVE.
        for clustered_service in conf["app_per_cs"].keys():
            cs_name = \
            self.vcs.generate_clustered_service_name(clustered_service,
                                                 self.cluster_id)

            # GATHER ALL OF THE NODES ON WHICH THE CS IS ACTIVE
            cmd = self.vcs.get_hagrp_state_cmd() + cs_name
            stdout, stderr, rc = self.run_command(self.primary_node, cmd,
                                                  su_root=True)
            self.assertEqual(0, rc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)

            # ADD AN ENTRY TO THE COMPILATION DICT OF THE CS WITH ANY ACTIVE
            # NODES FOUND FOR IT
            cs_active_node_dict = \
            self.vcs.check_hostname_cs_online(list_of_systems,
                                              clustered_service,
                                              stdout,
                                              cs_active_node_dict)
        return cs_active_node_dict

    def repair_vcs_group_or_resources(self, cs_death_conf, conf,
                                      hostname_mapping,
                                      resource=None):
        """
        Function to repair the VCS CS groups or resources.
        Args:
            cs_death_conf (dict): Clustered servicea expected to be faulted.

            conf (dict): Expected model of clustered services
                           and associated IP addresses

            hostname_mapping (dict): Dictionary with hostname keys and
                                     a value of a list of clustered services.

            resource (Str): Identifies the resource to be repaired. Only
                            valid for group and ipaddress at the moment.
        """
        for clustered_service in cs_death_conf.keys():

            if resource == None:
                self.issue_grp_repair_cmds(clustered_service, hostname_mapping)

            if resource == "ipaddress":
                ip_name_dict = \
                self.vcs.generate_ip_resource_names_from_conf(conf,
                                                              self.cluster_id)
                self.issue_ip_repair_cmds(clustered_service, ip_name_dict)

    def wait_for_resources_to_update(self):
        """
        Function to wait for all VCS resources to update status.
        """
        hastatus_cmd = self.vcs.get_hastatus_sum_cmd()
        grep_cmd = self.rh_os.grep_path
        self.assertEqual(True, self.wait_for_cmd(self.primary_node,
                              hastatus_cmd + " | {0} {1}".format(grep_cmd,
                                                    "STARTING"), 1,
                              timeout_mins=2, default_time=2,
                              su_root=True))

    def issue_ip_repair_cmds(self, cs_name, ip_name_dict):
        """
        Function to issue the vcs clear command against all of the faulted
        ip resources.
        Args:
            cs_name (Str): Name of the clustered service as it
                                     appears in the conf dictionary.

            ip_name_dict (dict): dictionary of ip resource names.
        """
        # IF THE CS NAME OF ONE OF THE CS'S IN THE DEATH LIST IS FOUND
        # IN THE LIST OF FAULTED IP RESOURCES THEN ADD IT TO THE LIST TO BE
        # REPAIRED
        ip_name_list = []
        for ip_name in ip_name_dict.keys():
            if cs_name in ip_name:
                ip_name_list.append(ip_name)

        # CYCLE THROUGH THE LIST OF FOUND IP RESOURCE VCS NAMES AND GATHER
        # THE FAULTED IP ENTRIES, THIS IS TO GATHER THE NODES ON WHICH THE
        # SERVICE HAS FAULTED.
        for ipaddress in ip_name_list:
            hares_state_cmd = self.vcs.get_hares_state_cmd()
            hares_state_cmd = \
            hares_state_cmd + ' {0} | {1} FAULTED'.format(ipaddress,
                                                          self.rh_os.grep_path)
            hares_stdout, _, _ = \
            self.run_command(self.primary_node, hares_state_cmd, su_root=True)
            if hares_stdout == []:
                continue

            # CYCLE THROUGH EACH LINE FOUND. GATHER THE NODE IN THE LINE AND
            # ISSUE THE REPAIR COMMAND AGAINST THE RESOURCE FOR THAT NODE
            for line in hares_stdout:
                lines_split = line.split(' ')
                self.assertTrue(len(lines_split) > 17)
                node_name = [x for x in lines_split if x != ''][2]
                cmd = self.vcs.get_hares_cs_clear_cmd(ipaddress, node_name)
                stdout, stderr, rc = \
                self.run_command(self.primary_node, cmd, su_root=True)
                self.assertEqual(0, rc)
                self.assertEqual([], stderr)
                self.assertEqual([], stdout)

    def online_offlined_service_groups(self, cs_death_conf):
        """
        Function to issue the vcs online command against the clustered
        services which have been offlined due to the test.
        Args:
            cs_death_conf (dict): Clustered services to be onlined by this
                                  function.
        """
        clustered_services = cs_death_conf.keys()
        for clustered_service in clustered_services:
            cs_vcs_name = \
            self.vcs.generate_clustered_service_name(clustered_service,
                                                 self.cluster_id)
            cmd = \
            self.vcs.get_hastatus_sum_cmd() + \
            ' | {0} {1} | {2} OFFLINE'.format(self.rh_os.grep_path,
                                              cs_vcs_name,
                                              self.rh_os.grep_path)
            stdout, _, return_code = \
            self.run_command(self.primary_node, cmd, su_root=True)
            self.assertEqual(0, return_code)
            if stdout == []:
                continue
            # RETRIEVE THE NODE TO ONLINE THE GROUP ON
            for line in stdout:
                grp_status_temp = line.split(' ')
                self.assertTrue(len(grp_status_temp) > 2)
                grp_status = [x for x in grp_status_temp if x != '']
                node_host_name = grp_status[2]
                cmd = \
                self.vcs.get_hagrp_cs_online_cmd(cs_vcs_name, node_host_name)
                _, _, rc = \
                self.run_command(self.primary_node, cmd, su_root=True)
                self.assertEqual(0, rc)

    def kill_service_on_node(self, node, clustered_service, conf):
        """
        Function to kill (stop) the clustered service on the provided node.
        Args:
            node (Str): Node on which the cmd is to be executed.

            clustered_service (Str): Name of the clustered service as it
                                     appears in the conf dictionary.

            conf (dict): Expected model of clustered services
                           and associated IP addresses
        """
        application = conf["app_per_cs"][clustered_service]
        service_name = conf["lsb_app_properties"][application]['service_name']
        cmd = self.rh_os.get_systemctl_stop_cmd(service_name)
        self.run_command(node, cmd, su_root=True, default_asserts=True)

    def issue_grp_repair_cmds(self, clustered_service, hostname_mapping):
        """
        Function to issue the vcs repair command against the specified
        clustered service for the system identified in the hostname mapping
        dictionary.
        Args:
            clustered_service (Str): Name of the clustered service as it
                                     appears in the conf dictionary.

            hostname_mapping (dict): Dictionary with hostname keys and
                                     a value of a list of clustered services.
        """
        service_name = \
        self.vcs.generate_clustered_service_name(clustered_service,
                                            self.cluster_id)
        for hostname in hostname_mapping.keys():
            if clustered_service in hostname_mapping[hostname]:
                system = hostname
        cmd = self.vcs.get_hagrp_cs_clear_cmd(service_name, system)
        stdout, stderr, rc = \
        self.run_command(self.primary_node, cmd, su_root=True)
        self.assertEqual(0, rc)
        self.assertEqual([], stderr)
        self.assertEqual([], stdout)

    def wait_for_resources_to_fault(self, cs_death_conf, conf, resources=None):
        """
        Function to wait for the faulted application or ip address to appear
        in the vcs console.
        Args:
            cs_death_conf (dict): Clustered servicea expected to be faulted.

            conf (dict): Expected model of clustered services
                           and associated IP addresses
        """
        failover_grp_names = {}
        hastatus_cmd = self.vcs.get_hastatus_sum_cmd()
        grep_cmd = self.rh_os.grep_path
        if resources == None:
            for clustered_service in cs_death_conf.keys():
                failover_grp_names[
                self.vcs.generate_clustered_service_name(clustered_service,
                                                self.cluster_id)] = \
                                   self.vcs.generate_application_resource_name(
                                   clustered_service, self.cluster_id,
                                   conf["app_per_cs"][clustered_service]
                                   )

            # CYCLE THROUGH THE HASTATUS CONSOLE AND ENSURE THAT THE RESOURCE
            # THAT HAS BEEN TAMPERED WITH SHOWS UP. USUALLY ONLY THE GROUP AND
            # NODE
            # ARE LISTED, SO IF THE RESOUORCE SHOWS UP THEN IT WILL BE UNDER
            # THE
            # RESOURCES FAILED HEADING
            # WAIT A FEW MOMENTS BETWEEN EACH CYCLE TO ALLOW VCS CONSOLE TO BE
            # UPDATED.
            for failover_grp_name in failover_grp_names.keys():
                self.assertEqual(True, self.wait_for_cmd(self.primary_node,
                                  hastatus_cmd + " | {0} {1}".format(grep_cmd,
                                                       failover_grp_names[
                                                           failover_grp_name]),
                                  0, timeout_mins=2, default_time=2,
                                  su_root=True))
        else:
            for resource in resources:
                self.assertEqual(True, self.wait_for_cmd(self.primary_node,
                                  hastatus_cmd + " | {0} {1}".format(grep_cmd,
                                                       resource),
                                  0, timeout_mins=2, default_time=2,
                                  su_root=True))

    def verify_failover(self, hostname_mapping, conf):
        """
        Function to verify that the clustered service has functioned in its
        expected manner following a service disruption. Active/standy C-S
        should failover to their standy node, parallel C-S should restart on
        the faulted node.

        This should only need to test that the active/standby configuration
        has failed over to its standby node. The verify_vcs_compared_to_conf()
        function should verify that the parallel C-S's have recovered.

        Args:
            hostname_mapping (dict): hostnames on which the C-S were killed.

            conf (dict): Expected model of clustered services
                           and associated IP addresses
        """
        hostnames = hostname_mapping.keys()
        hostname_dict = \
        {hostnames[0]: hostnames[1], hostnames[1]: hostnames[0]}
        # COMPILE A LIST OF THE C-S OPERATING IN ACTIVE/STANDBY MODE
        cs_configuration_dict = conf["params_per_cs"]
        failover_cs = []
        for clustered_service in cs_configuration_dict.keys():
            if conf["params_per_cs"][clustered_service]["active"] == 1 \
            and conf["params_per_cs"][clustered_service]["standby"] == 1:
                failover_cs.append(clustered_service)

        # CYCLE THROUGH THE ACTIVE/STANDBY C-S AND ENSURE THEY ARE ACTIVE
        # ON THEIR STANDBY NODE - THAT IS THE OPPOSITE NODE TO THAT
        # REPORTED IN THE LIST OF HOSTNAME_MAPPINGS
        cs_active_node_dict = {}
        for clustered_service in failover_cs:
            cs_name = \
            self.vcs.generate_clustered_service_name(clustered_service,
                                                 self.cluster_id)

            # GATHER ALL OF THE NODES ON WHICH THE CS IS ACTIVE
            cmd = self.vcs.get_hagrp_state_cmd() + cs_name
            stdout, stderr, rc = self.run_command(self.primary_node, cmd,
                                                  su_root=True)
            self.assertEqual(0, rc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)
            cs_active_node_dict = \
            self.vcs.check_hostname_cs_online(hostnames, clustered_service,
                                     stdout, cs_active_node_dict)
        # CYCLE THROUGH THE DICTIONARY AND ENSURE THAT THE C-S ARENT ACTIVE
        # ON THE NODES ON WHICH THEY WERE KILLED.
        for clustered_service in failover_cs:
            self.assertTrue(clustered_service in cs_active_node_dict.keys(),
                            "{0} not active".format(clustered_service))
            # NODE ON WHICH THE C_S SHOULD NOW BE ACTIVE.
            for hostname in hostname_mapping.keys():
                if not clustered_service in hostname_mapping[hostname]:
                    continue
                standby_host = hostname_dict[hostname]
                self.assertTrue(
                standby_host in cs_active_node_dict[clustered_service],
                "{0} is not active on its standby node {1}.".format(
                clustered_service, standby_host)
                                )

    def kill_provided_clustered_services_children(self, cs_death_list,
                                                  cs_active_node_dict, conf,
                                                  item=None):
        """
        Function to kill the application of the provided clustered-services.
        In the case of parallel clustered services a node shall be
        chosen at random on which to the service shall be killed.

        Args:
            cs_death_list (dict): Clustered services to be killed by this
                                  function.

            cs_active_node_dict (dict): Lists of nodes on which each C-S is
                                        active.

            conf (dict): Expected model of clustered services
                           and associated IP addresses

            item (Str): Child object to be killed, defaults to applications.
                        Currently only covers applications and ipaddress
        Return:
            dict. A dictionary detailing the C-S's active on each hostname.
            dict. A dictionary detailing the ipaddresses to be killed
                  on each node.
        """
        ###################################################
        # CODE TO MATCH THE HOSTNAME TO THE NODE FILENAME #
        ###################################################
        node_mapping = self.map_node_host_to_node_file()
        hostname_mapping = {}
        # node_mapping = {node1: mn1, node2: mn2}
        node_cs_list = {}

        #######################################################################
        # COMPILE A LIST OF CLUSTERED SERVICE APPLICATIONS TO BE KILLED ON    #
        # EACH NODE BASED ON THE PROVIDED CLUSTERED SERVICE DEATH LIST.       #
        # IN THE CASE OF CLUSTERED SERVICES WITH MULTIPLE ACTIVE              #
        # NODES IT IS NECESSARY TO FIND OUT WHICH NODE THE IP ADDRESS IS ON   #
        #######################################################################
        for clustered_service in cs_death_list.keys():
            hostname_mapping = \
            self.vcs.map_node_host_to_clustered_services(cs_active_node_dict,
                                                     clustered_service,
                                                     hostname_mapping)
            node_cs_list = \
            self.vcs.map_node_file_to_clustered_services(cs_active_node_dict,
                                            clustered_service, node_mapping,
                                            node_cs_list)

        #######################################################################
        # CYCLE THROUGH THE COMPILED LIST OF NODES                            #
        # IF THE INTENTION IS TO KILL THE APPLICATIONS THEN DETERMINE THE     #
        # APPLICATION NAME OF THE C-S ACTIVE ON THAT NODE AND STOP THE SERVICE#
        # IF THE INTENTION IS TO KILL A SINGLE OR MULTIPLE IP ADDRESSES       #
        # THEN IT IS REQUIRED TO DETERMINE THE ALIAS ON WHICH THE IP ADDRESS  #
        # IS FUNCTIONING BEFORE CLEARING THE ADDRESS FROM THAT ALIAS          #
        #######################################################################
        ipkilling_dict = {}
        for node in node_cs_list.keys():
            if node not in ipkilling_dict.keys():
                ipkilling_dict[node] = {}
            # {mn1: [CS1, CS2], mn2: [CS3, CS4]}
            clustered_services = node_cs_list[node]
            # [CS1, CS2]
            for clustered_service in clustered_services:
                if item == None:
                    self.kill_service_on_node(node, clustered_service, conf)

                if item == "ipaddress":
                    #ipkilling_dict = {}
                    ipkilling_dict = \
                    self.create_ip_kill_list(cs_death_list, clustered_service,
                                             node, ipkilling_dict)

        for node_to_exe in ipkilling_dict.keys():
            ipaddresses = ipkilling_dict[node_to_exe]
            for ip_to_kill in ipaddresses:
                nic = ipkilling_dict[node_to_exe][ip_to_kill]
                self.kill_ip_address_on_node(node_to_exe, ip_to_kill, nic)

        return hostname_mapping, ipkilling_dict

    def create_ip_kill_list(self, cs_death_list, clustered_service, node,
                            ipkilling_dict):
        """
        Function to compile a dictionary of nodes, and the ip addresses
        residing upon them to be killed during the execution of the test.
        Args:
            cs_death_list (dict): Clustered services to be killed by this
                                  function.

            clustered_service (Str): Name of the clustered service as it
                                     appears in the conf dictionary.

            node (Str): filename of the node on which to execute the cmd.

            ipkilling_dict (dict): dictionary with node filename key and
                                   a value of a dictionary identifying the
                                   ip addresses and interfaces to be killed.
        Returns:
            dict. A dictionary detailing the ip addresses to be killed on
                  each node filename.
        """
        ipaddresses = cs_death_list[clustered_service]
        for ipaddress in ipaddresses:
            ipaddress = ipaddress.replace('_', '.')

            # EXECUTE A GREP OF THE IP ADDRESS TO CHECK WHETHER THE IPADDRESS
            # HAS BEEN ASSIGNED TO THIS NODE
            cmd = self.net_utils.get_ifconfig_cmd() + ' | {0} -F {1}'.\
                format(self.rh_os.grep_path, ipaddress.split('/')[0])
            _, _, rc = \
            self.run_command(node, cmd, su_root=True)
            if rc != 0:
                continue
            # RETRIEVE THE NICS ON THE NODE
            cmd = self.net_utils.get_node_nic_interfaces_cmd()
            stdout, stderr, rc = self.run_command(node, cmd, su_root=True)
            self.assertEqual(0, rc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], stdout)

            # DISCOVER THE NIC WITH THE IPADDRESS
            nic, subnet_bits = \
                self.map_ip_address_to_nic(node, stdout, ipaddress)
            self.assertNotEqual(None, nic)
            self.assertNotEqual(None, subnet_bits)

            # ADD THE IPADDRESS AND ITS NIC TO A DICT FOR KILLING
            # AFTER ALL HAVE BEEN DISCOVERED
            if '/' in ipaddress:
                temp = {ipaddress: nic}
                ipkilling_dict[node].update(temp)
            else:
                temp = {ipaddress + subnet_bits: nic}
                ipkilling_dict[node].update(temp)
        return ipkilling_dict

    def map_ip_address_to_nic(self, node, nics, ipaddress):
        """
        Function to identify the NIC on which the provided ip address is
        assigned and to return the subnet bits.
        Args:
            node (Str): Filename of server on which to execute the command.

            nics (list): List of NICS operating on the node currently.

            ipaddress (Str): ipaddress to be mapped to the NIC.
        Returns:
            str. A string of the NIC name.
            str. A string of the subnet bits.
        """
        #######################################################################
        # CYCLE THROUGH THE PROVIDED LIST OF NICS AND RETURN THE NIC          #
        # TO WHICH THE PROVIDED IP ADDRESS HAS BEEN ASSIGNED.                 #
        #######################################################################
        for nic in nics:
            cmd = \
            self.net_utils.get_ifconfig_cmd(nic)
            stdout, _, return_code = \
            self.run_command(node, cmd, su_root=True)
            self.assertEqual(0, return_code)
            if stdout == []:
                continue
            ifcfg_dict = \
            self.net_utils.get_ifcfg_dict(stdout, nic)
            if '/' in ipaddress:
                ipaddress = ipaddress.split('/')[0]
            if ifcfg_dict['IPV4'] == ipaddress:
                mask = ifcfg_dict['MASK']
                if mask == '255.255.255.0':
                    subnet_bits = '/24'
                elif mask == '255.255.255.128':
                    subnet_bits = '/25'
                return nic, subnet_bits
            elif any(ipaddress in IP for IP in ifcfg_dict['IPV6']):
                subnet_bits = ipaddress.split('/')[-1]
                return nic, subnet_bits

        return None, None

    def kill_ip_address_on_node(self, node, ip_to_kill, nic):
        """
        Function to Kill (delete) the provided ip address from the provided NIC
        on the provided node.
        Args:
            node (Str): Node on which the cmd is to be executed.

            ip_to_kill (Str): ip address which is to be killed, including a
                              /subnet bits ending.

            nic (Str): NIC on which the ipaddress resides.
        """
        if ':' in ip_to_kill:
            cmd = \
            self.net_utils.get_clear_ip_cmd(ip_to_kill, nic, ip6=True)
        else:
            cmd = \
            self.net_utils.get_clear_ip_cmd(ip_to_kill, nic)
        stdout, stderr, rc = \
        self.run_command(node, cmd, su_root=True)
        self.assertEqual(0, rc)
        self.assertEqual([], stderr)
        self.assertEqual([], stdout)

    def map_node_host_to_node_file(self):
        """
        Function to map the node hostnames to their respective filenames
        Returns:
            dict. A dictionary mapping the nodes hostname to the node
                  filename.
        """
        node_mapping = {}
        for node in self.find(self.management_server, self.vcs_cluster_url,
                              "node"):

            node_filename = \
            self.get_node_filename_from_url(self.management_server, node)
            node_hostname = self.get_node_att(node_filename, "hostname")
            node_mapping[node_hostname] = node_filename
        return node_mapping

    def check_ip_res_state(self, ip_resource_dict, ip_resources_list,
                           ipaddress_list):
        '''
        Function to check the state of the IP resource of the specified CS

        Args:
            ip_resource_dict(dict): Dictionary generated by
            generate_ip_resource_names_from_conf() in vcs_utils

            ip_resources_list(list): List to be appended with the VCS IP
            resource names for each IP address that appears in the
            ipaddress_list

            ipaddress_list(list): List of IP addresses to be killed on the node

        Returns:
            List. A list of the VCS IP resources.
        '''
        for ip_res in ip_resource_dict.keys():
            hastatus_cmd = self.vcs.get_hares_state_cmd() + \
                           ' | {0} {1} | {0} {2}'.format(self.rh_os.grep_path,
                                                         ip_res, 'ONLINE')
            res_output, stderr, rc = \
                self.run_command(self.primary_node,
                                 hastatus_cmd, su_root=True)
            self.assertEqual(0, rc)
            self.assertEqual([], stderr)
            self.assertNotEqual([], res_output)
            for line in res_output:
                line = line.split(' ')
                line_blocks = [x for x in line if x != '']
                self.assertTrue(len(line_blocks) > 2)
                node_host_to_exe = line_blocks[2]
                node_dict = self.map_node_host_to_node_file()
                node_to_exe = node_dict[node_host_to_exe]
                ip_res_val_cmd = self.vcs.get_hares_ip_resource_address(ip_res)
                stdout, stderr, rc = \
                    self.run_command(node_to_exe, ip_res_val_cmd, su_root=True)
                self.assertEqual(0, rc)
                self.assertEqual([], stderr)
                self.assertNotEqual([], stdout)
                if stdout[0] in ipaddress_list:
                    ip_resources_list.append(ip_res)
        return ip_resources_list

    @attr('all', 'non-revert', 'kgb-other')
    def test_07_n_vcs_para_app_restart_and_act_stndby_app_failover(self):
        """
        @tms_id: litpcds_6164_tc07
        @tms_requirements_id: LITPCDS-6164
        @tms_title: Ensure killed apps on parallel clustered services
         Restart, and apps on active/standby clustered services Failover
        @tms_description:
         This test will kill the applications in a series of previously
            deployed clustered services and ensure that the applications
            operating on parallel clustered services restart, and that the
            applications operating on active standby clustered services
            fail over to their standby nodes.
        @tms_test_steps:
        @step: Generate configuration for the plans
        @result: Plan configuration generated
        @step: Run the 'hagrp -state' command to verify configuration
        @result: No errors output
        @result: Return code 0 is output
        @step: Run the 'hares -state' command to verify configuration
        @result: No errors output
        @result: Return code 0 is output
        @step: Determine the device that each network is on
        @result: Node network devices stored in network_dev_map
        @step: For each plan configuration, verify that each clustered-service
        and all of its resources are online on the correct nodes
        @result: Successfully verified.
        @step: Determine which nodes are active and which are parallel
        @result: The active and parallel nodes are determined.
        @step: Create a list of clustered services on which the applications
        will be destroyed.
        @result: List created.
        @step: Kill these applications on the nodes on which they're active.
        @result: The above kill is executed.
        @step: Waited for the faulted applications to appear in the vcs console
        @result: Applications appear in the console
        @step: Wait for all onlining attempts to complete.
        @result: All onlining attempts complete and waiting is ceased.
        @step: Verify that applications are active but not on the node on which
        they were originally active. ie. Failover successful
        @result: The above is successfully verified.
        @step: Verify configuration using the hagrp -state command to prove
        parallel resources restarted as expected
        @result: No errors output, return code 0 output
        @step: Verify conf using the hares -state command
        @result: No errors output, return code 0 output
        @result: Parallel resources restarted as expected
        @step: Repair the faulted services
        @result: Faulted services repaired
        @step: Wait for services to finish onlining (needed for next test)
        @result: Services finished onlining.
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        # Generate configuration for the plans
        conf = \
        self.vcs.generate_plan_conf_service_and_vip_children(
                                                        self.traffic_networks)

        # Verify configuration
        # Output from the hagrp -state command
        cmd = self.vcs.get_hagrp_state_cmd()
        hagrp_output, stderr, return_code = \
        self.run_command(self.primary_node, cmd, su_root=True)
        self.assertEqual(0, return_code)
        self.assertEqual([], stderr)

        # Output from the hares -state command
        cmd = self.vcs.get_hares_state_cmd()
        hares_output, stderr, return_code = \
        self.run_command(self.primary_node, cmd, su_root=True)
        self.assertEqual(0, return_code)
        self.assertEqual([], stderr)

        # Determine the device that each network is on
        network_dev_map = \
        self.get_node_network_devices(self.management_server,
                                      self.primary_node_url)

        cs_names = conf['app_per_cs'].keys()
        for cs_name in cs_names:
            self.assertTrue(self.vcs.verify_vcs_clustered_services(
                                                             cs_name,
                                                             self.cluster_id,
                                                             conf,
                                                             hagrp_output,
                                                             hares_output,
                                                             network_dev_map))

        # VERIFY WHICH NODES ARE ACTIVE....parallel
        cs_active_node_dict = \
            self.compile_cs_active_node_dict(conf)
        cs_death_conf = {
            "CS32": [],
            "CS33": []
        }
        hostname_mapping = {}
        try:
            # KILL THE APPLICATIONS BASED ON THE CS DEATH CONF...failover
            hostname_mapping, _ = \
                self.kill_provided_clustered_services_children(
                    cs_death_conf, cs_active_node_dict, conf)

            cs_death_conf = {
                "CS31": [],
                "CS34": [],
                "CS35": []
            }

            # KILL THE APPLICATIONS BASED ON THE CS DEATH CONF
            hostname_mapping, _ = \
               self.kill_provided_clustered_services_children(
                   cs_death_conf, cs_active_node_dict, conf)
            ###################################################################
            # WAIT FOR ALL OF THE APPLICATIONS TO SHOW UP IN THE HASTATUS LIST
            # WHICH ONLY OCCURS WHEN THEY FAULT
            ###################################################################
            self.wait_for_resources_to_fault(cs_death_conf, conf)

            ###################################################################
            # WAIT A FEW MOMENTS FOR VCS TO ATTEMPT TO START ONLINING THE
            # FAILOVER RESOURCES AND THEN CYCLE THROUGH THE HASTATUS UNTIL THE
            # RESOURCES ONLINING HEADING DISAPPEARS INDICATING NO FURTHER
            # ONLINING SHALL BE TAKING PLACE THUS ALLOWING A CHECK OF THE
            # SERVICE STATUS
            ###################################################################
            self.check_all_vcs_groups_returned_to_online_status(conf,
                                                            self.primary_node,
                                                            self.cluster_id)

            # VERIFY THE SERVICES ARE ACTIVE BUT NOT ON THEIR
            # ORIGINALLY ACTIVE NODES
            host_dict = self.map_node_host_to_node_file()
            for host in host_dict.keys():
                if host not in hostname_mapping.keys():
                    hostname_mapping[host] = []
            self.verify_failover(hostname_mapping, conf)

            # Verify configuration to prove parallel
            # services restarted as expected
            # Verify configuration
            # Output from the hagrp -state command
            cmd = self.vcs.get_hagrp_state_cmd()
            hagrp_output, stderr, return_code = \
            self.run_command(self.primary_node, cmd, su_root=True)
            self.assertNotEqual([], hagrp_output)
            self.assertEqual(0, return_code)
            self.assertEqual([], stderr)

            # Output from the hares -state command
            cmd = self.vcs.get_hares_state_cmd()
            hares_output, stderr, return_code = \
            self.run_command(self.primary_node, cmd, su_root=True)
            self.assertNotEqual([], hares_output)
            self.assertEqual(0, return_code)
            self.assertEqual([], stderr)

            # Determine the device that each network is on
            network_dev_map = \
            self.get_node_network_devices(self.management_server,
                                          self.primary_node_url)
            cs_names = conf['app_per_cs'].keys()
            for cs_name in cs_names:
                self.assertTrue(self.vcs.verify_vcs_clustered_services(
                                                             cs_name,
                                                             self.cluster_id,
                                                             conf,
                                                             hagrp_output,
                                                             hares_output,
                                                             network_dev_map))
        finally:
            ###################################################################
            #  REPAIR THE FAULTED SERVICES. PRIOR TO KILLING IP'S RESOURCES
            ###################################################################
            self.repair_vcs_group_or_resources(cs_death_conf, conf,
                                               hostname_mapping)

            ###################################################################
            # DO NOT END THE TEST UNTIL THE SERVICE GROUPS FINISH ONLINING
            # OTHERWISE THE INITIAL VERIFICATION STEP IN THE SUBSEQUENT TEST
            # SHALL FAIL
            ###################################################################
            self.wait_for_resources_to_update()

    @attr('all', 'non-revert', 'kgb-other')
    def test_08_n_vcs_act_stanby_single_ip_failover_and_para_fault(self):
        """
        @tms_id: litpcds_6164_tc08
        @tms_requirements_id: LITPCDS-6164
        @tms_title: Verify failover when ips killed on active standby and apps
        are faulted on parallel.
        @tms_description:
         This test will kill a single ip resource in a series of previously
            deployed clustered services and ensure that the applications
            operating on active standby clustered services fail over to their
            standby nodes and that parallel services are listed as faulted.
        @tms_test_steps:
        @step: Generate configuration for the plans
        @result: Plan configuration generated
        @step: Run the 'hagrp -state' command to verify configuration
        @result: No errors output
        @result: Return code 0 is output
        @step: Run the 'hares -state' command to verify configuration
        @result: No errors output
        @result: Return code 0 is output
        @step: Determine the device that each network is on
        @result: Node network devices stored in network_dev_map
        @step: For each plan configuration, verify that each clustered-service
        and all of its resources are online on the correct nodes
        @result: Successfully verified.
        @step: Generate a list of ip resources to kill
        @result: List generated
        @step: Kill the parallel ip resources.
        @result: Resources killed.
        @step: Wait for the applications to show up in the hastatus list,
        verifying that they are faulted.
        @result: Applications are shown as faulted.
        @step: Repair the faulted services
        @result: The services are no longer in a Faulted state.
        @step: Online the offlined groups
        @result: All offlined groups return to Online status.
        @step: Create an active node dictionary
        @result: Active node dict created
        @step: Create list of IP resources to offline
        @result: List created successfully
        @step: Kill the failover ips
        @result: Resources killed
        @step: Wait for the faulted applications to show in the hastatus list
        @result: Faulted applications listed
        @step: Wait for all groups to finish Onlining.
        @result: All groups finished onlining
        @step: Verify the service groups are now active on their standby nodes.
        @result: Service groups have failed over to alternative node
        successfully
        @step: Repair the faulted services
        @result: Faulted services are no longer in this state
        @step: Wait for the service groups to finish Onlining.
        @result: No service groups are left in an Onlining state
        @tms_test_precondition: NA
        @tms_execution_type: Automated
        """

        # Generate configuration for the plans
        conf = \
        self.vcs.generate_plan_conf_service_and_vip_children(
                                                        self.traffic_networks)

        # Verify configuration
        # Output from the hagrp -state command
        cmd = self.vcs.get_hagrp_state_cmd()
        hagrp_output, stderr, return_code = \
        self.run_command(self.primary_node, cmd, su_root=True)
        self.assertNotEqual([], hagrp_output)
        self.assertEqual(0, return_code)
        self.assertEqual([], stderr)

        # Output from the hares -state command
        cmd = self.vcs.get_hares_state_cmd()
        hares_output, stderr, return_code = \
        self.run_command(self.primary_node, cmd, su_root=True)
        self.assertNotEqual([], hares_output)
        self.assertEqual(0, return_code)
        self.assertEqual([], stderr)

        # Determine the device that each network is on
        network_dev_map = \
        self.get_node_network_devices(self.management_server,
                                      self.primary_node_url)
        cs_names = conf['app_per_cs'].keys()
        for cs_name in cs_names:
            self.assertTrue(self.vcs.verify_vcs_clustered_services(
                                                             cs_name,
                                                             self.cluster_id,
                                                             conf,
                                                             hagrp_output,
                                                             hares_output,
                                                             network_dev_map))
        # VERIFY WHICH NODES ARE ACTIVE....parallel
        cs_active_node_dict = \
            self.compile_cs_active_node_dict(conf)

        cs_death_conf = {
            "CS32": ["172.16.100.183"],
            "CS33": ["2001:2200:ef::14/64"]
        }

        temp_list = []
        for clustered_service in cs_death_conf.keys():
            temp_list.extend(cs_death_conf[clustered_service])
        ipaddress_list = []
        for ipaddress in temp_list:
            if '/' in ipaddress:
                ipaddress = ipaddress.split('/')[0]
            ipaddress_list.append(ipaddress)
        ip_resource_dict = self.vcs.generate_ip_resource_names_from_conf(conf,
                                                            self.cluster_id)
        ip_resources_list = []
        ip_resources_list = \
        self.check_ip_res_state(ip_resource_dict, ip_resources_list,
                                ipaddress_list)
        hostname_mapping = {}
        try:
            # KILL THE IPS BASED ON THE CS DEATH CONF
            hostname_mapping, _ = \
                self.kill_provided_clustered_services_children(
                    cs_death_conf, cs_active_node_dict, conf, item="ipaddress")

            ###################################################################
            # WAIT FOR ALL OF THE APPLICATIONS TO SHOW UP IN THE HASTATUS LIST
            # WHICH ONLY OCCURS WHEN THEY FAULT
            ##################################################################
            self.wait_for_resources_to_fault(cs_death_conf, conf,
                                             resources=ip_resources_list)

            ###################################################################
            #     REPAIR THE FAULTED SERVICES. PRIOR TO KILLING IP'S RESOURCES
            ###################################################################
            self.repair_vcs_group_or_resources(cs_death_conf, conf,
                                               hostname_mapping,
                                               resource="ipaddress")
            ###################################################################
            #     ONLINE THE OFFLINED GROUPS. #
            ###################################################################
            self.online_offlined_service_groups(cs_death_conf)
            self.check_all_vcs_groups_returned_to_online_status(conf,
                                                            self.primary_node,
                                                            self.cluster_id)

            # VERIFY WHICH NODES ARE ACTIVE...failover
            cs_active_node_dict = \
                self.compile_cs_active_node_dict(conf)

            cs_death_conf = {
                "CS31": ["172.16.100.181"],
                "CS35": ["2001:2200:ef::17/64"]
            }
            temp_list = []
            for clustered_service in cs_death_conf.keys():
                temp_list.extend(cs_death_conf[clustered_service])
            ipaddress_list = []
            for ipaddress in temp_list:
                if '/' in ipaddress:
                    ipaddress = ipaddress.split('/')[0]
                ipaddress_list.append(ipaddress)
            ip_resource_dict = \
            self.vcs.generate_ip_resource_names_from_conf(conf,
                                                          self.cluster_id)
            ip_resources_list = []
            ip_resources_list = \
            self.check_ip_res_state(ip_resource_dict, ip_resources_list,
                                    ipaddress_list)
            # KILL THE IPS BASED ON THE CS DEATH CONF
            hostname_mapping, _ = \
                self.kill_provided_clustered_services_children(
                    cs_death_conf, cs_active_node_dict, conf, item="ipaddress")
            ###################################################################
            # WAIT FOR ALL OF THE APPLICATIONS TO SHOW UP IN THE HASTATUS LIST
            # WHICH ONLY OCCURS WHEN THEY FAULT
            ##################################################################
            self.wait_for_resources_to_fault(cs_death_conf, conf,
                                             resources=ip_resources_list)

            ##################################################################
            # WAIT A FEW MOMENTS FOR VCS TO ATTEMPT TO START ONLINING THE
            # FAILOVER RESOURCES AND THEN CYCLE THROUGH THE HASTATUS UNTIL
            # THE RESOURCES ONLINING HEADING DISAPPEARS INDICATING NO
            # FURTHER ONLINING SHALL BE TAKING PLACE THUS ALLOWING A
            # CHECK OF THE SERVICE STATUS
            ##################################################################
            self.check_all_vcs_groups_returned_to_online_status(conf,
                                                            self.primary_node,
                                                            self.cluster_id)

            # VERIFY THE SERVICES ARE ACTIVE BUT NOT ON THEIR
            # ORIGINALLY ACTIVE NODES
            host_dict = self.map_node_host_to_node_file()
            for host in host_dict.keys():
                if host not in hostname_mapping.keys():
                    hostname_mapping[host] = []
            self.verify_failover(hostname_mapping, conf)
        finally:
            ###################################################################
            #     REPAIR THE FAULTED SERVICES. PRIOR TO KILLING IP'S RESOURCES
            ###################################################################
            self.repair_vcs_group_or_resources(cs_death_conf, conf,
                                               hostname_mapping,
                                           resource="ipaddress")

            ###################################################################
            # DO NOT END THE TEST UNTIL THE SERVICE GROUPS FINISH ONLINING
            # OTHERWISE THE INITIAL VERIFICATION STEP IN THE SUBSEQUENT TEST
            # SHALL FAIL
            ###################################################################
            self.wait_for_resources_to_update()

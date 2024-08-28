"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     June 2014
@author:    Philip Daly
@summary:   Integration tests for testing VCS scenarios
            Agile: STORY LITPCDS-3997
            As an application designer I want to set
            up resource dependencies so that my VCS
            service group can failover when a fault is
            detected
"""
from litp_generic_test import GenericTest, attr
from litp_cli_utils import CLIUtils
from redhat_cmd_utils import RHCmdUtils
from vcs_utils import VCSUtils
from networking_utils import NetworkingUtils
from random import Random
import time


class Story3997(GenericTest):
    """
    As an application designer I want to set up resource dependencies
    so that my VCS service group can failover when a fault is detected

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
        super(Story3997, self).setUp()
        self.cli = CLIUtils()
        self.rh_os = RHCmdUtils()
        self.management_server = self.get_management_node_filename()
        self.list_managed_nodes = self.get_managed_node_filenames()
        self.primary_node = self.list_managed_nodes[0]
        self.primary_node_url = self.get_node_url_from_filename(
            self.management_server, self.primary_node)
        self.vcs = VCSUtils()
        self.net_utils = NetworkingUtils()
        self.random = Random()

        # Current assumption is that only 1 VCS cluster will exist
        self.vcs_cluster_url = self.find(self.management_server,
                                    "/deployments", "vcs-cluster")[-1]
        self.cluster_id = self.vcs_cluster_url.split("/")[-1]

        # This has to be hardcoded for now, as there is no way to search
        # the model for only traffic networks
        self.traffic_networks = ["traffic1", "traffic2"]

    def tearDown(self):
        """
        Description:
            Runs after every single test
        Actions:
            -
        Results:
            The super class prints out diagnostics and variables
        """
        super(Story3997, self).tearDown()

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
            self.check_hostname_cs_online(list_of_systems, clustered_service,
                                          stdout,
                                          cs_active_node_dict)
        return cs_active_node_dict

    @staticmethod
    def check_hostname_cs_online(hostnames, clustered_service,
                                 vcs_output, cs_active_node_dict):
        """
        Function to check whether a clustered service is active on the provided
        hostnames.

        Args:
            hostnames (list): List of host names of nodes to be checked against

            clustered_service (Str): Name of the clustered service as it
                                     appears in the conf dictionary.

            vcs_output (list): The output from the VCS query issued against
                              the clustered service.

            cs_active_node_dict (dict): Lists of nodes on which each C-S is
                                        active.
        Returns:
            dict. A dictionary that identifies which C-S's are online on
                  each node.
        """
        cs_active_node_dict[clustered_service] = []
        for hostname in hostnames:
            for line in vcs_output:
                if hostname in line and "ONLINE" in line:
                    cs_active_node_dict[clustered_service].append(hostname)
        if cs_active_node_dict[clustered_service] == []:
            del cs_active_node_dict[clustered_service]
        return cs_active_node_dict

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
            self.check_hostname_cs_online(hostnames, clustered_service,
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
        # NODES IT IS NECESSAY TO FIND OUT WHICH NODE THE IP ADDRESS IS ON    #
        #######################################################################
        for clustered_service in cs_death_list.keys():
            hostname_mapping = \
            self.map_node_host_to_clustered_services(cs_active_node_dict,
                                                     clustered_service,
                                                     hostname_mapping)
            node_cs_list = \
            self.map_node_file_to_clustered_services(cs_active_node_dict,
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
            node_mapping[str(
                self.get_props_from_url(
                    self.management_server,
                    node,
                    filter_prop="hostname"))] = node_filename
        return node_mapping

    def map_node_file_to_node_host(self):
        """
        Function to map the node filenames to their respective hostnames.
        Returns:
            dict. A dictionary mapping the nodes filename to the nodes
                  hostname.
        """
        file_to_host_dict = {}
        host_to_file_dict = self.map_node_host_to_node_file()
        for host in host_to_file_dict.keys():
            # {node1: mn1, node2: mn2}
            file_name = host_to_file_dict[host]
            file_to_host_dict[file_name] = host
        return file_to_host_dict

    @staticmethod
    def map_node_host_to_clustered_services(cs_active_node_dict,
                                            clustered_service,
                                            hostname_mapping):
        """
        Function to map the nodes hostnames to the clustered services that
        reside upon them.
        Args:
            cs_active_node_dict (dict): Dictionary with keys of cs names and
                                        a value of a list of hostnames on which
                                        the cs's are active

            clustered_service (Str): Name of the clustered service as it
                                     appears in the conf dictionary.

            hostname_mapping (dict): Dictionary with hostname keys and
                                     a value of a list of clustered services.
        Returns:
            dict. A dictionary identifying which C-S's are active on each
                  hostname.
        """
        active_nodes = cs_active_node_dict[clustered_service]
        if len(active_nodes) > 1:
            for active_node in range(len(active_nodes)):
                hostname = active_nodes[active_node]
                if hostname not in hostname_mapping.keys():
                    hostname_mapping[hostname] = []
                hostname_mapping[hostname].append(clustered_service)
        else:
            hostname = active_nodes[0]
            # DICT TO BE RETURNED TO ENABLE VERIFICATION OF FAILOVER/PARALLEL
            # FUNCTIONALITY OCCURRING.
            if hostname not in hostname_mapping.keys():
                hostname_mapping[hostname] = []
            hostname_mapping[hostname].append(clustered_service)
        return hostname_mapping

    @staticmethod
    def map_node_file_to_clustered_services(cs_active_node_dict,
                                            clustered_service,
                                            node_mapping, node_cs_list):
        """
        Function to map the nodes files to the clustered services that
        reside upon the nodes to which they connect.
        Args:
            cs_active_node_dict (dict): Dictionary with keys of cs names and
                                        a value of a list of hostnames on which
                                        the cs's are active

            clustered_service (Str): Name of the clustered service as it
                                     appears in the conf dictionary.

            node_mapping (dict): dictionary with hostname keys and a value
                                 identifying the node filename.

            node_cs_list (dict): dictionary identifying which C-S's
                                 are active one which node filenames.
        Returns:
            dict. A dictionary identifying which C-S's are active
                  one which node filenames.
        """
        active_nodes = cs_active_node_dict[clustered_service]
        if len(active_nodes) > 1:
            for active_node in range(len(active_nodes)):
                # index = self.random.randint(0, 1)
                # hostname = active_nodes[index]
                hostname = active_nodes[active_node]
                node_filename = node_mapping[hostname]
                if node_filename not in node_cs_list.keys():
                    node_cs_list[node_filename] = []
                node_cs_list[node_filename].append(clustered_service)
        else:
            hostname = active_nodes[0]
            node_filename = node_mapping[hostname]
            if node_filename not in node_cs_list.keys():
                node_cs_list[node_filename] = []
            node_cs_list[node_filename].append(clustered_service)

        return node_cs_list

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
                grp_status = [x for x in grp_status_temp if x != '']
                node_host_name = grp_status[2]
                cmd = \
                self.vcs.get_hagrp_cs_online_cmd(cs_vcs_name, node_host_name)
                _, _, rc = \
                self.run_command(self.primary_node, cmd, su_root=True)
                self.assertEqual(0, rc)

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
            cmd = self.net_utils.get_ifconfig_cmd() + \
                  ' | {0} -F {1}'.format(self.rh_os.grep_path, ipaddress)
            _, _, rc = self.run_command(node, cmd, su_root=True)
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
            temp = {ipaddress + subnet_bits: nic}
            ipkilling_dict[node].update(temp)
        return ipkilling_dict

    def verify_ip_faulted(self, ipkilling_dict):
        """
        Function to check whether all of the provided ip addresses have
        indeed faulted on the clustered services.
        Args:
            ipkilling_dict (dict): dictionary with node filename key and
                                   a value of a dictionary identifying the
                                   ip addresses and interaces to be killed.
        """
        node_file_to_host_dict = self.map_node_file_to_node_host()
        # {'mn1':
        # {'172.16.100.60/24': 'eth4:1', '172.16.100.30/24': 'eth4:2'},
        # 'mn2': {'172.16.100.20/24': 'eth4:10'}}
        # COMPILE DICT
        killed_dict = {}
        for file_name in ipkilling_dict.keys():
            ipaddresses = ipkilling_dict[file_name].keys()
            for ipaddress in ipaddresses:
                index = ipaddress.index('/')
                address = ipaddress[:index]
                hostname = node_file_to_host_dict[file_name]
                if hostname not in killed_dict.keys():
                    killed_dict[hostname] = []
                killed_dict[hostname].append(address)
        resource_dict = {}
        # COMPILE A DICTIONARY OF IP RESOURCES THAT HAVE FAULTED
        # AND RELATE THEM TO THE NODE UPON WHICH THEY RESIDE.
        # THERE COULD BE MULTIPLE FAULTED IP ADDRESSES FOUND
        # IN THE CASE OF MULTI-NODE PARALLEL C-S's
        cmd = \
        self.vcs.get_hares_state_cmd() + \
        ' | {0} Res_IP | {1} FAULTED'.format(self.rh_os.grep_path,
                                             self.rh_os.grep_path)
        stdout, _, _ = \
        self.run_command(self.primary_node, cmd, su_root=True)
        self.assertNotEqual([], stdout)
        for resource_line in stdout:
            resources_temp = resource_line.split(' ')
            resources = [x for x in resources_temp if x != '']
            resource = resources[0]
            node = resources[2]
            if node not in resource_dict.keys():
                resource_dict[node] = []
            resource_dict[node].append(resource)
            # { node1: ['Res_IP_cluster1_CS6_APP6_traffic1_1']}
        # MAPPING THE ADDRESS VALUE OF THE VCS RESOURCE TO THE
        # NODE UPON WHICH THE RESOURCE ADDRESS HAS BEEN KILLED
        ipaddress_dict = {}
        node_mapping = self.map_node_host_to_node_file()
        for resource_node in resource_dict.keys():
            if resource_node not in ipaddress_dict.keys():
                ipaddress_dict[resource_node] = []
            resources = resource_dict[resource_node]
            for resource in resources:
                exe_node = node_mapping[resource_node]
                cmd = self.vcs.get_hares_ip_resource_address(resource)
                stdout, _, _ = \
                self.run_command(exe_node, cmd, su_root=True)
                self.assertNotEqual([], stdout)
                ipaddress_dict[resource_node].append(stdout[0])

        # CHECK THAT BOTH DICTIONARIES ARE THE SAME THUS PROVING THAT THE
        # KILLED IP ADDRESSES HAVE CORRECTLY FAULTED
        diff = set(ipaddress_dict.keys()) - set(killed_dict.keys())
        self.assertEqual(set([]), diff)
        for ipaddress_node in ipaddress_dict.keys():
            addresses_on_node = ipaddress_dict[ipaddress_node].sort()
            killed_addresses_on_node = killed_dict[ipaddress_node].sort()
            self.assertEqual(addresses_on_node, killed_addresses_on_node)

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
        cmd = \
        self.net_utils.get_clear_ip_cmd(ip_to_kill, nic)
        stdout, stderr, rc = \
        self.run_command(node, cmd, su_root=True)
        self.assertEqual(0, rc)
        self.assertEqual([], stderr)
        self.assertEqual([], stdout)

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
        service_name = conf["lsb_app_properties"][application]['name']
        cmd = self.rh_os.get_systemctl_stop_cmd(service_name)
        self.run_command(node, cmd, su_root=True, default_asserts=True)

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
            if ifcfg_dict['IPV4'] == ipaddress:
                mask = ifcfg_dict['MASK']
                if mask == '255.255.255.0':
                    subnet_bits = '/24'
                elif mask == '255.255.255.128':
                    subnet_bits = '/25'
                return nic, subnet_bits
        return None, None

    def wait_for_resources_to_fault(self, cs_death_conf, conf):
        """
        Function to wait for the faulted application or ip address to appear
        in the vcs console.
        Args:
            cs_death_conf (dict): Clustered servicea expected to be faulted.

            conf (dict): Expected model of clustered services
                           and associated IP addresses
        """
        # THIS FUNCTION NEEDS TO BE UPDATED TO CHECK FOR IP RESOURCE NAMES
        # AT THE MOMENT IT ONLY CHECKS FOR THE CLUSTERED SERVICE NAME
        failover_grp_names = {}

        for clustered_service in cs_death_conf.keys():
            failover_grp_names[
            self.vcs.generate_clustered_service_name(clustered_service,
                                            self.cluster_id)
                               ] = \
                               self.vcs.generate_application_resource_name(
                               clustered_service, self.cluster_id,
                               conf["app_per_cs"][clustered_service]
                               )

        # CYCLE THROUGH THE HASTATUS CONSOLE AND ENSURE THAT THE RESOURCE
        # THAT HAS BEEN TAMPERED WITH SHOWS UP. USUALLY ONLY THE GROUP AND NODE
        # ARE LISTED, SO IF THE RESOUORCE SHOWS UP THEN IT WILL BE UNDER THE
        # RESOURCES FAILED HEADING
        # WAIT A FEW MOMENTS BETWEEN EACH CYCLE TO ALLOW VCS CONSOLE TO BE
        # UPDATED.
        cmd = self.vcs.get_hastatus_sum_cmd()
        for failover_grp_name in failover_grp_names.keys():
            found = False
            counter = 0
            while found == False and counter < 20:
                stdout, stderr, rc = \
                self.run_command(self.primary_node,
                                 cmd, su_root=True)
                self.assertEqual(0, rc)
                self.assertEqual([], stderr)
                self.assertNotEqual([], stdout)
                if self.is_text_in_list(failover_grp_names[failover_grp_name],
                                        stdout):
                    found = True
                time.sleep(5)
                counter += 1

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

    # THIS FUNCTION MAY NEED EXTRA INFO
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
                node_name = line.split(' ')[18]
                cmd = self.vcs.get_hares_cs_clear_cmd(ipaddress, node_name)
                stdout, stderr, rc = \
                self.run_command(self.primary_node, cmd, su_root=True)
                self.assertEqual(0, rc)
                self.assertEqual([], stderr)
                self.assertEqual([], stdout)

    @attr('all', 'non-revert', 'kgb-other')
    def test_01_n_vcs_para_app_restart_and_act_stndby_app_failover(self):
        """
        @tms_id: litpcds_3997_tc01
        @tms_requirements_id: LITPCDS-3997
        @tms_title: vcs para app restart and act stndby app failover
        @tms_description:
            This test will kill the applications in a series of previously
            deployed clustered services and ensure that the applications
            operating on parallel clustered services restart, and that the
            applications operating on active standby clustered services
            fail over to their standby nodes.
            This test covers tests 01 - 09 in the test design document.
        @tms_test_steps:
        @step: Kill the applications
        @result: all applications killed
        @result: the active standby C-S's are active on their
        standby nodes
        @result:deployed clustered services are operating as expected
        @step: Repair all faulted clustered services
        @result: clustered services repaired
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        # Generate configuration for the plans
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

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

        # VERIFY WHICH NODES ARE ACTIVE
        cs_active_node_dict = \
            self.compile_cs_active_node_dict(conf)
        cs_death_conf = {
            "CS5": [],
            "CS7": [],
            "CS8": [],
            "CS10": [],
            "CS11": [],
            "CS12": []
        }

        # KILL THE APPLICATIONS BASED ON THE CS DEATH CONF
        hostname_mapping, _ = \
            self.kill_provided_clustered_services_children(
                cs_death_conf, cs_active_node_dict, conf)

        cs_death_conf = {
            "CS1": [],
            "CS2": [],
            "CS4": []
        }

        # KILL THE APPLICATIONS BASED ON THE CS DEATH CONF
        hostname_mapping, _ = \
            self.kill_provided_clustered_services_children(
                cs_death_conf, cs_active_node_dict, conf)
        #######################################################################
        # WAIT FOR ALL OF THE APPLICATIONS TO SHOW UP IN THE HASTATUS LIST
        # WHICH ONLY OCCURS WHEN THEY FAULT
        ######################################################################
        self.wait_for_resources_to_fault(cs_death_conf, conf)

        ######################################################################
        # WAIT A FEW MOMENTS FOR VCS TO ATTEMPT TO START ONLINING THE FAILOVER
        # RESOURCES AND THEN CYCLE THROUGH THE HASTATUS UNTIL THE RESOURCES
        # ONLINING HEADING DISAPPEARS INDICATING NO FURTHER ONLINING SHALL
        # BE TAKING PLACE THUS ALLOWING A CHECK OF THE SERVICE STATUS
        ######################################################################
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

        #######################################################################
        #     REPAIR THE FAULTED SERVICES. PRIOR TO KILLING IP'S RESOURCES    #
        #######################################################################
        self.repair_vcs_group_or_resources(cs_death_conf, conf,
                                           hostname_mapping)

        #######################################################################
        # DO NOT END THE TEST UNTIL THE SERVICE GROUPS FINISH ONLINING
        # OTHERWISE THE INITIAL VERIFICATION STEP IN THE SUBSEQUENT TEST SHALL
        # FAIL
        #######################################################################
        hagrp_cmd = self.vcs.get_hagrp_state_cmd()
        counter = 0
        starting = True
        while starting == True and counter < 10:
            hagrp_output, stderr, return_code = \
            self.run_command(self.primary_node, hagrp_cmd, su_root=True)
            self.assertNotEqual([], hagrp_output)
            self.assertEqual(0, return_code)
            self.assertEqual([], stderr)
            if not self.is_text_in_list("STARTING", hagrp_output):
                starting = False
            counter += 1
            time.sleep(5)
        self.assertEqual(False, starting)

    @attr('all', 'non-revert', 'kgb-other')
    def test_02_n_vcs_act_stanby_single_ip_failover(self):
        """
        @tms_id: litpcds_3997_tc02
        @tms_requirements_id: LITPCDS-3997
        @tms_title: vcs act stanby single ip failover
        @tms_description:
            This test will kill a single ip resource in a series of previously
            deployed clustered services and ensure that the applications
            operating on active standby clustered services fail over to their
            standby nodes.
            This test covers tests 14 - 16 in the test design document.
        @tms_test_steps:
        @step: Kill the ip resources
        @result: ip resources killed
        @result: active standby cluster services to failover
        @step: Repair all faulted clustered services
        @result: clustered services repaired
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        # Generate configuration for the plans
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

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
        network_dev_map = self.get_node_network_devices(self.management_server,
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

        # VERIFY WHICH NODES ARE ACTIVE
        cs_active_node_dict = \
            self.compile_cs_active_node_dict(conf)

        cs_death_conf = {
            "CS1": ["172.16.100.10"],
            "CS2": ["172.16.100.20"]
        }

        # KILL THE IPS BASED ON THE CS DEATH CONF
        hostname_mapping, _ = \
            self.kill_provided_clustered_services_children(
                cs_death_conf, cs_active_node_dict, conf, item="ipaddress")

        #######################################################################
        # WAIT FOR ALL OF THE APPLICATIONS TO SHOW UP IN THE HASTATUS LIST
        # WHICH ONLY OCCURS WHEN THEY FAULT
        ######################################################################
        self.wait_for_resources_to_fault(cs_death_conf, conf)

        ######################################################################
        # WAIT A FEW MOMENTS FOR VCS TO ATTEMPT TO START ONLINING THE FAILOVER
        # RESOURCES AND THEN CYCLE THROUGH THE HASTATUS UNTIL THE RESOURCES
        # ONLINING HEADING DISAPPEARS INDICATING NO FURTHER ONLINING SHALL
        # BE TAKING PLACE THUS ALLOWING A CHECK OF THE SERVICE STATUS
        ######################################################################
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

        #######################################################################
        #     REPAIR THE FAULTED SERVICES. PRIOR TO KILLING IP'S RESOURCES    #
        #######################################################################
        self.repair_vcs_group_or_resources(cs_death_conf, conf,
                                           hostname_mapping,
                                           resource="ipaddress")

        # VERIFY WHICH NODES ARE ACTIVE
        cs_active_node_dict = \
            self.compile_cs_active_node_dict(conf)

        cs_death_conf = {
            "CS2": ["172.16.200.140"]
        }

        # KILL THE IPS BASED ON THE CS DEATH CONF
        hostname_mapping, _ = \
            self.kill_provided_clustered_services_children(
                cs_death_conf, cs_active_node_dict, conf, item="ipaddress")
        #######################################################################
        # WAIT FOR ALL OF THE APPLICATIONS TO SHOW UP IN THE HASTATUS LIST
        # WHICH ONLY OCCURS WHEN THEY FAULT
        ######################################################################
        self.wait_for_resources_to_fault(cs_death_conf, conf)

        ######################################################################
        # WAIT A FEW MOMENTS FOR VCS TO ATTEMPT TO START ONLINING THE FAILOVER
        # RESOURCES AND THEN CYCLE THROUGH THE HASTATUS UNTIL THE RESOURCES
        # ONLINING HEADING DISAPPEARS INDICATING NO FURTHER ONLINING SHALL
        # BE TAKING PLACE THUS ALLOWING A CHECK OF THE SERVICE STATUS
        ######################################################################
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

        #######################################################################
        #     REPAIR THE FAULTED SERVICES. PRIOR TO KILLING IP'S RESOURCES    #
        #######################################################################
        self.repair_vcs_group_or_resources(cs_death_conf, conf,
                                           hostname_mapping,
                                           resource="ipaddress")

        #######################################################################
        # DO NOT END THE TEST UNTIL THE SERVICE GROUPS FINISH ONLINING
        # OTHERWISE THE INITIAL VERIFICATION STEP IN THE SUBSEQUENT TEST SHALL
        # FAIL
        #######################################################################
        hagrp_cmd = self.vcs.get_hagrp_state_cmd()
        counter = 0
        starting = True
        while starting == True and counter < 10:
            hagrp_output, stderr, return_code = \
            self.run_command(self.primary_node, hagrp_cmd, su_root=True)
            self.assertNotEqual([], hagrp_output)
            self.assertEqual(0, return_code)
            self.assertEqual([], stderr)
            if not self.is_text_in_list("STARTING", hagrp_output):
                starting = False
            counter += 1
            time.sleep(5)
        self.assertEqual(False, starting)

    @attr('all', 'non-revert', 'kgb-other')
    def test_03_n_vcs_parallel_single_ip_fault(self):
        """
        @tms_id: litpcds_3997_tc03
        @tms_requirements_id: LITPCDS-3997
        @tms_title: vcs parallel single ip fault
        @tms_description:
            This test will kill a single ip resource in a series of previously
            deployed clustered services and ensure that the applications
            operating on parallel clustered services are marked as faulted in
            the vcs console.
            This test covers tests 17 - 23 in the test design document.
        @tms_test_steps:
        @step: Kill the ip resources
        @result: ip resources killed
        @result: C-S resources affected have been listed as faulted
        @step: Repair all faulted clustered services
        @result: clustered services repaired
        @result: Online all clustered services that were offlined as a result
        of the test
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        # Generate configuration for the plans
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

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

        # VERIFY WHICH NODES ARE ACTIVE
        cs_active_node_dict = \
            self.compile_cs_active_node_dict(conf)

        cs_death_conf = {
            "CS6": ["172.16.100.60"],
            "CS7": ["172.16.200.171"],
            "CS8": ["172.16.200.181"],
            "CS9": ["172.16.200.190"],
            "CS12": ["172.16.100.120"]
        }
        # KILL THE IPS BASED ON THE CS DEATH CONF
        hostname_mapping, ipkilling_dict = \
            self.kill_provided_clustered_services_children(
                cs_death_conf, cs_active_node_dict, conf, item="ipaddress")
        #######################################################################
        # WAIT FOR ALL OF THE APPLICATIONS TO SHOW UP IN THE HASTATUS LIST
        # WHICH ONLY OCCURS WHEN THEY FAULT
        ######################################################################
        self.wait_for_resources_to_fault(cs_death_conf, conf)

        # VERIFY THE SERVICES ARE ACTIVE BUT NOT ON THEIR
        # ORIGINALLY ACTIVE NODES
        host_dict = self.map_node_host_to_node_file()
        for host in host_dict.keys():
            if host not in hostname_mapping.keys():
                hostname_mapping[host] = []

        self.verify_ip_faulted(ipkilling_dict)

        #######################################################################
        #     REPAIR THE FAULTED SERVICES. PRIOR TO KILLING IP'S RESOURCES    #
        #######################################################################
        self.repair_vcs_group_or_resources(cs_death_conf, conf,
                                           hostname_mapping,
                                           resource="ipaddress")

        #######################################################################
        #     ONLINE THE OFFLINED GROUPS. #
        #######################################################################
        self.online_offlined_service_groups(cs_death_conf)

        self.check_all_vcs_groups_returned_to_online_status(conf,
                                                            self.primary_node,
                                                            self.cluster_id)

        # VERIFY WHICH NODES ARE ACTIVE
        cs_active_node_dict = \
            self.compile_cs_active_node_dict(conf)

        cs_death_conf = {
            "CS12": ["172.16.200.220"]
        }
        # KILL THE IPS BASED ON THE CS DEATH CONF
        hostname_mapping, ipkilling_dict = \
            self.kill_provided_clustered_services_children(
                cs_death_conf, cs_active_node_dict, conf, item="ipaddress")
        #######################################################################
        # WAIT FOR ALL OF THE APPLICATIONS TO SHOW UP IN THE HASTATUS LIST
        # WHICH ONLY OCCURS WHEN THEY FAULT
        ######################################################################
        self.wait_for_resources_to_fault(cs_death_conf, conf)

        # VERIFY THE SERVICES ARE ACTIVE BUT NOT ON THEIR
        # ORIGINALLY ACTIVE NODES
        host_dict = self.map_node_host_to_node_file()
        for host in host_dict.keys():
            if host not in hostname_mapping.keys():
                hostname_mapping[host] = []

        self.verify_ip_faulted(ipkilling_dict)

        #######################################################################
        #     REPAIR THE FAULTED SERVICES. PRIOR TO KILLING IP'S RESOURCES    #
        #######################################################################
        self.repair_vcs_group_or_resources(cs_death_conf, conf,
                                           hostname_mapping,
                                           resource="ipaddress")

        #######################################################################
        #     ONLINE THE OFFLINED GROUPS. #
        #######################################################################
        self.online_offlined_service_groups(cs_death_conf)

        #######################################################################
        # DO NOT END THE TEST UNTIL THE SERVICE GROUPS FINISH ONLINING
        # OTHERWISE THE INITIAL VERIFICATION STEP IN THE SUBSEQUENT TEST SHALL
        # FAIL
        #######################################################################
        hagrp_cmd = self.vcs.get_hagrp_state_cmd()
        counter = 0
        starting = True
        while starting == True and counter < 10:
            hagrp_output, stderr, return_code = \
            self.run_command(self.primary_node, hagrp_cmd, su_root=True)
            self.assertNotEqual([], hagrp_output)
            self.assertEqual(0, return_code)
            self.assertEqual([], stderr)
            if not self.is_text_in_list("STARTING", hagrp_output):
                starting = False
            counter += 1
            time.sleep(5)
        self.assertEqual(False, starting)

    @attr('all', 'non-revert', 'kgb-other')
    def test_04_n_vcs_parallel_multiple_ip_fault(self):
        """
        @tms_id: litpcds_3997_tc04
        @tms_requirements_id: LITPCDS-3997
        @tms_title: vcs parallel multiple ip fault
        @tms_description:
            This test will kill multiple ip resources in a series of previously
            deployed clustered services and ensure that the applications
            operating on parallel clustered services are marked as faulted in
            the vcs console.
            This test covers tests 29 - 31 in the test design document.
        @tms_test_steps:
        @step: Kill the ip resources
        @result: ip resources killed
        @result: C-S resources affected have been listed as faulted
        @step: Repair all faulted clustered services
        @result: clustered services repaired
        @result: Online all clustered services that were offlined as a result
        of the test
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        # Generate configuration for the plans
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

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

        # VERIFY WHICH NODES ARE ACTIVE
        cs_active_node_dict = \
            self.compile_cs_active_node_dict(conf)

        cs_death_conf = {
            "CS7": ["172.16.200.171", "172.16.200.172"],
            "CS8": ["172.16.200.182", "172.16.100.80"],
            "CS10": ["172.16.200.200", "172.16.200.201"]
        }
        # KILL THE IPS BASED ON THE CS DEATH CONF
        hostname_mapping, ipkilling_dict = \
            self.kill_provided_clustered_services_children(
                cs_death_conf, cs_active_node_dict, conf, item="ipaddress")
        #######################################################################
        # WAIT FOR ALL OF THE APPLICATIONS TO SHOW UP IN THE HASTATUS LIST
        # WHICH ONLY OCCURS WHEN THEY FAULT
        ######################################################################
        self.wait_for_resources_to_fault(cs_death_conf, conf)

        # VERIFY THE SERVICES ARE ACTIVE BUT NOT ON THEIR
        # ORIGINALLY ACTIVE NODES
        host_dict = self.map_node_host_to_node_file()
        for host in host_dict.keys():
            if host not in hostname_mapping.keys():
                hostname_mapping[host] = []
        self.verify_ip_faulted(ipkilling_dict)

        #######################################################################
        #     REPAIR THE FAULTED SERVICES. PRIOR TO KILLING IP'S RESOURCES    #
        #######################################################################
        self.repair_vcs_group_or_resources(cs_death_conf, conf,
                                           hostname_mapping,
                                           resource="ipaddress")

        #######################################################################
        #     ONLINE THE OFFLINED GROUPS. #
        #######################################################################
        self.online_offlined_service_groups(cs_death_conf)

        #######################################################################
        # DO NOT END THE TEST UNTIL THE SERVICE GROUPS FINISH ONLINING
        # OTHERWISE THE INITIAL VERIFICATION STEP IN THE SUBSEQUENT TEST SHALL
        # FAIL
        #######################################################################
        hagrp_cmd = self.vcs.get_hagrp_state_cmd()
        counter = 0
        starting = True
        while starting == True and counter < 10:
            hagrp_output, stderr, return_code = \
            self.run_command(self.primary_node, hagrp_cmd, su_root=True)
            self.assertNotEqual([], hagrp_output)
            self.assertEqual(0, return_code)
            self.assertEqual([], stderr)
            if not self.is_text_in_list("STARTING", hagrp_output):
                starting = False
            counter += 1
            time.sleep(5)
        self.assertEqual(False, starting)

    @attr('all', 'non-revert', 'kgb-other')
    def test_05_n_vcs_act_stanby_multiple_ip_failover(self):
        """
        @tms_id: litpcds_3997_tc05
        @tms_requirements_id: LITPCDS-3997
        @tms_title: vcs act stanby multiple ip failover
        @tms_description:
            This test will kill a multiple ip resources in a series of
            previously deployed clustered services and ensure that the
            applications operating on active standby clustered services
            failover to their standby nodes.
            This test covers tests 27 - 28 in the test design document.
        @tms_test_steps:
        @step: Kill the ip resources
        @result: ip resources killed
        @result: the applications have failover over to their
        standby nodes
        @step: Repair all faulted clustered services
        @result: clustered services repaired
        @tms_test_precondition:NA
        @tms_execution_type: Automated
        """
        # Generate configuration for the plans
        conf = self.vcs.generate_plan_conf(self.traffic_networks)

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

        # VERIFY WHICH NODES ARE ACTIVE
        cs_active_node_dict = \
            self.compile_cs_active_node_dict(conf)

        cs_death_conf = {
            "CS2": ["172.16.200.140", "172.16.200.141"],
            "CS3": ["172.16.200.150", "172.16.100.30"]
        }

        # KILL THE IPS BASED ON THE CS DEATH CONF
        hostname_mapping, _ = \
            self.kill_provided_clustered_services_children(
                cs_death_conf, cs_active_node_dict, conf, item="ipaddress")
        #######################################################################
        # WAIT FOR ALL OF THE APPLICATIONS TO SHOW UP IN THE HASTATUS LIST
        # WHICH ONLY OCCURS WHEN THEY FAULT
        ######################################################################
        self.wait_for_resources_to_fault(cs_death_conf, conf)

        ######################################################################
        # WAIT A FEW MOMENTS FOR VCS TO ATTEMPT TO START ONLINING THE FAILOVER
        # RESOURCES AND THEN CYCLE THROUGH THE HASTATUS UNTIL THE RESOURCES
        # ONLINING HEADING DISAPPEARS INDICATING NO FURTHER ONLINING SHALL
        # BE TAKING PLACE THUS ALLOWING A CHECK OF THE SERVICE STATUS
        ######################################################################
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

        #######################################################################
        #     REPAIR THE FAULTED SERVICES. PRIOR TO KILLING IP'S RESOURCES    #
        #######################################################################
        self.repair_vcs_group_or_resources(cs_death_conf, conf,
                                           hostname_mapping,
                                           resource="ipaddress")

        #######################################################################
        # DO NOT END THE TEST UNTIL THE SERVICE GROUPS FINISH ONLINING
        # OTHERWISE THE INITIAL VERIFICATION STEP IN THE SUBSEQUENT TEST SHALL
        # FAIL
        #######################################################################
        hagrp_cmd = self.vcs.get_hagrp_state_cmd()
        counter = 0
        starting = True
        while starting == True and counter < 10:
            hagrp_output, stderr, return_code = \
            self.run_command(self.primary_node, hagrp_cmd, su_root=True)
            self.assertNotEqual([], hagrp_output)
            self.assertEqual(0, return_code)
            self.assertEqual([], stderr)
            if not self.is_text_in_list("STARTING", hagrp_output):
                starting = False
            counter += 1
            time.sleep(5)
        self.assertEqual(False, starting)

OBSELETED TCS
==============

LITPCDS-2200: As a LITP architect, I want the VCS stack to
    be available on a cluster so I may use features
    that VCS provides
-----------------------------------------------------------
Test cases:
-----------

test_03_n_type_error
    Reason: OBSELETED, moved to AT:
    Location: ERIClitpvcs/ats/testset_story2200/

    git: a9fe6a3109976d19c6ee7373845fc8bc3d75992f
    gerrit: https://gerrit.ericsson.se/#/c/1229179/

    test_04_05_p_create_vcs_sfha_cluster.at Test cases combined
    test_04_p_create_vcs_cluster
    test_05_p_create_sfha_cluster

    Reason: OBSELETED, moved to AT:
    Location: ERIClitpvcsapi/ats/testset_story2200/

    git: 2df64f5d357fd8c6bc703db093c01d24eaff9ade
    gerrit: https://gerrit.ericsson.se/#/c/1230183/


LITPCDS-4377: As a LITP Developer I want to re-work how the
    VCS plug-in defines Virtual IPs so that the plug-in is
    aligned with the networking model
------------------------------------------------------------
Test cases:
-----------

test_01_deploy_cdb_cs
    Reason: OBSELETED, covered by testset_vcs_setup.py test cases
    Location: ERIClitpvcs-testware/python-testcases/src/main/resources/vcs/

    git: 211f193c01c3d88a7f33da8bb7abdb9242f653a3
    gerrit: https://gerrit.ericsson.se/#/c/922646/


LITPCDS-4422: As a LITP user i want to be able to expand my VCS cluster so
    that I can meet growing capacity requirements
-------------------------------------------------------------------------------
Test Cases:
-----------

    Reason: OBSELETED Test cases that do not perform expansion tests(part of
    old CI expansion test cases)
    Location: NONE

    git: 50c66975fe88755b5cb4c31dbb9adc8185b53b4e
    gerrit: https://gerrit.ericsson.se/#/c/1286921/

    test_01_p_vcs_conf_files_exist
    test_02_p_llt_file
    test_03_p_gab_file
    test_04_p_llthosts_file
    test_05_p_gabtab_file
    test_06_p_validate_main_cf
    test_07_p_all_services_running
    test_08_p_create_cs_after_expansion


LITPCDS-5167: As a LITP User I want to expand my parallel VCS Service Group
    so that an application can run on more nodes if required
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_04_p_expand_cs_two_to_three_nodes

    Reason: Functionality and validation is covered in
    "test_20_21_22_p_deps_on_expanded_services" expansion test case of
    testset_story5938 test script.

    git: a0242533d45c4f378813dfd8ccc953a0eaa53b86
    gerrit: https://gerrit.ericsson.se/#/c/1343178/


LITPCDS-8558: As a LITP user I want more than a single "service" item in a
    "vcs-clustered-service" so that the creation of more than a single
    application resource type in a VCS group is possible
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_01_deploy_cdb_multi_cs:

    Reason: Test is obsolete because is replaced from testutils function
    self.apply_cs_and_apps_sg. We don't need the setup(test baseline) to
    be separated test anymore. Also this specific TC is covered in VCS KGB by
    testset_story9490.

    test_02_p_vcs_cs_multi_srvc_3:
    Reason: Test is obsoleted because is duplicate with
    test_04_p_vcs_cs_dep_list_1_cs_failover in the same script.

    test_03_p_vcs_cs_multi_srvc_10:
    Reason: Test is obsoleted because is replaced in form of AT found in:
    ERIClitpvcs/ats/testset_story8558/test_03_p_vcs_cs_multi_srvc_10.at

    git: I2015d63efe8119734825c743488e38e31cab4852
    gerrit: https://gerrit.ericsson.se/#/c/1570023/2


LITPCDS-6164: As a LITP Developer I want to use the service item along with VIP
    items with the VCS plug in so that there is a consistent modelling approach
    to managing LSB services
-------------------------------------------------------------------------------
Test Cases:
-----------

    test_03_p_cs32_verify:
    Reason:
    This test verified the successful deployment of clustered-service(CS32), by
    ensuring the relevant packages were installed on the correct nodes. But
    never fully implemented the coverage in its description. This test case
    will now be fully covered by test_02_verify_sg_vcs_clustered_service in
    testset_vcs script

    git: I2015d63efe8119734825c743488e38e31cab4852
    gerrit: https://gerrit.ericsson.se/#/c/1570023/2


LITPCDS-3828
    As a HA application designer I want to create a basic VCS service group
    so that my application can be managed
-------------------------------------------------------------------------------
Test Cases:
    test_01_p_jee_container

    Reason:This story is automatically verified by any test case which deploys
    a failover service. testset_vcs_deploy.py test_deploy_service_groups_tc01
    also covers the requirement to deploy via XML.

-------------------------------------------------------------------------------
LITPCDS-2210
    As an application designer, I want split-brain protection to be configured
    in the VCS stack so that I can prevent resource collision..
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_01_p_split_brain

    Reason:
    Test case is now fully covered in test_01_p_verify_vcs in testset_vcs.py

    git: Icb76a9a188d55adc0b6ed4acd79bb42c6fa929ef
    gerrit: https://gerrit.ericsson.se/#/c/21575736

-------------------------------------------------------------------------------
LITPCDS-3764
    As a LITP troubleshooter, I want the VCS tools to be available
    on my path,so that I can use these to resolve problems
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_01_check_hastatus

    Reason:
    Test case is now fully covered in test_01_p_verify_vcs in testset_vcs.py

    git: Icb76a9a188d55adc0b6ed4acd79bb42c6fa929ef
    gerrit: https://gerrit.ericsson.se/#/c/21575736

-------------------------------------------------------------------------------
LITPCDS-3766
    As a LITP Plugin Developer, I want the Cluster Id to be an optional property
    so that I can handle all install cases
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_01_p_reading_llttab_file

    Reason:
    Test case is now fully covered in test_01_p_verify_vcs in testset_vcs.py

    git: Icb76a9a188d55adc0b6ed4acd79bb42c6fa929ef
    gerrit: https://gerrit.ericsson.se/#/c/21575736

-------------------------------------------------------------------------------
LITPCDS-3807
    As an application designer I need a NIC service group created so other
    VCS service group can monitor that NIC using a proxy
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_01_p_nic_service_group

    Reason:
    Test case is now fully covered in test_01_p_verify_vcs in testset_vcs.py

    git: Icb76a9a188d55adc0b6ed4acd79bb42c6fa929ef
    gerrit: https://gerrit.ericsson.se/#/c/21575736

-------------------------------------------------------------------------------
LITPCDS-4475
    As a LITP installer, I want to install and configure VxVM tools
    on a node so that I can utilise movable storage on that node
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_01_p_check_vxvm_cmds

    Reason:
    Test case is now fully covered in test_01_p_verify_vcs in testset_vcs.py

    git: Icb76a9a188d55adc0b6ed4acd79bb42c6fa929ef
    gerrit: https://gerrit.ericsson.se/#/c/21575736

-------------------------------------------------------------------------------
LITPCDS-3809
    As a HA application designer I want to manage Mounting movable VxVM block
    devices so that my application will failover when a fault is detected
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_01_p_create_cs_with_mount

    Reason:
    Test case was obsoleted a long time ago.
    The test case requires access to physical hardware. In any case, this
    scenario is fully tested in the deployment plans in PCDB_2node and
    PCDB_2node_autoinstall Jenkins Jobs.
    If we ever plan to execute this test case again in automated way, we would
    rewrite the test case in a much easier way.

    git: I2fb7b22bf54ea6e9d6e30280511f79f7eb149a10
    gerrit: https://gerrit.ericsson.se/#/c/1626083/

-------------------------------------------------------------------------------
LITPCDS-11241
    As a LITP User I want to add VCS Service Group Dependencies so that I can
    order startup sequences of my applications
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_01_p_update_applied_cs_dependency_list
    test_02_p_update_updated_cs_dependency_list

    Reasons:
    Test case 1 coverage is now seen in testset_vcs.py as part of
    testset_vcs_update_1.
    Test case 2 is now an AT

    git: I2fb7b22bf54ea6e9d6e30280511f79f7eb149a10
    gerrit: https://gerrit.ericsson.se/#/c/1626083/

-------------------------------------------------------------------------------
LITPCDS-5167
    As a LITP User I want to expand my parallel VCS Service Group so that an
    application can run on more nodes if required
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_01_p_add_one_node_deps_idemp
    test_02_p_add_one_node_vips
    test_03_p_add_one_node_prio

    Reasons:
    Test case 1, 2 and 3 coverage is now seen in testset_vcs.py as part of
    testset_vcs_update_1. Multiple instances of dependencies test cases seen in
    5167 TCs are seen elsewhere.

    git: I2fb7b22bf54ea6e9d6e30280511f79f7eb149a10
    gerrit: https://gerrit.ericsson.se/#/c/1626083/

-------------------------------------------------------------------------------
LITPCDS-13411
    As a litp user i want my VCS service group to clear any faults so it
    can attempt to online itself indefinitely
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_06_p_ensure_trig_brings_sg_online_and_remove_trig
    test_07_p_default_behaviour_and_idpempotency
    test_09_p_rmve_trig_create_trig_in_same_plan

    Reasons:
    Test case 6 and 7 coverage is now seen in testset_vcs.py as part of
    testset_vcs_update_1.
    Test case 9 is now an AT

    git: I2fb7b22bf54ea6e9d6e30280511f79f7eb149a10
    gerrit: https://gerrit.ericsson.se/#/c/1626083/

-------------------------------------------------------------------------------
LITPCDS-5172
    As a LITP User I want to modify LITP allowed tunable attributes of a VCS
    Application Resource so that I can manage my applications running behaviour
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_01_p_cs_deploy_update_create_props
    test_02_p_cs_remove_cleanup_command_service

    Reasons:
    Test case 1 coverage is now seen in testset_vcs.py as part of
    testset_vcs_update_1.
    Test case 2 is now an AT

    git: I2fb7b22bf54ea6e9d6e30280511f79f7eb149a10
    gerrit: https://gerrit.ericsson.se/#/c/1626083/

-------------------------------------------------------------------------------
LITPCDS-5168
    As a LITP user i want to contract my parallel VCS Service Group so that an
    application can run on less nodes if required
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_01_p_rmve_node_frm_node_lst
    test_02_p_verify_cs_contraction_apps_can_be_reused

    Reasons:
    Test case 1 coverage is now seen in testset_vcs.py as part of
    testset_vcs_update_1.
    Test case 2 is now an AT

    git: I2fb7b22bf54ea6e9d6e30280511f79f7eb149a10
    gerrit: https://gerrit.ericsson.se/#/c/1626083/
-------------------------------------------------------------------------------
LITPCDS-8968
    Test the use story to reconfigure Failover VCS Service Group
    to be a Parallel Service Group
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_01_p_update_vcs_service_group_failover_to_parallel

    Reasons:
    Test case 1 coverage is now seen in testset_vcs.py as part of
    testset_vcs_update_1.

    git: I2fb7b22bf54ea6e9d6e30280511f79f7eb149a10
    gerrit: https://gerrit.ericsson.se/#/c/1626083/
-------------------------------------------------------------------------------
LITPCDS-11453
    As a LITP User I want to remove/modify VCS Service Group Dependencies so
    that I can re-order startup sequences of my applications
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_01_p_add_and_remove_vcs_cs_id

    Reasons:
    Test case 1 coverage is now seen in testset_vcs.py as part of
    testset_vcs_update_1.

    git: I2fb7b22bf54ea6e9d6e30280511f79f7eb149a10
    gerrit: https://gerrit.ericsson.se/#/c/1626083/
-------------------------------------------------------------------------------
LITPCDS-5653
    As an application designer I want to specify priority order so that I can
    balance my applications across the nodes in the VCS cluster
-------------------------------------------------------------------------------
Test Cases:
-----------
    test_03_p_verify_failover
    test_04_p_verify_parallel

    Reason:
    Both test cases are already covered in testset_vcs.py test case 2, as part
    of optimization.

    git: I2fb7b22bf54ea6e9d6e30280511f79f7eb149a10
    gerrit: https://gerrit.ericsson.se/#/c/1626083/

-------------------------------------------------------------------------------

######################################################################
STORY 3993
######################################################################

TEST: test_01_p_node1_unlocking

TMS-ID: litpcds_3993_tc_01

DESCRIPTION: Verify that node lock/unlock tasks are generated for node1
             only. Since only 1 node is locked, failover
             clustered-services should be on the opposite node after
             the node unlocking has completed.

REASON OBSOLETED: Merged with test_03_p_both_nodes_unlocking.

GERRIT LINK: https://gerrit.ericsson.se/#/c/4335882/

-----------------------------------------------------------------------
TEST: test_02_p_node2_unlocking

TMS-ID: litpcds_3993_tc_02

DESCRIPTION: Verify that node lock/unlock tasks are generated for node2
             only. Since only 2 node is locked, failover
             clustered-services should be on the opposite node after
             the node unlocking has completed.

REASON OBSOLETED: Covered in test_03_p_both_nodes_unlocking.

GERRIT LINK: https://gerrit.ericsson.se/#/c/4335882/

-----------------------------------------------------------------------

######################################################################
STORY 10741
######################################################################

TEST: test_01_p_remove_ipv4_vcs_network_hosts

TMS-ID: litpcds_10741_tc1

DESCRIPTION:
    This positive test is checking that LITP can successfully remove
    IPv4 vcs-network-hosts items related with mgmt, traffic and dhcp
    network interfaces.

REASON OBSOLETED:
    This test was merged with
    test_03_p_remove_network_and_vcs_network_hosts.

GERRIT LINK: https://gerrit.ericsson.se/#/c/4368555/

-----------------------------------------------------------------------
TEST: test_02_p_remove_ipv6_vcs_network_hosts

TMS-ID: litpcds_10741_tc2

DESCRIPTION:
    This positive test is checking that LITP can successfully remove
    IPv6 vcs-network-hosts items related with traffic network.

REASON OBSOLETED:
    This test was merged with
    test_03_p_remove_network_and_vcs_network_hosts.

GERRIT LINK: https://gerrit.ericsson.se/#/c/4368555/

-----------------------------------------------------------------------

######################################################################
STORY 12815
######################################################################

TEST: test_01_p_update_one_mac_address

DESCRIPTION:
    Update a MAC address on one of the nodes. Ensure that the new MAC
    address is in the /etc/llttab file. It should be the only entry
    in llttab that has changed.

REASON OBSOLETED: Testing of mac update in test_02 is sufficient coverage as it
                  tests that multiple mac addresses can be changed.
                  test_01 had a LITP restart but wasn't a true idempotency test
                  as it didn't make an update after the restart and it didn't
                  test the contents of the re-created plan.

GERRIT LINK: https://gerrit.ericsson.se/#/c/4341588/

TMS-ID: litpcds_12815_tc1

-----------------------------------------------------------------------

######################################################################
STORY 13258
######################################################################

TEST: test_01_p_chck_mii_att_updated

TMS-ID: litpcds_13258_tc1

DESCRIPTION: Test to validate if the Mii attribute is affected when
             updating the default_nic_monitor property from netstat
             to mii. Verify the mii attribute is set correctly for
             service group resources with/ without network hosts.

REASON OBSOLETED: Merged with test_02_p_chck_netstat_set
                  which is now renamed as test_02_p_update_default_nic_monitor.

GERRIT LINK: https://gerrit.ericsson.se/#/c/4341911/

-------------------------------------------------------------------------------

######################################################################
STORY 5507
######################################################################

TEST: test_01_p_verify_config

TMS-ID: litpcds_5507_tc1

DESCRIPTION:
    Verify VCS NetworkHost parameters. Test case to ensure the VCS NetworkHost
    parameters have been populated according to the model.

REASON OBSOLETED:
    This test is covered in
    testset_story10741.py:test_03_p_remove_network_and_vcs_network_hosts.

GERRIT LINK: https://gerrit.ericsson.se/#/c/4445946/

-------------------------------------------------------------------------------

######################################################################
STORY 11240
######################################################################

TEST: test_06_p_sg_online_update_ignore_cs_initial

TMS-ID: litpcds_11240_tc06

DESCRIPTION: The original TMS description for this test was incorrect and
             doesn't reflect the code. The test actually checks that no plan is
             created when the cs_inital_online property is updated.

REASON OBSOLETED: Obsoleted as it is covered in AT found testset_story11240/
                  test_02_n_no_model_update_cs_initial_no_generate_plan.at

GERRIT LINK: https://gerrit.ericsson.se/#/c/4478875/

-----------------------------------------------------------------------
TEST: test_07_p_stop_plan_pre_online_task_update_cs_initial_off

TMS-ID: litpcds_11240_tc07

DESCRIPTION: Test to validate when the cs_initial_online property
             is set to on and a new vcs-clustered-service is added, if the litp
             plan is stopped before the online task phase is executed and the
             cs_initial_online property is updated to off, then the subsequent
             plan will not include service group online task.

REASON OBSOLETED: Obsoleted as it is deemed to be an edge case and has
                  become invalid due to the use of resume plan.

GERRIT LINK: https://gerrit.ericsson.se/#/c/4478875/

-----------------------------------------------------------------------

######################################################################
STORY 2200
######################################################################

TEST: test_01_p_vcs_in_yum_repo

DESCRIPTION: Verify that all VCS packages exist in the yum repository on the
             MS.

REASON OBSOLETED: A basic test from initial LITP development which simply
                  tests if packages are present in a yum repository. No longer
                  needed.

GERRIT LINK: https://gerrit.ericsson.se/#/c/4532658/


TMS-ID: litpcds_2200_tc01
-----------------------------------------------------------------------

TEST: test_02_p_rpms_installed

DESCRIPTION: Checks if VCS packages for specified type(sfha or vcs)
             are installed on all of the nodes in the cluster.

REASON OBSOLETED: A basic test from initial LITP development which simply
                  tests if packages are installed. No longer needed.

GERRIT LINK: https://gerrit.ericsson.se/#/c/4532658/


TMS-ID: litpcds_2200_tc02
-----------------------------------------------------------------------

TEST: test_06_p_test_missing_rpm

DESCRIPTION: Un-installs a VCS package from a managed node using yum and
             verifies that puppet then re-installs it.


REASON OBSOLETED: A basic test from initial LITP development which simply
                  tests if puppet replaces a package which is deliberately
                  uninstalled. No longer needed.

GERRIT LINK: https://gerrit.ericsson.se/#/c/4532658/


TMS-ID: litpcds_2200_tc06
-----------------------------------------------------------------------

######################################################################
STORY 5938
######################################################################

TEST: test_02_p_verify_dependency_order_after_node_locking

TMS-ID: litpcds_5938_tc02

DESCRIPTION: This test assume the setup test has run successfully. It assumes
             that the node locking tests have also run. Test case will verify
             that all the dependencies were set correctly in VCS.
             The VCS dependencies should be configured as: 'online local soft'
             or 'online global soft'

REASON OBSOLETED: This is a basic test that simply checks that the dependency
                  param is either 'online local soft' or 'online global soft'.
                  The order of the tests is defined so that this test runs
                  after a test with a node lock. Keeping this test with a
                  dependency on an earlier test, increases the complexity of
                  the VCS KGB and is not justified.

GERRIT LINK:

-------------------------------------------------------------------------------

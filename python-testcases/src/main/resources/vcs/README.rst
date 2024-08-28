These modules rely on the 3rd party libraries: jsonschema and jinja2. Linux package rpm-build is required for "test rpm" auto generation (only for testing outside of vApp). Make sure you have them on your system.

*generate.py* accepts one mandatory parameter and a number of other parameters defined in the generator help. The help can be accessed by using the --help command line parameter.

The --s parameter accepts the story number as an integer and it is used to generate various names for the model items as well as the RPM packages.

The other parameters are --a, --hsc and --vcs which accept an integer that specifies how many model items are generated for the service, ha-service-config and vcs-clustered-service items respectively.

The last parameters are --ao, --hsco and --vcso which accept a string (best written with single quotes) that contains a number of key value items separated by a single space. The items are written in a key="value" format. They represent options for the service, ha-service-config and vcs-clustered-service respectively. For example: --hsc 'offline_timeout="120" online_timeout="120"'

There is also one additional boolean parameter --atc that marks services to be added to cleanup or, if the parameter is not present, marks the add_to_cleanup flag as false.

The generate.py module contains a few helper functions for the test cases.

*validate_fixtures* function that, if used, validates the input JSON dict with a JSON schema.

*load_fixtures* function loads and modifies a fixture either from a variable or from a file. It inspects the state of the deployment systems during runtime and appends node information where necessary.

*apply_options_changes* function accepts a generated fixture, a string with the item type, an index of the item that needs to be changed, and a dictionary of custom options that are going to update the generated one at runtime, the last parameter is a boolean which can change the behaviour of this function making it overwrite the options instead of updating them.

*apply_item_changes* function works similarly to the apply_options_changes function but the dictionary it accepts does not change the options, it changes the whole item structure.

If generate.py is used with the following command line parameters:

--s 9600 --a 1 --hsc 1 --vcs 1 --hsco 'fault_on_monitor_timeouts="280" tolerance_limit="300"' --vcso 'online_timeout="180"'

the resulting JSON file is named 9600data.json and, when unpacked, it looks as follows:

{
    "litp_default_values":
    {
        "vcs-clustered-service":
        {
            "online_timeout": "300",
            "offline_timeout": "300"
        },

        "service":
        {
            "cleanup_command": "/bin/true"
        },

        "ha-service-config":
        {
            "clean_timeout": "60",
            "fault_on_monitor_timeouts": "4",
            "tolerance_limit": "0"
        }
    },

    "service":
    [
        {
            "package_vpath": "/software/items/EXTR-lsbwrapper-9600-1",
            "parent": "CS_9600_1",
            "options_string": "service_name=\"test-lsb-9600-1\"",
            "destination": "/services/CS_9600_1/applications/APP_9600_1",
            "id": "APP_9600_1",
            "package_id": "EXTR-lsbwrapper-9600-1",
            "package_destination": "/software/services/APP_9600_1/packages/EXTR-lsbwrapper-9600-1",
            "add_to_cleanup": false,
            "options":
            {
                "service_name": "test-lsb-9600-1"
            },
            "vpath": "/software/services/APP_9600_1"
        }
    ],

    "ha-service-config":
    [
        {
            "parent": "CS_9600_1",
            "add_to_cleanup": false,
            "id": "HSC_9600_1",
            "options_string": "service_id=\"APP_9600_1\" fault_on_monitor_timeouts=\"280\" tolerance_limit=\"300\"",
            "options":
            {
                "service_id": "APP_9600_1",
                "fault_on_monitor_timeouts": "280",
                "tolerance_limit": "300"
            },

            "vpath": "/services/CS_9600_1/ha_configs/HSC_9600_1"
        }
    ],

    "vcs-clustered-service":
    [
        {
            "options_string": "active=\"1\" standby=\"0\" name=\"CS_9600_1\" online_timeout=\"180\"",
            "add_to_cleanup": false,
            "options":
            {
                "active": "1",
                "standby": "0",
                "name": "CS_9600_1",
                "online_timeout": "180"
            },

            "vpath": "/services/CS_9600_1",
            "id": "CS_9600_1"
        }
    ],

    "packages":
    [
        "EXTR-lsbwrapper-9600-1-1.0-1.noarch.rpm",
    ],

    "options":
    {
        "story": "9600",
        "hsc_length": 1,
        "vcs_length": 1,
        "app_length": 1
    }
}

The "options" key holds a dictionary that has the story number and length of the items generated.
The "packages" key holds an array of strings of RPMs generated.
The "litp_default_values" key holds a dictionary of item name keys ("vcs-clustered-service", "service", "ha-service-config") and values that are in a format of another dictionary holding a key value that is a representation of default values that the LITP generates for the items in case they are missing.
The dictionaries with keys "vcs-clustered-service", "service" and "ha-service-config" hold an array of another dictionaries that describe the items.

Every item has the following keys:
The "add_to_cleanup" key is a boolean that describes weather or not the item is to be added to cleanup.
The "options" key holds the dictionary of the options that are not serialized, but can be easily asserted against.
The "options_string" key holds a string of serialized options for the litp command.
The "vpath" key holds a suffix for the basic vpath of the item (the prefix is generated afterwards, per test case basis, with the load_fixtures function).
The "id" key holds the ID of the item.

The "vcs-clustered-service" items include only the the generic options.

The "service" items also contain a "package_vpath" key that describes where the package is created, the "package_id" key and the "package_destination" path to which the package is inherited. There is also a "parent" key which describes the "vcs-clustered-service" under which the service is located and a "destination" key which describes the vpath to which the service is inherited.

The "ha-service-config" items also have a "parent" key alongside generic options that behaves the same way as the "parent" key in the "service" item dictionary.

*rpm_generator.py* can be used with --s and --c parameters which are representing the story and the number of packages to be generated written as integers. It uses the jinja2 templates in the rpm-template directory and creates RPM packages in the rpm-out/dist directory. While it can be used separately, the rpm_generator is used as a part of the generate.py that generates the fixture and the RPM packages.

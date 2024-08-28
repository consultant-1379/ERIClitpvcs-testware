"""
COPYRIGHT Ericsson 2019
The copyright to the computer program(s) herein is the property of
Ericsson Inc. The programs may be used and/or copied only with written
permission from Ericsson Inc. or in accordance with the terms and
conditions stipulated in the agreement/contract under which the
program(s) have been supplied.

@since:     September 2015
@author:    Zlatko Masek, Boyan Mihovski
@summary:   Integration tests test data generator for testing VCS scenarios
            Agile: LITPCDS-10172
"""
FIXTURES_SCHEMA = {
    "name": "Model",
    "type": "object",
    "required": ["litp_default_values", "packages", "options",
                 "vcs-clustered-service", "service",
                 "ha-service-config"],
    "properties": {
        "litp_default_values": {
            "type": "object",
            "required": ["vcs-clustered-service", "service",
                         "ha-service-config", "vip"],
            "properties": {
                "vcs-clustered-service": {
                    "type": "object",
                    "required": ["online_timeout", "offline_timeout"],
                    "properties": {
                        "online_timeout": {"type": "string"},
                        "offline_timeout": {"type": "string"}
                    },
                    "additionalProperties": False
                },
                "service": {
                    "type": "object",
                    "required": ["cleanup_command"],
                    "properties": {
                        "cleanup_command": {"type": "string"}
                    },
                    "additionalProperties": True
                },
                "ha-service-config": {
                    "type": "object",
                    "required": ["clean_timeout", "fault_on_monitor_timeouts",
                                 "tolerance_limit"],
                    "properties": {
                        "clean_timeout": {"type": "string"},
                        "fault_on_monitor_timeouts": {"type": "string"},
                        "tolerance_limit": {"type": "string"}
                    },
                    "additionalProperties": False
                },
                "vip": {
                        "type": "object",
                        "ipaddress": "string",
                        "network_name": "string",
                        "additionalProperties": True
                }
            },
            "additionalProperties": False
        },
        "packages": {
            "type": "array",
            "items": {"type": "string"}
        },
        "options": {
            "type": "object",
            "required": ["story", "hsc_length", "vcs_length", "app_length"],
            "properties": {
                "story": {"type": "string"},
                "hsc_length": {"type": "number", "minimum": 0},
                "vcs_length": {"type": "number", "minimum": 0},
                "app_length": {"type": "number", "minimum": 0},
                "vip_length": {"type": "number", "minimum": 0}
            },
            "additionalProperties": False
        },
        "vcs-clustered-service": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["options_string", "add_to_cleanup", "vpath", "id",
                             "options"],
                "properties": {
                    "options_string": {"type": "string"},
                    "add_to_cleanup": {"type": "boolean"},
                    "vpath": {"type": "string"},
                    "id": {"type": "string"},
                    "options": {
                        "type": "object",
                        "required": ["name", "active", "standby"],
                        "properties": {
                            "active": {"type": "string"},
                            "standby": {"type": "string"},
                            "name": {"type": "string"}
                        },
                        "additionalProperties": {
                            "type": "string"
                        }
                    }

                },
                "additionalProperties": False
            }
        },
        "service": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["options", "id", "add_to_cleanup",
                             "options_string", "vpath", "destination",
                             "parent", "package_id", "package_vpath",
                             "package_destination"],
                "properties": {
                    "package_vpath": {"type": "string"},
                    "parent": {"type": "string"},
                    "options_string": {"type": "string"},
                    "destination": {"type": "string"},
                    "id": {"type": "string"},
                    "package_id": {"type": "string"},
                    "package_destination": {"type": "string"},
                    "vpath": {"type": "string"},
                    "add_to_cleanup": {"type": "boolean"},
                    "options": {
                        "type": "object",
                        "required": ["service_name"],
                        "properties": {
                            "service_name": {"type": "string"}
                        },
                        "additionalProperties": {
                            "type": "string"
                        }
                    }
                },
                "additionalProperties": False
            }
        },
        "ha-service-config": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["options", "options_string", "id", "vpath",
                             "add_to_cleanup", "parent"],
                "properties": {
                    "parent": {"type": "string"},
                    "add_to_cleanup": {"type": "boolean"},
                    "id": {"type": "string"},
                    "options_string": {"type": "string"},
                    "vpath": {"type": "string"},
                    "options": {
                        "type": "object"
                    },
                    "additionalProperties": {
                        "type": "string"
                    }
                },
                "additionalProperties": False
            }
        },
        "vip": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "add_to_cleanup": {"type": "boolean"},
                    "id": {"type": "string"},
                    "options_string": {"type": "string"},
                    "vpath": {"type": "string"},
                    "options": {
                        "type": "object"
                    },
                    "additionalProperties": {
                        "type": "string"
                    }
                },
                "additionalProperties": False
            }
        }
    },
    "additionalProperties": False
}

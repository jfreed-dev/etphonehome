import silo_common.snippets as em7_snippets

# Palo Alto: Prisma WAN Interface Stats
# Version: 1.3
#
# Purpose: Collects WAN interface metrics for ION devices.
# Data Source: Reads from API Collector cache (PRISMACLOUD+WANINTERFACES).
# Metrics: Interface counts, admin status, utilization, errors.
# Alerting: Interface failures handled by Event Processor (DEVICEHW_INTERFACE_DOWN).
#
# v1.3: Changed to lookup WAN interfaces by site_id instead of element_id
#       WAN interfaces are site-level circuit definitions shared by all elements at a site
#       Lookup path: element_id -> DEVICES cache -> site_id -> WANINTERFACES cache

SNIPPET_NAME = "Palo Alto: Prisma WAN Interface Stats | v 1.3.0"

# Cache keys - use root device ID for parent cache access
CACHE_KEY_WAN = "PRISMACLOUD+WANINTERFACES+%s" % (self.root_did)
CACHE_KEY_DEVS = "PRISMACLOUD+DEVICES+%s" % (self.root_did)

CACHE_PTR = em7_snippets.cache_api(self)

# Thresholds for metric classification (informational only - alerts via Event Processor)
UTILIZATION_WARNING_PCT = 80
UTILIZATION_CRITICAL_PCT = 95
ERROR_RATE_WARNING = 100  # errors per collection cycle
ERROR_RATE_CRITICAL = 1000

RESULTS = {
    "wan_interfaces": [(0, 0)],
    "interfaces_up": [(0, 0)],
    "interfaces_down": [(0, 0)],
    "high_utilization": [(0, 0)],
    "high_errors": [(0, 0)],
    "flapping": [(0, 0)],
}


def logger_debug(s=7, m=None, v=None):
    sevs = {
        0: "EMERGENCY",
        1: "ALERT",
        2: "CRITICAL",
        3: "ERROR",
        4: "WARNING",
        5: "NOTICE",
        6: "INFORMATION",
        7: "DEBUG",
    }
    if m is not None and v is not None:
        self.logger.ui_debug("[%s] %s %s" % (sevs[s], str(m), str(v)))
    elif m is not None:
        self.logger.ui_debug("[%s] %s" % (sevs[s], str(m)))


##main:
logger_debug(7, SNIPPET_NAME)

# Get this component's unique ID (element_id from Prisma)
element_id = str(self.comp_unique_id) if self.comp_unique_id else None

if not element_id:
    logger_debug(3, "No component unique ID - this DA requires component device context")
    result_handler.update(RESULTS)
else:
    logger_debug(7, "Processing WAN interfaces for element: %s" % (element_id))

    # Step 1: Look up element to get its site_id
    # WAN interfaces are site-level resources, not per-element
    device_cache_key = "%s+%s" % (CACHE_KEY_DEVS, element_id)
    element_data = CACHE_PTR.get(device_cache_key)

    site_id = None
    if isinstance(element_data, dict):
        site_id = str(element_data.get("site_id", ""))
        logger_debug(7, "Element %s belongs to site %s" % (element_id, site_id))
    else:
        logger_debug(4, "Could not find element %s in devices cache" % (element_id))

    # Step 2: Get WAN interfaces by site_id
    wan_interfaces = None
    if site_id:
        wan_cache_key = "%s+%s" % (CACHE_KEY_WAN, site_id)
        wan_interfaces = CACHE_PTR.get(wan_cache_key)
        logger_debug(7, "WAN cache key: %s" % (wan_cache_key))

    if not wan_interfaces:
        logger_debug(
            4, "No cached WAN interface data for site %s (element %s)" % (site_id, element_id)
        )
        result_handler.update(RESULTS)
    else:
        try:
            # Counters
            total_interfaces = 0
            interfaces_up = 0
            interfaces_admin_disabled = 0
            high_utilization_count = 0
            high_errors_count = 0
            flapping_count = 0

            for intf in wan_interfaces:
                total_interfaces += 1
                intf_name = intf.get("name", "Unknown")
                intf_type = intf.get("type", "unknown")
                link_bw_down = intf.get("link_bw_down", 0)  # Mbps
                link_bw_up = intf.get("link_bw_up", 0)
                admin_up = intf.get("admin_up", True)
                network_id = intf.get("network_id", "")  # Carrier/circuit label

                logger_debug(
                    7, "  Interface: %s (%s, admin_up=%s)" % (intf_name, intf_type, admin_up)
                )

                # Track administrative status (informational metric only)
                # NOTE: admin_up=False means intentionally disabled, NOT a failure
                # Operational failures generate DEVICEHW_INTERFACE_DOWN events
                # which are handled by Event Processor -> CARRIER_TICKET alerts
                if admin_up:
                    interfaces_up += 1
                else:
                    interfaces_admin_disabled += 1
                    logger_debug(6, "  Interface %s is administratively disabled" % (intf_name))

                # Check bandwidth configuration (0 may indicate unconfigured)
                if link_bw_down == 0 and link_bw_up == 0:
                    logger_debug(7, "    Bandwidth not configured for %s" % (intf_name))
                else:
                    logger_debug(
                        7, "    Bandwidth: %d Mbps down / %d Mbps up" % (link_bw_down, link_bw_up)
                    )

                # Future: If real-time utilization/error data becomes available in cache,
                # calculate high_utilization_count and high_errors_count here
                # Currently the WAN interfaces API provides config, not real-time stats

            # Update results
            RESULTS["wan_interfaces"] = [(0, total_interfaces)]
            RESULTS["interfaces_up"] = [(0, interfaces_up)]
            RESULTS["interfaces_down"] = [(0, interfaces_admin_disabled)]  # Admin-disabled count
            RESULTS["high_utilization"] = [(0, high_utilization_count)]
            RESULTS["high_errors"] = [(0, high_errors_count)]
            RESULTS["flapping"] = [(0, flapping_count)]

            logger_debug(
                6,
                "WAN Stats for element %s (site %s): %d total, %d admin-up, %d admin-disabled"
                % (element_id, site_id, total_interfaces, interfaces_up, interfaces_admin_disabled),
            )

            result_handler.update(RESULTS)

        except Exception as e:
            logger_debug(2, "Exception processing WAN interfaces", str(e))
            result_handler.update(RESULTS)
        except:
            logger_debug(3, "Unknown exception")
            result_handler.update(RESULTS)
####

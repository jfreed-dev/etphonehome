import silo_common.snippets as em7_snippets

# Palo Alto: Prisma Cloud Event Processor
# Version: 3.1
#
# Purpose: Processes Prisma SD-WAN events and generates actionable alerts.
# Data Source: Reads from API Collector cache (PRISMACLOUD+EVENTS).
#
# Alerting Strategy:
#   CARRIER_TICKET - Circuit failures (DEVICEHW_INTERFACE_DOWN, DIRECTINTERNET_DOWN)
#   BANDWIDTH_REVIEW - Capacity issues (BANDWIDTH_LIMIT_EXCEEDED)
#   INVESTIGATE - Root cause events (SITE_CONNECTIVITY_DOWN, BGP_DOWN)
#   INFORMATIONAL - Downstream/aggregate events (ANYNETLINK, VPNLINK) - logged only
#
# Filters: Suppressed events, cleared events, correlation dedup, severity (critical/major only)

SNIPPET_NAME = "Palo Alto: Prisma Devices Event Processor | v 3.1.0"
CACHE_KEY_EVTS = "PRISMACLOUD+EVENTS+%s" % (self.did)
CACHE_KEY_SITES = "PRISMACLOUD+SITES+%s" % (self.did)
CACHE_KEY_DEVS = "PRISMACLOUD+DEVICES+%s" % (self.did)

RESULTS = {"events_total": [(0, 0)], "events_ok": [(0, 0)], "events_failed": [(0, 0)]}

ALERTABLE_SEVERITIES = ["critical", "major"]

CARRIER_TICKET_EVENTS = [
    "NETWORK_DIRECTINTERNET_DOWN",
    "NETWORK_DIRECTPRIVATE_DOWN",
    "DEVICEHW_INTERFACE_DOWN",
    "DEVICEHW_INTERFACE_ERRORS",
]

BANDWIDTH_REVIEW_EVENTS = [
    "VION_BANDWIDTH_LIMIT_EXCEEDED",
    "SPN_BANDWIDTH_LIMIT_EXCEEDED",
    "NETWORK_PRIVATEWAN_DEGRADED",
]

INVESTIGATE_EVENTS = [
    "SITE_CONNECTIVITY_DOWN",
    "SITE_CONNECTIVITY_DEGRADED",
    "NETWORK_SECUREFABRICLINK_DOWN",
    "PEERING_BGP_DOWN",
]

INFORMATIONAL_EVENTS = [
    "NETWORK_ANYNETLINK_DOWN",
    "NETWORK_ANYNETLINK_DEGRADED",
    "NETWORK_VPNLINK_DOWN",
    "NETWORK_VPNLINK_DEGRADED",
    "NETWORK_VPNPEER_UNAVAILABLE",
    "NETWORK_SECUREFABRICLINK_DEGRADED",
    "NETWORK_VPNKEK_UNAVAILABLE",
]


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


def get_child_devices():
    res_dict = {}
    sql = (
        "SELECT `unique_id`, `did` FROM `collector_state`.`V_device` WHERE `unique_id` IS NOT NULL"
    )
    self.dbc.execute(sql)
    for row in self.dbc.fetchall():
        if isinstance(row, tuple) and len(row) > 0:
            res_dict[str(row[0])] = str(row[1])
    return res_dict


def get_site_name_map(cache_ptr):
    site_map = {}
    try:
        sites_data = cache_ptr.get(CACHE_KEY_SITES)
        if sites_data and isinstance(sites_data, dict) and "items" in sites_data:
            for site in sites_data["items"]:
                site_id = str(site.get("id", ""))
                if site_id:
                    site_map[site_id] = site.get("name", "Unknown Site")
    except Exception as e:
        logger_debug(4, "Error building site map:", str(e))
    return site_map


def get_device_name_map(cache_ptr):
    device_map = {}
    try:
        devices_data = cache_ptr.get(CACHE_KEY_DEVS)
        if devices_data and isinstance(devices_data, dict) and "items" in devices_data:
            for device in devices_data["items"]:
                element_id = str(device.get("id", ""))
                if element_id:
                    device_map[element_id] = device.get("name", "Unknown Device")
    except Exception as e:
        logger_debug(4, "Error building device map:", str(e))
    return device_map


def classify_event(event_code):
    if event_code in CARRIER_TICKET_EVENTS:
        return "CARRIER_TICKET"
    elif event_code in BANDWIDTH_REVIEW_EVENTS:
        return "BANDWIDTH_REVIEW"
    elif event_code in INVESTIGATE_EVENTS:
        return "INVESTIGATE"
    elif event_code in INFORMATIONAL_EVENTS:
        return "INFORMATIONAL"
    else:
        return "UNKNOWN"


def extract_root_cause(event):
    root_causes = []
    info = event.get("info")
    if info and isinstance(info, dict):
        vpn_reasons = info.get("vpn_reasons", [])
        if vpn_reasons and isinstance(vpn_reasons, list):
            for reason in vpn_reasons:
                root_causes.append(
                    {
                        "code": reason.get("code", "UNKNOWN"),
                        "element_id": str(reason.get("element_id", "")),
                        "site_id": str(reason.get("site_id", "")),
                    }
                )
    return root_causes


def build_actionable_message(event, classification, site_map, device_map):
    event_code = event.get("code", "UNKNOWN")
    severity = event.get("severity", "unknown")
    site_id = str(event.get("site_id", ""))
    site_name = site_map.get(site_id, "Unknown Site")
    root_causes = extract_root_cause(event)
    root_cause_text = ""
    if root_causes:
        rc = root_causes[0]
        rc_device = device_map.get(rc["element_id"], rc["element_id"][:8] + "...")
        rc_site = site_map.get(rc["site_id"], "Unknown")
        root_cause_text = " | Root cause: %s at %s (%s)" % (rc["code"], rc_device, rc_site)
    if classification == "CARRIER_TICKET":
        if event_code == "NETWORK_DIRECTINTERNET_DOWN":
            msg = "CARRIER TICKET REQUIRED: Internet circuit down at %s" % site_name
        elif event_code == "NETWORK_DIRECTPRIVATE_DOWN":
            msg = "CARRIER TICKET REQUIRED: Private WAN circuit down at %s" % site_name
        elif event_code == "DEVICEHW_INTERFACE_DOWN":
            msg = "CARRIER TICKET REQUIRED: Physical interface down at %s" % site_name
        elif event_code == "DEVICEHW_INTERFACE_ERRORS":
            msg = (
                "CARRIER TICKET REQUIRED: High interface error rate at %s (check circuit quality)"
                % site_name
            )
        else:
            msg = "CARRIER TICKET REQUIRED: %s at %s" % (event_code, site_name)
    elif classification == "BANDWIDTH_REVIEW":
        if event_code == "VION_BANDWIDTH_LIMIT_EXCEEDED":
            msg = "BANDWIDTH UPGRADE RECOMMENDED: Virtual ION capacity exceeded at %s" % site_name
        elif event_code == "SPN_BANDWIDTH_LIMIT_EXCEEDED":
            msg = (
                "BANDWIDTH UPGRADE RECOMMENDED: Security service capacity exceeded at %s"
                % site_name
            )
        elif event_code == "NETWORK_PRIVATEWAN_DEGRADED":
            msg = "BANDWIDTH/ROUTING REVIEW: Private WAN degraded at %s" % site_name
        else:
            msg = "BANDWIDTH REVIEW: %s at %s" % (event_code, site_name)
    elif classification == "INVESTIGATE":
        if event_code == "SITE_CONNECTIVITY_DOWN":
            msg = "CRITICAL - SITE UNREACHABLE: %s%s" % (site_name, root_cause_text)
        elif event_code == "SITE_CONNECTIVITY_DEGRADED":
            msg = "SITE CONNECTIVITY DEGRADED: %s%s" % (site_name, root_cause_text)
        elif event_code == "PEERING_BGP_DOWN":
            msg = "BGP PEER DOWN: %s - Check routing configuration" % site_name
        else:
            msg = "INVESTIGATE: %s at %s%s" % (event_code, site_name, root_cause_text)
    elif classification == "INFORMATIONAL":
        msg = "INFO: %s at %s (redundancy may be active)" % (
            event_code.replace("_", " ").title(),
            site_name,
        )
    else:
        msg = "SD-WAN Alert: %s at %s (%s)" % (event_code, site_name, severity)
    return msg


##main:
logger_debug(7, SNIPPET_NAME)

try:
    cache_ptr = em7_snippets.cache_api(self)
    cache_data = cache_ptr.get(CACHE_KEY_EVTS)

    if cache_data is None:
        logger_debug(7, "Cache key does not exist: %s" % CACHE_KEY_EVTS)
        result_handler.update(RESULTS)
    elif isinstance(cache_data, list):
        if len(cache_data) > 0:
            logger_debug(7, "Cache found with %d events" % len(cache_data))
            child_devices = get_child_devices()
            site_map = get_site_name_map(cache_ptr)
            device_map = get_device_name_map(cache_ptr)
            events_total = len(cache_data)
            events_ok, events_failed, events_suppressed, events_correlated, events_low_severity = (
                0,
                0,
                0,
                0,
                0,
            )
            alerts_carrier, alerts_bandwidth, alerts_investigate = 0, 0, 0
            processed_correlations = set()

            for event_dict in cache_data:
                event_code = event_dict.get("code", "UNKNOWN")
                correlation_id = event_dict.get("correlation_id", "")
                is_suppressed = event_dict.get("suppressed", False)
                is_cleared = event_dict.get("cleared", False)
                severity = event_dict.get("severity", "unknown").lower()
                logger_debug(
                    7, "EVENT: %s (severity: %s, corr: %s)" % (event_code, severity, correlation_id)
                )

                if is_suppressed:
                    logger_debug(7, "  > SKIPPED: Event is suppressed by Prisma")
                    events_suppressed += 1
                    continue
                if is_cleared:
                    logger_debug(7, "  > SKIPPED: Event is cleared")
                    continue
                if correlation_id and correlation_id in processed_correlations:
                    logger_debug(7, "  > SKIPPED: Correlation ID already processed")
                    events_correlated += 1
                    continue
                if correlation_id:
                    processed_correlations.add(correlation_id)

                classification = classify_event(event_code)
                logger_debug(7, "  > Classification: %s" % classification)

                if classification == "INFORMATIONAL":
                    logger_debug(
                        6, "  > Informational event logged but not alerted: %s" % event_code
                    )
                    events_ok += 1
                    continue

                if severity not in ALERTABLE_SEVERITIES:
                    logger_debug(
                        6,
                        "  > SKIPPED: Low severity (%s) - only alerting on critical/major"
                        % severity,
                    )
                    events_low_severity += 1
                    events_ok += 1
                    continue

                message = build_actionable_message(event_dict, classification, site_map, device_map)
                logger_debug(7, "  > Message: %s" % message)

                elements = []
                element_id = str(event_dict.get("element_id", "None"))
                if element_id == "None":
                    root_causes = extract_root_cause(event_dict)
                    for rc in root_causes:
                        if rc["element_id"]:
                            elements.append(rc["element_id"])
                else:
                    elements.append(element_id)

                if elements:
                    for elem_id in elements:
                        if elem_id in child_devices:
                            target_did = int(child_devices[elem_id])
                            logger_debug(7, "  > Alerting device DID: %s" % target_did)
                            em7_snippets.generate_alert(message, target_did, "1")
                            events_ok += 1
                            if classification == "CARRIER_TICKET":
                                alerts_carrier += 1
                            elif classification == "BANDWIDTH_REVIEW":
                                alerts_bandwidth += 1
                            elif classification == "INVESTIGATE":
                                alerts_investigate += 1
                        else:
                            logger_debug(7, "  > No SL1 device found for element: %s" % elem_id)
                            events_failed += 1
                else:
                    logger_debug(7, "  > No specific element, alerting parent device")
                    em7_snippets.generate_alert(message, self.did, "1")
                    events_ok += 1
                    if classification == "CARRIER_TICKET":
                        alerts_carrier += 1
                    elif classification == "BANDWIDTH_REVIEW":
                        alerts_bandwidth += 1
                    elif classification == "INVESTIGATE":
                        alerts_investigate += 1

            RESULTS["events_total"] = [(0, events_total)]
            RESULTS["events_ok"] = [(0, events_ok)]
            RESULTS["events_failed"] = [(0, events_failed)]
            logger_debug(
                6,
                "Processing complete: %d total, %d ok, %d suppressed, %d correlated, %d low_severity"
                % (
                    events_total,
                    events_ok,
                    events_suppressed,
                    events_correlated,
                    events_low_severity,
                ),
            )
            logger_debug(
                6,
                "Alerts generated: %d carrier, %d bandwidth, %d investigate"
                % (alerts_carrier, alerts_bandwidth, alerts_investigate),
            )
            result_handler.update(RESULTS)
        else:
            logger_debug(7, "Cache exists but is empty (no events in collection window)")
            result_handler.update(RESULTS)
    else:
        logger_debug(4, "Unexpected cache data type: %s" % type(cache_data).__name__)
except Exception as e:
    logger_debug(3, "Exception Caught: %s" % str(e))
except:
    logger_debug(3, "Unknown Exception")
#####

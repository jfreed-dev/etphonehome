import base64
import json
import pprint
import time
from datetime import datetime

import requests
import silo_common.snippets as em7_snippets

# Palo Alto: Prisma Cloud API Collector
# Version: 2.6
#
# Purpose: Collects and caches data from Prisma SD-WAN API for downstream DAs.
# Caches: Sites, Devices, Events, WAN Interfaces (keyed by site ID).
# Original: Used CloudGenix API key authentication.
# Changed: Migrated to Prisma SASE OAuth2; added WAN interface caching.
# v2.3: Fixed WAN interface caching - fetch at element level instead of site level
#       Site-level API doesn't return element_id, causing per-element cache to be empty
# v2.4: Added dynamic WANINTERFACE_VERSION lookup from permissions API
# v2.5: Changed WAN interface fetch to site-level /api/sites/{site_id}/waninterfaces
#       Per-element endpoint doesn't exist in v2.10+ API (returns 502)
# v2.6: Fixed WAN interface caching - cache by SITE not element
#       API confirms: WAN interfaces are site-level circuit definitions (no element_id)
#       Elements at a site share the same WAN interface pool

SNIPPET_NAME = "Palo Alto: Prisma Cloud API Collector | v 2.6.0"
RESULTS = {
    "sites": [(0, "Fail")],
    "devices": [(0, "Fail")],
    "events": [(0, "Fail")],
    "tenant": [(0, "Fail")],
    "waninterfaces": [(0, "Fail")],
}

CACHE_KEY_DEVS = "PRISMACLOUD+DEVICES+%s" % (self.did)
CACHE_KEY_EVET = "PRISMACLOUD+EVENTS+%s" % (self.did)
CACHE_KEY_SITE = "PRISMACLOUD+SITES+%s" % (self.did)
CACHE_KEY_TENT = "PRISMACLOUD+TENNANT+%s" % (self.did)
CACHE_KEY_WAN = "PRISMACLOUD+WANINTERFACES+%s" % (self.did)

CACHE_PTR = em7_snippets.cache_api(self)
CACHE_TTL = self.ttl + 1440
EVENT_SECONDS = 600  # seconds from start to end date for events
SESSION = None
TENANT_ID = None
ACCESS_TOKEN = None

# API base URL for Prisma SASE (replaces api.hood.cloudgenix.com)
API_BASE_URL = "https://api.sase.paloaltonetworks.com"

##default API versions for different endpoints
PROFILE_VERSION = "2.1"
SITE_VERSION = "4.7"
ELEMENTS_VERSION = "3.0"
EVENTS_VERSION = "3.4"
WANINTERFACE_VERSION = "2.5"


# functions
def var_dump(val):
    pp = pprint.PrettyPrinter(indent=0)
    pp.pprint(val)


##simple logger
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


def extract_tsg_id(username):
    """Extract TSG ID from service account username.
    Format: SA-xxx@{TSG_ID}.iam.panserviceaccount.com
    """
    if "@" in username:
        domain_part = username.split("@")[1]
        if ".iam.panserviceaccount.com" in domain_part:
            return domain_part.split(".")[0]
    return None


def get_oauth_token():
    """Get OAuth2 token from Prisma SASE auth endpoint using credential."""
    global ACCESS_TOKEN

    # Get auth URL from credential's curl_url field
    auth_url = self.cred_details.get("curl_url", "https://auth.apps.paloaltonetworks.com")
    if auth_url and not auth_url.startswith("http"):
        auth_url = "https://%s" % (auth_url)

    username = self.cred_details.get("cred_user", "")
    password = self.cred_details.get("cred_pwd", "")

    # Extract TSG ID from username
    tsg_id = extract_tsg_id(username)
    if not tsg_id:
        logger_debug(3, "Could not extract TSG ID from username")
        return None

    token_url = "%s/auth/v1/oauth2/access_token" % (auth_url.rstrip("/"))
    auth_header = base64.b64encode("%s:%s" % (username, password)).decode("utf-8")

    headers = {
        "Authorization": "Basic %s" % (auth_header),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    post_data = "grant_type=client_credentials&scope=tsg_id:%s" % (tsg_id)
    timeout = (
        int(self.cred_details["cred_timeout"] / 1000)
        if self.cred_details.get("cred_timeout")
        else 30
    )

    try:
        response = requests.post(
            token_url, headers=headers, data=post_data, verify=True, timeout=timeout
        )
        if response.status_code == 200:
            token_data = response.json()
            ACCESS_TOKEN = token_data.get("access_token")
            logger_debug(7, "OAuth token obtained successfully")
            return ACCESS_TOKEN
        else:
            logger_debug(3, "OAuth token request failed", response.status_code)
            return None
    except Exception as e:
        logger_debug(2, "Exception in get_oauth_token()", str(e))
        return None


def record_api_fails(status_code, api_path):
    if status_code != 200:
        logger_debug(4, "HTTP Status not correct: %s" % (status_code))
        if status_code == 429:
            em7_snippets.generate_alert(
                "Prisma Cloud API: Cloud Service Throttling Detected, Check Prisma Cloud Documents for Details (API: %s)"
                % (api_path),
                self.did,
                "1",
            )
        elif status_code == 401:
            em7_snippets.generate_alert(
                "Prisma Cloud API: Cloud Service Reporting Account is Unauthorized, Check Credential (API: %s)"
                % (api_path),
                self.did,
                "1",
            )
        elif status_code == 400:
            em7_snippets.generate_alert(
                "Prisma Cloud API: Cloud Service Reporting Bad Request (API: %s)" % (api_path),
                self.did,
                "1",
            )
        elif status_code == 403:
            em7_snippets.generate_alert(
                "Prisma Cloud API: Cloud Service Forbidding Access, Check Credential or URL (API: %s)"
                % (api_path),
                self.did,
                "1",
            )
        elif status_code == 503:
            em7_snippets.generate_alert(
                "Prisma Cloud API: The Cloud Service is Currently Unavailable, Check Vendor Service for Maintenance Schedules (API: %s)"
                % (api_path),
                self.did,
                "1",
            )
        elif status_code == 521:
            em7_snippets.generate_alert(
                "Prisma Cloud API: Cloud Service Reporting API is Down for Maintenance (API: %s)"
                % (api_path),
                self.did,
                "1",
            )
        else:
            em7_snippets.generate_alert(
                "Prisma Cloud API: Cloud Service Returned an Unexpected Status Code %s (API: %s)"
                % (status_code, api_path),
                self.did,
                "1",
            )


def scrub_version_chars(ver_str):
    r"""
    Unpack format for versions,
    Example: v(4\.6|4\.7)
    """
    ver_str = str(ver_str).replace("v", "").replace("(", "").replace(")", "").replace("\\", "")
    if "|" in ver_str:
        ver_str_parts = ver_str.split("|")
        return ver_str_parts[len(ver_str_parts) - 1].strip()
    return ver_str.strip()


def fetch_api_data(api_path, json_payload=None):
    """
    Fetch Data from Palo Alto Network
    Prisma Cloud API service, returns JSON payload
    Uses OAuth Bearer token authentication
    """
    global SESSION, ACCESS_TOKEN

    # Build URL using new API base
    url = "%s%s" % (API_BASE_URL, api_path)
    headers = {
        "accept": "application/json;charset=UTF-8",
        "Authorization": "Bearer %s" % (ACCESS_TOKEN),
    }
    timeout = (
        int(self.cred_details["cred_timeout"] / 100)
        if self.cred_details.get("cred_timeout")
        else 30
    )

    logger_debug(7, "Fetching: %s" % (url))

    try:
        if SESSION is None:
            SESSION = requests.Session()

        if json_payload is not None:
            api_request = SESSION.post(
                url, headers=headers, verify=True, timeout=timeout, json=json_payload
            )
        else:
            api_request = SESSION.get(url, headers=headers, verify=True, timeout=timeout)

        record_api_fails(api_request.status_code, api_path)

        if api_request.status_code == 200:
            return api_request.json()

    except Exception as e:
        logger_debug(2, "Exception Caught in fetch_api_data()", str(e))
    except:
        logger_debug(3, "Unknown Exception in fetch_api_data()")


##main:
logger_debug(7, SNIPPET_NAME)

if self.cred_details["cred_type"] == 3:
    username = self.cred_details.get("cred_user")
    password = self.cred_details.get("cred_pwd")

    if username is not None and password is not None:
        try:
            # Step 1: Get OAuth token
            token = get_oauth_token()
            if token is None:
                logger_debug(3, "Failed to obtain OAuth token")
                result_handler.update(RESULTS)
            else:
                # Step 2: CRITICAL - Initialize session with profile call
                logger_debug(7, "Initializing session with profile call")
                ret_data = fetch_api_data("/sdwan/v%s/api/profile" % (PROFILE_VERSION))

                if isinstance(ret_data, dict) and "tenant_id" in ret_data:
                    TENANT_ID = ret_data["tenant_id"]
                    RESULTS["tenant"] = [(0, "Okay")]
                    CACHE_PTR.cache_result(ret_data, ttl=CACHE_TTL, commit=True, key=CACHE_KEY_TENT)
                    logger_debug(7, "Profile initialized, tenant_id", TENANT_ID)

                # Step 3: Get permissions to check API versions (optional)
                perm_data = fetch_api_data("/sdwan/v2.0/api/permissions")
                if isinstance(perm_data, dict) and "resource_version_map" in perm_data:
                    logger_debug(7, " > VERSION MAP FOUND")
                    if "sites" in perm_data["resource_version_map"]:
                        SITE_VERSION = scrub_version_chars(
                            perm_data["resource_version_map"]["sites"]
                        )
                        logger_debug(7, " >> SITES VERSION FOUND: %s" % (SITE_VERSION))
                    if "elements" in perm_data["resource_version_map"]:
                        ELEMENTS_VERSION = scrub_version_chars(
                            perm_data["resource_version_map"]["elements"]
                        )
                        logger_debug(7, " >> ELEMENTS VERSION FOUND: %s" % (ELEMENTS_VERSION))
                    if "query_events" in perm_data["resource_version_map"]:
                        EVENTS_VERSION = scrub_version_chars(
                            perm_data["resource_version_map"]["query_events"]
                        )
                        logger_debug(7, " >> EVENTS VERSION FOUND: %s" % (EVENTS_VERSION))
                    if "waninterfaces" in perm_data["resource_version_map"]:
                        WANINTERFACE_VERSION = scrub_version_chars(
                            perm_data["resource_version_map"]["waninterfaces"]
                        )
                        logger_debug(
                            7, " >> WANINTERFACES VERSION FOUND: %s" % (WANINTERFACE_VERSION)
                        )
                    else:
                        logger_debug(
                            7,
                            " >> WANINTERFACES VERSION NOT IN MAP, using default: %s"
                            % (WANINTERFACE_VERSION),
                        )

                # Step 4: Fetch data if we have a tenant ID
                if TENANT_ID is not None:
                    ##SITE LOCATIONS....
                    ret_data = fetch_api_data("/sdwan/v%s/api/sites" % (SITE_VERSION))
                    if isinstance(ret_data, dict) and "items" in ret_data:
                        RESULTS["sites"] = [(0, "Okay")]
                        CACHE_PTR.cache_result(
                            ret_data, ttl=CACHE_TTL, commit=True, key=CACHE_KEY_SITE
                        )
                        ##store each site cache...
                        for ele_dict in ret_data["items"]:
                            site_id = str(ele_dict["id"])
                            logger_debug(7, "Site: %s" % (site_id))
                            cache_key = "%s+%s" % (CACHE_KEY_SITE, site_id)
                            CACHE_PTR.cache_result(
                                ele_dict, ttl=CACHE_TTL, commit=True, key=cache_key
                            )

                    ##DEVICES....
                    ret_data = fetch_api_data("/sdwan/v%s/api/elements" % (ELEMENTS_VERSION))
                    if isinstance(ret_data, dict) and "items" in ret_data:
                        RESULTS["devices"] = [(0, "Okay")]
                        CACHE_PTR.cache_result(
                            ret_data, ttl=CACHE_TTL, commit=True, key=CACHE_KEY_DEVS
                        )
                        ##store each device cache...
                        post_res = {}
                        for ele_dict in ret_data["items"]:
                            element_id = str(ele_dict["id"])
                            site_id = str(ele_dict["site_id"])
                            logger_debug(7, "Device ID: %s" % (element_id))
                            ##
                            if site_id not in post_res:
                                post_res[site_id] = []
                            post_res[site_id].append(ele_dict)
                            ##
                            cache_key = "%s+%s" % (CACHE_KEY_DEVS, element_id)
                            logger_debug(7, " > %s" % (cache_key))
                            CACHE_PTR.cache_result(
                                ele_dict, ttl=CACHE_TTL, commit=True, key=cache_key
                            )

                        ##A dict of lists for caching...
                        for site_id, list_vals in post_res.iteritems():
                            cache_key = "%s+%s+DEVICES" % (CACHE_KEY_SITE, site_id)
                            logger_debug(7, " > %s" % (cache_key))
                            CACHE_PTR.cache_result(
                                list_vals, ttl=CACHE_TTL, commit=True, key=cache_key
                            )

                        ##WAN INTERFACES - v2.6: fetch at site level, cache by site
                        # Per-element endpoint returns 502 - doesn't exist in unified SASE API
                        # WAN interfaces are site-level circuit definitions shared by all elements
                        logger_debug(7, "Fetching WAN interfaces at site level")
                        all_wan_interfaces = []
                        sites_with_wan = 0

                        # Get sites from cached data
                        site_data = CACHE_PTR.get(CACHE_KEY_SITE)
                        if isinstance(site_data, dict) and "items" in site_data:
                            for site_dict in site_data["items"]:
                                site_id = str(site_dict["id"])
                                wan_path = "/sdwan/v%s/api/sites/%s/waninterfaces" % (
                                    WANINTERFACE_VERSION,
                                    site_id,
                                )
                                wan_data = fetch_api_data(wan_path)

                                if isinstance(wan_data, dict) and "items" in wan_data:
                                    site_interfaces = wan_data["items"]
                                    logger_debug(
                                        7,
                                        "  Site %s: %d WAN interfaces"
                                        % (site_id, len(site_interfaces)),
                                    )

                                    # Add site_id to each interface for reference
                                    for intf in site_interfaces:
                                        intf["_site_id"] = site_id
                                        all_wan_interfaces.append(intf)

                                    # Cache per-site WAN interfaces
                                    if site_interfaces:
                                        wan_site_cache_key = "%s+%s" % (CACHE_KEY_WAN, site_id)
                                        CACHE_PTR.cache_result(
                                            site_interfaces,
                                            ttl=CACHE_TTL,
                                            commit=True,
                                            key=wan_site_cache_key,
                                        )
                                        logger_debug(
                                            7,
                                            "    Cached %d interfaces -> %s"
                                            % (len(site_interfaces), wan_site_cache_key),
                                        )
                                        sites_with_wan += 1

                        # Cache all WAN interfaces (aggregate)
                        if all_wan_interfaces:
                            wan_interface_count = len(all_wan_interfaces)
                            CACHE_PTR.cache_result(
                                all_wan_interfaces, ttl=CACHE_TTL, commit=True, key=CACHE_KEY_WAN
                            )
                            RESULTS["waninterfaces"] = [(0, "Okay")]
                            logger_debug(
                                6,
                                "Cached %d total WAN interfaces for %d sites"
                                % (wan_interface_count, sites_with_wan),
                            )
                        else:
                            logger_debug(5, "No WAN interfaces returned from site-level API")

                    ##EVENTS...
                    now_time = time.time()
                    sta_time = now_time - EVENT_SECONDS
                    end_obj = datetime.fromtimestamp(now_time)
                    sta_obj = datetime.fromtimestamp(sta_time)
                    end_iso = end_obj.isoformat()
                    sta_iso = sta_obj.isoformat()
                    payload = (
                        """{"severity":["critical","major","minor"],"query":{"type":["alarm"]},"_offset": null,"view":{"summary": false},"start_time":"%s","end_time":"%s"}"""
                        % (sta_iso, end_iso)
                    )
                    ##
                    ret_data = fetch_api_data(
                        "/sdwan/v%s/api/events/query" % (EVENTS_VERSION), json.loads(payload)
                    )
                    ##
                    if isinstance(ret_data, dict) and "items" in ret_data:
                        event_count = len(ret_data["items"])
                        logger_debug(
                            7,
                            "Events fetched: %d items in %d second window"
                            % (event_count, EVENT_SECONDS),
                        )
                        RESULTS["events"] = [(0, "Okay")]
                        CACHE_PTR.cache_result(
                            ret_data["items"], ttl=CACHE_TTL, commit=True, key=CACHE_KEY_EVET
                        )
                        logger_debug(7, "Events cached to: %s" % (CACHE_KEY_EVET))
                    else:
                        logger_debug(4, "Events API returned unexpected response")

                result_handler.update(RESULTS)
            ##
        except Exception as e:
            logger_debug(2, "Exception Caught in Snippet", str(e))
        except:
            logger_debug(3, "Unknown Exception in Snippet")
    else:
        logger_debug(3, "Credential Missing Username or Password")
else:
    logger_debug(
        3, "Wrong Credential Type Aligned to This Dynamic Application, Requires SOAP/XML Credential"
    )
####

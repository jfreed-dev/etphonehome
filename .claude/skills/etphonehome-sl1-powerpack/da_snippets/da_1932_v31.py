import base64
import json
import pprint
import time
from datetime import datetime

import requests
import silo_common.snippets as em7_snippets

# Palo Alto: Prisma Cloud API Collector
# Version: 3.1
#
# Collects and caches data from Prisma SD-WAN API for downstream DAs.
# Caches: Sites, Devices, Events, WAN Interfaces, Element Interfaces.
# v2.7: Added element interfaces fetching to extract management IPs
#       Stores _mgmt_ip in element cache for SNMP discovery/merge
# v2.8: Fixed controller interface detection - now checks interface name
#       for "controller" to correctly identify management interfaces
# v2.9: Fixed site-level cache to include _mgmt_ip for downstream DAs
#       (Prisma Cloud Devices DA can now collect controller IP)
# v3.0: Enhanced controller IP detection with ION 3200 fallback logic
#       Adds fallback to interface "5" with x.x.2.x pattern when no
#       explicit controller interface found (fixes ION 3200 detection)
# v3.1: Removed x.x.2.x pattern requirement for interface 5 fallback
#       Interface 5 now accepts any valid IP address (not just x.x.2.x)
#       Priority: controller type first, interface 5 as best guess fallback

SNIPPET_NAME = "Palo Alto: Prisma Cloud API Collector | v 3.1.0"
RESULTS = {
	"sites": [(0, "Fail")],
	"devices": [(0, "Fail")],
	"events": [(0, "Fail")],
	"tenant": [(0, "Fail")],
	"waninterfaces": [(0, "Fail")],
	"interfaces": [(0, "Fail")],
}

CACHE_KEY_DEVS = "PRISMACLOUD+DEVICES+%s" % (self.did)
CACHE_KEY_EVET = "PRISMACLOUD+EVENTS+%s" % (self.did)
CACHE_KEY_SITE = "PRISMACLOUD+SITES+%s" % (self.did)
CACHE_KEY_TENT = "PRISMACLOUD+TENNANT+%s" % (self.did)
CACHE_KEY_WAN = "PRISMACLOUD+WANINTERFACES+%s" % (self.did)
CACHE_KEY_INTF = "PRISMACLOUD+INTERFACES+%s" % (self.did)

CACHE_PTR = em7_snippets.cache_api(self)
CACHE_TTL = self.ttl + 1440
EVENT_SECONDS = 600
SESSION = None
TENANT_ID = None
ACCESS_TOKEN = None

API_BASE_URL = "https://api.sase.paloaltonetworks.com"

PROFILE_VERSION = "2.1"
SITE_VERSION = "4.7"
ELEMENTS_VERSION = "3.0"
EVENTS_VERSION = "3.4"
WANINTERFACE_VERSION = "2.5"
INTERFACES_VERSION = "4.20"

def var_dump(val):
	pp = pprint.PrettyPrinter(indent=0)
	pp.pprint(val)

def logger_debug(s=7, m=None, v=None):
	sevs = {0:"EMERGENCY",1:"ALERT",2:"CRITICAL",3:"ERROR",4:"WARNING",5:"NOTICE",6:"INFORMATION",7:"DEBUG"}
	if m is not None and v is not None:
		self.logger.ui_debug("[%s] %s %s" % (sevs[s], str(m), str(v)))
	elif m is not None:
		self.logger.ui_debug("[%s] %s" % (sevs[s], str(m)))

def extract_tsg_id(username):
	if "@" in username:
		domain_part = username.split("@")[1]
		if ".iam.panserviceaccount.com" in domain_part:
			return domain_part.split(".")[0]
	return None

def get_oauth_token():
	global ACCESS_TOKEN
	auth_url = self.cred_details.get("curl_url", "https://auth.apps.paloaltonetworks.com")
	if auth_url and not auth_url.startswith("http"):
		auth_url = "https://%s" % (auth_url)
	username = self.cred_details.get("cred_user", "")
	password = self.cred_details.get("cred_pwd", "")
	tsg_id = extract_tsg_id(username)
	if not tsg_id:
		logger_debug(3, "Could not extract TSG ID from username")
		return None
	token_url = "%s/auth/v1/oauth2/access_token" % (auth_url.rstrip("/"))
	auth_header = base64.b64encode("%s:%s" % (username, password)).decode("utf-8")
	headers = {"Authorization": "Basic %s" % (auth_header), "Content-Type": "application/x-www-form-urlencoded"}
	post_data = "grant_type=client_credentials&scope=tsg_id:%s" % (tsg_id)
	timeout = int(self.cred_details["cred_timeout"] / 1000) if self.cred_details.get("cred_timeout") else 30
	try:
		response = requests.post(token_url, headers=headers, data=post_data, verify=True, timeout=timeout)
		if response.status_code == 200:
			ACCESS_TOKEN = response.json().get("access_token")
			logger_debug(7, "OAuth token obtained successfully")
			return ACCESS_TOKEN
		else:
			logger_debug(3, "OAuth token request failed", response.status_code)
			return None
	except Exception, e:
		logger_debug(2, "Exception in get_oauth_token()", str(e))
		return None

def record_api_fails(status_code, api_path):
	if status_code != 200:
		logger_debug(4, "HTTP Status not correct: %s" % (status_code))
		if status_code == 429:
			em7_snippets.generate_alert("Prisma Cloud API: Throttling Detected (API: %s)" % (api_path), self.did, "1")
		elif status_code == 401:
			em7_snippets.generate_alert("Prisma Cloud API: Unauthorized (API: %s)" % (api_path), self.did, "1")
		elif status_code == 403:
			em7_snippets.generate_alert("Prisma Cloud API: Forbidden (API: %s)" % (api_path), self.did, "1")
		elif status_code == 503:
			em7_snippets.generate_alert("Prisma Cloud API: Unavailable (API: %s)" % (api_path), self.did, "1")
		else:
			em7_snippets.generate_alert("Prisma Cloud API: Status %s (API: %s)" % (status_code, api_path), self.did, "1")

def scrub_version_chars(ver_str):
	ver_str = str(ver_str).replace("v", "").replace("(", "").replace(")", "").replace("\\", "")
	if "|" in ver_str:
		return ver_str.split("|")[-1].strip()
	return ver_str.strip()

def extract_mgmt_ip(interfaces):
	"""
	Extract management IP from element interfaces.

	Priority:
	1. Interface with type/used_for/name containing 'controller'
	2. Interface named '5' (fallback best guess when controller not found)

	Returns: IP address string (without CIDR) or None
	"""
	# First pass: Look for controller interfaces by name, used_for, or type
	for intf in interfaces:
		name = intf.get("name", "").lower()
		used_for = intf.get("used_for", "")
		intf_type = str(intf.get("type", "")).lower()
		if "controller" in name or used_for == "controller" or "controller" in intf_type:
			ipv4_config = intf.get("ipv4_config", {})
			if isinstance(ipv4_config, dict):
				# Check static config first
				static_config = ipv4_config.get("static_config", {})
				if isinstance(static_config, dict):
					ip_addr = static_config.get("address")
					if ip_addr:
						return ip_addr.split("/")[0] if "/" in str(ip_addr) else ip_addr
				# Then check DHCP config
				dhcp_config = ipv4_config.get("dhcp_config", {})
				if isinstance(dhcp_config, dict):
					ip_addr = dhcp_config.get("address")
					if ip_addr:
						return ip_addr.split("/")[0] if "/" in str(ip_addr) else ip_addr

	# Second pass: Interface 5 fallback - best guess when controller interface not found
	for intf in interfaces:
		name = intf.get("name", "")
		if name == "5":
			ipv4_config = intf.get("ipv4_config", {})
			if isinstance(ipv4_config, dict):
				# Check static config first
				static_config = ipv4_config.get("static_config", {})
				if isinstance(static_config, dict):
					ip_addr = static_config.get("address")
					if ip_addr:
						clean_ip = ip_addr.split("/")[0] if "/" in str(ip_addr) else ip_addr
						logger_debug(6, "Using interface 5 as management IP (best guess):", clean_ip)
						return clean_ip
				# Then check DHCP config
				dhcp_config = ipv4_config.get("dhcp_config", {})
				if isinstance(dhcp_config, dict):
					ip_addr = dhcp_config.get("address")
					if ip_addr:
						clean_ip = ip_addr.split("/")[0] if "/" in str(ip_addr) else ip_addr
						logger_debug(6, "Using interface 5 as management IP (best guess):", clean_ip)
						return clean_ip

	# No controller IP found
	return None

def fetch_api_data(api_path, json_payload=None):
	global SESSION, ACCESS_TOKEN
	url = "%s%s" % (API_BASE_URL, api_path)
	headers = {"accept": "application/json;charset=UTF-8", "Authorization": "Bearer %s" % (ACCESS_TOKEN)}
	timeout = int(self.cred_details["cred_timeout"] / 100) if self.cred_details.get("cred_timeout") else 30
	logger_debug(7, "Fetching: %s" % (url))
	try:
		if SESSION is None:
			SESSION = requests.Session()
		if json_payload is not None:
			api_request = SESSION.post(url, headers=headers, verify=True, timeout=timeout, json=json_payload)
		else:
			api_request = SESSION.get(url, headers=headers, verify=True, timeout=timeout)
		record_api_fails(api_request.status_code, api_path)
		if api_request.status_code == 200:
			return api_request.json()
	except Exception, e:
		logger_debug(2, "Exception in fetch_api_data()", str(e))
	except:
		logger_debug(3, "Unknown Exception in fetch_api_data()")

logger_debug(7, SNIPPET_NAME)

if self.cred_details["cred_type"] == 3:
	username = self.cred_details.get("cred_user")
	password = self.cred_details.get("cred_pwd")
	if username is not None and password is not None:
		try:
			token = get_oauth_token()
			if token is None:
				logger_debug(3, "Failed to obtain OAuth token")
				result_handler.update(RESULTS)
			else:
				logger_debug(7, "Initializing session with profile call")
				ret_data = fetch_api_data("/sdwan/v%s/api/profile" % (PROFILE_VERSION))
				if isinstance(ret_data, dict) and "tenant_id" in ret_data:
					TENANT_ID = ret_data["tenant_id"]
					RESULTS["tenant"] = [(0, "Okay")]
					CACHE_PTR.cache_result(ret_data, ttl=CACHE_TTL, commit=True, key=CACHE_KEY_TENT)
					logger_debug(7, "Profile initialized, tenant_id", TENANT_ID)

				perm_data = fetch_api_data("/sdwan/v2.0/api/permissions")
				if isinstance(perm_data, dict) and "resource_version_map" in perm_data:
					logger_debug(7, " > VERSION MAP FOUND")
					if "sites" in perm_data["resource_version_map"]:
						SITE_VERSION = scrub_version_chars(perm_data["resource_version_map"]["sites"])
					if "elements" in perm_data["resource_version_map"]:
						ELEMENTS_VERSION = scrub_version_chars(perm_data["resource_version_map"]["elements"])
					if "query_events" in perm_data["resource_version_map"]:
						EVENTS_VERSION = scrub_version_chars(perm_data["resource_version_map"]["query_events"])
					if "waninterfaces" in perm_data["resource_version_map"]:
						WANINTERFACE_VERSION = scrub_version_chars(perm_data["resource_version_map"]["waninterfaces"])
					if "interfaces" in perm_data["resource_version_map"]:
						INTERFACES_VERSION = scrub_version_chars(perm_data["resource_version_map"]["interfaces"])

				if TENANT_ID is not None:
					ret_data = fetch_api_data("/sdwan/v%s/api/sites" % (SITE_VERSION))
					if isinstance(ret_data, dict) and "items" in ret_data:
						RESULTS["sites"] = [(0, "Okay")]
						CACHE_PTR.cache_result(ret_data, ttl=CACHE_TTL, commit=True, key=CACHE_KEY_SITE)
						for ele_dict in ret_data["items"]:
							site_id = str(ele_dict["id"])
							cache_key = "%s+%s" % (CACHE_KEY_SITE, site_id)
							CACHE_PTR.cache_result(ele_dict, ttl=CACHE_TTL, commit=True, key=cache_key)

					ret_data = fetch_api_data("/sdwan/v%s/api/elements" % (ELEMENTS_VERSION))
					if isinstance(ret_data, dict) and "items" in ret_data:
						RESULTS["devices"] = [(0, "Okay")]
						CACHE_PTR.cache_result(ret_data, ttl=CACHE_TTL, commit=True, key=CACHE_KEY_DEVS)
						post_res = {}
						element_list = ret_data["items"]

						# First pass: group elements by site_id
						for ele_dict in element_list:
							site_id = str(ele_dict["site_id"])
							if site_id not in post_res:
								post_res[site_id] = []
							post_res[site_id].append(ele_dict)

						# Second pass: fetch interfaces and add _mgmt_ip to each element
						logger_debug(7, "Fetching element interfaces for management IPs")
						all_interfaces = []
						elements_with_mgmt_ip = 0
						for ele_dict in element_list:
							element_id = str(ele_dict["id"])
							site_id = str(ele_dict["site_id"])
							element_name = ele_dict.get("name", element_id)
							intf_path = "/sdwan/v%s/api/sites/%s/elements/%s/interfaces" % (INTERFACES_VERSION, site_id, element_id)
							intf_data = fetch_api_data(intf_path)
							if isinstance(intf_data, dict) and "items" in intf_data:
								element_interfaces = intf_data["items"]
								logger_debug(7, "  Element %s: %d interfaces" % (element_name, len(element_interfaces)))
								mgmt_ip = extract_mgmt_ip(element_interfaces)
								if mgmt_ip:
									logger_debug(6, "  Element %s mgmt IP: %s" % (element_name, mgmt_ip))
									elements_with_mgmt_ip += 1
									# Add _mgmt_ip to element dict (this modifies the dict in post_res too)
									ele_dict["_mgmt_ip"] = mgmt_ip
								for intf in element_interfaces:
									intf["_element_id"] = element_id
									intf["_site_id"] = site_id
									all_interfaces.append(intf)
								if element_interfaces:
									intf_cache_key = "%s+%s" % (CACHE_KEY_INTF, element_id)
									CACHE_PTR.cache_result(element_interfaces, ttl=CACHE_TTL, commit=True, key=intf_cache_key)

						if all_interfaces:
							CACHE_PTR.cache_result(all_interfaces, ttl=CACHE_TTL, commit=True, key=CACHE_KEY_INTF)
							RESULTS["interfaces"] = [(0, "Okay")]
							logger_debug(6, "Cached %d interfaces, %d with mgmt IP" % (len(all_interfaces), elements_with_mgmt_ip))

						# Third pass: now cache elements with _mgmt_ip included
						# Cache individual elements
						for ele_dict in element_list:
							element_id = str(ele_dict["id"])
							cache_key = "%s+%s" % (CACHE_KEY_DEVS, element_id)
							CACHE_PTR.cache_result(ele_dict, ttl=CACHE_TTL, commit=True, key=cache_key)

						# Cache site-level device lists (now includes _mgmt_ip)
						for site_id, list_vals in post_res.iteritems():
							cache_key = "%s+%s+DEVICES" % (CACHE_KEY_SITE, site_id)
							CACHE_PTR.cache_result(list_vals, ttl=CACHE_TTL, commit=True, key=cache_key)

						logger_debug(6, "Cached devices for %d sites with _mgmt_ip" % len(post_res))

						logger_debug(7, "Fetching WAN interfaces at site level")
						all_wan_interfaces = []
						sites_with_wan = 0
						site_data = CACHE_PTR.get(CACHE_KEY_SITE)
						if isinstance(site_data, dict) and "items" in site_data:
							for site_dict in site_data["items"]:
								site_id = str(site_dict["id"])
								wan_path = "/sdwan/v%s/api/sites/%s/waninterfaces" % (WANINTERFACE_VERSION, site_id)
								wan_data = fetch_api_data(wan_path)
								if isinstance(wan_data, dict) and "items" in wan_data:
									site_interfaces = wan_data["items"]
									for intf in site_interfaces:
										intf["_site_id"] = site_id
										all_wan_interfaces.append(intf)
									if site_interfaces:
										wan_site_cache_key = "%s+%s" % (CACHE_KEY_WAN, site_id)
										CACHE_PTR.cache_result(site_interfaces, ttl=CACHE_TTL, commit=True, key=wan_site_cache_key)
										sites_with_wan += 1
						if all_wan_interfaces:
							CACHE_PTR.cache_result(all_wan_interfaces, ttl=CACHE_TTL, commit=True, key=CACHE_KEY_WAN)
							RESULTS["waninterfaces"] = [(0, "Okay")]
							logger_debug(6, "Cached %d WAN interfaces for %d sites" % (len(all_wan_interfaces), sites_with_wan))

					now_time = time.time()
					sta_time = now_time - EVENT_SECONDS
					end_iso = datetime.fromtimestamp(now_time).isoformat()
					sta_iso = datetime.fromtimestamp(sta_time).isoformat()
					payload = """{"severity":["critical","major","minor"],"query":{"type":["alarm"]},"_offset":null,"view":{"summary":false},"start_time":"%s","end_time":"%s"}""" % (sta_iso, end_iso)
					ret_data = fetch_api_data("/sdwan/v%s/api/events/query" % (EVENTS_VERSION), json.loads(payload))
					if isinstance(ret_data, dict) and "items" in ret_data:
						RESULTS["events"] = [(0, "Okay")]
						CACHE_PTR.cache_result(ret_data["items"], ttl=CACHE_TTL, commit=True, key=CACHE_KEY_EVET)
						logger_debug(7, "Events cached: %d items" % (len(ret_data["items"])))

				result_handler.update(RESULTS)
		except Exception, e:
			logger_debug(2, "Exception Caught in Snippet", str(e))
		except:
			logger_debug(3, "Unknown Exception in Snippet")
	else:
		logger_debug(3, "Credential Missing Username or Password")
else:
	logger_debug(3, "Wrong Credential Type")

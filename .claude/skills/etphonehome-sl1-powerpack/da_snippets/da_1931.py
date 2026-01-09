import base64

import requests

# Palo Alto: Prisma Cloud API Credential Check
# Version: 2.1.1
#
# Purpose: Validates OAuth2 credentials before data collection.
# Original: Used CloudGenix API key authentication.
# Changed: Migrated to Prisma SASE OAuth2 with service account credentials.

SNIPPET_NAME = "PAN Prisma Cloud API Credential Check | v 2.1.1"
RESULTS = {}

# API base URL for Prisma SASE
API_BASE_URL = "https://api.sase.paloaltonetworks.com"


def var_dump(val):
    import pprint

    pp = pprint.PrettyPrinter(indent=0)
    pp.pprint(val)


def logger_debug(sev_level=6, log_message=None, log_var=None):
    log_sev_types = {
        0: "EMERGENCY",
        1: "ALERT",
        2: "CRITICAL",
        3: "ERROR",
        4: "WARNING",
        5: "NOTICE",
        6: "INFORMATION",
        7: "DEBUG",
    }
    if log_message is not None and log_var is not None:
        self.logger.ui_debug(
            "[%s] %s %s" % (log_sev_types[sev_level], str(log_message), str(log_var))
        )
    elif log_message is not None:
        self.logger.ui_debug("[%s] %s" % (log_sev_types[sev_level], str(log_message)))


def get_http_code_desc(httpcode):
    http_codes = dict()
    http_codes["0"] = "Connection Refused"
    http_codes["1"] = "Access Denied"
    http_codes["2"] = "Operation Timed Out"
    http_codes["100"] = "Continue"
    http_codes["200"] = "OK"
    http_codes["201"] = "Created"
    http_codes["400"] = "Bad Request"
    http_codes["401"] = "Unauthorized"
    http_codes["403"] = "Forbidden"
    http_codes["404"] = "Not Found"
    http_codes["429"] = "Too Many Requests"
    http_codes["500"] = "Internal Server Error"
    http_codes["502"] = "Bad Gateway"
    http_codes["503"] = "Service Unavailable"
    if str(httpcode) in http_codes:
        return http_codes[str(httpcode)]
    else:
        return "Unknown"


def extract_tsg_id(username):
    """Extract TSG ID from service account username.
    Format: SA-xxx@{TSG_ID}.iam.panserviceaccount.com
    """
    if "@" in username:
        domain_part = username.split("@")[1]
        if ".iam.panserviceaccount.com" in domain_part:
            return domain_part.split(".")[0]
    return None


def get_oauth_token(auth_url, username, password, tsg_id, timeout):
    """Get OAuth2 token from Prisma SASE auth endpoint."""
    token_url = "%s/auth/v1/oauth2/access_token" % (auth_url.rstrip("/"))
    auth_header = base64.b64encode(("%s:%s" % (username, password)).encode("utf-8")).decode("utf-8")

    headers = {
        "Authorization": "Basic %s" % (auth_header),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    post_data = "grant_type=client_credentials&scope=tsg_id:%s" % (tsg_id)

    response = requests.post(
        token_url, headers=headers, data=post_data, verify=True, timeout=timeout
    )
    return response


def init_session_profile(token, timeout):
    """Initialize session by calling profile endpoint - REQUIRED before other API calls."""
    headers = {"Authorization": "Bearer %s" % (token)}
    response = requests.get(
        "%s/sdwan/v2.1/api/profile" % (API_BASE_URL), headers=headers, verify=True, timeout=timeout
    )
    return response


##Main:
logger_debug(7, SNIPPET_NAME)

if self.cred_details["cred_type"] == 3:
    # Get credentials - using cred_user and cred_pwd for OAuth2 service account
    username = self.cred_details.get("cred_user")
    password = self.cred_details.get("cred_pwd")

    # Get auth URL from credential's curl_url field
    auth_url = self.cred_details.get("curl_url", "https://auth.apps.paloaltonetworks.com")
    if auth_url and not auth_url.startswith("http"):
        auth_url = "https://%s" % (auth_url)

    if username is not None and password is not None:
        try:
            timeout = (
                int(self.cred_details["cred_timeout"] / 1000)
                if self.cred_details.get("cred_timeout")
                else 30
            )

            # Extract TSG ID from username
            tsg_id = extract_tsg_id(username)
            if tsg_id is None:
                logger_debug(3, "Could not extract TSG ID from username", username)
                RESULTS["http-code"] = [(0, 400)]
                RESULTS["http-descr"] = [(0, "Invalid username format - cannot extract TSG ID")]
                result_handler.update(RESULTS)
            else:
                logger_debug(7, "Extracted TSG ID", tsg_id)

                # Step 1: Get OAuth token
                logger_debug(7, "Requesting OAuth token from", auth_url)
                token_response = get_oauth_token(auth_url, username, password, tsg_id, timeout)

                if token_response.status_code == 200:
                    token_data = token_response.json()
                    access_token = token_data.get("access_token")
                    logger_debug(7, "OAuth token obtained successfully")

                    # Step 2: Initialize session with profile call (REQUIRED)
                    logger_debug(7, "Initializing session with profile call")
                    profile_response = init_session_profile(access_token, timeout)

                    if profile_response.status_code == 200:
                        profile_data = profile_response.json()
                        tenant_id = profile_data.get("tenant_id", tsg_id)
                        logger_debug(7, "Profile call successful, tenant_id", tenant_id)

                        RESULTS["http-code"] = [(0, 200)]
                        RESULTS["http-descr"] = [(0, "OK - Tenant: %s" % (tenant_id))]
                    else:
                        logger_debug(3, "Profile call failed", profile_response.status_code)
                        RESULTS["http-code"] = [(0, profile_response.status_code)]
                        RESULTS["http-descr"] = [
                            (
                                0,
                                "Profile Init Failed: %s"
                                % (get_http_code_desc(profile_response.status_code)),
                            )
                        ]
                else:
                    logger_debug(3, "OAuth token request failed", token_response.status_code)
                    RESULTS["http-code"] = [(0, token_response.status_code)]
                    RESULTS["http-descr"] = [
                        (
                            0,
                            "Token Auth Failed: %s"
                            % (get_http_code_desc(token_response.status_code)),
                        )
                    ]

                result_handler.update(RESULTS)

        except requests.exceptions.Timeout:
            logger_debug(2, "Request timed out")
            RESULTS["http-code"] = [(0, 2)]
            RESULTS["http-descr"] = [(0, get_http_code_desc(2))]
            result_handler.update(RESULTS)
        except requests.exceptions.ConnectionError:
            logger_debug(2, "Connection refused")
            RESULTS["http-code"] = [(0, 0)]
            RESULTS["http-descr"] = [(0, get_http_code_desc(0))]
            result_handler.update(RESULTS)
        except Exception as e:
            logger_debug(2, "Exception Caught in Snippet", str(e))
            RESULTS["http-code"] = [(0, 500)]
            RESULTS["http-descr"] = [(0, "Exception: %s" % (str(e)[:100]))]
            result_handler.update(RESULTS)
        except:
            logger_debug(3, "Unknown Exception in Snippet")
            RESULTS["http-code"] = [(0, 500)]
            RESULTS["http-descr"] = [(0, "Unknown Exception")]
            result_handler.update(RESULTS)
    else:
        logger_debug(3, "Credential Missing Username or Password")
        RESULTS["http-code"] = [(0, 401)]
        RESULTS["http-descr"] = [(0, "Missing Username or Password")]
        result_handler.update(RESULTS)
else:
    logger_debug(
        3, "Wrong Credential Type Aligned to This Dynamic Application, Requires SOAP/XML Credential"
    )
    RESULTS["http-code"] = [(0, 400)]
    RESULTS["http-descr"] = [(0, "Wrong Credential Type - Requires SOAP/XML (type 3)")]
    result_handler.update(RESULTS)

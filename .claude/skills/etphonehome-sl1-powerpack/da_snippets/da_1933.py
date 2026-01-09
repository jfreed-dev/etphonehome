import silo_common.snippets as em7_snippets

# Palo Alto: Prisma Cloud Site Discovery
# Version: 2.1
#
# Purpose: Discovers Prisma SD-WAN sites for component device creation.
# Data Source: Reads from API Collector cache (PRISMACLOUD+SITES).

SNIPPET_NAME     = "Palo Alto: Prisma Cloud Sites | v 2.0.1"
CACHE_KEY_SITE   = "PRISMACLOUD+SITES+%s" % (self.did)

def var_dump(val):
    import pprint
    pp = pprint.PrettyPrinter(indent=0)
    pp.pprint(val)

def logger_debug(s=7, m=None, v=None):
    sevs = {
            0:'EMERGENCY',
            1:'ALERT',
            2:'CRITICAL',
            3:'ERROR',
            4:'WARNING',
            5:'NOTICE',
            6:'INFORMATION',
            7:'DEBUG'
    }
    if m is not None \\
    and v is not None:
        self.logger.ui_debug("[%s] %s %s" % (sevs[s], str(m), str(v)))
    elif m is not None:
        self.logger.ui_debug("[%s] %s" % (sevs[s], str(m)))

##main:
logger_debug(7, SNIPPET_NAME)
##
try:
    cache_data = em7_snippets.cache_api(self).get(CACHE_KEY_SITE)
    ##
    if isinstance(cache_data, dict) \\
    and 'items' in cache_data \\
    and len(cache_data['items']) > 0:
        for site_dict in cache_data['items']:
            if 'id' in site_dict \\
            and 'name' in site_dict:
                ##the index.
                site_id = str(site_dict['id'])
                logger_debug(7, "Found %s [%s]" % (site_dict['name'], site_id))
                ##
                for group, oid_group in self.oids.iteritems():
                    for obj_id, oid_detail in oid_group.iteritems():
                        oid = str(oid_detail['oid'])
                        val = 'n/a'
                        ##dot walking
                        if '.' in oid:
                            oid_parts = oid.split('.')
                            if len(oid_parts) == 2 \\
                            and oid_parts[0] in site_dict \\
                            and isinstance(site_dict[oid_parts[0]], dict) \\
                            and oid_parts[1] in site_dict[oid_parts[0]]:
                                val = str(site_dict[oid_parts[0]][oid_parts[1]])
                        ##availability ro boolean
                        elif oid == 'avail':
                            val = 0
                            if 'admin_state' in site_dict \\
                            and str(site_dict['admin_state']) == 'active':
                                val = 1
                        ##everything else.
                        elif oid in site_dict:
                            val = str(site_dict[oid])
                        oid_detail["result"].append((site_id, val))
                        ##
            else:
                logger_debug(3, 'ID or Name Missing from Payload')
    else:
        logger_debug(3, 'Cache not Found: %s' % (CACHE_KEY_SITE))
except Exception as e:
    logger_debug(3, 'Exception Caught: %s' % (str(e)))
except:
    logger_debug(3, 'Unknown Exception')

import silo_common.snippets as em7_snippets

# Palo Alto: Prisma Cloud Devices
# Version: 2.0
#
# Purpose: Discovers ION devices under each site for component device creation.
# Data Source: Reads from API Collector cache (PRISMACLOUD+DEVICES).

SNIPPET_NAME     = "Palo Alto: Prisma Cloud Devices | v 2.0"
CACHE_KEY_DEVS   = "PRISMACLOUD+SITES+%s+%s+DEVICES" % (self.root_did, self.comp_unique_id)

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
	cache_data = em7_snippets.cache_api(self).get(CACHE_KEY_DEVS)
	##
	if isinstance(cache_data, list) \\
	and len(cache_data) > 0:
		for dev_dict in cache_data:
			if 'id' in dev_dict \\
			and 'name' in dev_dict:
				dev_id = str(dev_dict['id'])
				logger_debug(7, "Found %s [%s]" % (dev_dict['name'], dev_id))
				##
				for group, oid_group in self.oids.iteritems():
					for obj_id, oid_detail in oid_group.iteritems():
						oid = str(oid_detail['oid'])
						val = 'n/a'
						##discovery trigger - return 1 for each device
						if oid == 'l1':
							val = 1
						##dot walking for nested fields
						elif '.' in oid:
							oid_parts = oid.split('.')
							if len(oid_parts) == 2 \\
							and oid_parts[0] in dev_dict \\
							and isinstance(dev_dict[oid_parts[0]], dict) \\
							and oid_parts[1] in dev_dict[oid_parts[0]]:
								val = str(dev_dict[oid_parts[0]][oid_parts[1]])
						##boolean fields
						elif oid == 'connected':
							val = 'Connected' if dev_dict.get('connected', False) else 'Disconnected'
						##everything else
						elif oid in dev_dict:
							val = str(dev_dict[oid])
						oid_detail["result"].append((dev_id, val))
						##
			else:
				logger_debug(3, 'ID or Name Missing from Payload')
	else:
		logger_debug(3, 'Cache not Found: %s' % (CACHE_KEY_DEVS))
except Exception as e:
	logger_debug(3, 'Exception Caught: %s' % (str(e)))
except:
	logger_debug(3, 'Unknown Exception')

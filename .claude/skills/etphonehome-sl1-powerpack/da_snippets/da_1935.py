import silo_common.snippets as em7_snippets

# Palo Alto: Prisma Device Asset
# Version: 2.0
#
# Purpose: Collects asset information (model, serial, software) for ION devices.
# Data Source: Reads from API Collector cache.

SNIPPET_NAME    = "Palo Alto: Prisma Devices Asset | v 2.0"
CACHE_KEY       = "PRISMACLOUD+DEVICES+%s+%s" % (self.root_did, self.comp_unique_id)

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
	cache_data = em7_snippets.cache_api(self).get(CACHE_KEY)
	##
	if isinstance(cache_data, dict) \\
	and 'id' in cache_data:
		for group, oid_group in self.oids.iteritems():
			for obj_id, oid_detail in oid_group.iteritems():
				oid = str(oid_detail['oid'])
				val = 'n/a'
				if '.' in oid:
					oid_parts = oid.split('.')
					if len(oid_parts) == 2 \\
					and oid_parts[0] in cache_data \\
					and isinstance(cache_data[oid_parts[0]], dict) \\
					and oid_parts[1] in cache_data[oid_parts[0]]:
						val = str(cache_data[oid_parts[0]][oid_parts[1]])
				elif oid in cache_data:
					if isinstance(cache_data[oid], list):
						val = ', '.join(cache_data[oid])
					elif 'model_name' in str(oid):
						val = str(cache_data[oid]).upper()
					else:
						val = str(cache_data[oid])
				oid_detail["result"].append((0, val))

			else:
				logger_debug(3, 'ID or Name Missing from Payload')
	else:
		logger_debug(3, 'Cache not Found: %s' % (CACHE_KEY))
except Exception as e:
	logger_debug(3, 'Exception Caught: %s' % (str(e)))
except:
	logger_debug(3, 'Unknown Exception')
#####

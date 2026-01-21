#!/usr/bin/env python
"""
Event Policy Standardization Script for Prisma SD-WAN PowerPack

This script standardizes all Prisma event policies on SL1 to use consistent
naming and ensures all policies have proper descriptions.

Usage:
    python prisma_event_policy_update.py              # Apply updates
    python prisma_event_policy_update.py --dry-run    # Preview changes only
    python prisma_event_policy_update.py --backup-only # Create backup only

Requirements:
    - MySQLdb (pip install mysqlclient)
    - Run on SL1 server or host with database access

Applied: 2026-01-21 on sl1dev2 (108.174.225.156)
"""

import datetime
import json

import MySQLdb

# Connection details for SL1
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 7706,
    "user": "clientdbuser",
    "passwd": "em7admin",  # pragma: allowlist secret
    "db": "master",
    "charset": "utf8",
}

# Prisma PowerPack GUID
PPGUID = "21D9648A7D551E5F84294B72C86000C9"  # pragma: allowlist secret

# Policy updates: id -> (new_name, new_description)
# Descriptions use pcause field
POLICY_UPDATES = {
    # Policies needing name + description
    8031: (
        "Palo Alto Prisma Cloud: Major Severity Alert",
        """API Code: Various
Event Title: Major Severity Alert

Event Body
This is a catch-all policy for Prisma SD-WAN events classified as major severity that don't match a more specific policy.

Troubleshooting Steps
Review the alert message for specific details about the event type and affected component.""",
    ),
    8032: (
        "Palo Alto Prisma Cloud: Minor Severity Alert",
        """API Code: Various
Event Title: Minor Severity Alert

Event Body
This is a catch-all policy for Prisma SD-WAN events classified as minor severity that don't match a more specific policy.

Troubleshooting Steps
Review the alert message for specific details. Minor events typically don't require immediate action.""",
    ),
    8033: (
        "Palo Alto Prisma Cloud: Critical Severity Alert",
        """API Code: Various
Event Title: Critical Severity Alert

Event Body
This is a catch-all policy for Prisma SD-WAN events classified as critical severity that don't match a more specific policy.

Troubleshooting Steps
Immediate attention required. Review the alert message and escalate to network operations.""",
    ),
    8049: (
        "Palo Alto Prisma Cloud: Alert Cleared",
        """API Code: Various
Event Title: Alert Cleared

Event Body
Indicates that a previously raised Prisma SD-WAN alert has been cleared automatically or manually.

Troubleshooting Steps
No action required. Verify the underlying issue has been resolved.""",
    ),
    8057: (
        "Palo Alto Prisma Cloud: Device HW Interface Down",
        None,  # Already has description, just standardize name
    ),
    8058: (
        "Palo Alto Prisma Cloud: Device HW Interface Down (Cleared)",
        None,  # Already has description, just standardize name
    ),
    8060: (
        "Palo Alto Prisma Cloud: Carrier Ticket Required",
        """API Code: NETWORK_DIRECTINTERNET_DOWN, NETWORK_ANYNETLINK_DOWN
Event Title: Carrier Ticket Required

Event Body
An internet circuit or WAN link is down and requires opening a trouble ticket with the service provider. The alert includes circuit details (provider name, bandwidth) when available.

Troubleshooting Steps
1. Verify circuit status in Prisma SD-WAN console
2. Contact the carrier/ISP listed in the alert
3. Open a trouble ticket referencing the circuit details
4. Monitor for automatic recovery""",
    ),
    8061: (
        "Palo Alto Prisma Cloud: Bandwidth Upgrade Required",
        """API Code: NETWORK_BANDWIDTH_LIMIT
Event Title: Bandwidth Upgrade Required

Event Body
A WAN circuit has reached its bandwidth capacity threshold, indicating the need for a bandwidth upgrade to maintain performance.

Troubleshooting Steps
1. Review bandwidth utilization trends in Prisma SD-WAN
2. Identify high-bandwidth applications or users
3. Consider QoS policy adjustments
4. Plan bandwidth upgrade with carrier if utilization remains high""",
    ),
    8062: (
        "Palo Alto Prisma Cloud: Bandwidth Review",
        """API Code: NETWORK_BANDWIDTH_WARNING
Event Title: Bandwidth Review

Event Body
A WAN circuit is approaching its bandwidth capacity threshold. This is an early warning to review bandwidth utilization before it becomes critical.

Troubleshooting Steps
1. Monitor bandwidth trends over the next 24-48 hours
2. Review application traffic patterns
3. Consider proactive bandwidth upgrade if growth trend continues""",
    ),
    8063: (
        "Palo Alto Prisma Cloud: Site Unreachable",
        """API Code: SITE_CONNECTIVITY_DOWN
Event Title: Site Unreachable

Event Body
All connectivity to a branch site has been lost. This is a critical event indicating complete site isolation from the SD-WAN fabric.

Troubleshooting Steps
1. Check all WAN circuit status for the site
2. Verify ION device power and connectivity
3. Contact on-site personnel if available
4. Check for regional ISP outages
5. If HUB site, assess impact on dependent branch sites""",
    ),
    8064: (
        "Palo Alto Prisma Cloud: Site Connectivity Degraded",
        """API Code: SITE_CONNECTIVITY_DEGRADED
Event Title: Site Connectivity Degraded

Event Body
Partial connectivity issues detected at a site. One or more WAN links may be down or experiencing problems while other paths remain operational.

Troubleshooting Steps
1. Identify which WAN circuits are affected
2. Check circuit status with carriers
3. Verify failover paths are operational
4. Monitor application performance""",
    ),
    8065: (
        "Palo Alto Prisma Cloud: BGP Peer Down",
        """API Code: PEERING_BGP_DOWN
Event Title: BGP Peer Down

Event Body
A BGP peering session has gone down, affecting routing between the ION device and its BGP neighbor.

Troubleshooting Steps
1. Verify BGP neighbor reachability
2. Check BGP configuration on both sides
3. Review interface status for the peering link
4. Check for route table changes
5. Contact peer administrator if external peer""",
    ),
    8066: (
        "Palo Alto Prisma Cloud: Investigation Required",
        """API Code: Various
Event Title: Investigation Required

Event Body
An event has been detected that requires investigation but doesn't fall into a specific category. Review the detailed alert message for context.

Troubleshooting Steps
1. Review the full alert message for event details
2. Check Prisma SD-WAN console for additional context
3. Correlate with other recent events
4. Escalate to network engineering if needed""",
    ),
    8067: (
        "Palo Alto Prisma Cloud: Informational",
        """API Code: Various
Event Title: Informational Event

Event Body
An informational event has been logged. These events are typically for awareness and don't require immediate action.

Troubleshooting Steps
No immediate action required. Review for awareness of system changes or status.""",
    ),
    8068: (
        "Palo Alto Prisma Cloud: Generic Alert",
        """API Code: Various
Event Title: Generic Alert

Event Body
A Prisma SD-WAN event was processed that doesn't match a specific event category. The alert message contains details about the actual event.

Troubleshooting Steps
Review the alert message for specific details and take appropriate action based on the event type.""",
    ),
    8069: (
        "Palo Alto Prisma Cloud: Interface Error Rate",
        """API Code: DEVICEHW_INTERFACE_ERRORS
Event Title: Interface Error Rate

Event Body
An interface on an ION device is experiencing elevated error rates (CRC errors, collisions, drops). This may indicate physical layer issues or network congestion.

Troubleshooting Steps
1. Check interface statistics for error types
2. Inspect physical cabling and connections
3. Test port/cable replacement if errors persist
4. Check for network congestion or duplex mismatch""",
    ),
    8070: (
        "Palo Alto Prisma Cloud: API Throttling",
        """API Code: API_RATE_LIMIT
Event Title: API Throttling Detected

Event Body
The Prisma SD-WAN API is being rate-limited due to excessive API calls. This may affect data collection completeness.

Troubleshooting Steps
1. Review API collection frequency settings
2. Check for runaway collection processes
3. Adjust polling intervals if needed
4. Contact Palo Alto support if throttling persists""",
    ),
    8071: ("Palo Alto Prisma Cloud: General Alert", None),  # Name only, no description update
    # Policies needing name standardization only (already have descriptions)
    8034: ("Palo Alto Prisma Cloud: Remote Office Internet Circuit Down", None),
    8035: ("Palo Alto Prisma Cloud: Network Direct Internet Down", None),
    8036: ("Palo Alto Prisma Cloud: Network Private WAN Degraded (Cleared)", None),
    8037: ("Palo Alto Prisma Cloud: Network Private WAN Degraded", None),
    8038: ("Palo Alto Prisma Cloud: Network Private WAN Unreachable", None),
    8039: ("Palo Alto Prisma Cloud: Network Direct Private Down (Cleared)", None),
    8040: ("Palo Alto Prisma Cloud: Network Direct Private Down", None),
    8041: ("Palo Alto Prisma Cloud: Site Connectivity Down", None),
    8042: ("Palo Alto Prisma Cloud: Peering BGP Down", None),
    8043: ("Palo Alto Prisma Cloud: Device HW Power Lost", None),
    8044: ("Palo Alto Prisma Cloud: Device HW Power Lost (Cleared)", None),
    8045: ("Palo Alto Prisma Cloud: Device SW Critical Process Restart", None),
    8046: ("Palo Alto Prisma Cloud: Device SW Critical Process Stopped", None),
    8047: ("Palo Alto Prisma Cloud: Device SW System Boot", None),
    8048: ("Palo Alto Prisma Cloud: Peering BGP Down (Cleared)", None),
    8050: ("Palo Alto Prisma Cloud: Network Private WAN Unreachable (Cleared)", None),
    8051: ("Palo Alto Prisma Cloud: Device SW System Boot (Cleared)", None),
    8052: ("Palo Alto Prisma Cloud: Device SW Critical Process Stopped (Cleared)", None),
    8053: ("Palo Alto Prisma Cloud: Device SW Critical Process Restart (Cleared)", None),
    8054: ("Palo Alto Prisma Cloud: Network Direct Internet Down (Cleared)", None),
    8055: ("Palo Alto Prisma Cloud: Remote Office Internet Circuit Down (Cleared)", None),
    8056: ("Palo Alto Prisma Cloud: Site Connectivity Down (Cleared)", None),
    8059: ("Palo Alto Prisma Cloud: Peering BGP Down Flapping Detected", None),
}


def backup_policies(cursor):
    """Create a backup of current policy state."""
    print("=" * 60)
    print("BACKUP: Current Policy State")
    print("=" * 60)

    cursor.execute(
        """
        SELECT id, ename, pcause, eseverity
        FROM policies_events
        WHERE ppguid = %s
        ORDER BY id
    """,
        (PPGUID,),
    )

    policies = cursor.fetchall()
    backup_data = []

    for policy in policies:
        pid, name, desc, severity = policy
        backup_data.append(
            {"id": pid, "ename": name, "pcause": desc if desc else "", "eseverity": severity}
        )
        print("ID: %d | Name: %s" % (pid, name[:60] if name else "NULL"))

    print("\nTotal policies: %d" % len(policies))

    # Save backup to JSON
    backup_filename = "/tmp/policies_backup_%s.json" % datetime.datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )
    with open(backup_filename, "w") as f:
        json.dump(backup_data, f, indent=2)
    print("Backup saved to: %s" % backup_filename)

    return backup_data


def update_policies(cursor, dry_run=False):
    """Update policy names and descriptions."""
    print("\n" + "=" * 60)
    print("UPDATING POLICIES" + (" (DRY RUN)" if dry_run else ""))
    print("=" * 60)

    updated_count = 0
    skipped_count = 0

    for policy_id, (new_name, new_desc) in sorted(POLICY_UPDATES.items()):
        # Get current values
        cursor.execute(
            """
            SELECT ename, pcause FROM policies_events WHERE id = %s
        """,
            (policy_id,),
        )

        result = cursor.fetchone()
        if not result:
            print("SKIP ID %d: Not found in database" % policy_id)
            skipped_count += 1
            continue

        current_name, current_desc = result

        # Build update query
        updates = []
        params = []

        if new_name and current_name != new_name:
            updates.append("ename = %s")
            params.append(new_name)

        if new_desc is not None and current_desc != new_desc:
            updates.append("pcause = %s")
            params.append(new_desc)

        if not updates:
            print("SKIP ID %d: No changes needed" % policy_id)
            skipped_count += 1
            continue

        # Execute update
        if not dry_run:
            query = "UPDATE policies_events SET " + ", ".join(updates) + " WHERE id = %s"
            params.append(policy_id)
            cursor.execute(query, params)

        print("UPDATE ID %d:" % policy_id)
        if new_name and current_name != new_name:
            print("  Name: '%s' -> '%s'" % (current_name[:40], new_name[:40]))  # noqa: UP031
        if new_desc is not None and current_desc != new_desc:
            print(
                "  Description: %s -> %s chars"  # noqa: UP031
                % (len(current_desc) if current_desc else 0, len(new_desc))
            )

        updated_count += 1

    print("\nUpdated: %d | Skipped: %d" % (updated_count, skipped_count))
    return updated_count


def verify_updates(cursor):
    """Verify all policies follow the standard format."""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    # Check naming convention
    cursor.execute(
        """
        SELECT id, ename FROM policies_events
        WHERE ppguid = %s
        AND ename NOT LIKE 'Palo Alto Prisma Cloud:%%'
        ORDER BY id
    """,
        (PPGUID,),
    )

    non_standard = cursor.fetchall()
    if non_standard:
        print("WARNING: %d policies don't follow naming convention:" % len(non_standard))
        for pid, name in non_standard:
            print("  ID %d: %s" % (pid, name))
    else:
        print("OK: All policies follow 'Palo Alto Prisma Cloud:' naming convention")

    # Check for missing descriptions
    cursor.execute(
        """
        SELECT id, ename FROM policies_events
        WHERE ppguid = %s
        AND (pcause IS NULL OR pcause = '')
        ORDER BY id
    """,
        (PPGUID,),
    )

    no_desc = cursor.fetchall()
    if no_desc:
        print("WARNING: %d policies have no description:" % len(no_desc))
        for pid, name in no_desc:
            print("  ID %d: %s" % (pid, name))
    else:
        print("OK: All policies have descriptions")

    # Summary
    cursor.execute(
        """
        SELECT COUNT(*) FROM policies_events WHERE ppguid = %s
    """,
        (PPGUID,),
    )
    total = cursor.fetchone()[0]
    print("\nTotal policies in PowerPack: %d" % total)

    return len(non_standard) == 0 and len(no_desc) == 0


def main():
    import sys

    dry_run = "--dry-run" in sys.argv
    backup_only = "--backup-only" in sys.argv

    print("Connecting to database...")
    db = MySQLdb.connect(**DB_CONFIG)
    cursor = db.cursor()

    try:
        # Always backup first
        backup_policies(cursor)

        if backup_only:
            print("\nBackup complete. Exiting (--backup-only mode)")
            return

        # Update policies
        updated = update_policies(cursor, dry_run=dry_run)

        if not dry_run and updated > 0:
            db.commit()
            print("\nChanges committed to database")
        elif dry_run:
            print("\nDry run - no changes made")

        # Verify
        verify_updates(cursor)

    finally:
        cursor.close()
        db.close()


if __name__ == "__main__":
    main()

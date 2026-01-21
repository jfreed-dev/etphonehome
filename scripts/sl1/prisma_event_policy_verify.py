#!/usr/bin/env python
"""
Verification script for Prisma SD-WAN event policies on SL1.

Checks that all policies in the Prisma PowerPack:
- Follow the naming convention: "Palo Alto Prisma Cloud: [Event Name]"
- Have descriptions populated

Usage:
    python prisma_event_policy_verify.py

Requirements:
    - MySQLdb (pip install mysqlclient)
    - Run on SL1 server or host with database access
"""

import MySQLdb

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 7706,
    "user": "clientdbuser",
    "passwd": "em7admin",  # pragma: allowlist secret
    "db": "master",
    "charset": "utf8",
}

PPGUID = "21D9648A7D551E5F84294B72C86000C9"  # pragma: allowlist secret


def main():
    print("Connecting to database...")
    db = MySQLdb.connect(**DB_CONFIG)
    cursor = db.cursor()

    try:
        print("=" * 70)
        print("FINAL VERIFICATION - Prisma Event Policies")
        print("=" * 70)

        # Check all policies follow naming convention
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
            print("\nFAIL: %d policies don't follow naming convention:" % len(non_standard))
            for pid, name in non_standard:
                print("  ID %d: %s" % (pid, name))
        else:
            print("\nPASS: All policies follow 'Palo Alto Prisma Cloud:' naming convention")

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
            print("\nFAIL: %d policies have no description:" % len(no_desc))
            for pid, name in no_desc:
                print("  ID %d: %s" % (pid, name))
        else:
            print("PASS: All policies have descriptions")

        # Summary of all policies
        print("\n" + "=" * 70)
        print("ALL POLICIES (ID | Severity | Name)")
        print("=" * 70)
        cursor.execute(
            """
            SELECT id, ename, eseverity,
                   CASE WHEN pcause IS NULL OR pcause = '' THEN 'NO' ELSE 'YES' END as has_desc
            FROM policies_events
            WHERE ppguid = %s
            ORDER BY id
        """,
            (PPGUID,),
        )

        for row in cursor.fetchall():
            pid, name, sev, has_desc = row
            sev_map = {0: "Healthy", 1: "Notice", 2: "Minor", 3: "Major", 4: "Critical"}
            sev_str = sev_map.get(sev, str(sev))
            desc_str = "[DESC]" if has_desc == "YES" else "[NO DESC]"
            print("%4d | %-8s | %s %s" % (pid, sev_str, name[:50], desc_str))

        # Final count
        cursor.execute(
            """
            SELECT COUNT(*) FROM policies_events WHERE ppguid = %s
        """,
            (PPGUID,),
        )
        total = cursor.fetchone()[0]

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print("Total policies: %d" % total)
        print("Non-standard names: %d" % len(non_standard))
        print("Missing descriptions: %d" % len(no_desc))

        if len(non_standard) == 0 and len(no_desc) == 0:
            print("\nSTATUS: ALL POLICIES STANDARDIZED SUCCESSFULLY")
        else:
            print("\nSTATUS: ISSUES REMAIN")

    finally:
        cursor.close()
        db.close()


if __name__ == "__main__":
    main()

# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for ET Phone Home client.

Build with:
    pyinstaller build/pyinstaller/phonehome.spec
"""

import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(SPECPATH).parent.parent

block_cipher = None

# Hidden imports required for paramiko and cryptography
hidden_imports = [
    # Paramiko
    'paramiko',
    'paramiko.transport',
    'paramiko.channel',
    'paramiko.sftp',
    'paramiko.sftp_client',
    'paramiko.ssh_exception',
    'paramiko.ed25519key',
    'paramiko.rsakey',
    'paramiko.ecdsakey',
    'paramiko.dsskey',

    # Cryptography - required backends
    'cryptography',
    'cryptography.hazmat.backends',
    'cryptography.hazmat.backends.openssl',
    'cryptography.hazmat.bindings._rust',
    'cryptography.hazmat.primitives.asymmetric.ed25519',
    'cryptography.hazmat.primitives.asymmetric.rsa',
    'cryptography.hazmat.primitives.asymmetric.ec',
    'cryptography.hazmat.primitives.ciphers',
    'cryptography.hazmat.primitives.kdf',
    'cryptography.hazmat.primitives.serialization',

    # cffi (used by cryptography)
    'cffi',
    '_cffi_backend',

    # Other dependencies
    'bcrypt',
    'nacl',
    'nacl.bindings',
    'yaml',

    # Standard library modules that might be missed
    'logging.handlers',
    'html.parser',
]

# Exclude unnecessary modules to reduce size
excludes = [
    'tkinter',
    '_tkinter',
    'tcl',
    'tk',
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'PIL',
    'cv2',
    'torch',
    'tensorflow',
    'IPython',
    'jupyter',
    'notebook',
    'pytest',
    'unittest',
    'doctest',
    'pdb',
    'lib2to3',
    'xmlrpc',
    'curses',
]

a = Analysis(
    [str(PROJECT_ROOT / 'client' / 'phonehome.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='phonehome',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,   # Strip symbols to reduce size
    upx=False,    # DISABLED: UPX compression triggers many AV false positives
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# WINDOWS SECURITY NOTES:
# 1. AV False Positives: UPX is disabled above. If still flagged, consider:
#    - Submitting to AV vendors for whitelisting
#    - Using the portable archive distribution instead
#    - Code signing with a valid certificate
#
# 2. SmartScreen Warning: Windows will show "Unknown publisher" warning.
#    Fix by signing with a code signing certificate (EV cert removes warning).
#
# 3. Firewall: If port 2222 is blocked, configure server on port 443.
#    SSH over 443 often works as it looks like HTTPS traffic.

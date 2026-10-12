"""Print the AIRFLOW_CONN_SNOWFLAKE_DEFAULT line for .env from an encrypted key.

Usage:
  uv run python -I scripts/snowflake_conn_line.py ~/.snowflake/keys/edgar_13f_airflow.p8 >> .env

The passphrase is read from the terminal and never echoed. The key is checked
against it before anything is printed, so a wrong passphrase writes nothing.
The key goes in base64, which the Snowflake hook decodes when the content is
not PEM; the passphrase goes in the connection's password field, which the
hook uses to decrypt the key.
"""

import base64
import getpass
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization

key_path = Path(sys.argv[1]).expanduser()
pem = key_path.read_bytes()
passphrase = getpass.getpass("key passphrase: ")
if not passphrase:
    sys.exit("an empty passphrase is refused: the key must be encrypted with a real one")
serialization.load_pem_private_key(pem, password=passphrase.encode())

connection = {
    "conn_type": "snowflake",
    "login": "AIRFLOW_SVC",
    "password": passphrase,
    "extra": {
        "account": "JOPUFPW-EDGAR_13F",
        "authenticator": "SNOWFLAKE_JWT",
        "role": "LOADER",
        "warehouse": "EDGAR_WH",
        "database": "EDGAR_13F",
        "private_key_content": base64.b64encode(pem).decode(),
    },
}
print(f"AIRFLOW_CONN_SNOWFLAKE_DEFAULT={json.dumps(connection)}")
print("wrote the line to stdout; check .env", file=sys.stderr)

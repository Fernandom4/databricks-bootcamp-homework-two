"""
One-time setup script: creates the Databricks secret scope. Run this locally (with the Databricks CLI configured) or
from a notebook - never commit the resulting secret value anywhere.

Usage:
    python setup_secrets.py
"""

from databricks.sdk import WorkspaceClient
from databricks.sdk.service import workspace
import getpass

w = WorkspaceClient()

w.secrets.create_scope(scope="Homework_two")
w.secrets.put_secret(
    scope="Homework_two",
    key="lakebase-url",
    string_value=getpass.getpass("Paste your Lakebase URL: "),
)

w.secrets.put_acl(
    scope="Homework_two",
    principal="users",
    permission=workspace.AclPermission.READ,
)

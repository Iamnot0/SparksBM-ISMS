#!/usr/bin/env python3
"""
One-time setup: create the sparksbm realm, client, and user in Keycloak.
Required for ISMS dashboard, agent (list scopes), and Java backend.

Run once after Keycloak is deployed (e.g. on Render):

  KEYCLOAK_URL=https://keycloak-server-5xv3.onrender.com \\
  KEYCLOAK_ADMIN=admin \\
  KEYCLOAK_ADMIN_PASSWORD=admin123 \\
  python create-sparksbm-realm.py

Or with defaults for local Keycloak (http://localhost:8080):
  python create-sparksbm-realm.py
"""

import os
import sys
import json
import requests

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080").rstrip("/")
KEYCLOAK_ADMIN = os.getenv("KEYCLOAK_ADMIN", "admin")
KEYCLOAK_ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin123")
REALM_NAME = os.getenv("KEYCLOAK_REALM", "sparksbm")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "sparksbm")
USER_EMAIL = os.getenv("SPARKSBM_USERNAME", "admin@sparksbm.com")
USER_PASSWORD = os.getenv("SPARKSBM_PASSWORD", "admin123")

# Render free tier can be slow; admin API calls need longer timeout
REQUEST_TIMEOUT = int(os.getenv("KEYCLOAK_REQUEST_TIMEOUT", "90"))


def get_admin_token():
    """Get admin token from master realm."""
    url = f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"
    data = {
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": KEYCLOAK_ADMIN,
        "password": KEYCLOAK_ADMIN_PASSWORD,
    }
    r = requests.post(url, data=data, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()["access_token"]


def realm_exists(token):
    """Check if realm already exists."""
    r = requests.get(
        f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=REQUEST_TIMEOUT,
    )
    return r.status_code == 200


def create_realm(token):
    """Create sparksbm realm."""
    payload = {
        "realm": REALM_NAME,
        "enabled": True,
        "displayName": "SparksBM",
        "sslRequired": "external",
        "registrationAllowed": False,
        "loginWithEmailAllowed": True,
        "duplicateEmailsAllowed": False,
        "resetPasswordAllowed": True,
        "editUsernameAllowed": False,
        "bruteForceProtected": False,
        "accessTokenLifespan": 300,
        "ssoSessionIdleTimeout": 1800,
        "ssoSessionMaxLifespan": 36000,
    }
    r = requests.post(
        f"{KEYCLOAK_URL}/admin/realms",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code in (201, 204):
        print(f"  Realm '{REALM_NAME}' created.")
        return True
    if r.status_code == 409:
        print(f"  Realm '{REALM_NAME}' already exists.")
        return True
    print(f"  Failed to create realm: {r.status_code} {r.text[:200]}")
    return False


def create_client(token):
    """Create sparksbm client with Direct access grants (resource owner password)."""
    payload = {
        "clientId": CLIENT_ID,
        "name": "SparksBM",
        "enabled": True,
        "publicClient": True,
        "directAccessGrantsEnabled": True,
        "standardFlowEnabled": True,
        "implicitFlowEnabled": False,
        "serviceAccountsEnabled": False,
        "protocol": "openid-connect",
        "fullScopeAllowed": True,
        "defaultClientScopes": ["openid", "profile", "email"],
    }
    r = requests.post(
        f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/clients",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code in (201, 204):
        print(f"  Client '{CLIENT_ID}' created (Direct access grants enabled).")
        return True
    if r.status_code == 409:
        print(f"  Client '{CLIENT_ID}' already exists.")
        return True
    print(f"  Failed to create client: {r.status_code} {r.text[:200]}")
    return False


def create_user(token):
    """Create admin user in sparksbm realm."""
    username = USER_EMAIL.split("@")[0]
    # Check if user exists
    r = requests.get(
        f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/users",
        params={"username": username},
        headers={"Authorization": f"Bearer {token}"},
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code == 200 and r.json():
        print(f"  User '{USER_EMAIL}' already exists.")
        user_id = r.json()[0]["id"]
        _set_password(token, user_id)
        return True

    payload = {
        "username": username,
        "email": USER_EMAIL,
        "firstName": "Admin",
        "lastName": "SparksBM",
        "enabled": True,
        "emailVerified": True,
    }
    r = requests.post(
        f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/users",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code not in (201, 204):
        print(f"  Failed to create user: {r.status_code} {r.text[:200]}")
        return False
    # Get user id from list and set password
    r2 = requests.get(
        f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/users",
        params={"username": username},
        headers={"Authorization": f"Bearer {token}"},
        timeout=REQUEST_TIMEOUT,
    )
    if r2.status_code == 200 and r2.json():
        user_id = r2.json()[0]["id"]
        _set_password(token, user_id)
    print(f"  User '{USER_EMAIL}' created and password set.")
    return True


def _set_password(token, user_id):
    r = requests.put(
        f"{KEYCLOAK_URL}/admin/realms/{REALM_NAME}/users/{user_id}/reset-password",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"type": "password", "value": USER_PASSWORD, "temporary": False},
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code not in (200, 204):
        print(f"  Warning: could not set password: {r.status_code}")


def main():
    print("SparksBM Keycloak one-time setup")
    print("  KEYCLOAK_URL:", KEYCLOAK_URL)
    print("  Realm:", REALM_NAME)
    print("  Client:", CLIENT_ID)
    print("  User:", USER_EMAIL)
    print()

    try:
        token = get_admin_token()
        print("  Admin token obtained.")
    except Exception as e:
        print("  Failed to get admin token:", e)
        print("  Check KEYCLOAK_URL, KEYCLOAK_ADMIN, KEYCLOAK_ADMIN_PASSWORD.")
        sys.exit(1)

    if not create_realm(token):
        sys.exit(1)
    if not create_client(token):
        sys.exit(1)
    if not create_user(token):
        sys.exit(1)

    print()
    print("Done. You should now see realm '" + REALM_NAME + "' and client '" + CLIENT_ID + "' in Keycloak.")
    print("  Dashboard OIDC: use realm " + REALM_NAME + ", client " + CLIENT_ID)
    print("  Agent / list scopes: same realm and client; login as " + USER_EMAIL)


if __name__ == "__main__":
    main()

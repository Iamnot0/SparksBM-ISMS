#!/bin/bash

# Update Keycloak Master Realm (Admin Console) with SparksBM Branding
# This updates the admin console login page and branding

KEYCLOAK_URL="http://localhost:8080"
REALM="master"
ADMIN_USER="admin"
ADMIN_PASSWORD="admin123"

echo "🔐 Authenticating with Keycloak Admin..."
TOKEN_RESPONSE=$(curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${ADMIN_USER}" \
  -d "password=${ADMIN_PASSWORD}" \
  -d "grant_type=password" \
  -d "client_id=admin-cli")

if command -v jq &> /dev/null; then
  TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')
else
  TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
fi

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ] || [[ "$TOKEN" == *"error"* ]]; then
  echo "❌ Failed to authenticate. Please check:"
  echo "   1. Keycloak is running (http://localhost:8080)"
  echo "   2. Admin credentials are correct"
  echo "Response: $TOKEN_RESPONSE"
  exit 1
fi

echo "✅ Authenticated successfully"
echo ""

echo "📝 Updating Keycloak Admin Console (master realm) with SparksBM branding..."

# Get current realm config
REALM_CONFIG=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/${REALM}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json")

# Logo HTML with inline SVG (three blue arch shapes + SparksBM text)
LOGO_HTML='<div style="display: flex; align-items: center; gap: 12px; justify-content: center; padding: 8px 0;"><svg width="48" height="48" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><g fill="#1976d2"><path d="M 18 40 L 18 10 C 18 8 19 7 20 7 L 20 40 Z" /><path d="M 8 40 L 8 16 C 8 14 9 13 10 13 L 10 40 Z" /><path d="M 28 40 L 28 16 C 28 14 29 13 30 13 L 30 40 Z" /></g></svg><span style="font-size: 30px; font-weight: 600; color: #1976d2; letter-spacing: 0.5px;">SparksBM</span></div>'

# Update displayNameHtml with logo and set loginTheme to sparksbm (our custom theme)
UPDATED_CONFIG=$(echo "$REALM_CONFIG" | jq --arg logo "$LOGO_HTML" '.displayNameHtml = $logo | .displayName = "SparksBM" | .loginTheme = "sparksbm"')

# Update email settings only if SMTP is configured
if echo "$REALM_CONFIG" | jq -e '.smtpServer.host' > /dev/null 2>&1; then
  UPDATED_CONFIG=$(echo "$UPDATED_CONFIG" | jq '.smtpServer.fromDisplayName = "SparksBM Authentication Server"')
fi

# Send update
RESPONSE=$(curl -s -w "\n%{http_code}" -X PUT "${KEYCLOAK_URL}/admin/realms/${REALM}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "$UPDATED_CONFIG")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" == "204" ]; then
  echo "✅ Keycloak Admin Console (master realm) updated successfully!"
  echo ""
  echo "🎉 Admin Console now displays:"
  echo "   - SparksBM logo (three blue arch shapes)"
  echo "   - SparksBM branding text"
  echo "   - Instead of 'KEYCLOAK'"
  echo ""
  echo "Next steps:"
  echo "  1. Clear browser cache or use incognito mode"
  echo "  2. Visit http://localhost:8080/admin/master/console"
  echo "  3. You should see SparksBM branding on the login page"
else
  echo "❌ Failed to update realm. HTTP Code: $HTTP_CODE"
  echo "Response: $(echo "$RESPONSE" | head -n-1)"
  exit 1
fi

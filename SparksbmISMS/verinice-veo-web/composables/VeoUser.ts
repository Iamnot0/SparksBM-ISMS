/*
 * verinice.veo web
 * Copyright (C) 2022  Jonas Heitmann, jae
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */
import Keycloak from 'keycloak-js';
import type { ComputedRef, Ref } from 'vue';

export interface IVeoUserSettings {
  maxUnits: number;
  maxUsers: number;
}

export interface IVeoUserComposable {
  authenticated: Ref<boolean>;
  initialize: (context: any) => Promise<void>;
  keycloak: Ref<Keycloak | undefined>;
  keycloakInitialized: Ref<boolean>;
  login: (destination?: string) => Promise<void>;
  logout: (destination?: string, queryParameters?: Record<string, any>) => Promise<void>;
  profile: ComputedRef<Record<string, any> | undefined>;
  refreshKeycloakSession: () => Promise<void>;
  roles: ComputedRef<string[]>;
  tablePageSize: Ref<number>;
  token: ComputedRef<string | undefined>;
  userSettings: ComputedRef<IVeoUserSettings>;
}

const keycloak = ref<Keycloak | undefined>(undefined);
const _keycloak = ref<Keycloak | undefined>(undefined);
const keycloakInitializationStarted = ref(false);
const keycloakInitialized = ref(false);
const tablePageSize = ref<number>(25);

export const useVeoUser: () => IVeoUserComposable = () => {
  const initialize = async (context: any) => {
    if (keycloakInitialized.value || keycloakInitializationStarted.value) {
      return;
    }
    keycloakInitializationStarted.value = true;
    keycloak.value = new Keycloak({
      url: context.$config.public.oidcUrl,
      realm: context.$config.public.oidcRealm,
      clientId: context.$config.public.oidcClient
    });

    // Refresh token HAS to be set before calling init
    keycloak.value.onTokenExpired = async () => {
      try {
        await refreshKeycloakSession();
      } catch (e: any) {
        console.error(`VeoUser::initialize_ Automatically refreshing keycloak session failed: ${e.message}`);
        keycloakInitialized.value = false;
        keycloakInitializationStarted.value = false;
        await initialize(context);
      }
    };

    try {
      await keycloak.value.init({
        onLoad: 'check-sso',
        silentCheckSsoRedirectUri: window.location.origin + '/sso',
        checkLoginIframe: false,
        // Render / slow Keycloak: 3rd party cookie check iframe often times out; give it more time
        messageReceiveTimeout: 25000
      });

      if (keycloak.value.authenticated) {
        try {
        await keycloak.value.loadUserProfile();
        } catch (profileError: any) {
          const errorMessage = profileError?.message || profileError?.toString() || 'Unknown error';
          if (profileError?.error === 'invalid_request' || errorMessage.includes('CORS') || errorMessage.includes('account')) {
            console.info(`Profile loading skipped due to CORS (this is expected for account endpoint): ${errorMessage}`);
          } else {
            console.error(`Failed to load user profile: ${errorMessage}`);
          }
        }
      }
    } catch (error: any) {
      keycloakInitializationStarted.value = false;
      const errorMessage = error?.message || error?.toString() || 'Unknown error';
      const errorDetails = error?.error || error?.errorDescription || '';
      
      // Don't throw for login_required errors - these are expected for unauthenticated users
      if (error?.error === 'login_required' || errorMessage.includes('login_required')) {
        console.info('Authentication: User not logged in (login_required) - this is expected');
        keycloakInitialized.value = true; // Mark as initialized even without auth
        return;
      }
      // 3rd party cookie check failed (timeout, 404 on 3p-cookies/step1.html, or Keycloak doesn't expose it) - treat as "not logged in", show login
      const is3pCheckFailure =
        errorMessage.includes('Timeout when waiting for 3rd party check') ||
        errorMessage.includes('3rd party check iframe') ||
        errorMessage.includes('3p-cookies') ||
        errorMessage.includes('step1.html') ||
        (errorDetails && String(errorDetails).includes('404'));
      if (is3pCheckFailure) {
        console.info('Keycloak silent/3p check failed (timeout or 404); continuing as unauthenticated.');
        keycloakInitialized.value = true;
        keycloakInitializationStarted.value = false;
        _keycloak.value = keycloak.value;
        return;
      }
      
      const fullMessage = `Error while setting up authentication provider: ${errorMessage}${errorDetails ? ` - ${errorDetails}` : ''}`;
      console.error(fullMessage);
      throw new Error(fullMessage);
    }
    _keycloak.value = keycloak.value;
    keycloakInitialized.value = true;
  };

  const refreshKeycloakSession = async (): Promise<void> => {
    if (!keycloak.value) {
      throw new Error("Couldn't refresh session: Keycloak not initialized");
    }
    try {
      const refreshed = await keycloak.value.updateToken(300);
      if (refreshed) {
        _keycloak.value = { ...keycloak.value };
      }
    } catch (error: any) {
      console.error(`Token refresh failed: ${error.message}`);
      if (keycloak.value.authenticated) {
        keycloak.value.clearToken();
      }
      throw error;
    }
  };

  /**
   * This method handles logging the user in. It redirects the user to the keycloak login page.
   *
   * @param destination If set the user gets redirected to a different page than the one he tried to login from.
   */
  const login = async (destination?: string) => {
    if (keycloak.value) {
      await keycloak.value.login({
        redirectUri: `${window.location.origin}${destination || '/'}`,
        scope: 'openid'
      });
      try {
      await keycloak.value.loadUserProfile();
      } catch (profileError: any) {
        const errorMessage = profileError?.message || profileError?.toString() || 'Unknown error';
        if (errorMessage.includes('CORS') || errorMessage.includes('account')) {
          console.info(`Profile loading skipped after login (CORS expected): ${errorMessage}`);
        } else {
          console.error(`Failed to load user profile after login: ${errorMessage}`);
        }
      }
    } else {
      throw new Error("Couldn't login user: Keycloak not initialized");
    }
  };

  /**
   * This method handles logging the user out.
   *
   * @param destination If set the user gets redirected to a different page than the one he logged out from.
   */
  const logout = async (destination?: string, queryParameters?: Record<string, any>) => {
    if (keycloak.value) {
      if (!queryParameters) queryParameters = {};
      queryParameters.redirect_uri = false;
      await keycloak.value.logout({
        redirectUri: `${window.location.origin}${destination}?${Object.entries(queryParameters)
          .map(([key, value]) => `${key}=${value}`)
          .join('&')}`,
        id_token_hint: keycloak.value.idToken
      } as any); // Keycloak adpater doesn't know that the parameters changed
      keycloak.value.clearToken();
    } else {
      throw new Error("Couldn't logout user: Keycloak not initialized");
    }
  };

  const authenticated = computed<boolean>(() => keycloak.value?.authenticated || false);

  const token = computed<string | undefined>(() => keycloak.value?.token);

  const roles = computed<string[]>(() => [
    ...(keycloak.value?.tokenParsed?.realm_access?.roles || []),
    ...(keycloak.value?.tokenParsed?.resource_access?.['veo-accounts']?.roles || [])
  ]);

  const profile = computed(() => keycloak.value?.profile);

  const userSettings = computed<IVeoUserSettings>(() => ({
    maxUnits: keycloak.value?.tokenParsed?.max_units || 2,
    maxUsers: keycloak.value?.tokenParsed?.max_users || -1
  }));

  const accountDisabled = computed<boolean>(
    () => !(keycloak.value?.tokenParsed?.realm_access?.roles?.includes('veo-user') ?? false)
  );

  if (authenticated.value && accountDisabled.value) {
    logout('/login', { client_disabled: true });
  }

  return {
    authenticated,
    initialize,
    keycloak: _keycloak,
    keycloakInitialized,
    login,
    logout,
    profile,
    refreshKeycloakSession,
    roles,
    tablePageSize,
    token,
    userSettings
  };
};

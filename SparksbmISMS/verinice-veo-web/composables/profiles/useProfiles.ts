/*
 * verinice.veo web
 * Copyright (C) 2024 jae
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

import { useQuerySync } from '~/composables/api/utils/query';
import domainQueryDefinitions from '~/composables/api/queryDefinitions/domains';
import type { TVeoDomain } from '~/composables/domains/useDomains';

// API returns IVeoAPIProfile[]
interface IVeoAPIProfile {
  id: string;
  name: string;
  description: string;
  language: string;
  productId: string;
}

interface IVeoProfilesPerDomain {
  domainName: string;
  domainId: string;
  profiles: IVeoAPIProfile[];
}

// Internally this FE uses:
export interface TVeoProfile extends IVeoAPIProfile {
  domainName: string;
  domainId: string;
  raw: IVeoAPIProfile;
}

export function useProfiles() {
  const { data: domains } = useDomains();
  const { locale } = useI18n();
  const profiles = ref<TVeoProfile[]>([]);
  const isLoading = ref(true);

  // Fetch all profiles from all available domains
  async function getProfiles({ domains }: { domains: TVeoDomain[] }): Promise<IVeoProfilesPerDomain[]> {
    if (!domains) return [];

    return await Promise.all(
      domains.map(async (domain) => {
        try {
        const profiles = await useQuerySync(domainQueryDefinitions.queries.fetchProfiles, { domainId: domain.id });
          // Ensure profiles is always an array
          const profilesArray = Array.isArray(profiles) ? profiles : [];
        // The API does not return information on domainName, id etc.
        // This is why fetched profile data needs to be enhanced:
          return { domainName: domain.name, domainId: domain.id, profiles: profilesArray };
        } catch (error: any) {
          console.warn(`Failed to fetch profiles for domain ${domain.id}: ${error.message}`);
          return { domainName: domain.name, domainId: domain.id, profiles: [] };
        }
      })
    );
  }

  watch(
    domains,
    async () => {
      // Clone domains, because they are readonly
      const _domains = JSON.parse(JSON.stringify(domains.value));
      const profilesPerDomain = await getProfiles({ domains: _domains });
      profiles.value = map(profilesPerDomain, locale.value);
      isLoading.value = false;
    },
    { immediate: true }
  );

  return {
    profiles,
    isLoading
  };
}

// Transform data into a structure which can be used in SFCs
function map(profilesPerDomain: IVeoProfilesPerDomain[], currentLocale: string = 'en'): TVeoProfile[] {
  const preferredLanguages = ['en', 'en_US', 'en_GB'];
  
  return profilesPerDomain
    .map((domain) => {
      const profiles = domain?.profiles || [];
      
      // Group profiles by productId to handle multiple languages
      const profilesByProductId = new Map<string, IVeoAPIProfile[]>();
      profiles.forEach(profile => {
        const productId = profile.productId || 'unknown';
        if (!profilesByProductId.has(productId)) {
          profilesByProductId.set(productId, []);
        }
        profilesByProductId.get(productId)!.push(profile);
      });
      
      // For each productId, prefer English profiles, then current locale, then any
      const selectedProfiles: IVeoAPIProfile[] = [];
      profilesByProductId.forEach((profileGroup) => {
        let selected = profileGroup[0];
        
        // Prefer English
        const englishProfile = profileGroup.find(p => {
          if (!p.language) return false;
          return preferredLanguages.some(lang => 
            p.language.toLowerCase().startsWith(lang.toLowerCase())
          );
        });
        if (englishProfile) {
          selected = englishProfile;
        } else {
          // Then prefer current locale
          const localeProfile = profileGroup.find(p => {
            if (!p.language) return false;
            return p.language.toLowerCase().startsWith(currentLocale.toLowerCase());
          });
          if (localeProfile) {
            selected = localeProfile;
          }
        }
        
        selectedProfiles.push(selected);
      });
      
      return selectedProfiles.map((profile) => ({
        ...profile,
        domainName: domain.domainName,
        domainId: domain.domainId,
        raw: profile
      }));
    })
    .flat();
}

<!--
verinice.veo web
Copyright (C) 2025 gk

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
-->
<template>
  <v-row align="center" justify="center">
    <template v-if="!props.domains.length">
      <v-col cols="12">
        <VSkeletonLoader v-for="i in 5" :key="i" type="image" elevation="2" class="my-6" height="160px" />
      </v-col>
    </template>

    <template v-for="domain in domainsWithStatus" v-else :key="domain.id">
      <BaseListItem :item="domain" :data-veo-test="`domain-${domain.name}`">
        <template #center-aside="{ item: d }">
          <div class="d-flex align-center gap-2">
          <v-icon :color="d.color" :icon="mdiPuzzle" />
            <v-chip
              :color="d.statusBadgeColor"
              :prepend-icon="d.statusBadgeIcon"
              size="small"
              variant="flat"
            >
              {{ d.statusBadgeText }}
            </v-chip>
          </div>
        </template>
        <template #prepend="{ item: d }">
          <v-checkbox
            v-model="selected"
            :data-veo-test="`domain-card-checkbox-${d?.name ? d?.name.toLowerCase() : ''}`"
            color="primary"
            :value="d"
            :aria-label="`domain-${domain.name}`"
            :disabled="isDisabled || d.id === mandatoryDomain?.id || isDomainExisting(d)"
          />
        </template>
      </BaseListItem>
    </template>
  </v-row>
</template>

<script setup lang="ts">
import { mdiPuzzle, mdiCheckCircle, mdiAlertCircle } from '@mdi/js';
import type { TVeoDomain } from '~/composables/domains/useDomains';

const { data: currentUnit } = useUnit();

interface Props {
  domains: readonly TVeoDomain[];
  isAssociatingDomains?: boolean;
  isDisabled?: boolean;
  mandatoryDomain?: TVeoDomain;
}

const props = withDefaults(defineProps<Props>(), {
  isAssociatingDomains: false,
  isDisabled: false,
  mandatoryDomain: undefined
});

// State
const selected = defineModel<TVeoDomain[]>();

// Calculate subtype count for a domain
function getSubtypeCount(domain: TVeoDomain): number {
  const elementDefs = domain.raw?.elementTypeDefinitions || {};
  return Object.values(elementDefs).reduce((total: number, def: any) => {
    const subTypes = def?.subTypes || {};
    return total + Object.keys(subTypes).length;
  }, 0);
}

// Add status badge info to domains
const domainsWithStatus = computed(() => {
  return props.domains.map((domain) => {
    const count = getSubtypeCount(domain);
    const isBroken = count === 0;
    const isComplete = count > 15;
    
    return {
      ...domain,
      statusBadgeColor: isBroken ? 'error' : (isComplete ? 'success' : 'warning'),
      statusBadgeIcon: isBroken ? mdiAlertCircle : mdiCheckCircle,
      statusBadgeText: isBroken ? 'No subtypes' : (isComplete ? `${count} subtypes` : `${count} subtypes (incomplete)`)
    };
  });
});

const isDomainExisting = (domain: TVeoDomain): boolean => {
  return !!currentUnit.value?.raw?.domains?.some((d) => d.id === domain.id);
};

watch([() => props.domains, () => currentUnit.value?.raw?.domains], () => {
  selected.value ??= [];

  const unitDomains = currentUnit.value?.raw?.domains ?? [];
  const allDomains = props.domains;

  unitDomains.forEach((unitDomain) => {
    const matchingDomain = allDomains.find((d) => d.id === unitDomain.id);
    if (matchingDomain && !selected.value?.some((s) => s.id === matchingDomain.id)) {
      selected.value?.push(matchingDomain);
    }
  });
});
</script>

<i18n src="~/locales/base/components/unit-domains.json"></i18n>

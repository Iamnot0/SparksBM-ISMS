<!--
   - verinice.veo web
   - Copyright (C) 2021  Jonas Heitmann, Davit Svandize, Tino Groteloh, Jessica Lühnen, Jochen Kemnade, Annemarie Bufe
   -
   - This program is free software: you can redistribute it and/or modify
   - it under the terms of the GNU Affero General Public License as published by
   - the Free Software Foundation, either version 3 of the License, or
   - (at your option) any later version.
   -
   - This program is distributed in the hope that it will be useful,
   - but WITHOUT ANY WARRANTY; without even the implied warranty of
   - MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   - GNU Affero General Public License for more details.
   -
   - You should have received a copy of the GNU Affero General Public License
   - along with this program.  If not, see <http://www.gnu.org/licenses/>.
-->
<template>
  <BasePage :loading="reportsFetching" data-component-name="report-page">
    <template #header>
      <v-row v-if="report" dense class="justify-space-between mt-6">
        <v-col cols="12">
          <ReportItem
            :name="reportName"
            :description="reportDescription"
            :language="reportLang"
            data-component-name="report-selected"
          />
        </v-col>
      </v-row>
    </template>
    <template #default>
      <LayoutLoadingWrapper v-if="generatingReport" />

      <!-- @vue-ignore TODO #3066 $route does not exist -->
      <ObjectFilterBar
        class="mt-8"
        data-component-name="report-entity-selection-filter-bar"
        :available-object-types="availableObjectTypes"
        :available-sub-types="availableSubTypes"
        :domain-id="(Array.isArray($route.params.domain) ? $route.params.domain[0] : $route.params.domain) || ''"
        :filter="filter"
        :required-fields="requiredFields"
        :disabled-fields="disabledFields"
        :report-name="requestedReportName"
        @update:filter="updateRouteQuery"
      />

      <p v-if="report" class="text-body-1 my-2">
        {{ report.multipleTargetsSupported ? t('hintMultiple') : t('hintSingle') }}
      </p>

      <BaseCard>
        <ObjectTable
          v-model:page="page"
          v-model:sort-by="sortBy"
          :model-value="selectedObjects"
          show-select
          :default-headers="[
            'icon',
            'designator',
            'abbreviation',
            'name',
            'status',
            'description',
            'updatedBy',
            'updatedAt',
            'actions'
          ]"
          :items="objects"
          :loading="objectsFetching"
          data-component-name="report-entity-selection"
          @update:model-value="onReportSelectionUpdated"
        />
      </BaseCard>
      <v-row no-gutters class="mt-4">
        <v-spacer />
        <v-col cols="auto">
          <v-btn
            flat
            color="primary"
            :disabled="generatingReport || !selectedObjects.length"
            data-component-name="generate-report-button"
            @click="generateReport"
          >
            {{ t('generateReport') }}
          </v-btn>
          <a ref="downloadButton" :aria-label="t('generateReport')" href="#"></a>
        </v-col>
      </v-row>
    </template>
  </BasePage>
</template>

<script lang="ts">
import { omit, upperCase, upperFirst } from 'lodash';

import type { QueryClient } from '@tanstack/vue-query';
import type { RouteRecordName } from 'vue-router';
import { useFetchObjects } from '~/composables/api/objects';
import reportQueryDefinitions from '~/composables/api/queryDefinitions/reports';
import { useMutation } from '~/composables/api/utils/mutation';
import { useQuery } from '~/composables/api/utils/query';
import { useVeoAlerts } from '~/composables/VeoAlert';
import { useVeoUser } from '~/composables/VeoUser';
import type { IVeoEntity } from '~/types/VeoTypes';
import { VeoElementTypePlurals } from '~/types/VeoTypes';
import { LOCAL_STORAGE_KEYS } from '~/types/localStorage';

export const ROUTE_NAME = 'unit-domains-domain-reports-report';
export default defineComponent({
  name: 'VeoReportPage',
  setup() {
    const { t, locale } = useI18n();
    const route = useRoute();
    const { displayErrorMessage } = useVeoAlerts();
    const { tablePageSize } = useVeoUser();
    const reportLang = localStorage.getItem(LOCAL_STORAGE_KEYS.REPORT_LANG) || '';
    // Fetching the right report
    const requestedReportName = computed(() => {
      const reportParam = route.params.report;
      return Array.isArray(reportParam) ? reportParam[0] : (reportParam as string) || '';
    });
    const { data: reports, isFetching: reportsFetching } = useQuery(reportQueryDefinitions.queries.fetchAll);
    const report = computed(() => {
      const reportName = requestedReportName.value;
      const r = reportName && reports.value ? reports.value[reportName] : undefined;
      return r;
    });

    // Safe report name and description accessors
    const reportName = computed(() => {
      const r = report.value;
      if (!r || !r.name) return '';
      const lang = reportLang || 'en';
      return r.name[lang] || r.name['en'] || r.name[Object.keys(r.name)[0]] || '';
    });

    const reportDescription = computed(() => {
      const r = report.value;
      if (!r || !r.description) return '';
      const lang = reportLang || 'en';
      return r.description[lang] || r.description['en'] || r.description[Object.keys(r.description)[0]] || '';
    });

    const availableObjectTypes = computed<string[]>(() =>
      (report.value?.targetTypes || []).map((targetType) => targetType.modelType)
    );
    const availableSubTypes = computed<string[]>(
      () =>
        (report.value?.targetTypes || []).find((targetType) => targetType.modelType === filter.value.objectType)
          ?.subTypes || []
    );
    const outputType = computed<string>(() => {
      const outputTypes = report.value?.outputTypes;
      return (outputTypes && outputTypes.length > 0) ? outputTypes[0] : 'application/pdf';
    });

    const title = computed(() =>
      t('create', {
        type: reportName.value,
        format: upperCase(outputType.value.split('/').pop() || 'pdf')
      }).toString()
    );

    // Table stuff
    const selectedObjects = ref<{ id: string; type: string }[]>([]);

    const page = ref(0);
    const sortBy = ref([{ key: 'name', order: 'asc' }]);
    const resetQueryOptions = () => {
      page.value = 0;
      sortBy.value = [{ key: 'name', order: 'asc' }];
    };

    const requiredFields = computed(() =>
      availableSubTypes.value.length ? ['objectType', 'subType'] : ['objectType']
    );

    const disabledFields = ['objectType'];

    // accepted filter keys (others wont be respected when specified in URL query parameters)
    // Simplified filters for ALL reports
    const filterKeys = computed(() => [
      'objectType',
      'subType',
      'name'
    ] as const);

    // filter built from URL query parameters
    const filter = computed(() => {
      const query = route.query;

      let filterObject = Object.fromEntries(
        filterKeys.value.map((key) => {
          // Extract first query value
          const queryValue = query[key];
          const val = queryValue ? ([] as (string | null)[]).concat(queryValue).shift() : null;
          // Don't set filters to 'true' - just omit them if not specified
          return [key, val];
        })
      );

      const targetTypes = report.value?.targetTypes;
      const firstTargetType = targetTypes && targetTypes.length > 0 ? targetTypes[0] : null;
      const fixedSubTypes = firstTargetType?.subTypes || [];
      filterObject = {
        ...filterObject,
        objectType: firstTargetType?.modelType,
        subType: fixedSubTypes.length === 1 ? fixedSubTypes[0] : undefined
      };
      return filterObject;
    });

    watch(() => filter.value, resetQueryOptions, { deep: true });

    // Watch for report type changes and reset selection + refetch objects
    watch(() => requestedReportName.value, () => {
      // Reset selected objects when switching report types
      selectedObjects.value = [];
      // Reset pagination
      resetQueryOptions();
      // Refetch objects for the new report type
      if (objectsQueryEnabled.value) {
        refetchObjects();
      }
    });

    const endpoint = computed(() => {
      const objectType = filter.value.objectType;
      if (objectType && typeof objectType === 'string' && VeoElementTypePlurals[objectType]) {
        return VeoElementTypePlurals[objectType];
      }
      return '';
    });
    const combinedObjectsQueryParameters = computed(() => {
      const sortByValue = sortBy.value && sortBy.value.length > 0 ? sortBy.value[0] : { key: 'name', order: 'asc' as const };
      const unitParam = route.params.unit;
      const domainParam = route.params.domain;
      const unit = Array.isArray(unitParam) ? unitParam[0] : (typeof unitParam === 'string' ? unitParam : '');
      const domain = Array.isArray(domainParam) ? domainParam[0] : (typeof domainParam === 'string' ? domainParam : '');
      const sortOrder: 'asc' | 'desc' = (sortByValue.order === 'asc' || sortByValue.order === 'desc') ? sortByValue.order : 'asc';
      
      // Build params and filter out null/undefined values
      const filterValues = omit(filter.value, 'objectType');
      const cleanedFilter = Object.fromEntries(
        Object.entries(filterValues).filter(([_, v]) => v !== null && v !== undefined)
      );
      
      return {
        size: tablePageSize.value,
        sortBy: sortByValue.key,
        sortOrder,
        page: page.value,
        unit,
        domain,
        ...cleanedFilter,
        endpoint: endpoint.value
      };
    });
    const objectType = computed<string | undefined>(() => {
      const objType = filter.value.objectType;
      return (objType && typeof objType === 'string') ? objType : undefined;
    });
    const objectsQueryEnabled = computed(() => !!objectType.value && !!endpoint.value);

    const {
      data: objects,
      isLoading: objectsFetching,
      refetch: refetchObjects
    } = useFetchObjects(combinedObjectsQueryParameters, {
      enabled: objectsQueryEnabled,
      keepPreviousData: true,
      placeholderData: []
    });

    const updateRouteQuery = async (v: Record<string, string | undefined | null | true>, reset = true) => {
      const resetValues = reset ? filterKeys.value.map((key) => [key, undefined as string | undefined | null]) : [];
      const newValues = Object.fromEntries(
        resetValues.concat(Object.entries(v).map(([k, v]) => [k, v === true ? null : v]))
      );
      const query = { ...route.query, ...newValues };
      // obsolete params need to be removed from the query to match the route exactly in the NavigationDrawer
      Object.keys(query).forEach((key) => {
        if (query[key] === undefined) {
          Reflect.deleteProperty(query, key);
        }
      });
      await navigateTo({
        ...route,
        // @ts-ignore TODO #3066 does not exist
        name: route.name as RouteRecordName | undefined,
        query
      });
    };

    // Generating new report
    const downloadButton = ref<HTMLAnchorElement>();
    const openReport = (_queryClient: QueryClient, result: unknown) => {
      if (!downloadButton.value || !report.value) {
        return;
      }

      try {
        // Create blob URL - result should be a Blob from the mutation
        if (!(result instanceof Blob)) {
          throw new TypeError('Report result is not a valid Blob');
        }
        const blobUrl = URL.createObjectURL(result);
        downloadButton.value.href = blobUrl;
        
        // Sanitize filename (remove special characters, spaces)
        const reportNameObj = report.value.name || {};
        const localeValue = locale.value as string;
        const reportName = (reportNameObj[localeValue] || reportNameObj['en'] || 'report') as string;
        const sanitizedName = reportName.replace(/[^\w-]/g, '_');
        const fileExtension = (outputType.value.split('/').pop() || 'pdf') as string;
        downloadButton.value.download = `${sanitizedName}.${fileExtension}`;
        
        // Trigger download
      downloadButton.value.click();
        
        // Clean up blob URL after a short delay to ensure download starts
        setTimeout(() => {
          URL.revokeObjectURL(blobUrl);
        }, 100);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to download report';
        console.error('Failed to download report:', error);
        displayErrorMessage(t('generateReportError').toString(), errorMessage);
      }
    };

    const createMutationParameters = computed(() => ({
      type: requestedReportName.value,
      body: {
        outputType: outputType.value,
        language: reportLang,
        targets: selectedObjects.value,
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
      }
    }));
    const { mutateAsync: create, isLoading: generatingReport } = useMutation(reportQueryDefinitions.mutations.create, {
      onSuccess: openReport
    });

    const generateReport = async () => {
      if (report.value) {
        try {
          await create(createMutationParameters);
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to generate report';
          displayErrorMessage(t('generateReportError').toString(), errorMessage);
        }
      }
    };

    const onReportSelectionUpdated = (newObjects: IVeoEntity[]) => {
      if (newObjects?.length) {
        selectedObjects.value = [newObjects[0]];
      } else {
        selectedObjects.value = [];
      }
    };

    return {
      availableObjectTypes,
      availableSubTypes,
      downloadButton,
      filter,
      generateReport,
      generatingReport,
      objects,
      objectsFetching,
      onReportSelectionUpdated,
      selectedObjects,
      sortBy,
      page,
      refetchObjects,
      report,
      reportName,
      reportDescription,
      reportsFetching,
      requiredFields,
      disabledFields,
      requestedReportName,
      title,
      updateRouteQuery,
      t,
      reportLang,
      upperFirst
    };
  }
});
</script>

<i18n src="~/locales/base/pages/unit-domains-domain-reports-report.json"></i18n>

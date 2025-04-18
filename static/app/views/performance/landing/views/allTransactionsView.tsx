import {useTheme} from '@emotion/react';

import {canUseMetricsData} from 'sentry/utils/performance/contexts/metricsEnhancedSetting';
import {usePageAlert} from 'sentry/utils/performance/contexts/pageAlert';
import {PerformanceDisplayProvider} from 'sentry/utils/performance/contexts/performanceDisplayContext';
import useOrganization from 'sentry/utils/useOrganization';
import {
  DoubleChartRow,
  TripleChartRow,
} from 'sentry/views/performance/landing/widgets/components/widgetChartRow';
import {PerformanceWidgetSetting} from 'sentry/views/performance/landing/widgets/widgetDefinitions';
import Table from 'sentry/views/performance/table';
import {ProjectPerformanceType} from 'sentry/views/performance/utils';

import type {BasePerformanceViewProps} from './types';

export function AllTransactionsView(props: BasePerformanceViewProps) {
  const theme = useTheme();
  const {setPageError} = usePageAlert();
  const doubleChartRowCharts: PerformanceWidgetSetting[] = [];
  const organization = useOrganization();

  let allowedCharts = [
    PerformanceWidgetSetting.USER_MISERY_AREA,
    PerformanceWidgetSetting.TPM_AREA,
    PerformanceWidgetSetting.FAILURE_RATE_AREA,
    PerformanceWidgetSetting.APDEX_AREA,
    PerformanceWidgetSetting.P50_DURATION_AREA,
    PerformanceWidgetSetting.P75_DURATION_AREA,
    PerformanceWidgetSetting.P95_DURATION_AREA,
    PerformanceWidgetSetting.P99_DURATION_AREA,
  ];

  const hasTransactionSummaryCleanupFlag = organization.features.includes(
    'performance-transaction-summary-cleanup'
  );

  if (hasTransactionSummaryCleanupFlag) {
    allowedCharts = [
      PerformanceWidgetSetting.TPM_AREA,
      PerformanceWidgetSetting.FAILURE_RATE_AREA,
      PerformanceWidgetSetting.P50_DURATION_AREA,
      PerformanceWidgetSetting.P75_DURATION_AREA,
      PerformanceWidgetSetting.P95_DURATION_AREA,
      PerformanceWidgetSetting.P99_DURATION_AREA,
    ];
  }

  if (
    props.organization.features.includes('performance-new-trends') &&
    canUseMetricsData(props.organization)
  ) {
    if (props.organization.features.includes('insights-initial-modules')) {
      doubleChartRowCharts.unshift(PerformanceWidgetSetting.MOST_RELATED_ISSUES);
      doubleChartRowCharts.unshift(PerformanceWidgetSetting.MOST_CHANGED);
      doubleChartRowCharts.unshift(PerformanceWidgetSetting.MOST_TIME_CONSUMING_DOMAINS);
      doubleChartRowCharts.unshift(PerformanceWidgetSetting.MOST_TIME_SPENT_DB_QUERIES);
      doubleChartRowCharts.unshift(PerformanceWidgetSetting.OVERALL_PERFORMANCE_SCORE);
    } else {
      doubleChartRowCharts.unshift(PerformanceWidgetSetting.MOST_CHANGED);
      doubleChartRowCharts.unshift(PerformanceWidgetSetting.MOST_RELATED_ISSUES);
    }
  } else {
    doubleChartRowCharts.unshift(PerformanceWidgetSetting.MOST_REGRESSED);
    doubleChartRowCharts.push(PerformanceWidgetSetting.MOST_IMPROVED);
  }

  return (
    <PerformanceDisplayProvider value={{performanceType: ProjectPerformanceType.ANY}}>
      <div data-test-id="all-transactions-view">
        <DoubleChartRow {...props} allowedCharts={doubleChartRowCharts} />
        <TripleChartRow {...props} allowedCharts={allowedCharts} />
        <Table {...props} setError={setPageError} theme={theme} />
      </div>
    </PerformanceDisplayProvider>
  );
}

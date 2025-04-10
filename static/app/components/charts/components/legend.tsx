import 'echarts/lib/component/legend';
import 'echarts/lib/component/legendScroll';

import type {Theme} from '@emotion/react';
import type {LegendComponentOption} from 'echarts';
import merge from 'lodash/merge';

import type BaseChart from 'sentry/components/charts/baseChart';
import {truncationFormatter} from 'sentry/components/charts/utils';

type ChartProps = React.ComponentProps<typeof BaseChart>;

export default function Legend(
  props: ChartProps['legend'] & {theme: Theme}
): LegendComponentOption {
  const {truncate, theme, ...rest} = props ?? {};
  const formatter = (value: string) =>
    truncationFormatter(
      value,
      truncate ?? 0,
      // Escaping the legend string will cause some special
      // characters to render as their HTML equivalents.
      // So disable it here.
      false
    );

  return merge(
    {
      show: true,
      type: 'scroll' as const,
      padding: 0,
      formatter,
      icon: 'circle',
      itemHeight: 14,
      itemWidth: 8,
      itemGap: 12,
      align: 'left' as const,
      textStyle: {
        color: theme.textColor,
        verticalAlign: 'top',
        fontSize: 11,
        fontFamily: theme.text.family,
        lineHeight: 14,
      },
      inactiveColor: theme.subText,
      pageTextStyle: {
        color: theme.textColor,
      },
      pageIconColor: theme.textColor,
      pageIconInactiveColor: theme.disabled,
    } satisfies LegendComponentOption,
    rest
  );
}

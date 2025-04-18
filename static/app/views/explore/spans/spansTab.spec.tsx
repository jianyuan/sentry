import {initializeOrg} from 'sentry-test/initializeOrg';
import {render, screen, userEvent, within} from 'sentry-test/reactTestingLibrary';

import PageFiltersStore from 'sentry/stores/pageFiltersStore';
import type {TagCollection} from 'sentry/types/group';
import {trackAnalytics} from 'sentry/utils/analytics';
import {FieldKind} from 'sentry/utils/fields';
import * as spanTagsModule from 'sentry/views/explore/contexts/spanTagsContext';
import {SpansTabContent} from 'sentry/views/explore/spans/spansTab';

jest.mock('sentry/utils/analytics');

const mockStringTags: TagCollection = {
  stringTag1: {key: 'stringTag1', kind: FieldKind.TAG, name: 'stringTag1'},
  stringTag2: {key: 'stringTag2', kind: FieldKind.TAG, name: 'stringTag2'},
};

const mockNumberTags: TagCollection = {
  numberTag1: {key: 'numberTag1', kind: FieldKind.MEASUREMENT, name: 'numberTag1'},
  numberTag2: {key: 'numberTag2', kind: FieldKind.MEASUREMENT, name: 'numberTag2'},
};

// Mock getBoundingClientRect for container
jest.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
  this: HTMLElement
) {
  // Mock individual hint items
  if (this.hasAttribute('data-type')) {
    return {
      width: 200,
      right: 200,
      left: 0,
      top: 0,
      bottom: 100,
      height: 100,
      x: 0,
      y: 0,
      toJSON: () => {},
    };
  }
  return {
    width: 1000,
    right: 1000,
    left: 0,
    top: 0,
    bottom: 100,
    height: 100,
    x: 0,
    y: 0,
    toJSON: () => {},
  };
});

describe('SpansTabContent', function () {
  const {organization, project} = initializeOrg();

  beforeEach(function () {
    MockApiClient.clearMockResponses();

    // without this the `CompactSelect` component errors with a bunch of async updates
    jest.spyOn(console, 'error').mockImplementation();

    PageFiltersStore.init();
    PageFiltersStore.onInitializeUrlState(
      {
        projects: [project].map(p => parseInt(p.id, 10)),
        environments: [],
        datetime: {period: '7d', start: null, end: null, utc: null},
      },
      new Set()
    );
    MockApiClient.addMockResponse({
      url: `/subscriptions/${organization.slug}/`,
      method: 'GET',
      body: {},
    });
    MockApiClient.addMockResponse({
      url: `/organizations/${organization.slug}/recent-searches/`,
      method: 'GET',
      body: {},
    });

    MockApiClient.addMockResponse({
      url: `/organizations/${organization.slug}/spans/fields/`,
      method: 'GET',
      body: [],
    });
    MockApiClient.addMockResponse({
      url: `/organizations/${organization.slug}/events/`,
      method: 'GET',
      body: {},
    });
    MockApiClient.addMockResponse({
      url: `/organizations/${organization.slug}/events-stats/`,
      method: 'GET',
      body: {},
    });
    MockApiClient.addMockResponse({
      url: `/organizations/${organization.slug}/traces/`,
      method: 'GET',
      body: {},
    });
  });

  it('should fire analytics once per change', async function () {
    render(
      <SpansTabContent
        defaultPeriod="7d"
        maxPickableDays={7}
        relativeOptions={{'1h': 'Last hour', '24h': 'Last 24 hours', '7d': 'Last 7 days'}}
      />,
      {enableRouterMocks: false, organization}
    );

    await screen.findByText(/No spans found/);
    expect(trackAnalytics).toHaveBeenCalledTimes(1);
    expect(trackAnalytics).toHaveBeenCalledWith(
      'trace.explorer.metadata',
      expect.objectContaining({result_mode: 'span samples'})
    );

    (trackAnalytics as jest.Mock).mockClear();
    await userEvent.click(await screen.findByText('Trace Samples'));

    await screen.findByText(/No trace results found/);
    expect(trackAnalytics).toHaveBeenCalledTimes(1);
    expect(trackAnalytics).toHaveBeenCalledWith(
      'trace.explorer.metadata',
      expect.objectContaining({result_mode: 'trace samples'})
    );

    (trackAnalytics as jest.Mock).mockClear();
    await userEvent.click(
      within(screen.getByTestId('section-mode')).getByRole('radio', {name: 'Aggregates'})
    );

    await screen.findByText(/No spans found/);
    expect(trackAnalytics).toHaveBeenCalledTimes(1);
    expect(trackAnalytics).toHaveBeenCalledWith(
      'trace.explorer.metadata',
      expect.objectContaining({result_mode: 'aggregates'})
    );
  });

  it('should show hints when the feature flag is enabled', function () {
    jest.spyOn(spanTagsModule, 'useSpanTags').mockImplementation(type => {
      switch (type) {
        case 'number':
          return {tags: mockNumberTags, isLoading: false};
        case 'string':
          return {tags: mockStringTags, isLoading: false};
        default:
          return {tags: {}, isLoading: false};
      }
    });

    const {organization: schemaHintsOrganization} = initializeOrg({
      organization: {...organization, features: ['traces-schema-hints']},
    });

    // Mock clientWidth before rendering to display hints
    jest.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(1000);

    render(
      <SpansTabContent
        defaultPeriod="7d"
        maxPickableDays={7}
        relativeOptions={{'1h': 'Last hour', '24h': 'Last 24 hours', '7d': 'Last 7 days'}}
      />,
      {enableRouterMocks: false, organization: schemaHintsOrganization}
    );

    expect(screen.getByText('stringTag1')).toBeInTheDocument();
    expect(screen.getByText('stringTag2')).toBeInTheDocument();
    expect(screen.getByText('numberTag1')).toBeInTheDocument();
    expect(screen.getByText('numberTag2')).toBeInTheDocument();
    expect(screen.getByText('See full list')).toBeInTheDocument();
  });
});

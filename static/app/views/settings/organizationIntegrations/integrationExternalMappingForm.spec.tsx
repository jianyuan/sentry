import {GitHubIntegrationFixture} from 'sentry-fixture/githubIntegration';

import {render, screen, userEvent, waitFor} from 'sentry-test/reactTestingLibrary';

import IntegrationExternalMappingForm from './integrationExternalMappingForm';

describe('IntegrationExternalMappingForm', function () {
  const dataEndpoint = '/test/dataEndpoint/';
  const baseProps = {
    integration: GitHubIntegrationFixture(),
    dataEndpoint,
    getBaseFormEndpoint: jest.fn(_mapping => dataEndpoint),
    sentryNamesMapper: mappings => mappings,
  } satisfies Partial<React.ComponentProps<typeof IntegrationExternalMappingForm>>;
  const MOCK_USER_MAPPING = {
    id: '1',
    userId: '1',
    externalName: '@gwen',
    sentryName: 'gwen@mcu.org',
  };
  const MOCK_TEAM_MAPPING = {
    id: '1',
    teamId: '1',
    externalName: '@getsentry/animals',
    sentryName: '#zoo',
  };
  const DEFAULT_OPTIONS = [
    {id: '1', name: 'option1'},
    {id: '2', name: 'option2'},
    {id: '3', name: 'option3'},
  ];

  let getResponse: jest.Mock;
  let postResponse: jest.Mock;
  let putResponse: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    MockApiClient.clearMockResponses();
    getResponse = MockApiClient.addMockResponse({
      url: dataEndpoint,
      method: 'GET',
      body: DEFAULT_OPTIONS,
    });
    postResponse = MockApiClient.addMockResponse({
      url: dataEndpoint,
      method: 'POST',
      body: {},
    });
    putResponse = MockApiClient.addMockResponse({
      url: `${dataEndpoint}1/`,
      method: 'PUT',
      body: {},
    });
  });

  // No mapping provided (e.g. Create a new mapping)
  it('renders with no mapping provided as a form', async function () {
    render(<IntegrationExternalMappingForm type="user" {...baseProps} />);
    expect(await screen.findByPlaceholderText('@username')).toBeInTheDocument();
    expect(screen.getByText('Select Sentry User')).toBeInTheDocument();
    expect(screen.getByTestId('form-submit')).toBeInTheDocument();
  });
  it('renders with no mapping as an inline field', async function () {
    render(<IntegrationExternalMappingForm isInline type="user" {...baseProps} />);
    expect(await screen.findByText('Select Sentry User')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('@username')).not.toBeInTheDocument();
    expect(screen.queryByTestId('form-submit')).not.toBeInTheDocument();
  });

  // Full mapping provided (e.g. Update an existing mapping)
  it('renders with a full mapping provided as a form', async function () {
    render(
      <IntegrationExternalMappingForm
        type="user"
        mapping={MOCK_USER_MAPPING}
        {...baseProps}
      />
    );
    expect(
      await screen.findByDisplayValue(MOCK_USER_MAPPING.externalName)
    ).toBeInTheDocument();
    expect(
      await screen.findByText(`option${MOCK_USER_MAPPING.userId}`)
    ).toBeInTheDocument();
    expect(screen.getByTestId('form-submit')).toBeInTheDocument();
  });
  it('renders with a full mapping provided as an inline field', async function () {
    render(
      <IntegrationExternalMappingForm
        isInline
        type="user"
        mapping={MOCK_USER_MAPPING}
        {...baseProps}
      />
    );
    expect(
      await screen.findByText(`option${MOCK_USER_MAPPING.userId}`)
    ).toBeInTheDocument();
    expect(
      screen.queryByDisplayValue(MOCK_USER_MAPPING.externalName)
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId('form-submit')).not.toBeInTheDocument();
  });

  // Suggested mapping provided (e.g. Create new mapping from suggested external name)
  it('renders with a suggested mapping provided as a form', async function () {
    render(
      <IntegrationExternalMappingForm
        type="team"
        mapping={{externalName: MOCK_TEAM_MAPPING.externalName}}
        {...baseProps}
      />
    );
    expect(
      await screen.findByDisplayValue(MOCK_TEAM_MAPPING.externalName)
    ).toBeInTheDocument();
    expect(screen.getByText('Select Sentry Team')).toBeInTheDocument();
    expect(screen.getByTestId('form-submit')).toBeInTheDocument();
  });
  it('renders with a suggested mapping provided as an inline field', async function () {
    render(
      <IntegrationExternalMappingForm
        isInline
        type="team"
        mapping={{externalName: MOCK_TEAM_MAPPING.externalName}}
        {...baseProps}
      />
    );
    expect(await screen.findByText('Select Sentry Team')).toBeInTheDocument();
    expect(
      screen.queryByDisplayValue(MOCK_TEAM_MAPPING.externalName)
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId('form-submit')).not.toBeInTheDocument();
  });

  it('updates the model when submitting', async function () {
    render(
      <IntegrationExternalMappingForm
        type="user"
        mapping={{externalName: MOCK_USER_MAPPING.externalName}}
        {...baseProps}
      />
    );
    expect(baseProps.getBaseFormEndpoint).not.toHaveBeenCalled();
    expect(postResponse).not.toHaveBeenCalled();
    await userEvent.type(screen.getByText('Select Sentry User'), 'option2');
    await userEvent.click(screen.getAllByText('option2')[1]!);
    await userEvent.click(screen.getByTestId('form-submit'));

    await waitFor(() => {
      expect(baseProps.getBaseFormEndpoint).toHaveBeenCalledWith({
        externalName: MOCK_USER_MAPPING.externalName,
        integrationId: baseProps.integration.id,
        provider: baseProps.integration.provider.name.toLowerCase(),
        // From option2 selection
        userId: '2',
      });
    });

    expect(postResponse).toHaveBeenCalled();
    expect(putResponse).not.toHaveBeenCalled();
  });

  it('submits on blur when used as an inline field', async function () {
    render(
      <IntegrationExternalMappingForm
        isInline
        type="team"
        mapping={MOCK_TEAM_MAPPING}
        {...baseProps}
      />
    );
    expect(await screen.findByText('option1')).toBeInTheDocument();
    expect(baseProps.getBaseFormEndpoint).not.toHaveBeenCalled();
    expect(putResponse).not.toHaveBeenCalled();
    await userEvent.type(screen.getByRole('textbox'), 'option3');
    expect(await screen.findAllByText('option3')).toHaveLength(2);
    await userEvent.click(screen.getAllByText('option3')[1]!);
    await waitFor(() => {
      expect(baseProps.getBaseFormEndpoint).toHaveBeenCalledWith({
        ...MOCK_TEAM_MAPPING,
        integrationId: baseProps.integration.id,
        provider: baseProps.integration.provider.name.toLowerCase(),
        // From option3 selection
        teamId: '3',
      });
    });
    expect(putResponse).toHaveBeenCalled();
    expect(postResponse).not.toHaveBeenCalled();
  });

  it('allows defaultOptions to be provided', async function () {
    render(
      <IntegrationExternalMappingForm
        type="user"
        mapping={MOCK_USER_MAPPING}
        defaultOptions={DEFAULT_OPTIONS.map(({id, name}) => ({value: id, label: name}))}
        {...baseProps}
      />
    );
    const sentryNameField = screen.getByText(`option${MOCK_USER_MAPPING.userId}`);
    // Don't query for results on load
    expect(await screen.findByText('option1')).toBeInTheDocument();
    expect(sentryNameField).toBeInTheDocument();
    expect(getResponse).not.toHaveBeenCalled();
    // Now that the user types, query for results
    await userEvent.type(sentryNameField, 'option2');
    await userEvent.click(screen.getAllByText('option2')[1]!);
    await waitFor(() => expect(getResponse).toHaveBeenCalled());
  });
});

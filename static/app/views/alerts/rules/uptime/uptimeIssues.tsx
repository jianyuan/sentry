import EmptyStateWarning from 'sentry/components/emptyStateWarning';
import GroupList from 'sentry/components/issues/groupList';
import Panel from 'sentry/components/panels/panel';
import PanelBody from 'sentry/components/panels/panelBody';
import {t} from 'sentry/locale';
import {IssueType} from 'sentry/types/group';
import type {Project} from 'sentry/types/project';

interface Props {
  project: Project;
  ruleId: string;
}

export function UptimeIssues({project, ruleId}: Props) {
  // TODO(davidenwang): Replace this with an actual query for the specific uptime alert rule
  const query = `issue.type:${IssueType.UPTIME_DOMAIN_FAILURE} tags[uptime_rule]:${ruleId}`;

  const emptyMessage = () => {
    return (
      <Panel>
        <PanelBody>
          <EmptyStateWarning>
            <p>{t('No issues relating to this uptime alert have been found.')}</p>
          </EmptyStateWarning>
        </PanelBody>
      </Panel>
    );
  };

  return (
    <GroupList
      withChart={false}
      withPagination={false}
      withColumns={['assignee']}
      queryParams={{
        query,
        project: project.id,
        limit: 1,
      }}
      renderEmptyMessage={emptyMessage}
    />
  );
}

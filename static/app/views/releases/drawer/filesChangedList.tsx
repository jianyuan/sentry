import {Fragment} from 'react';
import styled from '@emotion/styled';

import LoadingError from 'sentry/components/loadingError';
import Pagination from 'sentry/components/pagination';
import Panel from 'sentry/components/panels/panel';
import PanelBody from 'sentry/components/panels/panelBody';
import PanelHeader from 'sentry/components/panels/panelHeader';
import Placeholder from 'sentry/components/placeholder';
import {t, tn} from 'sentry/locale';
import {space} from 'sentry/styles/space';
import type {Repository} from 'sentry/types/integrations';
import {useLocation} from 'sentry/utils/useLocation';
import {useNavigate} from 'sentry/utils/useNavigate';
import {EmptyState} from 'sentry/views/releases/detail/commitsAndFiles/emptyState';
import FileChange from 'sentry/views/releases/detail/commitsAndFiles/fileChange';
import RepositorySwitcher from 'sentry/views/releases/detail/commitsAndFiles/repositorySwitcher';
import {getFilesByRepository, getReposToRender} from 'sentry/views/releases/detail/utils';
import {useReleaseCommitFiles} from 'sentry/views/releases/utils/useReleaseCommitFiles';

interface FilesChangedProps {
  release: string;
  releaseRepos: Repository[];
}

export function FilesChangedList({releaseRepos, release}: FilesChangedProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const activeReleaseRepo =
    releaseRepos.find(repo => repo.name === location.query.activeRepo) ?? releaseRepos[0];

  const {
    data: fileList = [],
    isPending: isLoadingFileList,
    error: fileListError,
    refetch,
    getResponseHeader,
  } = useReleaseCommitFiles({
    release,
    activeRepository: activeReleaseRepo,
    cursor: location.query.fileCursor,
  });

  const filesByRepository = getFilesByRepository(fileList);
  const reposToRender = getReposToRender(Object.keys(filesByRepository));
  const fileListPageLinks = getResponseHeader?.('Link');

  return (
    <div>
      {releaseRepos.length > 1 && (
        <Actions>
          <RepositorySwitcher
            repositories={releaseRepos}
            activeRepository={activeReleaseRepo}
          />
        </Actions>
      )}
      <div>
        {fileListError && <LoadingError onRetry={refetch} />}
        {isLoadingFileList ? (
          <Placeholder height="120px" />
        ) : fileList.length ? (
          <Fragment>
            {reposToRender.map(repoName => {
              const repoData = filesByRepository[repoName]!;
              const repoDataEntries = Object.entries(repoData);
              const fileCount = repoDataEntries.length;
              return (
                <Panel key={repoName}>
                  <PanelHeader>
                    <span>{repoName}</span>
                    <span>{tn('%s file changed', '%s files changed', fileCount)}</span>
                  </PanelHeader>
                  <PanelBody>
                    {repoDataEntries.map(([filename, {authors}]) => {
                      return (
                        <FileChange
                          key={filename}
                          filename={filename}
                          authors={authors ? Object.values(authors) : []}
                        />
                      );
                    })}
                  </PanelBody>
                </Panel>
              );
            })}
            <Pagination
              pageLinks={fileListPageLinks}
              onCursor={(cursor, path, searchQuery) => {
                navigate({
                  pathname: path,
                  query: {...searchQuery, fileCursor: cursor},
                });
              }}
            />
          </Fragment>
        ) : (
          <EmptyState>
            {activeReleaseRepo
              ? t(
                  'There are no changed files associated with this release in the %s repository.',
                  activeReleaseRepo.name
                )
              : t('There are no changed files associated with this release.')}
          </EmptyState>
        )}
      </div>
    </div>
  );
}

const Actions = styled('div')`
  margin-bottom: ${space(2)};
`;

import {openHelpSearchModal} from 'sentry/actionCreators/modal';
import type {MenuItemProps} from 'sentry/components/dropdownMenu';
import {IconQuestion} from 'sentry/icons';
import {t} from 'sentry/locale';
import ConfigStore from 'sentry/stores/configStore';
import type {Organization} from 'sentry/types/organization';
import {trackAnalytics} from 'sentry/utils/analytics';
import {useFeedbackForm} from 'sentry/utils/useFeedbackForm';
import useMutateUserOptions from 'sentry/utils/useMutateUserOptions';
import useOrganization from 'sentry/utils/useOrganization';
import {useUser} from 'sentry/utils/useUser';
import {activateZendesk, zendeskIsLoaded} from 'sentry/utils/zendesk';
import {SidebarMenu} from 'sentry/views/nav/primary/components';
import {
  StackedNavigationTourReminder,
  useStackedNavigationTour,
} from 'sentry/views/nav/tour/tour';

function getContactSupportItem({
  organization,
}: {
  organization: Organization;
}): MenuItemProps | null {
  const supportEmail = ConfigStore.get('supportEmail');

  if (!supportEmail) {
    return null;
  }

  if (zendeskIsLoaded()) {
    return {
      key: 'support',
      label: t('Contact Support'),
      onAction() {
        activateZendesk();
        trackAnalytics('zendesk_link.clicked', {
          organization,
          source: 'sidebar',
        });
      },
    };
  }

  return {
    key: 'support',
    label: t('Contact Support'),
    externalHref: `mailto:${supportEmail}`,
  };
}

export function PrimaryNavigationHelp() {
  const organization = useOrganization();
  const user = useUser();
  const {mutate: mutateUserOptions} = useMutateUserOptions();
  const contactSupportItem = getContactSupportItem({organization});
  const openForm = useFeedbackForm();
  const {startTour} = useStackedNavigationTour();

  return (
    <StackedNavigationTourReminder>
      <SidebarMenu
        items={[
          {
            key: 'search',
            label: t('Search support, docs and more'),
            onAction() {
              openHelpSearchModal({organization});
            },
          },
          {
            key: 'resources',
            label: t('Resources'),
            children: [
              {
                key: 'help-center',
                label: t('Help Center'),
                externalHref: 'https://sentry.zendesk.com/hc/en-us',
              },
              {
                key: 'docs',
                label: t('Documentation'),
                externalHref: 'https://docs.sentry.io',
              },
            ],
          },
          {
            key: 'help',
            label: t('Get Help'),
            children: [
              ...(contactSupportItem ? [contactSupportItem] : []),
              {
                key: 'github',
                label: t('Sentry on GitHub'),
                externalHref: 'https://github.com/getsentry/sentry/issues',
              },
              {
                key: 'discord',
                label: t('Join our Discord'),
                externalHref: 'https://discord.com/invite/sentry',
              },
            ],
          },
          {
            key: 'actions',
            children: [
              {
                key: 'give-feedback',
                label: t('Give feedback'),
                onAction() {
                  openForm?.({
                    tags: {
                      ['feedback.source']: 'navigation_sidebar',
                    },
                  });
                },
                hidden: !openForm,
              },
              {
                key: 'tour',
                label: t('Tour the new navigation'),
                onAction() {
                  startTour();
                },
              },
              {
                key: 'new-ui',
                label: t('Switch to old navigation'),
                onAction() {
                  mutateUserOptions({prefersStackedNavigation: false});
                  trackAnalytics(
                    'navigation.help_menu_opt_out_stacked_navigation_clicked',
                    {
                      organization,
                    }
                  );
                },
              },
              organization?.features?.includes('chonk-ui')
                ? user.options.prefersChonkUI
                  ? {
                      key: 'new-chonk-ui',
                      label: t('Switch to old UI theme'),
                      onAction() {
                        mutateUserOptions({prefersChonkUI: false});
                        trackAnalytics('navigation.help_menu_opt_out_chonk_ui_clicked', {
                          organization,
                        });
                      },
                    }
                  : {
                      key: 'new-chonk-ui',
                      label: t('Try New UI2 Theme'),
                      onAction() {
                        mutateUserOptions({prefersChonkUI: true});
                        trackAnalytics('navigation.help_menu_opt_in_chonk_ui_clicked', {
                          organization,
                        });
                      },
                    }
                : null,
            ].filter(n => !!n),
          },
        ]}
        analyticsKey="help"
        label={t('Help')}
      >
        <IconQuestion />
      </SidebarMenu>
    </StackedNavigationTourReminder>
  );
}

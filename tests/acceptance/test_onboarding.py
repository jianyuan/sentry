from selenium.common.exceptions import TimeoutException

from sentry.models.project import Project
from sentry.testutils.cases import AcceptanceTestCase
from sentry.testutils.silo import no_silo_test
from sentry.utils.retries import TimedRetryPolicy


@no_silo_test
class OrganizationOnboardingTest(AcceptanceTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user("foo@example.com")
        self.org = self.create_organization(name="Rowdy Tiger", owner=None)
        self.team = self.create_team(organization=self.org, name="Mariachi Band")
        self.member = self.create_member(
            user=self.user, organization=self.org, role="owner", teams=[self.team]
        )
        self.login_as(self.user)

    def test_onboarding(self):
        self.browser.get("/onboarding/%s/" % self.org.slug)

        # Welcome step
        self.browser.wait_until('[data-test-id="onboarding-step-welcome"]')
        self.browser.click('[aria-label="Start"]')

        # Platform selection step
        self.browser.wait_until('[data-test-id="onboarding-step-select-platform"]')

        @TimedRetryPolicy.wrap(timeout=5, exceptions=((TimeoutException,)))
        def click_platform_select_name(browser):
            # Select and create React project
            browser.click('[data-test-id="platform-javascript-react"]')

            # Project getting started loads
            browser.wait_until(xpath='//h2[text()="Configure React SDK"]')

        click_platform_select_name(self.browser)

        # Verify project was created for org
        project = Project.objects.get(organization=self.org)
        assert project.name == "javascript-react"
        assert project.platform == "javascript-react"

        # Click on back button
        self.browser.click('[aria-label="Back"]')

        # Assert no deletion confirm dialog is shown
        assert not self.browser.element_exists("[role='dialog']")

        # Platform selection step
        self.browser.wait_until('[data-test-id="onboarding-step-select-platform"]')

        # Select generic platform
        self.browser.click('[data-test-id="platform-javascript"]')

        # Modal is shown prompting to select a framework
        self.browser.wait_until(xpath='//h6[text()="Do you use a framework?"]')

        # Close modal
        self.browser.click('[aria-label="Close Modal"]')

        # Platform is not selected
        assert not self.browser.element_exists('[aria-label="Clear"]')

        # Click again on the modal and continue with the vanilla project
        self.browser.click('[data-test-id="platform-javascript"]')
        self.browser.click('[aria-label="Configure SDK"]')

        # Project getting started loads
        self.browser.wait_until(xpath='//h2[text()="Configure Browser JavaScript SDK"]')

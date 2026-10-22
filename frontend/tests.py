from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from content.models import Content, ContentVersion
from research.models import ResearchProfile


class FrontendPresentationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="frontend@example.com",
            email="frontend@example.com",
            password="testpass123",
        )
        self.other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="testpass123",
        )
        self.content = Content.objects.create(
            owner=self.user,
            title="Review this content",
            topic="Accessibility",
            lifecycle_state="pending_review",
        )
        version = ContentVersion.create_initial_version(self.content, self.user, "Draft body")
        self.content.current_version = version
        self.content.save(update_fields=["current_version"])
        Content.objects.create(owner=self.other_user, title="Other user's content")
        ResearchProfile.get_or_create_for_user(self.user)

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse("frontend:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_dashboard_uses_only_the_authenticated_users_data(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("frontend:dashboard"))
        self.assertContains(response, "Your content workspace")
        self.assertContains(response, "Review this content")
        self.assertNotContains(response, "Other user's content")
        self.assertEqual(response.context["content_total"], 1)
        self.assertEqual(response.context["needs_review_count"], 1)

    def test_content_list_search_and_state_filter_remain_owner_scoped(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("content:list"), {"q": "access", "state": "pending_review"}
        )
        self.assertContains(response, "Review this content")
        self.assertNotContains(response, "Other user's content")

    def test_invalid_research_request_preserves_entered_values(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("research:request_new"),
            {
                "topics": "",
                "specific_query": "Accessible content patterns",
                "audience": "Designers",
                "content_goal": "Practical guide",
                "freshness_days": "14",
                "source_categories": ["news"],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accessible content patterns")
        self.assertContains(response, 'value="Designers"')

    def test_publishing_overview_requires_authentication(self):
        response = self.client.get(reverse("frontend:publishing"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_publishing_overview_renders_user_publications(self):
        from content.models import ContentPublication
        pub = ContentPublication.objects.create(
            content=self.content,
            content_version=self.content.current_version,
            user=self.user,
            profile_id="buf_prof_1",
            profile_name="Twitter Account",
            profile_service="twitter",
            status="scheduled",
            mode="scheduled",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("frontend:publishing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Publishing")
        self.assertContains(response, "Twitter Account")
        self.assertContains(response, "Scheduled")

    def test_help_page_renders_workflow_guide(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("frontend:help"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Help and workflow guide")
        self.assertContains(response, "Start with content or research")

    def test_ai_providers_dashboard_renders_with_design_system(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("ai_providers:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI Providers")
        self.assertContains(response, "Text generation")
        self.assertContains(response, "Image generation")

    def test_content_detail_renders_pipeline_and_evidence(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("content:detail", kwargs={"pk": self.content.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "End-to-End Workflow Pipeline")
        self.assertContains(response, "Review this content")
        self.assertContains(response, "Current Version")

"""Tests for CMO marketing connector clients — Mailchimp, Twitter/X, Semrush,
LinkedIn Ads, TikTok Ads, and Hotjar."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentic_cxo.integrations.live.hotjar_client import HotjarClient
from agentic_cxo.integrations.live.linkedin_ads_client import LinkedInAdsClient
from agentic_cxo.integrations.live.mailchimp_client import MailchimpClient
from agentic_cxo.integrations.live.manager import ConnectorManager
from agentic_cxo.integrations.live.semrush_client import SemrushClient
from agentic_cxo.integrations.live.tiktok_ads_client import TikTokAdsClient
from agentic_cxo.integrations.live.twitter_client import TwitterClient


@pytest.fixture(autouse=True)
def clean_data():
    yield
    for d in [Path(".cxo_data"), Path(".cxo_data/credentials")]:
        if d.exists():
            shutil.rmtree(d)


# ═══════════════════════════════════════════════════════════════
# Mailchimp
# ═══════════════════════════════════════════════════════════════


class TestMailchimpClient:
    def test_connector_id(self):
        client = MailchimpClient()
        assert client.connector_id == "mailchimp"

    def test_required_credentials(self):
        client = MailchimpClient()
        assert "api_key" in client.required_credentials

    def test_data_types(self):
        client = MailchimpClient()
        types = client.available_data_types
        assert "campaigns" in types
        assert "lists" in types
        assert "subscribers" in types
        assert "campaign_report" in types
        assert "automations" in types
        assert "account" in types

    def test_missing_key_fails(self):
        client = MailchimpClient()
        result = client.test_connection({})
        assert not result.success
        assert "required" in result.message.lower()

    def test_base_url_extracts_datacenter(self):
        client = MailchimpClient()
        assert "us21" in client._base_url("abc123-us21")
        assert "us6" in client._base_url("longkey-us6")
        assert "key" in client._base_url("no-dash-key")

    def test_fetch_unknown_type_returns_error(self):
        client = MailchimpClient()
        result = client.fetch({"api_key": "fake-us1"}, "nonexistent")
        assert result.error
        assert "Unknown" in result.error

    def test_fetch_subscribers_requires_list_id(self):
        client = MailchimpClient()
        result = client.fetch({"api_key": "fake-us1"}, "subscribers")
        assert result.error
        assert "list_id" in result.error

    def test_fetch_campaign_report_requires_campaign_id(self):
        client = MailchimpClient()
        result = client.fetch({"api_key": "fake-us1"}, "campaign_report")
        assert result.error
        assert "campaign_id" in result.error

    @patch("agentic_cxo.integrations.live.mailchimp_client.httpx.get")
    def test_test_connection_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "account_name": "TestCo",
            "email": "test@example.com",
        }
        mock_get.return_value = mock_resp

        client = MailchimpClient()
        result = client.test_connection({"api_key": "abc123-us21"})
        assert result.success
        assert "TestCo" in result.message

    @patch("agentic_cxo.integrations.live.mailchimp_client.httpx.get")
    def test_fetch_campaigns(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "campaigns": [
                {
                    "id": "c1",
                    "settings": {"title": "Spring Sale", "subject_line": "50% off!"},
                    "status": "sent",
                    "type": "regular",
                    "send_time": "2026-02-01T10:00:00Z",
                    "emails_sent": 5000,
                    "report_summary": {"open_rate": 0.32, "click_rate": 0.08},
                    "recipients": {"list_id": "list1"},
                }
            ],
            "total_items": 1,
        }
        mock_get.return_value = mock_resp

        client = MailchimpClient()
        data = client.fetch({"api_key": "abc123-us21"}, "campaigns")
        assert not data.error
        assert len(data.records) == 1
        assert data.records[0]["title"] == "Spring Sale"
        assert data.records[0]["open_rate"] == 0.32
        assert "1 campaigns" in data.summary

    @patch("agentic_cxo.integrations.live.mailchimp_client.httpx.get")
    def test_fetch_lists(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "lists": [
                {
                    "id": "lst1",
                    "name": "Newsletter",
                    "stats": {
                        "member_count": 12000,
                        "unsubscribe_count": 150,
                        "open_rate": 0.28,
                        "click_rate": 0.05,
                        "campaign_count": 45,
                    },
                    "date_created": "2024-01-15",
                }
            ]
        }
        mock_get.return_value = mock_resp

        client = MailchimpClient()
        data = client.fetch({"api_key": "abc123-us21"}, "lists")
        assert not data.error
        assert data.records[0]["member_count"] == 12000
        assert data.records[0]["name"] == "Newsletter"

    @patch("agentic_cxo.integrations.live.mailchimp_client.httpx.get")
    def test_fetch_automations(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "automations": [
                {
                    "id": "auto1",
                    "settings": {"title": "Welcome Series"},
                    "status": "active",
                    "emails_sent": 2500,
                    "start_time": "2025-06-01",
                    "recipients": {"recipient_count": 800},
                }
            ]
        }
        mock_get.return_value = mock_resp

        client = MailchimpClient()
        data = client.fetch({"api_key": "abc123-us21"}, "automations")
        assert not data.error
        assert data.records[0]["title"] == "Welcome Series"
        assert data.records[0]["emails_sent"] == 2500


# ═══════════════════════════════════════════════════════════════
# Twitter/X
# ═══════════════════════════════════════════════════════════════


class TestTwitterClient:
    def test_connector_id(self):
        client = TwitterClient()
        assert client.connector_id == "twitter_x"

    def test_required_credentials(self):
        client = TwitterClient()
        assert "bearer_token" in client.required_credentials

    def test_data_types(self):
        client = TwitterClient()
        types = client.available_data_types
        assert "search_recent" in types
        assert "user_tweets" in types
        assert "user_mentions" in types
        assert "user_info" in types
        assert "post_tweet" in types

    def test_missing_token_fails(self):
        client = TwitterClient()
        result = client.test_connection({})
        assert not result.success
        assert "required" in result.message.lower()

    def test_fetch_unknown_type(self):
        client = TwitterClient()
        result = client.fetch({"bearer_token": "fake"}, "nonexistent")
        assert result.error

    def test_search_requires_query(self):
        client = TwitterClient()
        result = client.fetch({"bearer_token": "fake"}, "search_recent")
        assert result.error
        assert "query" in result.error

    def test_user_tweets_requires_user_id(self):
        client = TwitterClient()
        result = client.fetch({"bearer_token": "fake"}, "user_tweets")
        assert result.error
        assert "user_id" in result.error

    def test_user_mentions_requires_user_id(self):
        client = TwitterClient()
        result = client.fetch({"bearer_token": "fake"}, "user_mentions")
        assert result.error
        assert "user_id" in result.error

    def test_user_info_requires_username(self):
        client = TwitterClient()
        result = client.fetch({"bearer_token": "fake"}, "user_info")
        assert result.error
        assert "username" in result.error

    def test_post_tweet_requires_oauth(self):
        client = TwitterClient()
        result = client.fetch({"bearer_token": "fake"}, "post_tweet", text="hello")
        assert result.error
        assert "oauth_access_token" in result.error

    @patch("agentic_cxo.integrations.live.twitter_client.httpx.get")
    def test_search_recent_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "id": "123",
                    "text": "Competitor is down again!",
                    "author_id": "456",
                    "created_at": "2026-02-28T12:00:00Z",
                    "lang": "en",
                    "public_metrics": {
                        "retweet_count": 50,
                        "like_count": 200,
                        "reply_count": 30,
                        "impression_count": 10000,
                    },
                }
            ],
            "meta": {"result_count": 1},
        }
        mock_get.return_value = mock_resp

        client = TwitterClient()
        data = client.fetch(
            {"bearer_token": "fake"}, "search_recent",
            query="competitor outage",
        )
        assert not data.error
        assert len(data.records) == 1
        assert data.records[0]["likes"] == 200
        assert data.records[0]["impressions"] == 10000
        assert "competitor outage" in data.summary

    @patch("agentic_cxo.integrations.live.twitter_client.httpx.get")
    def test_user_info_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "id": "789",
                "username": "acmecorp",
                "name": "Acme Corp",
                "description": "We make everything",
                "public_metrics": {
                    "followers_count": 50000,
                    "following_count": 200,
                    "tweet_count": 3500,
                },
                "verified": True,
                "created_at": "2010-01-01",
            }
        }
        mock_get.return_value = mock_resp

        client = TwitterClient()
        data = client.fetch(
            {"bearer_token": "fake"}, "user_info", username="acmecorp",
        )
        assert not data.error
        assert data.records[0]["followers"] == 50000
        assert data.records[0]["verified"] is True


# ═══════════════════════════════════════════════════════════════
# Semrush
# ═══════════════════════════════════════════════════════════════


class TestSemrushClient:
    def test_connector_id(self):
        client = SemrushClient()
        assert client.connector_id == "semrush"

    def test_required_credentials(self):
        client = SemrushClient()
        assert "api_key" in client.required_credentials

    def test_data_types(self):
        client = SemrushClient()
        types = client.available_data_types
        assert "domain_overview" in types
        assert "domain_organic_keywords" in types
        assert "domain_competitors" in types
        assert "keyword_overview" in types
        assert "backlinks_overview" in types
        assert "api_units" in types

    def test_missing_key_fails(self):
        client = SemrushClient()
        result = client.test_connection({})
        assert not result.success
        assert "required" in result.message.lower()

    def test_fetch_unknown_type(self):
        client = SemrushClient()
        result = client.fetch({"api_key": "fake"}, "nonexistent")
        assert result.error

    def test_domain_overview_requires_domain(self):
        client = SemrushClient()
        result = client.fetch({"api_key": "fake"}, "domain_overview")
        assert result.error
        assert "domain" in result.error

    def test_keyword_overview_requires_keyword(self):
        client = SemrushClient()
        result = client.fetch({"api_key": "fake"}, "keyword_overview")
        assert result.error
        assert "keyword" in result.error

    def test_backlinks_requires_domain(self):
        client = SemrushClient()
        result = client.fetch({"api_key": "fake"}, "backlinks_overview")
        assert result.error
        assert "domain" in result.error

    def test_competitors_requires_domain(self):
        client = SemrushClient()
        result = client.fetch({"api_key": "fake"}, "domain_competitors")
        assert result.error
        assert "domain" in result.error

    def test_organic_keywords_requires_domain(self):
        client = SemrushClient()
        result = client.fetch({"api_key": "fake"}, "domain_organic_keywords")
        assert result.error
        assert "domain" in result.error

    def test_parse_semrush_csv(self):
        client = SemrushClient()
        csv = "Domain;Rank;Organic Keywords\nsemrush.com;1;5000000"
        records = client._parse_semrush_csv(csv)
        assert len(records) == 1
        assert records[0]["Domain"] == "semrush.com"
        assert records[0]["Rank"] == "1"

    def test_parse_empty_csv(self):
        client = SemrushClient()
        assert client._parse_semrush_csv("") == []
        assert client._parse_semrush_csv("Headers Only") == []

    @patch("agentic_cxo.integrations.live.semrush_client.httpx.get")
    def test_fetch_domain_overview(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = (
            "Domain;Rank;Organic Keywords;Organic Traffic;Organic Cost;"
            "Adwords Keywords;Adwords Traffic;Adwords Cost\n"
            "example.com;150;45000;120000;85000;200;5000;3000"
        )
        mock_get.return_value = mock_resp

        client = SemrushClient()
        data = client.fetch(
            {"api_key": "fake"}, "domain_overview", domain="example.com",
        )
        assert not data.error
        assert len(data.records) == 1
        assert data.records[0]["rank"] == "150"
        assert "example.com" in data.summary

    @patch("agentic_cxo.integrations.live.semrush_client.httpx.get")
    def test_fetch_api_units(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "45000"
        mock_get.return_value = mock_resp

        client = SemrushClient()
        data = client.fetch({"api_key": "fake"}, "api_units")
        assert not data.error
        assert data.records[0]["remaining_units"] == "45000"


# ═══════════════════════════════════════════════════════════════
# LinkedIn Ads
# ═══════════════════════════════════════════════════════════════


class TestLinkedInAdsClient:
    def test_connector_id(self):
        client = LinkedInAdsClient()
        assert client.connector_id == "linkedin_ads"

    def test_required_credentials(self):
        client = LinkedInAdsClient()
        assert "access_token" in client.required_credentials
        assert "ad_account_id" in client.required_credentials

    def test_data_types(self):
        client = LinkedInAdsClient()
        types = client.available_data_types
        assert "campaigns" in types
        assert "campaign_analytics" in types
        assert "creatives" in types
        assert "account_info" in types
        assert "audience_counts" in types

    def test_missing_creds_fails(self):
        client = LinkedInAdsClient()
        result = client.test_connection({})
        assert not result.success
        assert "required" in result.message.lower()

    def test_missing_access_token_fails(self):
        client = LinkedInAdsClient()
        result = client.test_connection({"ad_account_id": "123"})
        assert not result.success

    def test_fetch_unknown_type(self):
        client = LinkedInAdsClient()
        result = client.fetch(
            {"access_token": "fake", "ad_account_id": "123"}, "nonexistent"
        )
        assert result.error

    def test_account_urn_formatting(self):
        client = LinkedInAdsClient()
        assert "sponsoredAccount:123" in client._account_urn({"ad_account_id": "123"})
        urn = "urn:li:sponsoredAccount:456"
        assert client._account_urn({"ad_account_id": urn}) == urn

    @patch("agentic_cxo.integrations.live.linkedin_ads_client.httpx.get")
    def test_test_connection_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "name": "TestCo Ads",
            "status": "ACTIVE",
        }
        mock_get.return_value = mock_resp

        client = LinkedInAdsClient()
        result = client.test_connection(
            {"access_token": "fake", "ad_account_id": "123"}
        )
        assert result.success
        assert "TestCo Ads" in result.message

    @patch("agentic_cxo.integrations.live.linkedin_ads_client.httpx.get")
    def test_fetch_campaigns(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "elements": [
                {
                    "id": "camp1",
                    "name": "B2B Lead Gen",
                    "status": "ACTIVE",
                    "type": "TEXT_AD",
                    "objectiveType": "LEAD_GENERATION",
                    "dailyBudget": {"amount": "50.00"},
                    "totalBudget": {"amount": "1500.00"},
                    "costType": "CPC",
                    "changeAuditStamps": {"created": {"time": 1700000000}},
                }
            ]
        }
        mock_get.return_value = mock_resp

        client = LinkedInAdsClient()
        data = client.fetch(
            {"access_token": "fake", "ad_account_id": "123"}, "campaigns"
        )
        assert not data.error
        assert len(data.records) == 1
        assert data.records[0]["name"] == "B2B Lead Gen"
        assert data.records[0]["objective_type"] == "LEAD_GENERATION"

    @patch("agentic_cxo.integrations.live.linkedin_ads_client.httpx.get")
    def test_fetch_account_info(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "123",
            "name": "TestCo Ads",
            "status": "ACTIVE",
            "type": "BUSINESS",
            "currency": "USD",
            "totalBudget": {"amount": "10000"},
        }
        mock_get.return_value = mock_resp

        client = LinkedInAdsClient()
        data = client.fetch(
            {"access_token": "fake", "ad_account_id": "123"}, "account_info"
        )
        assert not data.error
        assert data.records[0]["currency"] == "USD"


# ═══════════════════════════════════════════════════════════════
# TikTok Ads
# ═══════════════════════════════════════════════════════════════


class TestTikTokAdsClient:
    def test_connector_id(self):
        client = TikTokAdsClient()
        assert client.connector_id == "tiktok_ads"

    def test_required_credentials(self):
        client = TikTokAdsClient()
        assert "access_token" in client.required_credentials
        assert "advertiser_id" in client.required_credentials

    def test_data_types(self):
        client = TikTokAdsClient()
        types = client.available_data_types
        assert "campaigns" in types
        assert "ad_groups" in types
        assert "ads" in types
        assert "campaign_report" in types
        assert "advertiser_info" in types

    def test_missing_creds_fails(self):
        client = TikTokAdsClient()
        result = client.test_connection({})
        assert not result.success
        assert "required" in result.message.lower()

    def test_fetch_unknown_type(self):
        client = TikTokAdsClient()
        result = client.fetch(
            {"access_token": "fake", "advertiser_id": "123"}, "nonexistent"
        )
        assert result.error

    @patch("agentic_cxo.integrations.live.tiktok_ads_client.httpx.get")
    def test_test_connection_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": 0,
            "data": {
                "list": [{"name": "TikTok Store", "advertiser_id": "123"}]
            },
        }
        mock_get.return_value = mock_resp

        client = TikTokAdsClient()
        result = client.test_connection(
            {"access_token": "fake", "advertiser_id": "123"}
        )
        assert result.success
        assert "TikTok Store" in result.message

    @patch("agentic_cxo.integrations.live.tiktok_ads_client.httpx.get")
    def test_test_connection_api_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": 40001,
            "message": "Invalid token",
        }
        mock_get.return_value = mock_resp

        client = TikTokAdsClient()
        result = client.test_connection(
            {"access_token": "bad", "advertiser_id": "123"}
        )
        assert not result.success
        assert "Invalid token" in result.message

    @patch("agentic_cxo.integrations.live.tiktok_ads_client.httpx.get")
    def test_fetch_campaigns(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": 0,
            "data": {
                "list": [
                    {
                        "campaign_id": "c1",
                        "campaign_name": "Summer Promo",
                        "operation_status": "ENABLE",
                        "objective_type": "CONVERSIONS",
                        "budget": 500,
                        "budget_mode": "BUDGET_MODE_DAY",
                        "create_time": "2026-01-15",
                    }
                ],
                "page_info": {"total_number": 1},
            },
        }
        mock_get.return_value = mock_resp

        client = TikTokAdsClient()
        data = client.fetch(
            {"access_token": "fake", "advertiser_id": "123"}, "campaigns"
        )
        assert not data.error
        assert len(data.records) == 1
        assert data.records[0]["campaign_name"] == "Summer Promo"
        assert data.records[0]["budget"] == 500

    @patch("agentic_cxo.integrations.live.tiktok_ads_client.httpx.post")
    def test_fetch_campaign_report(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": 0,
            "data": {
                "list": [
                    {
                        "dimensions": {"campaign_id": "c1"},
                        "metrics": {
                            "spend": "150.50",
                            "impressions": "25000",
                            "clicks": "800",
                            "ctr": "3.2",
                            "cpc": "0.19",
                            "conversions": "45",
                            "cost_per_conversion": "3.34",
                        },
                    }
                ]
            },
        }
        mock_post.return_value = mock_resp

        client = TikTokAdsClient()
        data = client.fetch(
            {"access_token": "fake", "advertiser_id": "123"},
            "campaign_report",
            start_date="2026-01-01",
            end_date="2026-02-28",
        )
        assert not data.error
        assert data.records[0]["spend"] == "150.50"
        assert data.records[0]["conversions"] == "45"


# ═══════════════════════════════════════════════════════════════
# Hotjar
# ═══════════════════════════════════════════════════════════════


class TestHotjarClient:
    def test_connector_id(self):
        client = HotjarClient()
        assert client.connector_id == "hotjar"

    def test_required_credentials(self):
        client = HotjarClient()
        assert "api_token" in client.required_credentials
        assert "site_id" in client.required_credentials

    def test_data_types(self):
        client = HotjarClient()
        types = client.available_data_types
        assert "site_info" in types
        assert "heatmaps" in types
        assert "recordings" in types
        assert "funnels" in types
        assert "feedback" in types
        assert "surveys" in types

    def test_missing_creds_fails(self):
        client = HotjarClient()
        result = client.test_connection({})
        assert not result.success
        assert "required" in result.message.lower()

    def test_missing_site_id_fails(self):
        client = HotjarClient()
        result = client.test_connection({"api_token": "fake"})
        assert not result.success

    def test_fetch_unknown_type(self):
        client = HotjarClient()
        result = client.fetch(
            {"api_token": "fake", "site_id": "123"}, "nonexistent"
        )
        assert result.error

    @patch("agentic_cxo.integrations.live.hotjar_client.httpx.get")
    def test_test_connection_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "name": "My Website",
            "id": "123",
        }
        mock_get.return_value = mock_resp

        client = HotjarClient()
        result = client.test_connection({"api_token": "fake", "site_id": "123"})
        assert result.success
        assert "My Website" in result.message

    @patch("agentic_cxo.integrations.live.hotjar_client.httpx.get")
    def test_fetch_heatmaps(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "id": "hm1",
                    "name": "Homepage Click Map",
                    "url": "https://example.com/",
                    "status": "active",
                    "device_type": "desktop",
                    "pageviews": 15000,
                    "created_at": "2026-01-10",
                }
            ]
        }
        mock_get.return_value = mock_resp

        client = HotjarClient()
        data = client.fetch(
            {"api_token": "fake", "site_id": "123"}, "heatmaps"
        )
        assert not data.error
        assert len(data.records) == 1
        assert data.records[0]["pageviews"] == 15000
        assert data.records[0]["name"] == "Homepage Click Map"

    @patch("agentic_cxo.integrations.live.hotjar_client.httpx.get")
    def test_fetch_recordings(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "id": "rec1",
                    "url": "https://example.com/pricing",
                    "duration": 45,
                    "pages_visited": 3,
                    "country": "US",
                    "device": "desktop",
                    "browser": "Chrome",
                    "os": "macOS",
                    "created_at": "2026-02-20",
                    "rage_clicks": 2,
                    "u_turns": 1,
                }
            ]
        }
        mock_get.return_value = mock_resp

        client = HotjarClient()
        data = client.fetch(
            {"api_token": "fake", "site_id": "123"}, "recordings"
        )
        assert not data.error
        assert data.records[0]["rage_clicks"] == 2
        assert data.records[0]["duration"] == 45

    @patch("agentic_cxo.integrations.live.hotjar_client.httpx.get")
    def test_fetch_funnels(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "id": "f1",
                    "name": "Checkout Funnel",
                    "steps": ["/cart", "/checkout", "/confirmation"],
                    "total_visitors": 8000,
                    "conversion_rate": 0.035,
                    "created_at": "2026-01-05",
                }
            ]
        }
        mock_get.return_value = mock_resp

        client = HotjarClient()
        data = client.fetch(
            {"api_token": "fake", "site_id": "123"}, "funnels"
        )
        assert not data.error
        assert data.records[0]["conversion_rate"] == 0.035
        assert data.records[0]["total_visitors"] == 8000

    @patch("agentic_cxo.integrations.live.hotjar_client.httpx.get")
    def test_fetch_feedback(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "id": "fb1",
                    "widget_id": "w1",
                    "emotion": "happy",
                    "message": "Love the new pricing page!",
                    "url": "https://example.com/pricing",
                    "device": "mobile",
                    "country": "UK",
                    "created_at": "2026-02-25",
                }
            ]
        }
        mock_get.return_value = mock_resp

        client = HotjarClient()
        data = client.fetch(
            {"api_token": "fake", "site_id": "123"}, "feedback"
        )
        assert not data.error
        assert data.records[0]["emotion"] == "happy"

    @patch("agentic_cxo.integrations.live.hotjar_client.httpx.get")
    def test_fetch_surveys(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "id": "s1",
                    "name": "NPS Survey",
                    "status": "active",
                    "response_count": 350,
                    "questions": ["How likely are you to recommend us?"],
                    "created_at": "2026-01-20",
                }
            ]
        }
        mock_get.return_value = mock_resp

        client = HotjarClient()
        data = client.fetch(
            {"api_token": "fake", "site_id": "123"}, "surveys"
        )
        assert not data.error
        assert data.records[0]["response_count"] == 350


# ═══════════════════════════════════════════════════════════════
# Manager Integration
# ═══════════════════════════════════════════════════════════════


class TestCMOConnectorsInManager:
    """Verify all 6 new CMO connectors are registered in the manager."""

    def test_mailchimp_registered(self):
        mgr = ConnectorManager()
        assert "mailchimp" in mgr.available_clients
        info = mgr.get_setup_info("mailchimp")
        assert info is not None
        assert "api_key" in info["required_credentials"]
        assert "campaigns" in info["available_data_types"]

    def test_twitter_registered(self):
        mgr = ConnectorManager()
        assert "twitter_x" in mgr.available_clients
        info = mgr.get_setup_info("twitter_x")
        assert info is not None
        assert "bearer_token" in info["required_credentials"]
        assert "search_recent" in info["available_data_types"]

    def test_semrush_registered(self):
        mgr = ConnectorManager()
        assert "semrush" in mgr.available_clients
        info = mgr.get_setup_info("semrush")
        assert info is not None
        assert "api_key" in info["required_credentials"]
        assert "domain_overview" in info["available_data_types"]

    def test_linkedin_ads_registered(self):
        mgr = ConnectorManager()
        assert "linkedin_ads" in mgr.available_clients
        info = mgr.get_setup_info("linkedin_ads")
        assert info is not None
        assert "access_token" in info["required_credentials"]
        assert "campaigns" in info["available_data_types"]

    def test_tiktok_ads_registered(self):
        mgr = ConnectorManager()
        assert "tiktok_ads" in mgr.available_clients
        info = mgr.get_setup_info("tiktok_ads")
        assert info is not None
        assert "access_token" in info["required_credentials"]
        assert "campaigns" in info["available_data_types"]

    def test_hotjar_registered(self):
        mgr = ConnectorManager()
        assert "hotjar" in mgr.available_clients
        info = mgr.get_setup_info("hotjar")
        assert info is not None
        assert "api_token" in info["required_credentials"]
        assert "heatmaps" in info["available_data_types"]

    def test_total_connector_count(self):
        mgr = ConnectorManager()
        assert len(mgr.available_clients) == 32

    def test_status_includes_cmo_connectors(self):
        mgr = ConnectorManager()
        status = mgr.get_status()
        assert status["live_connectors"] == 32
        for cid in ["mailchimp", "twitter_x", "semrush", "linkedin_ads",
                     "tiktok_ads", "hotjar"]:
            assert cid in status["connectors"]
            assert status["connectors"][cid]["implemented"] is True

    def test_connect_missing_fields_mailchimp(self):
        mgr = ConnectorManager()
        result = mgr.connect("mailchimp", {})
        assert not result.success
        assert "missing" in result.message.lower()

    def test_fetch_not_connected(self):
        mgr = ConnectorManager()
        for cid in ["mailchimp", "twitter_x", "semrush", "linkedin_ads",
                     "tiktok_ads", "hotjar"]:
            data = mgr.fetch_data(cid, "campaigns")
            assert data.error
            assert "not connected" in data.error.lower()

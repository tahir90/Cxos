"""
Connector Manager — handles the full connect/test/fetch lifecycle.

The wizard flow:
1. User picks a connector from the registry
2. Manager shows required credentials
3. User enters credentials
4. Manager calls test_connection() — validates with a real API call
5. On success: stores credentials, marks as connected
6. Agent can now fetch live data from this connector
"""

from __future__ import annotations

import logging
from typing import Any

from agentic_cxo.integrations.live.ads_clients import GoogleAdsClient, MetaAdsClient
from agentic_cxo.integrations.live.analytics_clients import (
    AvalaraClient,
    IntercomClient,
    WebhooksClient,
    ZendeskClient,
)
from agentic_cxo.integrations.live.appstore_clients import (
    AppleAppStoreClient,
    FirebaseClient,
    GooglePlayClient,
)
from agentic_cxo.integrations.live.base import (
    BaseConnectorClient,
    ConnectionResult,
    ConnectorData,
    CredentialStore,
)
from agentic_cxo.integrations.live.chargebee_client import ChargebeeClient
from agentic_cxo.integrations.live.cmo_clients import (
    CloudinaryClient,
    ContentfulClient,
    CustomerIOClient,
    G2Client,
    KlaviyoClient,
    LinkedInAdsClient,
    MailchimpClient,
    SegmentClient,
    SemrushClient,
    TikTokAdsClient,
    TrustpilotClient,
    TwitterClient,
    TypeformClient,
    WordPressClient,
)
from agentic_cxo.integrations.live.cmo_write_clients import (
    AmplitudeRealClient,
    DalleClient,
    MailchimpWriteClient,
    MetaAdsWriteClient,
    MixpanelRealClient,
    NanoBananaClient,
    TwitterWriteClient,
)
from agentic_cxo.integrations.live.cso_clients import (
    CalendlyClient,
    CloseCRMClient,
    GongClient,
    OutreachClient,
    PandaDocClient,
    PipedriveClient,
)
from agentic_cxo.integrations.live.drive_client import (
    GoogleDriveClient,
    OneDriveClient,
)
from agentic_cxo.integrations.live.ga4_client import GA4Client
from agentic_cxo.integrations.live.github_client import (
    BitbucketClient,
    GitHubClient,
)
from agentic_cxo.integrations.live.gmail_client import GmailClient
from agentic_cxo.integrations.live.hubspot_client import HubSpotClient
from agentic_cxo.integrations.live.jira_client import JiraClient
from agentic_cxo.integrations.live.notion_client import NotionClient
from agentic_cxo.integrations.live.quickbooks_client import QuickBooksClient
from agentic_cxo.integrations.live.salesforce_client import SalesforceClient
from agentic_cxo.integrations.live.shopify_client import ShopifyClient
from agentic_cxo.integrations.live.slack_client import SlackClient
from agentic_cxo.integrations.live.stripe_client import StripeClient

logger = logging.getLogger(__name__)


LIVE_CLIENTS: dict[str, BaseConnectorClient] = {
    # Original 6
    "slack": SlackClient(),
    "stripe": StripeClient(),
    "github": GitHubClient(),
    "bitbucket": BitbucketClient(),
    "google_drive": GoogleDriveClient(),
    "onedrive": OneDriveClient(),
    # Tier 1 (12)
    "gmail": GmailClient(),
    "hubspot": HubSpotClient(),
    "jira": JiraClient(),
    "notion": NotionClient(),
    "shopify": ShopifyClient(),
    "chargebee": ChargebeeClient(),
    # mixpanel and amplitude replaced by real clients below
    "zendesk": ZendeskClient(),
    "intercom": IntercomClient(),
    "avalara": AvalaraClient(),
    "webhooks": WebhooksClient(),
    # Tier 2 (7)
    "ga4": GA4Client(),
    "google_ads": GoogleAdsClient(),
    "meta_ads": MetaAdsClient(),
    "salesforce": SalesforceClient(),
    "quickbooks": QuickBooksClient(),
    "apple_app_store": AppleAppStoreClient(),
    "google_play": GooglePlayClient(),
    "firebase": FirebaseClient(),
    # CMO Production
    "mailchimp": MailchimpClient(),
    "klaviyo": KlaviyoClient(),
    "segment": SegmentClient(),
    "semrush": SemrushClient(),
    "tiktok_ads": TikTokAdsClient(),
    "linkedin_ads": LinkedInAdsClient(),
    "trustpilot": TrustpilotClient(),
    "g2": G2Client(),
    "typeform": TypeformClient(),
    "contentful": ContentfulClient(),
    "wordpress": WordPressClient(),
    "twitter_x": TwitterClient(),
    "customer_io": CustomerIOClient(),
    "cloudinary": CloudinaryClient(),
    # CMO Write + Execute
    "dalle": DalleClient(),
    "nano_banana": NanoBananaClient(),
    "mailchimp_write": MailchimpWriteClient(),
    "twitter_write": TwitterWriteClient(),
    "meta_ads_write": MetaAdsWriteClient(),
    "mixpanel": MixpanelRealClient(),
    "amplitude": AmplitudeRealClient(),
    # CSO Production
    "pipedrive": PipedriveClient(),
    "close_crm": CloseCRMClient(),
    "gong": GongClient(),
    "outreach": OutreachClient(),
    "calendly": CalendlyClient(),
    "pandadoc": PandaDocClient(),
}


class ConnectorManager:
    """Manages live connector connections, credentials, and data fetching."""

    def __init__(self) -> None:
        self.cred_store = CredentialStore()
        self.clients = dict(LIVE_CLIENTS)

    def get_setup_info(self, connector_id: str) -> dict[str, Any] | None:
        """Get what's needed to connect a connector."""
        client = self.clients.get(connector_id)
        if not client:
            return None
        return {
            "connector_id": connector_id,
            "required_credentials": client.required_credentials,
            "available_data_types": client.available_data_types,
            "is_connected": self.cred_store.is_connected(connector_id),
        }

    def connect(
        self, connector_id: str, credentials: dict[str, str]
    ) -> ConnectionResult:
        """Test credentials and store on success."""
        client = self.clients.get(connector_id)
        if not client:
            return ConnectionResult(
                False, f"No live client for '{connector_id}'. "
                "This connector is defined but not yet implemented."
            )

        missing = [
            f for f in client.required_credentials
            if not credentials.get(f)
        ]
        if missing:
            return ConnectionResult(
                False,
                f"Missing required fields: {', '.join(missing)}",
            )

        result = client.test_connection(credentials)

        if result.success:
            self.cred_store.save(connector_id, credentials)
            logger.info("Connector %s connected successfully", connector_id)

        return result

    def disconnect(self, connector_id: str) -> bool:
        self.cred_store.delete(connector_id)
        return True

    def fetch_data(
        self,
        connector_id: str,
        data_type: str,
        **kwargs: Any,
    ) -> ConnectorData:
        """Fetch live data from a connected connector."""
        client = self.clients.get(connector_id)
        if not client:
            return ConnectorData(
                connector_id, data_type,
                error=f"No live client for '{connector_id}'",
            )

        creds = self.cred_store.load(connector_id)
        if not creds:
            return ConnectorData(
                connector_id, data_type,
                error=f"Connector '{connector_id}' not connected. "
                "Go to Settings to connect it.",
            )

        return client.fetch(creds, data_type, **kwargs)

    def get_status(self) -> dict[str, Any]:
        """Get connection status for all live connectors."""
        statuses: dict[str, Any] = {}
        for cid, client in self.clients.items():
            statuses[cid] = {
                "implemented": True,
                "connected": self.cred_store.is_connected(cid),
                "data_types": client.available_data_types,
            }
        return {
            "live_connectors": len(self.clients),
            "connected": len(self.cred_store.list_connected()),
            "connectors": statuses,
        }

    @property
    def connected_ids(self) -> list[str]:
        return self.cred_store.list_connected()

    @property
    def available_clients(self) -> list[str]:
        return list(self.clients.keys())

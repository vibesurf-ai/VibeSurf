import json
from typing import Any, List, Dict
from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import DropdownInput, MessageTextInput, IntInput, MultiselectInput
from vibe_surf.langflow.io import Output
from vibe_surf.langflow.schema.data import Data
from vibe_surf.tools.website_api.newsnow.client import global_client

class NewsNowComponent(Component):
    display_name = "NewsNow"
    description = "Fetch hot and real-time news from various sources."
    icon = "newspaper"

    inputs = [
        DropdownInput(
            name="source_category",
            display_name="Source Category",
            options=["hottest", "realtime", "all"],
            value="hottest",
            real_time_refresh=True,
        ),
        MultiselectInput(
            name="sources",
            display_name="Sources",
            options=["ALL"],
            value=["ALL"],
            info="Select sources (updates based on category)",
        ),
        IntInput(
            name="count",
            display_name="Count",
            value=10,
            info="Number of items per source",
        ),
        MessageTextInput(
            name="key_words",
            display_name="Keywords",
            info="Filter news by keywords (comma separated)",
        ),
    ]

    outputs = [
        Output(
            display_name="News Result",
            name="result",
            method="fetch_news",
            types=["Data"],
        )
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None):
        if field_name == "source_category":
            category = field_value
            options = ["ALL"]
            
            # Get available sources based on category
            news_type = category if category in ["hottest", "realtime"] else None
            available_sources = global_client.get_available_sources(news_type=news_type)
            
            # Add source IDs to options
            source_ids = list(available_sources.keys())
            source_ids.sort()
            options.extend(source_ids)
            
            build_config["sources"]["options"] = options
            
            # Reset value to ALL if current value is invalid or just strictly to ALL on category change
            # build_config["sources"]["value"] = ["ALL"] 
            
        return build_config

    async def fetch_news(self) -> Data:
        selected_sources = self.sources
        sources_to_fetch = []

        # Determine which sources to fetch
        if "ALL" in selected_sources:
            if self.source_category == "hottest":
                sources_to_fetch = global_client.HOTTEST_SOURCES
            elif self.source_category == "realtime":
                sources_to_fetch = global_client.REALTIME_SOURCES
            else:
                sources_to_fetch = global_client.HOTTEST_SOURCES + global_client.REALTIME_SOURCES
        else:
            sources_to_fetch = selected_sources

        # Fetch news
        # fetch_news_batch takes a list of source IDs
        results = await global_client.fetch_news_batch(sources_to_fetch)
        
        # Limit items per source
        if self.count > 0:
            for sid in results:
                results[sid] = results[sid][:self.count]

        # Filter by keywords
        if self.key_words:
            keywords = [kw.strip().lower() for kw in self.key_words.split(',') if kw.strip()]
            if keywords:
                filtered_results = {}
                for source_id, news_items in results.items():
                    filtered_items = []
                    for item in news_items:
                        # Simple search in item string representation
                        # Remove url for search
                        item_copy = item.copy()
                        if 'url' in item_copy:
                            del item_copy['url']
                        if 'id' in item_copy:
                            del item_copy['id']
                        if 'mobileUrl' in item_copy:
                            del item_copy['mobileUrl']
                        item_str = json.dumps(item_copy, ensure_ascii=False).lower()
                        if any(keyword in item_str for keyword in keywords):
                            filtered_items.append(item)
                    
                    if filtered_items:
                        filtered_results[source_id] = filtered_items
                results = filtered_results

        return Data(data=results)
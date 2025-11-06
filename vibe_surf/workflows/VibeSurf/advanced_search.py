import asyncio
import json
from typing import Any, List, Dict
from uuid import uuid4

from vibe_surf.langflow.custom import Component
from vibe_surf.langflow.inputs import MessageTextInput, HandleInput, IntInput
from vibe_surf.langflow.io import BoolInput, Output
from vibe_surf.langflow.schema.dataframe import DataFrame
from browser_use.llm.base import BaseChatModel
from vibe_surf.tools.utils import fallback_parallel_search, google_ai_model_search, _rank_search_results_with_llm
from vibe_surf.logger import get_logger

logger = get_logger(__name__)


class AdvancedSearchComponent(Component):
    display_name = "Advanced Search"
    description = "Advanced search component that can use Google AI model search or fallback parallel search with optional LLM reranking"
    icon = "search"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The search query to execute",
            required=True,
        ),
        BoolInput(
            name="google_ai_mode",
            display_name="Use Google AI Mode",
            value=True,
            info="Whether to use Google AI model search instead of fallback parallel search",
        ),
        BoolInput(
            name="rerank",
            display_name="Rerank Results",
            value=False,
            advanced=True,
            required=False,
            info="Whether to rerank search results using LLM for better relevance",
        ),
        HandleInput(
            name="llm",
            display_name="LLM Model",
            info="LLM Model for reranking results (required when rerank is enabled)",
            input_types=["BaseChatModel"],
            required=False,
            advanced=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="Maximum number of search results to return",
            value=100,
            advanced=True,
            required=False,
        )
    ]

    outputs = [
        Output(
            display_name="Search Results",
            name="search_results",
            method="run_advanced_search",
            types=["DataFrame"],
        ),
    ]

    async def run_advanced_search(self) -> DataFrame:
        try:
            from vibe_surf.backend import shared_state
            
            # Validate inputs
            if self.rerank and not self.llm:
                raise ValueError("LLM is required when rerank is enabled")
            
            # Get browser manager from shared state
            browser_manager = shared_state.browser_manager
            
            # Execute search based on mode
            if self.google_ai_mode:
                logger.info(f"Executing Google AI model search for query: {self.query}")
                search_results = await google_ai_model_search(
                    browser_manager=browser_manager,
                    query=self.query,
                    max_results=self.max_results
                )
            else:
                logger.info(f"Executing fallback parallel search for query: {self.query}")
                search_results = await fallback_parallel_search(
                    browser_manager=browser_manager,
                    query=self.query,
                    max_results=self.max_results
                )
            
            # Rerank results if requested
            if self.rerank and self.llm and search_results:
                logger.info("Reranking search results using LLM")
                search_results = await _rank_search_results_with_llm(
                    results=search_results,
                    query=self.query,
                    llm=self.llm
                )
            
            # Convert results to DataFrame format
            if not search_results:
                logger.warning("No search results found")
                return DataFrame(
                    data=[],
                    columns=['title', 'url', 'summary', 'source', 'source_tab']
                )
            
            # Prepare data for DataFrame
            df_data = []
            for result in search_results:
                row = {
                    'title': result.get('title', 'No title'),
                    'url': result.get('url', 'No URL'),
                    'summary': result.get('summary', 'No description available'),
                    'source': result.get('source', 'Unknown source'),
                    'source_tab': result.get('source_tab', 'unknown'),
                }
                
                # Add optional fields if they exist
                if 'time' in result:
                    row['time'] = result['time']
                if 'duration' in result:
                    row['duration'] = result['duration']
                if 'extraction_method' in result:
                    row['extraction_method'] = result['extraction_method']
                
                df_data.append(row)
            
            # Determine columns based on available data
            columns = ['title', 'url', 'summary', 'source', 'source_tab']
            if any('time' in result for result in search_results):
                columns.append('time')
            if any('duration' in result for result in search_results):
                columns.append('duration')
            if any('extraction_method' in result for result in search_results):
                columns.append('extraction_method')
            
            logger.info(f"Returning {len(df_data)} search results as DataFrame")
            
            return DataFrame(
                data=df_data,
                columns=columns
            )
            
        except Exception as e:
            logger.error(f"Advanced search failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Return error DataFrame
            return DataFrame(
                data=[{
                    'title': 'Search Error',
                    'url': 'N/A',
                    'summary': f'Search failed with error: {str(e)}',
                    'source': 'Error',
                    'source_tab': 'error'
                }],
                columns=['title', 'url', 'summary', 'source', 'source_tab']
            )
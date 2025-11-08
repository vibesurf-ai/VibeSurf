import ast
import pprint
from enum import Enum

import yfinance as yf
from langchain_core.tools import ToolException
from pydantic import BaseModel, Field
from vibe_surf.langflow.schema.message import Message
from vibe_surf.langflow.custom.custom_component.component import Component
from vibe_surf.langflow.inputs.inputs import DropdownInput, IntInput, MessageTextInput
from vibe_surf.langflow.io import Output
from vibe_surf.langflow.logging.logger import logger
from vibe_surf.langflow.schema.data import Data
from vibe_surf.langflow.schema.dataframe import DataFrame
from vibe_surf.tools.finance_tools import FinanceMethod, FinanceDataRetriever


class YahooFinanceSchema(BaseModel):
    symbol: str = Field(..., description="The stock symbol to retrieve data for.")
    method: FinanceMethod = Field(FinanceMethod.GET_INFO, description="The type of data to retrieve.")
    num_news: int | None = Field(5, description="The number of news articles to retrieve.")
    start_date: str | None = Field(None, description="The start date to retrieve data for.")
    end_date: str | None = Field(None, description="The end date to retrieve data for.")
    period: str | None = Field('1y', description="The period to retrieve data for.")
    interval: str | None = Field('1d', description="The interval to retrieve data for.")


class YfinanceComponent(Component):
    display_name = "Yahoo! Finance"
    description = """Uses [yfinance](https://pypi.org/project/yfinance/) (unofficial package) \
to access financial data and market information from Yahoo! Finance."""
    icon = "trending-up"

    inputs = [
        MessageTextInput(
            name="symbol",
            display_name="Stock Symbol",
            info="The stock symbol to retrieve data for (e.g., AAPL, GOOG).",
            tool_mode=True,
        ),
        DropdownInput(
            name="method",
            display_name="Data Method",
            info="The type of data to retrieve.",
            options=list(FinanceMethod),
            value="get_news",
        ),
        IntInput(
            name="num_news",
            display_name="Number of News",
            info="The number of news articles to retrieve (only applicable for GET_NEWS).",
            value=5,
            advanced=True
        ),
        MessageTextInput(
            name="period",
            display_name="Period",
            info="Time period for historical data (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max). (only applicable for GET_HISTORY)",
            value='1mo',
            advanced=True
        ),
        MessageTextInput(
            name="start_date",
            display_name="Start Date",
            info="Start date for historical data (YYYY-MM-DD format). Use with end_date instead of period. (only applicable for GET_HISTORY)",
            advanced=True
        ),
        MessageTextInput(
            name="end_date",
            display_name="End Date",
            info="End date for historical data (YYYY-MM-DD format). Use with start_date instead of period. (only applicable for GET_HISTORY)",
            advanced=True

        ),
        MessageTextInput(
            name="interval",
            display_name="Interval",
            info="Data interval for historical data (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo). (only applicable for GET_HISTORY)",
            advanced=True,
            value='1d'
        )
    ]

    outputs = [
        Output(display_name="FinanceResult", name="finance_result", method="fetch_yfinance_data"),
    ]

    def fetch_yfinance_data(self) -> Message:
        try:
            retriever = FinanceDataRetriever(self.symbol)
            if self.method == FinanceMethod.GET_NEWS:
                result = retriever._get_news(num_news=self.num_news)
            elif self.method == FinanceMethod.GET_HISTORY:
                result = retriever._get_history(period=self.period, interval=self.interval, start_date=self.start_date,
                                                end_date=self.end_date)
            else:
                result = getattr(retriever, f"_{self.method}")()
            return Message(text=pprint.pformat(result))
        except Exception as e:
            error_message = f"Error retrieving data: {e}"
            logger.debug(error_message)
            self.status = error_message
            raise ToolException(error_message) from e
